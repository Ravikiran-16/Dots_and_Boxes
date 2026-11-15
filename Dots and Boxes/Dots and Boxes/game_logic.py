"""Core game state and rules engine for Dots and Boxes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

HUMAN = 1
AI = 2
DRAW = 0

Orientation = Literal["h", "v"]
Move = tuple[Orientation, int, int]


@dataclass(frozen=True)
class MoveRecord:
    """Represents a completed move for undo and UI highlighting."""

    move: Move
    player: int
    completed_boxes: tuple[tuple[int, int], ...]
    previous_player: int


class DotsAndBoxesState:
    """Mutable, fast representation of a Dots and Boxes board."""

    def __init__(self, rows: int = 3, cols: int = 3, starting_player: int = HUMAN) -> None:
        if rows < 2 or cols < 2:
            raise ValueError("Board must be at least 2x2 boxes.")
        self.rows = rows
        self.cols = cols
        self.total_boxes = rows * cols
        self.total_edges = (rows + 1) * cols + rows * (cols + 1)

        # Edge grids: h_edges[r][c] for 0 <= r <= rows, 0 <= c < cols
        #             v_edges[r][c] for 0 <= r < rows, 0 <= c <= cols
        self.h_edges: list[list[bool]] = [[False] * cols for _ in range(rows + 1)]
        self.v_edges: list[list[bool]] = [[False] * (cols + 1) for _ in range(rows)]
        self.h_mask: int = 0
        self.v_mask: int = 0

        # Box owners: 0 = unclaimed, 1 = HUMAN, 2 = AI
        self.boxes: list[list[int]] = [[0] * cols for _ in range(rows)]
        self.box_sides: list[list[int]] = [[0] * cols for _ in range(rows)]

        self.scores: dict[int, int] = {HUMAN: 0, AI: 0}
        self.current_player: int = starting_player
        self.edges_drawn: int = 0
        self.history: list[MoveRecord] = []

    def clone(self) -> DotsAndBoxesState:
        """Create a fast shallow-structure copy without move history (for AI search)."""
        copy = DotsAndBoxesState.__new__(DotsAndBoxesState)
        copy.rows = self.rows
        copy.cols = self.cols
        copy.total_boxes = self.total_boxes
        copy.total_edges = self.total_edges
        copy.h_edges = [row[:] for row in self.h_edges]
        copy.v_edges = [row[:] for row in self.v_edges]
        copy.h_mask = self.h_mask
        copy.v_mask = self.v_mask
        copy.boxes = [row[:] for row in self.boxes]
        copy.box_sides = [row[:] for row in self.box_sides]
        copy.scores = {HUMAN: self.scores[HUMAN], AI: self.scores[AI]}
        copy.current_player = self.current_player
        copy.edges_drawn = self.edges_drawn
        copy.history = []
        return copy

    def state_key(self) -> tuple[int, int, int]:
        """Return a hashable key independent of prior box ownership."""
        return (self.h_mask, self.v_mask, self.current_player)

    def is_edge_drawn(self, move: Move) -> bool:
        orientation, r, c = move
        if orientation == "h":
            return self.h_edges[r][c]
        return self.v_edges[r][c]

    def get_valid_moves(self) -> list[Move]:
        """Return all remaining legal moves on the board."""
        moves: list[Move] = []
        for r in range(self.rows + 1):
            row = self.h_edges[r]
            for c in range(self.cols):
                if not row[c]:
                    moves.append(("h", r, c))
        for r in range(self.rows):
            row = self.v_edges[r]
            for c in range(self.cols + 1):
                if not row[c]:
                    moves.append(("v", r, c))
        return moves

    def adjacent_boxes(self, move: Move) -> list[tuple[int, int]]:
        """Return the 1 or 2 box coordinates adjacent to the given edge."""
        orientation, r, c = move
        adj: list[tuple[int, int]] = []
        if orientation == "h":
            if r > 0:
                adj.append((r - 1, c))
            if r < self.rows:
                adj.append((r, c))
        else:
            if c > 0:
                adj.append((r, c - 1))
            if c < self.cols:
                adj.append((r, c))
        return adj

    def make_move(self, move: Move, record_history: bool = True) -> int:
        """Apply a move, update scores and turn, and return boxes completed."""
        orientation, r, c = move
        if orientation == "h":
            if self.h_edges[r][c]:
                raise ValueError(f"Edge {move} is already drawn.")
            self.h_edges[r][c] = True
            self.h_mask |= 1 << (r * self.cols + c)
        else:
            if self.v_edges[r][c]:
                raise ValueError(f"Edge {move} is already drawn.")
            self.v_edges[r][c] = True
            self.v_mask |= 1 << (r * (self.cols + 1) + c)

        self.edges_drawn += 1
        previous_player = self.current_player
        completed: list[tuple[int, int]] = []

        for br, bc in self.adjacent_boxes(move):
            self.box_sides[br][bc] += 1
            if self.box_sides[br][bc] == 4:
                self.boxes[br][bc] = previous_player
                self.scores[previous_player] += 1
                completed.append((br, bc))

        if record_history:
            self.history.append(
                MoveRecord(
                    move=move,
                    player=previous_player,
                    completed_boxes=tuple(completed),
                    previous_player=previous_player,
                )
            )

        if not completed:
            self.current_player = AI if previous_player == HUMAN else HUMAN

        return len(completed)

    def undo_move(self) -> MoveRecord | None:
        """Undo the most recent move from history."""
        if not self.history:
            return None
        record = self.history.pop()
        orientation, r, c = record.move

        if orientation == "h":
            self.h_edges[r][c] = False
            self.h_mask &= ~(1 << (r * self.cols + c))
        else:
            self.v_edges[r][c] = False
            self.v_mask &= ~(1 << (r * (self.cols + 1) + c))

        self.edges_drawn -= 1
        for br, bc in self.adjacent_boxes(record.move):
            self.box_sides[br][bc] -= 1

        for br, bc in record.completed_boxes:
            self.boxes[br][bc] = 0
            self.scores[record.player] -= 1

        self.current_player = record.previous_player
        return record

    def undo_to_human_turn(self) -> bool:
        """Undo AI moves and the preceding human move so the human can replay."""
        if not self.history:
            return False
        # First pop any trailing AI moves (if AI is mid-chain or just finished)
        while self.history and self.history[-1].player == AI:
            self.undo_move()
        # Pop the human's last move as well if present
        if self.history and self.history[-1].player == HUMAN:
            self.undo_move()
        return True

    def is_game_over(self) -> bool:
        return self.edges_drawn >= self.total_edges

    def get_winner(self) -> int | None:
        """Return HUMAN, AI, DRAW (0), or None if the game is still ongoing."""
        if not self.is_game_over():
            return None
        if self.scores[HUMAN] > self.scores[AI]:
            return HUMAN
        if self.scores[AI] > self.scores[HUMAN]:
            return AI
        return DRAW

    def get_box_open_edges(self, br: int, bc: int) -> list[Move]:
        """Return the undrawn edges around box (br, bc)."""
        edges: list[Move] = []
        if not self.h_edges[br][bc]:
            edges.append(("h", br, bc))
        if not self.h_edges[br + 1][bc]:
            edges.append(("h", br + 1, bc))
        if not self.v_edges[br][bc]:
            edges.append(("v", br, bc))
        if not self.v_edges[br][bc + 1]:
            edges.append(("v", br, bc + 1))
        return edges

