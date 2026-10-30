"""Style translator: turns natural-language style requests (Portuguese or English) into changes on a StyleSet.

Examples it understands::

    "cenários estilo Dwarf Fortress"
    "personagens estilo NetHack e cenário estilo Caves of Qud"
    "mistura NetHack com Dwarf Fortress"
    "glifos do Rogue e cores do Caves of Qud"
    "make the whole game look like a green retro terminal"

Design rules
------------
* The translator only edits a ``StyleSet`` (appearance). It never touches kinds, maps or entities, so
  collisions, positions and gameplay cannot change when the style changes.
* It is deterministic keyword/pattern parsing, not an LLM: what it does not recognise it reports with an
  ``EngineError`` that lists what *is* available, instead of guessing.
* ``convert_text`` converts already-rendered ASCII art between styles. That direction is inherently lossy
  (one glyph can stand for several kinds); ambiguities are reported, never hidden.
"""
from __future__ import annotations

import difflib
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from ..core.errors import EngineError
from ..core.kinds import CATEGORIES, KindRegistry, default_kinds
from .library import StyleLibrary
from .style import Style, StyleSet


def _norm(s: str) -> str:
    """lower-case, strip accents, turn - _ / into spaces (so 'nethack-utf8' == 'nethack utf8')."""
    s = unicodedata.normalize("NFKD", s.lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[-_/]+", " ", s)


# real style name -> extra aliases (normalised). Library names are always aliases of themselves.
ALIASES: Dict[str, List[str]] = {
    "classic_ascii": ["classic ascii", "ascii classico", "ascii puro", "ascii simples", "plain ascii", "classico", "classic"],
    "rogue": ["rogue", "original rogue", "rogue classico"],
    "nethack": ["nethack", "net hack"],
    "nethack_utf8": ["nethack utf8", "nethack utf 8", "nethack unicode", "utf8graphics"],
    "dwarf_fortress": ["dwarf fortress", "dwarffortress", "dwarf fort", "df"],
    "caves_of_qud": ["caves of qud", "cavesofqud", "qud"],
    "cataclysm": ["cataclysm dda", "cataclysm", "cdda", "dda"],
    "retro_terminal": ["retro terminal", "terminal retro", "terminal verde", "green terminal", "green phosphor",
                       "fosforo verde", "crt verde", "terminal crt", "crt", "phosphor"],
    "amber_terminal": ["amber terminal", "terminal ambar", "fosforo ambar", "amber phosphor", "crt ambar", "ambar", "amber"],
    "minimalist": ["minimalist", "minimalista", "minimal", "minimo"],
    "unicode_detailed": ["unicode detailed", "unicode detalhado", "detalhado", "detailed", "unicode"],
    "ansi_modern": ["ansi modern", "ansi moderno", "terminal moderno", "modern terminal", "moderno", "modern", "truecolor"],
}

# scope words -> categories (matched on normalised text)
_SCOPE_PATTERNS: List[Tuple[str, List[str]]] = [
    (r"personagen\w*|criatura\w*|monstro\w*|inimig\w*|character\w*|creature\w*|monster\w*|enem\w*|entidade\w*|"
     r"entit\w*|npcs?|jogador\w*|player\w*|hero\w*|heroi\w*", ["entities"]),
    (r"cenario\w*|mapa\w*|terreno\w*|ambiente\w*|scener\w*|scenario\w*|environment\w*|terrain\w*|maps?|ground|chao",
     ["terrain", "structures"]),
    (r"parede\w*|wall\w*|estrutura\w*|structure\w*|porta\w*|door\w*", ["structures"]),
    (r"objeto\w*|iten\w*|item\w*|object\w*|loot|tesouro\w*", ["objects"]),
    (r"interface\w*|ui|hud|menu\w*|dialog\w*|painel|paineis|panel\w*", ["ui"]),
    (r"efeito\w*|effect\w*|particula\w*|particle\w*|fx", ["effects"]),
    (r"tudo|todo o jogo|jogo todo|jogo inteiro|everything|whole game|entire game|full game|"
     r"todas as categorias|all categories", list(CATEGORIES)),
]

# mix traits: words that, placed before a style mention, say *what to take* from that style
_TRAITS: List[Tuple[str, str]] = [
    (r"cor(?:es)?|colou?rs?|paleta|palette", "colors"),
    (r"simbolo\w*|glifo\w*|glyph\w*|symbol\w*|letras|letters|caracteres|chars", "glyphs"),
    (r"rampa|ramp|sombreamento|shading|densidade|density", "ramp"),
    (r"bordas|borders?|autotile|juncoes|junctions", "autotile"),
]
_TRAIT_TO_TAKE = {"colors": "colors", "glyphs": "glyphs", "ramp": "ramp", "autotile": "autotile"}

_CLAUSE_SPLIT = re.compile(
    r"\s*(?:[,;]|\.\s|\s+(?:e|and|mas|but|while|enquanto|porem|depois|then|also)\s+)\s*")
_STYLE_WORD = re.compile(r"\b(?:estilo|style|tipo|like|similar a|parecido com)\s+(?:de |do |da |of |the )?"
                         r"([a-z0-9]+(?:\s+[a-z0-9]+){0,2})")
_STOP_FIRST = {"com", "with", "e", "and", "para", "for", "de", "do", "da", "the", "a", "um", "uma", "mais", "more",
               "o", "as", "os", "no", "na", "nos", "nas", "em", "in", "to", "ao", "pra"}


def _wb(pattern: str) -> re.Pattern:
    return re.compile(r"(?<![a-z0-9])(?:" + pattern + r")(?![a-z0-9])")


@dataclass
class Instruction:
    categories: List[str]
    style: Style
    plan: str
    mixed: bool = False
    warnings: List[str] = field(default_factory=list)

    def to_dict(self):
        return {"categories": self.categories, "style": self.style.name, "mixed": self.mixed,
                "plan": self.plan, "warnings": self.warnings}


@dataclass
class TranslationResult:
    instructions: List[Instruction]
    styleset: Dict[str, str]

    def to_dict(self):
        return {"ok": True, "applied": [i.to_dict() for i in self.instructions], "styleset": self.styleset}


class StyleTranslator:
    def __init__(self, library: Optional[StyleLibrary] = None, kinds: Optional[KindRegistry] = None):
        self.library = library or StyleLibrary()
        self.kinds = kinds or default_kinds()
        self._scope_res = [(_wb(p), cats) for p, cats in _SCOPE_PATTERNS]
        self._trait_res = [(_wb(p), t) for p, t in _TRAITS]

    # ------------------------------------------------------------------ vocabulary
    def _alias_table(self) -> Dict[str, str]:
        table: Dict[str, str] = {}
        for real in self.library.names():
            table[_norm(real)] = real
        for real, al in ALIASES.items():
            if real in self.library.names():
                for a in al:
                    table.setdefault(_norm(a), real)
        return table

    def _mentions(self, text: str) -> List[Tuple[int, int, str]]:
        """Non-overlapping style mentions (start, end, style name), longest match wins."""
        found = []
        for alias, real in self._alias_table().items():
            for m in _wb(re.escape(alias).replace(r"\ ", r"\s+")).finditer(text):
                found.append((m.start(), m.end(), real))
        found.sort(key=lambda t: (-(t[1] - t[0]), t[0]))
        taken: List[Tuple[int, int, str]] = []
        for s, e, real in found:
            if all(e <= ts or s >= te for ts, te, _ in taken):
                taken.append((s, e, real))
        return sorted(taken)

    def _scopes(self, text: str) -> Set[str]:
        out: Set[str] = set()
        for rx, cats in self._scope_res:
            if rx.search(text):
                out.update(cats)
        return out

    def _check_unknown(self, text: str, mentions: List[Tuple[int, int, str]]):
        for m in _STYLE_WORD.finditer(text):
            cand = m.group(1)
            first = cand.split()[0]
            if first in _STOP_FIRST:
                continue
            start = m.start(1)
            if any(ms <= start < me for ms, me, _ in mentions):
                continue
            # a scope word right after "estilo" ("estilo cenario ...") is not a style name
            if any(rx.fullmatch(first) for rx, _ in self._scope_res):
                continue
            guess = cand
            close = difflib.get_close_matches(_norm(guess), list(self._alias_table()), n=3, cutoff=0.6)
            sugg = sorted({self._alias_table()[c] for c in close})
            raise EngineError(
                f"Unknown style '{guess}'",
                ("Did you mean: " + ", ".join(sugg) + "? " if sugg else "")
                + "Available styles: " + ", ".join(self.library.names())
                + ". Create a custom one with StyleLibrary.create(...).", "unknown_style")

    # ------------------------------------------------------------------ parsing
    def parse(self, request: str) -> List[Instruction]:
        """Interpret ``request`` without applying anything (a dry run / explanation)."""
        text = _norm(request)
        all_mentions = self._mentions(text)
        self._check_unknown(text, all_mentions)
        if not all_mentions:
            raise EngineError("No style recognised in the request",
                              "Name a style, e.g. 'cenários estilo Dwarf Fortress'. Available: "
                              + ", ".join(self.library.names()), "no_style")

        groups: List[dict] = []
        pending: Set[str] = set()
        for clause in [c for c in _CLAUSE_SPLIT.split(text) if c.strip()]:
            scopes, has_style = self._scopes(clause), bool(self._mentions(clause))
            if not has_style:
                pending |= scopes
                continue
            if not scopes and not pending and groups:      # "A e B" / "glifos do X e cores do Y": continuation
                groups[-1]["texts"].append(clause)
                continue
            groups.append({"scopes": scopes | pending, "texts": [clause]})
            pending = set()

        out = []
        for g in groups:
            cats = [c for c in CATEGORIES if c in g["scopes"]] or list(CATEGORIES)
            style, plan, mixed = self._resolve(" e ".join(g["texts"]), cats)
            warns = []
            miss = [k for k in self.kinds.names() if k not in style.glyphs]
            if miss:
                warns.append(f"style '{style.name}' lacks {len(miss)} kinds (rendered as '?'): " + ", ".join(miss[:8]))
            out.append(Instruction(cats, style, plan, mixed, warns))
        if pending:
            out[-1].warnings.append("scope words without a style were ignored: " + ", ".join(sorted(pending)))
        return out

    def _traits_in(self, segment: str) -> List[str]:
        return [t for rx, t in self._trait_res if rx.search(segment)]

    def _resolve(self, text: str, cats: List[str]) -> Tuple[Style, str, bool]:
        ms = self._mentions(text)
        if len(ms) == 1:
            st = self.library.get(ms[0][2])
            return st, f"apply '{st.name}' to {', '.join(cats)}", False
        # mix: traits written *before* each style mention say what to take from it
        parts, prev = [], 0
        for s, e, name in ms:
            parts.append((name, self._traits_in(text[prev:s])))
            prev = e
        base_i = next((i for i, (_, t) in enumerate(parts) if "glyphs" in t), None)
        if base_i is None:
            base_i = next((i for i, (_, t) in enumerate(parts) if not t), 0)
        base = self.library.get(parts[base_i][0])
        notes = [f"base = '{base.name}'" + (f" (glyphs)" if "glyphs" in parts[base_i][1] else "")]
        result = base
        for i, (name, traits) in enumerate(parts):
            if i == base_i or name == base.name:
                continue
            other = self.library.get(name)
            if not traits:
                traits = ["colors"]
                notes.append(f"'{name}' gave colors (default when no trait is named)")
            else:
                notes.append(f"'{name}' gave " + "+".join(traits))
            result = result.blend(other, take=tuple(_TRAIT_TO_TAKE[t] for t in traits))
        result.description = (f"Mix: {'; '.join(notes)}")
        return result, f"mix ({'; '.join(notes)}) applied to {', '.join(cats)}", True

    # ------------------------------------------------------------------ applying
    def apply(self, styleset: StyleSet, request: str, register_mixes: bool = False) -> TranslationResult:
        """Parse ``request`` and apply it to ``styleset``. Only appearance changes."""
        instr = self.parse(request)
        for i in instr:
            if i.mixed and register_mixes:
                self.library.add(i.style)
            styleset.set(i.style, None if set(i.categories) >= set(CATEGORIES) else i.categories)
        return TranslationResult(instr, styleset.describe())

    # ------------------------------------------------------------------ rendered text conversion
    def convert_text(self, text: str, source: str, target: str) -> Tuple[str, List[str]]:
        """Convert already-rendered ASCII art from one style to another.

        LOSSY by nature: a glyph may stand for several kinds (e.g. '#' = wall / corridor / tree). The most
        structural kind wins (structures > terrain > entities > objects > effects > ui) and every ambiguity
        is reported in the returned warnings. Characters the source style doesn't use pass through unchanged.
        For lossless restyling render from a map instead (kinds are kept there).
        """
        src, dst = self.library.get(source), self.library.get(target)
        prio = {c: i for i, c in enumerate(["structures", "terrain", "entities", "objects", "effects", "ui"])}
        by_glyph: Dict[str, List[str]] = {}
        for kind, g in src.glyphs.items():
            by_glyph.setdefault(g.ch, []).append(kind)
        chosen: Dict[str, str] = {}
        warns: List[str] = []
        used = set(text)
        for ch, kinds in by_glyph.items():
            kinds.sort(key=lambda k: (prio.get(self.kinds.category_of(k), 9), k))
            chosen[ch] = kinds[0]
            if ch in used and ch != " " and len(kinds) > 1:
                warns.append(f"ambiguous glyph {ch!r} in '{src.name}' could be {', '.join(kinds)}; assumed '{kinds[0]}'")
        out = []
        for ch in text:
            kind = chosen.get(ch) if ch != "\n" else None
            g = dst.glyph(kind) if kind else None
            out.append(g.ch if g else ch)
        unknown = sorted({c for c in used if c not in chosen and c not in " \n"})
        if unknown:
            warns.append("characters not in the source style, left unchanged: " + "".join(unknown))
        return "".join(out), warns
