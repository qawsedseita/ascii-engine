# API quick reference

## Core and styles

- `default_kinds()`, `KindRegistry`, `KindDef`: semantic categories/properties.
- `Style`, `StyleSet`, `Glyph`: display-only mappings and per-category composition.
- `StyleLibrary().get(name)`, `.names()`: built-in styles and custom style loading.
- `StyleTranslator(library).apply(styleset, natural_language_instruction)`: keyword-based PT/EN style instruction parser.

## Maps

- `dungeon(width, height, rooms, seed, lit_ratio)`, `cave(...)`, `biome(...)`, `generate(...)`, `populate(...)`.
- `MapEditor(map).run(commands)`: atomic JSON/text editing with undo/redo.
- `validate_map(map)`, `astar(map,start,goal)`, `player_view(map,x,y,light_radius=...)`, `render_map(map, style, ...)`.
- `LayeredMap.logic_signature()` returns gameplay-relevant collision/sight/entity/exit state for appearance invariance checks.

## Imaging and game runtime

- `image_to_ascii`, `AsciiArt`, `AsciiSprite`, `sprite_sheet`, `connected_components`, `sprites_from_components`, `register_sprite_kind`.
- `GameWorld(map)`: `move`, `step`, `attack`, `pickup`, `equip`, `npc_turn`, `camera`, `save`, `load`.
- `EffectSystem`, `Animation`, `Menu`, `Dialogue`, `HUD`.
- `AudioSystem`, `AudioEvent`, `WavSynthesizer`, `CommandPlaybackBackend`.
- `EngineTools`: structured high-level AI interface; `PluginManager`: optional extension lifecycle.

Public package exports and command signatures are documented in module docstrings; this page is intentionally a compact orientation, not a duplicate of every parameter.
