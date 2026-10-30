"""LayeredMap: the logical map. Stores KINDS only (never glyphs).

Layers: terrain, structures, objects (sparse grids), entities (list), effects (sparse grid) and lighting
(light sources + lit regions, computed in ``fov.py``). Appearance lives in styles, so restyling a map can
never change walkability, sight lines or positions.

Collision: a cell is walkable when its terrain, structure and object are all walkable. ``collision``
holds explicit per-cell overrides (True/False) that win over the kinds. Entities are NOT part of static
walkability (the game loop handles who stands where).
"""
from __future__ import annotations

import copy
import json
from typing import Dict, List, Optional, Tuple

from ..core.errors import EngineError
from ..core.kinds import KindRegistry, default_kinds

Pos = Tuple[int, int]
GRID_LAYERS = ("terrain", "structures", "objects", "effects")
CATEGORY_TO_LAYER = {"terrain": "terrain", "structures": "structures", "objects": "objects",
                     "entities": "entities", "effects": "effects"}
DOOR_CLOSED = "door_closed"


class LayeredMap:
    def __init__(self, width: int, height: int, kinds: Optional[KindRegistry] = None, name: str = "map"):
        if width < 3 or height < 3:
            raise EngineError(f"Map too small: {width}x{height}", "Minimum size is 3x3", "bad_size")
        self.width, self.height, self.name = width, height, name
        self.kinds = kinds or default_kinds()
        self.layers: Dict[str, Dict[Pos, str]] = {l: {} for l in GRID_LAYERS}
        self.entities: List[dict] = []
        self.lights: List[dict] = []                 # {"x","y","radius"}
        self.regions: Dict[str, dict] = {}           # name -> {"rect":[x,y,w,h],"type":str,"props":{}}
        self.collision: Dict[Pos, bool] = {}
        self.spawn: Optional[Pos] = None
        self.exit: Optional[Pos] = None
        self.meta: dict = {}

    # ------------------------------------------------------------------ basics
    def in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < self.width and 0 <= y < self.height

    def _check(self, x, y):
        if not self.in_bounds(x, y):
            raise EngineError(f"({x},{y}) is outside the {self.width}x{self.height} map",
                              f"x must be 0..{self.width - 1}, y must be 0..{self.height - 1}", "out_of_bounds")

    def layer_for_kind(self, kind: str) -> str:
        cat = self.kinds.get(kind).category
        if cat not in CATEGORY_TO_LAYER:
            raise EngineError(f"Kind '{kind}' (category '{cat}') cannot be placed on a map",
                              "UI kinds belong to the UI layer, not to maps", "bad_layer")
        return CATEGORY_TO_LAYER[cat]

    # ------------------------------------------------------------------ cells
    def set_cell(self, x: int, y: int, kind: Optional[str], layer: Optional[str] = None):
        """Set (or clear with kind=None) one cell. Layer is inferred from the kind's category."""
        self._check(x, y)
        if kind is None:
            if layer is None:
                raise EngineError("clearing a cell needs a layer", "Pass layer='structures' etc.", "missing_layer")
            self.layers[layer].pop((x, y), None)
            return
        inferred = self.layer_for_kind(kind)
        if layer is not None and layer != inferred:
            raise EngineError(f"Kind '{kind}' belongs to layer '{inferred}', not '{layer}'",
                              f"Use layer='{inferred}' or omit layer", "layer_mismatch")
        if inferred == "entities":
            raise EngineError(f"'{kind}' is an entity", "Use add_entity()/the 'place' command", "is_entity")
        if inferred == "terrain" and kind == "void":
            self.layers["terrain"].pop((x, y), None)
        else:
            self.layers[inferred][(x, y)] = kind

    def get(self, layer: str, x: int, y: int) -> Optional[str]:
        if layer == "terrain":
            return self.layers["terrain"].get((x, y), "void")
        return self.layers[layer].get((x, y))

    def stack(self, x: int, y: int) -> dict:
        self._check(x, y)
        out = {"terrain": self.get("terrain", x, y)}
        for l in ("structures", "objects", "effects"):
            k = self.layers[l].get((x, y))
            if k:
                out[l] = k
        ents = [e["kind"] for e in self.entities_at(x, y)]
        if ents:
            out["entities"] = ents
        return out

    # ------------------------------------------------------------------ entities
    def add_entity(self, kind: str, x: int, y: int, id: Optional[str] = None, props: Optional[dict] = None) -> dict:
        self._check(x, y)
        if self.layer_for_kind(kind) != "entities":
            raise EngineError(f"'{kind}' is not an entity kind", "Entity kinds: " + ", ".join(self.kinds.names("entities")),
                              "not_entity")
        used = {e["id"] for e in self.entities}
        if id is None:
            n = 1
            while f"{kind}_{n}" in used:
                n += 1
            id = f"{kind}_{n}"
        elif id in used:
            raise EngineError(f"Entity id '{id}' already exists", "Ids must be unique", "duplicate_id")
        e = {"id": id, "kind": kind, "x": x, "y": y, "props": dict(props or {})}
        self.entities.append(e)
        return e

    def entities_at(self, x: int, y: int) -> List[dict]:
        return [e for e in self.entities if e["x"] == x and e["y"] == y]

    def remove_entity(self, id: str) -> bool:
        n = len(self.entities)
        self.entities = [e for e in self.entities if e["id"] != id]
        return len(self.entities) != n

    # ------------------------------------------------------------------ logic queries
    def walkable(self, x: int, y: int, doors_open: bool = False) -> bool:
        """Static walkability. ``doors_open=True`` treats closed doors as passable (they can be opened)."""
        if not self.in_bounds(x, y):
            return False
        if (x, y) in self.collision:
            return self.collision[(x, y)]
        if not self.kinds.get(self.get("terrain", x, y)).walkable:
            return False
        s = self.layers["structures"].get((x, y))
        if s is not None and not self.kinds.get(s).walkable and not (doors_open and s == DOOR_CLOSED):
            return False
        o = self.layers["objects"].get((x, y))
        if o is not None and not self.kinds.get(o).walkable:
            return False
        return True

    def blocks_sight(self, x: int, y: int) -> bool:
        if not self.in_bounds(x, y):
            return True
        for layer in ("terrain", "structures", "objects"):
            k = self.get(layer, x, y)
            if k is not None and self.kinds.get(k).opaque:
                return True
        return False

    def region_at(self, x: int, y: int) -> List[str]:
        return [n for n, r in self.regions.items()
                if r["rect"][0] <= x < r["rect"][0] + r["rect"][2] and r["rect"][1] <= y < r["rect"][1] + r["rect"][3]]

    def cells(self):
        for y in range(self.height):
            for x in range(self.width):
                yield x, y

    # ------------------------------------------------------------------ copy / serialization
    def clone(self) -> "LayeredMap":
        c = LayeredMap.__new__(LayeredMap)
        c.__dict__ = {k: (v if k == "kinds" else copy.deepcopy(v)) for k, v in self.__dict__.items()}
        return c

    def restore(self, other: "LayeredMap"):
        for k, v in other.__dict__.items():
            if k != "kinds":
                self.__dict__[k] = copy.deepcopy(v)

    def to_dict(self) -> dict:
        return {"name": self.name, "width": self.width, "height": self.height,
                "layers": {l: {f"{x},{y}": k for (x, y), k in sorted(g.items())} for l, g in self.layers.items()},
                "entities": copy.deepcopy(self.entities), "lights": copy.deepcopy(self.lights),
                "regions": copy.deepcopy(self.regions),
                "collision": {f"{x},{y}": v for (x, y), v in sorted(self.collision.items())},
                "spawn": list(self.spawn) if self.spawn else None, "exit": list(self.exit) if self.exit else None,
                "meta": copy.deepcopy(self.meta)}

    @staticmethod
    def from_dict(d: dict, kinds: Optional[KindRegistry] = None) -> "LayeredMap":
        try:
            m = LayeredMap(d["width"], d["height"], kinds, d.get("name", "map"))
            for layer, cells in d.get("layers", {}).items():
                if layer not in m.layers:
                    raise EngineError(f"Unknown layer '{layer}'", f"Layers: {list(GRID_LAYERS)}", "bad_layer")
                for key, kind in cells.items():
                    x, y = (int(v) for v in key.split(","))
                    m.set_cell(x, y, kind, layer)
            for e in d.get("entities", []):
                m.add_entity(e["kind"], e["x"], e["y"], e.get("id"), e.get("props"))
            m.lights = copy.deepcopy(d.get("lights", []))
            m.regions = copy.deepcopy(d.get("regions", {}))
            for key, v in d.get("collision", {}).items():
                x, y = (int(c) for c in key.split(","))
                m.collision[(x, y)] = bool(v)
            m.spawn = tuple(d["spawn"]) if d.get("spawn") else None
            m.exit = tuple(d["exit"]) if d.get("exit") else None
            m.meta = copy.deepcopy(d.get("meta", {}))
            return m
        except KeyError as e:
            raise EngineError(f"Map JSON is missing field {e}", "Needs 'width' and 'height'", "bad_map")

    def save(self, path: str):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=1)

    @staticmethod
    def load(path: str, kinds: Optional[KindRegistry] = None) -> "LayeredMap":
        with open(path, encoding="utf-8") as f:
            return LayeredMap.from_dict(json.load(f), kinds)

    def logic_signature(self) -> dict:
        """Everything gameplay depends on (no appearance). Used to prove restyling changes nothing."""
        return {"walk": [[self.walkable(x, y) for x in range(self.width)] for y in range(self.height)],
                "sight": [[self.blocks_sight(x, y) for x in range(self.width)] for y in range(self.height)],
                "entities": sorted((e["id"], e["kind"], e["x"], e["y"]) for e in self.entities),
                "spawn": self.spawn, "exit": self.exit}
