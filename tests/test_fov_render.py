import unittest
from asciiengine.maps import LayeredMap, MapEditor, compute_fov, lit_cells, player_view, render_map, render_text
from asciiengine.styles.library import StyleLibrary
from asciiengine.styles.style import StyleSet

LIB = StyleLibrary()


def two_rooms(lit_b=True):
    m = LayeredMap(30, 10)
    ed = MapEditor(m)
    r = ed.run([f"room 0 0 8 7 name=a", f"room 16 0 10 7 name=b lit={str(lit_b).lower()}", "corridor 7 3 16 3",
                "door 7 3 doorway", "spawn 2 3", "exit 22 3"])
    assert all(x["ok"] for x in r), r
    return m


class TestFov(unittest.TestCase):
    def test_open_room_and_wall_blocking(self):
        m = LayeredMap(21, 11)
        MapEditor(m).run(["rect floor 0 0 21 11", "rect wall 10 3 1 5"])
        v = compute_fov(m, 5, 5, 8)
        self.assertIn((5, 5), v); self.assertIn((9, 5), v); self.assertIn((10, 5), v)    # the wall itself is seen
        self.assertNotIn((13, 5), v)                                                       # but not behind it
        self.assertIn((12, 1), v)                                                          # around the end of the wall
        self.assertNotIn((20, 5), compute_fov(m, 5, 5, 8))                                 # radius limit

    def test_limited_lighting(self):
        m = two_rooms(lit_b=True)
        lit = lit_cells(m)
        self.assertIn((20, 3), lit); self.assertNotIn((3, 3), lit)
        v = player_view(m, 2, 1, light_radius=2)
        self.assertIn((3, 1), v)                    # own light
        self.assertNotIn((6, 1), v)                 # dark room beyond the light radius
        self.assertNotIn((20, 3), v)                # lit room b exists but a wall blocks the line of sight
        v2 = player_view(m, 2, 3, light_radius=1)   # aligned with the doorway: sees along the corridor into lit room b
        self.assertIn((20, 3), v2)
        self.assertNotIn((6, 3), v2)                # the dark corridor/room stays dark
        self.assertNotIn((3, 3), player_view(m, 2, 3, light_radius=0))   # no own light: only the own cell

    def test_light_source(self):
        m = two_rooms(lit_b=False)
        self.assertNotIn((20, 3), lit_cells(m))
        MapEditor(m).run("light 20 3 4")
        self.assertIn((22, 3), lit_cells(m)); self.assertNotIn((2, 3), lit_cells(m))


class TestRender(unittest.TestCase):
    def test_autotile_box_and_ascii(self):
        m = LayeredMap(8, 6)
        MapEditor(m).run("room 0 0 6 4")
        t = render_text(m, "unicode_detailed").split("\n")
        self.assertEqual(t[0][:6], "┌────┐"); self.assertEqual(t[3][:6], "└────┘"); self.assertEqual(t[1][0], "│")
        t = render_text(m, "classic_ascii").split("\n")
        self.assertEqual(t[0][:6], "######")
        t = render_text(m, "nethack").split("\n")
        self.assertEqual(t[0][:6], "------"); self.assertEqual(t[1][0], "|")

    def test_door_junction_and_open_door_orientation(self):
        m = LayeredMap(9, 7)
        MapEditor(m).run(["room 0 0 9 7", "door 4 0 door_open", "door 0 3 door_open"])
        t = render_text(m, "nethack").split("\n")
        self.assertEqual(t[0][4], "|")      # open door in a horizontal wall is drawn '|'
        self.assertEqual(t[3][0], "-")      # in a vertical wall is drawn '-'

    def test_layers_entities_fog(self):
        m = two_rooms()
        m.add_entity("orc", 20, 3); m.add_entity("rat", 3, 3)
        full = render_map(m, "nethack")
        self.assertEqual(full.get(20, 3).ch, "o"); self.assertEqual(full.get(22, 3).ch, ">")
        m.remove_entity("rat_1"); m.add_entity("rat", 3, 1)
        vis = player_view(m, 2, 1, light_radius=2)
        fog = render_map(m, "nethack", visible=vis)
        self.assertEqual(fog.get(3, 1).ch, "r")                  # rat inside own light
        self.assertEqual(fog.get(20, 3).ch, " ")                 # unseen orc hidden
        mem = render_map(m, "nethack", visible=vis, explored={(20, 3), (22, 3)})
        self.assertEqual(mem.get(22, 3).ch, ">"); self.assertEqual(mem.get(20, 3).ch, ".")   # remembered: no entity
        self.assertLess(mem.get(22, 3).fg[0], full.get(22, 3).fg[0] + 1)
        self.assertEqual(mem.get(22, 3).fg, tuple(int(c * 0.45) for c in full.get(22, 3).fg))

    def test_viewport_and_spawn_marker(self):
        m = two_rooms()
        c = render_map(m, "classic_ascii", viewport=(0, 0, 8, 7), show_spawn=True)
        self.assertEqual((c.width, c.height), (8, 7)); self.assertEqual(c.get(2, 3).ch, "@")

    def test_per_category_styles_and_restyle_keeps_logic(self):
        m = two_rooms(); m.add_entity("orc", 20, 3)
        sig = m.logic_signature()
        ss = StyleSet(LIB.get("classic_ascii")); ss.set(LIB.get("dwarf_fortress"), ["entities"])
        self.assertEqual(render_map(m, ss).get(20, 3).ch, "O")      # entities DF
        self.assertEqual(render_map(m, ss).get(0, 0).ch, "#")       # structures classic
        for name in LIB.names():
            c = render_map(m, name)
            self.assertEqual((c.width, c.height), (30, 10))
            self.assertEqual(m.logic_signature(), sig, name)         # restyling cannot alter gameplay data


if __name__ == "__main__":
    unittest.main()
