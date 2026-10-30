import unittest
from asciiengine import EngineError
from asciiengine.maps import LayeredMap, validate_map
from asciiengine.maps.editor import MapEditor, parse_text


class TestEditor(unittest.TestCase):
    def setUp(self):
        self.m = LayeredMap(30, 15)
        self.ed = MapEditor(self.m)

    def test_parse_text(self):
        self.assertEqual(parse_text("room 2 3 10 6 lit=true name=hall"),
                         {"cmd": "room", "x": 2, "y": 3, "w": 10, "h": 6, "lit": True, "name": "hall"})
        self.assertEqual(parse_text("collision 1 1 none")["walkable"], None)
        with self.assertRaises(EngineError) as cm: parse_text("dance 1 2")
        self.assertEqual(cm.exception.code, "unknown_command")
        with self.assertRaises(EngineError): parse_text("room 1 2 3 4 5")

    def test_room_corridor_door_spawn_exit(self):
        r = self.ed.run("""
            # two rooms joined by a corridor
            room 1 1 8 6 name=a lit=true
            room 18 1 8 6 name=b
            corridor 8 3 18 3
            door 9 3 door_closed
            spawn 3 3
            exit 22 4
        """)
        self.assertTrue(all(x["ok"] for x in r), r)
        self.assertEqual(self.m.get("structures", 1, 1), "wall")
        self.assertEqual(self.m.get("structures", 9, 3), "door_closed")
        self.assertEqual(self.m.get("structures", 18, 3), "doorway")     # corridor pierced room b's wall
        self.assertEqual(self.m.get("terrain", 12, 3), "corridor")
        self.assertTrue(self.m.regions["a"]["props"]["lit"])
        rep = validate_map(self.m)
        self.assertTrue(rep["ok"], rep)
        self.assertEqual(rep["stats"]["rooms"], 2)

    def test_atomic_rollback_and_error_info(self):
        self.ed.run("room 1 1 8 6")
        before = self.m.to_dict()
        r = self.ed.run(["rect wall 0 0 2 2", {"cmd": "set", "x": 99, "y": 0, "kind": "wall"}, "rect floor 5 5 1 1"])
        self.assertFalse(r[0]["ok"]); self.assertEqual(r[0]["failed_index"], 1)
        self.assertEqual(r[0]["code"], "out_of_bounds"); self.assertTrue(r[0]["rolled_back"])
        self.assertEqual(self.m.to_dict(), before)

    def test_missing_args_and_bad_kind(self):
        self.assertEqual(self.ed.run_one("rect wall 1 1 3")["code"], "missing_arg")
        self.assertEqual(self.ed.run_one("rect lava_lake 1 1 3 3")["code"], "unknown_kind")
        self.assertEqual(self.ed.run_one("room 1 1 2 2")["code"], "bad_rect")
        self.assertEqual(self.ed.run_one("spawn 1 1")["code"], "bad_spawn")

    def test_undo_redo_batch_is_one_step(self):
        self.ed.run(["room 1 1 8 6", "rect grass 12 1 3 3"])
        self.assertEqual(self.m.get("terrain", 12, 1), "grass")
        self.assertTrue(self.ed.run("undo")[0]["ok"])
        self.assertEqual(self.m.get("terrain", 12, 1), "void"); self.assertEqual(self.m.regions, {})
        self.assertTrue(self.ed.run("redo")[0]["ok"])
        self.assertEqual(self.m.get("terrain", 12, 1), "grass"); self.assertIn("room_1", self.m.regions)
        self.ed.run("undo"); self.ed.run("undo")
        self.assertFalse(self.ed.run("undo")[0]["ok"])

    def test_line_fill_replace_remove(self):
        self.ed.run("rect floor 0 0 10 10")
        self.ed.run("line wall 0 5 9 5")
        self.assertEqual(self.m.get("structures", 4, 5), "wall")
        n = self.ed.run_one("fill 2 2 grass")["changed"]
        self.assertEqual(n, 100)                                     # fill is on the terrain layer, not stopped by walls
        self.ed.run("replace grass sand")
        self.assertEqual(self.m.get("terrain", 3, 3), "sand")
        self.assertEqual(self.ed.run_one("replace wall orc")["code"], "layer_mismatch")
        self.ed.run("remove 0 5 10 1 layer=structures")
        self.assertIsNone(self.m.get("structures", 4, 5))

    def test_copy_move_with_entities(self):
        self.ed.run(["room 1 1 6 5", "place orc 3 3 id=boss", "place chest 4 3"])
        self.ed.run("copy 1 1 6 5 15 1")
        self.assertEqual(self.m.get("structures", 15, 1), "wall"); self.assertEqual(self.m.get("objects", 18, 3), "chest")
        self.assertEqual(len(self.m.entities), 2)
        self.ed.run("move 1 1 6 5 1 8")
        self.assertIsNone(self.m.get("structures", 1, 1)); self.assertEqual(self.m.get("structures", 1, 8), "wall")
        self.assertIn("boss", {e["id"] for e in self.m.entities})

    def test_collision_inspect_light_region(self):
        self.ed.run(["room 1 1 8 6", "place chest 3 3", "collision 3 3 true"])
        i = self.ed.run_one("inspect 3 3")
        self.assertTrue(i["walkable"]); self.assertEqual(i["collision_override"], True)
        self.assertEqual(i["stack"]["objects"], "chest")
        self.ed.run("collision 3 3 none"); self.assertFalse(self.ed.run_one("inspect 3 3")["walkable"])
        self.ed.run(["light 4 4 5", "region swamp 10 1 5 5 type=biome biome=swamp lit=false"])
        self.assertEqual(self.m.lights[0]["radius"], 5); self.assertEqual(self.m.regions["swamp"]["props"]["biome"], "swamp")
        self.assertEqual(self.ed.run_one("inspect 2 2")["regions"], ["room_1"])


if __name__ == "__main__":
    unittest.main()
