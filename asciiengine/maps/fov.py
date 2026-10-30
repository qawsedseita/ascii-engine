"""Field of view (recursive shadowcasting) and limited lighting.

A cell is *seen* when it is in line of sight AND lit. Lit means: inside a region with props.lit=True,
reached by a light source (map.lights, with line of sight from the source), or within the viewer's own
small light radius. This gives NetHack-style play: lit rooms are revealed from afar, corridors and dark
rooms only a few cells around you.
"""
from __future__ import annotations

from typing import Optional, Set, Tuple

from .layered import LayeredMap, Pos

_XX = [1, 0, 0, -1, -1, 0, 0, 1]
_XY = [0, 1, -1, 0, 0, -1, 1, 0]
_YX = [0, 1, 1, 0, 0, -1, -1, 0]
_YY = [1, 0, 0, 1, -1, 0, 0, -1]


def _cast(m, cx, cy, row, start, end, radius, xx, xy, yx, yy, out):
    if start < end:
        return
    r2 = radius * radius + radius
    new_start = start
    for j in range(row, radius + 1):
        dx, dy = -j - 1, -j
        blocked = False
        while dx <= 0:
            dx += 1
            X, Y = cx + dx * xx + dy * xy, cy + dx * yx + dy * yy
            l_slope, r_slope = (dx - 0.5) / (dy + 0.5), (dx + 0.5) / (dy - 0.5)
            if start < r_slope:
                continue
            if end > l_slope:
                break
            if dx * dx + dy * dy <= r2 and m.in_bounds(X, Y):
                out.add((X, Y))
            opaque = m.blocks_sight(X, Y)
            if blocked:
                if opaque:
                    new_start = r_slope
                    continue
                blocked = False
                start = new_start
            elif opaque and j < radius:
                blocked = True
                _cast(m, cx, cy, j + 1, start, l_slope, radius, xx, xy, yx, yy, out)
                new_start = r_slope
        if blocked:
            break


def compute_fov(m: LayeredMap, x: int, y: int, radius: int) -> Set[Pos]:
    """Cells in line of sight of (x, y) within ``radius`` (opaque cells that bound the view are included)."""
    out: Set[Pos] = {(x, y)} if m.in_bounds(x, y) else set()
    for o in range(8):
        _cast(m, x, y, 1, 1.0, 0.0, radius, _XX[o], _XY[o], _YX[o], _YY[o], out)
    return out


def lit_cells(m: LayeredMap) -> Set[Pos]:
    out: Set[Pos] = set()
    for r in m.regions.values():
        if r.get("props", {}).get("lit"):
            x, y, w, h = r["rect"]
            out.update((i, j) for j in range(y, y + h) for i in range(x, x + w))
    for l in m.lights:
        out |= compute_fov(m, l["x"], l["y"], int(l["radius"]))
    return out


def player_view(m: LayeredMap, x: int, y: int, light_radius: int = 2, vision: int = 30,
                lit: Optional[Set[Pos]] = None) -> Set[Pos]:
    """What the viewer sees now. ``light_radius`` is the viewer's own light (0 = sees only lit areas + own cell)."""
    lit = lit_cells(m) if lit is None else lit
    seen = compute_fov(m, x, y, vision)
    r2 = light_radius * light_radius + light_radius
    out = {c for c in seen if c in lit or (c[0] - x) ** 2 + (c[1] - y) ** 2 <= r2}
    out.add((x, y))
    return out
