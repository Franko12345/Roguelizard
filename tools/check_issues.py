"""Check each open GitHub issue against the LIVE code, not against memory.

An issue is only closed when the code says so. This walks every open ticket and
asserts a concrete marker for it -- a symbol that must exist, a value that must
have changed, a check script that must pass -- so "done" is a measurement and
not a claim. Rows marked ``--`` are honestly not done and carry the reason.

Run from the repo root:  python tools/check_issues.py
"""
import os, sys, subprocess, inspect
os.environ.setdefault('SDL_VIDEODRIVER','dummy'); os.environ.setdefault('SDL_AUDIODRIVER','dummy')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pygame; pygame.init()
from lagarto.core import config as C
from lagarto.flow import rounds
from lagarto.flow.boss import patterns as pat, arena as ar
from lagarto.flow.boss import ai as bossai
from lagarto.creatures import base as cbase, parts, species
from lagarto.creatures.player import Player
from lagarto.combat.evolution import mutations as mut, synergies as syn
from lagarto.combat import charms
from lagarto.render import assets, icons, display
from lagarto.audio import engine as audio
from lagarto.game import menu, state_camp, loop as gameloop
from lagarto.input.controllers import _ACTIONS
from lagarto.flow.boss.personality import king_personality
import lagarto

src = lambda m: inspect.getsource(m)
R = []
def chk(num, name, ok, note=""):
    R.append((num, name, ok, note))

_mu = subprocess.run([sys.executable, 'tools/check_muralha.py'], capture_output=True,
                     env={**os.environ, 'PYTHONPATH': '.'})
chk(113, "grid na arena", 'arena_bounds' in src(__import__('lagarto.combat.emitter',
                                                          fromlist=['x']).grid_of_fire)
    and _mu.returncode == 0,
    "" if _mu.returncode == 0 else _mu.stderr.decode()[-90:])
_bm = subprocess.run([sys.executable, 'tools/check_boss_movement.py'], capture_output=True,
                      env={**os.environ, 'PYTHONPATH': '.'})
from lagarto.flow.boss import moves as bossmoves, ai as bossai
chk(118, "boss movement trail",
    'MOVES' in src(bossmoves) and 'move_orbit' in src(bossmoves)
    and 'moves.py' in str(bossmoves.__file__)
    and 'BOSS_WINDUP_FLOOR' in src(C)
    and C.BOSS_WINDUP_FLOOR >= 0.45
    and 'BOSS_CD_FLOOR' in src(C)
    and C.BOSS_CD_FLOOR >= 0.10
    and 'moves=' in src(pat)
    and _bm.returncode == 0,
    "" if _bm.returncode == 0 else _bm.stderr.decode()[-90:])
_kg = subprocess.run([sys.executable, 'tools/check_king_signature.py'], capture_output=True,
                      env={**os.environ, 'PYTHONPATH': '.'})
chk(123, "rei lagarto -- legibilidade",
    'proud_walk' in src(bossmoves)
    and '_pw_dir' in src(bossai)
    and '_path_samples' in src(bossai)
    and 'KING_SCAR_PATH_WINDOW' in src(bossai)
    and "_scar_path_snapshot" in src(bossai.spawn_scar)
    and "move='proud_walk'" in src(pat)
    and "moves=['proud_walk']" in src(pat)
    and C.BOSS_FAN_WINDUP >= 1.0 and C.BOSS_SHOCKWAVE_WINDUP >= 1.0
    and C.BOSS_RADIAL_WINDUP >= 1.0 and C.BOSS_CHARGE_WINDUP >= 1.0
    and king_personality().tell_mult == {}
    and _kg.returncode == 0,
    "" if _kg.returncode == 0 else _kg.stderr.decode()[-90:])
_ws = subprocess.run([sys.executable, 'tools/check_wasp_signature.py'], capture_output=True,
                      env={**os.environ, 'PYTHONPATH': '.'})
chk(122, "wasp signature",
    'dive_arc' in src(bossmoves) and 'flyby' in src(bossmoves)
    and 'curve_approach' in src(bossmoves) and 'climb_out' in src(bossmoves)
    and "'dive_line'" in src(__import__('lagarto.flow.boss.telegraph',
                                       fromlist=['x']))
    and "'shadow_circle'" in src(__import__('lagarto.flow.boss.telegraph',
                                            fromlist=['x']))
    and 'dive_arc' in src(__import__('lagarto.flow.boss.telegraph',
                                    fromlist=['x']))
    and 'terror_alado' in ar.ARENAS
    and _ws.returncode == 0,
    "" if _ws.returncode == 0 else _ws.stderr.decode()[-90:])
_ce = subprocess.run([sys.executable, 'tools/check_centipede_signature.py'], capture_output=True,
                      env={**os.environ, 'PYTHONPATH': '.'})
chk(124, "centopeiadeira signature -- burrow-as-locomotion",
    'move_spin_glide' in src(bossmoves) and 'move_lunge' in src(bossmoves)
    and "move='spin_glide'" in src(pat) and "move='lunge'" in src(pat)
    and "'burrow IS the locomotion'" in src(bossai)
    and _ce.returncode == 0,
    "" if _ce.returncode == 0 else _ce.stderr.decode()[-90:])
_sp = subprocess.run([sys.executable, 'tools/check_spider_signature.py'], capture_output=True,
                      env={**os.environ, 'PYTHONPATH': '.'})
chk(125, "aranha-rei signature -- erratic + siege",
    'move_erratic_step' in src(bossmoves) and 'move_trap_and_shift' in src(bossmoves)
    and 'cd_jitter' in src(pat) and 'cd_jitter' in src(bossai)
    and "move='erratic_step'" in src(pat) and "move='trap_and_shift'" in src(pat)
    and _sp.returncode == 0,
    "" if _sp.returncode == 0 else _sp.stderr.decode()[-90:])
_ttk = subprocess.run([sys.executable, 'tools/check_boss_ttk.py'], capture_output=True,
                       env={**os.environ, 'PYTHONPATH': '.'})
chk(120, "boss time-to-kill harness",
    os.path.exists('tools/check_boss_ttk.py')
    and 'PROFILES' in open('tools/check_boss_ttk.py').read()
    and 'BOSS_POOL' in open('tools/check_boss_ttk.py').read()
    and 'phase_reached' in open('tools/check_boss_ttk.py').read()
    and _ttk.returncode == 0,
    "" if _ttk.returncode == 0 else _ttk.stderr.decode()[-90:])
_tu = subprocess.run([sys.executable, 'tools/check_turret.py'], capture_output=True,
                     env={**os.environ, 'PYTHONPATH': '.'})
from lagarto.combat import weapons as weplib
chk(111, "deployable torreta", 'torreta' in weplib.WEAPONS
    and "'turret'" in src(__import__('lagarto.creatures.ai', fromlist=['x']))
    and _tu.returncode == 0,
    "" if _tu.returncode == 0 else _tu.stderr.decode()[-90:])
_br = subprocess.run([sys.executable, 'tools/check_boss_resist.py'], capture_output=True,
                     env={**os.environ, 'PYTHONPATH': '.'})
chk(119, "chefe resiste a slow", 'BOSS_SLOW_FLOOR' in src(cbase.Lizard.apply_slow)
    and C.BOSS_SLOW_FLOOR > 0 and C.BOSS_SLOW_TIME_MULT < 1.0
    and _br.returncode == 0,
    "" if _br.returncode == 0 else _br.stderr.decode()[-90:])
_ct = subprocess.run([sys.executable, 'tools/check_content.py'], capture_output=True,
                     env={**os.environ, 'PYTHONPATH': '.'})
from lagarto.creatures.ai import BEHAVIORS as _beh
chk(104, "conteudo bullet hell", {'lead', 'mortar'} <= set(_beh)
    and species.SPECIES['spitter']['genome'].shot is not None
    and 'dardo' in charms.CHARMS and _ct.returncode == 0,
    "" if _ct.returncode == 0 else _ct.stderr.decode()[-90:])
_roll = subprocess.run([sys.executable, 'tools/check_roll.py'], capture_output=True,
                       env={**os.environ, 'PYTHONPATH': '.'})
chk(103, "rolamento", hasattr(Player, 'rolling') and 'roll' in _ACTIONS
    and _roll.returncode == 0,
    "" if _roll.returncode == 0 else _roll.stderr.decode()[-90:])
_pj = subprocess.run([sys.executable, 'tools/check_projectile.py'], capture_output=True,
                     env={**os.environ, 'PYTHONPATH': '.'})
from lagarto.combat import projectile as projlib
chk(102, "projectile hooks", hasattr(projlib.Projectile(( 0, 0), (0, 0), (1, 1, 1)), 'on_update')
    and _pj.returncode == 0,
    "" if _pj.returncode == 0 else _pj.stderr.decode()[-90:])
from lagarto.render.fx import FX as _FX
chk(116, "faisca no lugar do rastro",
    not hasattr(projlib.Projectile((0, 0), (0, 0), (1, 1, 1)), 'trail')
    and 'pygame.draw.line' not in src(projlib)
    and 'direction' in inspect.signature(_FX.spark_burst).parameters
    and _pj.returncode == 0,
    "" if _pj.returncode == 0 else _pj.stderr.decode()[-90:])
_ss = subprocess.run([sys.executable, 'tools/check_sandbox_store.py'], capture_output=True,
                     env={**os.environ, 'PYTHONPATH': '.'})
from lagarto import sandbox as _sb
chk(107, "loja do sandbox", 'catalog = state_camp._roll_shop(g)' in src(_sb)
    and 'catalog = g._roll_shop()' not in src(_sb) and _ss.returncode == 0,
    "" if _ss.returncode == 0 else _ss.stderr.decode()[-90:])
_sp = subprocess.run([sys.executable, 'tools/check_shop_prices.py'], capture_output=True,
                     env={**os.environ, 'PYTHONPATH': '.'})
chk(105, "shop prices persist", 'shop_prices' in src(state_camp) and 'shop_prices' in src(gameloop)
    and C.SHOP_PRICE_MULT < 1.6 and _sp.returncode == 0,
    "" if _sp.returncode == 0 else _sp.stderr.decode()[-90:])
from lagarto.combat import emitter as emi
_fns = [p_['fn'] for p_ in pat.PATTERNS.values() if p_.get('fn')] + \
       [p_['select'] for p_ in pat.PATTERNS.values() if p_.get('select')]
chk(101, "shared emitter", bool(_fns)
    and all(f.__module__ == 'lagarto.combat.emitter' for f in _fns)
    and all(list(inspect.signature(f).parameters) == ['shooter', 'game', 'target', 'dials']
            for f in _fns)
    and 'def radial_burst' not in src(pat) and 'boss_ai.pattern_id' not in src(emi))
chk(98, "mouse offset", "RESIZABLE" in src(display) and "_screen.get_size()" in src(display)
    and "to_logical(pygame.mouse.get_pos())" in src(menu))
chk(75, "ANKH", 'ankh' in rounds.BOSS_POOL and len(pat.ankh_phases()) == 4
    and any('ankh' in ids for _, ids in rounds.BOSS_TIER_POOLS))
chk(74, "A Muralha", rounds.BOSS_POOL.get('muralha', {}).get('species') == 'muralha'
    and species.SPECIES['muralha']['genome'].plan == 'fixed' and 'muralha' in ar.ARENAS)
_muralha_sig = subprocess.run([sys.executable, 'tools/check_muralha_signature.py'],
                              capture_output=True, env={**os.environ, 'PYTHONPATH': '.'})
chk(121, "Muralha signature",
    'phase_sizes' in src(ar.BossArena)
    and 'muralha_on_phase' in src(pat)
    and 'invuln_states' in src(bossai.BossAI)
    and ('attack', 'recover') == tuple(rounds.BOSS_POOL['muralha'].get('invuln_states') or ())
    and tuple(ph['cd_mul'] for ph in pat.muralha_phases()) == (1.0, 1.0, 1.0)
    and _muralha_sig.returncode == 0,
    "" if _muralha_sig.returncode == 0 else _muralha_sig.stderr.decode()[-90:])
chk(73, "Olho-Sismico", 'olho_sismico' in rounds.BOSS_POOL
    and species.SPECIES['olho_sismico']['genome'].plan == 'orbital')
chk(72, "probe_display + __all__", not hasattr(lagarto, '__all__')
    and subprocess.run([sys.executable, 'tools/probe_display.py'],
                       capture_output=True, env={**os.environ}).returncode == 0)
chk(71, "doc paths", subprocess.run([sys.executable, 'tools/check_doc_paths.py'],
                                    capture_output=True).returncode == 0)
bal = open('docs/concepts/balance.md').read()
chk(28, "balance tracking", 'issue' in bal.lower() and ('|' in bal))
from lagarto.flow.boss import telegraph
chk(27, "telegraph module", len(telegraph.TELEGRAPHS) >= 7
    and 'TELEGRAPHS.get' in src(__import__('lagarto.flow.boss.ai', fromlist=['x'])))
chk(26, "boss arena", len(ar.ARENAS) >= 10 and 'for_boss' in src(rounds)
    and 'arena.apply' in src(rounds) and 'bounds' in src(cbase.Lizard.integrate))
root_ok = os.path.isdir(os.path.join(assets._ROOT, 'assets'))
chk(25, "assets", root_ok and 'ferrao_charm' in icons.ICONS
    and charms.CHARMS['ferrao'].icon == 'ferrao_charm')
chk(24, "adaptive music", hasattr(audio, 'set_music_intensity') and len(audio._STEM_CURVES) == 6)
chk(23, "difficulty", hasattr(rounds, 'wave_hp_bonus')
    and rounds.wave_hp_bonus(20) > int(20 * 0.7) * 1.5 and rounds.wave_cap(20, 6) > 6)
chk(22, "club charm-only", 'club' not in mut.MUTATIONS_LIST_IDS if False else
    all(m.id != 'club' for m in mut.MUTATIONS_LIST) and 'clava' in charms.CHARMS
    and any('clava' in s.needs for s in syn.SYNERGIES if s.id == 'bola'))
_t = subprocess.run([sys.executable, 'tools/check_tongue.py'], capture_output=True,
                    env={**os.environ, 'PYTHONPATH': '.'})
chk(21, "IK tongue", hasattr(Player, 'tongue_path') and _t.returncode == 0,
    "" if _t.returncode == 0 else _t.stderr.decode()[-90:])
chk(19, "menu dedup", '_step_creature_for_display' in src(menu)
    and src(menu).count('for leg in c.legs') <= 1)
chk(18, "outline", 'COL_INK, ink_w' in src(cbase) or 'C.COL_INK, ink' in src(cbase)
    or 'ink_w)' in src(cbase))
used = set()
for fn in dir(pat):
    if fn.endswith('_phases'):
        try:
            for ph in getattr(pat, fn)():
                used |= set(ph['patterns'])
        except Exception: pass
orphan_ids = {'minefield', 'gravity_well', 'teleport_strike'}
present = orphan_ids & set(pat.PATTERNS)
chk(14, "orphan patterns", not (present - used),
    f"in PATTERNS: {sorted(present) or 'none'}; of those still unused: {sorted(present - used) or 'none'}")
chk(12, "cosmetic skeleton", os.path.exists('lagarto/anim/cosmetics.py'),
    "rejected: 198 lines with zero callers")
chk(10, "ground adaptation", 'height_at' in open('lagarto/world/terrain.py').read(),
    "rejected: height_at/slope_at returned 0.0 unconditionally")
chk(9, "windup visual", C.DASH_ANTIC_T > 0, f"wind-ups zeroed by request; dash dust kept at launch")
chk(8, "tail chain", cbase.TAIL_CHAIN_LEN == 5 and
    subprocess.run([sys.executable, 'tools/check_tail_chain.py'], capture_output=True).returncode == 0)
p_src = src(Player)
chk(7, "follow-through", 'tongue_flick' in p_src,
    "whip ring-out lands via the #8 chain; tongue flick dropped (drew a frozen tongue)")
ai_antic = 'Anticipation' in open('lagarto/creatures/ai/ranged.py').read()
chk(5, "Anticipation", 'dash_antic' in p_src and ai_antic,
    "player gated; AI half rejected (was instantiate-and-never-read)")
chk(4, "oscillators", len(parts.OSC_PRESETS) >= 6 and
    subprocess.run([sys.executable, 'tools/check_oscillators.py'], capture_output=True).returncode == 0)

print(f"{'#':>4}  {'':2} {'issue':22} note")
for num, name, ok, note in sorted(R, key=lambda r: -r[0]):
    print(f"{num:>4}  {'OK' if ok else '--'} {name:22} {note}")
done = sum(1 for r in R if r[2])
print(f"\n{done}/{len(R)} verified done against the code")
