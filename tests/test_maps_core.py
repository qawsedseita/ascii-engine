import json, os, tempfile, unittest
from asciiengine import EngineError
from asciiengine.maps import LayeredMap, astar, components, reachable, validate_map


def room_map():
    m = LayeredMap(12, 8)
    for y in range(1, 7):
        for x in range(1, 11):
            m.set_cell(x, y, "floor")
    for x in range(0, 12):
        for y in (0, 7):
            m.set_cell(x, y, "wall")
    return m


class TestLayered(unittest.TestCase):
    def test_layers_and_validation_of_input(self):
        m = LayeredMap(5, 5)
        m.set_cell(1, 1, "floor"); m.set_cell(1, 1, "chest"); m.set_cell(1, 1, "wall")
        self.assertEqual(m.stack(1, 1), {"terrain": "floor", "structures": "wall", "objects": "chest"})
        with self.assertRaises(EngineError) as cm: m.set_cell(9, 9, "floor")
        self.assertEqual(cm.exception.code, "out_of_bounds")
        with self.assertRaises(EngineError) as cm: m.set_cell(1, 1, "wall", layer="terrain")
        self.assertEqual(cm.exception.code, "layer_mismatch")
        with self.assertRaises(EngineError) as cm: m.set_cell(1, 1, "orc")
        self.assertEqual(cm.exception.code, "is_entity")
        with self.assertRaises(EngineError) as cm: m.set_cell(1, 1, "dragonfruit")
        self.assertEqual(cm.exception.code, "unknown_kind")
        with self.assertRaises(EngineError): m.set_cell(1, 1, "ui_hline")
        m.set_cell(1, 1, None, "structures")
        self.assertNotIn("structures", m.stack(1, 1))

    def test_walkable_sight_collision_override(self):
        m = room_map()
        self.assertTrue(m.walkable(2, 2)); self.assertFalse(m.walkable(2, 0)); self.assertFalse(m.walkable(-1, 0))
        m.set_cell(3, 3, "door_closed")
        self.assertFalse(m.walkable(3, 3)); self.assertTrue(m.walkable(3, 3, doors_open=True))
        self.assertTrue(m.blocks_sight(3, 3)); self.assertTrue(m.blocks_sight(2, 0))
        m.set_cell(4, 4, "chest"); self.assertFalse(m.walkable(4, 4))
        m.collision[(4, 4)] = True; self.assertTrue(m.walkable(4, 4))        # override wins
        m.set_cell(5, 5, "water"); self.assertFalse(m.walkable(5, 5)); self.assertFalse(m.blocks_sight(5, 5))

    def test_entities(self):
        m = room_map()
        a = m.add_entity("orc", 2, 2); b = m.add_entity("orc", 3, 2)
        self.assertEqual((a["id"], b["id"]), ("orc_1", "orc_2"))
        with self.assertRaises(EngineError): m.add_entity("orc", 4, 2, id="orc_1")
        with self.assertRaises(EngineError): m.add_entity("wall", 4, 2)
        self.assertTrue(m.remove_entity("orc_1")); self.assertEqual(len(m.entities), 1)

    def test_json_roundtrip_and_clone(self):
        m = room_map(); m.add_entity("rat", 2, 2); m.spawn = (1, 1); m.exit = (10, 6)
        m.lights.append({"x": 2, "y": 2, "radius": 3}); m.regions["r"] = {"rect": [0, 0, 12, 8], "type": "room", "props": {}}
        m.collision[(5, 5)] = False
        d = json.loads(json.dumps(m.to_dict()))
        m2 = LayeredMap.from_dict(d)
        self.assertEqual(m2.to_dict(), m.to_dict())
        c = m.clone(); c.set_cell(2, 2, "wall"); self.assertTrue(m.walkable(2, 2))
        with tempfile.TemporaryDirectory() as t:
            p = os.path.join(t, "m.json"); m.save(p); self.assertEqual(LayeredMap.load(p).to_dict(), m.to_dict())
        with self.assertRaises(EngineError): LayeredMap.from_dict({"width": 5})


class TestPathValidate(unittest.TestCase):
    def test_astar_and_components(self):
        m = room_map()
        for y in range(1, 6): m.set_cell(5, y, "wall")                # wall with a gap at y=6
        p = astar(m, (1, 1), (10, 1))
        self.assertIsNotNone(p); self.assertIn((5, 6), p)
        self.assertEqual(len(p) - 1, 9 + 5 + 5)
        m.set_cell(5, 6, "wall")
        self.assertIsNone(astar(m, (1, 1), (10, 1)))
        self.assertEqual(len(components(m)), 2)
        m2 = room_map(); self.assertEqual(len(astar(m2, (1, 1), (4, 4), diag=True)) - 1, 3)
        self.assertEqual(len(astar(m2, (1, 1), (4, 4), diag=False)) - 1, 6)

    def test_closed_door_openable_for_paths(self):
        m = room_map()
        for y in range(1, 7): m.set_cell(5, y, "wall")
        m.set_cell(5, 3, "door_closed")
        self.assertIsNotNone(astar(m, (1, 1), (10, 1), doors_open=True))
        self.assertIsNone(astar(m, (1, 1), (10, 1), doors_open=False))

    def test_validate_reports(self):
        m = room_map()
        r = validate_map(m); self.assertFalse(r["ok"]); self.assertTrue(any("spawn" in e for e in r["errors"]))
        m.spawn, m.exit = (1, 1), (10, 6)
        self.assertTrue(validate_map(m)["ok"])
        m.add_entity("orc", 5, 0)
        self.assertTrue(any("non-walkable" in e for e in validate_map(m)["errors"]))
        m.remove_entity("orc_1")
        for y in range(1, 7): m.set_cell(5, y, "wall")
        r = validate_map(m); self.assertFalse(r["ok"]); self.assertTrue(any("no path" in e for e in r["errors"]))
        self.assertEqual(r["stats"]["components"], 2)


if __name__ == "__main__":
    unittest.main()
