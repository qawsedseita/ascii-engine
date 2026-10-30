"""Map validation: returns a report an AI can act on (errors must be fixed, warnings are advice)."""
from __future__ import annotations

from .layered import LayeredMap
from .pathing import astar, components, reachable


def validate_map(m: LayeredMap) -> dict:
    errors, warnings = [], []
    # unknown kinds (e.g. map loaded with a different registry)
    for layer, cells in m.layers.items():
        for (x, y), k in cells.items():
            if not m.kinds.has(k):
                errors.append(f"unknown kind '{k}' at ({x},{y}) on layer {layer}")
    for e in m.entities:
        if not m.kinds.has(e["kind"]):
            errors.append(f"entity {e['id']} has unknown kind '{e['kind']}'")
    if errors:
        return {"ok": False, "errors": errors, "warnings": warnings, "stats": {}}

    if m.spawn is None:
        errors.append("no spawn point (use the 'spawn' command)")
    elif not m.walkable(*m.spawn, doors_open=True):
        errors.append(f"spawn {m.spawn} is not walkable")
    if m.exit is None:
        errors.append("no exit (use the 'exit' command)")
    elif not m.walkable(*m.exit, doors_open=True):
        errors.append(f"exit {m.exit} is not walkable")
    if m.spawn and m.exit and not errors:
        if astar(m, m.spawn, m.exit, diag=False, doors_open=True) is None:
            errors.append(f"no path from spawn {m.spawn} to exit {m.exit} (4-directional, doors openable)")

    reach = reachable(m, m.spawn) if m.spawn and m.walkable(*m.spawn, True) else set()
    for name, r in m.regions.items():
        if r.get("type") == "room":
            x, y, w, h = r["rect"]
            inner = [(i, j) for j in range(y + 1, y + h - 1) for i in range(x + 1, x + w - 1) if m.walkable(i, j, True)]
            if not inner:
                errors.append(f"room '{name}' has no walkable interior")
            elif reach and not any(c in reach for c in inner):
                errors.append(f"room '{name}' is unreachable from spawn")
    rooms = [(n, r["rect"]) for n, r in m.regions.items() if r.get("type") == "room"]
    for i in range(len(rooms)):
        for j in range(i + 1, len(rooms)):
            (na, a), (nb, b) = rooms[i], rooms[j]
            if a[0] < b[0] + b[2] and b[0] < a[0] + a[2] and a[1] < b[1] + b[3] and b[1] < a[1] + a[3]:
                warnings.append(f"rooms '{na}' and '{nb}' overlap")

    for e in m.entities:
        if not m.walkable(e["x"], e["y"], True):
            errors.append(f"entity {e['id']} ({e['kind']}) stands on a non-walkable cell ({e['x']},{e['y']})")
        elif reach and (e["x"], e["y"]) not in reach:
            warnings.append(f"entity {e['id']} ({e['kind']}) is unreachable from spawn")
    seen = {}
    for e in m.entities:
        key = (e["x"], e["y"])
        if key in seen:
            warnings.append(f"entities {seen[key]} and {e['id']} share cell {key}")
        seen[key] = e["id"]
    for (x, y), o in m.layers["objects"].items():
        s = m.layers["structures"].get((x, y))
        if s is not None and not m.kinds.get(s).walkable:
            warnings.append(f"object '{o}' at ({x},{y}) is inside a solid structure '{s}'")
    comps = components(m)
    if len(comps) > 1 and reach:
        warnings.append(f"{len(comps) - 1} walkable area(s) are disconnected from the main area")
    return {"ok": not errors, "errors": errors, "warnings": warnings,
            "stats": {"width": m.width, "height": m.height, "walkable_cells": sum(len(c) for c in comps),
                      "components": len(comps), "reachable_from_spawn": len(reach), "rooms": len(rooms),
                      "entities": len(m.entities), "objects": len(m.layers["objects"])}}
