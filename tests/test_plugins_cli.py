import unittest
from asciiengine.plugins import Plugin, PluginManager
from asciiengine.aitools import EngineTools
from asciiengine.maps import dungeon

class DemoPlugin(Plugin):
 name="demo"
 def on_load(self,tools): self.loaded=True
 def on_unload(self): self.loaded=False

class PluginCliTests(unittest.TestCase):
 def test_plugin_lifecycle_and_tools(self):
  manager=PluginManager(EngineTools(dungeon(40,24,rooms=4,seed=3)))
  plugin=DemoPlugin(); self.assertEqual(manager.register(plugin),"demo"); self.assertTrue(plugin.loaded)
  self.assertEqual(manager.list(),["demo"]); self.assertTrue(manager.unload("demo")); self.assertFalse(plugin.loaded)
  self.assertFalse(manager.unload("missing"))
 def test_dispatch_structured_error(self):
  tools=EngineTools(dungeon(40,24,rooms=4,seed=7))
  self.assertTrue(tools.dispatch({"cmd":"validate"})["ok"])
  self.assertFalse(tools.dispatch({"cmd":"not-a-tool"})["ok"])
if __name__=="__main__": unittest.main()
