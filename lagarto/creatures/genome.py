"""Genome: a creature described entirely by numbers (RujiK the Comatose's idea).

A ``Genome`` is a bag of numeric traits -- size, body length, leg count, colour,
which parts it has, how it behaves. The generic ``Creature`` in ``creatures/base.py``
reads the genome to build its spine, legs and parts and to pick a colour, so
lizards / snakes / spiders / scorpions are just *different genomes*, not different
classes. The player's evolutions (Phase 4) mutate this same genome and the body
redraws itself -- no hand-made art per combination.
"""

from ..core import palette


class Genome:
    __slots__ = ('size', 'length', 'girth', 'leg_count', 'leg_len', 'radial',
                 'plan', 'knockback',
                 'eye_count', 'spikes', 'horns', 'plates', 'tail', 'fins',
                 'hue', 'sat', 'val', 'speed', 'hp', 'behavior', 'diet', 'name',
                 # how this creature SHOOTS: an emitter pattern + its dials
                 'shot',
                 # charm-driven visible parts
                 'antennae', 'wings', 'extra_eyes', 'spore_sacs', 'nectar_sac', 'fangs',
                 # weight/inertia feel (plans/01_animacao_procedural_avancada.md #7);
                 # default 0/0/1.0 = byte-for-byte the old turn/squash behaviour, so
                 # existing species are untouched until species.py opts a body in
                 'angular_damping', 'linear_damping', 'weight')

    def __init__(self, **kw):
        self.size = kw.get('size', 1.0)         # overall scale
        self.length = kw.get('length', 1.0)     # body elongation (joint count)
        self.girth = kw.get('girth', 1.0)       # body thickness
        self.leg_count = kw.get('leg_count', 4)
        self.leg_len = kw.get('leg_len', 1.0)
        self.radial = kw.get('radial', False)   # spider-style radial legs
        # body plan: 'normal' (chain lizard) | 'segmented' (centipede blob-chain)
        # | 'tentacle' (octopus: mantle + reaching arms). 'radial' stays its own flag.
        self.plan = kw.get('plan', 'normal')
        self.eye_count = kw.get('eye_count', 2)
        self.spikes = kw.get('spikes', 0)       # dorsal spike level (0..)
        self.horns = kw.get('horns', 0)         # head horn count
        self.plates = kw.get('plates', 0)       # armour level
        self.tail = kw.get('tail', 'normal')    # normal | club | sting | fin
        self.fins = kw.get('fins', 0)           # fin level (fish)
        self.hue = kw.get('hue', 130.0)
        self.sat = kw.get('sat', 0.82)
        self.val = kw.get('val', 0.95)
        self.speed = kw.get('speed', 1.0)
        self.hp = kw.get('hp', 2)
        self.knockback = kw.get('knockback', 1.0)     # <1 = shrugs off shove (heavy bruiser)
        self.behavior = kw.get('behavior', 'chase')   # chase | flee | wander | ranged | lunge
        # The attack pattern this creature fires, as data: ``dict(fn=<emitter
        # pattern>, **dials)``. Same shape the boss dial table uses, so a
        # species changes from a single spit to a radial burst by editing this
        # dict -- criatura = genoma (ADR-0001), and that includes how it shoots.
        self.shot = kw.get('shot', None)
        self.diet = tuple(kw.get('diet', ()))         # kinds this creature hunts
        self.name = kw.get('name', 'critter')
        # charm-driven visible parts (equip toggles these)
        self.antennae = kw.get('antennae', False)
        self.wings = kw.get('wings', False)
        self.extra_eyes = kw.get('extra_eyes', 0)
        self.spore_sacs = kw.get('spore_sacs', False)
        self.nectar_sac = kw.get('nectar_sac', False)
        self.fangs = kw.get('fangs', False)
        self.angular_damping = kw.get('angular_damping', 0.0)  # 0..0.95, slows turning
        self.linear_damping = kw.get('linear_damping', 0.0)    # 0..0.95, extra vel decay
        self.weight = kw.get('weight', 1.0)                    # >1 = less squash, slower squash-approach

    def copy(self):
        g = Genome.__new__(Genome)
        for s in self.__slots__:
            setattr(g, s, getattr(self, s))
        return g

    def color(self):
        return palette.hsv(self.hue, self.sat, self.val)

    def random_variation(self, rng):
        """A colour/size-jittered clone -- cheap procedural variety per spawn."""
        g = self.copy()
        g.hue = (self.hue + rng.uniform(-15, 15)) % 360
        g.sat = min(1.0, max(0.6, self.sat + rng.uniform(-0.08, 0.08)))
        g.val = min(1.0, max(0.78, self.val + rng.uniform(-0.06, 0.06)))
        g.size = self.size * rng.uniform(0.9, 1.14)
        g.speed = self.speed * rng.uniform(0.92, 1.1)
        return g


def basic_lizard(size=1.0):
    """Backwards-compatible default genome (a plain 4-legged lizard)."""
    return Genome(size=size, leg_count=4, hue=130, sat=0.82, val=0.95)
