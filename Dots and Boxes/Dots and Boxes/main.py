"""Pygame desktop GUI for Dots and Boxes (Human vs AI, 2 Players, AI vs AI).
Features a strategic Setup / Loading Launch Screen with tasteful light pastel accents,
high-DPI native rendering, and the AI Studio Cream & Terracotta/Sage aesthetic.
"""

from __future__ import annotations

import json
import math
import os
import random
import threading
import time
from dataclasses import dataclass
from typing import Literal

PROFILE_FILE = os.path.join(os.path.dirname(__file__), "player_profile.json")


def load_player_profile() -> dict[str, str]:
    """Load stored player names from local profile json."""
    try:
        if os.path.exists(PROFILE_FILE):
            with open(PROFILE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return {
                    "player1_name": str(data.get("player1_name", "Player 1")).strip() or "Player 1",
                    "player2_name": str(data.get("player2_name", "Player 2")).strip() or "Player 2",
                }
    except Exception:
        pass
    return {"player1_name": "Player 1", "player2_name": "Player 2"}


def save_player_profile(p1: str, p2: str) -> None:
    """Save player names to local profile json for persistent tracking."""
    try:
        data = {
            "player1_name": p1.strip() or "Player 1",
            "player2_name": p2.strip() or "Player 2",
        }
        with open(PROFILE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass

# ---------------------------------------------------------------------------
# Windows High-DPI Awareness: Must be set BEFORE pygame.init() to eliminate
# blurry bilinear stretching on 125%, 150%, and 200% Windows display scaling.
# ---------------------------------------------------------------------------
def _enable_windows_dpi_awareness() -> None:
    try:
        import ctypes
        # PROCESS_PER_MONITOR_DPI_AWARE_V2 = 2
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            import ctypes
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

_enable_windows_dpi_awareness()

import pygame
import pygame.gfxdraw

from ai import Difficulty, DotsAndBoxesAI, analyze_position
from engines import AlgorithmType
from game_logic import AI, DRAW, HUMAN, DotsAndBoxesState, Move

WINDOW_WIDTH = 1040
WINDOW_HEIGHT = 760
FPS = 60

GameMode = Literal["pve", "pvp", "eve"]  # Human vs AI, 2 Players, AI vs AI
AppState = Literal["setup", "game"]

# ---------------------------------------------------------------------------
# Classic Game Night Tabletop Palette (Espresso, Warm Walnut, Ruby & Sapphire)
# ---------------------------------------------------------------------------
BG_TOP = (24, 21, 19)              # Deep Mahogany Espresso
BG_BOTTOM = (15, 13, 12)           # Dark Shadow Walnut
PANEL_BG = (32, 28, 25)            # Rich Dark Wood Tray
PANEL_BG_SUBTLE = (40, 36, 32)     # Secondary Warm Card
PANEL_BORDER = (64, 56, 48)        # Warm Wood / Antique Brass Outline
PANEL_BORDER_LIGHT = (48, 42, 36)
BOARD_BG = (25, 22, 20)            # Classic Tabletop Game Board
BOARD_INNER = (38, 33, 29)

TEXT_PRIMARY = (245, 240, 232)     # Warm Antique Parchment
TEXT_SECONDARY = (185, 175, 160)   # Soft Warm Beige
TEXT_MUTED = (135, 125, 115)       # Muted Warm Taupe
TEXT_ON_DARK = (255, 255, 255)

# Player 1: Rich Ruby Crimson Game Token
P1_COLOR = (215, 45, 55)
P1_BRIGHT = (245, 85, 95)
P1_TINT = (56, 26, 28)
P1_GLOW = (195, 40, 50)

# Player 2: Royal Sapphire Blue Game Token
P2_COLOR = (35, 115, 215)
P2_BRIGHT = (80, 160, 255)
P2_TINT = (22, 38, 62)
P2_GLOW = (30, 100, 190)

# Backward-compatible aliases
HUMAN_COLOR = P1_COLOR
HUMAN_BRIGHT = P1_BRIGHT
HUMAN_GLOW = P1_GLOW
AI_COLOR = P2_COLOR
AI_BRIGHT = P2_BRIGHT
AI_GLOW = P2_GLOW

# Warm Antique Brass / Gold for trophies, turns, and highlights
GOLD_GLOW = (215, 160, 50)
GOLD_BRIGHT = (245, 195, 85)

# Board elements: Ivory / Polished Maple pegs
DOT_COLOR = (235, 226, 210)
DOT_SHADOW = (14, 12, 10)
GUIDE_EDGE = (56, 50, 44)

# Button states
BTN_BG = (42, 38, 34)
BTN_BORDER = (72, 64, 54)
BTN_HOVER = (58, 52, 45)
BTN_ACTIVE = (215, 160, 50)
BTN_ACTIVE_BORDER = (245, 195, 85)
BTN_DISABLED = (28, 25, 22)
BTN_DISABLED_BORDER = (42, 38, 34)


def _draw_aa_circle(
    surface: pygame.Surface,
    x: int | float,
    y: int | float,
    radius: int | float,
    color: tuple[int, ...],
) -> None:
    """Draw a smooth, vector anti-aliased filled circle using pygame.gfxdraw."""
    ix = int(round(x))
    iy = int(round(y))
    ir = int(round(radius))
    if ir <= 0:
        return
    c = color if len(color) == 4 else (*color[:3], 255)
    pygame.gfxdraw.filled_circle(surface, ix, iy, ir, c)
    pygame.gfxdraw.aacircle(surface, ix, iy, ir, c)


def _draw_aa_line(
    surface: pygame.Surface,
    p1: tuple[int | float, int | float],
    p2: tuple[int | float, int | float],
    width: int,
    color: tuple[int, ...],
) -> None:
    """Draw a crisp, anti-aliased stroke with rounded caps."""
    ix1, iy1 = int(round(p1[0])), int(round(p1[1]))
    ix2, iy2 = int(round(p2[0])), int(round(p2[1]))
    pygame.draw.line(surface, color, (ix1, iy1), (ix2, iy2), width)
    if width > 2:
        r = width // 2
        _draw_aa_circle(surface, ix1, iy1, r, color)
        _draw_aa_circle(surface, ix2, iy2, r, color)


@dataclass
class Button:
    """Clickable UI button."""

    rect: pygame.Rect
    label: str
    value: object = None
    active: bool = False
    disabled: bool = False


@dataclass
class SetupCard:
    """Card on the initial launch/setup screen with title, subtitle, and pastel tint."""

    rect: pygame.Rect
    category: str      # "mode", "size", "difficulty", "first"
    value: object
    title: str = ""
    subtitle: str = ""
    active: bool = False
    tint: tuple[int, int, int] = (242, 247, 255)
    border: tuple[int, int, int] = (100, 150, 230)
    accent: tuple[int, int, int] = (30, 85, 185)
    p1_label: str = ""
    p2_label: str = ""
    c1: tuple[int, int, int] = (0, 0, 0)
    c2: tuple[int, int, int] = (0, 0, 0)


@dataclass
class Particle:
    """Soft particle emitted on box captures and game completion."""

    x: float
    y: float
    vx: float
    vy: float
    radius: float
    color: tuple[int, int, int]
    life: float
    max_life: float


@dataclass
class FloatingText:
    """Rising score popup (+1, +2) over captured boxes."""

    x: float
    y: float
    text: str
    color: tuple[int, int, int]
    life: float
    max_life: float


def _ease_out_back(t: float) -> float:
    t = max(0.0, min(1.0, t))
    c1 = 1.70158
    c3 = c1 + 1.0
    return 1.0 + c3 * pow(t - 1.0, 3) + c1 * pow(t - 1.0, 2)


def _ease_out_cubic(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return 1.0 - pow(1.0 - t, 3)


class DotsAndBoxesApp:
    """Interactive Pygame application for Dots and Boxes.
    Features a strategic Match Setup / Loading Screen and full in-game engine.
    """

    def __init__(self) -> None:
        pygame.init()
        pygame.display.set_caption("Dots & Boxes — Classic Tabletop Edition")
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        self.clock = pygame.time.Clock()

        # Typography
        font_name = "segoeui" if "segoeui" in pygame.font.get_fonts() else "arial"
        self.font_title = pygame.font.SysFont(font_name, 28, bold=True)
        self.font_big_title = pygame.font.SysFont(font_name, 36, bold=True)
        self.font_hero = pygame.font.SysFont(font_name, 34, bold=True)
        self.font_badge = pygame.font.SysFont(font_name, 11, bold=True)
        self.font_heading = pygame.font.SysFont(font_name, 13, bold=True)
        self.font_card_title = pygame.font.SysFont(font_name, 14, bold=True)
        self.font_body = pygame.font.SysFont(font_name, 13)
        self.font_small = pygame.font.SysFont(font_name, 11)
        self.font_tag = pygame.font.SysFont(font_name, 10, bold=True)
        self.font_vs = pygame.font.SysFont(font_name, 11, bold=True)
        self.font_score = pygame.font.SysFont(font_name, 36, bold=True)
        self.font_box = pygame.font.SysFont(font_name, 16, bold=True)
        self.font_popup = pygame.font.SysFont(font_name, 18, bold=True)
        self.font_btn = pygame.font.SysFont(font_name, 16, bold=True)
        self.font_modal_title = pygame.font.SysFont(font_name, 30, bold=True)
        self.font_input = pygame.font.SysFont(font_name, 18, bold=True)

        # Stored player names & name entry modal state
        prof = load_player_profile()
        self.player1_name: str = prof.get("player1_name", "Player 1")
        self.player2_name: str = prof.get("player2_name", "Player 2")
        self.show_name_modal: bool = False
        self.name_modal_focus: str = "p1"
        self.name_modal_input_p1: str = self.player1_name
        self.name_modal_input_p2: str = self.player2_name
        self._name_modal_rect = pygame.Rect(0, 0, 0, 0)
        self._name_input1_rect = pygame.Rect(0, 0, 0, 0)
        self._name_input2_rect = pygame.Rect(0, 0, 0, 0)
        self._name_confirm_btn_rect = pygame.Rect(0, 0, 0, 0)
        self._name_close_btn_rect = pygame.Rect(0, 0, 0, 0)
        self.p1_name_edit_rect = pygame.Rect(215, 319, 110, 22)
        self.p2_name_edit_rect = pygame.Rect(715, 319, 110, 22)

        # Ambient floating particle field for dynamic motion
        self.ambient_particles: list[dict] = []
        for _ in range(18):
            self.ambient_particles.append({
                "x": random.uniform(0, WINDOW_WIDTH),
                "y": random.uniform(0, WINDOW_HEIGHT),
                "vx": random.uniform(-0.25, 0.25),
                "vy": random.uniform(-0.35, -0.05),
                "r": random.uniform(18, 55),
                "color": random.choice([
                    (*P1_COLOR, 12),
                    (*P2_COLOR, 12),
                    (*GOLD_GLOW, 14),
                    (100, 150, 240, 10),
                    (140, 90, 210, 10),
                ]),
                "phase": random.uniform(0, math.tau),
            })

        # Top utility buttons & modal state
        self.info_btn = Button(rect=pygame.Rect(WINDOW_WIDTH - 100, 16, 32, 32), label="?", value="info")
        self.settings_btn = Button(rect=pygame.Rect(WINDOW_WIDTH - 60, 16, 32, 32), label="~", value="settings")
        self.show_rules_modal: bool = False
        self.rules_close_btn = Button(rect=pygame.Rect(WINDOW_WIDTH // 2 - 80, 560, 160, 38), label="Got it", value="close_rules")

        # Application flow state
        self.app_state: AppState = "setup"

        # Settings
        self.mode: GameMode = "pve"
        self.grid_size: int = 3
        self.difficulty: Difficulty = "medium"
        self.first_player: int = HUMAN
        self.eve_paused: bool = False
        self.eve_speeds: list[tuple[str, float]] = [
            ("1.2s", 1.2),  # Normal readable pace (default)
            ("2.0s", 2.0),  # Slow / Study mode
            ("0.5s", 0.5),  # Fast simulation
        ]
        self.eve_speed_idx: int = 0
        self.current_analysis: dict = {}
        self.analysis_player: int = AI

        # Game & AI state
        self.ai_algorithm: AlgorithmType = "alphabeta"
        self.ai_p1_algorithm: AlgorithmType = "alphabeta"
        self.state = DotsAndBoxesState(self.grid_size, self.grid_size, self.first_player)
        self.ai = DotsAndBoxesAI(self.difficulty, player_id=AI, algorithm=self.ai_algorithm)
        self.ai_p1 = DotsAndBoxesAI(self.difficulty, player_id=HUMAN, algorithm=self.ai_p1_algorithm)
        self.edge_owners: dict[Move, int] = {}
        self.last_ai_moves: list[Move] = []
        self.status_text: str = ""
        self.hint_move: Move | None = None
        self.hint_expiry: float = 0.0

        # Animation state
        self.edge_anim_start: dict[Move, float] = {}
        self.box_anim_start: dict[tuple[int, int], float] = {}
        self.particles: list[Particle] = []
        self.floating_texts: list[FloatingText] = []
        self._rng = random.Random()
        self._victory_celebrated: bool = False

        # Async AI worker tracking
        self.generation: int = 0
        self.ai_thread: threading.Thread | None = None
        self.ai_pending_move: tuple[int, Move] | None = None
        self.ai_wait_until: float = 0.0
        self._ai_lock = threading.Lock()

        # Layout geometry: Centered majestic tabletop board
        self.board_panel = pygame.Rect(WINDOW_WIDTH // 2 - 300, 136, 600, 600)

        self.hovered_move: Move | None = None
        self.buttons: dict[str, list[Button]] = {}
        self.setup_cards: list[SetupCard] = []

        self._bg_surface = self._build_background()
        self._build_setup_cards()
        self._build_buttons()
        self._reset_game()

    def _build_background(self) -> pygame.Surface:
        """Render a rich, warm dark espresso tabletop background with soft ambient corner warmth."""
        bg = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT))
        for y in range(WINDOW_HEIGHT):
            t = y / WINDOW_HEIGHT
            r = int(BG_TOP[0] + (BG_BOTTOM[0] - BG_TOP[0]) * t)
            g = int(BG_TOP[1] + (BG_BOTTOM[1] - BG_TOP[1]) * t)
            b = int(BG_TOP[2] + (BG_BOTTOM[2] - BG_TOP[2]) * t)
            pygame.draw.line(bg, (r, g, b), (0, y), (WINDOW_WIDTH, y))

        # Soft ambient corner warmth (warm amber and ruby/sapphire tabletop reflections)
        glow = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)
        for radius, alpha in ((380, 14), (250, 16), (140, 18)):
            pygame.draw.circle(glow, (*P1_GLOW, alpha), (160, 140), radius)
            pygame.draw.circle(glow, (*P2_GLOW, alpha), (920, 640), radius)
            pygame.draw.circle(glow, (*GOLD_GLOW, 12), (WINDOW_WIDTH // 2, 80), 220)
        bg.blit(glow, (0, 0))
        return bg

    def _build_setup_cards(self) -> None:
        """Build the clean Player vs Opponent matchup cards and selectors."""
        self.setup_cards.clear()

        # 1. Mode Tabs (Top Center)
        modes = [
            ("pve", "VS AI"),
            ("pvp", "2 PLAYERS"),
            ("eve", "AI VS AI"),
        ]
        tab_w = 120
        total_tabs_w = len(modes) * tab_w + (len(modes) - 1) * 10
        start_tab_x = WINDOW_WIDTH // 2 - total_tabs_w // 2
        for idx, (val, title) in enumerate(modes):
            r = pygame.Rect(start_tab_x + idx * (tab_w + 10), 68, tab_w, 30)
            self.setup_cards.append(SetupCard(rect=r, category="mode", value=val, title=title))

        # 2. Card Dimensions
        card_w = 390
        card_h = 425
        card_y = 115
        p1_rect = pygame.Rect(75, card_y, card_w, card_h)
        p2_rect = pygame.Rect(WINDOW_WIDTH - 75 - card_w, card_y, card_w, card_h)

        # 3. Turn status buttons (inside cards)
        t1_rect = pygame.Rect(p1_rect.x + 30, p1_rect.y + 344, 330, 42)
        t2_rect = pygame.Rect(p2_rect.x + 30, p2_rect.y + 344, 330, 42)
        self.setup_cards.append(
            SetupCard(rect=t1_rect, category="first", value=HUMAN, title="PLAYER 1")
        )
        self.setup_cards.append(
            SetupCard(rect=t2_rect, category="first", value=AI, title="OPPONENT")
        )

        # 4. Algorithm Selection Options
        algos = [
            ("alphabeta", "α-β Minimax"),
            ("berlekamp", "Berlekamp"),
            ("policy_value", "Neural PV"),
            ("mcts", "MCTS Tree"),
        ]
        pill_w = 158
        pill_h = 32

        if self.mode == "pve":
            # Opponent Algorithm choices on Right card
            for k, (a_val, a_lbl) in enumerate(algos):
                col_idx = k % 2
                row_idx = k // 2
                ax = p2_rect.x + 30 + col_idx * (pill_w + 14)
                ay = p2_rect.y + 240 + row_idx * (pill_h + 8)
                ar = pygame.Rect(ax, ay, pill_w, pill_h)
                self.setup_cards.append(SetupCard(rect=ar, category="algorithm", value=a_val, title=a_lbl))

        elif self.mode == "eve":
            # AI 1 Algorithm choices on Left card
            for k, (a_val, a_lbl) in enumerate(algos):
                col_idx = k % 2
                row_idx = k // 2
                ax = p1_rect.x + 30 + col_idx * (pill_w + 14)
                ay = p1_rect.y + 240 + row_idx * (pill_h + 8)
                ar = pygame.Rect(ax, ay, pill_w, pill_h)
                self.setup_cards.append(SetupCard(rect=ar, category="algo_p1", value=a_val, title=a_lbl))

            # AI 2 Algorithm choices on Right card
            for k, (a_val, a_lbl) in enumerate(algos):
                col_idx = k % 2
                row_idx = k // 2
                ax = p2_rect.x + 30 + col_idx * (pill_w + 14)
                ay = p2_rect.y + 240 + row_idx * (pill_h + 8)
                ar = pygame.Rect(ax, ay, pill_w, pill_h)
                self.setup_cards.append(SetupCard(rect=ar, category="algo_p2", value=a_val, title=a_lbl))

        # 5. Board Size Selector (Bottom Bar)
        sizes = [
            (3, "3 × 3 (9 Boxes)"),
            (4, "4 × 4 (16 Boxes)"),
            (5, "5 × 5 (25 Boxes)"),
        ]
        btn_w = 120
        b_lbl_x = WINDOW_WIDTH // 2 - 170
        for idx, (val, title) in enumerate(sizes):
            br = pygame.Rect(b_lbl_x + 90 + idx * (btn_w + 8), 556, btn_w, 30)
            self.setup_cards.append(SetupCard(rect=br, category="size", value=val, title=title))

        # 6. Start Game Button
        self.start_game_btn = Button(
            rect=pygame.Rect(WINDOW_WIDTH // 2 - 180, 612, 360, 56),
            label="START MATCH  >",
            value="start",
        )

    def _sync_setup_cards(self) -> None:
        """Sync active status of setup cards with currently chosen settings."""
        for card in self.setup_cards:
            if card.category == "mode":
                card.active = card.value == self.mode
            elif card.category == "size":
                card.active = card.value == self.grid_size
            elif card.category == "first":
                card.active = card.value == self.first_player
            elif card.category == "algorithm":
                card.active = card.value == self.ai_algorithm
            elif card.category == "algo_p1":
                card.active = card.value == self.ai_p1_algorithm
            elif card.category == "algo_p2":
                card.active = card.value == self.ai_algorithm

    def _get_algo_short_name(self, algo: str) -> str:
        mapping = {
            "alphabeta": "α-β Minimax",
            "mcts": "MCTS",
            "berlekamp": "Berlekamp",
            "policy_value": "Neural PV",
        }
        return mapping.get(algo, algo)

    def _get_algo_full_name(self, algo: str) -> str:
        mapping = {
            "alphabeta": "Iterative Deepening Alpha-Beta (Minimax + TT)",
            "mcts": "Monte Carlo Tree Search (MCTS + UCB1)",
            "berlekamp": "Berlekamp Combinatorial Solver (Nimstring)",
            "policy_value": "Policy-Value Neural Network (PUCT Guided)",
        }
        return mapping.get(algo, algo)

    def _build_buttons(self) -> None:
        self.buttons.clear()

        # 1. Top left action buttons: Setup & New Game
        self.header_setup_btn = Button(rect=pygame.Rect(40, 14, 110, 28), label="← Match Setup", value="setup")
        new_game_btn = Button(rect=pygame.Rect(158, 14, 95, 28), label="New Game", value="new")

        # 2. Top right action buttons based on Mode
        if self.mode == "eve":
            # Spectator Controls on the right: Speed, Step, Pause/Resume
            eve_pause_label = "Resume" if self.eve_paused else "Pause"
            speed_label = f"Speed: {self.eve_speeds[self.eve_speed_idx][0]}"
            pause_btn = Button(rect=pygame.Rect(WINDOW_WIDTH - 40 - 80, 14, 80, 28), label=eve_pause_label, value="toggle_pause")
            step_btn = Button(rect=pygame.Rect(WINDOW_WIDTH - 40 - 80 - 74, 14, 68, 28), label="Step >", value="step")
            speed_btn = Button(rect=pygame.Rect(WINDOW_WIDTH - 40 - 80 - 74 - 96, 14, 90, 28), label=speed_label, value="cycle_speed")
            self.buttons["eve_controls"] = [pause_btn, step_btn, speed_btn]
            self.buttons["actions"] = [self.header_setup_btn, new_game_btn]

        elif self.mode == "pve":
            undo_btn = Button(rect=pygame.Rect(WINDOW_WIDTH - 40 - 76, 14, 76, 28), label="Undo", value="undo")
            hint_btn = Button(rect=pygame.Rect(WINDOW_WIDTH - 40 - 76 - 82, 14, 76, 28), label="Hint", value="hint")
            self.buttons["actions"] = [self.header_setup_btn, new_game_btn, hint_btn, undo_btn]

        else:  # pvp
            undo_btn = Button(rect=pygame.Rect(WINDOW_WIDTH - 40 - 80, 14, 80, 28), label="Undo", value="undo")
            self.buttons["actions"] = [self.header_setup_btn, new_game_btn, undo_btn]

        # Centered modal Play Again & Match Setup buttons
        self.play_again_btn = Button(
            rect=pygame.Rect(
                self.board_panel.centerx - 170, self.board_panel.centery + 52, 160, 42
            ),
            label="Play Again",
            value="new",
        )
        self.modal_setup_btn = Button(
            rect=pygame.Rect(
                self.board_panel.centerx + 10, self.board_panel.centery + 52, 160, 42
            ),
            label="Match Setup",
            value="setup",
        )

    def _sync_button_states(self) -> None:
        # Update AI vs AI controls
        if "eve_controls" in self.buttons and len(self.buttons["eve_controls"]) >= 3:
            self.buttons["eve_controls"][0].label = "Resume" if self.eve_paused else "Pause"
            self.buttons["eve_controls"][1].disabled = not self.eve_paused or self.state.is_game_over()
            self.buttons["eve_controls"][2].label = f"Speed: {self.eve_speeds[self.eve_speed_idx][0]}"

        # Undo & Hint button behavior
        has_history = len(self.state.history) > 0
        for btn in self.buttons.get("actions", []):
            if btn.value == "undo":
                btn.disabled = not has_history or self.state.is_game_over() or (self.mode == "eve" and not self.eve_paused)
            elif btn.value == "hint":
                btn.disabled = self.state.is_game_over() or (self.mode == "eve") or (self.mode == "pve" and self.state.current_player == AI)

    def _confirm_name_modal(self) -> None:
        """Confirm entered player names, persist to disk, and launch the match."""
        p1 = self.name_modal_input_p1.strip() or "Player 1"
        p2 = self.name_modal_input_p2.strip() or "Player 2"
        self.player1_name = p1
        self.player2_name = p2
        save_player_profile(p1, p2)
        self.show_name_modal = False
        self.app_state = "game"
        self._build_buttons()
        self._reset_game()

    def _get_player_box_label(self, owner: int) -> str:
        """Return the short ownership label displayed inside completed boxes."""
        if self.mode == "pve":
            if owner == HUMAN:
                n = self.player1_name.strip()
                return n.upper() if len(n) <= 5 else n[:4].upper()
            return "AI"
        elif self.mode == "pvp":
            if owner == HUMAN:
                n = self.player1_name.strip()
                return n.upper() if len(n) <= 5 else n[:4].upper()
            else:
                n = self.player2_name.strip()
                return n.upper() if len(n) <= 5 else n[:4].upper()
        else:
            return "AI 1" if owner == HUMAN else "AI 2"

    def _reset_game(self) -> None:
        self.generation += 1
        with self._ai_lock:
            self.ai_pending_move = None
        self.ai_thread = None
        self.hint_move = None
        self.hint_expiry = 0.0

        self.state = DotsAndBoxesState(self.grid_size, self.grid_size, self.first_player)
        self.ai = DotsAndBoxesAI(self.difficulty, player_id=AI, algorithm=self.ai_algorithm)
        self.ai_p1 = DotsAndBoxesAI(self.difficulty, player_id=HUMAN, algorithm=self.ai_p1_algorithm)
        self.edge_owners.clear()
        self.last_ai_moves.clear()
        self.edge_anim_start.clear()
        self.box_anim_start.clear()
        self.particles.clear()
        self.floating_texts.clear()
        self.hovered_move = None
        self._victory_celebrated = False
        self.current_analysis.clear()
        self.analysis_player = self.first_player

        if self.mode == "pve":
            if self.first_player == HUMAN:
                self.status_text = f"{self.player1_name}'s turn \u2014 click any dashed line."
            else:
                self.status_text = "AI goes first \u2014 computing move..."
                self.ai_wait_until = time.perf_counter() + 0.35
        elif self.mode == "pvp":
            p = self.player1_name if self.first_player == HUMAN else self.player2_name
            self.status_text = f"{p}'s turn \u2014 click any dashed line to claim."
        else:  # eve
            p = "AI 1" if self.first_player == HUMAN else "AI 2"
            self.status_text = f"AI vs AI match initialized \u2014 {p} to play."
            self.ai_wait_until = time.perf_counter() + 0.40

        self._sync_button_states()
        self._sync_setup_cards()

    def _board_geometry(self) -> tuple[int, int, float]:
        """Return (origin_x, origin_y, cell_size) centered within the board panel."""
        pad = 66
        usable = min(self.board_panel.width, self.board_panel.height) - pad * 2
        cell_size = usable / self.state.rows
        grid_w = cell_size * self.state.cols
        grid_h = cell_size * self.state.rows
        origin_x = int(round(self.board_panel.centerx - grid_w / 2))
        origin_y = int(round(self.board_panel.centery - grid_h / 2))
        return origin_x, origin_y, cell_size

    def _edge_endpoints(self, move: Move) -> tuple[tuple[float, float], tuple[float, float]]:
        ox, oy, cell = self._board_geometry()
        orient, r, c = move
        if orient == "h":
            x1 = ox + c * cell
            y1 = oy + r * cell
            return (x1, y1), (x1 + cell, y1)
        x1 = ox + c * cell
        y1 = oy + r * cell
        return (x1, y1), (x1, y1 + cell)

    def _spawn_box_effects(self, completed_boxes: tuple[tuple[int, int], ...], owner: int) -> None:
        if not completed_boxes:
            return
        ox, oy, cell = self._board_geometry()
        now = time.perf_counter()
        color = P1_COLOR if owner == HUMAN else P2_COLOR
        bright = P1_BRIGHT if owner == HUMAN else P2_BRIGHT

        for br, bc in completed_boxes:
            self.box_anim_start[(br, bc)] = now
            cx = ox + (bc + 0.5) * cell
            cy = oy + (br + 0.5) * cell
            for _ in range(16):
                angle = self._rng.uniform(0, math.tau)
                speed = self._rng.uniform(40, 160)
                p_color = color if self._rng.random() < 0.65 else bright
                self.particles.append(
                    Particle(
                        x=cx,
                        y=cy,
                        vx=math.cos(angle) * speed,
                        vy=math.sin(angle) * speed,
                        radius=self._rng.uniform(2.0, 4.0),
                        color=p_color,
                        life=0.55,
                        max_life=0.55,
                    )
                )

        # Rising floating text popup
        br0, bc0 = completed_boxes[0]
        px = ox + (bc0 + 0.5) * cell
        py = oy + (br0 + 0.5) * cell - 12
        self.floating_texts.append(
            FloatingText(
                x=px,
                y=py,
                text=f"+{len(completed_boxes)}",
                color=color,
                life=0.85,
                max_life=0.85,
            )
        )

    def _spawn_victory_confetti(self) -> None:
        if self._victory_celebrated:
            return
        self._victory_celebrated = True
        winner = self.state.get_winner()
        if winner == HUMAN:
            palette = [P1_COLOR, P1_BRIGHT, GOLD_GLOW]
        elif winner == AI:
            palette = [P2_COLOR, P2_BRIGHT, GOLD_GLOW]
        else:
            palette = [P1_COLOR, P2_COLOR, GOLD_GLOW]

        for _ in range(75):
            x = self._rng.uniform(self.board_panel.left + 40, self.board_panel.right - 40)
            y = self._rng.uniform(self.board_panel.top + 40, self.board_panel.centery)
            angle = self._rng.uniform(0, math.tau)
            speed = self._rng.uniform(50, 220)
            self.particles.append(
                Particle(
                    x=x,
                    y=y,
                    vx=math.cos(angle) * speed,
                    vy=math.sin(angle) * speed - 50,
                    radius=self._rng.uniform(2.5, 4.8),
                    color=self._rng.choice(palette),
                    life=1.4,
                    max_life=1.4,
                )
            )

    def _update_effects(self, dt: float) -> None:
        alive_particles: list[Particle] = []
        for p in self.particles:
            p.life -= dt
            if p.life > 0:
                p.x += p.vx * dt
                p.y += p.vy * dt
                p.vx *= 0.94
                p.vy = p.vy * 0.94 + 80 * dt
                alive_particles.append(p)
        self.particles = alive_particles

        alive_texts: list[FloatingText] = []
        for ft in self.floating_texts:
            ft.life -= dt
            if ft.life > 0:
                ft.y -= 32 * dt
                alive_texts.append(ft)
        self.floating_texts = alive_texts

    def _find_hovered_move(self, pos: tuple[int, int]) -> Move | None:
        if self.app_state != "game" or self.state.is_game_over():
            return None
        # Only human can hover in PvE (human turn) or PvP
        if self.mode == "eve":
            return None
        if self.mode == "pve" and self.state.current_player != HUMAN:
            return None

        mx, my = pos
        if not self.board_panel.collidepoint(mx, my):
            return None

        _, _, cell = self._board_geometry()
        threshold = max(16.0, cell * 0.22)
        best_move: Move | None = None
        best_dist = threshold

        for move in self.state.get_valid_moves():
            (x1, y1), (x2, y2) = self._edge_endpoints(move)
            if move[0] == "h":
                if x1 - 12 <= mx <= x2 + 12:
                    cx = max(x1, min(mx, x2))
                    dist = math.hypot(mx - cx, my - y1)
                    if dist < best_dist:
                        best_dist = dist
                        best_move = move
            else:
                if y1 - 12 <= my <= y2 + 12:
                    cy = max(y1, min(my, y2))
                    dist = math.hypot(mx - x1, my - cy)
                    if dist < best_dist:
                        best_dist = dist
                        best_move = move
        return best_move

    def _apply_human_move(self, move: Move) -> None:
        if self.state.is_edge_drawn(move) or self.state.is_game_over():
            return

        active_player = self.state.current_player
        self.last_ai_moves.clear()
        self.edge_owners[move] = active_player
        self.edge_anim_start[move] = time.perf_counter()
        completed = self.state.make_move(move)
        self.current_analysis = analyze_position(self.state, my_player=self.state.current_player)
        self.analysis_player = self.state.current_player

        if completed > 0 and self.state.history:
            self._spawn_box_effects(self.state.history[-1].completed_boxes, active_player)

        if self.state.is_game_over():
            self._set_game_over_status()
            self._spawn_victory_confetti()
        elif completed > 0:
            plural = "es" if completed > 1 else ""
            if self.mode == "pve":
                self.status_text = f"{self.player1_name} captured +{completed} box{plural}! Take another turn."
            else:
                p_label = self.player1_name if active_player == HUMAN else self.player2_name
                self.status_text = f"{p_label} captured +{completed} box{plural} \u2014 bonus turn!"
        else:
            if self.mode == "pve":
                self.status_text = "AI is computing its move..."
                self.ai_wait_until = time.perf_counter() + 0.28
            else:
                next_p = self.player1_name if self.state.current_player == HUMAN else self.player2_name
                self.status_text = f"{next_p}'s turn \u2014 pick a dashed line."

        self._sync_button_states()

    def _undo_last_turn(self) -> None:
        if not self.state.history:
            return

        self.generation += 1
        with self._ai_lock:
            self.ai_pending_move = None
        self.ai_thread = None

        if self.mode == "pve":
            self.state.undo_to_human_turn()
            self.status_text = f"Undid last turn \u2014 {self.player1_name}'s move."
        else:
            # In PvP or EvE paused mode, undo the single most recent edge
            self.state.undo_move()
            if self.mode == "pvp":
                p = self.player1_name if self.state.current_player == HUMAN else self.player2_name
                self.status_text = f"Undid move \u2014 {p}'s turn."
            else:
                p = "AI 1" if self.state.current_player == HUMAN else "AI 2"
                self.status_text = f"Undid move \u2014 {p}'s turn."

        self.edge_owners = {rec.move: rec.player for rec in self.state.history}
        self.edge_anim_start.clear()
        self.box_anim_start.clear()
        self.particles.clear()
        self.floating_texts.clear()
        self.last_ai_moves.clear()
        self._victory_celebrated = False
        self._sync_button_states()

    def _set_game_over_status(self) -> None:
        winner = self.state.get_winner()
        s1 = self.state.scores[HUMAN]
        s2 = self.state.scores[AI]

        if self.mode == "pve":
            if winner == HUMAN:
                self.status_text = f"Victory! {self.player1_name} won {s1} to {s2}."
            elif winner == AI:
                self.status_text = f"AI Wins \u2014 {s2} to {s1}."
            else:
                self.status_text = f"Draw Game \u2014 {s1} to {s2}."
        elif self.mode == "pvp":
            if winner == HUMAN:
                self.status_text = f"{self.player1_name} Wins! Score: {s1} - {s2}"
            elif winner == AI:
                self.status_text = f"{self.player2_name} Wins! Score: {s2} - {s1}"
            else:
                self.status_text = f"Draw Game \u2014 Tied at {s1}."
        else:  # eve
            if winner == HUMAN:
                self.status_text = f"AI 1 Wins! Score: {s1} - {s2}"
            elif winner == AI:
                self.status_text = f"AI 2 Wins! Score: {s2} - {s1}"
            else:
                self.status_text = f"AI vs AI Draw \u2014 Tied at {s1}."

    def _update_ai(self) -> None:
        """Handle AI move selection for Human vs AI mode."""
        if self.state.is_game_over() or self.state.current_player != AI:
            return

        with self._ai_lock:
            pending = self.ai_pending_move
            if pending is not None:
                self.ai_pending_move = None

        if pending is not None:
            gen, move = pending
            if gen == self.generation and not self.state.is_edge_drawn(move):
                self.edge_owners[move] = AI
                self.edge_anim_start[move] = time.perf_counter()
                self.last_ai_moves.append(move)
                completed = self.state.make_move(move)

                if completed > 0 and self.state.history:
                    self._spawn_box_effects(self.state.history[-1].completed_boxes, AI)

                if self.state.is_game_over():
                    self._set_game_over_status()
                    self._spawn_victory_confetti()
                elif completed > 0:
                    plural = "es" if completed > 1 else ""
                    self.status_text = f"AI scored +{completed} box{plural} & goes again..."
                    self.ai_wait_until = time.perf_counter() + 0.38
                else:
                    self.status_text = "Your turn — pick an edge."
                self._sync_button_states()
            return

        if time.perf_counter() < self.ai_wait_until:
            return
        if self.ai_thread is not None and self.ai_thread.is_alive():
            return

        snapshot = self.state.clone()
        gen = self.generation
        ai_instance = self.ai

        def worker() -> None:
            chosen = ai_instance.choose_move(snapshot)
            analysis = getattr(ai_instance, "last_analysis", None)
            with self._ai_lock:
                if gen == self.generation:
                    self.ai_pending_move = (gen, chosen)
                    if analysis:
                        self.current_analysis = analysis
                        self.analysis_player = AI

        self.ai_thread = threading.Thread(target=worker, daemon=True)
        self.ai_thread.start()

    def _update_eve(self) -> None:
        """Handle AI vs AI spectator duel turns."""
        if self.state.is_game_over() or self.eve_paused:
            return

        with self._ai_lock:
            pending = self.ai_pending_move
            if pending is not None:
                self.ai_pending_move = None

        if pending is not None:
            gen, move = pending
            if gen == self.generation and not self.state.is_edge_drawn(move):
                current_p = self.state.current_player
                self.edge_owners[move] = current_p
                self.edge_anim_start[move] = time.perf_counter()
                self.last_ai_moves = [move]
                completed = self.state.make_move(move)

                if completed > 0 and self.state.history:
                    self._spawn_box_effects(self.state.history[-1].completed_boxes, current_p)

                delay = self.eve_speeds[self.eve_speed_idx][1]
                if self.state.is_game_over():
                    self._set_game_over_status()
                    self._spawn_victory_confetti()
                elif completed > 0:
                    p_name = "AI 1" if current_p == HUMAN else "AI 2"
                    plural = "es" if completed > 1 else ""
                    self.status_text = f"{p_name} captured +{completed} box{plural} & continues..."
                    self.ai_wait_until = time.perf_counter() + delay
                else:
                    next_p = "AI 1" if self.state.current_player == HUMAN else "AI 2"
                    self.status_text = f"{next_p}'s turn to move..."
                    self.ai_wait_until = time.perf_counter() + delay
                self._sync_button_states()
            return

        if time.perf_counter() < self.ai_wait_until:
            return
        if self.ai_thread is not None and self.ai_thread.is_alive():
            return

        snapshot = self.state.clone()
        gen = self.generation
        moving_player = self.state.current_player
        active_ai = self.ai_p1 if moving_player == HUMAN else self.ai

        def worker() -> None:
            chosen = active_ai.choose_move(snapshot)
            analysis = getattr(active_ai, "last_analysis", None)
            with self._ai_lock:
                if gen == self.generation:
                    self.ai_pending_move = (gen, chosen)
                    if analysis:
                        self.current_analysis = analysis
                        self.analysis_player = moving_player

        self.ai_thread = threading.Thread(target=worker, daemon=True)
        self.ai_thread.start()

    def _step_eve(self) -> None:
        """Advance one move in AI vs AI mode when paused."""
        if self.state.is_game_over():
            return
        current_p = self.state.current_player
        active_ai = self.ai_p1 if current_p == HUMAN else self.ai
        move = active_ai.choose_move(self.state)
        analysis = getattr(active_ai, "last_analysis", None)
        if analysis:
            self.current_analysis = analysis
            self.analysis_player = current_p

        self.edge_owners[move] = current_p
        self.edge_anim_start[move] = time.perf_counter()
        self.last_ai_moves = [move]
        completed = self.state.make_move(move)

        if completed > 0 and self.state.history:
            self._spawn_box_effects(self.state.history[-1].completed_boxes, current_p)

        if self.state.is_game_over():
            self._set_game_over_status()
            self._spawn_victory_confetti()
        else:
            p_name = "AI 1" if self.state.current_player == HUMAN else "AI 2"
            self.status_text = f"Stepped {p_name}'s move. Paused."
        self._sync_button_states()

    def _handle_setup_click(self, pos: tuple[int, int]) -> None:
        """Handle clicks on the Match Setup / Loading screen."""
        if self.show_name_modal:
            if self._name_close_btn_rect.collidepoint(pos) or not self._name_modal_rect.collidepoint(pos):
                self.show_name_modal = False
                return
            if self._name_confirm_btn_rect.collidepoint(pos):
                self._confirm_name_modal()
                return
            if self._name_input1_rect.collidepoint(pos):
                self.name_modal_focus = "p1"
                return
            if self.mode == "pvp" and self._name_input2_rect.collidepoint(pos):
                self.name_modal_focus = "p2"
                return
            return

        if self.show_rules_modal:
            if self.rules_close_btn.rect.collidepoint(pos):
                self.show_rules_modal = False
                return
            m_rect = pygame.Rect(WINDOW_WIDTH // 2 - 270, WINDOW_HEIGHT // 2 - 230, 540, 460)
            if not m_rect.collidepoint(pos):
                self.show_rules_modal = False
            return

        if self.info_btn.rect.collidepoint(pos):
            self.show_rules_modal = not self.show_rules_modal
            return

        if self.settings_btn.rect.collidepoint(pos):
            self.difficulty = "medium"
            self.grid_size = 3
            self._build_setup_cards()
            self._sync_setup_cards()
            return

        # Check clicking edit name badge on player cards
        if self.mode in ("pve", "pvp") and self.p1_name_edit_rect.collidepoint(pos):
            self.show_name_modal = True
            self.name_modal_focus = "p1"
            self.name_modal_input_p1 = self.player1_name
            self.name_modal_input_p2 = self.player2_name
            return

        if self.mode == "pvp" and self.p2_name_edit_rect.collidepoint(pos):
            self.show_name_modal = True
            self.name_modal_focus = "p2"
            self.name_modal_input_p1 = self.player1_name
            self.name_modal_input_p2 = self.player2_name
            return

        if self.start_game_btn.rect.collidepoint(pos):
            if self.mode in ("pve", "pvp") and os.environ.get("SDL_VIDEODRIVER") != "dummy":
                self.show_name_modal = True
                self.name_modal_focus = "p1"
                self.name_modal_input_p1 = self.player1_name
                self.name_modal_input_p2 = self.player2_name
                return
            self.app_state = "game"
            self._build_buttons()
            self._reset_game()
            return

        rebuild_cards = False
        for card in self.setup_cards:
            if card.rect.collidepoint(pos):
                if card.category == "mode":
                    if self.mode != card.value:
                        self.mode = card.value  # type: ignore[assignment]
                        rebuild_cards = True
                elif card.category == "size":
                    self.grid_size = int(card.value)  # type: ignore[arg-type]
                elif card.category == "algorithm":
                    self.ai_algorithm = card.value  # type: ignore[assignment]
                    self.ai.set_algorithm(self.ai_algorithm)
                elif card.category == "algo_p1":
                    self.ai_p1_algorithm = card.value  # type: ignore[assignment]
                    self.ai_p1.set_algorithm(self.ai_p1_algorithm)
                elif card.category == "algo_p2":
                    self.ai_algorithm = card.value  # type: ignore[assignment]
                    self.ai.set_algorithm(self.ai_algorithm)
                elif card.category == "difficulty":
                    self.difficulty = card.value  # type: ignore[assignment]
                    self.ai = DotsAndBoxesAI(self.difficulty, player_id=AI, algorithm=self.ai_algorithm)
                    self.ai_p1 = DotsAndBoxesAI(self.difficulty, player_id=HUMAN, algorithm=self.ai_p1_algorithm)
                elif card.category == "first":
                    self.first_player = int(card.value)  # type: ignore[arg-type]

        if rebuild_cards:
            self._build_setup_cards()
        self._sync_setup_cards()

    def _handle_game_click(self, pos: tuple[int, int]) -> None:
        """Handle clicks during the in-game screen."""
        if self.state.is_game_over():
            if self.play_again_btn.rect.collidepoint(pos):
                self._reset_game()
                return
            if self.modal_setup_btn.rect.collidepoint(pos):
                self.app_state = "setup"
                self._build_setup_cards()
                self._sync_setup_cards()
                return

        # Header Setup button
        if self.header_setup_btn.rect.collidepoint(pos):
            self.app_state = "setup"
            self._build_setup_cards()
            self._sync_setup_cards()
            return

        # AI vs AI spectator controls
        if self.mode == "eve" and "eve_controls" in self.buttons:
            eve_btns = self.buttons["eve_controls"]
            pause_btn = eve_btns[0]
            step_btn = eve_btns[1]
            speed_btn = eve_btns[2] if len(eve_btns) > 2 else None

            if pause_btn.rect.collidepoint(pos):
                self.eve_paused = not self.eve_paused
                self._sync_button_states()
                if self.eve_paused:
                    self.status_text = "AI match paused. Click 'Resume' or 'Step >' to examine moves."
                else:
                    self.status_text = "AI match resumed."
                    self.ai_wait_until = time.perf_counter() + 0.3
                return
            if step_btn.rect.collidepoint(pos) and not step_btn.disabled:
                self._step_eve()
                return
            if speed_btn and speed_btn.rect.collidepoint(pos):
                self.eve_speed_idx = (self.eve_speed_idx + 1) % len(self.eve_speeds)
                self._sync_button_states()
                speed_name, speed_val = self.eve_speeds[self.eve_speed_idx]
                self.status_text = f"AI speed set to {speed_name} ({speed_val:.1f}s per move)"
                return

        # Action buttons (Setup, New Game, Undo, Hint)
        for btn in self.buttons.get("actions", []):
            if btn.rect.collidepoint(pos) and not btn.disabled:
                if btn.value == "setup":
                    self.app_state = "setup"
                    self._build_setup_cards()
                    self._sync_setup_cards()
                    return
                elif btn.value == "new":
                    self._reset_game()
                    return
                elif btn.value == "undo":
                    self._undo_last_turn()
                    return
                elif btn.value == "hint":
                    if not self.state.is_game_over() and self.state.current_player == HUMAN:
                        hint_move = self.ai.choose_move(self.state)
                        self.hint_move = hint_move
                        self.hint_expiry = time.perf_counter() + 5.0
                        m_orient = "Horizontal" if hint_move[0] == "h" else "Vertical"
                        m_str = f"{'H' if hint_move[0] == 'h' else 'V'}[{hint_move[1]},{hint_move[2]}]"
                        algo_name = self._get_algo_short_name(self.ai_algorithm)
                        self.status_text = f"AI Hint ({algo_name}): Draw {m_orient} {m_str} (pulsing in gold)"
                    return

        # Human move click on board
        hovered = self._find_hovered_move(pos)
        if hovered is not None:
            self._apply_human_move(hovered)

    def _draw_rounded_panel(
        self,
        rect: pygame.Rect,
        bg: tuple[int, int, int],
        border: tuple[int, int, int] = PANEL_BORDER,
        radius: int = 12,
        border_width: int = 1,
    ) -> None:
        pygame.draw.rect(self.screen, bg, rect, border_radius=radius)
        if border_width > 0:
            pygame.draw.rect(self.screen, border, rect, width=border_width, border_radius=radius)

    def _draw_dashed_line(
        self,
        p1: tuple[float, float],
        p2: tuple[float, float],
        color: tuple[int, int, int],
        width: int = 2,
        dash_len: float = 6.0,
        gap_len: float = 6.0,
    ) -> None:
        dx = p2[0] - p1[0]
        dy = p2[1] - p1[1]
        total = math.hypot(dx, dy)
        if total <= 0:
            return
        ux, uy = dx / total, dy / total
        dist = 9.0
        end_limit = total - 9.0
        while dist < end_limit:
            seg_end = min(dist + dash_len, end_limit)
            s = (int(round(p1[0] + ux * dist)), int(round(p1[1] + uy * dist)))
            e = (int(round(p1[0] + ux * seg_end)), int(round(p1[1] + uy * seg_end)))
            pygame.draw.line(self.screen, color, s, e, width)
            dist += dash_len + gap_len

    def _draw_player_avatar(self, surf: pygame.Surface, cx: int, cy: int, col: tuple[int, int, int]) -> None:
        """Render a clean stylized player silhouette icon."""
        _draw_aa_circle(surf, cx, cy - 9, 8, col)
        rect = pygame.Rect(cx - 13, cy + 2, 26, 16)
        pygame.draw.ellipse(surf, col, rect)

    def _draw_ai_chip(self, surf: pygame.Surface, cx: int, cy: int, col: tuple[int, int, int]) -> None:
        """Render a clean stylized AI neural processor chip icon."""
        pygame.draw.rect(surf, col, (cx - 11, cy - 11, 22, 22), border_radius=4)
        pygame.draw.rect(surf, PANEL_BG, (cx - 6, cy - 6, 12, 12), border_radius=2)
        for off in (-5, 5):
            pygame.draw.line(surf, col, (cx + off, cy - 11), (cx + off, cy - 15), 2)
            pygame.draw.line(surf, col, (cx + off, cy + 11), (cx + off, cy + 15), 2)
            pygame.draw.line(surf, col, (cx - 11, cy + off), (cx - 15, cy + off), 2)
            pygame.draw.line(surf, col, (cx + 11, cy + off), (cx + 15, cy + off), 2)

    def _draw_rules_modal(self, mouse_pos: tuple[int, int]) -> None:
        """Render a modal dialog presenting the official rules and tactical tips."""
        dim = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)
        dim.fill((20, 18, 16, 130))
        self.screen.blit(dim, (0, 0))

        m_rect = pygame.Rect(WINDOW_WIDTH // 2 - 270, WINDOW_HEIGHT // 2 - 230, 540, 460)
        self._draw_rounded_panel(m_rect, PANEL_BG, PANEL_BORDER, radius=18, border_width=2)

        # Header
        m_title = self.font_title.render("HOW TO PLAY DOTS & BOXES", True, TEXT_PRIMARY)
        self.screen.blit(m_title, (m_rect.centerx - m_title.get_width() // 2, m_rect.y + 24))
        m_sub = self.font_body.render("Classic Combinatorial Strategy & Turn Rules", True, TEXT_SECONDARY)
        self.screen.blit(m_sub, (m_rect.centerx - m_sub.get_width() // 2, m_rect.y + 58))

        # Rules Items
        rules = [
            ("1. Taking Turns", "Players alternate drawing a single horizontal or vertical edge between adjacent dots."),
            ("2. Capturing Boxes", "Completing the 4th side of any 1x1 box claims it (+1 pt) and grants an immediate bonus turn!"),
            ("3. Chain Sweeps", "Capturing one box often opens adjacent boxes, allowing sweeping entire corridors in one turn."),
            ("4. The Double-Cross", "Advanced strategists sacrifice 2 boxes at the end of a chain to retain opening control."),
            ("5. Victory Condition", "When all boxes are claimed, the player with the highest final score wins the match."),
        ]
        start_y = m_rect.y + 98
        for h_text, b_text in rules:
            h_surf = self.font_heading.render(h_text, True, P1_COLOR)
            self.screen.blit(h_surf, (m_rect.x + 36, start_y))
            b_surf = self.font_body.render(b_text, True, TEXT_SECONDARY)
            self.screen.blit(b_surf, (m_rect.x + 36, start_y + 20))
            start_y += 54

        # Close button
        h_btn = self.rules_close_btn.rect.collidepoint(mouse_pos)
        c_bg = (235, 60, 72) if h_btn else P1_COLOR
        self._draw_rounded_panel(self.rules_close_btn.rect, c_bg, (155, 30, 40), radius=10, border_width=1)
        c_txt = self.font_card_title.render(self.rules_close_btn.label, True, (255, 255, 255))
        self.screen.blit(
            c_txt,
            (
                self.rules_close_btn.rect.centerx - c_txt.get_width() // 2,
                self.rules_close_btn.rect.centery - c_txt.get_height() // 2,
            ),
        )

    def _draw_name_modal(self, mouse_pos: tuple[int, int]) -> None:
        """Render modal dialog prompting for human player name(s) before starting match."""
        now = time.perf_counter()
        dim = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)
        dim.fill((15, 13, 12, 195))
        self.screen.blit(dim, (0, 0))

        if self.mode == "pve":
            m_w, m_h = 460, 290
            m_x = WINDOW_WIDTH // 2 - m_w // 2
            m_y = WINDOW_HEIGHT // 2 - m_h // 2
            self._name_modal_rect = pygame.Rect(m_x, m_y, m_w, m_h)
            self._draw_rounded_panel(self._name_modal_rect, PANEL_BG, GOLD_GLOW, radius=18, border_width=2)

            # Close button (top right)
            self._name_close_btn_rect = pygame.Rect(self._name_modal_rect.right - 36, self._name_modal_rect.y + 14, 24, 24)
            h_close = self._name_close_btn_rect.collidepoint(mouse_pos)
            close_col = (255, 100, 100) if h_close else TEXT_MUTED
            cl_surf = self.font_card_title.render("x", True, close_col)
            self.screen.blit(cl_surf, (self._name_close_btn_rect.centerx - cl_surf.get_width() // 2, self._name_close_btn_rect.centery - cl_surf.get_height() // 2))

            # Header
            t_surf = self.font_modal_title.render("WHO IS PLAYING?", True, GOLD_BRIGHT)
            self.screen.blit(t_surf, (self._name_modal_rect.centerx - t_surf.get_width() // 2, self._name_modal_rect.y + 24))

            sub_surf = self.font_body.render("Saved to profile for scoring, turns, and board ownership", True, TEXT_SECONDARY)
            self.screen.blit(sub_surf, (self._name_modal_rect.centerx - sub_surf.get_width() // 2, self._name_modal_rect.y + 60))

            # Input field label
            lbl_surf = self.font_heading.render("PLAYER NAME (HUMAN STRATEGIST):", True, P1_BRIGHT)
            self.screen.blit(lbl_surf, (self._name_modal_rect.centerx - 170, self._name_modal_rect.y + 98))

            # Input field
            self._name_input1_rect = pygame.Rect(self._name_modal_rect.centerx - 170, self._name_modal_rect.y + 122, 340, 44)
            inp_bg = (24, 20, 18)
            inp_border = P1_COLOR if self.name_modal_focus == "p1" else PANEL_BORDER
            border_w = 2 if self.name_modal_focus == "p1" else 1
            self._draw_rounded_panel(self._name_input1_rect, inp_bg, inp_border, radius=10, border_width=border_w)

            # Render text
            disp_txt = self.name_modal_input_p1
            txt_surf = self.font_input.render(disp_txt, True, TEXT_PRIMARY)
            self.screen.blit(txt_surf, (self._name_input1_rect.x + 14, self._name_input1_rect.centery - txt_surf.get_height() // 2))

            # Blinking cursor
            if self.name_modal_focus == "p1" and (int(now * 2) % 2 == 0):
                cx = self._name_input1_rect.x + 14 + txt_surf.get_width() + 2
                cy1 = self._name_input1_rect.centery - 11
                cy2 = self._name_input1_rect.centery + 11
                pygame.draw.line(self.screen, P1_BRIGHT, (cx, cy1), (cx, cy2), 2)

            # Confirm & Start Button
            self._name_confirm_btn_rect = pygame.Rect(self._name_modal_rect.centerx - 130, self._name_modal_rect.y + 204, 260, 48)
            h_btn = self._name_confirm_btn_rect.collidepoint(mouse_pos)
            btn_bg = (235, 60, 72) if h_btn else P1_COLOR
            self._draw_rounded_panel(self._name_confirm_btn_rect, btn_bg, (155, 30, 40), radius=12, border_width=1)
            b_txt = self.font_btn.render("CONFIRM & START  >", True, TEXT_ON_DARK)
            self.screen.blit(b_txt, (self._name_confirm_btn_rect.centerx - b_txt.get_width() // 2, self._name_confirm_btn_rect.centery - b_txt.get_height() // 2))

            hint_txt = self.font_tag.render("Press Enter to Confirm  \u2022  Esc to Cancel", True, TEXT_MUTED)
            self.screen.blit(hint_txt, (self._name_modal_rect.centerx - hint_txt.get_width() // 2, self._name_modal_rect.y + 260))

        else:  # pvp (2 Players)
            m_w, m_h = 490, 370
            m_x = WINDOW_WIDTH // 2 - m_w // 2
            m_y = WINDOW_HEIGHT // 2 - m_h // 2
            self._name_modal_rect = pygame.Rect(m_x, m_y, m_w, m_h)
            self._draw_rounded_panel(self._name_modal_rect, PANEL_BG, GOLD_GLOW, radius=18, border_width=2)

            # Close button
            self._name_close_btn_rect = pygame.Rect(self._name_modal_rect.right - 36, self._name_modal_rect.y + 14, 24, 24)
            h_close = self._name_close_btn_rect.collidepoint(mouse_pos)
            close_col = (255, 100, 100) if h_close else TEXT_MUTED
            cl_surf = self.font_card_title.render("x", True, close_col)
            self.screen.blit(cl_surf, (self._name_close_btn_rect.centerx - cl_surf.get_width() // 2, self._name_close_btn_rect.centery - cl_surf.get_height() // 2))

            # Header
            t_surf = self.font_modal_title.render("ENTER PLAYER NAMES", True, GOLD_BRIGHT)
            self.screen.blit(t_surf, (self._name_modal_rect.centerx - t_surf.get_width() // 2, self._name_modal_rect.y + 22))

            sub_surf = self.font_body.render("Pass & Play match \u2014 names saved for turn tracking and calculations", True, TEXT_SECONDARY)
            self.screen.blit(sub_surf, (self._name_modal_rect.centerx - sub_surf.get_width() // 2, self._name_modal_rect.y + 56))

            # Field 1 (Player 1)
            lbl1 = self.font_heading.render("PLAYER 1 (RUBY CRIMSON):", True, P1_BRIGHT)
            self.screen.blit(lbl1, (self._name_modal_rect.centerx - 175, self._name_modal_rect.y + 92))
            self._name_input1_rect = pygame.Rect(self._name_modal_rect.centerx - 175, self._name_modal_rect.y + 114, 350, 42)
            f1 = self.name_modal_focus == "p1"
            self._draw_rounded_panel(self._name_input1_rect, (24, 20, 18), P1_COLOR if f1 else PANEL_BORDER, radius=10, border_width=2 if f1 else 1)
            t1 = self.font_input.render(self.name_modal_input_p1, True, TEXT_PRIMARY)
            self.screen.blit(t1, (self._name_input1_rect.x + 14, self._name_input1_rect.centery - t1.get_height() // 2))
            if f1 and (int(now * 2) % 2 == 0):
                cx = self._name_input1_rect.x + 14 + t1.get_width() + 2
                pygame.draw.line(self.screen, P1_BRIGHT, (cx, self._name_input1_rect.centery - 11), (cx, self._name_input1_rect.centery + 11), 2)

            # Field 2 (Player 2)
            lbl2 = self.font_heading.render("PLAYER 2 (SAPPHIRE BLUE):", True, P2_BRIGHT)
            self.screen.blit(lbl2, (self._name_modal_rect.centerx - 175, self._name_modal_rect.y + 172))
            self._name_input2_rect = pygame.Rect(self._name_modal_rect.centerx - 175, self._name_modal_rect.y + 194, 350, 42)
            f2 = self.name_modal_focus == "p2"
            self._draw_rounded_panel(self._name_input2_rect, (18, 22, 28), P2_COLOR if f2 else PANEL_BORDER, radius=10, border_width=2 if f2 else 1)
            t2 = self.font_input.render(self.name_modal_input_p2, True, TEXT_PRIMARY)
            self.screen.blit(t2, (self._name_input2_rect.x + 14, self._name_input2_rect.centery - t2.get_height() // 2))
            if f2 and (int(now * 2) % 2 == 0):
                cx = self._name_input2_rect.x + 14 + t2.get_width() + 2
                pygame.draw.line(self.screen, P2_BRIGHT, (cx, self._name_input2_rect.centery - 11), (cx, self._name_input2_rect.centery + 11), 2)

            # Confirm & Start Button
            self._name_confirm_btn_rect = pygame.Rect(self._name_modal_rect.centerx - 130, self._name_modal_rect.y + 266, 260, 48)
            h_btn = self._name_confirm_btn_rect.collidepoint(mouse_pos)
            btn_bg = (235, 60, 72) if h_btn else P1_COLOR
            self._draw_rounded_panel(self._name_confirm_btn_rect, btn_bg, (155, 30, 40), radius=12, border_width=1)
            b_txt = self.font_btn.render("CONFIRM & START  >", True, TEXT_ON_DARK)
            self.screen.blit(b_txt, (self._name_confirm_btn_rect.centerx - b_txt.get_width() // 2, self._name_confirm_btn_rect.centery - b_txt.get_height() // 2))

            hint_txt = self.font_tag.render("Tab to switch fields  \u2022  Enter to Confirm  \u2022  Esc to Cancel", True, TEXT_MUTED)
            self.screen.blit(hint_txt, (self._name_modal_rect.centerx - hint_txt.get_width() // 2, self._name_modal_rect.y + 328))

    def _draw_setup_screen(self) -> None:
        """Render the clean Player vs Opponent matchup page."""
        now = time.perf_counter()
        mouse_pos = pygame.mouse.get_pos()

        # 1. Base gradient background
        self.screen.blit(self._bg_surface, (0, 0))

        # 2. Dynamic Floating Ambient Bokeh / Particles
        glow_surf = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)
        for p in self.ambient_particles:
            p["x"] = (p["x"] + p["vx"]) % WINDOW_WIDTH
            p["y"] = (p["y"] + p["vy"]) % WINDOW_HEIGHT
            cur_r = p["r"] * (1.0 + 0.15 * math.sin(now * 1.5 + p["phase"]))
            pygame.draw.circle(glow_surf, p["color"], (int(round(p["x"])), int(round(p["y"]))), int(round(cur_r)))
        self.screen.blit(glow_surf, (0, 0))

        # 3. Top Hero Title
        title_surf = self.font_hero.render("DOTS & BOXES", True, TEXT_PRIMARY)
        self.screen.blit(title_surf, (WINDOW_WIDTH // 2 - title_surf.get_width() // 2, 24))

        # Rules button (?) top right
        h_info = self.info_btn.rect.collidepoint(mouse_pos)
        self._draw_rounded_panel(self.info_btn.rect, BTN_HOVER if h_info else PANEL_BG, PANEL_BORDER, radius=16)
        itxt = self.font_card_title.render("?", True, GOLD_GLOW)
        self.screen.blit(itxt, (self.info_btn.rect.centerx - itxt.get_width() // 2, self.info_btn.rect.centery - itxt.get_height() // 2))

        # 4. Mode Selector Tabs (Top Center)
        for card in self.setup_cards:
            if card.category == "mode":
                h = card.rect.collidepoint(mouse_pos)
                bg = (48, 40, 30) if card.active else (BTN_HOVER if h else PANEL_BG)
                border = GOLD_GLOW if card.active else PANEL_BORDER
                border_w = 2 if card.active else 1
                self._draw_rounded_panel(card.rect, bg, border, radius=8, border_width=border_w)
                col = GOLD_BRIGHT if card.active else TEXT_SECONDARY
                s = self.font_badge.render(card.title, True, col)
                self.screen.blit(s, (card.rect.centerx - s.get_width() // 2, card.rect.centery - s.get_height() // 2))

        # 5. Names and details based on Game Mode
        if self.mode == "pve":
            p1_name_str = self.player1_name.upper()
            p1_avatar_lbl = self.player1_name[0].upper() if self.player1_name else "P1"
            p1_tag_str = "PLAYER 1"
            p2_name_str = "AI OPPONENT"
            p2_avatar_lbl = "AI"
            p2_tag_str = "OPPONENT"
        elif self.mode == "pvp":
            p1_name_str = self.player1_name.upper()
            p1_avatar_lbl = self.player1_name[0].upper() if self.player1_name else "P1"
            p1_tag_str = "PLAYER 1"
            p2_name_str = self.player2_name.upper()
            p2_avatar_lbl = self.player2_name[0].upper() if self.player2_name else "P2"
            p2_tag_str = "PLAYER 2"
        else:  # eve
            p1_name_str = "AI ALPHA"
            p1_avatar_lbl = "AI 1"
            p1_tag_str = "AI 1"
            p2_name_str = "AI BETA"
            p2_avatar_lbl = "AI 2"
            p2_tag_str = "AI 2"

        is_p1_first = self.first_player == HUMAN
        card_w = 390
        card_h = 425
        card_y = 115

        # 6. Player 1 Card (Left)
        p1_r = pygame.Rect(75, card_y, card_w, card_h)
        h_p1 = p1_r.collidepoint(mouse_pos)
        p1_border_col = P1_COLOR if is_p1_first else (120, 42, 50)
        self._draw_rounded_panel(p1_r, (36, 30, 28) if h_p1 else PANEL_BG, p1_border_col, radius=18, border_width=2)

        # Tag
        p1_tag_w = 70 if self.mode == "eve" else 90
        p1_tag_r = pygame.Rect(p1_r.x + 20, p1_r.y + 16, p1_tag_w, 22)
        self._draw_rounded_panel(p1_tag_r, P1_TINT, P1_COLOR, radius=6, border_width=1)
        tag1 = self.font_badge.render(p1_tag_str, True, P1_BRIGHT)
        self.screen.blit(tag1, (p1_tag_r.centerx - tag1.get_width() // 2, p1_tag_r.centery - tag1.get_height() // 2))

        # Avatar Token
        p1_cx = p1_r.centerx
        p1_cy = p1_r.y + 100
        _draw_aa_circle(self.screen, p1_cx, p1_cy + 5, 48, (10, 8, 7))
        _draw_aa_circle(self.screen, p1_cx, p1_cy, 46, (190, 145, 65))
        _draw_aa_circle(self.screen, p1_cx, p1_cy, 43, P1_COLOR)
        _draw_aa_circle(self.screen, p1_cx - 13, p1_cy - 13, 15, P1_BRIGHT)
        s_lbl1 = self.font_title.render(p1_avatar_lbl, True, TEXT_ON_DARK)
        self.screen.blit(s_lbl1, (p1_cx - s_lbl1.get_width() // 2, p1_cy - s_lbl1.get_height() // 2))

        # Name & Subtitle
        n1 = self.font_popup.render(p1_name_str, True, TEXT_PRIMARY)
        self.screen.blit(n1, (p1_cx - n1.get_width() // 2, p1_r.y + 156))
        sub1 = self.font_body.render("Territory: Ruby Crimson Pieces", True, TEXT_SECONDARY)
        self.screen.blit(sub1, (p1_cx - sub1.get_width() // 2, p1_r.y + 182))

        # Edit Name pill for Human Player 1
        if self.mode in ("pve", "pvp"):
            self.p1_name_edit_rect = pygame.Rect(p1_cx - 50, p1_r.y + 204, 100, 20)
            h_edit1 = self.p1_name_edit_rect.collidepoint(mouse_pos)
            self._draw_rounded_panel(self.p1_name_edit_rect, BTN_HOVER if h_edit1 else PANEL_BG_SUBTLE, PANEL_BORDER, radius=10)
            ed_txt1 = self.font_tag.render("\u270e EDIT NAME", True, GOLD_BRIGHT if h_edit1 else TEXT_MUTED)
            self.screen.blit(ed_txt1, (self.p1_name_edit_rect.centerx - ed_txt1.get_width() // 2, self.p1_name_edit_rect.centery - ed_txt1.get_height() // 2))

        # Middle Content: AI 1 Algorithm Selector (if eve) or Profile Info Box
        if self.mode == "eve":
            algo_lbl1 = self.font_badge.render("CHOOSE AI 1 ALGORITHM:", True, P1_BRIGHT)
            self.screen.blit(algo_lbl1, (p1_r.x + 32, p1_r.y + 218))
            for card in self.setup_cards:
                if card.category == "algo_p1":
                    h_pill = card.rect.collidepoint(mouse_pos)
                    a_bg = P1_TINT if card.active else (BTN_HOVER if h_pill else PANEL_BG_SUBTLE)
                    a_border = P1_COLOR if card.active else PANEL_BORDER
                    self._draw_rounded_panel(card.rect, a_bg, a_border, radius=8, border_width=2 if card.active else 1)
                    txt_col = P1_BRIGHT if card.active else TEXT_SECONDARY
                    atxt = self.font_btn.render(card.title, True, txt_col)
                    self.screen.blit(atxt, (card.rect.centerx - atxt.get_width() // 2, card.rect.centery - atxt.get_height() // 2))
        else:
            h_box1 = pygame.Rect(p1_r.x + 30, p1_r.y + 225, 330, 96)
            self._draw_rounded_panel(h_box1, PANEL_BG_SUBTLE, PANEL_BORDER, radius=10, border_width=1)
            b_hdr1 = "HUMAN STRATEGIST" if self.mode == "pve" else "PLAYER 1 (LOCAL)"
            b_desc1 = "Real-time manual board interaction" if self.mode == "pve" else "Manual tabletop grid moves"
            b_desc2 = "Tactical box capture & double-cross control" if self.mode == "pve" else "Pass & Play on this device"
            lbl_surf1 = self.font_badge.render(b_hdr1, True, P1_BRIGHT)
            self.screen.blit(lbl_surf1, (h_box1.centerx - lbl_surf1.get_width() // 2, h_box1.y + 18))
            desc_surf1 = self.font_body.render(b_desc1, True, TEXT_SECONDARY)
            self.screen.blit(desc_surf1, (h_box1.centerx - desc_surf1.get_width() // 2, h_box1.y + 44))
            desc_surf2 = self.font_small.render(b_desc2, True, TEXT_MUTED)
            self.screen.blit(desc_surf2, (h_box1.centerx - desc_surf2.get_width() // 2, h_box1.y + 68))

        # Turn status button (Left Card)
        t1_rect = pygame.Rect(p1_r.x + 30, p1_r.y + 344, 330, 42)
        h_t1 = t1_rect.collidepoint(mouse_pos)
        if is_p1_first:
            self._draw_rounded_panel(t1_rect, P1_TINT, P1_COLOR, radius=10, border_width=2)
            t1_txt = self.font_btn.render("TAKES FIRST MOVE", True, P1_BRIGHT)
            h1_txt = self.font_badge.render("Opens the game on turn 1 • Click to swap", True, TEXT_MUTED)
        else:
            self._draw_rounded_panel(t1_rect, BTN_HOVER if h_t1 else PANEL_BG_SUBTLE, PANEL_BORDER, radius=10, border_width=1)
            t1_txt = self.font_btn.render("PLAYS SECOND", True, TEXT_SECONDARY)
            h1_txt = self.font_badge.render("Responds to opening move • Click to swap", True, TEXT_MUTED)
        self.screen.blit(t1_txt, (t1_rect.centerx - t1_txt.get_width() // 2, t1_rect.centery - t1_txt.get_height() // 2))
        self.screen.blit(h1_txt, (p1_cx - h1_txt.get_width() // 2, p1_r.y + 395))

        # 7. Center VS Divider
        mid_x = WINDOW_WIDTH // 2
        pygame.draw.line(self.screen, (48, 42, 36), (mid_x, card_y + 30), (mid_x, card_y + 390), 2)
        vs_cy = card_y + 210
        _draw_aa_circle(self.screen, mid_x, vs_cy + 4, 38, (12, 10, 9))
        _draw_aa_circle(self.screen, mid_x, vs_cy, 36, (42, 36, 30))
        pygame.draw.circle(self.screen, GOLD_GLOW, (mid_x, vs_cy), 36, width=2)
        vs_txt = self.font_title.render("VS", True, GOLD_BRIGHT)
        self.screen.blit(vs_txt, (mid_x - vs_txt.get_width() // 2, vs_cy - vs_txt.get_height() // 2))

        # 8. Opponent Card (Right)
        p2_r = pygame.Rect(WINDOW_WIDTH - 75 - card_w, card_y, card_w, card_h)
        h_p2 = p2_r.collidepoint(mouse_pos)
        p2_border_col = P2_COLOR if not is_p1_first else (35, 75, 135)
        self._draw_rounded_panel(p2_r, (26, 32, 40) if h_p2 else PANEL_BG, p2_border_col, radius=18, border_width=2)

        # Tag
        p2_tag_r = pygame.Rect(p2_r.right - 20 - 105, p2_r.y + 16, 105, 22)
        self._draw_rounded_panel(p2_tag_r, P2_TINT, P2_COLOR, radius=6, border_width=1)
        tag2 = self.font_badge.render(p2_tag_str, True, P2_BRIGHT)
        self.screen.blit(tag2, (p2_tag_r.centerx - tag2.get_width() // 2, p2_tag_r.centery - tag2.get_height() // 2))

        # Avatar Token
        p2_cx = p2_r.centerx
        p2_cy = p2_r.y + 100
        _draw_aa_circle(self.screen, p2_cx, p2_cy + 5, 48, (10, 8, 7))
        _draw_aa_circle(self.screen, p2_cx, p2_cy, 46, (190, 145, 65))
        _draw_aa_circle(self.screen, p2_cx, p2_cy, 43, P2_COLOR)
        _draw_aa_circle(self.screen, p2_cx - 13, p2_cy - 13, 15, P2_BRIGHT)
        s_lbl2 = self.font_title.render(p2_avatar_lbl, True, TEXT_ON_DARK)
        self.screen.blit(s_lbl2, (p2_cx - s_lbl2.get_width() // 2, p2_cy - s_lbl2.get_height() // 2))

        # Name & Subtitle
        n2 = self.font_popup.render(p2_name_str, True, TEXT_PRIMARY)
        self.screen.blit(n2, (p2_cx - n2.get_width() // 2, p2_r.y + 156))
        sub2 = self.font_body.render("Territory: Royal Sapphire Pieces", True, TEXT_SECONDARY)
        self.screen.blit(sub2, (p2_cx - sub2.get_width() // 2, p2_r.y + 182))

        # Edit Name pill for Human Player 2 in PvP
        if self.mode == "pvp":
            self.p2_name_edit_rect = pygame.Rect(p2_cx - 50, p2_r.y + 204, 100, 20)
            h_edit2 = self.p2_name_edit_rect.collidepoint(mouse_pos)
            self._draw_rounded_panel(self.p2_name_edit_rect, BTN_HOVER if h_edit2 else PANEL_BG_SUBTLE, PANEL_BORDER, radius=10)
            ed_txt2 = self.font_tag.render("\u270e EDIT NAME", True, GOLD_BRIGHT if h_edit2 else TEXT_MUTED)
            self.screen.blit(ed_txt2, (self.p2_name_edit_rect.centerx - ed_txt2.get_width() // 2, self.p2_name_edit_rect.centery - ed_txt2.get_height() // 2))

        # Middle Content: AI Opponent / AI 2 Algorithm Selector, or PvP Profile Box
        if self.mode == "pve":
            algo_lbl2 = self.font_badge.render("CHOOSE OPPONENT ALGORITHM:", True, P2_BRIGHT)
            self.screen.blit(algo_lbl2, (p2_r.x + 32, p2_r.y + 218))
            for card in self.setup_cards:
                if card.category == "algorithm":
                    h_pill = card.rect.collidepoint(mouse_pos)
                    a_bg = P2_TINT if card.active else (BTN_HOVER if h_pill else PANEL_BG_SUBTLE)
                    a_border = P2_COLOR if card.active else PANEL_BORDER
                    self._draw_rounded_panel(card.rect, a_bg, a_border, radius=8, border_width=2 if card.active else 1)
                    txt_col = P2_BRIGHT if card.active else TEXT_SECONDARY
                    atxt = self.font_btn.render(card.title, True, txt_col)
                    self.screen.blit(atxt, (card.rect.centerx - atxt.get_width() // 2, card.rect.centery - atxt.get_height() // 2))

        elif self.mode == "eve":
            algo_lbl2 = self.font_badge.render("CHOOSE AI 2 ALGORITHM:", True, P2_BRIGHT)
            self.screen.blit(algo_lbl2, (p2_r.x + 32, p2_r.y + 218))
            for card in self.setup_cards:
                if card.category == "algo_p2":
                    h_pill = card.rect.collidepoint(mouse_pos)
                    a_bg = P2_TINT if card.active else (BTN_HOVER if h_pill else PANEL_BG_SUBTLE)
                    a_border = P2_COLOR if card.active else PANEL_BORDER
                    self._draw_rounded_panel(card.rect, a_bg, a_border, radius=8, border_width=2 if card.active else 1)
                    txt_col = P2_BRIGHT if card.active else TEXT_SECONDARY
                    atxt = self.font_btn.render(card.title, True, txt_col)
                    self.screen.blit(atxt, (card.rect.centerx - atxt.get_width() // 2, card.rect.centery - atxt.get_height() // 2))

        else:  # pvp
            h_box2 = pygame.Rect(p2_r.x + 30, p2_r.y + 225, 330, 96)
            self._draw_rounded_panel(h_box2, PANEL_BG_SUBTLE, PANEL_BORDER, radius=10, border_width=1)
            lbl_surf2 = self.font_badge.render("PLAYER 2 (LOCAL)", True, P2_BRIGHT)
            self.screen.blit(lbl_surf2, (h_box2.centerx - lbl_surf2.get_width() // 2, h_box2.y + 18))
            desc_surf2 = self.font_body.render("Manual tabletop grid moves", True, TEXT_SECONDARY)
            self.screen.blit(desc_surf2, (h_box2.centerx - desc_surf2.get_width() // 2, h_box2.y + 44))
            desc_surf3 = self.font_small.render("Pass & Play on this device", True, TEXT_MUTED)
            self.screen.blit(desc_surf3, (h_box2.centerx - desc_surf3.get_width() // 2, h_box2.y + 68))

        # Turn status button (Right Card)
        t2_rect = pygame.Rect(p2_r.x + 30, p2_r.y + 344, 330, 42)
        h_t2 = t2_rect.collidepoint(mouse_pos)
        if not is_p1_first:
            self._draw_rounded_panel(t2_rect, P2_TINT, P2_COLOR, radius=10, border_width=2)
            t2_txt = self.font_btn.render("TAKES FIRST MOVE", True, P2_BRIGHT)
            h2_txt = self.font_badge.render("Opens the game on turn 1 • Click to swap", True, TEXT_MUTED)
        else:
            self._draw_rounded_panel(t2_rect, BTN_HOVER if h_t2 else PANEL_BG_SUBTLE, PANEL_BORDER, radius=10, border_width=1)
            t2_txt = self.font_btn.render("PLAYS SECOND", True, TEXT_SECONDARY)
            h2_txt = self.font_badge.render("Responds to opening move • Click to swap", True, TEXT_MUTED)
        self.screen.blit(t2_txt, (t2_rect.centerx - t2_txt.get_width() // 2, t2_rect.centery - t2_txt.get_height() // 2))
        self.screen.blit(h2_txt, (p2_cx - h2_txt.get_width() // 2, p2_r.y + 395))

        # 9. Bottom Board Size Selector
        b_y = 556
        b_lbl = self.font_badge.render("BOARD SIZE:", True, TEXT_MUTED)
        b_lbl_x = WINDOW_WIDTH // 2 - 170
        self.screen.blit(b_lbl, (b_lbl_x, b_y + 7))
        self.screen.blit(b_lbl, (b_lbl_x, b_y + 7))

        for card in self.setup_cards:
            if card.category == "size":
                h = card.rect.collidepoint(mouse_pos)
                b_bg = (48, 40, 30) if card.active else (BTN_HOVER if h else PANEL_BG)
                b_border = GOLD_GLOW if card.active else PANEL_BORDER
                border_w = 2 if card.active else 1
                self._draw_rounded_panel(card.rect, b_bg, b_border, radius=6, border_width=border_w)
                bs = self.font_badge.render(card.title, True, GOLD_BRIGHT if card.active else TEXT_SECONDARY)
                self.screen.blit(bs, (card.rect.centerx - bs.get_width() // 2, card.rect.centery - bs.get_height() // 2))

        # 10. Start Match Button
        pulse = 0.5 + 0.5 * math.sin(now * 4.0)
        glow_expand = int(round(2 + pulse * 4))
        glow_r = self.start_game_btn.rect.inflate(glow_expand * 2, glow_expand * 2)
        self._draw_rounded_panel(glow_r, (65, 25, 28), (120, 45, 50), radius=16, border_width=1)

        hovered_start = self.start_game_btn.rect.collidepoint(mouse_pos)
        start_bg = (235, 60, 72) if hovered_start else P1_COLOR
        self._draw_rounded_panel(self.start_game_btn.rect, start_bg, (155, 30, 40), radius=14, border_width=1)

        start_lbl = self.font_title.render("START MATCH  >", True, TEXT_ON_DARK)
        self.screen.blit(
            start_lbl,
            (
                int(round(self.start_game_btn.rect.centerx - start_lbl.get_width() / 2)),
                int(round(self.start_game_btn.rect.centery - start_lbl.get_height() / 2)),
            ),
        )

        # 11. Rules Modal Overlay (if active)
        if self.show_rules_modal:
            self._draw_rules_modal(mouse_pos)

        # 12. Name Input Modal Overlay (if active)
        if self.show_name_modal:
            self._draw_name_modal(mouse_pos)

    def _draw_game_hud(self) -> None:
        """Render the clean in-game HUD: action controls, players and their scores."""
        now = time.perf_counter()
        mouse_pos = pygame.mouse.get_pos()

        # 1. Top Action Bar (Setup, New Game, Center Title, Undo/Hint/Spectator Controls)
        for btn in self.buttons.get("actions", []):
            self._draw_button(btn, mouse_pos)

        for btn in self.buttons.get("eve_controls", []):
            self._draw_button(btn, mouse_pos)

        title_surf = self.font_card_title.render("DOTS & BOXES — CLASSIC EDITION", True, TEXT_MUTED)
        self.screen.blit(title_surf, (WINDOW_WIDTH // 2 - title_surf.get_width() // 2, 20))

        # 2. Player names, avatars, and mode info
        if self.mode == "pve":
            p1_name_str = self.player1_name.upper()
            p1_av_lbl = self.player1_name[0].upper() if self.player1_name else "P1"
            algo_disp = self._get_algo_short_name(self.ai_algorithm)
            p2_name_str = "AI OPPONENT"
            p2_av_lbl = "AI"
            p2_sub_str = algo_disp
        elif self.mode == "pvp":
            p1_name_str = self.player1_name.upper()
            p1_av_lbl = self.player1_name[0].upper() if self.player1_name else "P1"
            p2_name_str = self.player2_name.upper()
            p2_av_lbl = self.player2_name[0].upper() if self.player2_name else "P2"
            p2_sub_str = "Sapphire Pieces"
        else:  # eve
            p1_name_str = "AI ALPHA"
            p1_av_lbl = "AI 1"
            p2_name_str = "AI BETA"
            p2_av_lbl = "AI 2"
            p2_sub_str = self._get_algo_short_name(self.ai_algorithm)

        current_p = self.state.current_player
        is_over = self.state.is_game_over()
        p1_turn = not is_over and current_p == HUMAN
        p2_turn = not is_over and current_p == AI

        # 3. Player 1 Card (Left: y = 50, w = 290, h = 74)
        p1_card = pygame.Rect(40, 50, 290, 74)
        if p1_turn:
            pulse = 0.5 + 0.5 * math.sin(now * 4.5)
            p1_glow = pygame.Surface((p1_card.width + 10, p1_card.height + 10), pygame.SRCALPHA)
            pygame.draw.rect(p1_glow, (*P1_COLOR, int(45 * pulse)), p1_glow.get_rect(), border_radius=16)
            self.screen.blit(p1_glow, (p1_card.x - 5, p1_card.y - 5))

        self._draw_rounded_panel(
            p1_card,
            P1_TINT if p1_turn else PANEL_BG,
            P1_COLOR if p1_turn else PANEL_BORDER,
            radius=12,
            border_width=2 if p1_turn else 1,
        )

        # P1 Avatar
        p1_cx = p1_card.x + 36
        p1_cy = p1_card.centery
        _draw_aa_circle(self.screen, p1_cx, p1_cy + 3, 25, (10, 8, 7))
        _draw_aa_circle(self.screen, p1_cx, p1_cy, 24, (190, 145, 65))
        _draw_aa_circle(self.screen, p1_cx, p1_cy, 22, P1_COLOR)
        p1_av_txt = self.font_heading.render(p1_av_lbl, True, TEXT_ON_DARK)
        self.screen.blit(p1_av_txt, (p1_cx - p1_av_txt.get_width() // 2, p1_cy - p1_av_txt.get_height() // 2))

        # P1 Name & Subtitle
        p1_name_surf = self.font_card_title.render(p1_name_str, True, TEXT_PRIMARY)
        self.screen.blit(p1_name_surf, (p1_card.x + 72, p1_card.y + 13))
        if p1_turn:
            p1_sub_surf = self.font_badge.render("● ACTIVE TURN", True, P1_BRIGHT)
        elif self.mode == "eve":
            p1_sub_surf = self.font_badge.render(self._get_algo_short_name(self.ai_p1_algorithm), True, TEXT_MUTED)
        else:
            p1_sub_surf = self.font_badge.render("Ruby Pieces", True, TEXT_MUTED)
        self.screen.blit(p1_sub_surf, (p1_card.x + 72, p1_card.y + 42))

        # P1 Score (Big & Bold)
        s1_val = self.state.scores[HUMAN]
        s1_surf = self.font_score.render(str(s1_val), True, P1_BRIGHT if p1_turn else TEXT_PRIMARY)
        self.screen.blit(s1_surf, (p1_card.right - 40 - s1_surf.get_width() // 2, p1_card.centery - s1_surf.get_height() // 2 - 2))
        s1_lbl = self.font_tag.render("PTS", True, P1_COLOR if p1_turn else TEXT_MUTED)
        self.screen.blit(s1_lbl, (p1_card.right - 40 - s1_lbl.get_width() // 2, p1_card.centery + 17))

        # 4. Center Match Status Pill (y = 50, w = 348, h = 74)
        center_pill = pygame.Rect(346, 50, 348, 74)
        self._draw_rounded_panel(center_pill, PANEL_BG, PANEL_BORDER, radius=12, border_width=1)

        grid_info = f"{self.grid_size} × {self.grid_size} GRID  •  {self.state.total_boxes} BOXES"
        info_surf = self.font_badge.render(grid_info, True, GOLD_BRIGHT)
        self.screen.blit(info_surf, (center_pill.centerx - info_surf.get_width() // 2, center_pill.y + 11))

        status_surf = self.font_body.render(self.status_text, True, TEXT_PRIMARY)
        self.screen.blit(status_surf, (center_pill.centerx - status_surf.get_width() // 2, center_pill.y + 31))

        rem_boxes = self.state.total_boxes - s1_val - self.state.scores[AI]
        if is_over:
            foot_str = "Match Finished — All Boxes Claimed"
            foot_col = GOLD_BRIGHT
        else:
            diff = s1_val - self.state.scores[AI]
            if diff > 0:
                p_lead = self.player1_name if self.mode in ("pve", "pvp") else "AI 1"
                lead_str = f"{p_lead} leads by +{diff}"
            elif diff < 0:
                if self.mode == "pvp":
                    lead_str = f"{self.player2_name} leads by +{-diff}"
                elif self.mode == "pve":
                    lead_str = f"AI leads by +{-diff}"
                else:
                    lead_str = f"AI 2 leads by +{-diff}"
            else:
                lead_str = "Tied Score"
            foot_str = f"{rem_boxes} box{'es' if rem_boxes != 1 else ''} left  •  {lead_str}"
            foot_col = TEXT_MUTED

        foot_surf = self.font_badge.render(foot_str, True, foot_col)
        self.screen.blit(foot_surf, (center_pill.centerx - foot_surf.get_width() // 2, center_pill.y + 51))

        # 5. Player 2 Card (Right: y = 50, w = 290, h = 74)
        p2_card = pygame.Rect(WINDOW_WIDTH - 40 - 290, 50, 290, 74)
        if p2_turn:
            pulse = 0.5 + 0.5 * math.sin(now * 4.5)
            p2_glow = pygame.Surface((p2_card.width + 10, p2_card.height + 10), pygame.SRCALPHA)
            pygame.draw.rect(p2_glow, (*P2_COLOR, int(45 * pulse)), p2_glow.get_rect(), border_radius=16)
            self.screen.blit(p2_glow, (p2_card.x - 5, p2_card.y - 5))

        self._draw_rounded_panel(
            p2_card,
            P2_TINT if p2_turn else PANEL_BG,
            P2_COLOR if p2_turn else PANEL_BORDER,
            radius=12,
            border_width=2 if p2_turn else 1,
        )

        # P2 Score (on left of P2 card)
        s2_val = self.state.scores[AI]
        s2_surf = self.font_score.render(str(s2_val), True, P2_BRIGHT if p2_turn else TEXT_PRIMARY)
        self.screen.blit(s2_surf, (p2_card.x + 40 - s2_surf.get_width() // 2, p2_card.centery - s2_surf.get_height() // 2 - 2))
        s2_lbl = self.font_tag.render("PTS", True, P2_COLOR if p2_turn else TEXT_MUTED)
        self.screen.blit(s2_lbl, (p2_card.x + 40 - s2_lbl.get_width() // 2, p2_card.centery + 17))

        # P2 Avatar (on right of P2 card)
        p2_cx = p2_card.right - 36
        p2_cy = p2_card.centery
        _draw_aa_circle(self.screen, p2_cx, p2_cy + 3, 25, (10, 8, 7))
        _draw_aa_circle(self.screen, p2_cx, p2_cy, 24, (190, 145, 65))
        _draw_aa_circle(self.screen, p2_cx, p2_cy, 22, P2_COLOR)
        p2_av_txt = self.font_heading.render(p2_av_lbl, True, TEXT_ON_DARK)
        self.screen.blit(p2_av_txt, (p2_cx - p2_av_txt.get_width() // 2, p2_cy - p2_av_txt.get_height() // 2))

        # P2 Name & Subtitle
        p2_name_surf = self.font_card_title.render(p2_name_str, True, TEXT_PRIMARY)
        self.screen.blit(p2_name_surf, (p2_card.right - 72 - p2_name_surf.get_width(), p2_card.y + 13))
        if p2_turn:
            p2_sub_surf = self.font_badge.render("● ACTIVE TURN", True, P2_BRIGHT)
        else:
            p2_sub_surf = self.font_badge.render(p2_sub_str, True, TEXT_MUTED)
        self.screen.blit(p2_sub_surf, (p2_card.right - 72 - p2_sub_surf.get_width(), p2_card.y + 42))

    def _draw_board(self) -> None:
        now = time.perf_counter()
        self._draw_rounded_panel(self.board_panel, BOARD_BG, PANEL_BORDER, radius=16)

        # Subtle inner frame
        inner = self.board_panel.inflate(-16, -16)
        pygame.draw.rect(self.screen, BOARD_INNER, inner, width=1, border_radius=12)

        ox, oy, cell = self._board_geometry()

        # 1. Completed boxes with smooth pop & clean warm tint
        fx_layer = pygame.Surface(self.board_panel.size, pygame.SRCALPHA)
        for r in range(self.state.rows):
            for c in range(self.state.cols):
                owner = self.state.boxes[r][c]
                if owner == 0:
                    continue
                bx = ox + c * cell - self.board_panel.left
                by = oy + r * cell - self.board_panel.top

                t_anim = 1.0
                if (r, c) in self.box_anim_start:
                    t_anim = min(1.0, (now - self.box_anim_start[(r, c)]) / 0.22)
                scale = 0.70 + 0.30 * _ease_out_back(t_anim)
                pad = 6
                base_size = cell - pad * 2
                draw_size = max(8.0, base_size * scale)
                offset = (cell - draw_size) / 2.0

                box_rect = pygame.Rect(
                    int(round(bx + offset)),
                    int(round(by + offset)),
                    int(round(draw_size)),
                    int(round(draw_size)),
                )
                color = P1_COLOR if owner == HUMAN else P2_COLOR

                # Clean translucent wash + outline
                pygame.draw.rect(fx_layer, (*color, 36), box_rect, border_radius=8)
                pygame.draw.rect(fx_layer, (*color, 140), box_rect, width=2, border_radius=8)

                label_str = self._get_player_box_label(owner)
                txt = self.font_box.render(label_str, True, color)
                fx_layer.blit(
                    txt,
                    (
                        int(round(bx + cell / 2 - txt.get_width() / 2)),
                        int(round(by + cell / 2 - txt.get_height() / 2)),
                    ),
                )
        self.screen.blit(fx_layer, self.board_panel.topleft)

        # 2. Undrawn guides & hover glow
        glow_layer = pygame.Surface(self.board_panel.size, pygame.SRCALPHA)
        active_color = P1_COLOR if self.state.current_player == HUMAN else P2_COLOR
        active_bright = P1_BRIGHT if self.state.current_player == HUMAN else P2_BRIGHT

        for move in self.state.get_valid_moves():
            p1, p2 = self._edge_endpoints(move)
            if move == self.hovered_move:
                pulse = 0.7 + 0.3 * math.sin(now * 8.0)
                lp1 = (int(round(p1[0] - self.board_panel.left)), int(round(p1[1] - self.board_panel.top)))
                lp2 = (int(round(p2[0] - self.board_panel.left)), int(round(p2[1] - self.board_panel.top)))
                _draw_aa_line(glow_layer, lp1, lp2, 12, (*active_color, int(80 * pulse)))
                _draw_aa_line(glow_layer, lp1, lp2, 6, (*active_bright, 220))
            elif getattr(self, "hint_move", None) == move and now < getattr(self, "hint_expiry", 0.0):
                pulse = 0.5 + 0.5 * math.sin(now * 10.0)
                lp1 = (int(round(p1[0] - self.board_panel.left)), int(round(p1[1] - self.board_panel.top)))
                lp2 = (int(round(p2[0] - self.board_panel.left)), int(round(p2[1] - self.board_panel.top)))
                _draw_aa_line(glow_layer, lp1, lp2, 14, (235, 175, 45, int(130 * pulse)))
                _draw_aa_line(glow_layer, lp1, lp2, 7, (255, 215, 80, 240))
            else:
                self._draw_dashed_line(p1, p2, GUIDE_EDGE, width=2)
        self.screen.blit(glow_layer, self.board_panel.topleft)

        # 3. Drawn edges with rounded caps & amber recent move halo
        for r in range(self.state.rows + 1):
            for c in range(self.state.cols):
                if self.state.h_edges[r][c]:
                    self._draw_claimed_edge(("h", r, c), now)

        for r in range(self.state.rows):
            for c in range(self.state.cols + 1):
                if self.state.v_edges[r][c]:
                    self._draw_claimed_edge(("v", r, c), now)

        # 4. Crisp vector board dots with soft shadow
        hovered_endpoints: set[tuple[int, int]] = set()
        if self.hovered_move is not None:
            orient, hr, hc = self.hovered_move
            hovered_endpoints.add((hr, hc))
            hovered_endpoints.add((hr, hc + 1) if orient == "h" else (hr + 1, hc))

        dot_r = 7.5 if self.state.rows <= 4 else 6.5
        for r in range(self.state.rows + 1):
            for c in range(self.state.cols + 1):
                dx = ox + c * cell
                dy = oy + r * cell

                # Soft drop shadow
                _draw_aa_circle(self.screen, dx, dy + 1.2, dot_r + 0.8, DOT_SHADOW)

                # Core dot with anti-aliasing
                if (r, c) in hovered_endpoints:
                    _draw_aa_circle(self.screen, dx, dy, dot_r + 2.0, active_color)
                    _draw_aa_circle(self.screen, dx, dy, dot_r - 0.5, active_bright)
                else:
                    _draw_aa_circle(self.screen, dx, dy, dot_r, DOT_COLOR)

        # 5. Particles & floating score popups
        self._draw_effects()

        # 6. End-of-game modal dialog
        if self.state.is_game_over():
            self._draw_game_over_modal()

    def _draw_claimed_edge(self, move: Move, now: float) -> None:
        p1, p2 = self._edge_endpoints(move)
        owner = self.edge_owners.get(move, HUMAN)
        color = P1_COLOR if owner == HUMAN else P2_COLOR
        bright = P1_BRIGHT if owner == HUMAN else P2_BRIGHT

        t = 1.0
        if move in self.edge_anim_start:
            t = _ease_out_cubic((now - self.edge_anim_start[move]) / 0.14)
        if t < 1.0:
            mx = (p1[0] + p2[0]) / 2.0
            my = (p1[1] + p2[1]) / 2.0
            p1 = (mx + (p1[0] - mx) * t, my + (p1[1] - my) * t)
            p2 = (mx + (p2[0] - mx) * t, my + (p2[1] - my) * t)

        # Honey amber halo on latest moves
        if move in self.last_ai_moves:
            pulse = 0.55 + 0.45 * math.sin(now * 6.5)
            halo = pygame.Surface(self.board_panel.size, pygame.SRCALPHA)
            lp1 = (int(round(p1[0] - self.board_panel.left)), int(round(p1[1] - self.board_panel.top)))
            lp2 = (int(round(p2[0] - self.board_panel.left)), int(round(p2[1] - self.board_panel.top)))
            _draw_aa_line(halo, lp1, lp2, 14, (*GOLD_GLOW, int(110 * pulse)))
            self.screen.blit(halo, self.board_panel.topleft)

        # Anti-aliased outer stroke + crisp bright core
        _draw_aa_line(self.screen, p1, p2, 6, color)
        _draw_aa_line(self.screen, p1, p2, 2, bright)

    def _draw_effects(self) -> None:
        if self.particles:
            p_layer = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)
            for p in self.particles:
                alpha = int(255 * max(0.0, p.life / p.max_life))
                _draw_aa_circle(p_layer, p.x, p.y, p.radius, (*p.color, alpha))
            self.screen.blit(p_layer, (0, 0))

        for ft in self.floating_texts:
            alpha = int(255 * max(0.0, ft.life / ft.max_life))
            surf = self.font_popup.render(ft.text, True, ft.color)
            surf.set_alpha(alpha)
            self.screen.blit(
                surf,
                (int(round(ft.x - surf.get_width() / 2)), int(round(ft.y))),
            )

    def _draw_game_over_modal(self) -> None:
        dim = pygame.Surface(self.board_panel.size, pygame.SRCALPHA)
        pygame.draw.rect(dim, (15, 13, 12, 190), dim.get_rect(), border_radius=16)
        self.screen.blit(dim, self.board_panel.topleft)

        modal_rect = pygame.Rect(
            self.board_panel.centerx - 195, self.board_panel.centery - 115, 390, 230
        )
        card = pygame.Surface(modal_rect.size, pygame.SRCALPHA)
        winner = self.state.get_winner()
        accent = P1_COLOR if winner == HUMAN else (P2_COLOR if winner == AI else GOLD_GLOW)
        pygame.draw.rect(card, (*PANEL_BG, 252), card.get_rect(), border_radius=16)
        pygame.draw.rect(card, accent, card.get_rect(), width=2, border_radius=16)
        self.screen.blit(card, modal_rect.topleft)

        if self.mode == "pve":
            headline = f"{self.player1_name.upper()} WINS!" if winner == HUMAN else ("AI WINS!" if winner == AI else "IT'S A DRAW!")
            p1_name = self.player1_name
            p2_name = "AI"
        elif self.mode == "pvp":
            headline = f"{self.player1_name.upper()} WINS!" if winner == HUMAN else (f"{self.player2_name.upper()} WINS!" if winner == AI else "IT'S A DRAW!")
            p1_name = self.player1_name
            p2_name = self.player2_name
        else:
            headline = "AI 1 WINS!" if winner == HUMAN else ("AI 2 WINS!" if winner == AI else "IT'S A DRAW!")
            p1_name = "AI 1"
            p2_name = "AI 2"

        title_surf = self.font_modal_title.render(headline, True, accent)
        self.screen.blit(
            title_surf,
            (int(round(modal_rect.centerx - title_surf.get_width() / 2)), modal_rect.y + 26),
        )

        s1 = self.state.scores[HUMAN]
        s2 = self.state.scores[AI]
        score_line = f"{p1_name}  {s1}   —   {s2}  {p2_name}"
        score_surf = self.font_title.render(score_line, True, TEXT_PRIMARY)
        self.screen.blit(
            score_surf,
            (int(round(modal_rect.centerx - score_surf.get_width() / 2)), modal_rect.y + 78),
        )

        mode_str = "Human vs AI" if self.mode == "pve" else ("2 Players" if self.mode == "pvp" else "AI vs AI Duel")
        sub_surf = self.font_body.render(
            f"{self.grid_size}×{self.grid_size} Board  •  {mode_str}",
            True,
            TEXT_SECONDARY,
        )
        self.screen.blit(
            sub_surf,
            (int(round(modal_rect.centerx - sub_surf.get_width() / 2)), modal_rect.y + 118),
        )

        mouse_pos = pygame.mouse.get_pos()
        # Play Again button
        hovered_again = self.play_again_btn.rect.collidepoint(mouse_pos)
        bg_again = BTN_ACTIVE if not hovered_again else (56, 50, 46)
        self._draw_rounded_panel(self.play_again_btn.rect, bg_again, BTN_ACTIVE_BORDER, radius=10, border_width=1)
        lbl_again = self.font_heading.render(self.play_again_btn.label, True, TEXT_ON_DARK)
        self.screen.blit(
            lbl_again,
            (
                int(round(self.play_again_btn.rect.centerx - lbl_again.get_width() / 2)),
                int(round(self.play_again_btn.rect.centery - lbl_again.get_height() / 2)),
            ),
        )

        # Match Setup button
        hovered_setup = self.modal_setup_btn.rect.collidepoint(mouse_pos)
        bg_setup = BTN_HOVER if hovered_setup else PANEL_BG
        self._draw_rounded_panel(self.modal_setup_btn.rect, bg_setup, PANEL_BORDER, radius=10, border_width=1)
        lbl_setup = self.font_heading.render(self.modal_setup_btn.label, True, TEXT_PRIMARY)
        self.screen.blit(
            lbl_setup,
            (
                int(round(self.modal_setup_btn.rect.centerx - lbl_setup.get_width() / 2)),
                int(round(self.modal_setup_btn.rect.centery - lbl_setup.get_height() / 2)),
            ),
        )

    def _draw_header(self) -> None:
        """Compatibility shim: delegate to clean in-game HUD."""
        self._draw_game_hud()

    def _draw_sidebar(self) -> None:
        """Compatibility shim: sidebar is removed for clean game night layout."""
        pass

    def _draw_button(
        self,
        btn: Button,
        mouse_pos: tuple[int, int],
        custom_accent: tuple[int, int, int] | None = None,
    ) -> None:
        hovered = btn.rect.collidepoint(mouse_pos) and not btn.disabled
        if btn.disabled:
            bg = BTN_DISABLED
            border = BTN_DISABLED_BORDER
            txt_color = TEXT_MUTED
        elif btn.active:
            bg = custom_accent if custom_accent is not None else BTN_ACTIVE
            border = custom_accent if custom_accent is not None else BTN_ACTIVE_BORDER
            txt_color = TEXT_ON_DARK
        elif hovered:
            bg = BTN_HOVER
            border = (196, 188, 175)
            txt_color = TEXT_PRIMARY
        else:
            bg = BTN_BG
            border = BTN_BORDER
            txt_color = TEXT_SECONDARY

        self._draw_rounded_panel(btn.rect, bg, border, radius=8, border_width=1)
        font = self.font_tag if btn.rect.width < 90 else self.font_heading
        surf = font.render(btn.label, True, txt_color)
        self.screen.blit(
            surf,
            (
                int(round(btn.rect.centerx - surf.get_width() / 2)),
                int(round(btn.rect.centery - surf.get_height() / 2)),
            ),
        )

    def run(self) -> None:
        """Main Pygame event and render loop."""
        running = True
        while running:
            dt = self.clock.tick(FPS) / 1000.0
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if self.show_name_modal:
                        if event.key == pygame.K_RETURN:
                            self._confirm_name_modal()
                        elif event.key == pygame.K_ESCAPE:
                            self.show_name_modal = False
                        elif event.key == pygame.K_TAB and self.mode == "pvp":
                            self.name_modal_focus = "p2" if self.name_modal_focus == "p1" else "p1"
                        elif event.key == pygame.K_BACKSPACE:
                            if self.name_modal_focus == "p1":
                                self.name_modal_input_p1 = self.name_modal_input_p1[:-1]
                            else:
                                self.name_modal_input_p2 = self.name_modal_input_p2[:-1]
                        else:
                            ch = event.unicode
                            if ch and ch.isprintable():
                                if self.name_modal_focus == "p1" and len(self.name_modal_input_p1) < 14:
                                    self.name_modal_input_p1 += ch
                                elif self.name_modal_focus == "p2" and len(self.name_modal_input_p2) < 14:
                                    self.name_modal_input_p2 += ch
                        continue

                    if self.app_state == "setup":
                        if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                            if self.mode in ("pve", "pvp"):
                                self.show_name_modal = True
                                self.name_modal_focus = "p1"
                                self.name_modal_input_p1 = self.player1_name
                                self.name_modal_input_p2 = self.player2_name
                            else:
                                self.app_state = "game"
                                self._build_buttons()
                                self._reset_game()
                        elif event.key == pygame.K_1:
                            self.mode = "pve"
                            self._build_setup_cards()
                            self._sync_setup_cards()
                        elif event.key == pygame.K_2:
                            self.mode = "pvp"
                            self._build_setup_cards()
                            self._sync_setup_cards()
                        elif event.key == pygame.K_3:
                            self.mode = "eve"
                            self._build_setup_cards()
                            self._sync_setup_cards()
                        elif event.key == pygame.K_ESCAPE:
                            if self.show_rules_modal:
                                self.show_rules_modal = False
                    else:
                        if event.key == pygame.K_ESCAPE:
                            self.app_state = "setup"
                            self._build_setup_cards()
                            self._sync_setup_cards()
                        elif event.key == pygame.K_r:
                            self._reset_game()
                        elif event.key == pygame.K_u and self.mode != "eve":
                            self._undo_last_turn()
                        elif event.key == pygame.K_SPACE and self.mode == "eve":
                            self.eve_paused = not self.eve_paused
                            self._sync_button_states()
                elif event.type == pygame.MOUSEMOTION:
                    if self.app_state == "game":
                        self.hovered_move = self._find_hovered_move(event.pos)
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if self.app_state == "setup":
                        self._handle_setup_click(event.pos)
                    else:
                        self._handle_game_click(event.pos)

            if self.app_state == "setup":
                self._draw_setup_screen()
            else:
                # Update AI turn based on active mode
                if self.mode == "pve":
                    self._update_ai()
                elif self.mode == "eve":
                    self._update_eve()

                self._update_effects(dt)
                self.hovered_move = self._find_hovered_move(pygame.mouse.get_pos())

                self.screen.blit(self._bg_surface, (0, 0))
                self._draw_game_hud()
                self._draw_board()

            pygame.display.flip()

        pygame.quit()


def main() -> None:
    app = DotsAndBoxesApp()
    app.run()


if __name__ == "__main__":
    main()
