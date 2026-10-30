"""Pathfinding and connectivity on static map walkability (4- or 8-directional)."""
from __future__ import annotations

import heapq
from collections import deque
from typing import Dict, Iterable, List, Optional, Set, Tuple

from .layered import LayeredMap, Pos

DIRS4 = [(1, 0), (-1, 0), (0, 1), (0, -1)]
DIRS8 = DIRS4 + [(1, 1), (1, -1), (-1, 1), (-1, -1)]


def neighbors(m: LayeredMap, x: int, y: int, diag: bool = False, doors_open: bool = True,
              blocked: Optional[Set[Pos]] = None) -> Iterable[Pos]:
    for dx, dy in (DIRS8 if diag else DIRS4):
        nx, ny = x + dx, y + dy
        if not m.walkable(nx, ny, doors_open) or (blocked and (nx, ny) in blocked):
            continue
        if dx and dy and not (m.walkable(x + dx, y, doors_open) and m.walkable(x, y + dy, doors_open)):
            continue                                   # no cutting corners
        yield nx, ny


def astar(m: LayeredMap, start: Pos, goal: Pos, diag: bool = False, doors_open: bool = True,
          blocked: Optional[Set[Pos]] = None) -> Optional[List[Pos]]:
    """Shortest path start->goal inclusive, or None. Every step costs 1."""
    if not m.walkable(*start, doors_open) or not m.walkable(*goal, doors_open):
        return None
    h = (lambda a: max(abs(a[0] - goal[0]), abs(a[1] - goal[1]))) if diag else \
        (lambda a: abs(a[0] - goal[0]) + abs(a[1] - goal[1]))
    openq = [(h(start), 0, start)]
    g: Dict[Pos, int] = {start: 0}
    came: Dict[Pos, Pos] = {}
    while openq:
        _, cost, cur = heapq.heappop(openq)
        if cur == goal:
            path = [cur]
            while cur in came:
                cur = came[cur]
                path.append(cur)
            return path[::-1]
        if cost > g.get(cur, 1 << 30):
            continue
        for n in neighbors(m, cur[0], cur[1], diag, doors_open, blocked):
            nc = cost + 1
            if nc < g.get(n, 1 << 30):
                g[n], came[n] = nc, cur
                heapq.heappush(openq, (nc + h(n), nc, n))
    return None


def distance_map(m: LayeredMap, start: Pos, diag: bool = False, doors_open: bool = True) -> Dict[Pos, int]:
    if not m.walkable(*start, doors_open):
        return {}
    dist = {start: 0}
    q = deque([start])
    while q:
        c = q.popleft()
        for n in neighbors(m, c[0], c[1], diag, doors_open):
            if n not in dist:
                dist[n] = dist[c] + 1
                q.append(n)
    return dist


def reachable(m: LayeredMap, start: Pos, diag: bool = False, doors_open: bool = True) -> Set[Pos]:
    return set(distance_map(m, start, diag, doors_open))


def components(m: LayeredMap, diag: bool = False, doors_open: bool = True) -> List[Set[Pos]]:
    seen: Set[Pos] = set()
    out = []
    for x, y in m.cells():
        if (x, y) not in seen and m.walkable(x, y, doors_open):
            comp = reachable(m, (x, y), diag, doors_open)
            seen |= comp
            out.append(comp)
    return sorted(out, key=len, reverse=True)
