# Dots and Boxes

A Python-based Dots and Boxes game with a polished desktop UI, competitive AI opponents, and local multiplayer. The project combines a game engine, strategy AI, benchmarking tools, and a decorative front-end experience inspired by an AI studio aesthetic.

## High-level overview

This repository contains an interactive board game implementation of Dots and Boxes built with Python and Pygame. It includes:

- Human vs AI, 2-player local play, and AI-vs-AI spectator mode
- Multiple board sizes: 3x3, 4x4, and 5x5
- Difficulty levels for the AI (easy, medium, hard)
- Match setup flow, turn logic, score tracking, and undo support
- A more advanced benchmark and analysis suite to evaluate AI behavior and performance
- Supporting reports, charts, and test coverage for gameplay validation

The main game logic and GUI live in the nested `Dots and Boxes/` project folder, while the root of the repository mainly acts as a container for the project and its documentation.

## Repository structure

```text
Dots_and_Boxes/
├── README.md                   # Repository overview
├── Dots and Boxes/             # Main project directory
│   ├── README.md               # Detailed project documentation
│   ├── run_game.bat            # Windows launcher
│   ├── powershell.cmd          # Optional helper script
│   └── Dots and Boxes/         # Core game source files
│       ├── main.py             # Pygame UI and game flow
│       ├── game_logic.py       # Core rules engine
│       ├── ai.py               # AI implementations and search logic
│       ├── engines.py          # Additional engine logic / evaluation support
│       ├── benchmark_suite.py  # AI benchmarking tools
│       ├── benchmark_results.json
│       ├── test_game.py         # Automated tests
│       ├── requirements.txt    # Python dependencies
│       └── ...                 # Visual assets, reports, and generated outputs
```

## Tech stack

- Python
- Pygame
- JSON-based configuration and benchmarking output
- Unit-style smoke tests for validation

## Getting started

From the repository root:

```bash
cd "Dots and Boxes/Dots and Boxes"
python -m venv .venv
. .venv/bin/activate    # Linux/macOS
# or .venv\Scripts\activate   # Windows
pip install -r requirements.txt
python main.py
```

On Windows, you can also run:

```bat
cd "Dots and Boxes"
run_game.bat
```

## Game features

- Classic Dots and Boxes rules
- Box capture and bonus turn logic
- AI difficulty levels with strategic moves
- Board resets and match configuration screen
- Desktop game experience with animated UI elements

## Notes

This repo appears to be a self-contained game project and is primarily focused on gameplay, AI strategy, and experimentation rather than a broader application framework. The nested project README contains additional, more detailed instructions and game design information.

## License

No explicit license file was found in the repository metadata provided, so license terms should be confirmed before redistribution or commercial use.
