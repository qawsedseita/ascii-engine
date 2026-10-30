"""Semantic kinds.

Game logic NEVER depends on glyphs. Every tile/object/entity is a *kind* (``"wall"``,
``"orc"``) with gameplay properties. Styles map kinds -> glyphs. This separation is what
lets the style converter restyle a whole game without touching collisions or positions.
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Dict, Optional

# Layers, bottom to top. Rendering composites them in this order.
LAYERS = ["terrain", "structures", "objects", "entities", "lighting", "effects"]
# Style categories (what the style translator can target).
CATEGORIES = ["terrain", "structures", "objects", "entities", "ui", "effects"]


@dataclass
class KindDef:
    name: str
    category: str              # one of CATEGORIES
    walkable: bool = True
    opaque: bool = False       # blocks line of sight
    description: str = ""
    props: dict = field(default_factory=dict)

    def to_dict(self):
        return asdict(self)


class KindRegistry:
    def __init__(self):
        self._kinds: Dict[str, KindDef] = {}

    def register(self, kind: KindDef, overwrite: bool = True):
        if kind.category not in CATEGORIES:
            from .errors import EngineError
            raise EngineError(f"Unknown category '{kind.category}' for kind '{kind.name}'",
                              f"Use one of {CATEGORIES}", "bad_category")
        if not overwrite and kind.name in self._kinds:
            return
        self._kinds[kind.name] = kind

    def get(self, name: str) -> KindDef:
        try:
            return self._kinds[name]
        except KeyError:
            from .errors import EngineError
            raise EngineError(f"Unknown kind '{name}'",
                              "Register it with KindRegistry.register(KindDef(...)) or pick one of: "
                              + ", ".join(sorted(self._kinds)), "unknown_kind")

    def has(self, name: str) -> bool:
        return name in self._kinds

    def names(self, category: Optional[str] = None):
        return sorted(k for k, v in self._kinds.items() if category in (None, v.category))

    def category_of(self, name: str) -> str:
        return self._kinds[name].category if name in self._kinds else "objects"

    def all(self):
        return dict(self._kinds)


def default_kinds() -> KindRegistry:
    r = KindRegistry()
    T, S, O, E, F = "terrain", "structures", "objects", "entities", "effects"
    for n, w, o, d in [
        ("void", False, True, "solid rock / nothing"),
        ("floor", True, False, "room floor"),
        ("corridor", True, False, "corridor floor"),
        ("grass", True, False, "grass"),
        ("sand", True, False, "sand"),
        ("water", False, False, "deep water (blocks walking, not sight)"),
        ("shallow_water", True, False, "wading water"),
        ("lava", False, False, "lava"),
        ("snow", True, False, "snow"),
        ("mud", True, False, "mud / swamp"),
        ("road", True, False, "road"),
    ]:
        r.register(KindDef(n, T, w, o, d))
    for n, w, o, d in [
        ("wall", False, True, "solid wall"),
        ("door_closed", False, True, "closed door"),
        ("door_open", True, False, "open door"),
        ("doorway", True, False, "empty doorway"),
        ("stairs_down", True, False, "stairs down / exit"),
        ("stairs_up", True, False, "stairs up / entrance"),
        ("tree", False, True, "tree"),
        ("rock", False, True, "boulder"),
        ("pillar", False, False, "pillar (blocks walking only)"),
        ("window", False, False, "window (blocks walking, not sight)"),
        ("fence", False, False, "fence"),
    ]:
        r.register(KindDef(n, S, w, o, d))
    for n, w, d in [
        ("chest", False, "treasure chest"), ("torch", True, "wall torch / light source"),
        ("gold", True, "gold coins"), ("potion", True, "potion"), ("weapon", True, "weapon item"),
        ("armor", True, "armor item"), ("scroll", True, "scroll"), ("key", True, "key"),
        ("altar", False, "altar"), ("fountain", False, "fountain"), ("trap", True, "trap"),
        ("table", False, "table"), ("bed", True, "bed"), ("food", True, "food"),
    ]:
        r.register(KindDef(n, O, w, False, d))
    for n, d in [
        ("player", "the player"), ("npc", "friendly character"), ("rat", "small vermin"),
        ("goblin", "goblin"), ("orc", "orc"), ("skeleton", "skeleton"), ("slime", "slime"),
        ("bat", "bat"), ("dragon", "dragon"), ("wolf", "wolf"), ("ghost", "ghost"),
        ("creature", "generic creature (default for custom sprites)"),
    ]:
        r.register(KindDef(n, E, False, False, d))
    for n, d in [("spark", "spark"), ("smoke", "smoke"), ("fire", "fire"), ("blood", "blood splat"),
                 ("magic", "magic glow"), ("rain", "rain drop"), ("slash", "melee slash")]:
        r.register(KindDef(n, F, True, False, d))
    for n, d in [("ui_hline", "horizontal border"), ("ui_vline", "vertical border"),
                 ("ui_corner_tl", "corner top-left"), ("ui_corner_tr", "corner top-right"),
                 ("ui_corner_bl", "corner bottom-left"), ("ui_corner_br", "corner bottom-right"),
                 ("ui_bar_full", "filled bar cell"), ("ui_bar_empty", "empty bar cell"),
                 ("ui_cursor", "menu cursor")]:
        r.register(KindDef(n, "ui", True, False, d))
    return r
