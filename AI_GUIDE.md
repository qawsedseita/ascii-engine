# ASCII Engine: AI Guide

An AI-operated ASCII game toolkit. The core is Python 3.12 + standard library; Pillow is isolated to `asciiengine.imaging`. Install Pillow only if you need image conversion. Gameplay is semantic: maps store kinds such as `wall`, `orc`, and `floor`; styles map kinds to glyphs. **Never use glyphs for collision, movement, sight, or entity identity.**

## Quick start

```python
from asciiengine.maps import dungeon, populate, validate_map, player_view, render_map
from asciiengine.styles.library import StyleLibrary
from asciiengine.styles.style import StyleSet
from asciiengine.world import GameWorld

m = dungeon(80, 40, rooms=20, seed=11, lit_ratio=0.2)
populate(m, seed=11, creatures=18)
m.add_entity("player", *m.spawn, props={"faction": "heroes"})
assert validate_map(m)["ok"]
styles = StyleSet(StyleLibrary().get("nethack"))
print(render_map(m, styles, visible=player_view(m, *m.spawn, light_radius=2)).to_text())
world = GameWorld(m)
world.step(world.player_id, 1, 0)
```

The complete requested 20-room NetHack-style connected dungeon is [`python -m examples.nethack_dungeon`](examples/nethack_dungeon.py). Full synthetic image→ASCII→style conversion→map insertion→turn test is [`python -m examples.image_sprite_to_map`](examples/image_sprite_to_map.py).

## AI-facing API and CLI

```python
from asciiengine.aitools import EngineTools
tools = EngineTools(m, style="nethack")
tools.edit_map(["room 2 2 10 6 name=hall lit=true", "place orc 5 4"])
tools.validate()
tools.restyle("personagens estilo NetHack")
tools.playtest()  # static validation + spawn/exit route check, not a full simulation
```

Structured calls use `tools.dispatch({"cmd": "validate"})`. Available commands: `edit`, `validate`, `render`, `playtest`, `restyle`, `path`. Errors return `{"ok": false, "code": ..., "error": ..., "hint": ...}`.

```sh
python -m asciiengine dungeon --rooms 20 --seed 11 --output dungeon.json
python -m asciiengine validate dungeon.json
python -m asciiengine render dungeon.json --style nethack
python -m asciiengine edit dungeon.json '[{"cmd":"place","kind":"orc","x":5,"y":4}]'
```

## Map editing

`MapEditor(m).run(...)` accepts one command, a list of JSON objects, or newline-delimited text. A batch is atomic and supports undo/redo. Common commands: `room`, `corridor`, `door`, `set`, `rect`, `fill`, `replace`, `place`, `light`, `region`, `spawn`, `exit`, `collision`, `inspect`, `validate`, `stats`. Read full signatures in `asciiengine/maps/editor.py`.

`LayeredMap` grids contain semantic kinds. Entity kinds are placed with `add_entity`, not `set_cell`. New image-derived entity kinds: `registry.register(KindDef(...))`, add a glyph to a `Style`, and call `map.add_entity(kind, x, y)`. The image helper `register_sprite_kind` does this registration and stores sprite metadata. Map entities remain one logical tile each; the ASCII sprite sheet is metadata/art, not a collision footprint.

## Image conversion

`image_to_ascii(image_or_path, width=80, mode="mono")` supports `mono`, `color`, `high-density`, `minimal`, `edges`, `shaded`, optional ramp/style, palette, brightness/contrast/density, background removal, and terminal aspect correction (~2 vertical pixels per character cell). Results are `AsciiArt` with text/JSON methods. `sprite_sheet` splits fixed-size cells. `connected_components` and `sprites_from_components` extract connected nontransparent components. Pillow is needed only here.

## World, effects, UI, audio, plugins

- `GameWorld` provides turn-based movement, adjacent combat, inventory pickup/equip, simple pursuit AI, push/knockback, camera viewport, and JSON save/load. Entity movement respects static map collision and occupied live entities.
- `EffectSystem` tracks semantic effect kinds with lifetimes. UI widgets (`Menu`, `Dialogue`, `HUD`) render through the UI style category.
- Audio includes event routing, channels, distance attenuation, tone synthesis to WAV, and a null backend. `CommandPlaybackBackend` delegates to an installed OS player. **Actual device playback is not verified or tested in this sandbox.**
- Plugins subclass `asciiengine.plugins.Plugin`, implement `name` and `on_load(tools)`, then register with `PluginManager`.

## Honest limitations

- The style translator is PT/EN keyword parsing, not an LLM. Unknown terms produce a helpful error.
- Converting already-rendered glyph art between styles is lossy and ambiguous.
- Map `playtest()` is a static smoke check, not autonomous full-game QA.
- Sprite artwork does not become multi-cell collision or animation automatically; entities stay one map cell.
- Audio synthesis is testable, device playback is not.

## Tests and examples

Run `python3 -m unittest discover -s tests -t .`. Tests use `unittest`, synthetic images, and no network. More detail: [API overview](docs/API.md), [built-in styles](docs/STYLES.md), and [examples](examples/).
