# 04 — Sandbox: modo de depuração em tempo real

> **Legacy design notes.** This plan shipped whole — the behaviour lives in
> [docs/concepts/sandbox.md](../docs/concepts/sandbox.md) and the code in
> `lagarto/sandbox.py`. The file is preserved because that module cites these
> section numbers (`plans/04 §3`, `§8`-`§12`) as the record of what each part
> was for; no other file carries the Q-decisions behind them. Canonical
> vocabulary in [CONTEXT.md](../CONTEXT.md); actionable work in GitHub Issues
> (see [docs/agents/issue-tracker.md](../docs/agents/issue-tracker.md)).

Spec de implementação. Ferramenta **dev-only** para invocar qualquer
entidade do jogo à mão e testá-la nos sistemas reais (mundo, colisão,
combate, HUD, câmera). Nasceu de: "preciso de um launcher pra spawnar
qualquer entidade sozinho e testar".

> Termos em **negrito** são canônicos — ver [CONTEXT.md](../CONTEXT.md).

---

## 1. Objetivo

Um **Sandbox**: um `Game` real, sem progressão forçada, com um overlay de
depuração que deixa o dev spawnar **Boss**/**Champion**/**Species**/pickup
onde quiser, montar loadout na hora, disparar rodadas parametrizadas, e
gerar loja — tudo pra observar comportamento e animação procedural em
isolamento.

Não é feature de jogador. Não aparece no menu. Só existe atrás de uma flag.

## 2. Entrada e gating

- `python lizard_game.py --sandbox` — parseado em `lagarto/app.py:main`,
  ao lado de `--smoke` (mesma leitura de `sys.argv`).
- Sem entrada no menu. Nenhum código de sandbox toca `menu.py`.
- Ship inofensivo: uma flag que ninguém passa. (Decisão Q14.)
- **1 jogador** apenas. As costuras de coop (`make_controllers(num,...)`,
  câmera dual) já existem; `--sandbox 2` é adição trivial futura se
  precisar testar coop. (Q13.)

## 3. Arquitetura

- **Reusa o `Game` inteiro** (Q2). `main` pula `run_menu`, constrói
  `Game(1, controllers, font, bigfont, mode='sandbox', chars=[preset.character])`
  e spawna o jogador como hoje.
- **`Rounds` não auto-inicia.** O spawner de ondas/boss só roda quando o
  dev pede pelo menu. Guarda mínima: em `Rounds.update`/start automático,
  `if game.mode == 'sandbox': return` (não avançar onda sozinho).
- **Módulo novo e isolado**: `lagarto/sandbox.py` (Q7). Um arquivo, dono
  do overlay + do controlador de sandbox + do preset. Zero acoplamento com
  a UI de produção. Fácil de deletar. (ADR-0010: single-file-per-module.)
- O loop principal em `app.main` ganha, no ramo sandbox, uma chamada por
  frame ao `Sandbox` (processa input do overlay, desenha por cima).

### Vocabulário único de spawn

Toda invocação — pelo menu **e** pelo preset — passa pela mesma tupla:

```
('boss',      '<boss_id>',           pos)   # ex ('boss','rei_lagarto',(1200,800))
('champion',  '<champ_id>:<species>', pos)  # ex ('champion','alfa:tank', None)
('species',   '<species_key>',        pos)  # ex ('species','snake', None)
('pickup',    'bug'|'fruit'|'egg',    pos)
```

`pos = None` → perto do jogador. Um único `spawn(kind, key, pos)` em
`sandbox.py` resolve a tupla e chama a fábrica certa. Menu, preset e
código de spawn compartilham esse caminho — sem divergência. (Q4/Q15.)

## 4. Prefactors (fazer antes, cada um seu commit)

Spawn **determinístico e específico** (Q4-A) exige duas extrações — úteis
além do sandbox:

1. **`rounds.make_boss(game, boss_id_or_key, tier, pos) -> boss`.**
   Hoje as ~80 linhas de montagem de **Boss** vivem inline em
   `Rounds._spawn_boss` (escala, hp, damping, `behavior='boss'`,
   `BossAI`, personality, emblem). Extrair pra fábrica reutilizável;
   `_spawn_boss` passa a só escolher o boss e chamar `make_boss`.
   `boss_id` vindo de `BOSS_POOL`; `tier` controla hp/xp/score.
2. **`champions.promote_to(creature, champ_id, game)`.**
   Hoje só existe `maybe_promote` (rola aleatório). Adicionar helper que
   aplica um **Champion** específico: `BY_ID[champ_id].apply(creature, game)`
   + `_rebuild`. `maybe_promote` passa a delegar nele.

`species.make(key, pos)` e os pickups (`Bug`/`Fruit`/`Egg`) já são fábricas
diretas — nada a extrair.

## 5. Overlay: menu dropdown

Painel imediato, desenhado por cima do jogo vivo, dirigido a **mouse**
(Q7-A). Tecla alterna aberto/fechado (`` ` `` ou `F1`); com o painel
fechado o jogo roda normal e cliques de spawn armado ainda funcionam.

Itens (Q3): **spawn entity · start round · reset round · generate store ·
equip instantly · kill-all · god mode · pause-AI/step · swap character**,
mais os botões **Save preset · Clear preset** (§11).

Dropdowns enumeram os ids válidos das registries (`species.SPECIES`,
`BOSS_POOL`, `champions.BY_ID`, `weapons.WEAPONS`, `items.ITEMS`,
`charms.CHARMS`, `characters.CHARACTERS`) — o dev nunca digita nome à mão.

## 6. Spawn entity (click-to-place, sticky)

- Escolher categoria+alvo no dropdown **arma** um spawn.
- Próximo clique-esquerdo no mundo coloca ali: `mouse` →
  `display.to_logical()` → `camera.s2w()` → pos no mundo. (Q5-A.)
- **Sticky** (Q6-A): fica armado; cada clique solta outro até cancelar
  (clique-direito / Esc). HUD mostra o nome do que está armado.
- **Boss**: `make_boss(...)` → `game.enemies.append`.
  **Champion**: `species.make(species, pos)` → `promote_to(c, champ_id)` →
  append. **Species**: `species.make` → `game.spawn_enemy` (fila) ou append
  direto conforme role. **Pickup**: `game.pickups.append`.

## 7. Start round (parametrizado)

- Dropdown de **theme** (9 chaves de `THEMES`: `enxame`, `cuspidores`,
  `tanques`, `aranhas`, `toca`, `revoada`, `estouro`, `praga`, `invasao`)
  + campo/rolagem de **wave** (int). (Q3.)
- `wave` sozinho já dita budget, tier, boss-a-cada-5 e final. Setar
  `game.rounds.wave = wave - 1` e chamar `start_round(theme)`, que faz
  `wave += 1` e monta a onda (mobs, nests, boss se `wave % 5 == 0`).
- Roda a máquina de ondas **real** — nada é reimplementado.

## 8. Reset round (só o campo)

Ação que limpa a cena e devolve o `Rounds` ao zero, **sem tocar o
jogador** (Q8-A):

- Esvazia `enemies`, `prey`, `projectiles`, `pickups`, `friends`, `boss`,
  `rounds.nests`, `rounds.marks`.
- Reseta estado do `Rounds` (`wave=0`, `state='intermission'`).
- Jogador mantém posição, vida, loadout, nível. Reseta a *cena*, não o
  sujeito do teste.

## 9. Generate store (loja parametrizada, dinheiro infinito)

Exercita o fluxo de compra **real** (`Game.camp_buy` → `_apply_buy`),
com a loja populada por você (Q9/Q10-B):

- Catálogo = ofertas nativas do camp (as 5 de `_roll_shop`:
  cura/vitalidade/vigor/charm/ovo) **+** qualquer **weapon**/**item**/
  **charm** embrulhado como entrada de loja com preço debug (default
  fixo, editável).
- Popular por **específico** (escolher ids) ou **random N**.
- Preços exibidos. `infinite_money`: setar `game.pollen` altíssimo, então
  `camp_buy` roda sem mudança (checagem `pollen < cost` nunca bloqueia).
- Cada weapon/item/charm vira uma entrada `dict(name, desc, cost, hue,
  icon, fn)` onde `fn` chama o grant real (`gain_weapon`/`items.give`/
  `gain_charm`).

## 10. Equip instantly (grant livre)

Atalho que pula a loja: dropdown sobre os pools reais — qualquer
**weapon** (`WEAPONS`), **item** (`ITEMS`), **charm** (`CHARMS`) ou
mutation (`evolution`) — clique aplica de graça no jogador via as APIs
existentes: `player.gain_weapon(id)`, `items.give(player, item, game)`,
`player.gain_charm(id, game)`, `Mutation.apply(player, game)`. (Q9-A.)

## 11. Staples de depuração

Semântica confirmada (Q12):

- **God mode** (toggle): jogador ignora aplicação de dano. Resto normal
  (energia, movimento, dash reais).
- **Kill-all** (ação): limpa `enemies` + `boss` + projéteis hostis.
  Mantém prey, pickups, friends, jogador.
- **Pause-AI** (toggle) + **Step**: congela `update` de enemies/boss — o
  jogador ainda anda em volta pra inspecionar a pose. **Step** avança
  *toda* a sim exatamente um tick fixo (`C.DT`), pra folhear a animação
  procedural quadro a quadro (o feature-chave pra trabalhar IK/leg cycle).
- **Swap character** (Q11): reconstrói o jogador como qualquer
  `Character` de `CHARACTERS` (arma/corpo inicial próprios).

## 12. Preset gerenciado por UI

O preset é autorado **pela própria UI**, nunca digitado à mão — os
dropdowns já conhecem os ids válidos (Q15).

- **Botão "Save preset"** (na tela): serializa o setup vivo —
  `character`, toggles (`god_mode`, `pause_ai`, `infinite_money`), **toda
  entidade viva** como `(kind, key, pos)`, o loadout atual do jogador, a
  rodada ativa `(theme, wave)` e a loja gerada.
- **Botão "Clear preset"** (na tela): apaga o arquivo.
- Persistência: **`~/.lagarto/sandbox.json`**, mesmo diretório e mesmo
  padrão de escrita atômica (tmp → rename) de `core/settings.py`.
- No launch `--sandbox`: se o arquivo existe → reconstrói a cena exata
  automaticamente; senão → abre ocioso (só a flag = sandbox vazio).
- A reconstrução usa o **mesmo** `(kind, key, pos)` e o mesmo
  `spawn()`/grant do menu. Um caminho, zero divergência.

## 13. Arquivos tocados

| Arquivo | Mudança |
|---|---|
| `lagarto/sandbox.py` | **novo** — overlay, controlador `Sandbox`, `Preset` I/O |
| `lagarto/app.py` | parse `--sandbox`; ramo que pula menu, constrói Game sandbox, chama `Sandbox` por frame |
| `lagarto/rounds.py` | extrair `make_boss(...)`; guarda `mode=='sandbox'` no auto-spawn |
| `lagarto/champions.py` | `promote_to(creature, champ_id, game)` |
| `lagarto/game.py` | `mode='sandbox'`; hook god-mode no caminho de dano; hook pause-AI/step no update |

Reusados sem alteração: `species.make`, `camera.s2w`, `display.to_logical`,
`camp_buy`/`_apply_buy`, `gain_weapon`/`items.give`/`gain_charm`,
`Mutation.apply`, `Bug`/`Fruit`/`Egg`.

## 14. Docs a atualizar

- `CONTEXT.md`: termo **Sandbox** (feito junto com esta spec).
- `docs/concepts/sandbox.md`: doc de conceito (comportamento observável).
- `docs/concepts/README.md`: linha no índice.
- **Sem ADR**: reversível, não surpreendente, sem trade-off difícil de
  desfazer — falha os 3 critérios (`docs/adr/README.md`).

## 15. Fora de escopo

- Coop (`--sandbox 2`) — costuras prontas, adiar.
- Botão de menu escondido — só a flag.
- Reset do jogador junto com a cena — ação separada só se sentir falta.
- Editar preço debug por item numa UI rica — default fixo basta no v1.
