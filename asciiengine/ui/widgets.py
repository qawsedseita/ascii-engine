"""Small terminal UI widgets rendered with the existing semantic UI style kinds."""
from dataclasses import dataclass, field
from ..core.canvas import Canvas
from ..styles.style import StyleSet


def _glyph(styles, kind, fallback):
    return styles.glyph(kind, "ui").ch if styles else fallback


def _frame(canvas, x, y, w, h, styles, title=""):
    tl, tr = _glyph(styles,"ui_corner_tl","+"), _glyph(styles,"ui_corner_tr","+")
    bl, br = _glyph(styles,"ui_corner_bl","+"), _glyph(styles,"ui_corner_br","+")
    hl, vl = _glyph(styles,"ui_hline","-"), _glyph(styles,"ui_vline","|")
    for xx in range(x+1,x+w-1): canvas.put(xx,y,hl); canvas.put(xx,y+h-1,hl)
    for yy in range(y+1,y+h-1): canvas.put(x,yy,vl); canvas.put(x+w-1,yy,vl)
    canvas.put(x,y,tl); canvas.put(x+w-1,y,tr); canvas.put(x,y+h-1,bl); canvas.put(x+w-1,y+h-1,br)
    if title: canvas.text(x+2,y,title[:max(0,w-4)])

@dataclass
class Menu:
    title: str
    options: list[str]
    selected: int = 0
    def move(self, delta):
        if self.options: self.selected = (self.selected + delta) % len(self.options)
        return self.selected
    def choose(self): return self.options[self.selected] if self.options else None
    def draw(self, styles: StyleSet | None = None, width: int | None = None) -> Canvas:
        width = width or max(12, max([len(self.title), *(len(x) for x in self.options)] or [0]) + 6)
        height = max(3, len(self.options)+2); c=Canvas(width,height); _frame(c,0,0,width,height,styles,self.title)
        cursor=_glyph(styles,"ui_cursor",">")
        for i,opt in enumerate(self.options): c.text(1,i+1,(cursor if i==self.selected else " ")+" "+opt[:width-5])
        return c

@dataclass
class Dialogue:
    speaker: str
    text: str
    choices: list[str] = field(default_factory=list)
    selected: int = 0
    def draw(self, width=60, styles: StyleSet | None = None) -> Canvas:
        lines=[]
        words=self.text.split(); line=""
        for word in words:
            if line and len(line)+1+len(word)>width-4: lines.append(line); line=word
            else: line=(line+" "+word).strip()
        if line: lines.append(line)
        height=max(4,len(lines)+len(self.choices)+3); c=Canvas(width,height); _frame(c,0,0,width,height,styles,self.speaker)
        for i,s in enumerate(lines): c.text(2,i+1,s)
        for i,opt in enumerate(self.choices): c.text(2,len(lines)+i+2,("* " if i==self.selected else "  ")+opt[:width-5])
        return c

@dataclass
class HUD:
    hp: int
    max_hp: int
    status: str = ""
    def draw(self, width=30, styles: StyleSet | None = None) -> Canvas:
        c=Canvas(width,2); full=_glyph(styles,"ui_bar_full","#"); empty=_glyph(styles,"ui_bar_empty","-")
        ratio=0 if self.max_hp<=0 else max(0,min(1,self.hp/self.max_hp)); bar=max(0,width-10)
        n=round(bar*ratio); c.text(0,0,"HP "); c.text(3,0,full*n+empty*(bar-n)); c.text(min(width-1,bar+4),0,f"{self.hp}/{self.max_hp}"[:max(0,width-bar-4)])
        c.text(0,1,self.status[:width]); return c
