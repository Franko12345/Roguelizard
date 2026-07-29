# Preços da loja por tier + grid de stats

Spec derivada de uma sessão de grilling. Duas frentes que se sustentam:
o preço da loja passa a escalar com o estágio da run, e o jogador ganha
uma leitura permanente do que já comprou — sem essa leitura, preço maior
parece arbitrário.

## O problema medido

Renda in-run cresce, preço não.

- Pólen por kill: `score_value // 12` (`loop.py:174`), ou 3-5 para um
  inimigo comum (score 40-70), multiplicado pelo combo (até 3,4×) e por
  `pollen_mult` (até 1,5× via Colheita).
- Boss de tier *t*: `score_value = 500 + 200·t` (`rounds.py:371`), ou
  41+16·t de pólen base, também multiplicado pelo combo.
- Inimigos por round: `wave_budget = (3 + wave·1.1) · theme_budget`
  (`rounds.py:312`), com joelho que acelera no late.

Renda por round, por tier (média das waves do tier, pré-joelho): tier 0
≈ 5,8 unidades de budget, tier 1 ≈ 10,7, tier 2 ≈ 16, tier 3 ≈ 22. Ou
seja **~+95% por tier, aproximadamente linear**. Na prática, uma wave 12
com ~18 inimigos rende na ordem de 200 pólen num round.

Contra isso, os preços base de `_roll_shop` (`state_camp.py:117`) são
fixos: Néctar 12, Vitalidade 28, Vigor 32, Charm 150, Ovo 40. O único
freio é `SHOP_PRICE_MULT = 1.25` por compra do mesmo item — que já
persiste pela run inteira via `Game.shop_prices` (conserto da issue
#105), mas é fraco: Vigor cinco vezes custa 32 → 40 → 50 → 62 → 78,
total 262, trocado por 200 de pólen num único round do late.

Resultado: no late o pólen sobra e a loja para de ser uma decisão.

## Decisões

| Eixo | Decisão |
|---|---|
| Sensação-alvo | Poder de compra **levemente crescente**: preço cresce menos que a renda |
| Estágio | **tier** = `wave // BOSS_EVERY`, muda exatamente na wave do boss |
| Forma | **Linear**: `base × (1 + 0.7·tier)` → 1,0 / 1,7 / 2,4 / 3,1× |
| Composição com a inflação por compra | **Ortogonais**: guardar contagem de compras, não preço absoluto |
| Inflação por compra | **Por item, mult por categoria**: permanentes 1.45, consumíveis 1.25 |
| Cap no INFINITO | **Nenhum**, nos dois eixos |
| Arredondamento | `int()` truncado, como hoje |
| Bônus de rota "polen" | Escala pelo mesmo mult de tier |
| Escopo | Só a loja de pólen. DNA fica fora (sem sintoma medido) |
| Grid de stats — local | Camp, ao lado da loja **e** no play, coluna por jogador junto da barra de vida |
| Grid — toggle | TAB liga/desliga (latch), **default ligada**, persistido em settings |
| Grid — conteúdo | Stats numéricos + fileira de ícones dos itens/charms possuídos |
| Grid — coop | Duas colunas compactas, P1 e P2 (uma só em single) |
| Tooltip | Hover com dwell de ~0,25 s, no camp e no play |
| Preview de compra | Delta no item focado: `1.72× → 1.98×` fantasmado na grid |

Escolhas linear + tier + 0.7 batem com a aritmética acima: preço a
+70%/tier contra renda a +95%/tier deixa ~25% de folga crescente, que é
a sensação de progresso pedida.

Por que o DNA saiu do escopo: a renda dele já escala com a wave alcançada
(`dna_for_run = score/90 + wave·4 + kills·0.4`) e o custo já escala com o
nível (`30 + 25·l`). O catálogo inteiro sai em ~6 runs boas. Não é o
mesmo furo, e misturar as duas curvas numa passada só atrapalha o
balanceamento das duas.

## Fórmula

```python
# core/config.py
SHOP_TIER_STEP = 0.7          # +70% de preço por tier
SHOP_PRICE_MULT = 1.25        # recompra de consumível (existente)
SHOP_PRICE_MULT_PERM = 1.45   # recompra de upgrade permanente (novo)
```

```python
# flow/rounds.py, junto das outras curvas por wave (a partir da linha 280)
def tier_price_mult(wave):
    """Multiplicador de preço do estágio. Cresce por tier, não por wave,
    então o preço salta na wave do boss e fica estável entre bosses."""
    return 1.0 + C.SHOP_TIER_STEP * (wave // BOSS_EVERY)
```

```python
# game/state_camp.py
def shop_price(base, perm, buys, wave):
    mult = C.SHOP_PRICE_MULT_PERM if perm else C.SHOP_PRICE_MULT
    return int(base * rounds.tier_price_mult(wave) * mult ** buys)
```

`tier_price_mult` mora em `rounds.py` porque é lá que toda dial baseada
em wave vive (o próprio doc do módulo diz isso). `shop_price` mora em
`state_camp.py` porque é a loja; `loop.py` já importa `state_camp`
(linha 35), então `_apply_buy` chama sem import novo.

Curvas resultantes, contando só a primeira compra de cada tier:

| Item | Base | Tier 0 | Tier 1 | Tier 2 | Tier 3 |
|---|---|---|---|---|---|
| Néctar de Cura | 12 | 12 | 20 | 28 | 37 |
| Vitalidade | 28 | 28 | 47 | 67 | 86 |
| Vigor | 32 | 32 | 54 | 76 | 99 |
| Charm | 150 | 150 | 255 | 360 | 465 |
| Ovo de Amigo | 40 | 40 | 68 | 96 | 124 |

Vigor comprado repetidamente **dentro** do tier 2 (mult 2,4): 76 → 111 →
161 → 233 → 338. Néctar no mesmo tier: 28 → 36 → 45 → 56.

## Mudanças de estado

`Game.shop_prices` (nome → preço absoluto) vira `Game.shop_buys`
(nome → contagem de compras), ainda por run e em memória — nada de save
para migrar.

- `loop.py:107` — renomear o dict.
- `loop.py:423` — `_apply_buy` incrementa a contagem e recalcula
  `it['cost']` via `shop_price`, em vez de multiplicar o preço em cima
  de si mesmo.
- `state_camp.py:127-128` — `_roll_shop` calcula cada `cost` a partir de
  base + tier + contagem, em vez de reler um preço absoluto.
- `loop.py:445` — bônus de rota "polen" passa a ser
  `int(25 * rounds.tier_price_mult(wave))` → 25 / 42 / 60 / 77.

Cada oferta de `_roll_shop` ganha dois campos:

- `perm=True` para Vitalidade, Vigor e Charm (acumulam poder);
  `perm=False` para Néctar e Ovo (são gastos).
- `preview=('might', 1.15, 'mul')` / `('max_health', 20, 'add')` para o
  delta fantasma. Charm e Ovo não têm preview — o efeito não é numérico.

O `preview` existe porque hoje o efeito da oferta é uma lambda opaca
(`fn`), impossível de prever sem executar. É o mínimo declarativo que a
UI precisa; não é um sistema de efeitos.

## Grid de stats

Uma função nova em `game/hud.py` (`stat_grid`), sem módulo novo,
desenhando um bloco por jogador:

- Linhas: dano (`might`), vida (`health`/`max_health`), recarga
  (`cooldown_mult`), velocidade (`speed_mult`), área (`area_mult`).
- Abaixo, fileira de ícones dos itens e charms possuídos, reusando os
  ícones que `docs/concepts/icons-audio.md` já define.
- Cacheada via `game._panel` com chave quantizada nos valores exibidos
  (ADR-0009), porque os números mudam raramente e o bloco é redesenhado
  todo frame.

No play: uma coluna compacta por jogador, colada na barra de vida do
próprio jogador — escala de 1P para 2P sem mudar layout. Visível por
default; TAB alterna e a preferência persiste em `core/settings.py`,
como o toggle de perf. TAB está livre (P1 usa WASD/espaço/LSHIFT/Q/E/
LCTRL, P2 usa setas/IJKL/RCTRL/RSHIFT/RALT/U/O). Um toggle só, do jogo,
não um por jogador.

No camp: o mesmo bloco em duas colunas ao lado dos cinco cards da loja.
O card focado projeta o delta na linha correspondente
(`dano 1.72× → 1.98×`), o que fecha o laço entre preço e efeito.

Tooltip: o cursor precisa pousar sobre a linha ou o ícone por ~0,25 s.
Mostra nome do stat, valor atual e de onde veio ("Dano 1.72× — Vigor ×3,
charm Presa"). O dwell existe porque no play o mouse **é** a mira (dash
no botão esquerdo) e o cursor cruza a coluna sem intenção. Gamepad não
tem cursor, então cada linha carrega abreviação legível por si.

## Verificação

`tools/check_shop_prices.py` precisa ser estendido (ele hoje roda em
tier 0, onde o mult é 1,0 — as assertivas atuais continuam valendo como
regressão do early game):

- tier 0 abre exatamente com os preços de hoje;
- avançar a wave até tier 1 e 2 e conferir 1,7× e 2,4×;
- recompra compõe por categoria: 1,45 em Vigor, 1,25 em Néctar;
- a contagem sobrevive à troca de camp (comportamento da #105 mantido) e
  o salto de tier se aplica também ao item já comprado;
- preços voltam ao base numa `Game` nova (não vazam entre runs);
- bônus de rota "polen" escala com o tier.

`tools/check_stat_grid.py`, novo:

- a grid renderiza headless em 1P e 2P;
- TAB alterna e o estado persiste em settings;
- tooltip abre só depois do dwell;
- o delta previsto do item focado bate com o efeito real depois da
  compra (chamando a `fn` de verdade).

Mais `--smoke 90` e um screenshot headless (blit para `Surface(...,0,24)`
e salvar BMP→PNG, porque o driver dummy não salva PNG do surface de
display).

## Docs a atualizar

- `CONTEXT.md`: entradas para o preço escalado por tier e para a grid de
  stats.
- `docs/concepts/camp.md`: a loja tem preço por estágio.
- `docs/concepts/balance.md`: registrar esta como a terceira passada de
  balanceamento, com a aritmética de renda × preço.
- `docs/concepts/stat-grid.md`: novo, mais a linha no índice de
  `docs/concepts/README.md` e links de `ui-legibility.md` e
  `health-hud.md`.
- `docs/concepts/controls.md`: TAB.

Sem ADR: é reversível (duas constantes e uma função), não é um trade-off
arquitetural. Falha o critério (1) da regra dos três de
`docs/adr/README.md`.

## Assunções e pontas soltas

- **Preços base mantidos** (12/28/32/150/40). Como o mult do tier 0 é
  1,0, o early game fica idêntico ao de hoje — o furo não estava lá.
- **0.7 é a constante a tunar.** A forma da curva está fixada pela
  aritmética; o número exige playtest.
- O sandbox chama `_enter_camp` sem avançar wave, logo vê tier 0 e nada
  quebra. Testar preços de tier alto por lá exigiria expor a wave — fora
  do escopo.
- Modo INFINITO sem cap assume que a renda também segue subindo lá. Se
  um platô aparecer no playtest, o conserto é um teto no mult de tier,
  não uma mudança de forma.
