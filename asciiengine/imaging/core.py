"""Image-to-ASCII tools. Pillow is intentionally isolated to this package.

Gameplay remains semantic: sprites can register a one-cell entity kind and a style glyph;
image pixels never participate in collision, movement, or visibility.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Optional

from ..core.errors import EngineError
from ..core.kinds import KindDef, KindRegistry
from ..styles.style import Glyph, Style

try:
    from PIL import Image, ImageEnhance, ImageFilter, ImageOps
except ImportError:  # pragma: no cover - environment-specific
    Image = ImageEnhance = ImageFilter = ImageOps = None

MODES = {"mono", "color", "high-density", "minimal", "edges", "shaded"}
DEFAULT_RAMP = " .:-=+*#%@"
MINIMAL_RAMP = " .oO@"


def _pillow():
    if Image is None:
        raise EngineError("Pillow is required for image conversion", "Install Pillow to use asciiengine.imaging", "missing_pillow")


def _open_image(source):
    _pillow()
    try:
        if isinstance(source, Image.Image):
            return source.copy()
        if isinstance(source, (str, Path)):
            return Image.open(source)
        if hasattr(source, "read"):
            return Image.open(source)
    except Exception as exc:
        raise EngineError(f"Could not read image: {exc}", "Pass a valid image path, file object, or PIL Image", "bad_image") from exc
    raise EngineError("Unsupported image source", "Pass a path, file object, or PIL Image", "bad_image")


def _ramp_index(lum: float, ramp: str) -> int:
    # Ramps run from light/empty to dark/dense.
    return min(len(ramp) - 1, max(0, int(round((1.0 - lum / 255.0) * (len(ramp) - 1)))))


def _rgb_to_ansi(rgb, palette):
    if not palette:
        return tuple(int(max(0, min(255, c))) for c in rgb)
    return min(palette, key=lambda p: sum((int(rgb[i]) - p[i]) ** 2 for i in range(3)))


@dataclass
class AsciiArt:
    """ASCII conversion result with optional per-cell RGB colors."""
    rows: list[str]
    colors: Optional[list[list[Optional[tuple[int, int, int]]]]] = None
    mode: str = "mono"
    source_size: tuple[int, int] = (0, 0)

    @property
    def width(self):
        return max((len(row) for row in self.rows), default=0)

    @property
    def height(self):
        return len(self.rows)

    def to_text(self) -> str:
        return "\n".join(self.rows)

    def to_json(self) -> dict:
        return {"rows": self.rows, "colors": self.colors, "mode": self.mode, "source_size": list(self.source_size)}

    @classmethod
    def from_json(cls, data: dict) -> "AsciiArt":
        return cls(list(data["rows"]), data.get("colors"), data.get("mode", "mono"), tuple(data.get("source_size", (0, 0))))


def image_to_ascii(source, width: int = 80, *, height: Optional[int] = None, mode: str = "mono",
                   ramp: Optional[str] = None, charset: Optional[str] = None, brightness: float = 1.0,
                   contrast: float = 1.0, density: float = 1.0, palette: Optional[Iterable] = None,
                   remove_background: bool = False, background_color=None, background_tolerance: float = 30,
                   preserve_aspect: bool = True, cell_aspect: float = 2.0, style: Optional[Style] = None) -> AsciiArt:
    """Convert an image to character rows. ``cell_aspect`` is terminal cell height/width (~2).

    Modes: mono/color use a luminance ramp, high-density uses an extended ramp, minimal
    uses a compact ramp, edges emphasizes outlines, shaded maps luminance to block shades.
    Alpha and optional near-background color removal produce empty cells.
    """
    if mode not in MODES:
        raise EngineError(f"Unknown image conversion mode '{mode}'", f"Choose one of {sorted(MODES)}", "bad_mode")
    if width < 1 or (height is not None and height < 1):
        raise EngineError("Output dimensions must be positive", "Set width and height to at least 1", "bad_size")
    if cell_aspect <= 0 or density < 0:
        raise EngineError("cell_aspect must be positive and density non-negative", "Use cell_aspect≈2 and density between 0 and 2", "bad_parameter")
    if brightness < 0 or contrast < 0:
        raise EngineError("brightness and contrast must be non-negative", "Use 1.0 for no adjustment", "bad_parameter")
    img = _open_image(source).convert("RGBA")
    source_size = img.size
    if height is None:
        if preserve_aspect:
            height = max(1, round(width * img.height / img.width / cell_aspect))
        else:
            height = max(1, round(width * img.height / img.width))
    img = img.resize((width, height), Image.Resampling.LANCZOS)
    rgb_img = img.convert("RGB")
    if brightness != 1.0:
        rgb_img = ImageEnhance.Brightness(rgb_img).enhance(brightness)
    if contrast != 1.0:
        rgb_img = ImageEnhance.Contrast(rgb_img).enhance(contrast)
    gray = ImageOps.grayscale(rgb_img)
    if mode == "edges":
        gray = gray.filter(ImageFilter.FIND_EDGES)
    elif mode == "shaded":
        gray = gray.filter(ImageFilter.SMOOTH)
    active_ramp = ramp or (style.ramp if style else None) or (" ░▒▓█" if mode == "shaded" else (" .,:;irsXA253hMHGS#9B&@" if mode == "high-density" else MINIMAL_RAMP if mode == "minimal" else DEFAULT_RAMP))
    if not active_ramp:
        raise EngineError("Character ramp cannot be empty", "Provide a non-empty ramp", "bad_ramp")
    if charset:
        active_ramp = "".join(ch for ch in active_ramp if (charset == "ascii" and ord(ch) < 128) or charset != "ascii")
        if not active_ramp:
            raise EngineError("Ramp has no characters in the requested charset", "Use ASCII ramp characters or omit charset", "bad_ramp")
    if density != 1.0:
        active_ramp = active_ramp[:max(1, min(len(active_ramp), round(len(active_ramp) * density)))]
    bg = tuple(background_color) if background_color is not None else None
    if palette is None and style is not None and style.palette:
        palette = [tuple(c) for c in style.palette.values() if c is not None]
    colors_out = [] if mode == "color" else None
    rows = []
    for y in range(height):
        chars, color_row = [], []
        for x in range(width):
            r, g, b, a = img.getpixel((x, y))
            is_bg = a == 0 or (remove_background and bg is not None and sum((v - bg[i]) ** 2 for i, v in enumerate((r, g, b))) ** 0.5 <= background_tolerance)
            lum = gray.getpixel((x, y))
            if mode == "edges":
                lum = min(255, lum * 2)
            if mode == "shaded":
                shades = " ░▒▓█"
                idx = min(len(shades) - 1, int(lum / 256 * len(shades)))
                ch = shades[idx]
            else:
                ch = active_ramp[_ramp_index(lum, active_ramp)]
            chars.append(" " if is_bg else ch)
            if mode == "color":
                col = _rgb_to_ansi((r, g, b), palette)
                color_row.append(None if is_bg else col)
        rows.append("".join(chars))
        if colors_out is not None:
            colors_out.append(color_row)
    return AsciiArt(rows, colors_out, mode, source_size)


@dataclass
class AsciiSprite:
    """A compact ASCII sprite. Map integration uses one representative glyph per entity cell."""
    rows: list[str]
    name: str = "sprite"
    colors: Optional[list[list[Optional[tuple[int, int, int]]]]] = None
    metadata: dict = field(default_factory=dict)

    @property
    def width(self): return max((len(r) for r in self.rows), default=0)
    @property
    def height(self): return len(self.rows)

    def to_dict(self):
        return {"name": self.name, "rows": self.rows, "colors": self.colors, "metadata": self.metadata}

    def to_json(self): return json.dumps(self.to_dict(), ensure_ascii=False, separators=(",", ":"))

    @classmethod
    def from_json(cls, payload):
        d = json.loads(payload) if isinstance(payload, str) else payload
        return cls(list(d["rows"]), d.get("name", "sprite"), d.get("colors"), dict(d.get("metadata", {})))

    def representative_glyph(self, fallback: str = "?") -> str:
        chars = [ch for row in self.rows for ch in row if not ch.isspace()]
        return max(set(chars), key=lambda c: (chars.count(c), c)) if chars else fallback

    @classmethod
    def from_art(cls, art: AsciiArt, name="sprite"):
        return cls(list(art.rows), name, art.colors, {"source_size": list(art.source_size), "mode": art.mode})


def sprite_sheet(source, cell_size: tuple[int, int], *, names: Optional[list[str]] = None) -> list[AsciiSprite]:
    """Split an image into row-major fixed-size cells and convert each cell to a small sprite."""
    img = _open_image(source)
    cw, ch = cell_size
    if cw < 1 or ch < 1:
        raise EngineError("Sprite-sheet cell dimensions must be positive", "Use (cell_width, cell_height)", "bad_size")
    sprites = []
    for y in range(0, img.height - ch + 1, ch):
        for x in range(0, img.width - cw + 1, cw):
            idx = len(sprites)
            name = names[idx] if names and idx < len(names) else f"sprite_{idx}"
            art = image_to_ascii(img.crop((x, y, x + cw, y + ch)), width=cw, height=ch, mode="mono", preserve_aspect=False)
            sprites.append(AsciiSprite.from_art(art, name))
    if not sprites:
        raise EngineError("Sprite sheet contains no complete cells", "Check cell size against image dimensions", "empty_sheet")
    return sprites


def connected_components(source, *, threshold: int = 1, connectivity: int = 8, background_color=None, background_tolerance: float = 0) -> list[tuple[int, int, int, int]]:
    """Return (x,y,w,h) boxes for connected foreground. Transparent pixels are background;
    for opaque images, the top-left pixel is the inferred background unless explicitly supplied."""
    img = _open_image(source).convert("RGBA")
    if connectivity not in (4, 8):
        raise EngineError("Connectivity must be 4 or 8", "Choose 4 or 8", "bad_connectivity")
    pixels = img.load(); w, h = img.size
    has_transparency = any(pixels[x,y][3] < 255 for y in range(h) for x in range(w))
    bg = tuple(background_color) if background_color is not None else (pixels[0,0][:3] if not has_transparency else None)
    def foreground(x, y):
        r,g,b,a = pixels[x,y]
        if a < threshold: return False
        if has_transparency: return a > 0
        return bg is None or sum((v-bg[i])**2 for i,v in enumerate((r,g,b)))**0.5 > background_tolerance
    active = {(x, y) for y in range(h) for x in range(w) if foreground(x,y)}
    comps = []
    while active:
        seed = active.pop(); stack = [seed]; xs = [seed[0]]; ys = [seed[1]]
        while stack:
            x, y = stack.pop()
            neighbors = [(x+dx, y+dy) for dy in (-1,0,1) for dx in (-1,0,1) if (dx or dy) and (connectivity == 8 or abs(dx)+abs(dy)==1)]
            for p in neighbors:
                if p in active:
                    active.remove(p); stack.append(p); xs.append(p[0]); ys.append(p[1])
        comps.append((min(xs), min(ys), max(xs)-min(xs)+1, max(ys)-min(ys)+1))
    return sorted(comps, key=lambda b: (b[1], b[0]))


def sprites_from_components(source, *, connectivity: int = 8, name_prefix: str = "sprite") -> list[AsciiSprite]:
    img = _open_image(source).convert("RGBA")
    result = []
    for i, box in enumerate(connected_components(img, connectivity=connectivity)):
        art = image_to_ascii(img.crop((box[0], box[1], box[0]+box[2], box[1]+box[3])), width=box[2], height=box[3], mode="mono", preserve_aspect=False)
        result.append(AsciiSprite.from_art(art, f"{name_prefix}_{i}"))
    return result


def register_sprite_kind(sprite: AsciiSprite, registry: KindRegistry, style: Style, kind_name: str,
                         *, glyph: Optional[str] = None, description: Optional[str] = None) -> str:
    """Register a semantic entity kind and its display glyph. Does not alter map/game logic."""
    ch = glyph or sprite.representative_glyph()
    if len(ch) != 1:
        raise EngineError("Entity glyph must be one character", "Choose a single terminal cell glyph", "bad_glyph")
    registry.register(KindDef(kind_name, "entities", False, False, description or f"Custom sprite: {sprite.name}",
                              {"sprite": sprite.to_dict()}))
    fg = style.palette.get("fg")
    if fg is None and style.palette:
        fg = next(iter(style.palette.values()))
    style.glyphs[kind_name] = Glyph(ch, fg)
    return kind_name
