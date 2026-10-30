"""Requested example: NetHack-ish 20-room linked dungeon with limited light and creatures."""
from asciiengine.maps import dungeon, populate, player_view, render_map, validate_map
from asciiengine.styles.library import StyleLibrary
from asciiengine.styles.style import StyleSet
from asciiengine.world import GameWorld

m=dungeon(80,40,rooms=20,seed=11,lit_ratio=0.2)
populate(m,seed=11,creatures=18,items=20)
m.add_entity("player",*m.spawn,props={"faction":"player"})
report=validate_map(m)
assert report["ok"], report
ss=StyleSet(StyleLibrary().get("nethack"))
view=player_view(m,*m.spawn,light_radius=2)
print(render_map(m,ss,visible=view).to_ansi("ansi16"))
world=GameWorld(m)
print(f"20 rooms={m.meta['rooms']}, connected and valid={report['ok']}, creatures={sum(e['kind'] not in {'player','npc'} for e in m.entities)}")
print("Player turn smoke test:",world.step(world.player_id,1,0))
