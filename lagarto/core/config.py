"""Global configuration: window/world sizes, timing and the colour palette.

Keeping every tunable in one module makes balancing and re-theming a one-file job.
"""

import math

# --- window / world -------------------------------------------------------- #
WIDTH, HEIGHT = 1120, 720
# Retro pixelation (feedback: "deixa mais pixelado"): present() downsamples the
# logical surface to WIDTH/PIXEL_SCALE x HEIGHT/PIXEL_SCALE, then upscales with
# NEAREST (not smoothscale) -- chunky visible pixels. 1 = off (old crisp-vector
# look). Pure post-process: doesn't touch world/UI coordinates, hitboxes, or
# any drawing code, so nothing else needs to know this exists.
PIXEL_SCALE = 1
WORLD_W, WORLD_H = 3200, 3200

# --- como a bala se le (Gungeon: gorda e quente) --------------------------- #
# Os dois botoes de aparencia de projetil. Sao DESENHO, nao regra: colisao e
# sobreposicao de corpo contra a criatura, entao mexer aqui nao muda o alcance
# de nada. Cada chamador continua passando `radius=` como peso relativo.
BULLET_SCALE = 1.45      # tamanho do corpo. 1.0 era o tamanho antigo
BULLET_GLOW = 1.0        # intensidade do halo aditivo (era 0.75, fixo no draw)
# As faiscas que saem pra tras da bala, no lugar do rastro em linha. Os dois
# valores sao UM orcamento, nao duas preferencias: as faiscas vivas por bala sao
# BULLET_SPARK_LIFE*0.75 / BULLET_SPARK_GAP, e a ~100 balas isso tem que caber
# em FX.MAX_SPARKS com folga pro resto do jogo. Ver docs/concepts/projectile.md.
BULLET_SPARK_GAP = 0.09  # segundos entre faiscas de uma mesma bala
BULLET_SPARK_LIFE = 0.2  # a faisca de bala apaga rapido; a generica vive 0.5

# --- timing (fixed simulation step, render decoupled) ---------------------- #
SIM_HZ = 60
DT = 1.0 / SIM_HZ
MAX_STEPS = 5            # cap sim steps per frame -> avoids the "spiral of death"

# --- ability energy costs (shared by the logic and the HUD dials) ---------- #
RUN_FINAL_WAVE = 20      # modo normal: onda do chefe final (vitoria)

FRIEND_HP = 6            # aliados agora tomam dano de verdade -> precisam aguentar
# Vida dos inimigos. Historico: 3.0 -> 2.2 (medicao) -> 3.5 (playtest do usuario,
# que manda). O bot headless media o TTK das ARMAS e concluiu 2.2; jogando de
# verdade quem mata e o dash + a rabada, que sao muito mais rapidos, entao a
# sensacao real era de inimigos de papel. Licao: o bot mede atrito, nao dificuldade.
# O preco de 3.5 e que jogar passivo fica ainda mais inviavel (ver CLAUDE.md,
# "Balanceamento 2a passada") -- a dificuldade continua vindo do dano, nao daqui.
ENEMY_HP_MULT = 3.5

# --- dano dos inimigos ----------------------------------------------------- #
# Sobe DANO, nao vida. Num jogo de ataque automatico a unica agencia do jogador e
# posicionamento, entao a dificuldade tem que ser consequencia de erro de posicao;
# vida a mais so vira esponja e ainda faz a build parecer mais fraca do que e.
ENEMY_DMG_BASE = 11          # era 8 fixo
ENEMY_DMG_SIZE = 0.5         # era 0.4 -- predador maior bate mais forte
# Escada por onda em DEGRAUS discretos: uma rampa continua o jogador nao percebe,
# um degrau ele sente ("a partir da onda 5 o corredor me machuca de verdade").
ENEMY_DMG_STEP = 4           # a cada N ondas sobe um degrau
ENEMY_DMG_PER_STEP = 2.0     # quanto sobe por degrau
ENEMY_PROJ_DMG = 10          # cuspe inimigo (era 8); lento e telegrafado -> da p/ desviar
# --- inimigos da fase 2 ---------------------------------------------------- #
# Bombardeiro (kamikaze). A regra do Mulliboom (Isaac): depois que o pavio acende
# ele DESACELERA e a explosao sai onde ele parar, entao andar embora sempre
# funciona. Uma carga que te persegue ate detonar nao e telegrafo, e so dano.
BOMBER_TRIGGER = 130     # distancia que acende o pavio
BOMBER_FUSE = 0.85       # >27 frames de aviso (250ms de reacao + duracao do dash)
BOMBER_RADIUS = 108
BOMBER_DMG = 26          # no centro; a borda da ~45% disso (falloff)
BOMBER_SPLASH = 4        # fogo amigo: bombardeiros afinam a propria horda

# Metralhador: pressao continua, nao pico. Dano baixo por tiro, rajada rapida.
GUNNER_BURST = 4         # tiros por rajada
GUNNER_BURST_GAP = 0.13  # intervalo dentro da rajada
GUNNER_RELOAD = 1.9      # respiro entre rajadas -> da pra quebrar a linha de tiro
GUNNER_DMG = 5
GUNNER_SPREAD = 7.0      # graus de dispersao

# Venenoso: negacao de area. Mira onde voce ESTA e a pocas cai la, entao quem
# pune e ficar parado -- empurra o jogador a se mover, sem ser um acerto direto.
VENOM_WINDUP = 0.5
VENOM_CD = 3.1
VENOM_SPIT_SPEED = 260
VENOM_SPIT_DMG = 6
VENOM_PUDDLE_R = 62
VENOM_PUDDLE_DMG = 7     # dano POR TICK (a poca tem cadencia propria), nao dps
VENOM_PUDDLE_TICK = 0.55
# Tem que ser MENOR que VENOM_CD, senao as pocas se sobrepoem e o dano empilha --
# e exatamente o bug do Acido, ja documentado e ja corrigido uma vez.
VENOM_PUDDLE_LIFE = 2.8

# --- inimigos da issue #104: os dois habitos que o ROLAMENTO criou ---------- #
# ANTECIPADOR: atira LIDERANDO, onde voce VAI estar. Ataca o habito de rolar por
# reflexo -- o rolamento e barato (5 de energia, 0.2s de recarga), entao o
# jogador aprende a apertar sem olhar; este mira o ponto de chegada. O telegrafo
# e o proprio ponto no chao, redesenhado a cada quadro do windup: ficar parado e
# uma resposta valida, rolar sem ler nao e.
SNIPER_WINDUP = 0.55     # >27 quadros de aviso, com a marca visivel o tempo todo
SNIPER_CD = 2.6
SNIPER_RANGE = 470
SNIPER_LEAD = 1.0        # QUALIDADE da previsao (0..1), nao segundos: 1.0 = mira
                         # exatamente onde voce vai estar quando a bala chegar.
                         # O tempo vem do voo (dist/velocidade) em emitter.lead_point.
                         # Era 0.5 s fixo, o que so acertava na unica distancia em
                         # que dist/SNIPER_SPEED batia com 0.5 -- medido, errava por
                         # 44 px a 150 px de alcance e 172 px a 450, contra um corpo
                         # de 21 px. Andar reto era imune; ficar parado, morte certa.
SNIPER_SHOTS = 2         # rajada curta: a decisao e o ponto, nao a cadencia
SNIPER_GAP = 0.16
SNIPER_SPEED = 340
SNIPER_DMG = 8
SNIPER_MARK_R = 30       # raio da marca no chao (o tamanho do erro que ela pune)
# MORTEIRO: negacao de area que ARMA COM ATRASO. Ataca o habito de investir na
# cara -- a poca nasce onde voce ia pousar, entao a investida sem plano de saida
# termina dentro dela. A pegada aparece ANTES de armar (regra do telegrafo).
MORTAR_ARM = 0.9         # tempo de VOO da bomba: a pegada aparece no lance e a
                         # poca nasce quando o projetil cai nela. E o mesmo relogio
                         # -- lob_shot recebe flight=MORTAR_ARM, entao a bomba pousa
                         # quando a contagem da pegada zera, seja qual for a distancia
MORTAR_ARC = 130         # altura falsa do arco em pixels de tela (Projectile.lift).
                         # So desenho: a posicao no mundo anda reto ate a marca
MORTAR_CD = 2.4          # era 4.0 -- cadencia baixa demais para ele aparecer
MORTAR_RANGE = 780       # artilharia tem que superar a propria lentidao. Era 440,
                         # mal acima do topo (380) da sua propria banda de kite: com
                         # genome speed 0.72 contra os 224 px/s do jogador, ele ficava
                         # para tras e so estava em alcance 13% do tempo -- medido,
                         # 1 poca em 15 s contra alvo andando, 4 contra alvo parado.
                         # O alcance maior nao o torna injusto: MORTAR_ARM de 1 s e a
                         # pegada no chao continuam sendo a saida, e de longe sobra
                         # ainda mais tempo para andar para fora.
MORTAR_SPREAD = 46       # ruido no ponto: mira o pouso, nao a cabeca
MORTAR_R = 58
MORTAR_DMG = 6           # dano POR TICK (poca hostil tem cadencia propria)
MORTAR_TICK = 0.6
# Tem que ser MENOR que MORTAR_CD, senao as pocas de UM mesmo morteiro se
# sobrepoem e o dano empilha -- Acido, poca de veneno e slow do ferrao ja
# cairam nisso; ver docs/concepts/enemy-behaviors.md.
MORTAR_LIFE = 1.8        # desceu junto com o CD (2.4): a regra e LIFE < CD, entao
                         # subir cadencia obriga a encurtar a poca, nao so o timer

# --- inimigos da fase B4 (corpos procedurais novos) ------------------------- #
# CENTOPEIA (corpo 'segmented'): cavadora. Ataca o habito de ACAMPAR/andar reto --
# mergulha (intangivel), viaja por baixo ate um ponto que voce ve marcado no chao
# e ERUPCIONA la. Parada = ela sai embaixo de voce; movimento = voce sai do anel.
CENT_SURFACE_TIME = 2.6     # segundos cacando na superficie antes de mergulhar
CENT_DIG_TIME = 0.5         # telegrafo de MERGULHO: enraiza, cava um buraco, afunda
CENT_UNDER_TIME = 1.4       # teto de tempo submersa (erupcao forcada) -- e o telegrafo
CENT_ERUPT_DMG = 15         # dano do estouro ao aflorar (anel curto)
# POLVO (corpo 'tentacle'): agarrador. Ataca o habito de FICAR NO MEIO-ALCANCE /
# kitar de perto -- estica os bracos (telegrafo visivel), e no estalo te puxa para
# dentro e retarda. So funciona se voce estiver por perto: fugir cedo o nega.
OCTO_GRAB_RANGE = 280      # dentro disso ele arma o agarrao
OCTO_WINDUP = 0.75         # telegrafo: bracos convergem/esticam (>27 frames)
OCTO_CD = 2.4              # respiro entre agarroes
OCTO_PULL_DIST = 120       # o quanto voce e puxado
OCTO_SLOW_MUL = 0.5
OCTO_SLOW_TIME = 0.8
OCTO_GRAB_SHOW = 0.25      # quadros mostrando o braco fisgado

# --- itens (items.py) ------------------------------------------------------- #
# Qualidade 0-4 no molde do Isaac: enviesa a chance de ser oferecido, nao trava.
# Um item forte pode existir sem ser comum; um fraco pode existir sem ser cilada.
ITEM_QUALITY_WEIGHT = (2.2, 1.6, 1.0, 0.6, 0.3)
ITEM_CHARGE_KILLS = 14   # abates para carregar o ativo (liga o recurso ao combo)

ITEM_PULSO_R = 190
ITEM_PULSO_DMG = 14
ITEM_PULSO_KNOCK = 520
ITEM_MUDA_TIME = 1.1     # segundos de invulnerabilidade da muda de pele
ITEM_CHAMADO_COUNT = 3
ITEM_FERRAO_COUNT = 8
ITEM_FERRAO_DMG = 6

# passivos de mecanica
ITEM_TRAIL_R = 44        # raio do rastro corrosivo do dash
ITEM_TRAIL_DMG = 5       # dano por tick da poca (a poca tem cadencia propria)
ITEM_TRAIL_LIFE = 1.6
ITEM_TRAIL_DROP = 0.07   # espacamento entre pocas do rastro
ITEM_CASULO_TIME = 0.45  # i-frames extras do Casulo ao levar dano
ITEM_KILL_BLAST_R = 92
ITEM_KILL_BLAST_DMG = 7
ITEM_KILL_HEAL = 1.5
ITEM_MAGNET_R = 260
ITEM_THROW_SPEED = 900   # arremesso da lingua
ITEM_ADRENALINE_HP = 0.35   # abaixo desta fracao de vida...
ITEM_ADRENALINE_MULT = 1.6  # ...o dano sobe isto
ITEM_DRAIN = 4.0         # vida drenada pela lingua por acerto
ITEM_DART_DMG = 5        # farpas disparadas pela rabada
ITEM_DART_COUNT = 5      # quantas farpas por golpe
ITEM_DART_SPREAD = 16    # graus entre farpas
ITEM_DART_SPEED = 520
ITEM_SPIRAL_MULT = 2.4   # multiplica a varredura da rabada (Cauda em Espiral)
ITEM_MAGNET_PULL = 420   # velocidade com que o ima puxa coletaveis (px/s)
ITEM_SPREAD_R = 130      # alcance do contagio

# Synergy Factor (Gungeon): multiplica o PESO de uma carta que avanca uma
# sinergia. E anti-frustracao -- o jogo conspira para a sua build fechar em vez
# de pendurar meia sinergia pelo resto da run. Nao e sistema novo: roll_cards ja
# escolhia por peso.
SYNERGY_FACTOR_CLOSE = 3.2   # esta carta COMPLETA uma sinergia
SYNERGY_FACTOR_START = 1.4   # esta carta comeca uma

# --- personagens jogaveis (characters.py) ----------------------------------- #
CHAR_LAGARTO_REROLLS = 1        # rerrolagens da mao de cartas, por ROUND

CHAR_VIBORA_WEAPON_CAP = 2      # o teto E a mecanica: com 6 armas o rabo e bonus,
                                # com 2 ele e o seu dano e voce tem que golpear
CHAR_VIBORA_WHIP_CD = 0.42      # multiplicador da recarga da rabada
CHAR_VIBORA_WHIP_MULT = 2.4     # multiplicador do dano da rabada
CHAR_VIBORA_HP = 0.7            # fragil: ficar no alcance do rabo tem que custar

CHAR_COURACADO_ARMOR = 0.3      # tirar o dash e invasivo -> pago tres vezes:
CHAR_COURACADO_THORNS = 2       # armadura, dano de contato e imunidade a empurrao
CHAR_COURACADO_HP = 1.45

CHAR_LARVA_HP = 0.62            # comeca indefesa de verdade
CHAR_LARVA_KILLS_PER_STEP = 12  # abates por degrau de crescimento
CHAR_LARVA_SIZE_STEP = 1.13     # cada degrau multiplica o tamanho
CHAR_LARVA_MAX_SIZE = 1.75
CHAR_LARVA_HP_STEP = 14
CHAR_LARVA_MAX_SLOTS = 6

# --- campeoes (champions.py) ------------------------------------------------ #
# Chance sobe com a onda, no formato do Isaac (~5% cedo, ~20% tarde). Vida dos
# campeoes fica MODESTA de proposito: campeao e ameaca pelo que FAZ; um que so
# tem mais vida nao ensina nada e vira pedagio.
CHAMP_CHANCE_BASE = 0.05
# Issue #23: rampa mais ingreme a partir da onda 7 (antes 0.012/onda ate 0.22).
# Mid-game tinha pouquissimo campeao; agora ondas 7+ tem pressao elite real.
CHAMP_CHANCE_PER_WAVE = 0.018
CHAMP_CHANCE_MAX = 0.30

# --- dificuldade por onda (rounds.py) --------------------------------------- #
# Issue #23: antes o HP subia +0.7/onda linear e a velocidade capava em +40%.
# O jogador entrava em snowball no meio da run porque os inimigos morriam antes
# de chegar nele. Os "joelhos" sao propositais: ondas 1-6 ficam EXATAMENTE como
# eram, para nao punir quem esta aprendendo; a rampa engata onde o snowball
# comecava. Toda a curva vive em rounds.wave_* -- estes sao so os numeros.
WAVE_HP_KNEE = 10               # onda a partir da qual o HP escala super-linear
WAVE_HP_BASE = 0.7              # bonus de HP por onda antes do joelho (linear)
WAVE_HP_POST_KNEE_EXP = 1.4     # expoente do termo pos-joelho
WAVE_HP_POST_KNEE_MULT = 1.2    # multiplicador do termo pos-joelho

WAVE_SPEED_KNEE = 10
WAVE_SPEED_PER_WAVE = 0.025     # antes 0.02/onda
WAVE_SPEED_MAX = 0.60           # antes 0.40 (cap em +60%)
WAVE_SPEED_POST_KNEE_PER_WAVE = 0.015
WAVE_SPEED_POST_KNEE_MAX = 0.15  # +15% extra no fim, somando +75%

WAVE_BUDGET_KNEE = 10
WAVE_BUDGET_POST_KNEE_MULT = 0.6   # orcamento extra por onda pos-joelho

WAVE_CAP_KNEE = 8               # onda a partir da qual o teto de vivos cresce
WAVE_CAP_POST_KNEE_PER_WAVES = 2   # +1 inimigo a cada 2 ondas pos-joelho
WAVE_CAP_POST_KNEE_MAX = 4      # teto do bonus, em cima do cap do tema
CHAMP_MODIFIER_CHANCE = 0.28   # variante que ainda ganha um modificador em cima

# Velocidade ABSOLUTA do filhote (jogador ~224, dash ~672): mais rapido que andar,
# mais lento que um dash. Ele te alcanca se voce so caminhar, e voce escapa se
# usar o dash -- e o que torna "minusculo e veloz" uma ameaca justa e nao um golpe
# inevitavel. Relativo nao serve: um filhote de tanque sairia mais lento que voce.
CHAMP_FILHOTE_SPEED = 440
CHAMP_ALFA_RANGE = 360   # alcance do chamado e da deteccao
CHAMP_ALFA_CD = 4.5
CHAMP_ALFA_TIME = 3.0    # duracao do frenesi nos aliados
CHAMP_ALFA_SPEED = 1.35
CHAMP_ESPECTRO_REVEAL = 330   # distancia em que a camuflagem se desfaz
CHAMP_SALTADOR_RANGE = 420
CHAMP_SALTADOR_CD = 2.4
CHAMP_SALTADOR_POWER = 3.1
CHAMP_ARMOR = 0.6        # fracao bloqueada de frente (por tras leva normal)
CHAMP_SPLIT_SIZE = 0.62  # DIVISOR: tamanho de cada cria (do pai) -- Blobulon/Fistula
CHAMP_SPLIT_HP = 0.5     # vida de cada cria (fracao da max_hp do pai)

# Ferrao (escorpiao/envenenador): TEM que durar menos que o attack_cd de 0.8s de
# quem o aplica, senao a lentidao e permanente por construcao -- foi o terceiro
# bug desta mesma forma no projeto (Acido, poca de veneno, agora o ferrao).
STING_SLOW = 0.7         # 30% mais lento (era 50%, e invisivel demais para tanto)
STING_SLOW_TIME = 0.4    # << attack_cd (0.8): uptime ~50%, nao ~75%

CRIT_MULT = 2.0          # dano ao acertar a cabeca (ponto fraco)
AGGRO_TIME = 5.0         # segundos que um aliado segura o aggro apos bater
FRIEND_LIFE = 45.0       # aliados sao temporarios (segundos)

# --- acampamento FISICO (clareira estilo Hades: barraca + 3 portas) --------- #
CAMP_TENT_R = 66         # encostar a esta distancia da barraca abre a loja
CAMP_DOOR_R = 52         # atravessar a esta distancia de uma porta avanca a onda
CAMP_REOPEN_CD = 0.7     # respiro apos fechar a loja (nao reabre no mesmo passo)
CAMP_TENT_OFF = (-260, 40)     # posicao da barraca relativa ao centro da clareira
CAMP_DOOR_SPAN = 285     # espacamento entre as 3 portas
CAMP_DOOR_UP = 215       # o quanto as portas ficam "a frente" (para cima) do centro
# a barraca e as portas CAEM do ceu ao entrar no acampamento (juice: shake + poeira)
CAMP_DROP_H = 900        # altura inicial (mundo) de onde tudo despenca -- fora da tela
CAMP_DROP_DUR = 0.40     # duracao da queda de cada peca
CAMP_TENT_DELAY = 0.12   # a barraca cai primeiro
CAMP_DOOR_DELAY = 0.30   # 1a porta; as outras escalonam por CAMP_DOOR_STAGGER
CAMP_DOOR_STAGGER = 0.14
# o preco de um item da loja sobe a cada compra e PERSISTE pela run inteira
# (era 1.6x resetando a cada camp -- dava pra farmar cura barata pra sempre)
SHOP_PRICE_MULT = 1.25

# --- ritmo das telas de jogo (level-up / acampamento) ---------------------- #
# Estados que animam a propria entrada/saida (veu + dropdown + absorcao):
# transicoes ENTRE eles nao usam Fade -- o blackout esconderia o impacto.
SOFT_TRANSITION_STATES = frozenset(('play', 'levelup', 'camp', 'pause'))
UI_VEIL = 0.20           # fade do fundo escuro antes de qualquer conteudo
UI_STAGGER = 0.075       # atraso entre um item e o proximo no dropdown
UI_DROP = 0.30           # duracao da queda de cada item
UI_READY = 0.36          # so aceita escolha depois disso (evita clique acidental)
# slots de charm na ordem em que aparecem no acampamento (colunas da grade)
CHARM_SLOTS = (('head', 'CABECA'), ('back', 'COSTAS'), ('tail', 'CAUDA'))
# absorcao da escolha pelo jogador: centraliza -> segura -> voa pro lagarto
PICK_CENTER = 0.40       # chega ao centro da tela
PICK_HOLD = 0.56         # fica parado no centro ate aqui (da tempo de ler)
PICK_END = 0.86          # atinge o jogador -> efeito aplicado
PICK_ROUTE_END = 0.50    # rotas: versao curta (so expande e avanca)

# Dano de UM dash (antes o dash reaplicava 3 por frame = ~30 por investida).
# Mesmo tratamento da rabada: base menor + escala com `might`, porque 5 fixo era
# igual na onda 1 e na onda 20. Membranas ja melhorava velocidade/duracao/custo
# do dash mas NAO o dano, apesar de a carta prometer "dash mais forte" -- agora
# `DASH_WINGS_MULT` cumpre a promessa e da ao dash o mesmo par base+upgrade que a
# cauda tem com a clava.
#   nu ............... 4  (critico 8)
#   + membranas ...... 6  (critico 12)
#   + membranas e 3 Vigor  10 (critico 21)
DASH_DAMAGE = 4
DASH_WINGS_MULT = 1.5

# Colisao macia: atravessar inimigo custa velocidade em vez de te empurrar.
# Medido antes: um pastador (inofensivo!) a 30px te deixava a 49% da velocidade, e
# UM corredor ja saturava o efeito -- ou seja, era liga-desliga, nao gradiente.
# Hoje so INIMIGOS arrastam (collision.DRAGS_PLAYER) e a saturacao exige estar
# enterrado em ~3 corpos.
CONTACT_DRAG = 0.35      # freio maximo, quando totalmente enterrado
CONTACT_FULL = 3.0       # quantos corpos sobrepostos equivalem a "atolado de vez"

# pressionada fica valida por este tempo: sobrevive a frames sem passo de simulacao
# (jitter e hit-stop) e a um clique pouco antes do cooldown acabar
INPUT_BUFFER = 0.15

DASH_COST = 14
TONGUE_COST = 8
# Lingua-Dardo (amuleto, issue #104): a lingua tambem dispara. O unico tiro
# MIRADO do jogador -- as armas continuam automaticas. Dano baixo de proposito:
# o valor esta em ter um tiro no botao que voce ja aperta, nao em dano.
TONGUE_DART_DMG = 5
TONGUE_DART_SPEED = 420

# --- rolamento: a segunda esquiva, barata e sem dano (issue #103) ------------- #
# A investida (o dash) e invulneravel mas PONTUAL: 0,16 s de i-frames num cd de
# 0,45 s por 18 de energia = 36% do ciclo em rajada, 5% sustentado. Com 5% nao da
# pra subir a densidade de bala sem ser injusto. O rolamento nao mexe em nada
# disso: ele ganha na FREQUENCIA (custo 5, cd 0,2 s) e perde o dano. Lanca como a
# investida, so que mais curto -- escapar de bala e cobrir chao, e a versao sem
# impulso lia como "tentou rolar e nao deu dash".
ROLL_COST = 5
ROLL_CD = 0.2            # contado do FIM do rolamento: 0,15 rolando + 0,2 se
                         # recuperando = 43% do ciclo invulneravel em rajada, e
                         # a energia (6/s de regen) e o que limita de verdade
ROLL_TIME = 0.15         # i-frames por rolamento
ROLL_SPEED = 3.4         # multiplicador de IMPULSO (x max_speed). A investida usa
                         # 3.0 (3.5 com asas) por 0.16 s; o rolamento usa mais por
                         # menos tempo, entao anda parecido e volta o dobro mais
                         # rapido -- ele e a SAIDA, e sair precisa cobrir chao.
                         # Historico: nasceu como 1.9 multiplicando steer, sem
                         # impulso nenhum (movia ~1/3 do corpo), passou por 2.6 e
                         # ainda leu como "mal ganha distancia" no playtest.

# --- a pose do rolamento: comprime e relaxa, nao enrola ---------------------- #
# A primeira versao colapsava as juntas num disco girando (fake roll). Lia como
# "te enrola todo": o corpo virava uma bola e o gesto sumia. O que se quer e
# squash-and-stretch -- o bicho COMPRIME no lancamento e RELAXA na saida, como
# mola. Sem giro, sem colapso de link: a espinha continua uma espinha.
# ATENCAO aos dois numeros abaixo: eles parecem exagerados e nao sao. Nada
# desenha `squat_bias` -- base.py o consome num `approach(squash, alvo,
# 9/sqrt(weight))`, e num evento de 0,15 s esse filtro deixa passar so ~37% do
# que voce pediu. Medido: 0.62 aqui vira 0.86 na tela. Entao estes sao valores
# de ENTRADA de um filtro, nao a pose final. check_roll mede `p.squash`, que e
# o que aparece, justamente para ninguem "corrigir" isto de volta.
ROLL_SQUAT = 0.35        # -> ~0.75 desenhado: comprime de verdade
ROLL_STRETCH = 1.42      # -> ~1.15 desenhado. Estica ALEM do neutro ao soltar --
                         # e o "relaxa" da dupla. Sem passar de 1.0 a volta e um
                         # retorno, nao uma mola
ROLL_IFRAME_COLOR = (150, 225, 255)   # azul-gelo: le como "intocavel". NAO use
                                      # branco -- hit_flash ja clareia o corpo, e
                                      # "nao posso ser atingido" nao pode parecer
                                      # "acabei de ser atingido"
ROLL_IFRAME_MIX = 0.8    # quanto da cor de i-frame no auge (0..1)
ROLL_LEG_PULL = 0.55     # pernas recolhidas no auge (menos que o antigo 0.45: sem
                         # bola pra formar, elas so precisam sair do caminho)
ROLL_EASE = 30           # taxa de entrada na compressao. NUNCA snapado --
                         # compressao instantanea teleporta o corpo.
ROLL_RELEASE_EASE = 8    # taxa de SAIDA, deliberadamente mais lenta: fast in,
                         # slow out. Com a mesma taxa dos dois lados o alvo
                         # esticado decaia tao rapido quanto `squash` conseguia
                         # persegui-lo, saindo de 0.62 comprimido -- o overshoot
                         # visivel morria em 1.05 por mais que se subisse
                         # ROLL_STRETCH. Segurar o alvo e o que deixa a mola
                         # chegar la.

# --- tongue: a chameleon slingshot, not an arc ------------------------------- #
# Three beats, and the split between them IS the feel. OUT is short and
# ease-out so the tongue leaves the mouth explosively and decelerates into the
# target; STICK is the moment it snaps taut, which is where the hit lands and
# where all the impact juice fires; REEL is the longest, because dragging your
# food home is the payoff and it should be watchable.
TONGUE_OUT_T = 0.085
TONGUE_STICK_T = 0.075
TONGUE_REEL_T = 0.17
TONGUE_REACH_MISS = 210          # how far it shoots with nothing to aim at
TONGUE_OVERSHOOT = 0.07          # springs this fraction past the target on STICK
# Shaft. Pinned at the mouth and at the tip; every point between is a spring, so
# the tongue whips and undulates like a tentacle instead of being a stiff curve.
TONGUE_SEGMENTS = 13
TONGUE_LAG = 500.0               # shaft spring stiffness toward its ideal curve.
                                 # Low values LOOK like more lag but actually mean
                                 # the shaft never reaches the coiled shape at all
                                 # -- the reel is only ~10 frames long. Raising it
                                 # past ~700 lets the bow reach the span itself,
                                 # which is where lobes start meeting each other.
TONGUE_WAVE_CYCLES = 1.2         # how many waves fit along the tongue. More lobes
                                 # means more chances for two of them to cross once
                                 # the shaft is wide relative to its span.
TONGUE_WAVE_SPEED = 19.0         # rad/s the wave travels toward the tip
# How far the shaft bows sideways, and it is NOT a fixed fraction of the current
# length -- that made the bow vanish exactly when the tongue was longest.
# Instead the tongue tracks MATERIAL: how much of it is still outside the mouth.
# On the way back the mouth swallows the tongue, and it swallows more slowly
# than the two ends close on each other -- that difference is the slack, and the
# slack is the coil. Crucially the number of SEGMENTS still outside shrinks with
# the material (see Player._tongue_active): keeping every segment while only the
# tip came home crammed a fixed point count into a vanishing span, and the
# points had nowhere to go but sideways, folding the shaft into a knot.
TONGUE_TAUT_BOW = 0.03           # bow while it is being thrown: nearly straight
TONGUE_COIL_MAX = 0.40           # cap on the bulge, fraction of material length
TONGUE_SAG_SHARE = 0.34          # of the bulge that goes into the downward droop;
                                 # kept below the wave share so the coil reads as
                                 # gathering rather than as the tongue falling over
TONGUE_WAVE_SHARE = 0.95         # ...and into the travelling wave
TONGUE_RECOIL = 105.0            # px/s the lizard is tugged toward what it grabs
TONGUE_DRAG = 1500.0             # px/s^2 pulling a grabbed enemy toward the mouth
TONGUE_YANK = 240.0              # px/s inward impulse the moment the line goes taut

# Wind-up before each player verb fires (issue #5), and the squat_bias the body
# holds during it (issue #9).
#
# ZERO ON PURPOSE. Wind-up is for things you fight, not for the thing you ARE:
# a boss telegraphing is information, the player's own dash stalling is just
# latency, and 60-100 ms on the core verbs read as the whole game being
# sluggish. The Anticipation gate is still in place at 0 -- it fires on the
# press frame but still exactly once per press, so holding a button cannot
# repeat-fire, which is the half of issue #5 worth having.
#
# Raise any of these above 0 and the coil comes back with it: the *_SQUAT value
# is what the body holds during the window (< 1.0 crouches, > 1.0 stretches).
# Enemy and boss wind-ups are a separate system and untouched -- see
# BossAI's 'windup' state and the shoot_charge / lunge_t / grapple_t timers.
DASH_ANTIC_T = 0.0
DASH_ANTIC_SQUAT = 0.86
TONGUE_ANTIC_T = 0.0
TONGUE_ANTIC_SQUAT = 1.12
WHIP_ANTIC_T = 0.0
WHIP_ANTIC_SQUAT = 0.90
KILL_ENERGY = 4      # energia devolvida ao abater (sustenta o combo agressivo)

# rabada: golpe de cauda. A clava aumenta o dano e o empurrao; o ferrao envenena.
# Curvatura TOTAL da cauda no auge, distribuida entre as juntas (peso quadratico
# rumo a ponta). Nao e o giro de um bloco: aplicar tudo na primeira junta vira
# dobradica. O golpe faz um periodo inteiro -> varre os dois lados numa so vez.
WHIP_SWEEP = 150
WHIP_TIME = 0.68         # duracao do golpe (dois lados cabem aqui). Mais lento le
                         # melhor: da peso e da tempo de ver a cauda passar.
WHIP_COST = 10
# A cauda NUA e fraca de proposito: sem upgrade ela vale pelo empurrao e pelo
# controle de espaco, nao pelo dano. O dano de verdade vem dos modificadores.
# Antes era 5 fixo e NAO escalava com nada (`might` so era lido pelas armas), ou
# seja a rabada era identica na onda 1 e na onda 20: dominava cedo e sumia tarde.
# Hoje `_whip_hit` multiplica por `player.might`, entao Vigor (+20%/carta) e
# Potencia (DNA, +6%/nivel) finalmente melhoram o golpe.
#   nua .............. 2   (critico 4)
#   + cauda-clava .... 5,2 (critico 10,4)
#   + clava e 3 Vigor  9   (critico 18)
WHIP_DAMAGE = 2
# 2.6 -> 2.3: retoque leve na escala ("dano subindo rapido demais"). O corte
# maior veio da area (7 -> 2-3 alvos por golpe); a clava continua sendo O upgrade
# da cauda, so um pouco menos ingreme.
WHIP_CLUB_MULT = 2.3
# Hitbox da rabada: so as juntas da PONTA (nao a metade que anima) e alcance
# menor -- a area cheia acertava ~7 de 12 num circulo, "matava a sala inteira".
WHIP_HIT_JOINTS = 3      # quantas juntas do final ferem
WHIP_REACH = 1.05        # x max_r (era 1.6)
WHIP_KNOCK = 170         # empurrao base (a clava usa WHIP_KNOCK_CLUB)
WHIP_KNOCK_CLUB = 460
# A simulacao e fixa em SIM_HZ e o desenho NAO interpola entre estados, entao
# renderizar acima de SIM_HZ so redesenha frames identicos: era 120, ou seja 2x o
# custo de draw + smoothscale + flip (a GPU ficava em 100%) por zero ganho visual.
RENDER_FPS = SIM_HZ

TAU = math.tau

# --- palette: VIVID, saturated, cartoonish (dark ground -> glow pops) ------- #
COL_BG      = (16, 14, 30)                          # void / behind the world
COL_BG2     = (26, 24, 50)
COL_DOT     = (48, 46, 84)
COL_PLAYER  = [(78, 236, 126), (54, 200, 116)]     # P1 vivid green
COL_PLAYER2 = [(72, 212, 255), (52, 176, 236)]     # P2 vivid cyan
COL_ENEMY   = (255, 72, 88)
COL_PREY    = (255, 210, 64)
COL_FRIEND  = (168, 120, 255)
COL_BUG     = (255, 96, 224)
COL_FRUIT   = (255, 122, 66)
COL_EGG     = (245, 245, 224)
COL_POLLEN  = (250, 214, 90)     # moeda da run (bolsa no camp, particulas de compra)
COL_WHITE   = (250, 250, 255)
COL_INK     = (16, 14, 26)
COL_HUD     = (240, 240, 252)
# Cores compartilhadas de efeito -- estavam soltas como tuplas hardcoded, subindo aqui
# para nao divergirem em silencio (o creme do spark tem que casar com o glow do popup).
COL_FX_SPARK    = (255, 240, 200)   # hit spark: bege quente (dash/rabada/impacto)
COL_FX_REVIVE   = (255, 240, 160)   # segundo folego: ouro claro (ring+spark+popup)

# --- Fase 5: framework de chefes (boss.py) ---------------------------------- #
# Telegrafo >=27 frames (0.45s a 60Hz) e regra dura do projeto (fase 2). Windups
# dos padroes ficam bem acima disso -- e tempo E visibilidade, nunca so um.
# Issue #118: a regra vira codigo -- BOSS_WINDUP_FLOOR e o piso aplicado via
# BossAI._eff_windup. Cada windup abaixo e dimensionado para que
# PATTERNS[pid]['windup'] * windup_mult(mood) >= 0.45 mesmo no enraivecido
# (o multiplicador mais agressivo, 0.65), entao nenhum telegrafo real cai
# abaixo do piso em qualquer humor.
BOSS_INTRO_TIME = 1.0       # entrada: invulneravel, corpo ainda assentando
BOSS_TRANSITION_TIME = 1.0  # troca de fase: invulneravel (~1s), no maximo 2 coisas mudam
# Issue #118: cadence is now a MOVES trail, not a long pause. The default
# MIN/MAX collapsed to near zero; the per-boss `cd_mul` from the phase kit
# becomes the rhythm signature. BOSS_CD_FLOOR is the global safety net so a
# cd_mul of 0 (or very small) cannot make the boss illegible.
BOSS_CD_MIN = 0.0           # near zero; the per-boss cd_mul carries the signature
BOSS_CD_MAX = 0.05
BOSS_CD_FLOOR = 0.15        # safety net: never below 0.15s of breath between attacks
BOSS_RECOVER_TIME = 0.15    # default post-attack freeze (charged moves override)
BOSS_APPROACH_SPEED = 0.55  # fracao da velocidade normal enquanto se aproxima
# 0.45s is the 27-frame rule at SIM_HZ=60 made code: everything called a
# "telegraph" stays at >= 0.45s of windup, before any mood multiplier. The
# clamp lives in BossAI; the rule is documented in enemy-behaviors.md.
BOSS_WINDUP_FLOOR = 0.45
# Issue #123: Rei Lagarto's windups sit at the top of the pool -- the
# longest of the five signatures, the boss where the player learns that
# a telegraph language exists. These constants are shared with other
# bosses (Kraken, Beetle, Crystal, Wasp, ANKH also use fan/shockwave/
# radial) so the bump raises the floor for everyone -- the other four
# signatures (#121, #122, #124, #125) keep their tighter cadences
# through ``cd_mul`` and per-pattern overrides.
BOSS_RADIAL_WINDUP = 1.1
BOSS_RADIAL_COUNT = 10
BOSS_RADIAL_SPEED = 230
BOSS_RADIAL_DMG = 17
BOSS_FAN_WINDUP = 1.1
BOSS_FAN_COUNT = 5
BOSS_FAN_SPREAD = 46         # graus, ponta a ponta
BOSS_FAN_SPEED = 260
BOSS_FAN_DMG = 16
BOSS_BARRAGE_WINDUP = 0.7
BOSS_BARRAGE_SHOTS = 4
BOSS_BARRAGE_GAP = 0.12
BOSS_BARRAGE_SPEED = 300
BOSS_BARRAGE_DMG = 14
BOSS_BARRAGE_LEAD = 0.8      # QUALIDADE da previsao (0..1), nao segundos -- uma
                             # formula so (emitter.lead_point), que tira o tempo do
                             # voo. Chefe le bem mas nao perfeito: 0.8 deixa margem
                             # para quem muda de ritmo. O ANTECIPADOR usa 1.0.
BOSS_SUMMON_WINDUP = 0.9
BOSS_SUMMON_COUNT = 2
BOSS_SUMMON_CD = 6.0         # separado do cd normal -- nao pode invocar toda vez

# --- Resistencia a interrupcao (issue #119) --------------------------------- #
# `knockback = 0` (flow/rounds.py) ja tirou o empurrao do chefe. O que sobrou
# atrapalhando era o `slow`, que passava por `Lizard.apply_slow` sem nenhuma
# resistencia: uma pilha de Feromonio + projetil-lento levava o chefe a 40% da
# velocidade e desligava a leitura dos padroes de movimento. Nao e imunidade --
# Feromonio e projetil-lento precisam continuar sendo escolha valida contra
# chefe -- e um piso: o multiplicador nunca desce disso, empilhe quantas fontes
# empilhar, e a duracao de cada fonte e cortada. Ver docs/concepts/combat.md.
BOSS_SLOW_FLOOR = 0.7        # 30% mais lento da pra sentir; 0.4 (Feromonio nivel
                             # 4) deixava a orbita ilegivel
BOSS_SLOW_TIME_MULT = 0.5    # metade da duracao pedida, seja qual for a fonte
BOSS_HIT_FLASH = 0.45        # pico de hit_flash num acerto em chefe: continua
                             # sendo feedback de acerto, mas fica abaixo do
                             # limiar de 0.5 da pose 'hurt' (creatures/ai/posing)

# --- BossAI 2.0 (plans/02_sistema_chefes.md): mood + novos padroes ---------- #
BOSS_CORNERED_DIST = 120     # jogador mais perto que isso -> mood 'cornered'
BOSS_FRUSTRATION_SEC = 5.0   # sem acertar por tanto tempo -> mood 'frustrated'
# charge: bumped from 0.5 to 0.7 so even the enraged (0.65) multiplier
# leaves the windup at 0.455s -- the 27-frame rule applies to charge too,
# not just ranged attacks. The dash itself is the danger; the windup is
# the only window to react.
# Issue #123: bumped 0.7 -> 1.1 -- Rei's charge windup is part of the
# "longest telegraph" signature. The dash still kills at contact, the
# player just gets a longer read.
BOSS_CHARGE_WINDUP = 1.1
BOSS_CHARGE_TIME = 0.65      # duracao da investida em si
BOSS_CHARGE_SPEED_MULT = 2.0 # fracao de max_speed durante a investida
# Issue #123: bumped 0.7 -> 1.1 -- Rei's shockwave is the longest ring
# telegraph of the pool. See the docstring in patterns.king_phases.
BOSS_SHOCKWAVE_WINDUP = 1.1
BOSS_SHOCKWAVE_RADIUS = 210
BOSS_SHOCKWAVE_DMG = 19
BOSS_SPIRAL_WINDUP = 0.7
BOSS_SPIRAL_SHOTS = 14
BOSS_SPIRAL_GAP = 0.05
BOSS_SPIRAL_SPEED = 240
BOSS_SPIRAL_DMG = 14
BOSS_SPIRAL_TURN = 46        # graus de rotacao entre um tiro e o proximo

# Rei Lagarto (primeiro chefe autoral, onda 5) -- mecanica "Cicatriz"
KING_SCAR_SLOW = 0.55
KING_SCAR_TIME = 2.5
KING_SCAR_DMG = 6
KING_SCAR_LIFE = 14.0        # some na transicao de fase de qualquer forma

# pincha: bumped from 0.3 to 0.7 (issue #118). The pincer is no longer
# "fast" in the windup sense; the danger is the contact damage, not the
# tell. The 27-frame rule is the floor for every telegraph, including
# contact bites -- the player reads the body posture, not the snap.
BOSS_PINCHA_WINDUP = 0.7
BOSS_PINCHA_REACH = 1.5      # x max_r
BOSS_PINCHA_DMG = 20
BOSS_DEATHROLL_SHOTS = 40    # spiral bem mais denso/rapido -- reusa spiral_pattern
BOSS_DEATHROLL_TURN = 95     # graus/tiro (spiral normal: 46)
BOSS_DEATHROLL_GAP = 0.03    # spiral normal: 0.05

# Centopeiadeira (onda 10 / tier 2) -- "Degradacao": encolhe e acelera por fase
CENT_BOSS_SHRINK = 0.18      # genome.length perdido por transicao
CENT_BOSS_SPEED_BUMP = 1.25  # genome.speed x por transicao

# Kraken-Mor (onda 15 / tier 3)
BOSS_ARMS_RAIN_WINDUP = 0.7
BOSS_ARMS_RAIN_COUNT = 3
BOSS_ARMS_RAIN_SPREAD = 220  # raio em volta do alvo onde os pontos caem
BOSS_ARMS_RAIN_RADIUS = 90
BOSS_ARMS_RAIN_DMG = 17

# Primordial (onda 20, chefe final do modo normal)
BOSS_MASSIVE_FAN_WINDUP = 0.9        # telegrafos grandes e lentos (doc: 0.8s+)
BOSS_SKY_SLAM_WINDUP = 1.0           # sombra enorme -- tempo de sobra pra sair
BOSS_SKY_SLAM_RADIUS = 130
BOSS_SKY_SLAM_DMG = 30
BOSS_SKY_SLAM_PUDDLE_R = 100         # magma que fica depois do impacto
BOSS_SKY_SLAM_PUDDLE_DMG = 6
BOSS_SKY_SLAM_PUDDLE_LIFE = 5.0

# Mae-Escaravelho (endless, tier5+)
BOSS_WEB_TRAP_WINDUP = 0.7
BOSS_WEB_TRAP_R = 85
BOSS_WEB_TRAP_DMG = 2
BOSS_WEB_TRAP_LIFE = 6.0
BOSS_WEB_TRAP_SLOW = 0.4
# Olho-Sismico (B9, tier 5) -- "O Observador": globo ocular flutuante (plan='orbital').
# Mecanica do Olho: acertar o olho ABERTO da o critico de cabeca de graca (ja e o
# ponto fraco); durante a piscada (0.1s aleatoria) o olho fica blindado -- nao pode
# ser critico (hit_test devolve 'body') e leva 75% menos (dmg_taken_mult).
EYE_BLINK_DUR = 0.1              # membrana desce+sobe: janela em que o olho e blindado
EYE_BLINK_DMG_MULT = 0.25       # golpe durante a piscada = 75% menos dano
# (lo, hi) do intervalo entre piscadas por fase: entediado -> constante. O flip
# do <33% e abrupto (a fase 3 pisca sem parar), casando com eye_personality.
EYE_BLINK_INTERVAL = ((3.5, 5.0), (2.0, 3.2), (0.45, 0.9))
EYE_GAZE_WINDUP = 0.7           # iris brilha 0.7s * 60 = 42 frames (> 27); a
                                 # eye_personality zera o encurtamento de tell, entao
                                 # o gaze fica 42 frames em TODO mood (regra do telegrafo)
EYE_GAZE_SHOTS = 22
EYE_GAZE_GAP = 0.04
EYE_GAZE_TURN = 9               # varredura lenta (graus por tiro) -- "varre lentamente"
EYE_GAZE_SPEED = 300
EYE_GAZE_DMG = 10
EYE_GAZE_ARC = 70               # comeca a varredura ARC/2 antes do jogador
# bumped from 0.4 to 0.7 -- eye_personality zeroes tell_mult, so the
# multiplier is 1.0 across moods for the eye, but the safety check
# uses the worst-case multiplier (0.65) to catch any future pattern
# being reused by a boss with the default personality. The eye's multiplier
# leaves 0.7 untouched; a future re-user with the default multiplier
# still hits 0.455s in enraged.
EYE_SWIPE_WINDUP = 0.7
EYE_SWIPE_REACH = 2.6          # x max_r (o tentaculo alcanca longe)
EYE_SWIPE_DMG = 18
EYE_ORB_WINDUP = 0.7           # glow nos tentaculos
EYE_ORB_COUNT = 3
EYE_BULLET_WINDUP = 0.7
EYE_BULLET_SHOTS = 60          # bullet hell: spiral bem denso reusando spiral_pattern
EYE_BULLET_TURN = 33
EYE_BULLET_GAP = 0.035
EYE_BULLET_SPEED = 200
EYE_BULLET_DMG = 12

# A Muralha (B10, tier 6) -- plan='fixed', arena corridor
# Fire breath: sweeping cone from mouth
MURALHA_FIRE_WINDUP = 0.7
MURALHA_FIRE_DURATION = 2.0
MURALHA_FIRE_DMG = 12
MURALHA_FIRE_TICK = 0.15
MURALHA_FIRE_SPEED = 220
MURALHA_FIRE_SPREAD = 60       # degrees
# Fire breath per-tick settings (fire_breath pattern uses tick-based)
MURALHA_BREATH_SHOTS = 12       # shots per breath burst
MURALHA_BREATH_GAP = 0.12       # gap between bursts
MURALHA_BREATH_SPEED = 220
MURALHA_BREATH_DMG = 12
MURALHA_BREATH_SPREAD = 60      # degrees; the breath cone when a pattern omits it
# Hand slam: stone hands from sides. Bumped from 0.5 to 0.7 so the
# wall_personality's default enraged multiplier (0.65) still leaves the
# windup at 0.455s -- the floor applies to the wall too.
MURALHA_HAND_WINDUP = 0.7
MURALHA_HAND_DMG = 22
MURALHA_HAND_RADIUS = 80
MURALHA_HAND_SPRING_STIFF = 8.0
MURALHA_HAND_SPRING_DAMP = 0.7
# Eye laser (beam barrage): multiple eyes firing beams. Bumped 0.6 -> 0.7
# for the same reason; the eye laser is the wall's most dangerous attack
# and got the shortest windup, which violated the floor.
MURALHA_EYE_WINDUP = 0.7
MURALHA_EYE_BEAMS = 3
MURALHA_EYE_SPEED = 400
MURALHA_EYE_DMG = 10
MURALHA_EYE_GAP = 0.08
MURALHA_EYE_SPREAD = 45         # degrees between the outermost beams
# Bouncing bullets (ricochete). Bumped 0.5 -> 0.7 -- the ricochet fans
# out from a wide arc, so the wall's windup is the only signal.
MURALHA_BOUNCE_WINDUP = 0.7
MURALHA_BOUNCE_COUNT = 5
MURALHA_BOUNCE_SPEED = 280
MURALHA_BOUNCE_DMG = 14
MURALHA_BOUNCE_BOUNCES = 3
MURALHA_BOUNCE_SPREAD = 70      # degrees the ricochet volley fans out over
# Grid of fire (ground hazard). The grid is anchored to the arena
# (900x640), so the cell size decides how many puddles one cast asks for --
# and Game.spawn_puddle caps the world at 40. At cell 80 the arena wanted 59
# and the last 19 were silently dropped, leaving the right third of the box
# dark; 120 asks for 23 and fits with room for the player's own puddles.
MURALHA_GRID_WINDUP = 0.8
MURALHA_GRID_CELL = 120
MURALHA_GRID_DMG = 8
MURALHA_GRID_TICK = 0.3
# Tem que ser MENOR que o intervalo que reapplica o padrao (recover +
# BOSS_CD_FLOOR * cd_mul da fase 3 + windup = ~1.0 s), senao duas grades
# se sobrepoem e o dano empilha -- a mesma regra do Acido, da poca de
# veneno e do slow do ferrao. Ver tools/check_muralha.py.
MURALHA_GRID_LIFE = 1.0
# Arena fire pushes player
MURALHA_FIRE_PUSH = 350        # px/s push toward wall
MURALHA_FIRE_DMG = 6           # dps from ground fire

# --------------------------------------------------------------------------- #
# Issue #167: 5 new projectile hooks + slow_homing dial.
# All read by ``lagarto.combat.projectile``; tuning happens here so the
# pattern rows in ``lagarto.flow.boss.patterns`` can stay dial-only.
# --------------------------------------------------------------------------- #
CHAIN_LINK_DIST = 120          # px: a chain link draws between two projectiles within
CHAIN_BREAK_DIST = 200         # px: link breaks if either end drifts past this
CHAIN_DMG_BONUS = 3            # bonus damage per chain link on player contact
CHAIN_MAX_PER_PROJECTILE = 3   # cap partners per projectile (avoids N*(N-1)/2 lines)
CHAIN_BEZIER_SAMPLES = 6       # segments per chain Bezier render
CHAIN_SPARK_GAP = 0.07         # seconds between mid-link spark bursts
WAVE_FREQ = 8.0                # rad/s: base wave phase rate
WAVE_AMP = 12.0                # px: peak perpendicular displacement
BOOMERANG_RETURN_TIME = 0.8    # s: time before boomerang flips
BOOMERANG_RANGE = 280          # px: distance from shooter -> return point
BURST_STOP_TRAVEL = 0.5        # s: time before burst_stop detonates
BURST_STOP_PUDDLE = dict(r=42, dmg=4, life=2.5, hue=18, tick=0.5)
SPIRAL_RADIUS_INIT = 80        # px: starting orbit radius
SPIRAL_RADIUS_DECAY = 0.96     # factor per FRAME at 60 Hz; == ~0.28s half-life
SPIRAL_OMEGA = 2.0             # rad/s: angular speed
