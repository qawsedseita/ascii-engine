import unittest
from asciiengine.core.kinds import default_kinds
from asciiengine.maps import LayeredMap
from asciiengine.fx import Animation, EffectSystem
from asciiengine.ui import Dialogue, HUD, Menu
from asciiengine.styles.library import StyleLibrary
from asciiengine.styles.style import StyleSet

class FxUiTests(unittest.TestCase):
 def test_effect_lifetime_and_animation(self):
  m=LayeredMap(5,5,default_kinds()); fx=EffectSystem(); fx.emit(m,"spark",2,2,2)
  self.assertEqual(m.layers["effects"][(2,2)],"spark"); self.assertEqual(fx.tick(m),1); self.assertEqual(fx.tick(m),0); self.assertFalse(m.layers["effects"])
  a=Animation(["spark","fire"],1,1); self.assertEqual(a.kind,"spark"); self.assertTrue(a.advance()); self.assertEqual(a.kind,"fire"); self.assertFalse(a.advance())
 def test_ui_widgets(self):
  style=StyleSet(StyleLibrary().get("classic_ascii")); menu=Menu("Items",["Potion","Gold"])
  self.assertEqual(menu.choose(),"Potion"); menu.move(1); self.assertEqual(menu.choose(),"Gold"); self.assertIn("Gold",menu.draw(style).to_text())
  self.assertIn("hello",Dialogue("Guide","hello there",["Ok"]).draw(styles=style).to_text())
  self.assertIn("HP",HUD(5,10,"Ready").draw(styles=style).to_text())
if __name__=="__main__": unittest.main()
