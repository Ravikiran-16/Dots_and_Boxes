# Dots and Boxes

Welcome to the Dots and Boxes project! This is a beginner-friendly Python game where you can play the classic Dots and Boxes board game on your computer.

## What this project does

This repository contains a desktop game built with Python and Pygame. You can:

- play against the computer,
- play with another person on the same computer,
- watch AI play against AI,
- choose different board sizes and difficulty levels.

The project also includes AI logic, tests, and benchmark files to measure and improve how the computer plays.

## Why this repo is interesting

This project is a good example of how to build:

- a simple turn-based board game,
- a graphical user interface with Python,
- AI strategies for a game,
- small project structure and testing in Python.

## Project layout

```text
Dots_and_Boxes/
├── README.md                   # Project overview
├── Dots and Boxes/             # Main game folder
│   ├── README.md               # Detailed project guide
│   ├── run_game.bat            # Easy Windows launcher
│   ├── powershell.cmd          # Helper script
│   └── Dots and Boxes/         # Main source code
│       ├── main.py             # Game window and gameplay flow
│       ├── game_logic.py       # Board rules and scoring logic
│       ├── ai.py               # AI opponent logic
│       ├── engines.py          # Supporting game/AI engine code
│       ├── benchmark_suite.py  # AI benchmarking and analysis
│       ├── requirements.txt    # Python dependencies
│       ├── test_game.py        # Automated tests
│       └── ...                 # Extra assets and output files
```

## How to run the game

### Option 1: Run with the Windows launcher

From the project folder, double-click:

```text
run_game.bat
```

### Option 2: Run it manually

Open your terminal and type:

```bash
cd "Dots and Boxes/Dots and Boxes"
python -m venv .venv
# On Windows:
# .venv\Scripts\activate
# On macOS/Linux:
# source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

## Main features

- Classic Dots and Boxes rules
- Human vs AI mode
- Two-player local mode
- AI vs AI option
- Different board sizes
- Easy to hard AI difficulty levels
- Setup screen and score tracking

## Good places to start learning

If you're new to the project, these files are the best places to begin:

1. `main.py` — starts the game and builds the interface.
2. `game_logic.py` — explains how moves and scoring work.
3. `ai.py` — shows how the computer decides what move to make.
4. `test_game.py` — shows how the project checks for errors.

## Notes

This repo is mainly a game and AI project, so it is best explored by playing the game, reading the code, and experimenting with the AI difficulty settings.

## License

No explicit license file was found in the repository metadata. If you plan to reuse or share this project, confirm the copyright/license terms before doing so.
