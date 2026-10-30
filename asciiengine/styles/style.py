"""Style = a mapping from semantic kinds to glyphs, plus palette / density / conventions.

A Style never touches gameplay data. Swapping a Style changes only appearance.
"""
from __future__ import annotations
import copy
import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from ..core.canvas import ANSI16
from ..core.errors import EngineError
from ..core.kinds import CATEGORIES

RGB = Tuple[int, int, int]

# bit order: N=1, E=2, S=4, W=8
AUTOTILE_TABLES = {
    "box_light":  ["▪", "│", "─", "└", "│", "│", "┌", "├", "─", "┘", "─", "┴", "┐", "┤", "┬", "┼"],
    "box_double": ["▪", "║", "═", "╚", "║", "║", "╔", "╠", "═", "╝", "═", "╩", "╗", "╣", "╦", "╬"],
    "ascii_nh":   ["-", "|", "-", "-", "|", "|", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-"],
    "ascii_plus": ["+", "|", "-", "+", "|", "|", "+", "+", "-", "+", "-", "+", "+", "+", "+", "+"],
}


def parse_color(v) -> Optional[RGB]:
    """Accepts None, '#rrggbb', 'ansi:N' (0-15), [r,g,b] or (r,g,b)."""
    if v is None:
        return None
    if isinstance(v, str):
        if v.startswith("#") and len(v) == 7:
            return (int(v[1:3], 16), int(v[3:5], 16), int(v[5:7], 16))
        if v.startswith("ansi:"):
            return ANSI16[int(v[5:]) % 16]
        raise EngineError(f"Bad color '{v}'", "Use '#rrggbb', 'ansi:N' (0-15) or [r,g,b]", "bad_color")
    if isinstance(v, (list, tuple)) and len(v) == 3:
        return (int(v[0]), int(v[1]), int(v[2]))
    raise EngineError(f"Bad color {v!r}", "Use '#rrggbb', 'ansi:N' or [r,g,b]", "bad_color")


def color_to_json(c: Optional[RGB]):
    return None if c is None else "#%02x%02x%02x" % tuple(c)


@dataclass
class Glyph:
    ch: str
    fg: Optional[RGB] = None
    bg: Optional[RGB] = None

    def __post_init__(self):
        self.fg, self.bg = parse_color(self.fg), parse_color(self.bg)

    def to_json(self):
        d = {"ch": self.ch}
        if self.fg is not None: d["fg"] = color_to_json(self.fg)
        if self.bg is not None: d["bg"] = color_to_json(self.bg)
        return d

    @staticmethod
    def from_json(d):
        if isinstance(d, str):
            return Glyph(d[:1])
        return Glyph(d["ch"][:1], parse_color(d.get("fg")), parse_color(d.get("bg")))


@dataclass
class Style:
    name: str
    description: str = ""
    tags: List[str] = field(default_factory=list)
    charset: str = "ascii"             # ascii | cp437 | unicode  (informational + used for validation)
    color_mode: str = "none"           # none | ansi16 | truecolor
    glyphs: Dict[str, Glyph] = field(default_factory=dict)
    ramp: str = " .:-=+*#%@"           # luminance ramp, light -> dense
    palette: Dict[str, RGB] = field(default_factory=dict)
    autotile: Optional[str] = None     # key of AUTOTILE_TABLES or None
    autotile_kinds: List[str] = field(default_factory=lambda: ["wall"])
    conventions: Dict[str, object] = field(default_factory=dict)
    references: List[str] = field(default_factory=list)
    examples: List[str] = field(default_factory=list)

    # ---- lookup ----
    def glyph(self, kind: str) -> Optional[Glyph]:
        return self.glyphs.get(kind)

    def autotile_char(self, mask: int) -> Optional[str]:
        t = AUTOTILE_TABLES.get(self.autotile or "")
        return t[mask] if t else None

    # ---- composition ----
    def copy(self, name: Optional[str] = None) -> "Style":
        s = copy.deepcopy(self)
        if name:
            s.name = name
        return s

    def override(self, **kind_glyphs) -> "Style":
        """Return a copy with some kinds replaced. Values: 'x' or {'ch':'x','fg':'#fff'} or Glyph."""
        s = self.copy()
        for k, v in kind_glyphs.items():
            s.glyphs[k] = v if isinstance(v, Glyph) else Glyph.from_json(v)
        return s

    def blend(self, other: "Style", take=("colors",), kinds: Optional[List[str]] = None,
              name: Optional[str] = None) -> "Style":
        """Mix characteristics: keep ``self`` as the base and take chosen traits from ``other``.

        take items: 'glyphs' (characters), 'colors' (fg/bg per kind, + palette + color_mode),
        'ramp', 'autotile', 'conventions'. ``kinds`` restricts glyph/color transfer to some kinds.
        """
        s = self.copy(name or f"{self.name}+{other.name}")
        sel = kinds if kinds is not None else list(other.glyphs)
        for k in sel:
            og = other.glyphs.get(k)
            if og is None:
                continue
            cur = s.glyphs.get(k)
            if "glyphs" in take:
                s.glyphs[k] = Glyph(og.ch, og.fg if "colors" in take else (cur.fg if cur else None),
                                    og.bg if "colors" in take else (cur.bg if cur else None))
            elif "colors" in take and cur is not None:
                s.glyphs[k] = Glyph(cur.ch, og.fg, og.bg)
        if "glyphs" in take and any(k in other.glyphs for k in sel):
            rank = {"ascii": 0, "cp437": 1, "unicode": 2}   # keep charset honest: it must cover the glyphs taken
            if rank.get(other.charset, 2) > rank.get(s.charset, 2):
                s.charset = other.charset
        if "colors" in take:
            s.palette = {**s.palette, **other.palette}
            s.color_mode = other.color_mode
        if "ramp" in take: s.ramp = other.ramp
        if "autotile" in take:
            s.autotile, s.autotile_kinds = other.autotile, list(other.autotile_kinds)
        if "conventions" in take: s.conventions = {**s.conventions, **other.conventions}
        s.tags = sorted(set(s.tags) | set(other.tags))
        s.references = list(dict.fromkeys(s.references + other.references))
        s.description = f"Blend of {self.name} (base) and {other.name} (traits: {', '.join(take)})"
        return s

    def tinted(self, color: RGB, name: str, bg: Optional[RGB] = None) -> "Style":
        """Monochrome phosphor look: every fg becomes `color` scaled by its luminance."""
        s = self.copy(name)
        s.color_mode = "truecolor"
        for k, g in s.glyphs.items():
            lum = 1.0 if g.fg is None else max(0.35, (0.299 * g.fg[0] + 0.587 * g.fg[1] + 0.114 * g.fg[2]) / 255)
            g.fg = tuple(int(c * lum) for c in color)
            g.bg = bg
        s.palette = {"fg": color, "bg": bg or (0, 0, 0)}
        return s

    # ---- serialization ----
    def to_dict(self):
        return {"name": self.name, "description": self.description, "tags": self.tags,
                "charset": self.charset, "color_mode": self.color_mode,
                "ramp": self.ramp, "autotile": self.autotile, "autotile_kinds": self.autotile_kinds,
                "palette": {k: color_to_json(v) for k, v in self.palette.items()},
                "conventions": self.conventions, "references": self.references, "examples": self.examples,
                "glyphs": {k: g.to_json() for k, g in self.glyphs.items()}}

    @staticmethod
    def from_dict(d) -> "Style":
        try:
            return Style(name=d["name"], description=d.get("description", ""), tags=list(d.get("tags", [])),
                         charset=d.get("charset", "unicode"), color_mode=d.get("color_mode", "none"),
                         glyphs={k: Glyph.from_json(v) for k, v in d.get("glyphs", {}).items()},
                         ramp=d.get("ramp", " .:-=+*#%@"),
                         palette={k: parse_color(v) for k, v in d.get("palette", {}).items()},
                         autotile=d.get("autotile"), autotile_kinds=list(d.get("autotile_kinds", ["wall"])),
                         conventions=dict(d.get("conventions", {})), references=list(d.get("references", [])),
                         examples=list(d.get("examples", [])))
        except KeyError as e:
            raise EngineError(f"Style JSON is missing field {e}", "A style needs at least 'name' and 'glyphs'",
                              "bad_style")

    def save(self, path: str):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=1)

    @staticmethod
    def load(path: str) -> "Style":
        with open(path, encoding="utf-8") as f:
            return Style.from_dict(json.load(f))

    def validate(self, kinds=None) -> List[str]:
        """Return problems: wrong-width glyphs, charset violations, missing kinds."""
        probs = []
        for k, g in self.glyphs.items():
            if len(g.ch) != 1:
                probs.append(f"{k}: glyph must be exactly one character, got {g.ch!r}")
            if self.charset == "ascii" and ord(g.ch[:1] or " ") > 126:
                probs.append(f"{k}: non-ASCII glyph {g.ch!r} in an 'ascii' charset style")
        if kinds is not None:
            miss = [k for k in kinds.names() if k not in self.glyphs]
            if miss:
                probs.append("missing kinds (will render as '?'): " + ", ".join(miss))
        return probs


class StyleSet:
    """The style 'in force' for a game: a default style plus per-category overrides."""

    FALLBACK = Glyph("?", (255, 0, 255))

    def __init__(self, default: Style):
        self.default = default
        self.by_category: Dict[str, Style] = {}

    def style_for(self, category: str) -> Style:
        return self.by_category.get(category, self.default)

    def set(self, style: Style, categories: Optional[List[str]] = None):
        if categories is None or set(categories) >= set(CATEGORIES):
            self.default, self.by_category = style, {}
            return
        for c in categories:
            if c not in CATEGORIES:
                raise EngineError(f"Unknown category '{c}'", f"Use {CATEGORIES}", "bad_category")
            self.by_category[c] = style

    def glyph(self, kind: str, category: str) -> Glyph:
        st = self.style_for(category)
        g = st.glyph(kind) or self.default.glyph(kind)
        return g or self.FALLBACK

    def describe(self):
        return {"default": self.default.name, **{c: s.name for c, s in sorted(self.by_category.items())}}

    def to_dict(self):
        return {"default": self.default.to_dict(), "by_category": {c: s.to_dict() for c, s in self.by_category.items()}}

    @staticmethod
    def from_dict(d) -> "StyleSet":
        ss = StyleSet(Style.from_dict(d["default"]))
        ss.by_category = {c: Style.from_dict(s) for c, s in d.get("by_category", {}).items()}
        return ss
