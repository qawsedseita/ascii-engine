"""End-to-end: synthetic creature image -> ASCII -> NetHack style -> map -> game turn."""
from PIL import Image, ImageDraw
from asciiengine.core.kinds import default_kinds
from asciiengine.imaging import image_to_ascii, AsciiSprite, register_sprite_kind
from asciiengine.maps import dungeon, render_map
from asciiengine.styles.library import StyleLibrary
from asciiengine.styles.style import StyleSet
from asciiengine.styles.translator import StyleTranslator
from asciiengine.world import GameWorld

image=Image.new("RGBA",(16,16),(0,0,0,0)); draw=ImageDraw.Draw(image)
draw.ellipse((3,2,12,13),fill=(210,80,70,255)); draw.point((6,6),fill="white"); draw.point((10,6),fill="white")
art=image_to_ascii(image,width=8,height=8,mode="high-density")
sprite=AsciiSprite.from_art(art,"crimson_beast")
kinds=default_kinds(); lib=StyleLibrary(); styles=StyleSet(lib.get("classic_ascii"))
register_sprite_kind(sprite,kinds,styles.default,"crimson_beast",glyph="C")
StyleTranslator(lib).apply(styles,"personagens estilo NetHack")
m=dungeon(50,30,rooms=8,seed=31)
m.kinds=kinds
# Use a reachable floor adjacent to spawn for a demonstrable first turn.
m.add_entity("player",*m.spawn,props={"faction":"hero"})
spot=next((p for p in [(m.spawn[0]+1,m.spawn[1]),(m.spawn[0]-1,m.spawn[1]),(m.spawn[0],m.spawn[1]+1),(m.spawn[0],m.spawn[1]-1)] if m.walkable(*p)),m.spawn)
m.add_entity("crimson_beast",*spot,props={"faction":"beasts","hp":6})
world=GameWorld(m)
print("Image converted to ASCII:\n"+art.to_text())
print("Creature glyph after style conversion:",styles.glyph("crimson_beast","entities").ch)
print(render_map(m,styles).to_text())
print("Game turn:",world.step(world.player_id,0,1))
