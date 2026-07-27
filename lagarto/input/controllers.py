"""Input abstraction.

Every player reads its intent through a ``Controller`` (move / aim / dash / tongue),
so keyboard+mouse, a second keyboard layout and a gamepad all drive the identical
lizard logic. A future ``NetworkController`` (inputs arriving from the network)
would slot in here without touching the simulation -- that is the "ready for
online" hook from the plan.
"""

import pygame
from pygame import Vector2

from ..core import config as C
from ..render import display
from ..core.mathutil import safe_norm, decay


# --------------------------------------------------------------------------- #
#  Gamepad helpers (robust across Xbox / PlayStation / generic pads)          #
# --------------------------------------------------------------------------- #

def _axis(joy, i, dead):
    try:
        v = joy.get_axis(i)
    except Exception:
        return 0.0
    return v if abs(v) > dead else 0.0


def _btn(joy, i):
    try:
        return bool(joy.get_button(i))
    except Exception:
        return False


def pad_move(joy, dead=0.25):
    """Left stick, falling back to the D-pad hat (some pads report the dpad only)."""
    m = Vector2(_axis(joy, 0, dead), _axis(joy, 1, dead))
    if m.length_squared() < 0.02:
        try:
            if joy.get_numhats() > 0:
                hx, hy = joy.get_hat(0)
                m = Vector2(hx, -hy)          # hat y is up-positive; screen y is down
        except Exception:
            pass
    return m


def pad_aim(joy, dead=0.25):
    """Right stick. Axis layout differs by pad -> pick by axis count."""
    try:
        n = joy.get_numaxes()
    except Exception:
        n = 0
    if n >= 6:
        return Vector2(_axis(joy, 3, dead), _axis(joy, 4, dead))   # Xbox-style
    if n >= 4:
        return Vector2(_axis(joy, 2, dead), _axis(joy, 3, dead))   # some pads
    return Vector2()


def pad_dash(joy):
    return _btn(joy, 0) or _btn(joy, 5)          # A / RB


def pad_tongue(joy):
    return _btn(joy, 2) or _btn(joy, 1) or _btn(joy, 4)   # X / B / LB


def pad_whip(joy):
    return _btn(joy, 3)                          # Y


def pad_item(joy):
    return _btn(joy, 1)                          # B


TRIGGER_DEAD = 0.3       # a trigger is a 0..1 axis; this is where it counts as pressed


def pad_roll(joy):
    """LT or RT -- the only slot left (all four face buttons are taken).

    Raw-joystick fallback only, and only on a 6-axis pad: on a 4-axis one
    ``pad_aim`` reads axes 2/3 as the RIGHT STICK, so trusting axis 2 there would
    make aiming roll.
    """
    try:
        if joy.get_numaxes() < 6:
            return False
    except Exception:
        return False
    return _axis(joy, 2, TRIGGER_DEAD) > 0 or _axis(joy, 5, TRIGGER_DEAD) > 0


class Pad:
    """A gamepad.

    Prefers SDL2's **GameController** API, which normalises the layout per device
    (right stick is always RIGHTX/RIGHTY, A is always A) using SDL's mapping
    database -- so DualSense, Xbox and generic pads all work. Falls back to the raw
    joystick axis guesswork only if the pad isn't in the database.
    """

    def __init__(self, index):
        self.ctrl = None
        self.joy = None
        self.name = 'gamepad'
        try:
            from pygame._sdl2 import controller as sdlc
            sdlc.init()
            if sdlc.is_controller(index):
                self.ctrl = sdlc.Controller(index)
                self.name = self.ctrl.name
        except Exception:
            self.ctrl = None
        if self.ctrl is None:
            self.joy = pygame.joystick.Joystick(index)
            self.joy.init()
            self.name = self.joy.get_name()

    # -- GameController helpers -- #
    def _ca(self, axis, dead=0.25):
        try:
            v = self.ctrl.get_axis(axis) / 32768.0
        except Exception:
            return 0.0
        return v if abs(v) > dead else 0.0

    def _cb(self, b):
        try:
            return bool(self.ctrl.get_button(b))
        except Exception:
            return False

    # -- unified interface -- #
    def move(self):
        if self.ctrl:
            m = Vector2(self._ca(pygame.CONTROLLER_AXIS_LEFTX),
                        self._ca(pygame.CONTROLLER_AXIS_LEFTY))
            if m.length_squared() < 0.02:
                m = Vector2(self._cb(pygame.CONTROLLER_BUTTON_DPAD_RIGHT)
                            - self._cb(pygame.CONTROLLER_BUTTON_DPAD_LEFT),
                            self._cb(pygame.CONTROLLER_BUTTON_DPAD_DOWN)
                            - self._cb(pygame.CONTROLLER_BUTTON_DPAD_UP))
            return m
        return pad_move(self.joy)

    def aim(self):
        if self.ctrl:
            return Vector2(self._ca(pygame.CONTROLLER_AXIS_RIGHTX),
                           self._ca(pygame.CONTROLLER_AXIS_RIGHTY))
        return pad_aim(self.joy)

    def dash(self):
        if self.ctrl:
            return (self._cb(pygame.CONTROLLER_BUTTON_A)
                    or self._cb(pygame.CONTROLLER_BUTTON_RIGHTSHOULDER))
        return pad_dash(self.joy)

    def tongue(self):
        if self.ctrl:
            return (self._cb(pygame.CONTROLLER_BUTTON_X)
                    or self._cb(pygame.CONTROLLER_BUTTON_LEFTSHOULDER))
        return pad_tongue(self.joy)

    def whip(self):
        if self.ctrl:
            return self._cb(pygame.CONTROLLER_BUTTON_Y)
        return pad_whip(self.joy)

    def item(self):
        if self.ctrl:
            return self._cb(pygame.CONTROLLER_BUTTON_B)
        return pad_item(self.joy)

    def roll(self):
        if self.ctrl:
            return (self._ca(pygame.CONTROLLER_AXIS_TRIGGERLEFT, TRIGGER_DEAD) > 0
                    or self._ca(pygame.CONTROLLER_AXIS_TRIGGERRIGHT, TRIGGER_DEAD) > 0)
        return pad_roll(self.joy)

    # -- menu navigation -- #
    def confirm(self):
        if self.ctrl:
            return self._cb(pygame.CONTROLLER_BUTTON_A)
        return _btn(self.joy, 0)

    def cancel(self):
        if self.ctrl:
            return self._cb(pygame.CONTROLLER_BUTTON_B)
        return _btn(self.joy, 1)

    def start(self):
        """Start/Options button -- opens and closes the pause menu.

        Without this a controller-only player could navigate the pause screen but
        had no way to *open* it (ESC was keyboard-only).
        """
        if self.ctrl:
            return self._cb(pygame.CONTROLLER_BUTTON_START)
        return _btn(self.joy, 7)


class MenuNav:
    """Turns pad sticks/d-pads into discrete menu events (with key-repeat).

    Menus are event-driven but a pad is polled, so this converts the held
    direction into single 'pressed' edges that repeat while held.
    """

    DEAD = 0.5
    FIRST = 0.35        # delay before the first repeat
    REPEAT = 0.13

    def __init__(self):
        self._dir = (0, 0)
        self._t = 0.0
        self._pa = self._pb = self._ps = False
        self.up = self.down = self.left = self.right = False
        self.confirm = self.cancel = self.start = False

    def poll(self, pads, dt):
        self.up = self.down = self.left = self.right = False
        self.confirm = self.cancel = self.start = False
        if not pads:
            self._dir = (0, 0)
            self._pa = self._pb = self._ps = False
            return
        x = y = 0.0
        a = b = s = False
        for p in pads:
            m = p.move()
            if abs(m.x) > abs(x):
                x = m.x
            if abs(m.y) > abs(y):
                y = m.y
            a = a or p.confirm()
            b = b or p.cancel()
            s = s or p.start()

        dx = 1 if x > self.DEAD else (-1 if x < -self.DEAD else 0)
        dy = 1 if y > self.DEAD else (-1 if y < -self.DEAD else 0)
        cur = (dx, dy)
        fire = False
        if cur != self._dir:
            self._dir = cur
            self._t = self.FIRST
            fire = cur != (0, 0)
        elif cur != (0, 0):
            self._t -= dt
            if self._t <= 0:
                self._t = self.REPEAT
                fire = True
        if fire:
            self.left, self.right = dx < 0, dx > 0
            self.up, self.down = dy < 0, dy > 0

        self.confirm = a and not self._pa
        self.cancel = b and not self._pb
        self.start = s and not self._ps
        self._pa, self._pb, self._ps = a, b, s


def describe_joysticks(pads):
    for p in pads:
        api = 'GameController (mapeamento SDL)' if p.ctrl else 'joystick cru (fallback)'
        print(f"[gamepad] '{p.name}' via {api}")


_ACTIONS = ('dash', 'tongue', 'whip', 'item', 'roll')


class Controller:
    """Input intent, with a short BUFFER on the action presses.

    A plain one-frame edge flag gets lost: ``poll()`` runs once per *rendered*
    frame while the sim runs on a fixed-step accumulator, so a frame can run zero
    sim steps (jitter, and every hit-stop). An edge detected on such a frame is
    never consumed, and the next poll sees the button as still held -- no new
    rising edge, press swallowed. Buffering the press for ``C.INPUT_BUFFER``
    seconds fixes that, and also lets a press land slightly *before* a cooldown
    ends instead of being thrown away.
    """

    def __init__(self):
        self.move = Vector2()
        self.aim_world = Vector2(1, 0)
        self._buf = {a: 0.0 for a in _ACTIONS}      # time left on a pending press
        self._held = {a: False for a in _ACTIONS}   # previous raw state (edge detect)

    def _edges(self, dash, tongue, whip=False, item=False, roll=False, dt=0.0):
        for action, now in zip(_ACTIONS, (dash, tongue, whip, item, roll)):
            if self._buf[action] > 0.0:
                self._buf[action] = decay(self._buf[action], dt)
            if now and not self._held[action]:      # rising edge only: holding never repeats
                self._buf[action] = C.INPUT_BUFFER
            self._held[action] = now

    def consume(self, action):
        """Called when the ability actually fires, so it can't fire twice."""
        self._buf[action] = 0.0

    @property
    def dash_edge(self):
        return self._buf['dash'] > 0.0

    @property
    def tongue_edge(self):
        return self._buf['tongue'] > 0.0

    @property
    def whip_edge(self):
        return self._buf['whip'] > 0.0

    @property
    def item_edge(self):
        return self._buf['item'] > 0.0

    @property
    def roll_edge(self):
        return self._buf['roll'] > 0.0

    def poll(self, keys, mouse_btn, cam, player_pos, dt=0.0):
        raise NotImplementedError


class KeyboardMouseController(Controller):
    label = "WASD + mouse / gamepad"

    def __init__(self, joy=None):
        super().__init__()
        self.joy = joy               # optional: P1 can also use a pad (single-player)

    def poll(self, keys, mouse_btn, cam, player_pos, dt=0.0):
        m = Vector2()
        if keys[pygame.K_w]: m.y -= 1
        if keys[pygame.K_s]: m.y += 1
        if keys[pygame.K_a]: m.x -= 1
        if keys[pygame.K_d]: m.x += 1

        dash = bool(mouse_btn[0]) or keys[pygame.K_SPACE]
        tongue = bool(mouse_btn[2]) or keys[pygame.K_LSHIFT]
        whip = bool(mouse_btn[1]) or keys[pygame.K_q]      # middle mouse / Q
        item = keys[pygame.K_e]                            # active item
        roll = keys[pygame.K_LCTRL]                        # rolamento (mouse has no
        #                                                    free button left)
        # the window is a scaled copy of the logical surface -> map the cursor back
        self.aim_world = cam.s2w(display.mouse_logical())

        if self.joy is not None:     # blend in the pad if one is present
            stick = self.joy.move()
            if stick.length_squared() > 0.02:
                m = stick
            aim = self.joy.aim()
            if aim.length_squared() > 0.02:
                self.aim_world = player_pos + aim * 200
            dash = dash or self.joy.dash()
            tongue = tongue or self.joy.tongue()
            whip = whip or self.joy.whip()
            item = item or self.joy.item()
            roll = roll or self.joy.roll()
        self.move = m
        self._edges(dash, tongue, whip, item, roll, dt)


class KeyboardController(Controller):
    label = "setas + IJKL"

    def poll(self, keys, mouse_btn, cam, player_pos, dt=0.0):
        m = Vector2()
        if keys[pygame.K_UP]: m.y -= 1
        if keys[pygame.K_DOWN]: m.y += 1
        if keys[pygame.K_LEFT]: m.x -= 1
        if keys[pygame.K_RIGHT]: m.x += 1
        self.move = m
        a = Vector2()
        if keys[pygame.K_i]: a.y -= 1
        if keys[pygame.K_k]: a.y += 1
        if keys[pygame.K_j]: a.x -= 1
        if keys[pygame.K_l]: a.x += 1
        if a.length_squared() < 0.1:
            a = m if m.length_squared() > 0.1 else Vector2(1, 0)
        self.aim_world = player_pos + safe_norm(a) * 200
        self._edges(keys[pygame.K_RCTRL], keys[pygame.K_RSHIFT],
                    keys[pygame.K_RALT], keys[pygame.K_u], keys[pygame.K_o], dt)


class GamepadController(Controller):
    label = "gamepad"

    def __init__(self, joy):
        super().__init__()
        self.joy = joy

    def poll(self, keys, mouse_btn, cam, player_pos, dt=0.0):
        self.move = self.joy.move()
        aim = self.joy.aim()
        if aim.length_squared() > 0.02:
            self.aim_world = player_pos + aim * 200
        elif self.move.length_squared() > 0.1:
            self.aim_world = player_pos + self.move * 200
        self._edges(self.joy.dash(), self.joy.tongue(), self.joy.whip(),
                    self.joy.item(), self.joy.roll(), dt)


def make_controllers(num_players, joysticks):
    if num_players == 1:
        # solo: keyboard+mouse, and a pad too if one is plugged in
        return [KeyboardMouseController(joysticks[0] if joysticks else None)]
    # co-op: P1 keyboard+mouse, P2 the pad (or a second keyboard layout)
    p2 = GamepadController(joysticks[0]) if joysticks else KeyboardController()
    return [KeyboardMouseController(), p2]
