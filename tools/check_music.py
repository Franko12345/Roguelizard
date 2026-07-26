"""Assert the adaptive stem mix behaves (issue #24).

Runs against a REAL mixer (the dummy audio driver makes every call a no-op, so
it would prove nothing): the SDL 'disk' driver writes to a file and gives us
working channels.
"""
import os, sys
os.environ['SDL_AUDIODRIVER'] = 'disk'
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_DISKAUDIOFILE',
                      os.path.join(os.environ.get('TMPDIR', '/tmp'), 'lagarto_mixtest.raw'))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pygame
pygame.init()
from lagarto.audio import engine as audio

audio.init()
assert audio.ok(), "mixer did not open; cannot test the mix"
assert audio._stems, "no stems were built"

n_stems = len(audio._STEM_CURVES)
print(f"stems: {', '.join(audio._STEM_CURVES)}")

# 1. A heavy combat frame must not take the music apart. pygame will not evict
#    a playing stem (it drops the new sfx when saturated), so this passes with
#    or without set_reserved -- it is a regression guard on the mix surviving
#    load, not proof that reserving fixed a live bug.
assert pygame.mixer.get_num_channels() > n_stems + 1
audio.set_music_intensity(1.0)
for _ in range(120):
    audio.update_music(1 / 60)
# Saturate: with 24 channels and only 7 busy there is idle room, so a handful of
# sfx never need to evict anyone. The theft only shows once every channel is
# busy and pygame starts reusing them -- which is a heavy combat frame.
for _ in range(4):
    for name in audio._sfx:
        for _ in range(3):
            audio.play(name)
for name in audio._stems:
    playing = audio._stem_ch[name].get_sound()
    assert playing is audio._stems[name], \
        f"a sound effect took {name}'s channel (got {playing})"
busy = sum(1 for i in range(pygame.mixer.get_num_channels())
           if pygame.mixer.Channel(i).get_busy())
print(f"after saturating the mixer ({busy}/{pygame.mixer.get_num_channels()} channels busy), "
      f"all {n_stems} stems still hold their channels")

# 2. intensity drives the curve: calm has no percussion, boss has all of it
def mix(intensity):
    audio.set_music_intensity(intensity)
    for _ in range(200):            # let update_music ease all the way in
        audio.update_music(1 / 60)
    return {k: round(v, 4) for k, v in audio._stem_cur.items()}

calm, combat, boss = mix(0.0), mix(0.5), mix(1.0)
for label, m in (('calm  ', calm), ('combat', combat), ('boss  ', boss)):
    print(f"  {label}: " + "  ".join(f"{k}={m[k]:.3f}" for k in audio._STEM_CURVES))
assert calm['perc_low'] == 0.0 and calm['perc_high'] == 0.0, "calm must have no drums"
assert combat['perc_low'] > 0 and combat['perc_high'] == 0.0, "combat: kick in, hats out"
assert boss['perc_high'] > 0, "boss must bring the hats in"
assert boss['perc_low'] >= combat['perc_low']
for m in (calm, combat, boss):
    assert m['bass'] > 0 and m['pad'] > 0, "bass and pad are the constant floor"

# 3. the ease is gradual, not a step
audio.set_music_intensity(0.0)
for _ in range(200):
    audio.update_music(1 / 60)
audio.set_music_intensity(1.0)
audio.update_music(1 / 60)
one_frame = audio._stem_cur['perc_high']
assert 0.0 < one_frame < boss['perc_high'] * 0.5, \
    f"one frame should ease part-way, not snap: {one_frame} vs {boss['perc_high']}"
print(f"one frame of ease toward boss: perc_high {one_frame:.4f} -> settles {boss['perc_high']:.3f}")

# 4. switching back to a discrete track silences the stems and re-arms set_music
audio.set_music('victory')
assert audio._stem_mode is False
assert audio._music_name == 'victory'
audio.set_music_intensity(1.0)
assert audio._music_name is None, "stem mode must clear _music_name (needs `global`)"
audio.set_music('victory')
assert audio._music_name == 'victory', "set_music must work again after stem mode"
print("discrete <-> stem handover ok")
print("ALL OK")
