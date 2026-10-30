import json
import unittest
from PIL import Image, ImageDraw
from asciiengine.imaging import (AsciiArt, AsciiSprite, image_to_ascii, sprite_sheet,
                                 connected_components, sprites_from_components, register_sprite_kind)
from asciiengine.core.kinds import default_kinds
from asciiengine.styles.library import StyleLibrary
from asciiengine.maps import LayeredMap


class ImagingTests(unittest.TestCase):
    def test_modes_dimensions_and_aspect(self):
        im = Image.new("RGB", (40, 20), "white")
        ImageDraw.Draw(im).rectangle((10, 5, 30, 15), fill="black")
        a = image_to_ascii(im, 20, mode="mono")
        self.assertEqual((a.width, a.height), (20, 5))
        self.assertEqual(a.source_size, (40, 20))
        for mode in ("color", "high-density", "minimal", "edges", "shaded"):
            result = image_to_ascii(im, 12, height=6, mode=mode)
            self.assertEqual((result.width, result.height), (12, 6))
        self.assertEqual(len(image_to_ascii(im, 10, height=4, mode="color").colors), 4)

    def test_transforms_and_background(self):
        im = Image.new("RGBA", (4, 2), (255, 0, 0, 255)); im.putpixel((0, 0), (0, 0, 0, 0))
        art = image_to_ascii(im, 4, height=2, remove_background=True, background_color=(255,0,0), background_tolerance=0)
        self.assertEqual(art.rows[0][0], " ")
        self.assertTrue(all(c == " " for row in art.rows for c in row))
        with self.assertRaises(Exception): image_to_ascii(im, 2, mode="nope")

    def test_serialization_and_sheet(self):
        im = Image.new("RGB", (8, 4), "white")
        ImageDraw.Draw(im).rectangle((0, 0, 3, 3), fill="black")
        sheet = sprite_sheet(im, (4, 4), names=["left", "right"])
        self.assertEqual([s.name for s in sheet], ["left", "right"])
        restored = AsciiSprite.from_json(sheet[0].to_json())
        self.assertEqual(restored.rows, sheet[0].rows)
        art = AsciiArt.from_json(image_to_ascii(im, 8, height=4).to_json())
        self.assertEqual(art.width, 8)

    def test_opaque_component_background_inference(self):
        im = Image.new("RGB", (7, 5), "white")
        ImageDraw.Draw(im).rectangle((2, 1, 4, 3), fill="black")
        self.assertEqual(connected_components(im, connectivity=4), [(2, 1, 3, 3)])

    def test_components_and_map_style_registration(self):
        im = Image.new("RGBA", (8, 5), (0, 0, 0, 0))
        d = ImageDraw.Draw(im); d.rectangle((1,1,2,2), fill="white"); d.rectangle((6,2,7,4), fill="white")
        boxes = connected_components(im, connectivity=4)
        self.assertEqual(boxes, [(1,1,2,2), (6,2,2,3)])
        sprites = sprites_from_components(im)
        self.assertEqual(len(sprites), 2)
        kinds = default_kinds(); style = StyleLibrary().get("classic_ascii")
        register_sprite_kind(sprites[0], kinds, style, "sprite_golem", glyph="G")
        m = LayeredMap(5, 5, kinds); m.add_entity("sprite_golem", 2, 2)
        self.assertEqual(m.entities[0]["kind"], "sprite_golem")
        self.assertEqual(style.glyph("sprite_golem").ch, "G")
        self.assertIn("sprite", kinds.get("sprite_golem").props)


if __name__ == "__main__": unittest.main()
