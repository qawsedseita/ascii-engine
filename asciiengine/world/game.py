"""Small turn-based world runtime built on semantic LayeredMap kinds."""
from __future__ import annotations
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from ..core.errors import EngineError
from ..maps.layered import LayeredMap


@dataclass
class Entity:
    id: str
    kind: str
    x: int
    y: int
    hp: int = 10
    max_hp: int = 10
    attack: int = 2
    defense: int = 0
    faction: str = "neutral"
    inventory: list[str] = field(default_factory=list)
    equipped: dict[str, str] = field(default_factory=dict)
    alive: bool = True
    props: dict = field(default_factory=dict)

    def to_dict(self):
        return {"id": self.id, "kind": self.kind, "x": self.x, "y": self.y,
                "hp": self.hp, "max_hp": self.max_hp, "attack": self.attack,
                "defense": self.defense, "faction": self.faction,
                "inventory": list(self.inventory), "equipped": dict(self.equipped),
                "alive": self.alive, "props": dict(self.props)}

    @classmethod
    def from_map_entity(cls, row):
        p = dict(row.get("props", {}))
        return cls(row["id"], row["kind"], row["x"], row["y"], int(p.get("hp", 10)), int(p.get("max_hp", p.get("hp", 10))),
                   int(p.get("attack", 2)), int(p.get("defense", 0)), p.get("faction", "neutral"),
                   list(p.get("inventory", [])), dict(p.get("equipped", {})), bool(p.get("alive", True)), p)


class GameWorld:
    """Deterministic turn-based rules. Actions are semantic and glyph-independent."""
    def __init__(self, game_map: LayeredMap, *, player_id: Optional[str] = None):
        self.map = game_map
        self.entities = {e["id"]: Entity.from_map_entity(e) for e in game_map.entities}
        self.turn = 0
        self.log: list[dict] = []
        self.player_id = player_id or next((e.id for e in self.entities.values() if e.kind == "player"), None)
        self._sync_map()

    def entity(self, entity_id: str) -> Entity:
        try: return self.entities[entity_id]
        except KeyError: raise EngineError(f"Unknown entity '{entity_id}'", "Use an id in this world's entity list", "unknown_entity")

    def living_at(self, x, y, except_id=None):
        return next((e for e in self.entities.values() if e.alive and e.id != except_id and (e.x, e.y) == (x, y)), None)

    def _sync_map(self):
        rows = []
        for e in self.entities.values():
            p = dict(e.props); p.update({"hp": e.hp, "max_hp": e.max_hp, "attack": e.attack, "defense": e.defense,
                                         "faction": e.faction, "inventory": e.inventory, "equipped": e.equipped, "alive": e.alive})
            rows.append({"id": e.id, "kind": e.kind, "x": e.x, "y": e.y, "props": p})
        self.map.entities = rows

    def _record(self, event, **data):
        row = {"turn": self.turn, "event": event, **data}; self.log.append(row); return row

    def move(self, entity_id: str, dx: int, dy: int):
        if (dx, dy) not in {(0, -1), (1, 0), (0, 1), (-1, 0)}:
            raise EngineError("Movement must be one orthogonal tile", "Use dx,dy as one of (0,-1),(1,0),(0,1),(-1,0)", "bad_move")
        e = self.entity(entity_id)
        if not e.alive: return {"ok": False, **self._record("blocked", entity=entity_id, reason="dead")}
        x, y = e.x + dx, e.y + dy
        if not self.map.walkable(x, y): return {"ok": False, **self._record("blocked", entity=entity_id, reason="terrain")}
        target = self.living_at(x, y, e.id)
        if target:
            if e.faction != target.faction:
                return self.attack(entity_id, target.id)
            return {"ok": False, **self._record("blocked", entity=entity_id, reason="occupied")}
        e.x, e.y = x, y; self.turn += 1; self._record("move", entity=entity_id, x=x, y=y); self._sync_map()
        return {"ok": True, "x": x, "y": y}

    def attack(self, attacker_id: str, target_id: str, *, power: Optional[int] = None):
        a, t = self.entity(attacker_id), self.entity(target_id)
        if not a.alive or not t.alive: return self._record("miss", attacker=attacker_id, target=target_id, reason="dead")
        if abs(a.x-t.x) + abs(a.y-t.y) != 1:
            raise EngineError("Target is not adjacent", "Attack requires Manhattan distance 1", "out_of_range")
        raw = a.attack if power is None else max(0, int(power))
        damage = max(1, raw - t.defense)
        t.hp = max(0, t.hp - damage); t.alive = t.hp > 0
        self.turn += 1; result = self._record("attack", attacker=attacker_id, target=target_id, damage=damage, hp=t.hp, killed=not t.alive)
        self._sync_map(); return {"ok": True, **result}

    def pickup(self, entity_id: str, item_kind: Optional[str] = None):
        e = self.entity(entity_id)
        item = self.map.layers["objects"].get((e.x, e.y))
        if not item or (item_kind and item != item_kind):
            raise EngineError("No matching item here", "Move onto an object tile or specify the kind present", "no_item")
        e.inventory.append(item); self.map.layers["objects"].pop((e.x, e.y), None)
        self.turn += 1; self._record("pickup", entity=entity_id, item=item); self._sync_map()
        return {"ok": True, "item": item}

    def equip(self, entity_id: str, item_kind: str, slot: str = "weapon"):
        e = self.entity(entity_id)
        if item_kind not in e.inventory: raise EngineError(f"'{item_kind}' is not in inventory", "Pick up the item first", "missing_item")
        e.equipped[slot] = item_kind
        bonus = int(self.map.kinds.get(item_kind).props.get("attack_bonus", 0)) if self.map.kinds.has(item_kind) else 0
        if slot == "weapon": e.attack = max(e.attack, 2 + bonus)
        self.turn += 1; self._record("equip", entity=entity_id, item=item_kind, slot=slot); self._sync_map()
        return {"ok": True, "slot": slot, "item": item_kind}

    def push(self, entity_id: str, dx: int, dy: int):
        """Simple grid knockback: move one tile if terrain and occupancy allow."""
        e = self.entity(entity_id); x, y = e.x + dx, e.y + dy
        if not self.map.walkable(x, y) or self.living_at(x, y, e.id): return False
        e.x, e.y = x, y; self._sync_map(); return True

    def npc_turn(self, entity_id: str, target_id: Optional[str] = None):
        """Basic hostile AI: attack adjacent player, otherwise step toward it using A* first step."""
        from ..maps.pathing import astar
        npc = self.entity(entity_id)
        target = self.entity(target_id or self.player_id) if (target_id or self.player_id) else None
        if not npc.alive or target is None or not target.alive or npc.faction == target.faction:
            return {"ok": True, "acted": False}
        if abs(npc.x-target.x)+abs(npc.y-target.y) == 1:
            return self.attack(npc.id, target.id)
        path = astar(self.map, (npc.x, npc.y), (target.x, target.y), diag=False)
        if len(path) > 1:
            dx, dy = path[1][0]-npc.x, path[1][1]-npc.y
            npc.x, npc.y = path[1]; self.turn += 1; self._record("npc_move", entity=npc.id, x=npc.x, y=npc.y); self._sync_map()
            return {"ok": True, "acted": True, "x": npc.x, "y": npc.y}
        return {"ok": True, "acted": False}

    def step(self, entity_id: str, dx: int = 0, dy: int = 0, *, npc_ai: bool = True):
        if dx or dy:
            result = self.move(entity_id, dx, dy)
        else:
            self.turn += 1; self._record("wait", entity=entity_id); result = {"ok": True, "wait": True}
        if result.get("ok") and npc_ai:
            for enemy in list(self.entities.values()):
                if enemy.alive and enemy.id != entity_id and enemy.faction not in ("neutral", self.entity(entity_id).faction):
                    self.npc_turn(enemy.id, entity_id)
        return result

    def camera(self, entity_id: str, width: int, height: int):
        """Return a clamped viewport centered as closely as possible on an entity."""
        e = self.entity(entity_id); width = min(width, self.map.width); height = min(height, self.map.height)
        x = min(max(0, e.x-width//2), self.map.width-width); y = min(max(0, e.y-height//2), self.map.height-height)
        return (x, y, width, height)

    def to_dict(self):
        self._sync_map()
        return {"version": 1, "turn": self.turn, "player_id": self.player_id, "map": self.map.to_dict(), "log": self.log}

    def save(self, path):
        Path(path).write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

    @classmethod
    def from_dict(cls, data, kinds=None):
        if data.get("version") != 1: raise EngineError("Unsupported save version", "Use a save created by this engine version", "bad_save")
        world = cls(LayeredMap.from_dict(data["map"], kinds), player_id=data.get("player_id"))
        world.turn = int(data.get("turn", 0)); world.log = list(data.get("log", [])); return world

    @classmethod
    def load(cls, path, kinds=None):
        try: return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")), kinds)
        except (OSError, json.JSONDecodeError, KeyError) as exc:
            raise EngineError(f"Could not load world save: {exc}", "Check that the file is valid engine JSON", "bad_save") from exc
