# Cache the camera transform, invalidated by property setters

**Context.** `Camera.w2s` is the hottest function in the frame — around 5,500
calls per frame with 30 creatures on screen, roughly 4.7 ms of a ~13 ms draw,
more than any drawing primitive. It was recomputing an affine transform from
`self.center`, `self.pos.x/y`, `self.zoom` and `self.shake_off.x/y` on every
call: about ten attribute lookups to derive something that only changes when
the camera itself moves, which is once per frame.

**Decision.** Fold zoom, position, screen centre and shake into three cached
floats (`_z`, `_ox`, `_oy`) so `w2s` is one multiply-add per axis. Make `pos`,
`zoom`, `center` and `shake_off` **properties** whose setters call `_refresh()`.
Callers keep writing `cam.pos = Vector2(...)` exactly as before and never learn
the cache exists.

**Why.** Attribute lookups were the cost, not arithmetic, and the derived value
has a much lower change frequency than its read frequency — the textbook case
for caching. Doing it behind properties rather than behind an explicit
`cam.begin_frame()` call is what makes it safe: an explicit refresh is a fourth
thing every new call site has to remember, and this repo has already been bitten
three times by "a second call site forgot to update the new state" (the menu's
hand-rolled `integrate()` subsets all forgot `tail_spring`).

**Consequences.**

- **Never mutate a camera vector in place.** `cam.pos.x = 5` or
  `cam.pos += v` bypasses the setter and silently leaves the cache stale —
  every world-to-screen conversion is then wrong until something reassigns.
  Assign a new `Vector2`. Nothing in the tree does otherwise today, and
  `camera.py`'s docstring says so.
- Reversing means unwinding four properties back to plain attributes, and
  giving up ~1.6 ms/frame of draw.
- `follow()` writes the three private fields directly and calls `_refresh()`
  once, rather than tripping three setters for one logical move.
- `w2s_many(points)` exists for the same reason at list granularity, and
  `visible()` inlines the transform to skip the `int()` rounding and the tuple
  it never needs.
- **`tools/check_camera.py` is the guard, and it tests the cache rather than
  the speed:** `w2s` must equal the naive formula after every mutation path
  (each setter, and `follow()` which moves pos + zoom + shake at once),
  `w2s_many` must agree with `w2s` pointwise, `visible()` must agree with the
  bounds test it replaced at three margins, and `s2w` must still invert `w2s`.
  A stale-cache regression fails it immediately; a benchmark would not.
