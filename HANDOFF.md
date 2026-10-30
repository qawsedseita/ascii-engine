# HANDOFF — ASCII Engine (estado em 2026-10-30, após stages 4–8)

## Objetivo
Engine de jogos ASCII operada por IAs. Três sistemas obrigatórios, integrados entre si:
(1) tradutor/conversor de estilos, (2) editor de mapas para IA, (3) conversor imagem→ASCII.
Requisitos: modular, testada, documentada (`AI_GUIDE.md`), sem simular o que não existe.
Fluxo de integração a demonstrar no fim: imagem de criatura → ASCII → ajuste de estilo → inserção no mapa → teste no jogo.
Exemplo obrigatório: "dungeon estilo NetHack com 20 salas, corredores conectados, iluminação limitada e criaturas distribuídas".

## Decisões de arquitetura (valem sobre qualquer suposição)
- Python 3.12, **stdlib only** no núcleo; Pillow (já disponível no sandbox) só no módulo `imaging`. Testes com `unittest` (sem pytest).
- **A lógica nunca depende de glifos.** Tudo é um *kind* semântico (`wall`, `orc`...) com propriedades (walkable/opaque).
  Estilo = mapa kind→glifo. Trocar estilo não altera colisão/posição/visão (provado por `LayeredMap.logic_signature()` nos testes).
- Camadas do mapa: terrain, structures, objects, entities, lighting (luzes/regiões lit), effects.
- Categorias de estilo aplicáveis separadamente (`StyleSet`): terrain, structures, objects, entities, ui, effects.
- Erros sempre `EngineError(message, hint, code)` com dica acionável; comandos de IA devolvem dict `{"ok":False,"code","error","hint"}`.
- Áudio: backend abstrato; síntese WAV com stdlib; reprodução real via comando do SO — **NÃO testável no sandbox; declarar isso**.
- Sandbox sem rede: sem push para GitHub; entregar zip e o usuário publica.

## Pesquisa usada nos estilos (referências gravadas em `Style.references`)
NetHack (nethackwiki Symset / UTF8graphics / Custom map symbols), Dwarf Fortress wiki (Color, Tileset, Map legend: CP437, 16 cores, fg+bg por tile),
Caves of Qud wiki (Visual Style: 80x25, 3 cores por tile; letras=criaturas, dígitos=robôs), Cataclysm DDA (fórum: box-drawing, cor integrada ao símbolo),
r/roguelikedev FAQ Friday #28, convenções do Rogue. São regras re-implementadas, não assets copiados.

## Estado atual — 71 testes passando (`python3 -m unittest discover -s tests -t .`)
Repo local importado do zip. Stages de `imaging/` até `aitools/docs/examples` implementados e testados; stages 4–8 estão commitados. Pacote final ainda será gerado fora da árvore do repositório. Não houve push de rede.

| Módulo | Estado | Cobertura |
|---|---|---|
| `core/`, `styles/`, `maps/` | feito | testes originais de estilos, tradução, mapas, editor, FOV/render e geração |
| `imaging/` | feito | conversão sintética, modos, proporção, remoção de fundo, sprites/sheets/componentes e kinds semânticos |
| `world/` | feito | movimento, colisão viva, combate, inventário, IA simples, câmera e save/load |
| `fx/` + `ui/` | feito | ciclo de vida de efeitos/animações e renderização de widgets |
| `audio/` | feito, reprodução real não verificada | WAV stdlib, canais, atenuação posicional e backend silencioso |
| `plugins.py`, `aitools/`, CLI | feito | lifecycle de plugin, dispatch estruturado, exemplos de CLI |
| docs, templates, examples | feito | AI_GUIDE, API, catálogo de estilos, dungeon NetHack 20 salas e fluxo imagem→jogo |

Estilos built-in: classic_ascii, rogue, nethack, nethack_utf8, dwarf_fortress, caves_of_qud, cataclysm, retro_terminal,
amber_terminal, minimalist, unicode_detailed, ansi_modern.

## API existente (cola rápida)
```python
from asciiengine import default_kinds, EngineError, Canvas
from asciiengine.styles.library import StyleLibrary
from asciiengine.styles.style import Style, StyleSet, Glyph
from asciiengine.styles.translator import StyleTranslator
from asciiengine.maps import (LayeredMap, MapEditor, dungeon, cave, biome, generate, populate,
                              validate_map, astar, player_view, render_map, render_text)
from asciiengine.imaging import image_to_ascii, AsciiSprite, register_sprite_kind
from asciiengine.world import GameWorld
from asciiengine.aitools import EngineTools

lib = StyleLibrary(user_dir="styles_user"); ss = StyleSet(lib.get("classic_ascii"))
StyleTranslator(lib).apply(ss, "personagens estilo NetHack e cenário estilo Dwarf Fortress")
m = dungeon(80, 40, rooms=20, seed=11, lit_ratio=0.2); populate(m, seed=11)
m.add_entity("player", *m.spawn, props={"faction": "heroes"})
world = GameWorld(m); world.step(world.player_id, 1, 0)
print(EngineTools(m, library=lib).playtest())
```
- Conversão de imagem e exemplo completo: `examples/image_sprite_to_map.py`; dungeon obrigatório: `examples/nethack_dungeon.py`.
- Comandos do editor: set rect line room corridor door fill replace copy move remove region spawn exit collision place light inspect validate stats undo redo (`maps/editor.py` → `SIGNATURES`).
- `playtest()` valida o mapa e rota de spawn até saída; não simula uma sessão completa.
- Entidades de imagem continuam uma célula lógica. Arte sprite multicaractere fica como metadado, não footprint/colisão.

## Trabalho restante
- Fazer revisão final de segurança/qualidade e executar todos os testes/exemplos.
- Criar o zip excluindo `.git` e `__pycache__`, entregar ao usuário para publicação. Sandbox sem rede: sem push GitHub.

## Limites conhecidos (não esconder)
- Tradutor é parsing por palavras-chave PT/EN, não LLM; fora do vocabulário → erro explicativo com sugestões.
- `convert_text` (arte já renderizada → outro estilo) é lossy: glifo ambíguo escolhe o kind mais estrutural e avisa.
- `Style.validate` só checa `ascii` de verdade; não confere se cada glifo existe no CP437.
- `collision` override afeta andar, não visão. Conectividade validada em 4 direções (mais estrita que 8).
- Estilos sem autotile mostram glifo fixo para porta aberta (a convenção perpendicular só existe via autotile).

## Armadilhas já encontradas
- `/bin/sh` é dash: sem brace expansion (`mkdir -p a/{b,c}`) e sem `time`; use `bash -c '...'`.
- `Glyph` aceita cores como '#rrggbb' / 'ansi:N' / tupla. Typo de chave em `color_over` quebra o build do estilo (KeyError).
- (255,0,0) mapeia para ANSI 1, não 9 (distância euclidiana na paleta de 16): cuidado em testes de cor.
- FOV: um corredor alinhado com a porta REALMENTE enxerga a sala iluminada em linha reta; não é bug.
- Ao escrever expectativas de teste de geometria, conferir raio (usa `r² + r`) e coordenadas absolutas antes de culpar o código.

## Regra de honestidade
Só marcar um sistema como concluído após implementado **e** coberto por teste passando. Áudio: reprodução real não verificada.

## Continuation update — completed stages 4–8
- `imaging/` implemented: conversion modes, style ramps/palettes, sprites, sheets, connected components, JSON, semantic entity registration. Tests cover synthetic images and map/style registration.
- `world/` implemented: turn runtime, combat, inventory/equip, basic pursuit AI, movement collision, push, camera, JSON save/load.
- `fx/` + `ui/` implemented: timed semantic effects/animations and terminal menu/dialogue/HUD widgets.
- `audio/` implemented: events, channel gains, positional attenuation, transitions, standard-library WAV synthesis, null and OS-command playback backends. Device playback remains explicitly unverified.
- `plugins.py`, `aitools/`, `python -m asciiengine`, `AI_GUIDE.md`, docs, templates, integration examples, and integration tests added.
- End-to-end example exercises synthetic image → ASCII sprite → style translation → map entity → world turn. Required 20-room NetHack example is in `examples/nethack_dungeon.py`.
- Validation at this checkpoint: `python3 -m unittest discover -s tests -t .` (71 tests at this checkpoint). Each stage has its own commit; no network push attempted.
