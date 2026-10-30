# ASCII Engine

A semantic, AI-operable ASCII game engine. Gameplay uses kinds and properties, never glyphs, so changing visual styles cannot change map logic.

- Style library and PT/EN keyword style translator
- Layered map editor, procedural dungeons, pathfinding, validation, lighting and rendering
- Pillow-backed image→ASCII and sprite helpers (optional dependency)
- Turn-based world runtime, effects, terminal UI, WAV synthesis and plugin hooks
- Structured AI API and `python -m asciiengine` CLI

Start with [AI_GUIDE.md](AI_GUIDE.md). Try the 20-room NetHack-style dungeon with `python -m examples.nethack_dungeon`, or the complete image-to-game workflow with `python -m examples.image_sprite_to_map`.

## Install and test

Python 3.12+; core has no third-party runtime dependencies. For image conversion, install the optional extra:

```sh
pip install -e '.[imaging]'
python3 -m unittest discover -s tests -t .
```

Actual audio-device playback uses an OS-installed player and is not verified by the automated tests.
