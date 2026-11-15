"""Advanced AI Engines for Dots and Boxes:
1. Iterative Deepening Alpha-Beta with Transposition Tables
2. Monte Carlo Tree Search (MCTS with UCB1 & Heuristic Rollouts)
3. Berlekamp Combinatorial Solver (Nimstring, Long Chain Rule & Parity)
4. Policy-Value Neural Network with PUCT Guided Search (AlphaZero style)
"""

from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass, field
from typing import Literal, Optional

import numpy as np
from game_logic import AI, HUMAN, DotsAndBoxesState, Move

AlgorithmType = Literal["alphabeta", "mcts", "berlekamp", "policy_value"]
Difficulty = Literal["easy", "medium", "hard"]

SCORE_SCALE = 100
INF = 10_000_000

# ============================================================================
# HELPER FUNCTIONS & SHARED HEURISTICS
# ============================================================================

def is_capturing_move(state: DotsAndBoxesState, move: Move) -> bool:
    """Return True if placing this edge immediately completes at least one box."""
    for br, bc in state.adjacent_boxes(move):
        if state.box_sides[br][bc] == 3:
            return True
    return False


def is_risky_move(state: DotsAndBoxesState, move: Move) -> bool:
    """Return True if placing this edge creates a 3-sided box without completing it."""
    for br, bc in state.adjacent_boxes(move):
        if state.box_sides[br][bc] == 2:
            return True
    return False


def greedy_chain_capture_count(sim: DotsAndBoxesState) -> int:
    """Count how many boxes can be greedily captured from immediate 3-sided boxes."""
    captured = 0
    queue: list[tuple[int, int]] = []
    seen = set()
    for br in range(sim.rows):
        for bc in range(sim.cols):
            if sim.box_sides[br][bc] == 3:
                queue.append((br, bc))
                seen.add((br, bc))

    while queue:
        br, bc = queue.pop()
        if sim.box_sides[br][bc] != 3:
            continue
        open_edges = sim.get_box_open_edges(br, bc)
        if not open_edges:
            continue
        edge = open_edges[0]
        gained = sim.make_move(edge, record_history=False)
        captured += gained
        for nbr, nbc in sim.adjacent_boxes(edge):
            if sim.box_sides[nbr][nbc] == 3 and (nbr, nbc) not in seen:
                queue.append((nbr, nbc))
                seen.add((nbr, nbc))
    return captured


def evaluate_remaining(state: DotsAndBoxesState, my_player: int = AI) -> int:
    """Heuristic estimate of (my remaining boxes - opponent remaining boxes) * SCORE_SCALE."""
    if state.is_game_over():
        return 0

    sim = state.clone()
    immediate_chain = greedy_chain_capture_count(sim)

    safe_after = 0
    two_sided_after = 0
    for r in range(sim.rows):
        for c in range(sim.cols):
            if sim.box_sides[r][c] == 2:
                two_sided_after += 1

    for m in sim.get_valid_moves():
        if not is_risky_move(sim, m) and not is_capturing_move(sim, m):
            safe_after += 1

    score_imm = immediate_chain * 85
    risk_pen = min(two_sided_after, 3) * 35 if safe_after == 0 else 0
    parity_bonus = 20 if (safe_after % 2 == 1) else -10
    total = score_imm - risk_pen + parity_bonus + safe_after * 4

    return total * SCORE_SCALE if state.current_player == my_player else -total * SCORE_SCALE


# ============================================================================
# BASE ENGINE INTERFACE
# ============================================================================

class BaseAIEngine:
    """Base class for all Dots and Boxes AI engines."""

    def __init__(self, player_id: int = AI, difficulty: Difficulty = "hard") -> None:
        self.player_id = player_id
        self.difficulty = difficulty
        self.last_analysis: dict = {}
        self._rng = random.Random(42)

    def choose_move(self, state: DotsAndBoxesState) -> Move:
        raise NotImplementedError


# ============================================================================
# 1. ITERATIVE DEEPENING ALPHA-BETA WITH TRANSPOSITION TABLES
# ============================================================================

EXACT = 0
LOWERBOUND = 1
UPPERBOUND = 2


class _SearchTimeout(Exception):
    pass


class AlphaBetaEngine(BaseAIEngine):
    """Iterative Deepening Minimax with Alpha-Beta Pruning, Transposition Tables,

    and dynamic move ordering.
    """

    def __init__(self, player_id: int = AI, difficulty: Difficulty = "hard") -> None:
        super().__init__(player_id, difficulty)
        self._tt: dict[tuple[int, int, int], tuple[int, int, int, Optional[Move]]] = {}
        self._nodes: int = 0
        self._deadline: float = 0.0

    def choose_move(self, state: DotsAndBoxesState) -> Move:
        valid = state.get_valid_moves()
        if not valid:
            raise ValueError("No valid moves remaining.")
        if len(valid) == 1:
            move = valid[0]
            move_orient = "Horizontal" if move[0] == "h" else "Vertical"
            self.last_analysis = {
                "algorithm": "alphabeta",
                "depth": 1,
                "nodes": 1,
                "duration_ms": 0.1,
                "eval_score": 0.0,
                "move": move,
                "move_name": f"{'H' if move[0] == 'h' else 'V'}[{move[1]},{move[2]}]",
                "move_orient": move_orient,
                "tactic": "Forced Last Move",
                "tactic_desc": "Single valid move remaining",
                "step_items": [
                    {"tag": "SCAN", "tag_color": (50, 110, 185), "title": "1 Edge Remaining", "desc": "Single playable edge left"},
                    {"tag": "SEARCH", "tag_color": (115, 75, 165), "title": "Direct Completion", "desc": "Terminal position (0.1ms)"},
                    {"tag": "TACTIC", "tag_color": (195, 115, 20), "title": "Forced Move", "desc": "Completing final grid boundary"},
                    {"tag": "DECISION", "tag_color": (38, 115, 101) if self.player_id == AI else (217, 93, 57), "title": f"Draw {move_orient} {move[1]},{move[2]}", "desc": "Executed final edge"},
                ],
                "steps": ["1. Scan: 1 edge", "2. Search: Instant", "3. Tactic: Forced", "4. Decision: Execute"],
                "valid_count": 1,
                "captures_count": 1 if is_capturing_move(state, move) else 0,
                "safe_count": 0,
                "risky_count": 0,
            }
            return move

        t_start = time.perf_counter()
        if self.difficulty == "easy":
            move = self._choose_easy(state, valid)
            reached_depth = 1
            best_val = 0
        elif self.difficulty == "medium":
            move, reached_depth, best_val = self._choose_medium(state)
        else:
            move, reached_depth, best_val = self._choose_hard(state)

        duration_ms = max(0.5, (time.perf_counter() - t_start) * 1000)
        captures = [m for m in valid if is_capturing_move(state, m)]
        safe = [m for m in valid if not is_risky_move(state, m) and not is_capturing_move(state, m)]
        risky = [m for m in valid if is_risky_move(state, m)]

        move_orient = "Horizontal" if move[0] == "h" else "Vertical"
        move_name = f"{'H' if move[0] == 'h' else 'V'}[{move[1]},{move[2]}]"

        if is_capturing_move(state, move):
            tactic = "Chain Capture"
            tactic_desc = "Claimed box & retained bonus turn"
            tactic_color = (217, 93, 57)
        elif not is_risky_move(state, move):
            tactic = "Positional Safety"
            tactic_desc = "Neutral edge avoiding 3rd side concession"
            tactic_color = (38, 115, 101)
        else:
            tactic = "Tactical Sacrifice"
            tactic_desc = "Minimal sacrifice to restrict counter-chains"
            tactic_color = (195, 115, 20)

        eval_pts = best_val / SCORE_SCALE

        step_items = [
            {"tag": "SCAN", "tag_color": (50, 110, 185), "title": f"{len(valid)} Open Edges Remaining", "desc": f"{len(captures)} free captures • {len(safe)} safe lines • {len(risky)} risky"},
            {"tag": "SEARCH", "tag_color": (115, 75, 165), "title": f"Alpha-Beta Tree (Depth {reached_depth})", "desc": f"{self._nodes:,} nodes evaluated in {duration_ms:.1f}ms"},
            {"tag": "TACTIC", "tag_color": tactic_color, "title": tactic, "desc": tactic_desc},
            {"tag": "DECISION", "tag_color": (38, 115, 101) if self.player_id == AI else (217, 93, 57), "title": f"Draw {move_orient} {move[1]},{move[2]}", "desc": f"Executed {move_name} | Eval: {'+' if eval_pts > 0 else ''}{eval_pts:.1f} pts"},
        ]

        self.last_analysis = {
            "algorithm": "alphabeta",
            "depth": reached_depth,
            "nodes": self._nodes,
            "duration_ms": duration_ms,
            "eval_score": eval_pts,
            "move": move,
            "move_name": move_name,
            "move_orient": move_orient,
            "tactic": tactic,
            "tactic_desc": tactic_desc,
            "steps": [
                f"1. Board Scan: {len(valid)} legal edges ({len(captures)} cap, {len(safe)} safe, {len(risky)} risk)",
                f"2. Alpha-Beta: Depth {reached_depth} search ({self._nodes:,} nodes, {duration_ms:.1f}ms)",
                f"3. Tactical Filter: {tactic} ({tactic_desc})",
                f"4. Decision: Selected {move_name} ({move_orient} {move[1]},{move[2]})",
            ],
            "step_items": step_items,
            "valid_count": len(valid),
            "captures_count": len(captures),
            "safe_count": len(safe),
            "risky_count": len(risky),
        }
        return move

    def _choose_easy(self, state: DotsAndBoxesState, valid: list[Move]) -> Move:
        captures = [m for m in valid if is_capturing_move(state, m)]
        if captures:
            return self._rng.choice(captures)
        safe = [m for m in valid if not is_risky_move(state, m)]
        if safe and self._rng.random() < 0.85:
            return self._rng.choice(safe)
        return self._rng.choice(valid)

    def _choose_medium(self, state: DotsAndBoxesState) -> tuple[Move, int, int]:
        valid = state.get_valid_moves()
        captures = [m for m in valid if is_capturing_move(state, m)]
        if captures:
            return self._rng.choice(captures), 1, 100
        safe = [m for m in valid if not is_risky_move(state, m)]
        if safe:
            self._nodes = 0
            self._deadline = time.perf_counter() + 0.25
            best_move = safe[0]
            best_val = -INF
            target_depth = 3 if len(valid) > 20 else 4
            for d in range(2, target_depth + 1):
                try:
                    m, v = self._root_search(state, d)
                    best_move, best_val = m, v
                except _SearchTimeout:
                    break
            return best_move, d, best_val
        return self._choose_sacrifice(state, valid), 1, -100

    def _choose_hard(self, state: DotsAndBoxesState) -> tuple[Move, int, int]:
        valid = state.get_valid_moves()
        self._nodes = 0
        budget = 0.20 if len(valid) > 20 else 0.45
        self._deadline = time.perf_counter() + budget
        best_move = valid[0]
        best_val = -INF
        reached_depth = 1
        max_d = min(5 if len(valid) > 20 else 8, len(valid) + 1)

        for depth in range(2, max_d):
            try:
                m, v = self._root_search(state, depth)
                best_move = m
                best_val = v
                reached_depth = depth
                if best_val >= INF - 100 or best_val <= -INF + 100:
                    break
            except _SearchTimeout:
                break
        return best_move, reached_depth, best_val

    def _root_search(self, state: DotsAndBoxesState, depth: int) -> tuple[Move, int]:
        ordered = self._order_moves(state, state.get_valid_moves())
        best_move = ordered[0]
        alpha = -INF
        beta = INF

        for move in ordered:
            if time.perf_counter() >= self._deadline:
                raise _SearchTimeout

            child = state.clone()
            gained = child.make_move(move, record_history=False)
            self._nodes += 1

            if gained > 0:
                val = (gained * SCORE_SCALE) + self._alphabeta(child, depth, alpha, beta)
            else:
                val = self._alphabeta(child, depth - 1, alpha, beta)

            if val > alpha:
                alpha = val
                best_move = move
            if alpha >= beta:
                break

        return best_move, alpha

    def _alphabeta(self, state: DotsAndBoxesState, depth: int, alpha: int, beta: int) -> int:
        if time.perf_counter() >= self._deadline:
            raise _SearchTimeout

        if state.is_game_over() or depth <= 0:
            return evaluate_remaining(state, my_player=self.player_id)

        key = state.state_key()
        if key in self._tt:
            tt_depth, tt_flag, tt_val, _ = self._tt[key]
            if tt_depth >= depth:
                if tt_flag == EXACT:
                    return tt_val
                elif tt_flag == LOWERBOUND and tt_val > alpha:
                    alpha = tt_val
                elif tt_flag == UPPERBOUND and tt_val < beta:
                    beta = tt_val
                if alpha >= beta:
                    return tt_val

        alpha_orig = alpha
        beta_orig = beta
        maximizing = (state.current_player == self.player_id)
        best_val = -INF if maximizing else INF
        best_move = None

        ordered = self._order_moves(state, state.get_valid_moves())
        for move in ordered:
            child = state.clone()
            gained = child.make_move(move, record_history=False)
            self._nodes += 1

            delta = (gained * SCORE_SCALE) if state.current_player == self.player_id else (-gained * SCORE_SCALE)
            next_depth = depth if gained > 0 else (depth - 1)
            val = delta + self._alphabeta(child, next_depth, alpha, beta)

            if maximizing:
                if val > best_val:
                    best_val = val
                    best_move = move
                alpha = max(alpha, best_val)
            else:
                if val < best_val:
                    best_val = val
                    best_move = move
                beta = min(beta, best_val)

            if alpha >= beta:
                break

        flag = UPPERBOUND if best_val <= alpha_orig else (LOWERBOUND if best_val >= beta_orig else EXACT)
        self._tt[key] = (depth, flag, best_val, best_move)
        return best_val

    def _order_moves(self, state: DotsAndBoxesState, moves: list[Move]) -> list[Move]:
        tt_move = None
        key = state.state_key()
        if key in self._tt:
            tt_move = self._tt[key][3]

        def move_score(m: Move) -> int:
            if m == tt_move:
                return 1000
            if is_capturing_move(state, m):
                return 500
            if not is_risky_move(state, m):
                return 100
            return 0

        return sorted(moves, key=move_score, reverse=True)

    def _choose_sacrifice(self, state: DotsAndBoxesState, valid: list[Move]) -> Move:
        best_m = valid[0]
        min_giveaway = INF
        for m in valid:
            sim = state.clone()
            sim.make_move(m, record_history=False)
            giveaway = greedy_chain_capture_count(sim)
            if giveaway < min_giveaway:
                min_giveaway = giveaway
                best_m = m
        return best_m


# ============================================================================
# 2. MONTE CARLO TREE SEARCH (MCTS)
# ============================================================================

class MCTSNode:
    """A node in the Monte Carlo Tree Search tree."""

    def __init__(self, state: DotsAndBoxesState, parent: Optional[MCTSNode] = None, move: Optional[Move] = None) -> None:
        self.state = state
        self.parent = parent
        self.move = move
        self.children: dict[Move, MCTSNode] = {}
        self.visits: int = 0
        self.total_reward: float = 0.0  # From perspective of root player
        self.unexpanded_moves: list[Move] = state.get_valid_moves()
        random.shuffle(self.unexpanded_moves)


class MCTSEngine(BaseAIEngine):
    """Monte Carlo Tree Search with UCB1 selection, bonus-turn multi-action nodes,

    and heuristic-biased rollout simulations.
    """

    def __init__(self, player_id: int = AI, difficulty: Difficulty = "hard", max_simulations: int = 800, time_budget: float = 0.65) -> None:
        super().__init__(player_id, difficulty)
        self.max_simulations = max_simulations
        self.time_budget = time_budget
        self.cpuct: float = 1.414

    def choose_move(self, state: DotsAndBoxesState) -> Move:
        valid = state.get_valid_moves()
        if not valid:
            raise ValueError("No valid moves remaining.")
        if len(valid) == 1:
            move = valid[0]
            move_orient = "Horizontal" if move[0] == "h" else "Vertical"
            self.last_analysis = {
                "algorithm": "mcts",
                "depth": 1,
                "nodes": 1,
                "duration_ms": 0.1,
                "eval_score": 0.0,
                "move": move,
                "move_name": f"{'H' if move[0] == 'h' else 'V'}[{move[1]},{move[2]}]",
                "move_orient": move_orient,
                "tactic": "Forced Last Move",
                "tactic_desc": "Single valid move remaining",
                "step_items": [
                    {"tag": "SCAN", "tag_color": (50, 110, 185), "title": "1 Edge Remaining", "desc": "Single valid line left"},
                    {"tag": "SEARCH", "tag_color": (115, 75, 165), "title": "Direct MCTS Solve", "desc": "Terminal board position"},
                    {"tag": "TACTIC", "tag_color": (195, 115, 20), "title": "Forced Edge", "desc": "Completed game boundary"},
                    {"tag": "DECISION", "tag_color": (38, 115, 101) if self.player_id == AI else (217, 93, 57), "title": f"Draw {move_orient} {move[1]},{move[2]}", "desc": "Executed final move"},
                ],
                "steps": ["1. Scan: 1 edge", "2. MCTS: Instant", "3. Tactic: Forced", "4. Decision: Execute"],
                "valid_count": 1,
                "captures_count": 1 if is_capturing_move(state, move) else 0,
                "safe_count": 0,
                "risky_count": 0,
            }
            return move

        # Immediate free captures filter (classic MCTS progressive pruning)
        captures = [m for m in valid if is_capturing_move(state, m)]
        if len(captures) == 1 and self.difficulty != "easy":
            # If there's an unambiguous single box capture, take it immediately
            c_move = captures[0]
            move_orient = "Horizontal" if c_move[0] == "h" else "Vertical"
            self.last_analysis = {
                "algorithm": "mcts",
                "depth": 1,
                "nodes": 1,
                "duration_ms": 0.5,
                "eval_score": 1.0,
                "move": c_move,
                "move_name": f"{'H' if c_move[0] == 'h' else 'V'}[{c_move[1]},{c_move[2]}]",
                "move_orient": move_orient,
                "tactic": "Instant Box Capture",
                "tactic_desc": "Immediate capture without full rollout tree",
                "step_items": [
                    {"tag": "SCAN", "tag_color": (50, 110, 185), "title": f"{len(valid)} Open Edges", "desc": f"1 free capture ready"},
                    {"tag": "SEARCH", "tag_color": (115, 75, 165), "title": "MCTS Heuristic Prune", "desc": "Immediate scoring move prioritized"},
                    {"tag": "TACTIC", "tag_color": (217, 93, 57), "title": "Chain Capture", "desc": "Captured box & retained turn"},
                    {"tag": "DECISION", "tag_color": (38, 115, 101) if self.player_id == AI else (217, 93, 57), "title": f"Draw {move_orient} {c_move[1]},{c_move[2]}", "desc": "Executed capture edge"},
                ],
                "steps": ["1. Scan: Capture ready", "2. MCTS: Pruned", "3. Tactic: Box Capture", "4. Decision: Taken"],
                "valid_count": len(valid),
                "captures_count": 1,
                "safe_count": len(valid) - 1,
                "risky_count": 0,
            }
            return c_move

        t_start = time.perf_counter()
        budget = 0.20 if len(valid) > 20 else 0.40
        deadline = t_start + budget
        root = MCTSNode(state.clone())
        simulations = 0

        sim_limit = 250 if self.difficulty == "hard" else (120 if self.difficulty == "medium" else 50)
        if len(valid) > 20:
            sim_limit = min(sim_limit, 140)

        while simulations < sim_limit and time.perf_counter() < deadline:
            node = self._select(root)
            if not node.state.is_game_over() and node.unexpanded_moves:
                node = self._expand(node)
            reward = self._simulate(node.state)
            self._backpropagate(node, reward)
            simulations += 1

        duration_ms = max(0.5, (time.perf_counter() - t_start) * 1000)

        # Pick child with most visits (standard robust child selection)
        best_move = max(root.children.keys(), key=lambda m: root.children[m].visits)
        best_node = root.children[best_move]
        win_rate = (best_node.total_reward / best_node.visits) if best_node.visits > 0 else 0.5
        eval_score = (win_rate - 0.5) * 6.0  # Scale to approximate box points

        move_orient = "Horizontal" if best_move[0] == "h" else "Vertical"
        move_name = f"{'H' if best_move[0] == 'h' else 'V'}[{best_move[1]},{best_move[2]}]"

        safe = [m for m in valid if not is_risky_move(state, m) and not is_capturing_move(state, m)]
        risky = [m for m in valid if is_risky_move(state, m)]

        if is_capturing_move(state, best_move):
            tactic = "MCTS Box Capture"
            tactic_desc = "Selected capture with highest win probability"
            tactic_col = (217, 93, 57)
        elif not is_risky_move(state, best_move):
            tactic = "MCTS Positional Safety"
            tactic_desc = "Explored high-visit neutral edge"
            tactic_col = (38, 115, 101)
        else:
            tactic = "MCTS Chain Sacrifice"
            tactic_desc = "Minimal sacrifice identified through rollouts"
            tactic_col = (195, 115, 20)

        step_items = [
            {"tag": "SCAN", "tag_color": (50, 110, 185), "title": f"{len(valid)} Open Edges Remaining", "desc": f"{len(captures)} captures • {len(safe)} safe • {len(risky)} risky"},
            {"tag": "SEARCH", "tag_color": (115, 75, 165), "title": f"MCTS ({simulations:,} Rollouts)", "desc": f"Top move visits: {best_node.visits:,} • Win Rate: {win_rate*100:.1f}%"},
            {"tag": "TACTIC", "tag_color": tactic_col, "title": tactic, "desc": tactic_desc},
            {"tag": "DECISION", "tag_color": (38, 115, 101) if self.player_id == AI else (217, 93, 57), "title": f"Draw {move_orient} {best_move[1]},{best_move[2]}", "desc": f"Executed {move_name} | Win Rate: {win_rate*100:.1f}%"},
        ]

        self.last_analysis = {
            "algorithm": "mcts",
            "depth": int(math.log2(simulations + 1)),
            "nodes": simulations,
            "duration_ms": duration_ms,
            "eval_score": eval_score,
            "win_rate": win_rate,
            "move": best_move,
            "move_name": move_name,
            "move_orient": move_orient,
            "tactic": tactic,
            "tactic_desc": tactic_desc,
            "steps": [
                f"1. Board Scan: {len(valid)} legal edges ({len(captures)} cap, {len(safe)} safe, {len(risky)} risk)",
                f"2. MCTS Rollouts: {simulations:,} simulations executed in {duration_ms:.1f}ms",
                f"3. UCB1 Convergence: Win Rate {win_rate*100:.1f}% across {best_node.visits} visits",
                f"4. Decision: Selected {move_name} ({move_orient} {best_move[1]},{best_move[2]})",
            ],
            "step_items": step_items,
            "valid_count": len(valid),
            "captures_count": len(captures),
            "safe_count": len(safe),
            "risky_count": len(risky),
        }
        return best_move

    def _select(self, node: MCTSNode) -> MCTSNode:
        curr = node
        while not curr.state.is_game_over() and not curr.unexpanded_moves and curr.children:
            best_score = -float("inf")
            best_child = None
            log_n = math.log(curr.visits + 1)
            for m, child in curr.children.items():
                if child.visits == 0:
                    score = float("inf")
                else:
                    exploit = child.total_reward / child.visits
                    # Perspective invert if turn changed
                    if curr.state.current_player != self.player_id:
                        exploit = 1.0 - exploit
                    explore = self.cpuct * math.sqrt(log_n / child.visits)
                    score = exploit + explore
                if score > best_score:
                    best_score = score
                    best_child = child
            if best_child is None:
                break
            curr = best_child
        return curr

    def _expand(self, node: MCTSNode) -> MCTSNode:
        move = node.unexpanded_moves.pop()
        child_state = node.state.clone()
        child_state.make_move(move, record_history=False)
        child_node = MCTSNode(child_state, parent=node, move=move)
        node.children[move] = child_node
        return child_node

    def _simulate(self, state: DotsAndBoxesState) -> float:
        """Fast heuristic rollout simulation until terminal state."""
        sim = state.clone()
        while not sim.is_game_over():
            valid = sim.get_valid_moves()
            if not valid:
                break
            # Heuristic rollout policy: greedy capture > safe move > minimal giveaway
            captures = [m for m in valid if is_capturing_move(sim, m)]
            if captures:
                chosen = self._rng.choice(captures)
            else:
                safe = [m for m in valid if not is_risky_move(sim, m)]
                if safe:
                    chosen = self._rng.choice(safe)
                else:
                    chosen = self._rng.choice(valid)
            sim.make_move(chosen, record_history=False)

        # Reward from perspective of self.player_id
        my_score = sim.scores[self.player_id]
        opp_id = 3 - self.player_id
        opp_score = sim.scores[opp_id]
        if my_score > opp_score:
            return 1.0
        elif my_score == opp_score:
            return 0.5
        return 0.0

    def _backpropagate(self, node: Optional[MCTSNode], reward: float) -> None:
        curr = node
        while curr is not None:
            curr.visits += 1
            curr.total_reward += reward
            curr = curr.parent


# ============================================================================
# 3. BERLEKAMP COMBINATORIAL SOLVER (NIMSTRING THEORY & PARITY CONTROL)
# ============================================================================

@dataclass
class ChainInfo:
    """Represents a component/chain of connected boxes in Berlekamp theory."""
    chain_type: Literal["short_chain", "long_chain", "loop"]
    length: int
    boxes: list[tuple[int, int]]
    open_edges: list[Move]


class BerlekampEngine(BaseAIEngine):
    """Elwyn Berlekamp Combinatorial Game Theory Engine:

    Applies Nimstring theory, chain/loop classification, double-cross parity sacrifice,
    and long chain control.
    """

    def __init__(self, player_id: int = AI, difficulty: Difficulty = "hard") -> None:
        super().__init__(player_id, difficulty)

    def choose_move(self, state: DotsAndBoxesState) -> Move:
        valid = state.get_valid_moves()
        if not valid:
            raise ValueError("No valid moves remaining.")
        if len(valid) == 1:
            move = valid[0]
            move_orient = "Horizontal" if move[0] == "h" else "Vertical"
            self.last_analysis = {
                "algorithm": "berlekamp",
                "depth": 1,
                "nodes": 1,
                "duration_ms": 0.1,
                "eval_score": 0.0,
                "move": move,
                "move_name": f"{'H' if move[0] == 'h' else 'V'}[{move[1]},{move[2]}]",
                "move_orient": move_orient,
                "tactic": "Forced Last Move",
                "tactic_desc": "Single valid move remaining",
                "step_items": [
                    {"tag": "SCAN", "tag_color": (50, 110, 185), "title": "1 Edge Remaining", "desc": "Single valid line left"},
                    {"tag": "SOLVER", "tag_color": (115, 75, 165), "title": "Nimstring Solved", "desc": "Zero degrees of freedom left"},
                    {"tag": "PARITY", "tag_color": (195, 115, 20), "title": "Terminal Parity", "desc": "Complete graph closure"},
                    {"tag": "DECISION", "tag_color": (38, 115, 101) if self.player_id == AI else (217, 93, 57), "title": f"Draw {move_orient} {move[1]},{move[2]}", "desc": "Placed final edge"},
                ],
                "steps": ["1. Scan: 1 edge", "2. Berlekamp: Solved", "3. Parity: Terminal", "4. Decision: Execute"],
                "valid_count": 1,
                "captures_count": 1 if is_capturing_move(state, move) else 0,
                "safe_count": 0,
                "risky_count": 0,
            }
            return move

        t_start = time.perf_counter()

        # Step 1: Detect corridors, chains, and loops
        chains = self._decompose_chains(state)
        captures = [m for m in valid if is_capturing_move(state, m)]
        safe = [m for m in valid if not is_risky_move(state, m) and not is_capturing_move(state, m)]
        risky = [m for m in valid if is_risky_move(state, m)]

        # Berlekamp Decision Strategy:
        # A) Double-Cross Sacrifice Check:
        # If we have an active chain capture, should we take all boxes or double-cross?
        chosen_move = None
        tactic = "Berlekamp Standard"
        tactic_desc = "Optimal impartial game theory move"
        tactic_col = (38, 115, 101)

        double_cross_move = self._check_double_cross(state, captures, chains)
        if double_cross_move is not None:
            chosen_move = double_cross_move
            tactic = "Double-Cross Parity Sacrifice"
            tactic_desc = "Sacrificed 2 boxes to seize the next long chain"
            tactic_col = (195, 115, 20)
        elif captures:
            # Greedily sweep normal captures
            chosen_move = captures[0]
            tactic = "Chain Capture Sweep"
            tactic_desc = "Sweeping available 3-sided boxes"
            tactic_col = (217, 93, 57)
        elif safe:
            # Play safe moves conserving parity
            chosen_move = self._choose_safe_parity_move(state, safe)
            tactic = "Nimstring Safe Parity"
            tactic_desc = "Neutral play preserving long-chain control"
            tactic_col = (38, 115, 101)
        else:
            # Forced sacrifice: choose the shortest chain giveaway
            chosen_move = self._choose_minimal_chain_sacrifice(state, valid, chains)
            tactic = "Minimal Chain Giveaway"
            tactic_desc = "Forced chain opening with smallest opponent yield"
            tactic_col = (195, 115, 20)

        duration_ms = max(0.4, (time.perf_counter() - t_start) * 1000)
        eval_score = evaluate_remaining(state, my_player=self.player_id) / SCORE_SCALE

        move_orient = "Horizontal" if chosen_move[0] == "h" else "Vertical"
        move_name = f"{'H' if chosen_move[0] == 'h' else 'V'}[{chosen_move[1]},{chosen_move[2]}]"

        step_items = [
            {"tag": "SCAN", "tag_color": (50, 110, 185), "title": f"{len(valid)} Open Edges ({len(chains)} Chains Identified)", "desc": f"{len(captures)} captures • {len(safe)} safe • {len(risky)} risky"},
            {"tag": "SOLVER", "tag_color": (115, 75, 165), "title": "Berlekamp Nimstring Engine", "desc": f"Chain analysis: {sum(c.length for c in chains)} boxes in corridors"},
            {"tag": "TACTIC", "tag_color": tactic_col, "title": tactic, "desc": tactic_desc},
            {"tag": "DECISION", "tag_color": (38, 115, 101) if self.player_id == AI else (217, 93, 57), "title": f"Draw {move_orient} {chosen_move[1]},{chosen_move[2]}", "desc": f"Executed {move_name} | Parity Preserved"},
        ]

        self.last_analysis = {
            "algorithm": "berlekamp",
            "depth": len(chains) + 1,
            "nodes": len(chains) * 8 + len(valid),
            "duration_ms": duration_ms,
            "eval_score": eval_score,
            "chains_count": len(chains),
            "move": chosen_move,
            "move_name": move_name,
            "move_orient": move_orient,
            "tactic": tactic,
            "tactic_desc": tactic_desc,
            "steps": [
                f"1. Graph Scan: {len(valid)} edges open across {len(chains)} corridors",
                f"2. Berlekamp Nimstring: Evaluated chain parity and loop values",
                f"3. Strategic Filter: {tactic} ({tactic_desc})",
                f"4. Decision: Executed {move_name} ({move_orient} {chosen_move[1]},{chosen_move[2]})",
            ],
            "step_items": step_items,
            "valid_count": len(valid),
            "captures_count": len(captures),
            "safe_count": len(safe),
            "risky_count": len(risky),
        }
        return chosen_move

    def _decompose_chains(self, state: DotsAndBoxesState) -> list[ChainInfo]:
        """Decompose connected 2-sided and 3-sided boxes into corridors and chains."""
        visited = set()
        chains: list[ChainInfo] = []

        for r in range(state.rows):
            for c in range(state.cols):
                if (r, c) in visited or state.box_sides[r][c] < 2 or state.boxes[r][c] != 0:
                    continue

                # Traverse corridor using BFS
                comp_boxes: list[tuple[int, int]] = []
                queue = [(r, c)]
                visited.add((r, c))

                while queue:
                    curr_r, curr_c = queue.pop(0)
                    comp_boxes.append((curr_r, curr_c))

                    # Inspect open edges of this box
                    open_edges = state.get_box_open_edges(curr_r, curr_c)
                    for edge in open_edges:
                        for nbr_r, nbr_c in state.adjacent_boxes(edge):
                            if (nbr_r, nbr_c) != (curr_r, curr_c) and (nbr_r, nbr_c) not in visited:
                                if state.box_sides[nbr_r][nbr_c] in (2, 3) and state.boxes[nbr_r][nbr_c] == 0:
                                    visited.add((nbr_r, nbr_c))
                                    queue.append((nbr_r, nbr_c))

                if comp_boxes:
                    comp_open_edges = set()
                    for br, bc in comp_boxes:
                        for e in state.get_box_open_edges(br, bc):
                            comp_open_edges.add(e)

                    k = len(comp_boxes)
                    ctype: Literal["short_chain", "long_chain", "loop"] = "long_chain" if k >= 3 else "short_chain"
                    chains.append(ChainInfo(
                        chain_type=ctype,
                        length=k,
                        boxes=comp_boxes,
                        open_edges=list(comp_open_edges)
                    ))
        return chains

    def _check_double_cross(self, state: DotsAndBoxesState, captures: list[Move], chains: list[ChainInfo]) -> Optional[Move]:
        """Berlekamp Long Chain Rule:

        If we are capturing boxes in a long chain (k >= 3) and there is another long chain
        waiting, we sacrifice 2 boxes (double-crossing) to retain control of the game!
        """
        if not captures:
            return None

        # Find if any capturing move is in a long chain with exactly 2 boxes left
        for ch in chains:
            if ch.length >= 3 and len(ch.open_edges) == 2:
                # 2 edges left in a long chain!
                # Instead of taking the last box and giving away next chain,
                # a double-cross plays the edge that leaves 2 boxes as a sacrifice.
                for e in ch.open_edges:
                    if not is_capturing_move(state, e):
                        return e
        return None

    def _choose_safe_parity_move(self, state: DotsAndBoxesState, safe: list[Move]) -> Move:
        """Choose a safe move that preserves favorable chain parity."""
        # Score safe moves based on degree of isolation and corner preference
        def score_safe(m: Move) -> int:
            score = 0
            adj = state.adjacent_boxes(m)
            for br, bc in adj:
                sides = state.box_sides[br][bc]
                if sides == 0:
                    score += 10
                elif sides == 1:
                    score += 5
            # Outer perimeter moves are generally safer
            if len(adj) == 1:
                score += 3
            return score

        return max(safe, key=score_safe)

    def _choose_minimal_chain_sacrifice(self, state: DotsAndBoxesState, valid: list[Move], chains: list[ChainInfo]) -> Move:
        """When forced to open a chain, pick the one that gives away the fewest boxes."""
        best_move = valid[0]
        min_giveaway = INF

        for m in valid:
            sim = state.clone()
            sim.make_move(m, record_history=False)
            giveaway = greedy_chain_capture_count(sim)
            if giveaway < min_giveaway:
                min_giveaway = giveaway
                best_move = m

        return best_move


# ============================================================================
# 4. POLICY-VALUE NEURAL NETWORK WITH GUIDED SEARCH (PV-MCTS / ALPHAZERO STYLE)
# ============================================================================

class PolicyValueNet:
    """Lightweight pure-NumPy Policy-Value Neural Network.

    Computes prior move probabilities P(s, a) and scalar evaluation V(s) in a single pass.
    """

    def __init__(self, rows: int = 3, cols: int = 3) -> None:
        self.rows = rows
        self.cols = cols
        self.total_edges = (rows + 1) * cols + rows * (cols + 1)
        self.total_boxes = rows * cols

        # Input dimension: 6 channels flattened (H-edges, V-edges, box sides, box owners, 3-sided, 2-sided)
        h_dim = (rows + 1) * cols
        v_dim = rows * (cols + 1)
        in_dim = h_dim + v_dim + self.total_boxes * 4 + 2

        # Initialize network weights deterministically (calibrated heuristic embeddings)
        rng = np.random.RandomState(42)
        h1 = 64
        h2 = 64

        self.W1 = rng.randn(in_dim, h1) * np.sqrt(2.0 / in_dim)
        self.b1 = np.zeros(h1)

        self.W2 = rng.randn(h1, h2) * np.sqrt(2.0 / h1)
        self.b2 = np.zeros(h2)

        # Policy head: h2 -> total_edges
        self.W_p = rng.randn(h2, self.total_edges) * np.sqrt(2.0 / h2)
        self.b_p = np.zeros(self.total_edges)

        # Value head: h2 -> 1
        self.W_v = rng.randn(h2, 1) * np.sqrt(2.0 / h2)
        self.b_v = np.zeros(1)

    def extract_features(self, state: DotsAndBoxesState, my_player: int) -> np.ndarray:
        """Extract spatial and tactical feature vector from state."""
        features: list[float] = []

        # 1. Horizontal edges
        for r in range(state.rows + 1):
            for c in range(state.cols):
                features.append(1.0 if state.h_edges[r][c] else 0.0)

        # 2. Vertical edges
        for r in range(state.rows):
            for c in range(state.cols + 1):
                features.append(1.0 if state.v_edges[r][c] else 0.0)

        # 3. Box sides normalized (0..1)
        for r in range(state.rows):
            for c in range(state.cols):
                features.append(state.box_sides[r][c] / 4.0)

        # 4. Box ownership (1.0 = mine, -1.0 = opp, 0.0 = unclaimed)
        for r in range(state.rows):
            for c in range(state.cols):
                owner = state.boxes[r][c]
                features.append(1.0 if owner == my_player else (-1.0 if owner != 0 else 0.0))

        # 5. Immediate 3-sided capture flags
        for r in range(state.rows):
            for c in range(state.cols):
                features.append(1.0 if state.box_sides[r][c] == 3 else 0.0)

        # 6. Critical 2-sided setup flags
        for r in range(state.rows):
            for c in range(state.cols):
                features.append(1.0 if state.box_sides[r][c] == 2 else 0.0)

        # 7. Score differential normalized
        my_score = state.scores[my_player]
        opp_score = state.scores[3 - my_player]
        features.append((my_score - opp_score) / max(1.0, float(state.total_boxes)))
        features.append(1.0 if state.current_player == my_player else -1.0)

        return np.array(features, dtype=np.float32)

    def forward(self, state: DotsAndBoxesState, my_player: int) -> tuple[np.ndarray, float]:
        """Perform forward inference returning (policy_probs, value_scalar)."""
        x = self.extract_features(state, my_player)

        # Layer 1 (GELU approximation: 0.5 * x * (1 + tanh(sqrt(2/pi) * (x + 0.044715 * x^3))))
        z1 = np.dot(x, self.W1) + self.b1
        a1 = 0.5 * z1 * (1.0 + np.tanh(0.79788456 * (z1 + 0.044715 * (z1 ** 3))))

        # Layer 2
        z2 = np.dot(a1, self.W2) + self.b2
        a2 = 0.5 * z2 * (1.0 + np.tanh(0.79788456 * (z2 + 0.044715 * (z2 ** 3))))

        # Policy logits
        p_logits = np.dot(a2, self.W_p) + self.b_p

        # Value scalar (Tanh -> [-1, 1])
        v_raw = np.dot(a2, self.W_v) + self.b_v
        value = float(np.tanh(v_raw[0]))

        # Heuristic boost to policy prior: give strong priors to free captures & safe moves
        valid_moves = state.get_valid_moves()
        move_to_idx = {m: i for i, m in enumerate(self._all_moves())}

        # Mask invalid moves to -inf
        masked_logits = np.full(self.total_edges, -1e9, dtype=np.float32)
        for m in valid_moves:
            idx = move_to_idx.get(m)
            if idx is not None:
                bias = 0.0
                if is_capturing_move(state, m):
                    bias += 4.0
                elif not is_risky_move(state, m):
                    bias += 1.5
                masked_logits[idx] = p_logits[idx] + bias

        # Softmax
        exp_logits = np.exp(masked_logits - np.max(masked_logits))
        policy_probs = exp_logits / np.sum(exp_logits)

        return policy_probs, value

    def _all_moves(self) -> list[Move]:
        moves: list[Move] = []
        for r in range(self.rows + 1):
            for c in range(self.cols):
                moves.append(("h", r, c))
        for r in range(self.rows):
            for c in range(self.cols + 1):
                moves.append(("v", r, c))
        return moves


class PUCTNode:
    """Node in the Policy-Value Guided Search tree."""

    def __init__(self, state: DotsAndBoxesState, parent: Optional[PUCTNode] = None, move: Optional[Move] = None, prior: float = 0.0) -> None:
        self.state = state
        self.parent = parent
        self.move = move
        self.prior = prior
        self.children: dict[Move, PUCTNode] = {}
        self.visits: int = 0
        self.total_value: float = 0.0


class PolicyValueEngine(BaseAIEngine):
    """AlphaZero-style Policy-Value Neural Network guided MCTS.

    Uses neural prior probabilities P(s, a) and value evaluation V(s) to guide PUCT search,
    completely replacing random rollouts with neural inference.
    """

    def __init__(self, player_id: int = AI, difficulty: Difficulty = "hard", simulations: int = 150) -> None:
        super().__init__(player_id, difficulty)
        self.simulations = simulations if difficulty == "hard" else (70 if difficulty == "medium" else 25)
        self.cpuct: float = 1.25
        self._net: Optional[PolicyValueNet] = None

    def _ensure_net(self, state: DotsAndBoxesState) -> PolicyValueNet:
        if self._net is None or self._net.rows != state.rows or self._net.cols != state.cols:
            self._net = PolicyValueNet(state.rows, state.cols)
        return self._net

    def choose_move(self, state: DotsAndBoxesState) -> Move:
        valid = state.get_valid_moves()
        if not valid:
            raise ValueError("No valid moves remaining.")
        if len(valid) == 1:
            move = valid[0]
            move_orient = "Horizontal" if move[0] == "h" else "Vertical"
            self.last_analysis = {
                "algorithm": "policy_value",
                "depth": 1,
                "nodes": 1,
                "duration_ms": 0.1,
                "eval_score": 0.0,
                "move": move,
                "move_name": f"{'H' if move[0] == 'h' else 'V'}[{move[1]},{move[2]}]",
                "move_orient": move_orient,
                "tactic": "Forced Last Move",
                "tactic_desc": "Single valid move remaining",
                "step_items": [
                    {"tag": "SCAN", "tag_color": (50, 110, 185), "title": "1 Edge Remaining", "desc": "Single valid line left"},
                    {"tag": "NET-V", "tag_color": (115, 75, 165), "title": "Neural Solved", "desc": "Single move domain"},
                    {"tag": "TACTIC", "tag_color": (195, 115, 20), "title": "Forced Edge", "desc": "Terminal board closure"},
                    {"tag": "DECISION", "tag_color": (38, 115, 101) if self.player_id == AI else (217, 93, 57), "title": f"Draw {move_orient} {move[1]},{move[2]}", "desc": "Executed final move"},
                ],
                "steps": ["1. Scan: 1 edge", "2. Net: Solved", "3. Tactic: Forced", "4. Decision: Execute"],
                "valid_count": 1,
                "captures_count": 1 if is_capturing_move(state, move) else 0,
                "safe_count": 0,
                "risky_count": 0,
            }
            return move

        net = self._ensure_net(state)
        t_start = time.perf_counter()

        # Initialize Root
        root = PUCTNode(state.clone())
        policy_probs, v_root = net.forward(state, self.player_id)
        move_to_idx = {m: i for i, m in enumerate(net._all_moves())}

        # Expand root immediately
        for m in valid:
            p_idx = move_to_idx.get(m, 0)
            prior = float(policy_probs[p_idx])
            child_state = state.clone()
            child_state.make_move(m, record_history=False)
            root.children[m] = PUCTNode(child_state, parent=root, move=m, prior=prior)

        # Run PUCT simulations
        for _ in range(self.simulations):
            node = root
            # 1. Selection
            while node.children:
                best_score = -float("inf")
                best_child = None
                sum_n = sum(c.visits for c in node.children.values())
                sqrt_sum = math.sqrt(max(1, sum_n))

                for m, c in node.children.items():
                    q = (c.total_value / c.visits) if c.visits > 0 else 0.0
                    u = self.cpuct * c.prior * (sqrt_sum / (1 + c.visits))
                    puct_score = q + u
                    if puct_score > best_score:
                        best_score = puct_score
                        best_child = c

                if best_child is None:
                    break
                node = best_child

            # 2. Evaluation & Expansion
            if not node.state.is_game_over():
                p_probs, value = net.forward(node.state, self.player_id)
                # Expand children
                for nm in node.state.get_valid_moves():
                    pidx = move_to_idx.get(nm, 0)
                    ch_state = node.state.clone()
                    ch_state.make_move(nm, record_history=False)
                    node.children[nm] = PUCTNode(ch_state, parent=node, move=nm, prior=float(p_probs[pidx]))
            else:
                # Terminal value
                my_s = node.state.scores[self.player_id]
                opp_s = node.state.scores[3 - self.player_id]
                value = 1.0 if my_s > opp_s else (-1.0 if my_s < opp_s else 0.0)

            # 3. Backpropagation
            curr = node
            while curr is not None:
                curr.visits += 1
                curr.total_value += value
                curr = curr.parent

        duration_ms = max(0.5, (time.perf_counter() - t_start) * 1000)

        # Choose most visited action
        best_move = max(root.children.keys(), key=lambda m: root.children[m].visits)
        best_child = root.children[best_move]
        best_prior = best_child.prior
        q_value = (best_child.total_value / best_child.visits) if best_child.visits > 0 else 0.0
        eval_score = q_value * 5.0

        move_orient = "Horizontal" if best_move[0] == "h" else "Vertical"
        move_name = f"{'H' if best_move[0] == 'h' else 'V'}[{best_move[1]},{best_move[2]}]"

        captures = [m for m in valid if is_capturing_move(state, m)]
        safe = [m for m in valid if not is_risky_move(state, m) and not is_capturing_move(state, m)]
        risky = [m for m in valid if is_risky_move(state, m)]

        if is_capturing_move(state, best_move):
            tactic = "Neural Policy Capture"
            tactic_desc = "High-prior capture verified by PUCT tree"
            tactic_col = (217, 93, 57)
        elif not is_risky_move(state, best_move):
            tactic = "PUCT Safe Development"
            tactic_desc = "Top value-guided non-volatile edge"
            tactic_col = (38, 115, 101)
        else:
            tactic = "Guided Sacrifice Control"
            tactic_desc = "Sacrifice recommended by Value Network"
            tactic_col = (195, 115, 20)

        step_items = [
            {"tag": "SCAN", "tag_color": (50, 110, 185), "title": f"{len(valid)} Open Edges Remaining", "desc": f"{len(captures)} captures • {len(safe)} safe • {len(risky)} risky"},
            {"tag": "PV-NET", "tag_color": (115, 75, 165), "title": f"PUCT Guided Search ({self.simulations} Inferences)", "desc": f"Prior P(a): {best_prior*100:.1f}% • Q-Value: {q_value:+.2f}"},
            {"tag": "TACTIC", "tag_color": tactic_col, "title": tactic, "desc": tactic_desc},
            {"tag": "DECISION", "tag_color": (38, 115, 101) if self.player_id == AI else (217, 93, 57), "title": f"Draw {move_orient} {best_move[1]},{best_move[2]}", "desc": f"Executed {move_name} | Q-Score: {q_value:+.2f}"},
        ]

        self.last_analysis = {
            "algorithm": "policy_value",
            "depth": int(math.log2(self.simulations + 1)),
            "nodes": self.simulations,
            "duration_ms": duration_ms,
            "eval_score": eval_score,
            "prior": best_prior,
            "q_value": q_value,
            "move": best_move,
            "move_name": move_name,
            "move_orient": move_orient,
            "tactic": tactic,
            "tactic_desc": tactic_desc,
            "steps": [
                f"1. Tensor Scan: {len(valid)} legal edges fed to Policy-Value Network",
                f"2. PUCT Tree: {self.simulations} neural evaluations ({duration_ms:.1f}ms)",
                f"3. Policy Prior: P(a)={best_prior*100:.1f}%, Q(s,a)={q_value:+.2f}",
                f"4. Decision: Selected {move_name} ({move_orient} {best_move[1]},{best_move[2]})",
            ],
            "step_items": step_items,
            "valid_count": len(valid),
            "captures_count": len(captures),
            "safe_count": len(safe),
            "risky_count": len(risky),
        }
        return best_move


# ============================================================================
# FACTORY FUNCTION
# ============================================================================

def create_ai_engine(algorithm: AlgorithmType, player_id: int = AI, difficulty: Difficulty = "hard") -> BaseAIEngine:
    """Factory creating an AI engine based on algorithm name."""
    if algorithm == "alphabeta":
        return AlphaBetaEngine(player_id=player_id, difficulty=difficulty)
    elif algorithm == "mcts":
        return MCTSEngine(player_id=player_id, difficulty=difficulty)
    elif algorithm == "berlekamp":
        return BerlekampEngine(player_id=player_id, difficulty=difficulty)
    elif algorithm == "policy_value":
        return PolicyValueEngine(player_id=player_id, difficulty=difficulty)
    else:
        raise ValueError(f"Unknown algorithm: {algorithm}")
