"""Champions: elite spawns that make a familiar enemy read as a different creature.

Two layers on purpose, because they solve different problems.

**Variants** are named creatures with an identity -- a colour, a *visible trait
that explains the ability*, and behaviour. Rain World's lizard breeds are the
model: the yellow one has long antennae **because** it coordinates a pack, the
white one is pale **because** it ambushes. The trait is the tell, and a recolour
with no tell is a lie the player only discovers by dying to it.

**Modifiers** are purely mechanical (armoured, giant, explosive), stack on top of
anything including a variant, and buy combinatorial variety for very little code.

Legibility rules both layers: a champion announces itself with tint + scale + its
own glow, and its health multiplier stays **modest**. A champion is a threat
because of what it *does*; an enemy that is merely a sponge teaches nothing.

This package is a deliberate exception to the empty-``__init__`` convention: it
re-exports so ``champions.maybe_promote`` keeps working unchanged.
"""

from .base import (BY_ID, CHAMPIONS, MODIFIERS, VARIANTS, Champion, chance,
                   maybe_promote, promote_to)

__all__ = ['BY_ID', 'CHAMPIONS', 'MODIFIERS', 'VARIANTS', 'Champion', 'chance',
           'maybe_promote', 'promote_to']
