# CLAUDE.md — Lagarto (jogo com animação procedural)

Contexto permanente do projeto para agentes. Este arquivo é um **índice**
— toda substância técnica vive em `docs/concepts/`, `docs/adr/`,
`docs/agents/`, e no glossário em `CONTEXT.md`. Leia primeiro os docs
relevantes ao que você vai mexer.

## O que é

Jogo em **pygame** onde você controla um **lagarto animado 100%
proceduralmente** (sem sprites/quadros). Mistura exploração/coleta com
caça/combate por dash. Suporta singleplayer e coop local de 2 jogadores.

Origem: evoluído de `procedural_animation.py` (cobra follow-the-leader).
Esse arquivo e `pygamebase.py` ficam **intactos como referência**.

## Como rodar

Ver [Running](docs/concepts/running.md).

Resumo: `python lizard_game.py` (menu) / `--smoke 90` (headless).

## Onde tudo mora

Cada seção aponta pro doc canônico. Se um doc está desatualizado, esse
é o lugar de corrigir — não este arquivo.

### Arquitetura

- [Architecture](docs/concepts/architecture.md) — pacote `lagarto/`,
  subpackage `core/`, e a tabela módulo → responsabilidade.
- [ADR-0010](docs/adr/0010-single-file-per-module.md) — por que não
  voltar a arquivo único.

### Anatomia e animação

- [Genome](docs/concepts/genome.md) · [Spine](docs/concepts/spine.md) ·
  [Leg](docs/concepts/leg.md) · [Parts](docs/concepts/parts.md) ·
  [Body plan](docs/concepts/body-plan.md).
- [Procedural animation](docs/concepts/procedural-animation.md) —
  Intent / Action / Reaction / Follow-through.
- [ADR-0001](docs/adr/0001-genome-is-the-creature.md) — criatura = genoma.
- [ADR-0007](docs/adr/0007-cosmetic-skeleton-for-tail.md) — sim/draw
  split para a cauda.

### Criaturas e IA

- [Species](docs/concepts/species.md) · [Character](docs/concepts/character.md) ·
  [Champion](docs/concepts/champion.md) · [Boss](docs/concepts/boss.md).
- [AI](docs/concepts/ai.md) — behaviors dispatch.
- [Enemy behaviors](docs/concepts/enemy-behaviors.md) — phase-2 species
  e a regra do telegrafo.
- [ADR-0004](docs/adr/0004-boss-pool-per-tier.md) — pool de chefe por tier.

### Combate

- [Combat](docs/concepts/combat.md) — dash, whip (rabada), tongue,
  soft-contact, clog.
- [Projectile](docs/concepts/projectile.md) — a bala e seus três ganchos
  (`on_update` / `on_hit` / `on_death`).
- [Weapon](docs/concepts/weapon.md) · [Item](docs/concepts/item.md) ·
  [Charm](docs/concepts/charm.md) · [Synergy](docs/concepts/synergy.md).
- [Hitbox](docs/concepts/hitbox.md) — corpo inteiro + cabeça é ponto
  fraco. [Damage](docs/concepts/damage.md) — modelo de vida.
- [ADR-0006](docs/adr/0006-soft-player-contact.md) — contato macio.
- [ADR-0008](docs/adr/0008-might-scales-all-damage.md) — `might` escala
  armas + dash + rabada.
  [ADR-0014](docs/adr/0014-bullet-colour-encodes-side.md) — cor da bala
  codifica o lado, não a criatura.

### Run e progressão

- [Gameloop](docs/concepts/gameloop.md) · [Game modes](docs/concepts/game-modes.md)
  (NORMAL / INFINITO) · [Sandbox](docs/concepts/sandbox.md) (`--sandbox`, dev,
  não é um modo).
- [Round](docs/concepts/round.md) · [Camp](docs/concepts/camp.md) ·
  [Evolution](docs/concepts/evolution.md) · [Progression](docs/concepts/progression.md).
- [ADR-0005](docs/adr/0005-camp-is-a-physical-clearing.md) — camp é
  clareira andável.
- [Balance](docs/concepts/balance.md) — duas passadas registradas; regras
  de balanceamento futuras.

### UI e feel

- [UI screens](docs/concepts/ui-screens.md) — level-up / camp entry +
  absorção da escolha.
- [UI legibility](docs/concepts/ui-legibility.md) — texto + TopStack.
- [Health HUD](docs/concepts/health-hud.md) · [Juice](docs/concepts/juice.md) ·
  [Icons & audio](docs/concepts/icons-audio.md).
- [ADR-0003](docs/adr/0003-zero-assets-with-png-fallback.md) — invariante
  zero-assets quebrada de propósito.

### Input e runtime

- [Controls](docs/concepts/controls.md) · [Input buffer](docs/concepts/input-buffer.md) ·
  [Pause](docs/concepts/pause.md).
- [Performance](docs/concepts/performance.md) — timestep fixo, glow
  cache, texto cacheado, transformada de câmera cacheada,
  `RENDER_FPS = SIM_HZ`. Como medir sem se enganar está lá também.
- [ADR-0002](docs/adr/0002-fixed-timestep-decoupled-render.md) — o loop
  determinístico. [ADR-0009](docs/adr/0009-glow-cache-quantized-keys.md)
  — chave de brilho quantizada.
  [ADR-0011](docs/adr/0011-camera-transform-cached-on-property-writes.md)
  — `w2s` cacheada; nunca mutar vetor de câmera in-place.
- [Networking](docs/concepts/networking.md) — coop local hoje; costuras
  prontas para online.

### Meta

- [CONTEXT.md](CONTEXT.md) — glossário canônico (Genome, Charm, Might,
  Mood, Tier, Telegraph, Cosmetic Skeleton, etc.).
- [docs/README.md](docs/README.md) — mapa da árvore de docs.
- [docs/adr/README.md](docs/adr/README.md) — regra dos 3-critérios pra ADR.
- [docs/agents/](docs/agents/) — issue tracker, triage labels, domain
  skill, regra de verificação.

## Convenções mínimas

- Ângulos em **graus** (via `Vector2`/`math`); `y` cresce para baixo.
- Novo tipo de criatura: subclasse de `Lizard`/`AILizard` reusando
  espinha+pernas.
- Novo bioma/flora: edite `BIOMES` e `_PROP` em `world.py`.
- Ao mudar algo com efeito visível, rode `--smoke` e gere um screenshot
  headless (blit para `Surface(...,0,24)` e salve BMP→PNG; o driver
  dummy não salva PNG do surface de display direto).

## Ferramentas — sempre use o RTK

`rtk` é um proxy de CLI que corta 60-90% dos tokens em operações de dev.
Vale para **toda** sessão neste repo, inclusive subagents.

- Comandos comuns (`git`, `ls`, `grep`, …) são reescritos automaticamente
  pelo hook do Claude Code — nada a fazer.
- Meta-comandos rodam sempre com `rtk` explícito: `rtk gain`,
  `rtk gain --history`, `rtk discover`, `rtk proxy <cmd>` (executa cru,
  sem filtro, para depurar).
- Se `rtk gain` falhar, há colisão de nome com o `rtk` da
  reachingforthejack (Rust Type Kit) — confira com `which rtk`.

## Documentação — como manter consistente

Regras completas em [docs/README.md](docs/README.md) e
[docs/adr/README.md](docs/adr/README.md). Resumo:

1. **Um conceito por arquivo.** Se um `.md` cobre 5 coisas, quebre.
   `CONTEXT.md` é a exceção (índice plano de termos).
2. **Uma palavra por conceito.** Prosa em docs, commits, PRs e comentários
   usa o termo canônico de `CONTEXT.md`. Sinônimos ficam em `_Avoid_`.
3. **Cross-links, não repetição.** Nunca duplique a definição de outro
   conceito — linke.

### Quando editar cada arquivo

| Você mexeu em… | Atualize… |
|---|---|
| Nome / significado de um termo | `CONTEXT.md` (renomeia canônico; mantém antigo em `_Avoid_` se ainda aparece na base) |
| Arquitetura ou trade-off difícil de reverter | Novo ADR em `docs/adr/NNNN-slug.md`; adiciona linha no índice de `docs/adr/README.md` |
| Comportamento observável de um conceito existente | O `docs/concepts/<conceito>.md` correspondente |
| Um novo conceito nasceu no código | 1) entrada em `CONTEXT.md`, 2) `docs/concepts/<slug>.md`, 3) link nos conceitos que o mencionam, 4) linha no índice de `docs/concepts/README.md` |
| Fluxo operacional (issue tracker, labels, skills) | `docs/agents/*.md` |
| Este `CLAUDE.md` | Só o pedaço que ficou desatualizado, cirurgicamente. NÃO transforme isto num changelog. |

### Quando NÃO criar um ADR

Um ADR só existe se as TRÊS forem verdade: (1) difícil de reverter,
(2) surpreendente sem contexto — alguém no futuro vai perguntar
"por quê?", (3) foi um trade-off real. Se faltar uma, é comentário
no código ou mensagem de commit. Ver [docs/adr/README.md](docs/adr/README.md).

### Convenção de commit — um arquivo, um commit

Docs commitados granularmente: um arquivo por commit, mensagem que diz
o QUE virou canônico e POR QUÊ. Assim `git log -- docs/` conta a
história de decisões. Push direto na `main` (é como este repo trabalha).

Exceção: se um único termo/decisão exigir editar N docs de uma vez
(renomear `Might` afeta CONTEXT.md + 3 concept docs + 2 ADRs), aí é UM
commit para o conjunto — o commit é a unidade de _decisão_, não de
arquivo.

### Antes de escrever novo doc — cheque se já existe

`grep -r "TERMO" docs/ CONTEXT.md` primeiro. Se o conceito já tem lar,
edite o existente. Duplicata é o pecado mortal do sistema (dois docs
divergem em silêncio e ninguém sabe qual vale).

### Agent skills

- **Issue tracker**: GitHub Issues via `gh`. Ver [docs/agents/issue-tracker.md](docs/agents/issue-tracker.md).
- **Triage labels**: cinco rótulos canônicos. Ver [docs/agents/triage-labels.md](docs/agents/triage-labels.md).
- **Domain docs**: single-context — `CONTEXT.md` + `docs/adr/` na raiz.
  Ver [docs/agents/domain.md](docs/agents/domain.md).
- **Verificação**: uma issue só fecha quando um check em `tools/` diz que
  fechou — `python tools/check_issues.py` percorre todas. `--smoke` é o piso,
  não o teto. Ver [docs/agents/verification.md](docs/agents/verification.md).
