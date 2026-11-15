"""Unit and smoke tests for Dots and Boxes game logic, AI, and Pygame UI."""

from __future__ import annotations

import os
import unittest

import pygame

from ai import DotsAndBoxesAI
from game_logic import AI, DRAW, HUMAN, DotsAndBoxesState


class TestGameLogic(unittest.TestCase):
    def test_initial_counts(self) -> None:
        for size, expected_edges in ((3, 24), (4, 40), (5, 60)):
            state = DotsAndBoxesState(size, size)
            self.assertEqual(len(state.get_valid_moves()), expected_edges)
            self.assertEqual(state.total_edges, expected_edges)
            self.assertEqual(state.total_boxes, size * size)
            self.assertFalse(state.is_game_over())
            self.assertIsNone(state.get_winner())

    def test_turn_switch_and_bonus_turn(self) -> None:
        state = DotsAndBoxesState(3, 3, starting_player=HUMAN)
        # Draw 3 sides of top-left box (0, 0) alternating turns
        self.assertEqual(state.make_move(("h", 0, 0)), 0)
        self.assertEqual(state.current_player, AI)

        self.assertEqual(state.make_move(("v", 0, 0)), 0)
        self.assertEqual(state.current_player, HUMAN)

        self.assertEqual(state.make_move(("h", 1, 0)), 0)
        self.assertEqual(state.current_player, AI)

        # AI draws 4th side -> scores 1 and keeps turn
        self.assertEqual(state.make_move(("v", 0, 1)), 1)
        self.assertEqual(state.scores[AI], 1)
        self.assertEqual(state.boxes[0][0], AI)
        self.assertEqual(state.current_player, AI)

    def test_double_box_completion(self) -> None:
        state = DotsAndBoxesState(2, 2, starting_player=HUMAN)
        # Surround (0,0) and (0,1) except the shared edge ("v", 0, 1)
        for m in (
            ("h", 0, 0),
            ("h", 1, 0),
            ("v", 0, 0),
            ("h", 0, 1),
            ("h", 1, 1),
            ("v", 0, 2),
        ):
            state.make_move(m)

        scorer = state.current_player
        gained = state.make_move(("v", 0, 1))
        self.assertEqual(gained, 2)
        self.assertEqual(state.scores[scorer], 2)
        self.assertEqual(state.current_player, scorer)

    def test_undo_to_human_turn(self) -> None:
        state = DotsAndBoxesState(3, 3, starting_player=HUMAN)
        state.make_move(("h", 0, 0))
        state.make_move(("h", 0, 1))  # AI move
        self.assertEqual(state.current_player, HUMAN)
        self.assertEqual(state.edges_drawn, 2)

        undone = state.undo_to_human_turn()
        self.assertTrue(undone)
        self.assertEqual(state.edges_drawn, 0)
        self.assertEqual(state.current_player, HUMAN)

    def test_full_game_draw(self) -> None:
        state = DotsAndBoxesState(2, 2, starting_player=HUMAN)
        while not state.is_game_over():
            state.make_move(state.get_valid_moves()[0])
        self.assertTrue(state.is_game_over())
        self.assertEqual(state.scores[HUMAN] + state.scores[AI], 4)
        self.assertIn(state.get_winner(), (HUMAN, AI, DRAW))


class TestAI(unittest.TestCase):
    def test_all_difficulties_return_legal_moves(self) -> None:
        for diff in ("easy", "medium", "hard"):
            ai = DotsAndBoxesAI(diff, seed=42)  # type: ignore[arg-type]
            for size in (3, 4, 5):
                state = DotsAndBoxesState(size, size, starting_player=AI)
                move = ai.choose_move(state)
                self.assertIn(move, state.get_valid_moves())

    def test_medium_and_hard_take_free_box(self) -> None:
        for diff in ("medium", "hard"):
            state = DotsAndBoxesState(3, 3, starting_player=HUMAN)
            state.make_move(("h", 0, 0))
            state.make_move(("v", 0, 0))
            state.make_move(("h", 1, 0))
            # Now AI can capture (0, 0) via ("v", 0, 1)
            self.assertEqual(state.current_player, AI)
            ai = DotsAndBoxesAI(diff, seed=1)  # type: ignore[arg-type]
            move = ai.choose_move(state)
            self.assertEqual(move, ("v", 0, 1))

    def test_hard_avoids_risky_move_when_safe_moves_exist(self) -> None:
        s = DotsAndBoxesState(3, 3, starting_player=AI)
        s.make_move(("h", 0, 0))
        s.make_move(("v", 0, 0))
        # Now (0,0) has 2 sides; ("h", 1, 0) and ("v", 0, 1) are risky.
        ai = DotsAndBoxesAI("hard", seed=7)
        move = ai.choose_move(s)
        self.assertNotIn(move, {("h", 1, 0), ("v", 0, 1)})

    def test_hard_prefers_smaller_sacrifice_when_forced(self) -> None:
        s = DotsAndBoxesState(3, 3, starting_player=AI)
        # Claim boxes in rows 1 and 2 except (2,2), leaving (2,2) as a 1-box sacrifice
        # and row 0 as a 3-box chain.
        setup_edges = [
            # Row 0 horizontal walls
            ("h", 0, 0), ("h", 0, 1), ("h", 0, 2),
            ("h", 1, 0), ("h", 1, 1), ("h", 1, 2),
            # Row 1 & 2 claimed boxes: (1,0), (1,1), (1,2), (2,0), (2,1)
            ("v", 1, 0), ("v", 1, 1), ("v", 1, 2), ("v", 1, 3),
            ("h", 2, 0), ("h", 2, 1), ("h", 2, 2),
            ("v", 2, 0), ("v", 2, 1), ("v", 2, 2),
            ("h", 3, 0), ("h", 3, 1),
        ]
        for m in setup_edges:
            s.make_move(m)
        s.current_player = AI
        # Remaining moves: 4 edges in 3-box chain (row 0) vs 2 outer edges on (2,2) (1-box sacrifice)
        ai = DotsAndBoxesAI("hard", seed=3)
        move = ai.choose_move(s)
        self.assertIn(move, {("h", 3, 2), ("v", 2, 3)})


class TestPygameSmoke(unittest.TestCase):
    def test_app_initializes_and_renders_headless(self) -> None:
        os.environ["SDL_VIDEODRIVER"] = "dummy"
        from main import DotsAndBoxesApp

        app = DotsAndBoxesApp()
        app._draw_header()
        app._draw_board()
        app._draw_sidebar()
        pygame.quit()

    def test_pvp_mode_switch_and_move(self) -> None:
        os.environ["SDL_VIDEODRIVER"] = "dummy"
        from main import DotsAndBoxesApp

        app = DotsAndBoxesApp()
        app.mode = "pvp"
        app._build_buttons()
        app._reset_game()

        self.assertEqual(app.state.current_player, HUMAN)
        app._apply_human_move(("h", 0, 0))
        # In PvP, turn passes to Player 2 (represented by AI constant 2)
        self.assertEqual(app.state.current_player, AI)
        self.assertEqual(app.edge_owners[("h", 0, 0)], HUMAN)

        # Player 2 applies move
        app._apply_human_move(("h", 0, 1))
        self.assertEqual(app.state.current_player, HUMAN)
        self.assertEqual(app.edge_owners[("h", 0, 1)], AI)
        pygame.quit()

    def test_eve_mode_step_and_moves(self) -> None:
        os.environ["SDL_VIDEODRIVER"] = "dummy"
        from main import DotsAndBoxesApp

        app = DotsAndBoxesApp()
        app.mode = "eve"
        app.eve_paused = True
        app._build_buttons()
        app._reset_game()

        # Step 1 move in paused AI vs AI mode
        app._step_eve()
        self.assertEqual(app.state.edges_drawn, 1)
        self.assertEqual(len(app.last_ai_moves), 1)
        pygame.quit()

    def test_ai_analysis_telemetry_and_sidebar(self) -> None:
        """Verify AI analysis step generation, position evaluation, and sidebar UI."""
        os.environ["SDL_VIDEODRIVER"] = "dummy"
        os.environ["SDL_AUDIODRIVER"] = "dummy"
        from ai import analyze_position
        from main import DotsAndBoxesApp
        pygame.init()

        app = DotsAndBoxesApp()
        self.assertEqual(app.app_state, "setup")

        # Test setup card clicks
        for card in app.setup_cards:
            app._handle_setup_click((card.rect.centerx, card.rect.centery))

        # Start game
        app._handle_setup_click((app.start_game_btn.rect.centerx, app.start_game_btn.rect.centery))
        self.assertEqual(app.app_state, "game")

        # Verify live position analysis telemetry
        analysis = analyze_position(app.state, my_player=AI)
        self.assertIn("steps", analysis)
        self.assertGreaterEqual(len(analysis["steps"]), 4)
        self.assertIn("eval_score", analysis)
        self.assertIn("valid_count", analysis)

        # Let AI choose a move and verify AI analysis steps
        ai_move = app.ai.choose_move(app.state)
        self.assertIsNotNone(ai_move)
        self.assertIn("steps", app.ai.last_analysis)
        self.assertGreaterEqual(len(app.ai.last_analysis["steps"]), 4)
        self.assertIn("tactic", app.ai.last_analysis)
        self.assertIn("depth", app.ai.last_analysis)
        self.assertIn("nodes", app.ai.last_analysis)

        # Verify sidebar drawing with AI analysis panel
        app._draw_sidebar()
        pygame.quit()


if __name__ == "__main__":
    unittest.main()
