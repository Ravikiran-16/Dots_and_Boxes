# Dots and Boxes — AI Studio Edition

An interactive, luxury-styled desktop game built with **Python** and **Pygame**, featuring a warm **AI Studio Cream & Terracotta/Sage** aesthetic, multiple game modes (**Human vs AI**, **2 Players Local**, and **AI vs AI Spectator**), and an advanced Alpha-Beta minimax engine with transposition tables and iterative deepening.

---

## Match Setup / Launch Screen

When launched, the game presents a **Match Setup Screen** featuring:
- **Game Mode Selection**: Choose between **vs AI**, **2 Players (Local)**, and **AI vs AI (Spectator)**.
- **Grid Size Cards**: **3×3** (Fast Match), **4×4** (Standard), **5×5** (Deep Strategy).
- **Difficulty Tiers**: **Easy** (Casual), **Medium** (Smart Alpha-Beta), **Hard** (Expert Minimax).
- **First Move Control**: Select who takes the opening turn.
- **Live Match Summary**: Dynamic summary text showing current configurations.
- **1-Click Start**: Click **START GAME >** to begin the match immediately.
- **Return Anytime**: In-game **⚙ Match Setup** buttons let you return to this setup screen at any point.

---

## Luxury AI Cream Palette

- **Canvas**: Warm Alabaster Cream (`#FCFAF6` to `#F4F0E8`) with ambient corner warmth and micro dot-matrix grain.
- **Player 1**: Anthropic-inspired Warm Terracotta (`#D95D39` & `#F28C6E`).
- **Player 2**: Mineral Forest Sage / Teal (`#267365` & `#44A594`).
- **Controls & Typography**: High-contrast Obsidian (`#1C1917` / `#221E1C`) on elevated ivory cards.
- **Highlights**: Warm Honey Ochre (`#D98F27`) halos marking the most recent moves.

---

## Project Structure

```text
Dots and Boxes/
│
├── run_game.bat                   # 1-Click launcher script for Windows
├── README.md                      # Project documentation and guide
│
└── Dots and Boxes/                # Core application directory
    ├── main.py                    # Pygame desktop UI & game loop (neon animations, particle FX)
    ├── game_logic.py              # Pure rules engine, bitmask state, turn & capture logic
    ├── ai.py                      # Multi-difficulty AI (Easy, Medium, Hard with Alpha-Beta / TT)
    ├── test_game.py               # 10 unit & smoke test suite
    ├── requirements.txt           # Python dependencies (pygame==2.6.1)
    └── .venv/                     # Configured Python 3.13 virtual environment
```

---

## How to Run the Game

### Method 1: Double-Click Launcher (Easiest)
Simply double-click the **`run_game.bat`** file in the root folder.

### Method 2: From PowerShell / Command Prompt

1. Open PowerShell or Command Prompt.
2. Navigate to the game folder:
   ```powershell
   cd "d:\Dots and Boxes\Dots and Boxes"
   ```
3. Run with the virtual environment:
   ```powershell
   .\.venv\Scripts\python.exe main.py
   ```
   *Or with system Python:*
   ```powershell
   python main.py
   ```

---

## How to Run the Test Suite

Run the 10 unit and smoke tests anytime:
```powershell
cd "d:\Dots and Boxes\Dots and Boxes"
.\.venv\Scripts\python.exe test_game.py
```

---

## Features & Controls

- **Game Mechanics**: Standard Dots and Boxes rules. Complete the 4th side of any box to claim it and earn a bonus turn.
- **Difficulty Modes**:
  - **Easy**: Casual play with randomized moves and occasional capture priority.
  - **Medium**: Depth-limited search with transposition tables and safe move heuristics.
  - **Hard**: Iterative deepening alpha-beta minimax, transposition tables, and chain/sacrifice optimization.
- **Board Sizes**: 3x3, 4x4, and 5x5 grids.
- **Turn Toggle**: Choose whether Human or AI goes first.
- **Undo Support**: Rewind recent moves to analyze alternate strategies.
- **Modern Neon UI**: Glowing edge highlights, particle bursts on box capture, floating score popups, and smooth transitions.
