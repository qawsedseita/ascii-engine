import unittest
from asciiengine import default_kinds, EngineError
from asciiengine.styles.library import StyleLibrary
from asciiengine.styles.style import StyleSet
from asciiengine.styles.translator import StyleTranslator


def snapshot(kinds):
    return {n: (k.category, k.walkable, k.opaque) for n, k in kinds.all().items()}


class TestTranslator(unittest.TestCase):
    def setUp(self):
        self.kinds, self.lib = default_kinds(), StyleLibrary()
        self.tr = StyleTranslator(self.lib, self.kinds)
        self.ss = StyleSet(self.lib.get("classic_ascii"))

    def test_scenery_pt(self):
        r = self.tr.apply(self.ss, "Quero os cenários estilo Dwarf Fortress")
        self.assertEqual(r.instructions[0].categories, ["terrain", "structures"])
        self.assertEqual(self.ss.glyph("wall", "structures").ch, "#")
        self.assertEqual(self.ss.glyph("tree", "structures").ch, "♣")        # DF tree
        self.assertEqual(self.ss.glyph("orc", "entities").ch, "o")           # entities untouched (classic)
        self.assertEqual(self.ss.describe()["terrain"], "dwarf_fortress")
        self.assertNotIn("entities", self.ss.describe())

    def test_two_clauses_two_scopes(self):
        self.tr.apply(self.ss, "personagens estilo NetHack e cenário estilo Caves of Qud")
        d = self.ss.describe()
        self.assertEqual((d["entities"], d["terrain"], d["structures"]), ("nethack", "caves_of_qud", "caves_of_qud"))
        self.assertEqual(self.ss.glyph("skeleton", "entities").ch, "Z")

    def test_whole_game_then_override(self):
        self.tr.apply(self.ss, "jogo todo estilo Rogue, mas personagens estilo NetHack")
        d = self.ss.describe()
        self.assertEqual((d["default"], d["entities"]), ("rogue", "nethack"))

    def test_english_and_ui(self):
        self.tr.apply(self.ss, "make the UI and effects look like the amber terminal")
        d = self.ss.describe()
        self.assertEqual((d["ui"], d["effects"]), ("amber_terminal", "amber_terminal"))
        self.tr.apply(self.ss, "items in minimalist style")
        self.assertEqual(self.ss.describe()["objects"], "minimalist")

    def test_default_scope_is_everything(self):
        self.tr.apply(self.ss, "estilo NetHack")
        self.assertEqual(self.ss.describe(), {"default": "nethack"})

    def test_mix_default_base_first_colors_from_second(self):
        r = self.tr.apply(self.ss, "mistura NetHack com Dwarf Fortress")
        st = r.instructions[0].style
        self.assertTrue(r.instructions[0].mixed)
        nh, df = self.lib.get("nethack"), self.lib.get("dwarf_fortress")
        self.assertEqual(st.glyph("wall").ch, nh.glyph("wall").ch)
        self.assertEqual(st.glyph("grass").fg, df.glyph("grass").fg)
        self.assertEqual(st.validate(self.kinds), [])

    def test_mix_with_traits(self):
        r = self.tr.apply(self.ss, "glifos do Dwarf Fortress e cores do NetHack")
        st = r.instructions[0].style
        df, nh = self.lib.get("dwarf_fortress"), self.lib.get("nethack")
        self.assertEqual(st.glyph("player").ch, df.glyph("player").ch)       # ☺
        self.assertEqual(st.glyph("player").fg, nh.glyph("player").fg)
        self.assertEqual(st.charset, "cp437")
        self.assertEqual(st.validate(self.kinds), [])
        r2 = self.tr.parse("colors of Rogue with glyphs of Caves of Qud")
        self.assertEqual(r2[0].style.glyph("creature").ch, "8")

    def test_register_mix(self):
        r = self.tr.apply(self.ss, "mistura rogue com qud", register_mixes=True)
        self.assertIn(r.instructions[0].style.name, self.lib.names())

    def test_unknown_style_explains(self):
        with self.assertRaises(EngineError) as cm:
            self.tr.apply(self.ss, "personagens estilo gameboy")
        self.assertEqual(cm.exception.code, "unknown_style")
        self.assertIn("Available styles", cm.exception.hint)
        with self.assertRaises(EngineError) as cm:
            self.tr.parse("cenarios estilo nethak")                          # typo -> suggestion
        self.assertIn("nethack", cm.exception.hint)
        self.assertEqual(self.ss.describe(), {"default": "classic_ascii"})   # nothing applied on error

    def test_no_style_error(self):
        with self.assertRaises(EngineError) as cm:
            self.tr.parse("deixa tudo mais bonito")
        self.assertEqual(cm.exception.code, "no_style")

    def test_custom_library_style_is_recognised(self):
        self.lib.create("neon_city", based_on="ansi_modern")
        self.tr.apply(self.ss, "personagens estilo neon city")
        self.assertEqual(self.ss.describe()["entities"], "neon_city")

    def test_restyling_never_changes_gameplay(self):
        before = snapshot(self.kinds)
        for req in ["tudo estilo Dwarf Fortress", "mistura rogue com qud", "ui estilo minimalista",
                    "personagens estilo nethack utf8", "cenários estilo terminal verde"]:
            self.tr.apply(self.ss, req)
        self.assertEqual(snapshot(self.kinds), before)

    def test_convert_text_reports_ambiguity(self):
        art = "###\n#@o#\n###"
        out, warns = self.tr.convert_text(art, "classic_ascii", "dwarf_fortress")
        self.assertIn("☺", out)                      # @ -> player glyph of DF
        self.assertEqual(out.split("\n")[1][-2], "O")  # o -> orc: 'O' in DF ('o' is orc in classic, goblin is g)
        self.assertTrue(any("'#'" in w for w in warns))
        out2, w2 = self.tr.convert_text("@ Q", "classic_ascii", "nethack")
        self.assertTrue(any("left unchanged" in w and "Q" in w for w in w2))   # unknown char passes through, reported
        self.assertIn("Q", out2)


if __name__ == "__main__":
    unittest.main()
