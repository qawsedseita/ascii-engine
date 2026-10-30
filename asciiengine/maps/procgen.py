"""Procedural generation: dungeon (N rooms, always connected), cave, biomes, and populate().

All generators are deterministic for a given ``seed``. They never silently degrade: if the requested
layout cannot be built (e.g. 20 rooms in a tiny map) they raise an EngineError with a hint.
"""
from __future__ import annotations

import math
import random
from typing import Dict, List, Optional, Tuple

from ..core.errors import EngineError
from .editor import MapEditor
from .layered import LayeredMap, Pos
from .pathing import components, distance_map, reachable
from .validate import validate_map

Rect = Tuple[int, int, int, int]
DOOR_CHOICES = [("doorway", 0.4), ("door_closed", 0.35), ("door_open", 0.25)]


def _rng(seed) -> random.Random:
    return random.Random(seed)


def _inside(r: Rect, x: int, y: int) -> bool:
    return r[0] <= x < r[0] + r[2] and r[1] <= y < r[1] + r[3]


def _interior(r: Rect):
    return [(x, y) for y in range(r[1] + 1, r[1] + r[3] - 1) for x in range(r[0] + 1, r[0] + r[2] - 1)]


def _center(r: Rect) -> Pos:
    return (r[0] + r[2] // 2, r[1] + r[3] // 2)


def _set_stairs(m: LayeredMap):
    m.set_cell(*m.spawn, "stairs_up")
    m.set_cell(*m.exit, "stairs_down")


# ---------------------------------------------------------------------------------------------- dungeon
def dungeon(width: int = 80, height: int = 40, rooms: int = 20, seed=None, min_size: Tuple[int, int] = (6, 5),
            max_size: Tuple[int, int] = (12, 8), lit_ratio: float = 0.4, extra_links: int = 3,
            name: str = "dungeon") -> LayeredMap:
    """Rooms (outer sizes include walls) joined by corridors; spawn in one room, exit in the farthest room."""
    rng = _rng(seed)
    m = LayeredMap(width, height, name=name)
    ed = MapEditor(m)
    rects: List[Rect] = []
    for _ in range(rooms * 300):
        if len(rects) >= rooms:
            break
        w, h = rng.randint(min_size[0], max_size[0]), rng.randint(min_size[1], max_size[1])
        if w > width - 2 or h > height - 2:
            continue
        x, y = rng.randint(1, width - w - 1), rng.randint(1, height - h - 1)
        if all(x + w + 2 <= r[0] or r[0] + r[2] + 2 <= x or y + h + 2 <= r[1] or r[1] + r[3] + 2 <= y for r in rects):
            rects.append((x, y, w, h))
    if len(rects) < rooms:
        raise EngineError(f"Could only place {len(rects)} of {rooms} rooms in {width}x{height}",
                          "Use a bigger map, fewer rooms or smaller max_size", "dungeon_too_small")
    rects.sort(key=lambda r: (r[1], r[0]))
    for i, r in enumerate(rects):
        res = ed.run_one({"cmd": "room", "x": r[0], "y": r[1], "w": r[2], "h": r[3], "name": f"room_{i + 1}",
                          "lit": rng.random() < lit_ratio})
        assert res["ok"], res
    # links: Prim's minimum spanning tree over centres, then a few extra loops
    cs = [_center(r) for r in rects]
    d = lambda a, b: abs(cs[a][0] - cs[b][0]) + abs(cs[a][1] - cs[b][1])
    in_tree, links = {0}, []
    while len(in_tree) < len(rects):
        a, b = min(((a, b) for a in in_tree for b in range(len(rects)) if b not in in_tree), key=lambda p: d(*p))
        links.append((a, b)); in_tree.add(b)
    for _ in range(extra_links):
        a, b = rng.sample(range(len(rects)), 2)
        if (a, b) not in links and (b, a) not in links:
            links.append((a, b))
    for a, b in links:
        _link(m, rects, a, b, rng)
    m.spawn = _center(rects[0])
    dist = distance_map(m, m.spawn)
    far = max(range(1, len(rects)), key=lambda i: dist.get(_center(rects[i]), -1))
    m.exit = _center(rects[far])
    _set_stairs(m)
    m.meta.update({"generator": "dungeon", "seed": seed, "rooms": len(rects)})
    rep = validate_map(m)
    if not rep["ok"]:                                    # a generator bug must never reach the user silently
        raise EngineError("Generated dungeon failed validation: " + "; ".join(rep["errors"]), "report this seed", "gen_bug")
    return m


def _door_cell(r: Rect, side: str, rng) -> Tuple[Pos, Pos]:
    """(door cell on the wall, corridor cell just outside)."""
    x, y, w, h = r
    if side in ("E", "W"):
        yy = rng.randint(y + 1, y + h - 2)
        return ((x + w - 1, yy), (x + w, yy)) if side == "E" else ((x, yy), (x - 1, yy))
    xx = rng.randint(x + 1, x + w - 2)
    return ((xx, y + h - 1), (xx, y + h)) if side == "S" else ((xx, y), (xx, y - 1))


def _link(m: LayeredMap, rects: List[Rect], a: int, b: int, rng):
    ra, rb = rects[a], rects[b]
    (ax, ay), (bx, by) = _center(ra), _center(rb)
    if abs(bx - ax) >= abs(by - ay):
        sa, sb = ("E", "W") if bx > ax else ("W", "E")
    else:
        sa, sb = ("S", "N") if by > ay else ("N", "S")
    (da, oa), (db, ob) = _door_cell(ra, sa, rng), _door_cell(rb, sb, rng)
    others = [r for i, r in enumerate(rects) if i not in (a, b)]

    def path(order):
        (x1, y1), (x2, y2) = oa, ob
        sx, sy = (1 if x2 >= x1 else -1), (1 if y2 >= y1 else -1)
        if order == "hv":
            return [(x, y1) for x in range(x1, x2 + sx, sx)] + [(x2, y) for y in range(y1 + sy, y2 + sy, sy)]
        return [(x1, y) for y in range(y1, y2 + sy, sy)] + [(x, y2) for x in range(x1 + sx, x2 + sx, sx)]

    cost = lambda p: sum(any(_inside(r, x, y) for r in others) for x, y in p)
    pa, pb = path("hv"), path("vh")
    for x, y in (pa if cost(pa) <= cost(pb) else pb):
        s = m.layers["structures"].get((x, y))
        if s == "wall":                                  # crossing a wall: open a doorway through it
            m.set_cell(x, y, "doorway")
        elif s is None and m.get("terrain", x, y) == "void":
            m.set_cell(x, y, "corridor")
    for cell in (da, db):
        kind = rng.choices([k for k, _ in DOOR_CHOICES], [w for _, w in DOOR_CHOICES])[0]
        m.set_cell(cell[0], cell[1], kind)


# ---------------------------------------------------------------------------------------------- populate
CREATURE_TIERS = [["rat", "bat", "slime"], ["goblin", "wolf", "skeleton"],
                  ["orc", "orc", "ghost", "wolf", "skeleton", "dragon"]]   # dragons are rare, even far away
ITEMS = ["gold", "gold", "potion", "scroll", "food", "weapon", "armor", "key"]


def populate(m: LayeredMap, seed=None, creatures: int = 24, items: int = 18, chests: int = 3, torches: int = 3,
             min_spawn_distance: int = 8, creature_kinds: Optional[List[str]] = None) -> dict:
    """Spread creatures over the rooms (one per room first, round-robin), stronger farther from the spawn;
    then items, chests (only where they do not block connectivity) and torches with light sources."""
    rng = _rng(seed)
    if m.spawn is None:
        raise EngineError("populate needs a spawn point", "Generate or set spawn first", "no_spawn")
    dist = distance_map(m, m.spawn)
    rooms = [(n, r["rect"]) for n, r in sorted(m.regions.items()) if r.get("type") == "room"]
    if not rooms:
        rooms = [("map", [0, 0, m.width, m.height])]
    maxd = max(dist.values()) or 1
    taken = {m.spawn, m.exit} | {(e["x"], e["y"]) for e in m.entities}

    def free_cells(rect, min_dist=0):
        return [c for c in _interior(tuple(rect)) if c in dist and c not in taken and dist[c] >= min_dist
                and m.walkable(*c) and not m.layers["objects"].get(c)]

    def tier_kind(d):
        if creature_kinds:
            return rng.choice(creature_kinds)
        t = min(len(CREATURE_TIERS) - 1, int((d / maxd) * len(CREATURE_TIERS) + rng.uniform(-0.6, 0.6)))
        return rng.choice(CREATURE_TIERS[max(0, t)])

    order = [r for r in rooms]
    placed_c, rooms_used = 0, set()
    attempts = 0
    while placed_c < creatures and attempts < creatures * 20:
        rng.shuffle(order)
        for name, rect in order:
            if placed_c >= creatures:
                break
            attempts += 1
            cells = free_cells(rect, min_spawn_distance)
            if not cells:
                continue
            c = rng.choice(cells)
            m.add_entity(tier_kind(dist[c]), c[0], c[1]); taken.add(c); rooms_used.add(name); placed_c += 1
    placed_i = 0
    for _ in range(items):
        name, rect = rng.choice(rooms)
        cells = free_cells(rect)
        if cells:
            c = rng.choice(cells); m.set_cell(c[0], c[1], rng.choice(ITEMS)); taken.add(c); placed_i += 1
    placed_ch = 0
    base = len(reachable(m, m.spawn))
    for _ in range(chests * 10):
        if placed_ch >= chests:
            break
        name, rect = rng.choice(rooms)
        cells = free_cells(rect)
        if not cells:
            continue
        c = rng.choice(cells)
        m.set_cell(c[0], c[1], "chest")
        if len(reachable(m, m.spawn)) < base - 1 or (m.exit and m.exit not in reachable(m, m.spawn)):
            m.set_cell(c[0], c[1], None, "objects")      # would block a route: undo
            continue
        taken.add(c); placed_ch += 1; base -= 1
    placed_t = 0
    dark = [(n, r) for n, r in rooms if not m.regions.get(n, {}).get("props", {}).get("lit")]
    for _ in range(torches):
        if not dark:
            break
        name, rect = rng.choice(dark)
        cells = free_cells(rect)
        if cells:
            c = rng.choice(cells); m.set_cell(c[0], c[1], "torch"); m.lights.append({"x": c[0], "y": c[1], "radius": 5})
            taken.add(c); placed_t += 1
    return {"creatures": placed_c, "rooms_with_creatures": len(rooms_used), "items": placed_i, "chests": placed_ch,
            "torches": placed_t}


# ---------------------------------------------------------------------------------------------- cave
def cave(width: int = 60, height: int = 30, seed=None, fill: float = 0.45, steps: int = 4, name: str = "cave") -> LayeredMap:
    rng = _rng(seed)
    for _try in range(20):
        wall = [[(x in (0, width - 1) or y in (0, height - 1) or rng.random() < fill) for x in range(width)] for y in range(height)]
        for _ in range(steps):
            new = [row[:] for row in wall]
            for y in range(1, height - 1):
                for x in range(1, width - 1):
                    n = sum(wall[y + j][x + i] for j in (-1, 0, 1) for i in (-1, 0, 1) if i or j)
                    new[y][x] = n >= 5 if wall[y][x] else n >= 6
            wall = new
        m = LayeredMap(width, height, name=name)
        for y in range(height):
            for x in range(width):
                if not wall[y][x]:
                    m.set_cell(x, y, "floor")
        comps = components(m)
        if not comps or len(comps[0]) < width * height * 0.12:
            continue
        keep = comps[0]
        for y in range(height):
            for x in range(width):
                if not wall[y][x] and (x, y) not in keep:
                    m.set_cell(x, y, None, "terrain")
        for y in range(height):
            for x in range(width):
                if m.get("terrain", x, y) == "void" and any(m.get("terrain", x + i, y + j) == "floor"
                                                            for i in (-1, 0, 1) for j in (-1, 0, 1)
                                                            if m.in_bounds(x + i, y + j)):
                    m.set_cell(x, y, "wall")
        return _finish_open_map(m, keep, rng, "cave", seed)
    raise EngineError("Could not generate a cave of useful size", "Lower fill (e.g. 0.40) or use a bigger map", "cave_failed")


def _finish_open_map(m: LayeredMap, keep, rng, gen, seed) -> LayeredMap:
    cells = sorted(keep)
    m.spawn = cells[rng.randrange(len(cells))]
    dist = distance_map(m, m.spawn)
    m.exit = max(sorted(dist), key=lambda c: dist[c])
    _set_stairs(m)
    m.regions[gen] = {"rect": [0, 0, m.width, m.height], "type": "zone", "props": {"lit": False, "biome": gen}}
    m.meta.update({"generator": gen, "seed": seed})
    rep = validate_map(m)
    if not rep["ok"]:
        raise EngineError("Generated map failed validation: " + "; ".join(rep["errors"]), "report this seed", "gen_bug")
    return m


# ---------------------------------------------------------------------------------------------- biomes
def _noise(rng, w, h, scale):
    gw, gh = w // scale + 3, h // scale + 3
    g = [[rng.random() for _ in range(gw)] for _ in range(gh)]
    sm = lambda t: t * t * (3 - 2 * t)
    out = []
    for y in range(h):
        row = []
        for x in range(w):
            fx, fy = x / scale, y / scale
            ix, iy = int(fx), int(fy)
            tx, ty = sm(fx - ix), sm(fy - iy)
            a = g[iy][ix] * (1 - tx) + g[iy][ix + 1] * tx
            b = g[iy + 1][ix] * (1 - tx) + g[iy + 1][ix + 1] * tx
            row.append(a * (1 - ty) + b * ty)
        out.append(row)
    return out


BIOMES = ("forest", "desert", "swamp", "snow", "island")


def biome(kind: str = "forest", width: int = 60, height: int = 30, seed=None, name: Optional[str] = None) -> LayeredMap:
    if kind not in BIOMES:
        raise EngineError(f"Unknown biome '{kind}'", "Biomes: " + ", ".join(BIOMES), "unknown_biome")
    rng = _rng(seed)
    for _try in range(20):
        e1, e2, mo = _noise(rng, width, height, 8), _noise(rng, width, height, 4), _noise(rng, width, height, 6)
        m = LayeredMap(width, height, name=name or kind)
        for y in range(height):
            for x in range(width):
                e = 0.7 * e1[y][x] + 0.3 * e2[y][x]
                q = mo[y][x]
                if kind == "island":
                    dx, dy = (x - width / 2) / (width / 2), (y - height / 2) / (height / 2)
                    e = e * 0.5 + (1 - min(1.0, math.hypot(dx, dy))) * 0.7
                t, s = _biome_cell(kind, e, q, rng)
                m.set_cell(x, y, t)
                if s:
                    m.set_cell(x, y, s)
        comps = components(m)
        if not comps or len(comps[0]) < width * height * 0.15:
            continue
        return _finish_open_map(m, comps[0], rng, kind, seed)
    raise EngineError(f"Could not generate a '{kind}' biome with enough walkable land", "Try another seed or a bigger map", "biome_failed")


def _biome_cell(kind, e, q, rng):
    r = rng.random()
    if kind == "forest":
        if e < 0.30: return "water", None
        if e < 0.36: return "shallow_water", None
        if e < 0.40: return "sand", None
        return "grass", ("tree" if q > 0.45 and r < 0.40 else "rock" if e > 0.8 and r < 0.3 else None)
    if kind == "desert":
        if e < 0.16: return "shallow_water", None
        if e < 0.2: return "grass", None
        return "sand", ("rock" if e > 0.72 and r < 0.35 else None)
    if kind == "swamp":
        if e < 0.30: return "water", None
        if e < 0.5: return "shallow_water", None
        return "mud", ("tree" if r < 0.12 and q > 0.5 else None)
    if kind == "snow":
        if e < 0.22: return "water", None
        return "snow", ("tree" if q > 0.55 and r < 0.25 else "rock" if e > 0.75 and r < 0.3 else None)
    # island
    if e < 0.30: return "water", None
    if e < 0.36: return "shallow_water", None
    if e < 0.42: return "sand", None
    return "grass", ("tree" if q > 0.5 and r < 0.3 else None)


def generate(kind: str, **kw) -> LayeredMap:
    """Single entry point: 'dungeon' | 'cave' | one of BIOMES."""
    if kind == "dungeon":
        return dungeon(**kw)
    if kind == "cave":
        return cave(**kw)
    return biome(kind, **kw)
