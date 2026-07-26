"""Persisted options in ``~/.lagarto/settings.json``.

Only display options for now (fullscreen / window scale / vsync). Everything is
best-effort: a missing, unreadable or corrupt file just falls back to defaults so
the game always starts. The meta-progression save (DNA/unlocks) will live in the
same folder later.
"""

import json
import os

DEFAULTS = {'fullscreen': False, 'scale': 2, 'vsync': True,
            'sfx_vol': 0.7, 'music_vol': 0.45,
            'perf': 0}      # medidor de FPS: 0 desligado / 1 fps / 2 detalhado


def _dir():
    return os.path.join(os.path.expanduser('~'), '.lagarto')


def path():
    return os.path.join(_dir(), 'settings.json')


def load():
    data = dict(DEFAULTS)
    try:
        with open(path(), 'r', encoding='utf-8') as f:
            raw = json.load(f)
        if isinstance(raw, dict):
            for k, v in DEFAULTS.items():
                got = raw.get(k, v)
                if isinstance(got, type(v)) or (isinstance(v, int) and isinstance(got, int)):
                    data[k] = got
    except Exception:
        pass                       # missing/corrupt -> defaults
    if data['scale'] not in (1, 2, 3):
        data['scale'] = DEFAULTS['scale']
    if data['perf'] not in (0, 1, 2):
        data['perf'] = DEFAULTS['perf']
    for k in ('sfx_vol', 'music_vol'):
        try:
            data[k] = min(1.0, max(0.0, float(data[k])))
        except Exception:
            data[k] = DEFAULTS[k]
    return data


def _atomic_write(p, obj):
    """Write ``obj`` as JSON to ``p`` atomically (tmp -> rename), creating its dir.

    The shared write primitive for everything under ``~/.lagarto`` -- ``save``
    below and the sandbox preset (``sandbox.py``) both funnel through it so there
    is one tmp->rename pattern, never a half-written file on disk.
    """
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(obj, f, indent=1)
    os.replace(tmp, p)


def save(data):
    try:
        _atomic_write(path(), {k: data.get(k, v) for k, v in DEFAULTS.items()})
        return True
    except Exception:
        return False


def save_display(display_mod, audio_mod=None):
    data = {'fullscreen': display_mod.is_fullscreen(),
            'scale': display_mod.get_scale(),
            'vsync': display_mod.get_vsync()}
    if audio_mod is not None:
        sfx, music = audio_mod.volumes()
        data['sfx_vol'], data['music_vol'] = sfx, music
    else:
        cur = load()
        data['sfx_vol'], data['music_vol'] = cur['sfx_vol'], cur['music_vol']
    data['perf'] = load()['perf']       # never clobber the perf toggle
    return save(data)
