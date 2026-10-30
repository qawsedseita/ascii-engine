# Built-in styles

Generated from `StyleLibrary` definitions. The rules are re-implementations of documented genre conventions; no third-party game glyph assets are bundled.

## `amber_terminal`

Amber phosphor CRT terminal.

- Charset: `ascii`; color: `truecolor`; autotile: `ascii_plus`
- Tags: retro, terminal, monochrome, crt
- References: Rogue/NetHack-era ASCII conventions

## `ansi_modern`

Modern truecolor terminal: solid blocks for walls, simulated transparency via ░▒▓ shades, dark theme palette, box-drawing UI.

- Charset: `unicode`; color: `truecolor`; autotile: `none`
- Tags: modern, terminal, truecolor, unicode
- References: modern terminal truecolor (24-bit SGR) palettes

## `cataclysm`

Cataclysm: DDA-like ncurses look: extended-ASCII box-drawing roads and walls, color is part of the symbol's meaning, zombies as Z, built to survive limited-color terminals.

- Charset: `cp437`; color: `ansi16`; autotile: `box_light`
- Tags: roguelike, cdda, cp437, ansi, survival
- References: https://discourse.cataclysmdda.org/t/my-overmap-looks-very-unintelligible-help/26474; https://discourse.cataclysmdda.org/t/map-symbol-clarification/5597

## `caves_of_qud`

Caves of Qud-like: punctuation ground textures, letters for creatures, digits for robots, dark backgrounds, each tile limited to a primary / detail / background color triple.

- Charset: `unicode`; color: `truecolor`; autotile: `none`
- Tags: roguelike, qud, unicode, colorful, sci-fi
- References: https://wiki.cavesofqud.com/wiki/Visual_Style; https://waltoriouswritesaboutgames.com/2013/02/23/roguelike-highlights-caves-of-qud/

## `classic_ascii`

Plain 7-bit ASCII, no color. Maximum compatibility; every kind is one printable ASCII char.

- Charset: `ascii`; color: `none`; autotile: `none`
- Tags: classic, ascii, monochrome
- References: Rogue/NetHack-era ASCII conventions

## `dwarf_fortress`

Dwarf Fortress-like: CP437 glyphs, a 16-color scheme with per-tile foreground AND background, color encodes material/biome, smoothed walls drawn with double-line box characters, ☺ for the citizens.

- Charset: `cp437`; color: `ansi16`; autotile: `box_double`
- Tags: roguelike, dwarf_fortress, cp437, ansi, colorful
- References: https://dwarffortresswiki.org/index.php/DF2014:Color; https://dwarffortresswiki.org/index.php/DF2014:Tileset; https://dwarffortresswiki.org/Map_legend

## `minimalist`

Minimal: empty floors, # walls, @ player, e for enemies, * for any item. Few distinct glyphs, high readability.

- Charset: `ascii`; color: `none`; autotile: `none`
- Tags: minimal, ascii, monochrome
- References: reduction of the classic set

## `nethack`

NetHack default symset: | and - walls, . floor, # corridor, + door, < > stairs, letters for monsters, $ gold, % food, ! potion, ? scroll, [ armor, ) weapon, ( tool, } water.

- Charset: `ascii`; color: `ansi16`; autotile: `ascii_nh`
- Tags: roguelike, nethack, ascii, ansi
- References: https://nethackwiki.com/wiki/Symset; https://nethackwiki.com/wiki/Custom_map_symbols_(3.4.3); https://alt.org/nethack/mirror/www.geocities.com/TimesSquare/Portal/2416/map.html

## `nethack_utf8`

NetHack with UTF8graphics-style symbols: box-drawing walls, · doorway/floor, ░ ▒ corridors, ≡ iron bars, Ψ tree.

- Charset: `unicode`; color: `ansi16`; autotile: `box_light`
- Tags: roguelike, nethack, unicode, ansi
- References: https://nethackwiki.com/wiki/UTF8graphics; https://nethackwiki.com/wiki/Custom_map_symbols_(3.4.3)

## `retro_terminal`

Green phosphor CRT terminal: a single hue, brightness carries the information.

- Charset: `ascii`; color: `truecolor`; autotile: `ascii_plus`
- Tags: retro, terminal, monochrome, crt
- References: monochrome CRT phosphor convention (P1 green)

## `rogue`

Original Rogue conventions: | - walls, + doors, # passages, % stairs, * gold, ! potion, ? scroll, ] armor.

- Charset: `ascii`; color: `none`; autotile: `ascii_nh`
- Tags: roguelike, classic, ascii
- References: https://nethackwiki.com (genealogy), r/roguelikedev FAQ Friday #28 (map object representation)

## `unicode_detailed`

Detailed Unicode: box-drawing walls, shade blocks, dingbats; richer silhouettes per kind.

- Charset: `unicode`; color: `ansi16`; autotile: `box_light`
- Tags: unicode, detailed, ansi
- References: Unicode Box Drawing, Block Elements, Geometric Shapes blocks

