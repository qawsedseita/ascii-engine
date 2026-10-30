"""MapEditor: edit a LayeredMap with JSON commands or one-line text commands.

JSON:  {"cmd": "room", "x": 2, "y": 2, "w": 10, "h": 6}
Text:  "room 2 2 10 6"      (positional args per command, plus optional key=value)

``run(commands)`` is ATOMIC: if any command fails, the whole batch is rolled back and the error says which
command failed. One successful batch = one undo step.

Commands (positional order in brackets):
  set [x y kind]            one cell            rect [kind x y w h] filled=true
  line [kind x1 y1 x2 y2]   Bresenham           room [x y w h]  outer rect incl. walls; floor=, wall=, name=, lit=
  corridor [x1 y1 x2 y2]    L-shaped; order=hv|vh; walls crossed become doorways
  door [x y kind]           door_closed (default) | door_open | doorway
  fill [x y kind]           flood-fill a layer region; layer= (inferred from kind)
  replace [from to]         every cell of kind `from` becomes `to`; optionally x y w h
  copy [x y w h tx ty]      all layers + entities;  move: same, clears the source
  remove [x y w h]          clear cells; layer= or kind= to limit
  region [name x y w h]     type=room|biome|zone, biome=, lit=, props via key=value
  spawn [x y] / exit [x y]  exit also places stairs_down; spawn places stairs_up
  collision [x y walkable]  per-cell override (walkable=none removes it)
  place [kind x y]          entity or object by kind; id= props via props={...}
  light [x y radius]        light source
  inspect [x y]             read-only: full stack + walkable/opaque/regions
  validate / stats / undo / redo (read-only except undo/redo)
"""
from __future__ import annotations

import json
import shlex
from typing import Any, Dict, List, Optional, Union

from ..core.errors import EngineError
from .layered import LayeredMap
from .validate import validate_map

SIGNATURES: Dict[str, List[str]] = {
    "set": ["x", "y", "kind"], "rect": ["kind", "x", "y", "w", "h"], "line": ["kind", "x1", "y1", "x2", "y2"],
    "room": ["x", "y", "w", "h"], "corridor": ["x1", "y1", "x2", "y2"], "door": ["x", "y", "kind"],
    "fill": ["x", "y", "kind"], "replace": ["from", "to"], "copy": ["x", "y", "w", "h", "tx", "ty"],
    "move": ["x", "y", "w", "h", "tx", "ty"], "remove": ["x", "y", "w", "h"],
    "region": ["name", "x", "y", "w", "h"], "spawn": ["x", "y"], "exit": ["x", "y"],
    "collision": ["x", "y", "walkable"], "place": ["kind", "x", "y"], "light": ["x", "y", "radius"],
    "inspect": ["x", "y"], "validate": [], "stats": [], "undo": [], "redo": [],
}
READ_ONLY = {"inspect", "validate", "stats", "undo", "redo"}


def _auto(v: str):
    low = v.lower()
    if low in ("true", "yes"): return True
    if low in ("false", "no"): return False
    if low in ("none", "null"): return None
    try: return int(v)
    except ValueError: pass
    try: return float(v)
    except ValueError: pass
    if v[:1] in "[{":
        try: return json.loads(v)
        except ValueError: pass
    return v


def parse_text(line: str) -> dict:
    toks = shlex.split(line.strip())
    if not toks:
        raise EngineError("Empty command", "Example: room 2 2 10 6", "empty_command")
    cmd, args = toks[0].lower(), toks[1:]
    if cmd not in SIGNATURES:
        raise EngineError(f"Unknown command '{cmd}'", "Commands: " + ", ".join(sorted(SIGNATURES)), "unknown_command")
    out: dict = {"cmd": cmd}
    pos = [a for a in args if "=" not in a]
    for name, val in zip(SIGNATURES[cmd], pos):
        out[name] = _auto(val)
    if len(pos) > len(SIGNATURES[cmd]):
        raise EngineError(f"Too many arguments for '{cmd}'", f"Usage: {cmd} " + " ".join(SIGNATURES[cmd]), "bad_args")
    for a in args:
        if "=" in a:
            k, v = a.split("=", 1)
            out[k] = _auto(v)
    return out


class MapEditor:
    def __init__(self, m: LayeredMap):
        self.map = m
        self._undo: List[LayeredMap] = []
        self._redo: List[LayeredMap] = []

    # ------------------------------------------------------------------ public API
    def run(self, commands: Union[str, dict, List[Union[str, dict]]]) -> List[dict]:
        """Run text (one command per line, '#' comments) / a dict / a list. Atomic. Returns one result per command."""
        if isinstance(commands, str):
            commands = [l for l in commands.splitlines() if l.strip() and not l.strip().startswith("#")]
        elif isinstance(commands, dict):
            commands = [commands]
        before = self.map.clone()
        results: List[dict] = []
        mutated = False
        for i, c in enumerate(commands):
            try:
                cmd = parse_text(c) if isinstance(c, str) else dict(c)
                if cmd.get("cmd") in ("undo", "redo"):
                    if i or len(commands) > 1:
                        raise EngineError("undo/redo must be the only command in a batch", "Send it alone", "bad_batch")
                    return [self._undo_redo(cmd["cmd"])]
                res = self._dispatch(cmd)
                mutated = mutated or cmd.get("cmd") not in READ_ONLY
                results.append({"ok": True, "cmd": cmd.get("cmd"), **res})
            except EngineError as e:
                self.map.restore(before)
                return [{"ok": False, "failed_index": i, "failed_command": c, "rolled_back": True, **e.to_dict()}]
        if mutated:
            self._undo.append(before)
            self._redo.clear()
        return results

    def run_one(self, command) -> dict:
        return self.run([command])[0]

    # ------------------------------------------------------------------ dispatch
    def _dispatch(self, c: dict) -> dict:
        name = c.get("cmd")
        fn = getattr(self, f"_cmd_{name}", None)
        if fn is None:
            raise EngineError(f"Unknown command '{name}'", "Commands: " + ", ".join(sorted(SIGNATURES)), "unknown_command")
        optional = {"door": ["kind"], "set": ["kind"], "fill": ["kind"]}    # these have their own checks / defaults
        need = [k for k in SIGNATURES[name] if k not in c and k not in optional.get(name, [])]
        if need:
            raise EngineError(f"'{name}' is missing {', '.join(need)}", f"Usage: {name} " + " ".join(SIGNATURES[name]),
                              "missing_arg")
        return fn(c) or {}

    def _undo_redo(self, which: str) -> dict:
        src, dst = (self._undo, self._redo) if which == "undo" else (self._redo, self._undo)
        if not src:
            return {"ok": False, "cmd": which, "error": f"nothing to {which}", "hint": "", "code": "empty_history"}
        dst.append(self.map.clone())
        self.map.restore(src.pop())
        return {"ok": True, "cmd": which, "undo_depth": len(self._undo), "redo_depth": len(self._redo)}

    # ------------------------------------------------------------------ helpers
    def _int(self, c, *keys):
        out = []
        for k in keys:
            try:
                out.append(int(c[k]))
            except (TypeError, ValueError):
                raise EngineError(f"'{k}' must be an integer, got {c[k]!r}", "Coordinates are integers", "bad_arg")
        return out

    def _rect_cells(self, x, y, w, h):
        if w < 1 or h < 1:
            raise EngineError(f"Rectangle {w}x{h} is empty", "w and h must be >= 1", "bad_rect")
        for j in range(y, y + h):
            for i in range(x, x + w):
                yield i, j

    def _put(self, x, y, kind, layer=None):
        self.map.set_cell(x, y, kind, layer)

    def _kind_layer(self, c):
        kind = c.get("kind")
        return kind, (c.get("layer") or (self.map.layer_for_kind(kind) if kind else None))

    # ------------------------------------------------------------------ commands
    def _cmd_set(self, c):
        x, y = self._int(c, "x", "y")
        kind = c.get("kind")
        if kind is None:
            if not c.get("layer"):
                raise EngineError("'set' needs kind (or layer to clear)", "set 3 4 wall", "missing_arg")
            self._put(x, y, None, c["layer"])
        else:
            self._put(x, y, kind, c.get("layer"))
        return {"changed": 1}

    def _cmd_rect(self, c):
        x, y, w, h = self._int(c, "x", "y", "w", "h")
        filled = c.get("filled", True)
        n = 0
        for i, j in self._rect_cells(x, y, w, h):
            if filled or i in (x, x + w - 1) or j in (y, y + h - 1):
                self._put(i, j, c["kind"], c.get("layer")); n += 1
        return {"changed": n}

    def _cmd_line(self, c):
        x1, y1, x2, y2 = self._int(c, "x1", "y1", "x2", "y2")
        dx, dy = abs(x2 - x1), -abs(y2 - y1)
        sx, sy = (1 if x1 < x2 else -1), (1 if y1 < y2 else -1)
        err, x, y, n = dx + dy, x1, y1, 0
        while True:
            self._put(x, y, c["kind"], c.get("layer")); n += 1
            if (x, y) == (x2, y2): break
            e2 = 2 * err
            if e2 >= dy: err += dy; x += sx
            if e2 <= dx: err += dx; y += sy
        return {"changed": n}

    def _cmd_room(self, c):
        x, y, w, h = self._int(c, "x", "y", "w", "h")
        if w < 3 or h < 3:
            raise EngineError(f"Room {w}x{h} is too small", "w and h are OUTER sizes including walls; minimum 3x3", "bad_rect")
        floor, wall = c.get("floor", "floor"), c.get("wall", "wall")
        for i, j in self._rect_cells(x, y, w, h):
            edge = i in (x, x + w - 1) or j in (y, y + h - 1)
            if edge:
                if self.map.get("terrain", i, j) == "void":
                    self._put(i, j, "floor")             # terrain under the wall, so doors/doorways cut into it work
                self._put(i, j, wall)
            else:
                self._put(i, j, floor)
                self.map.layers["structures"].pop((i, j), None)
        name = c.get("name") or self._free_name("room")
        self.map.regions[name] = {"rect": [x, y, w, h], "type": "room", "props": {"lit": bool(c.get("lit", False))}}
        return {"changed": w * h, "region": name, "interior": [x + 1, y + 1, w - 2, h - 2]}

    def _free_name(self, base):
        n = 1
        while f"{base}_{n}" in self.map.regions:
            n += 1
        return f"{base}_{n}"

    def _cmd_corridor(self, c):
        x1, y1, x2, y2 = self._int(c, "x1", "y1", "x2", "y2")
        order = c.get("order", "hv")
        if order not in ("hv", "vh"):
            raise EngineError(f"order must be 'hv' or 'vh', got {order!r}", "", "bad_arg")
        pts = []
        step = lambda a, b: 1 if b >= a else -1
        if order == "hv":
            pts += [(x, y1) for x in range(x1, x2 + step(x1, x2), step(x1, x2))]
            pts += [(x2, y) for y in range(y1 + step(y1, y2), y2 + step(y1, y2), step(y1, y2))] if y1 != y2 else []
        else:
            pts += [(x1, y) for y in range(y1, y2 + step(y1, y2), step(y1, y2))]
            pts += [(x, y2) for x in range(x1 + step(x1, x2), x2 + step(x1, x2), step(x1, x2))] if x1 != x2 else []
        doorways = 0
        for x, y in pts:
            s = self.map.layers["structures"].get((x, y))
            if s == "wall":
                self._put(x, y, "doorway"); self._put(x, y, "floor"); doorways += 1
            elif s is None and self.map.get("terrain", x, y) in ("void",):
                self._put(x, y, c.get("kind", "corridor"))
        return {"changed": len(pts), "doorways_created": doorways}

    def _cmd_door(self, c):
        x, y = self._int(c, "x", "y")
        kind = c.get("kind", "door_closed")
        if kind not in ("door_closed", "door_open", "doorway"):
            raise EngineError(f"'{kind}' is not a door kind", "Use door_closed, door_open or doorway", "bad_kind")
        if self.map.get("terrain", x, y) == "void":
            self._put(x, y, "floor")
        self._put(x, y, kind)
        return {"changed": 1}

    def _cmd_fill(self, c):
        x, y = self._int(c, "x", "y")
        kind, layer = c.get("kind"), c.get("layer")
        if kind is None:
            raise EngineError("'fill' needs kind", "fill 5 5 grass", "missing_arg")
        layer = layer or self.map.layer_for_kind(kind)
        if layer == "entities":
            raise EngineError("cannot fill entities", "Use place", "is_entity")
        self.map._check(x, y)
        target = self.map.get(layer, x, y)
        if target == kind:
            return {"changed": 0}
        stack, seen, n = [(x, y)], set(), 0
        while stack:
            i, j = stack.pop()
            if (i, j) in seen or not self.map.in_bounds(i, j) or self.map.get(layer, i, j) != target:
                continue
            seen.add((i, j)); self._put(i, j, kind, layer); n += 1
            stack += [(i + 1, j), (i - 1, j), (i, j + 1), (i, j - 1)]
        return {"changed": n}

    def _cmd_replace(self, c):
        src, dst = c["from"], c["to"]
        ls, ld = self.map.layer_for_kind(src), self.map.layer_for_kind(dst)
        if ls != ld:
            raise EngineError(f"Cannot replace '{src}' ({ls}) with '{dst}' ({ld})", "Both kinds must be on the same layer", "layer_mismatch")
        if ls == "entities":
            n = 0
            for e in self.map.entities:
                if e["kind"] == src and self._in_area(c, e["x"], e["y"]):
                    e["kind"] = dst; n += 1
            return {"changed": n}
        n = 0
        for (x, y), k in list(self.map.layers[ls].items()) if ls != "terrain" else \
                [((x, y), self.map.get("terrain", x, y)) for x, y in self.map.cells()]:
            if k == src and self._in_area(c, x, y):
                self._put(x, y, dst, ls); n += 1
        return {"changed": n}

    def _in_area(self, c, x, y):
        if "w" in c and "h" in c and "x" in c and "y" in c:
            return c["x"] <= x < c["x"] + c["w"] and c["y"] <= y < c["y"] + c["h"]
        return True

    def _copy_move(self, c, move):
        x, y, w, h, tx, ty = self._int(c, "x", "y", "w", "h", "tx", "ty")
        for i, j in ((x, y), (x + w - 1, y + h - 1), (tx, ty), (tx + w - 1, ty + h - 1)):
            self.map._check(i, j)
        snap = {}
        for i, j in self._rect_cells(x, y, w, h):
            snap[(i, j)] = ({l: self.map.layers[l].get((i, j)) for l in ("terrain", "structures", "objects", "effects")},
                            [dict(e) for e in self.map.entities_at(i, j)])
        if move:
            for (i, j) in snap:
                for l in ("terrain", "structures", "objects", "effects"):
                    self.map.layers[l].pop((i, j), None)
            moving = {e["id"] for _, es in snap.values() for e in es}
            self.map.entities = [e for e in self.map.entities if e["id"] not in moving]
        for (i, j), (layers, ents) in snap.items():
            ni, nj = i - x + tx, j - y + ty
            for l, k in layers.items():
                if k is not None:
                    self.map.layers[l][(ni, nj)] = k
                else:
                    self.map.layers[l].pop((ni, nj), None)
            for e in ents:
                eid = e["id"] if move else None
                self.map.add_entity(e["kind"], ni, nj, eid, e.get("props"))
        return {"changed": len(snap)}

    def _cmd_copy(self, c): return self._copy_move(c, False)
    def _cmd_move(self, c): return self._copy_move(c, True)

    def _cmd_remove(self, c):
        x, y, w, h = self._int(c, "x", "y", "w", "h")
        layer, kind, n = c.get("layer"), c.get("kind"), 0
        for i, j in self._rect_cells(x, y, w, h):
            if not self.map.in_bounds(i, j):
                raise EngineError(f"({i},{j}) is outside the map", "", "out_of_bounds")
            for l in ("terrain", "structures", "objects", "effects"):
                if layer and layer != l: continue
                cur = self.map.layers[l].get((i, j))
                if cur is not None and (kind is None or cur == kind):
                    del self.map.layers[l][(i, j)]; n += 1
            if layer in (None, "entities"):
                for e in self.map.entities_at(i, j):
                    if kind is None or e["kind"] == kind:
                        self.map.remove_entity(e["id"]); n += 1
        return {"changed": n}

    def _cmd_region(self, c):
        x, y, w, h = self._int(c, "x", "y", "w", "h")
        self.map._check(x, y); self.map._check(x + w - 1, y + h - 1)
        reserved = {"cmd", "name", "x", "y", "w", "h", "type", "props"}
        props = dict(c.get("props") or {})
        props.update({k: v for k, v in c.items() if k not in reserved})
        self.map.regions[str(c["name"])] = {"rect": [x, y, w, h], "type": c.get("type", "zone"), "props": props}
        return {"region": c["name"]}

    def _cmd_spawn(self, c):
        x, y = self._int(c, "x", "y")
        if not self.map.walkable(x, y, True):
            raise EngineError(f"({x},{y}) is not walkable, cannot be a spawn", "Pick a floor cell (try 'inspect')", "bad_spawn")
        if self.map.spawn:
            if self.map.layers["structures"].get(self.map.spawn) == "stairs_up":
                del self.map.layers["structures"][self.map.spawn]
        self.map.spawn = (x, y)
        self._put(x, y, "stairs_up")
        return {"spawn": [x, y]}

    def _cmd_exit(self, c):
        x, y = self._int(c, "x", "y")
        if not self.map.walkable(x, y, True):
            raise EngineError(f"({x},{y}) is not walkable, cannot be an exit", "Pick a floor cell", "bad_exit")
        if self.map.exit and self.map.layers["structures"].get(self.map.exit) == "stairs_down":
            del self.map.layers["structures"][self.map.exit]
        self.map.exit = (x, y)
        self._put(x, y, "stairs_down")
        return {"exit": [x, y]}

    def _cmd_collision(self, c):
        x, y = self._int(c, "x", "y")
        self.map._check(x, y)
        v = c["walkable"]
        if v is None:
            self.map.collision.pop((x, y), None)
        else:
            self.map.collision[(x, y)] = bool(v)
        return {"override": v}

    def _cmd_place(self, c):
        x, y = self._int(c, "x", "y")
        layer = self.map.layer_for_kind(c["kind"])
        if layer == "entities":
            e = self.map.add_entity(c["kind"], x, y, c.get("id"), c.get("props"))
            return {"entity": e["id"]}
        self._put(x, y, c["kind"])
        return {"changed": 1}

    def _cmd_light(self, c):
        x, y, r = self._int(c, "x", "y", "radius")
        self.map._check(x, y)
        self.map.lights.append({"x": x, "y": y, "radius": r})
        return {"lights": len(self.map.lights)}

    def _cmd_inspect(self, c):
        x, y = self._int(c, "x", "y")
        return {"x": x, "y": y, "stack": self.map.stack(x, y), "walkable": self.map.walkable(x, y),
                "walkable_if_doors_open": self.map.walkable(x, y, True), "blocks_sight": self.map.blocks_sight(x, y),
                "regions": self.map.region_at(x, y), "collision_override": self.map.collision.get((x, y))}

    def _cmd_validate(self, c): return validate_map(self.map)

    def _cmd_stats(self, c): return validate_map(self.map)["stats"]
