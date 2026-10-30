"""Canvas: a grid of Cells with ANSI / plain-text / HTML output."""
from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional, Tuple

RGB = Tuple[int, int, int]

ANSI16 = [(0, 0, 0), (170, 0, 0), (0, 170, 0), (170, 85, 0), (0, 0, 170), (170, 0, 170), (0, 170, 170), (170, 170, 170),
          (85, 85, 85), (255, 85, 85), (85, 255, 85), (255, 255, 85), (85, 85, 255), (255, 85, 255), (85, 255, 255), (255, 255, 255)]


def nearest_ansi16(c: RGB) -> int:
    best, bi = 1 << 30, 0
    for i, p in enumerate(ANSI16):
        d = (p[0] - c[0]) ** 2 + (p[1] - c[1]) ** 2 + (p[2] - c[2]) ** 2
        if d < best:
            best, bi = d, i
    return bi


@dataclass
class Cell:
    ch: str = " "
    fg: Optional[RGB] = None
    bg: Optional[RGB] = None

    def copy(self):
        return Cell(self.ch, self.fg, self.bg)


class Canvas:
    def __init__(self, width: int, height: int, fill: str = " "):
        self.width, self.height = width, height
        self.cells: List[List[Cell]] = [[Cell(fill) for _ in range(width)] for _ in range(height)]

    def in_bounds(self, x, y):
        return 0 <= x < self.width and 0 <= y < self.height

    def put(self, x, y, ch, fg=None, bg=None, keep_bg=False):
        if self.in_bounds(x, y):
            c = self.cells[y][x]
            c.ch = ch[:1] if ch else " "
            c.fg = fg
            if not keep_bg or bg is not None:
                c.bg = bg

    def get(self, x, y) -> Cell:
        return self.cells[y][x]

    def text(self, x, y, s, fg=None, bg=None):
        for i, ch in enumerate(s):
            self.put(x + i, y, ch, fg, bg)

    def blit(self, other: "Canvas", ox: int, oy: int, transparent: str = None):
        for y in range(other.height):
            for x in range(other.width):
                c = other.cells[y][x]
                if transparent is not None and c.ch == transparent:
                    continue
                self.put(ox + x, oy + y, c.ch, c.fg, c.bg)

    def to_text(self) -> str:
        return "\n".join("".join(c.ch for c in row).rstrip() for row in self.cells)

    def to_ansi(self, mode: str = "truecolor") -> str:
        """mode: 'none' | 'ansi16' | 'truecolor'"""
        if mode == "none":
            return self.to_text()
        out = []
        for row in self.cells:
            line, last = [], (None, None)
            for c in row:
                key = (c.fg, c.bg)
                if key != last:
                    line.append("\x1b[0m")
                    if c.fg is not None:
                        if mode == "ansi16":
                            i = nearest_ansi16(c.fg)
                            line.append(f"\x1b[{30 + i}m" if i < 8 else f"\x1b[{90 + i - 8}m")
                        else:
                            line.append(f"\x1b[38;2;{c.fg[0]};{c.fg[1]};{c.fg[2]}m")
                    if c.bg is not None:
                        if mode == "ansi16":
                            i = nearest_ansi16(c.bg)
                            line.append(f"\x1b[{40 + i}m" if i < 8 else f"\x1b[{100 + i - 8}m")
                        else:
                            line.append(f"\x1b[48;2;{c.bg[0]};{c.bg[1]};{c.bg[2]}m")
                    last = key
                line.append(c.ch)
            line.append("\x1b[0m")
            out.append("".join(line))
        return "\n".join(out)

    def to_html(self) -> str:
        import html
        rows = []
        for row in self.cells:
            spans = []
            for c in row:
                st = []
                if c.fg: st.append("color:#%02x%02x%02x" % c.fg)
                if c.bg: st.append("background:#%02x%02x%02x" % c.bg)
                spans.append(f'<span style="{";".join(st)}">{html.escape(c.ch)}</span>')
            rows.append("".join(spans))
        return ('<pre style="background:#000;color:#ccc;font:14px/1 monospace;display:inline-block">'
                + "\n".join(rows) + "</pre>")

    def lines(self) -> List[str]:
        return ["".join(c.ch for c in row) for row in self.cells]
