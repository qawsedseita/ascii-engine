"""Turn-stepped visual effects. Effect state is semantic kinds, never glyphs."""
from dataclasses import dataclass
from ..core.errors import EngineError

@dataclass
class Particle:
    kind: str
    x: int
    y: int
    ttl: int = 1

class EffectSystem:
    def __init__(self): self.particles: list[Particle] = []
    def emit(self, game_map, kind: str, x: int, y: int, ttl: int = 1):
        if ttl < 1: raise EngineError("Effect ttl must be positive", "Use at least one tick", "bad_ttl")
        if game_map.kinds.get(kind).category != "effects": raise EngineError(f"'{kind}' is not an effect kind", "Register/use a kind in the effects category", "bad_effect")
        game_map._check(x, y); self.particles.append(Particle(kind, x, y, ttl)); self._apply(game_map)
    def _apply(self, game_map):
        game_map.layers["effects"].clear()
        for p in self.particles: game_map.layers["effects"][(p.x,p.y)] = p.kind
    def tick(self, game_map):
        self.particles = [Particle(p.kind,p.x,p.y,p.ttl-1) for p in self.particles if p.ttl > 1]
        self._apply(game_map); return len(self.particles)
    def clear(self, game_map): self.particles.clear(); game_map.layers["effects"].clear()

@dataclass
class Animation:
    """A sequence of semantic effect kinds at a fixed cell."""
    frames: list[str]
    x: int
    y: int
    frame: int = 0
    def advance(self):
        if self.frame < len(self.frames): self.frame += 1
        return self.frame < len(self.frames)
    @property
    def kind(self): return self.frames[self.frame] if self.frame < len(self.frames) else None
