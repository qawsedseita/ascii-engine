"""Optional plugin lifecycle manager."""
from __future__ import annotations
import importlib
from .core.errors import EngineError

class Plugin:
    name = "plugin"
    def on_load(self, tools): pass
    def on_unload(self): pass

class PluginManager:
    def __init__(self, tools=None): self.tools=tools; self.plugins={}
    def register(self, plugin):
        name=getattr(plugin,"name",None)
        if not name or not callable(getattr(plugin,"on_load",None)):
            raise EngineError("Plugin must define name and on_load(tools)", "Subclass asciiengine.plugins.Plugin", "bad_plugin")
        if name in self.plugins: raise EngineError(f"Plugin '{name}' is already loaded", "Unload it before registering a replacement", "duplicate_plugin")
        plugin.on_load(self.tools); self.plugins[name]=plugin; return name
    def load(self, module_path: str):
        try: module=importlib.import_module(module_path)
        except Exception as exc: raise EngineError(f"Could not import plugin '{module_path}': {exc}", "Check module path and plugin dependencies", "plugin_import") from exc
        factory=getattr(module,"create_plugin",None)
        cls=getattr(module,"Plugin",None)
        try: instance=factory() if callable(factory) else cls() if callable(cls) else None
        except Exception as exc: raise EngineError(f"Could not create plugin: {exc}", "Expose create_plugin() or a Plugin class", "plugin_init") from exc
        if instance is None: raise EngineError("Plugin module has no factory", "Expose create_plugin() or a Plugin class", "bad_plugin")
        return self.register(instance)
    def unload(self, name):
        if name not in self.plugins: return False
        plugin=self.plugins.pop(name); plugin.on_unload(); return True
    def list(self): return sorted(self.plugins)
