"""Survivor-like auto-weapons: they fire/act on their own so the player just moves.

Each weapon is a small object with a **per-level table** (VS-style: each level does
something specific, shown on the card) and its own **animation**. Weapons scale with
the player's global stats: ``might`` (damage), ``cooldown_mult`` (rate), ``area_mult``
(size/range) and ``amount`` (+projectiles/orbitals). Archetypes: projectile, homing,
slow-projectile, damage-aura, slow-aura, knockback-aura, orbital, ground puddles
and one **Deployable** (``torreta``, which spends its cooldown on a body that
acts on its own -- see ``docs/concepts/deployable.md``).

One file per weapon, so each ``tick``, its ``levels`` table and its tuning live
together and can be retuned without touching the others. Shared machinery
(``Weapon``, ``Puddle``, ``_enemies_in``) is in `base`. The registry is assembled
here rather than in `base` because every weapon module imports `base` -- building
it there would make `base` import its own importers.
"""

from .base import Weapon, Puddle
from .spit import Cuspe
from .sting import Ferrao
from .web import Teia
from .spores import Esporos
from .pheromone import Feromonio
from .breath import Sopro
from .swarm import Enxame
from .acid import Acido
from .torreta import Torreta

WEAPONS = {w.id: w for w in [Cuspe(), Ferrao(), Teia(), Esporos(),
                             Feromonio(), Sopro(), Enxame(), Acido(), Torreta()]}
