"""Render a LayeredMap to a Canvas through a StyleSet.

Composites terrain < structures < objects < entities < effects. Wall-like structures are autotiled
(box-drawing / ascii junctions) using the style's table. ``visible``/``explored`` implement fog of war:
visible cells at full brightness, explored-but-not-visible cells dimmed without entities/effects,
everything else blank. Rendering reads kinds only; it never modifies the map.
"""
from __future__ import annotations

from typing import Iterable, List, Optional, Set, Tuple, Union

from ..core.canvas import Canvas
from ..styles.library import StyleLibrary
from ..styles.style import Glyph, StyleSet
from .layered import LayeredMap, Pos

DOORS = {"door_closed", "door_open", "doorway"}
_N, _E, _S, _W = 1, 2, 4, 8


def _dim(c, f):
    return None if c is None else (int(c[0] * f), int(c[1] * f), int(c[2] * f))


def autotile_glyph(m: LayeredMap, ss: StyleSet, kind: str, x: int, y: int) -> Optional[str]:
    st = ss.style_for("structures")
    if not st.autotile or kind not in st.autotile_kinds:
        return None
    conn = set(st.autotile_kinds) | DOORS
    mask = 0
    for bit, (dx, dy) in ((_N, (0, -1)), (_E, (1, 0)), (_S, (0, 1)), (_W, (-1, 0))):
        if m.layers["structures"].get((x + dx, y + dy)) in conn:
            mask |= bit
    if kind == "door_open":                      # an open door is drawn perpendicular to its wall (NetHack convention)
        if mask & (_E | _W) and not mask & (_N | _S):
            mask = _N | _S
        elif mask & (_N | _S) and not mask & (_E | _W):
            mask = _E | _W
    return st.autotile_char(mask)


def render_map(m: LayeredMap, styleset: Union[StyleSet, str], visible: Optional[Set[Pos]] = None,
               explored: Optional[Set[Pos]] = None, show_entities: bool = True, show_spawn: bool = False,
               viewport: Optional[Tuple[int, int, int, int]] = None, dim: float = 0.45,
               extra_entities: Optional[Iterable[dict]] = None) -> Canvas:
    if isinstance(styleset, str):
        styleset = StyleSet(StyleLibrary().get(styleset))
    vx, vy, vw, vh = viewport or (0, 0, m.width, m.height)
    canvas = Canvas(vw, vh)
    ents = {}
    if show_entities:
        for e in list(m.entities) + list(extra_entities or []):
            ents[(e["x"], e["y"])] = e["kind"]
        if show_spawn and m.spawn and "player" not in ents.values():
            ents.setdefault(m.spawn, "player")
    fog = visible is not None
    for cy in range(vh):
        for cx in range(vw):
            x, y = vx + cx, vy + cy
            if not m.in_bounds(x, y):
                continue
            seen = (not fog) or (x, y) in visible
            if not seen and not (explored and (x, y) in explored):
                continue
            stack: List[Glyph] = []
            stack.append(styleset.glyph(m.get("terrain", x, y), "terrain"))
            s = m.layers["structures"].get((x, y))
            if s:
                g = styleset.glyph(s, "structures")
                ch = autotile_glyph(m, styleset, s, x, y)
                stack.append(Glyph(ch, g.fg, g.bg) if ch else g)
            o = m.layers["objects"].get((x, y))
            if o:
                stack.append(styleset.glyph(o, "objects"))
            if seen:
                if (x, y) in ents:
                    stack.append(styleset.glyph(ents[(x, y)], "entities"))
                f = m.layers["effects"].get((x, y))
                if f:
                    stack.append(styleset.glyph(f, "effects"))
            top = stack[-1]
            bg = next((g.bg for g in reversed(stack) if g.bg is not None), None)
            fg = top.fg
            if not seen:
                fg, bg = _dim(fg, dim), _dim(bg, dim)
            canvas.put(cx, cy, top.ch, fg, bg)
    return canvas


def render_text(m: LayeredMap, style: Union[StyleSet, str] = "classic_ascii", **kw) -> str:
    return render_map(m, style, **kw).to_text()
