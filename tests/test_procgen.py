import unittest
from asciiengine import EngineError
from asciiengine.maps import (LayeredMap, astar, components, dungeon, cave, biome, populate, generate, reachable,
                              validate_map, render_text, BIOMES)


class TestDungeon(unittest.TestCase):
    def test_20_rooms_connected_many_seeds(self):
        for seed in range(25):
            m = dungeon(80, 40, rooms=20, seed=seed)
            rep = validate_map(m)
            self.assertTrue(rep["ok"], (seed, rep))
            self.assertEqual(rep["stats"]["rooms"], 20, seed)
            self.assertEqual([w for w in rep["warnings"] if "overlap" in w], [], seed)
            self.assertIsNotNone(astar(m, m.spawn, m.exit), seed)
            reach = reachable(m, m.spawn)
            for n, r in m.regions.items():                          # every room is reachable from the spawn
                x, y, w, h = r["rect"]
                self.assertTrue(any((i, j) in reach for j in range(y + 1, y + h - 1) for i in range(x + 1, x + w - 1)), (seed, n))

    def test_deterministic_and_seed_changes_result(self):
        a, b, c = dungeon(seed=7), dungeon(seed=7), dungeon(seed=8)
        self.assertEqual(a.to_dict(), b.to_dict()); self.assertNotEqual(a.to_dict(), c.to_dict())

    def test_lit_ratio_and_exit_far_from_spawn(self):
        m = dungeon(seed=3, lit_ratio=1.0)
        self.assertTrue(all(r["props"]["lit"] for r in m.regions.values()))
        self.assertFalse(any(r["props"]["lit"] for r in dungeon(seed=3, lit_ratio=0.0).regions.values()))
        self.assertGreater(abs(m.spawn[0] - m.exit[0]) + abs(m.spawn[1] - m.exit[1]), 10)

    def test_too_small_is_an_honest_error(self):
        with self.assertRaises(EngineError) as cm:
            dungeon(30, 15, rooms=20, seed=1)
        self.assertEqual(cm.exception.code, "dungeon_too_small")
        self.assertIn("bigger map", cm.exception.hint)

    def test_populate_spreads_creatures_and_keeps_map_valid(self):
        for seed in range(10):
            m = dungeon(seed=seed)
            before = m.logic_signature()["walk"]
            info = populate(m, seed=seed, creatures=24, items=18, chests=3, torches=3)
            self.assertEqual(info["creatures"], 24)
            self.assertGreaterEqual(info["rooms_with_creatures"], 15)           # spread over many rooms
            rep = validate_map(m); self.assertTrue(rep["ok"], (seed, rep))
            self.assertEqual([w for w in rep["warnings"] if "unreachable" in w], [], seed)
            from asciiengine.maps import astar
            self.assertIsNotNone(astar(m, m.spawn, m.exit))
            from asciiengine.maps.pathing import distance_map
            d = distance_map(m, m.spawn)
            self.assertTrue(all(d[(e["x"], e["y"])] >= 8 for e in m.entities), seed)   # none next to the spawn
            self.assertEqual(len({(e["x"], e["y"]) for e in m.entities}), len(m.entities))
        self.assertEqual(len(m.lights), info["torches"])

    def test_populate_scales_danger_with_distance(self):
        m = dungeon(seed=5); populate(m, seed=5, creatures=40)
        from asciiengine.maps.pathing import distance_map
        d = distance_map(m, m.spawn)
        weak = {"rat", "bat", "slime"}
        near = [e for e in m.entities if d[(e["x"], e["y"])] < 25]
        far = [e for e in m.entities if d[(e["x"], e["y"])] > 60]
        if near and far:
            self.assertGreater(sum(e["kind"] in weak for e in near) / len(near), sum(e["kind"] in weak for e in far) / len(far))


class TestCaveBiome(unittest.TestCase):
    def test_cave_single_component(self):
        for seed in range(8):
            m = cave(seed=seed)
            self.assertEqual(len(components(m)), 1, seed)
            self.assertTrue(validate_map(m)["ok"], seed)
        self.assertEqual(cave(seed=2).to_dict(), cave(seed=2).to_dict())

    def test_biomes_valid_and_distinct(self):
        kinds_seen = {}
        for b in BIOMES:
            m = biome(b, seed=4)
            self.assertTrue(validate_map(m)["ok"], b)
            self.assertIsNotNone(astar(m, m.spawn, m.exit), b)
            kinds_seen[b] = {m.get("terrain", x, y) for x, y in m.cells()}
        self.assertIn("sand", kinds_seen["desert"]); self.assertIn("snow", kinds_seen["snow"]); self.assertIn("mud", kinds_seen["swamp"])
        self.assertIn("grass", kinds_seen["forest"])
        with self.assertRaises(EngineError) as cm: biome("jungle")
        self.assertEqual(cm.exception.code, "unknown_biome")
        self.assertEqual(generate("forest", seed=1).to_dict(), biome("forest", seed=1).to_dict())

    def test_generated_maps_render_in_every_style(self):
        from asciiengine.styles.library import StyleLibrary
        m = dungeon(seed=1)
        for n in StyleLibrary().names():
            self.assertTrue(render_text(m, n).strip(), n)


if __name__ == "__main__":
    unittest.main()
