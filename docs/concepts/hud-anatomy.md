# Anatomical HUD

Player vitals use distinct anatomical motions instead of interchangeable bars.
Health pulses, energy inflates, and XP fills a cranial cavity.

## Energy bellows

Energy is a bellows: its inflation follows `energy / max_energy`. Spending
energy collapses it on the same frame; its damped spring supplies reaction and
follow-through. Ability dials remain the source of cost-threshold information,
so the bellows has no cost notches.

## XP skull

The skull separates two progression signals:

- cerebrospinal fluid represents XP inside the current level and drains to zero
  at level-up;
- brain size and folds represent level, grow at level-up, and never shrink.

Brain size grows with the square root of level, so there is no reachable hard
cap and later growth becomes denser rather than escaping the skull. Each level
adds two folds. The fluid surface is a damped 16-point wave stepped at 30 Hz;
the renderer allocates no `Surface` per frame.

`tools/check_hud_anatomy.py` verifies monotonic brain growth, folds, fluid
drain and settling, bellows response, and two-player render cost.
