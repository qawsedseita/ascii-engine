import json, os, tempfile, unittest
from asciiengine import default_kinds, Canvas, EngineError
from asciiengine.styles.style import Glyph, Style, StyleSet
from asciiengine.styles.library import StyleLibrary


class TestKindsCanvas(unittest.TestCase):
    def test_kinds(self):
        k = default_kinds()
        self.assertEqual(len(k.names()), 64)
        self.assertFalse(k.get("wall").walkable)
        self.assertTrue(k.get("wall").opaque)
        with self.assertRaises(EngineError) as cm:
            k.get("nope")
        self.assertEqual(cm.exception.code, "unknown_kind")

    def test_canvas_outputs(self):
        c = Canvas(3, 2)
        c.put(0, 0, "@", (255, 0, 0))
        c.text(0, 1, "ab")
        c.put(99, 99, "x")                      # out of bounds is ignored
        self.assertEqual(c.to_text(), "@\nab")
        self.assertIn("\x1b[38;2;255;0;0m", c.to_ansi())
        self.assertIn("\x1b[31m", c.to_ansi("ansi16"))   # (255,0,0) is nearest to ANSI 1
        self.assertIn("color:#ff0000", c.to_html())


class TestStyles(unittest.TestCase):
    def setUp(self):
        self.kinds, self.lib = default_kinds(), StyleLibrary()

    def test_all_builtin_cover_every_kind_and_validate(self):
        self.assertEqual(len(self.lib.names()), 12)
        for n in self.lib.names():
            self.assertEqual(self.lib.get(n).validate(self.kinds), [], n)

    def test_json_roundtrip(self):
        for n in self.lib.names():
            s = self.lib.get(n)
            self.assertEqual(Style.from_dict(json.loads(json.dumps(s.to_dict()))).to_dict(), s.to_dict(), n)

    def test_unknown_style_and_missing_field(self):
        with self.assertRaises(EngineError) as cm:
            self.lib.get("gameboy")
        self.assertIn("nethack", cm.exception.hint)
        with self.assertRaises(EngineError):
            Style.from_dict({"glyphs": {}})

    def test_create_save_load(self):
        with tempfile.TemporaryDirectory() as d:
            lib = StyleLibrary(user_dir=d)
            lib.create("meu", based_on="rogue", glyphs={"orc": {"ch": "O", "fg": "#00ff00"}}, save=True)
            self.assertTrue(os.path.exists(os.path.join(d, "meu.style.json")))
            lib2 = StyleLibrary(user_dir=d)
            self.assertEqual(lib2.get("meu").glyph("orc").fg, (0, 255, 0))
            with self.assertRaises(EngineError):
                lib.create("ruim", glyphs={"orc": "ÖÖ"})          # two chars / non-ascii in ascii style

    def test_blend_keeps_charset_honest(self):
        mix = self.lib.get("classic_ascii").blend(self.lib.get("unicode_detailed"), take=("glyphs",))
        self.assertEqual(mix.charset, "unicode")
        self.assertEqual(mix.validate(self.kinds), [])
        colors_only = self.lib.get("classic_ascii").blend(self.lib.get("dwarf_fortress"), take=("colors",))
        self.assertEqual(colors_only.charset, "ascii")             # no glyphs taken -> stays ascii
        self.assertEqual(colors_only.glyph("wall").ch, "#")
        self.assertEqual(colors_only.glyph("player").fg, self.lib.get("dwarf_fortress").glyph("player").fg)

    def test_tinted_is_monochrome_hue(self):
        r = self.lib.get("retro_terminal")
        for g in r.glyphs.values():
            self.assertLessEqual(g.fg[0], g.fg[1])                  # green dominant (r <= g)

    def test_styleset_categories(self):
        ss = StyleSet(self.lib.get("classic_ascii"))
        ss.set(self.lib.get("nethack"), ["entities"])
        self.assertEqual(ss.glyph("skeleton", "entities").ch, "Z")
        self.assertEqual(ss.glyph("wall", "structures").ch, "#")
        ss.set(self.lib.get("rogue"))                              # all categories resets overrides
        self.assertEqual(ss.describe(), {"default": "rogue"})
        self.assertEqual(StyleSet.from_dict(ss.to_dict()).describe(), ss.describe())


if __name__ == "__main__":
    unittest.main()
