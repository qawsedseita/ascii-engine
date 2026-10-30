import unittest
from PIL import Image, ImageDraw
from asciiengine.core.kinds import default_kinds
from asciiengine.imaging import image_to_ascii, AsciiSprite, register_sprite_kind
from asciiengine.maps import dungeon
from asciiengine.styles.library import StyleLibrary
from asciiengine.styles.style import StyleSet
from asciiengine.styles.translator import StyleTranslator
from asciiengine.aitools import EngineTools
from asciiengine.world import GameWorld

class IntegrationTests(unittest.TestCase):
 def test_sprite_style_map_game_flow(self):
  im=Image.new("RGB",(8,8),"white"); ImageDraw.Draw(im).ellipse((1,1,6,6),fill="black")
  art=image_to_ascii(im,width=8,height=8); sprite=AsciiSprite.from_art(art,"test_beast")
  kinds=default_kinds(); lib=StyleLibrary(); ss=StyleSet(lib.get("classic_ascii")); register_sprite_kind(sprite,kinds,ss.default,"test_beast",glyph="B")
  m=dungeon(50,30,rooms=8,seed=13); m.kinds=kinds; x,y=m.spawn; spot=(x+1,y) if m.walkable(x+1,y) else (x-1,y)
  m.add_entity("player",*m.spawn,props={"faction":"hero"})
  m.add_entity("test_beast",*spot,props={"faction":"enemy"})
  before=m.logic_signature(); StyleTranslator(lib).apply(ss,"personagens estilo NetHack")
  self.assertEqual(m.logic_signature(),before)
  world=GameWorld(m); self.assertTrue(world.step(world.player_id,0,1)["ok"])
  tools=EngineTools(m,library=lib); self.assertTrue(tools.validate()["ok"]); self.assertTrue(tools.playtest()["ok"])
  self.assertEqual(ss.style_for("entities").name,"nethack"); self.assertEqual(ss.glyph("test_beast","entities").ch,"B")
if __name__=="__main__": unittest.main()
