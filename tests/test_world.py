import tempfile, unittest
from pathlib import Path
from asciiengine.core.kinds import default_kinds
from asciiengine.maps import LayeredMap
from asciiengine.world import GameWorld

class WorldTests(unittest.TestCase):
    def make_world(self):
        k=default_kinds(); m=LayeredMap(9,7,k)
        for y in range(1,6):
            for x in range(1,8): m.set_cell(x,y,"floor")
        m.add_entity("player",2,2,props={"faction":"hero","attack":5})
        m.add_entity("goblin",5,2,props={"faction":"enemy","hp":7,"defense":1})
        m.set_cell(2,2,"gold")
        return GameWorld(m)
    def test_turn_move_combat_and_ai(self):
        w=self.make_world(); self.assertTrue(w.move("player_1",1,0)["ok"])
        self.assertEqual(w.entity("player_1").x,3)
        w.entity("goblin_1").x = 4; w._sync_map()
        w.attack("player_1","goblin_1"); self.assertEqual(w.entity("goblin_1").hp,3)
        w.npc_turn("goblin_1"); self.assertEqual(w.entity("goblin_1").x,4)
        w.move("player_1",0,1); self.assertEqual(w.entity("player_1").y,3)
    def test_npc_pursuit_uses_astar(self):
        w=self.make_world(); result=w.npc_turn("goblin_1")
        self.assertTrue(result["acted"])
        self.assertEqual((w.entity("goblin_1").x,w.entity("goblin_1").y),(4,2))
    def test_inventory_equip_camera_and_save(self):
        w=self.make_world(); w.pickup("player_1")
        self.assertIn("gold", w.entity("player_1").inventory)
        self.assertEqual(w.camera("player_1",4,3), (0,1,4,3))
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"save.json"; w.save(p); other=GameWorld.load(p, default_kinds())
            self.assertEqual(other.entity("player_1").inventory,["gold"])
            self.assertEqual(other.map.logic_signature(), w.map.logic_signature())
    def test_collision_and_push(self):
        w=self.make_world(); w.map.set_cell(3,2,"wall")
        self.assertFalse(w.move("player_1",1,0)["ok"])
        self.assertTrue(w.push("player_1",0,1))
        with self.assertRaises(Exception): w.attack("player_1","goblin_1")

if __name__=="__main__": unittest.main()
