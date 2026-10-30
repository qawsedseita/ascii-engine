"""Built-in style library + registry (load/save custom styles).

Conventions below were distilled from public documentation of existing roguelikes
(NetHack symsets/guidebook, Dwarf Fortress wiki, Caves of Qud wiki, Cataclysm: DDA, the
r/roguelikedev "map object representation" FAQ). They are *rules we re-implement*,
not copies of any game's assets. See each style's ``references`` field.
"""
from __future__ import annotations
import glob
import os
from typing import Dict, List, Optional

from ..core.canvas import ANSI16
from ..core.errors import EngineError
from .style import Glyph, Style

C = lambda i: ANSI16[i]

# kind -> ansi16 index used by colored styles
COLOR_IDX = {
    "void": 0, "floor": 7, "corridor": 8, "grass": 2, "sand": 11, "water": 4, "shallow_water": 12, "lava": 9, "snow": 15,
    "mud": 3, "road": 8, "wall": 7, "door_closed": 3, "door_open": 3, "doorway": 7, "stairs_down": 15, "stairs_up": 15,
    "tree": 2, "rock": 8, "pillar": 7, "window": 14, "fence": 3,
    "chest": 3, "torch": 11, "gold": 11, "potion": 13, "weapon": 14, "armor": 6, "scroll": 15, "key": 11, "altar": 7,
    "fountain": 12, "trap": 9, "table": 3, "bed": 5, "food": 3,
    "player": 15, "npc": 11, "rat": 3, "goblin": 2, "orc": 10, "skeleton": 15, "slime": 10, "bat": 8, "dragon": 9,
    "wolf": 7, "ghost": 8, "creature": 13,
    "spark": 11, "smoke": 8, "fire": 9, "blood": 1, "magic": 13, "rain": 12, "slash": 15,
    "ui_hline": 7, "ui_vline": 7, "ui_corner_tl": 7, "ui_corner_tr": 7, "ui_corner_bl": 7, "ui_corner_br": 7,
    "ui_bar_full": 10, "ui_bar_empty": 8, "ui_cursor": 11,
}

# plain ASCII baseline for every built-in kind
BASE = {
    "void": " ", "floor": ".", "corridor": "#", "grass": '"', "sand": ":", "water": "~", "shallow_water": "-",
    "lava": "~", "snow": ".", "mud": ",", "road": ".",
    "wall": "#", "door_closed": "+", "door_open": "'", "doorway": ".", "stairs_down": ">", "stairs_up": "<",
    "tree": "T", "rock": "0", "pillar": "O", "window": "=", "fence": "|",
    "chest": "(", "torch": "!", "gold": "$", "potion": "!", "weapon": ")", "armor": "[", "scroll": "?", "key": "-",
    "altar": "_", "fountain": "{", "trap": "^", "table": "n", "bed": "=", "food": "%",
    "player": "@", "npc": "@", "rat": "r", "goblin": "g", "orc": "o", "skeleton": "s", "slime": "j", "bat": "b",
    "dragon": "D", "wolf": "d", "ghost": "G", "creature": "m",
    "spark": "*", "smoke": "'", "fire": "^", "blood": ",", "magic": "*", "rain": "/", "slash": "/",
    "ui_hline": "-", "ui_vline": "|", "ui_corner_tl": "+", "ui_corner_tr": "+", "ui_corner_bl": "+",
    "ui_corner_br": "+", "ui_bar_full": "#", "ui_bar_empty": ".", "ui_cursor": ">",
}

DENSE_RAMP = " .'`^\",:;Il!i><~+_-?][}{1)(|/tfjrxnuvczXYUJCLQ0OZmwqpdbkhao*#MW&8%B@$"


def _build(name, description, charset, color_mode, overrides=None, colors=True, color_over=None, bg=None, **kw) -> Style:
    g = {}
    for k, ch in BASE.items():
        g[k] = Glyph(ch, C(COLOR_IDX[k]) if colors and color_mode != "none" else None, bg if color_mode != "none" else None)
    for k, v in (overrides or {}).items():
        if isinstance(v, tuple):
            g[k] = Glyph(v[0], C(v[1]) if isinstance(v[1], int) else v[1], g[k].bg)
        else:
            g[k].ch = v
    for k, idx in (color_over or {}).items():
        g[k].fg = C(idx) if isinstance(idx, int) else idx
    return Style(name=name, description=description, charset=charset, color_mode=color_mode, glyphs=g, **kw)


def _builtin() -> Dict[str, Style]:
    L: Dict[str, Style] = {}

    L["classic_ascii"] = _build(
        "classic_ascii", "Plain 7-bit ASCII, no color. Maximum compatibility; every kind is one printable ASCII char.",
        "ascii", "none", tags=["classic", "ascii", "monochrome"],
        references=["Rogue/NetHack-era ASCII conventions"],
        conventions={"unlit": "hide", "creatures": "letters", "terrain": "punctuation"})

    L["rogue"] = _build(
        "rogue", "Original Rogue conventions: | - walls, + doors, # passages, % stairs, * gold, ! potion, ? scroll, ] armor.",
        "ascii", "none", overrides={"stairs_down": "%", "stairs_up": "%", "gold": "*", "food": ":", "armor": "]",
                                     "weapon": ")", "key": ",", "corridor": "#", "player": "@"},
        autotile="ascii_nh", tags=["roguelike", "classic", "ascii"],
        references=["https://nethackwiki.com (genealogy), r/roguelikedev FAQ Friday #28 (map object representation)"],
        conventions={"unlit": "remember", "creatures": "uppercase letters", "terrain": "punctuation"})
    L["rogue"].autotile_kinds = ["wall", "door_closed", "door_open"]

    nh_over = {"wall": "-", "corridor": "#", "door_closed": "+", "door_open": "|", "doorway": ".", "stairs_down": ">",
               "stairs_up": "<", "water": "}", "lava": "}", "shallow_water": "}", "tree": "#", "window": "#",
               "fountain": "{", "altar": "_", "trap": "^", "chest": "(", "armor": "[", "weapon": ")", "potion": "!",
               "scroll": "?", "gold": "$", "food": "%", "key": "(", "torch": "(", "rock": "`", "pillar": "|",
               "player": "@", "npc": "@", "rat": "r", "goblin": "o", "orc": "o", "skeleton": "Z", "slime": "j",
               "bat": "B", "dragon": "D", "wolf": "d", "ghost": "W", "creature": "&"}
    nh_col = {"floor": 7, "corridor": 7, "wall": 7, "door_closed": 3, "door_open": 3, "water": 4, "lava": 9, "tree": 2,
              "fountain": 12, "altar": 7, "gold": 11, "player": 15}
    L["nethack"] = _build(
        "nethack", "NetHack default symset: | and - walls, . floor, # corridor, + door, < > stairs, letters for monsters, "
        "$ gold, % food, ! potion, ? scroll, [ armor, ) weapon, ( tool, } water.",
        "ascii", "ansi16", overrides=nh_over, color_over=nh_col, autotile="ascii_nh",
        autotile_kinds=["wall", "door_open"], tags=["roguelike", "nethack", "ascii", "ansi"],
        references=["https://nethackwiki.com/wiki/Symset", "https://nethackwiki.com/wiki/Custom_map_symbols_(3.4.3)",
                    "https://alt.org/nethack/mirror/www.geocities.com/TimesSquare/Portal/2416/map.html"],
        conventions={"unlit": "remember", "creatures": "one letter per class, @ = human",
                     "line_of_sight": "lit rooms revealed as you enter", "doors": "+ closed, | or - open, . doorless"})

    L["nethack_utf8"] = L["nethack"].copy("nethack_utf8")
    L["nethack_utf8"].description = ("NetHack with UTF8graphics-style symbols: box-drawing walls, · doorway/floor, "
                                     "░ ▒ corridors, ≡ iron bars, Ψ tree.")
    L["nethack_utf8"].charset = "unicode"
    L["nethack_utf8"].autotile = "box_light"
    L["nethack_utf8"].tags = ["roguelike", "nethack", "unicode", "ansi"]
    for k, ch in {"floor": "·", "doorway": "·", "corridor": "▒", "window": "≡", "tree": "Ψ", "door_open": "▒",
                  "pillar": "│"}.items():
        L["nethack_utf8"].glyphs[k].ch = ch
    L["nethack_utf8"].references = ["https://nethackwiki.com/wiki/UTF8graphics",
                                    "https://nethackwiki.com/wiki/Custom_map_symbols_(3.4.3)"]

    df_over = {"floor": ".", "corridor": ".", "grass": '"', "sand": "~", "water": "≈", "shallow_water": "≈", "lava": "≈",
               "wall": "#", "door_closed": "▓", "door_open": "▒", "doorway": "'", "stairs_down": ">", "stairs_up": "<",
               "tree": "♣", "rock": "●", "pillar": "○", "window": "║", "fence": "╬", "chest": "≡", "gold": "☼",
               "torch": "i", "fountain": "≡", "table": "╥", "bed": "Θ", "player": "☺", "npc": "☺", "rat": "r", "goblin": "g",
               "orc": "O", "skeleton": "s", "slime": "j", "bat": "b", "dragon": "D", "wolf": "C", "ghost": "G",
               "creature": "☻"}
    df_col = {"floor": 8, "corridor": 8, "grass": 10, "sand": 14, "water": 12, "shallow_water": 12, "lava": 9, "wall": 7,
              "tree": 2, "player": 14, "npc": 14, "goblin": 2, "orc": 10, "wolf": 6, "rock": 8, "gold": 14}
    L["dwarf_fortress"] = _build(
        "dwarf_fortress", "Dwarf Fortress-like: CP437 glyphs, a 16-color scheme with per-tile foreground AND background, "
        "color encodes material/biome, smoothed walls drawn with double-line box characters, ☺ for the citizens.",
        "cp437", "ansi16", overrides=df_over, color_over=df_col, bg=C(0), autotile="box_double",
        autotile_kinds=["wall"], tags=["roguelike", "dwarf_fortress", "cp437", "ansi", "colorful"],
        references=["https://dwarffortresswiki.org/index.php/DF2014:Color", "https://dwarffortresswiki.org/index.php/DF2014:Tileset",
                    "https://dwarffortresswiki.org/Map_legend"],
        conventions={"colors": "16-color scheme; fg and bg per tile", "color_meaning": "material, biome and creature profession",
                     "walls": "smoothed walls autotile to double-line box characters", "unlit": "dim"})

    qud_over = {"floor": ".", "corridor": "·", "grass": ",", "sand": "`", "snow": "'", "mud": "~", "road": "=",
                "water": "≈", "shallow_water": "~", "lava": "≈", "wall": "#", "door_closed": "+", "door_open": "/",
                "tree": "♣", "rock": "▲", "chest": "&", "player": "@", "npc": "@", "rat": "r", "goblin": "g",
                "orc": "O", "skeleton": "s", "slime": "a", "bat": "b", "dragon": "D", "wolf": "d", "ghost": "&",
                "creature": "8"}
    qud_col = {"floor": 8, "grass": 2, "sand": 3, "water": 12, "lava": 9, "wall": 8, "tree": 2, "player": 15,
               "creature": 14, "slime": 10, "ghost": 13}
    L["caves_of_qud"] = _build(
        "caves_of_qud", "Caves of Qud-like: punctuation ground textures, letters for creatures, digits for robots, "
        "dark backgrounds, each tile limited to a primary / detail / background color triple.",
        "unicode", "truecolor", overrides=qud_over, color_over=qud_col, bg=(10, 14, 20), autotile=None,
        tags=["roguelike", "qud", "unicode", "colorful", "sci-fi"],
        references=["https://wiki.cavesofqud.com/wiki/Visual_Style",
                    "https://waltoriouswritesaboutgames.com/2013/02/23/roguelike-highlights-caves-of-qud/"],
        conventions={"zone": "80x25", "colors_per_tile": 3, "creatures": "letters", "robots": "digits",
                     "ground": "punctuation textures", "unlit": "dim"},
        palette={"primary": C(2), "detail": C(14), "background": (10, 14, 20)})

    cdda_over = {"floor": ".", "corridor": ".", "grass": ".", "road": "═", "tree": "T", "water": "~", "wall": "#",
                 "door_closed": "+", "door_open": "'", "window": "\"", "player": "@", "npc": "@", "rat": "r", "goblin": "g",
                 "orc": "O", "skeleton": "Z", "slime": "P", "bat": "b", "dragon": "D", "wolf": "d", "ghost": "Z",
                 "creature": "Z"}
    L["cataclysm"] = _build(
        "cataclysm", "Cataclysm: DDA-like ncurses look: extended-ASCII box-drawing roads and walls, color is part of the "
        "symbol's meaning, zombies as Z, built to survive limited-color terminals.",
        "cp437", "ansi16", overrides=cdda_over, color_over={"grass": 10, "tree": 2, "road": 8, "wall": 7, "skeleton": 7,
                                                             "creature": 10, "water": 12},
        autotile="box_light", autotile_kinds=["wall"], tags=["roguelike", "cdda", "cp437", "ansi", "survival"],
        references=["https://discourse.cataclysmdda.org/t/my-overmap-looks-very-unintelligible-help/26474",
                    "https://discourse.cataclysmdda.org/t/map-symbol-clarification/5597"],
        conventions={"colors": "integral to symbol meaning; must degrade to 16 colors", "unlit": "dim"})

    base_classic = L["classic_ascii"].copy("tmp")
    base_classic.autotile, base_classic.autotile_kinds = "ascii_plus", ["wall"]
    L["retro_terminal"] = base_classic.tinted((51, 255, 85), "retro_terminal", bg=(0, 12, 0))
    L["retro_terminal"].description = "Green phosphor CRT terminal: a single hue, brightness carries the information."
    L["retro_terminal"].tags = ["retro", "terminal", "monochrome", "crt"]
    L["retro_terminal"].conventions = {"scanlines": True, "unlit": "dim", "phosphor": "green"}
    L["retro_terminal"].references = ["monochrome CRT phosphor convention (P1 green)"]
    L["amber_terminal"] = base_classic.tinted((255, 176, 0), "amber_terminal", bg=(12, 6, 0))
    L["amber_terminal"].description = "Amber phosphor CRT terminal."
    L["amber_terminal"].tags = ["retro", "terminal", "monochrome", "crt"]
    L["amber_terminal"].conventions = {"scanlines": True, "unlit": "dim", "phosphor": "amber"}

    mini = {k: ("." if k in ("floor", "corridor", "grass", "road", "snow", "sand", "mud") else v) for k, v in BASE.items()}
    mini.update({"floor": " ", "corridor": " ", "grass": " ", "road": " ", "snow": " ", "sand": " ", "mud": " ",
                 "void": " ", "wall": "#", "door_closed": "+", "door_open": "/", "doorway": " ", "water": "~",
                 "shallow_water": "~", "lava": "~", "tree": "t", "rock": "o", "pillar": "o", "window": "#",
                 "fence": "#", "chest": "*", "torch": "*", "gold": "*", "potion": "*", "weapon": "*", "armor": "*",
                 "scroll": "*", "key": "*", "altar": "*", "fountain": "*", "trap": "^", "table": "*", "bed": "*",
                 "food": "*", "npc": "p", "rat": "e", "goblin": "e", "orc": "e", "skeleton": "e", "slime": "e",
                 "bat": "e", "dragon": "E", "wolf": "e", "ghost": "e", "creature": "e"})
    L["minimalist"] = Style("minimalist", "Minimal: empty floors, # walls, @ player, e for enemies, * for any item. "
                            "Few distinct glyphs, high readability.", charset="ascii", color_mode="none",
                            glyphs={k: Glyph(v) for k, v in mini.items()}, ramp=" .#", autotile=None,
                            tags=["minimal", "ascii", "monochrome"], references=["reduction of the classic set"],
                            conventions={"floor": "empty", "unlit": "hide"})

    det = {"floor": "·", "corridor": "░", "grass": "ʼ", "sand": "∙", "water": "≈", "shallow_water": "∼", "lava": "≋", "snow": "∙",
           "mud": "▒", "road": "▒", "wall": "█", "door_closed": "■", "door_open": "□", "doorway": "·", "stairs_down": "▼",
           "stairs_up": "▲", "tree": "♣", "rock": "●", "pillar": "◆", "window": "▫", "fence": "╫", "chest": "▣",
           "torch": "¡", "gold": "◎", "potion": "♁", "weapon": "†", "armor": "⛨", "scroll": "≡", "key": "⚷", "altar": "╤",
           "fountain": "♨", "trap": "×", "table": "┬", "bed": "▭", "food": "♥", "player": "☻", "npc": "☺", "rat": "ʀ",
           "goblin": "ɢ", "orc": "Ω", "skeleton": "☠", "slime": "◍", "bat": "ʙ", "dragon": "Ð", "wolf": "ᴡ", "ghost": "☁",
           "creature": "✦", "spark": "✧", "smoke": "░", "fire": "♨", "blood": "▪", "magic": "✺", "rain": "╱", "slash": "╱"}
    detailed = {k: Glyph(det.get(k, BASE[k]), C(COLOR_IDX[k])) for k in BASE}
    L["unicode_detailed"] = Style(
        "unicode_detailed", "Detailed Unicode: box-drawing walls, shade blocks, dingbats; richer silhouettes per kind.",
        charset="unicode", color_mode="ansi16", glyphs=detailed, ramp=" ·∙░▒▓█", autotile="box_light", tags=["unicode", "detailed", "ansi"],
        references=["Unicode Box Drawing, Block Elements, Geometric Shapes blocks"],
        conventions={"unlit": "dim", "shading": "░▒▓█ for density"})
    L["unicode_detailed"].autotile_kinds = ["wall"]

    modern = {k: Glyph(det.get(k, BASE[k]), None) for k in BASE}
    pal = {"bg": (20, 22, 30), "wall": (110, 118, 140), "floor": (62, 68, 86), "accent": (136, 192, 208),
           "danger": (191, 97, 106), "good": (163, 190, 140), "warn": (235, 203, 139)}
    tcol = {"void": (20, 22, 30), "floor": pal["floor"], "corridor": (50, 55, 72), "grass": (94, 129, 92),
            "sand": (190, 170, 120), "water": (76, 110, 170), "shallow_water": (100, 140, 190), "lava": (220, 90, 50),
            "snow": (225, 232, 240), "mud": (110, 85, 60), "road": (90, 90, 100), "wall": pal["wall"],
            "door_closed": (190, 140, 80), "door_open": (160, 120, 70), "doorway": pal["floor"], "stairs_down": pal["accent"],
            "stairs_up": pal["accent"], "tree": (80, 130, 80), "rock": (120, 120, 130), "player": (255, 255, 255),
            "npc": pal["warn"], "gold": pal["warn"], "dragon": pal["danger"], "orc": (130, 200, 110),
            "goblin": (110, 180, 100), "slime": (120, 220, 160), "ghost": (180, 190, 220), "creature": (200, 140, 220)}
    for k, g in modern.items():
        g.fg = tcol.get(k, (200, 205, 220) if k.startswith(("ui", "spark", "magic")) else (216, 222, 233))
        g.bg = pal["bg"]
    L["ansi_modern"] = Style(
        "ansi_modern", "Modern truecolor terminal: solid blocks for walls, simulated transparency via ░▒▓ shades, "
        "dark theme palette, box-drawing UI.", charset="unicode", color_mode="truecolor", glyphs=modern, ramp=" ░▒▓█", palette=pal,
        autotile="box_light", tags=["modern", "terminal", "truecolor", "unicode"],
        references=["modern terminal truecolor (24-bit SGR) palettes"],
        conventions={"transparency": "░▒▓ blocks simulate alpha", "unlit": "dim", "ui": "box drawing"})
    L["ansi_modern"].glyphs["wall"].ch = "█"
    L["ansi_modern"].autotile = None
    return L


class StyleLibrary:
    def __init__(self, user_dir: Optional[str] = None):
        self._styles: Dict[str, Style] = _builtin()
        self.builtin = set(self._styles)
        self.user_dir = user_dir
        if user_dir:
            self.load_directory(user_dir)

    def names(self) -> List[str]:
        return sorted(self._styles)

    def get(self, name: str) -> Style:
        key = name.lower().strip().replace(" ", "_").replace("-", "_")
        if key not in self._styles:
            raise EngineError(f"Unknown style '{name}'", "Available: " + ", ".join(self.names()), "unknown_style")
        return self._styles[key]

    def add(self, style: Style, save: bool = False, directory: Optional[str] = None) -> Style:
        self._styles[style.name] = style
        if save:
            d = directory or self.user_dir
            if not d:
                raise EngineError("No directory to save the style in", "Pass directory= or create the library with user_dir=",
                                  "no_dir")
            os.makedirs(d, exist_ok=True)
            style.save(os.path.join(d, f"{style.name}.style.json"))
        return style

    def create(self, name: str, based_on: str = "classic_ascii", glyphs: Optional[dict] = None, save: bool = False,
               description: str = "", **fields) -> Style:
        """Create a custom style: copy ``based_on``, override glyphs / fields, register (and optionally save)."""
        s = self.get(based_on).copy(name)
        s.description = description or f"Custom style based on {based_on}"
        s.tags = sorted(set(s.tags) | {"custom"})
        for k, v in (glyphs or {}).items():
            s.glyphs[k] = v if isinstance(v, Glyph) else Glyph.from_json(v)
        for k, v in fields.items():
            if not hasattr(s, k):
                raise EngineError(f"Style has no field '{k}'", "Fields: ramp, palette, autotile, color_mode, conventions...", "bad_field")
            setattr(s, k, v)
        probs = s.validate()
        if probs:
            raise EngineError("Invalid style: " + "; ".join(probs), "Fix the glyphs listed above", "invalid_style")
        return self.add(s, save=save)

    def load_directory(self, directory: str) -> int:
        n = 0
        for p in sorted(glob.glob(os.path.join(directory, "*.style.json"))):
            s = Style.load(p)
            self._styles[s.name] = s
            n += 1
        return n

    def search(self, *tags: str) -> List[str]:
        return [n for n, s in sorted(self._styles.items()) if all(t in s.tags for t in tags)]
