"""CLI: python -m asciiengine {dungeon,validate,render,edit}"""
import argparse, json, sys
from .core.errors import EngineError
from .maps import dungeon, render_map, validate_map, MapEditor
from .maps.layered import LayeredMap
from .styles.library import StyleLibrary
from .styles.style import StyleSet

def main(argv=None):
    p=argparse.ArgumentParser(prog="asciiengine",description="AI-operable semantic ASCII game engine")
    sub=p.add_subparsers(dest="cmd",required=True)
    d=sub.add_parser("dungeon",help="generate a connected dungeon"); d.add_argument("--width",type=int,default=80); d.add_argument("--height",type=int,default=40); d.add_argument("--rooms",type=int,default=20); d.add_argument("--seed",type=int,default=11); d.add_argument("--output",default="dungeon.json")
    v=sub.add_parser("validate",help="validate a map JSON"); v.add_argument("map")
    r=sub.add_parser("render",help="render a map as text"); r.add_argument("map"); r.add_argument("--style",default="classic_ascii")
    e=sub.add_parser("edit",help="apply one or more JSON map editor commands"); e.add_argument("map"); e.add_argument("commands",help="JSON object or list of objects"); e.add_argument("--output")
    args=p.parse_args(argv)
    try:
        if args.cmd=="dungeon":
            m=dungeon(args.width,args.height,args.rooms,args.seed); m.save(args.output); print(json.dumps({"ok":True,"path":args.output,"rooms":m.meta["rooms"]})); return 0
        m=LayeredMap.load(args.map)
        if args.cmd=="validate": print(json.dumps(validate_map(m),ensure_ascii=False,indent=2)); return 0
        if args.cmd=="render": print(render_map(m,StyleSet(StyleLibrary().get(args.style))).to_text()); return 0
        if args.cmd=="edit":
            commands=json.loads(args.commands); result=MapEditor(m).run(commands)
            m.save(args.output or args.map); print(json.dumps({"ok":True,"results":result},ensure_ascii=False)); return 0
    except (EngineError, ValueError, OSError) as exc:
        payload=exc.to_dict() if isinstance(exc,EngineError) else {"ok":False,"error":str(exc)}
        print(json.dumps(payload,ensure_ascii=False),file=sys.stderr); return 2
    return 1
if __name__=="__main__": raise SystemExit(main())
