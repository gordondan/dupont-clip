# dupont-clip

A parametric, 3D-printable clip that holds a row of Dupont jumper wires together
at 2.54 mm pitch, so they plug and unplug as one block and the wires comb out the
back in order.

Two printed parts, no supports, no hardware:

- **Clip** — front lip, head pocket, one wire channel per position, and two long
  snap arms down the sides.
- **Lid** — a flat plate with one rib per channel.

Drop each jumper in from above — head into its pocket, wire into its channel —
then press the lid down until both arms click over it. Nothing slides, and
nothing has to be threaded over a connector head. Push the two arms outward to
open it again.

Any number of positions, and any subset of them wired: unused positions are
filled with a solid rib so nothing can drift sideways into them.

## Print it

Ready-to-slice STLs are in [`generated/`](generated) — 2, 4, 6, 8 and 10-way,
plus a couple of partly-wired and square-head variants. Both parts are already
oriented and seated on Z=0, so slice them as they are.

- 0.4 mm nozzle, 0.2 mm layers, no supports.
- The clip's only overhangs are the two 0.5 mm ledges under the snap barbs.
  The lid has none at all.
- Leave the slicer's thin-wall handling on: the channel walls are 0.42 mm and the
  snap arm air gaps are 0.40 mm.

## Generate a different one

The generator is [`macros/DupontClipGen.FCMacro`](macros/DupontClipGen.FCMacro),
a FreeCAD macro. Symlink it into your FreeCAD macro directory and run it for a
dialog, or drive it headless:

```python
import DupontClipGen as g
g.generate({"n_positions": 6, "used": "1,3,5"})   # writes STLs to generated/
```

Everything is parametric — pitch, wire diameter, the measured head dimensions,
every clearance — and every derived dimension comes from a single `derived()`
function, so no two builders can disagree about the stack-up.

Filenames identify the configuration, so variants never overwrite each other:

```
DupontClip_6way_p1.3.5_2.54mm_2.5x2.2x14_Clip.stl
            |    |       |      |
            |    |       |      head w x h x length
            |    |       pitch
            |    which positions are wired ("all" when every one is)
            positions
```

A parameter that changes the geometry without appearing in the name adds a short
`cfg` tag, so two different solids can never share a filename.

## Verify it

```
FreeCADCmd check_dupont_clip.py
```

Runs 14 configurations and measures everything on the real solids rather than
trusting the parameters — booleans for interference and retention, bisection for
how far a jumper can actually move, `isInside` probes for the blanked positions,
and a face-normal scan for overhangs. Expect `FAILURES: 0`.

## Documentation

[`DESIGN.md`](DESIGN.md) has the as-built numbers, the clearance model, how each
jumper is retained in each direction, why the shape is what it is, and the open
threads. Worth reading before changing a dimension — particularly the note on why
the snap arms are on the clip and not the lid.

## Status

Verified in the model; **not yet test-printed.** The printer compensation knob
(`bore_comp`) is still uncalibrated at 0.0 — see the open threads in DESIGN.md.

`macros/WireGuideGen.FCMacro` is the earlier four-part generator this replaces.
It is kept because it still works and its defaults record measurements taken from
real parts.
