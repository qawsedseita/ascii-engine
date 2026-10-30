"""High-level, structured API intended for AI agents and scripts."""
from __future__ import annotations
from ..core.errors import EngineError
from ..maps import MapEditor, astar, render_map, validate_map
from ..styles.style import StyleSet
from ..styles.library import StyleLibrary
from ..styles.translator import StyleTranslator

class EngineTools:
    def __init__(self, game_map=None, style="classic_ascii", library=None):
        self.map=game_map; self.library=library or StyleLibrary(); self.styles=StyleSet(self.library.get(style)); self.editor=MapEditor(game_map) if game_map else None
        self.translator=StyleTranslator(self.library)
    def _need_map(self):
        if self.map is None: raise EngineError("No map is attached", "Create or load a LayeredMap first", "no_map")
    def edit_map(self, commands):
        self._need_map()
        try: return {"ok":True,"results":self.editor.run(commands)}
        except EngineError as e: return e.to_dict()
    def validate(self):
        self._need_map(); return validate_map(self.map)
    def restyle(self, instruction):
        try:
            result=self.translator.apply(self.styles,instruction)
            return {"ok":True,"styles":self.styles.describe(),"instructions":[{"style":i.style.name,"categories":i.categories,"take":i.take} for i in result.instructions]}
        except EngineError as e: return e.to_dict()
    def render(self, *, visible=None, explored=None, viewport=None):
        self._need_map()
        try: return {"ok":True,"text":render_map(self.map,self.styles,visible=visible,explored=explored,viewport=viewport).to_text(),"styles":self.styles.describe()}
        except EngineError as e: return e.to_dict()
    def path(self, start, goal):
        self._need_map()
        try: return {"ok":True,"path":astar(self.map,tuple(start),tuple(goal))}
        except EngineError as e: return e.to_dict()
    def playtest(self):
        """Static smoke test: validation + spawn-to-exit reachability + entity placement."""
        self._need_map(); report=validate_map(self.map)
        route=astar(self.map,self.map.spawn,self.map.exit) if self.map.spawn and self.map.exit else []
        return {"ok":report["ok"] and bool(route),"validation":report,"route_length":len(route),
                "entities":len(self.map.entities),"note":"Static map smoke test only; it does not simulate a full game session."}
    def dispatch(self, command: dict):
        if not isinstance(command,dict): return {"ok":False,"code":"bad_command","error":"Command must be a JSON object","hint":"Use {'cmd': ..., ...}"}
        name=command.get("cmd")
        table={"edit":lambda:self.edit_map(command.get("commands",[])),"validate":self.validate,
               "render":self.render,"playtest":self.playtest,
               "restyle":lambda:self.restyle(command.get("instruction","")),
               "path":lambda:self.path(command.get("start",[]),command.get("goal",[]))}
        if name not in table: return {"ok":False,"code":"unknown_tool","error":f"Unknown tool '{name}'","hint":f"Choose one of {sorted(table)}"}
        try: return table[name]()
        except EngineError as e: return e.to_dict()
