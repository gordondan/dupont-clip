# Dupont clip — as-built

A two-part printed clip that holds a row of Dupont jumpers together at 2.54 mm
pitch so they plug and unplug as one block, with the wires combed out the back.

Built by `macros/DupontClipGen.FCMacro`. It replaces the four-part
Guide / Lid / SimpleCollar / HoodedCollar set in `macros/WireGuideGen.FCMacro`,
which is left in place and untouched.

| File | What |
|---|---|
| `macros/DupontClipGen.FCMacro` | the generator, with the reasoning in its comments. Symlinked into FreeCAD's macro directory, so FreeCAD runs this file and git tracks it |
| `check_dupont_clip.py` | headless verification; run it after any change |
| `export_dupont_clip.py` | rebuilds the two `.FCStd` files and the whole STL set, then checks every mesh it wrote |
| `DupontClip.FCStd` | Clip + Lid, print-posed, both seated on Z=0 |
| `DupontClipAssembly.FCStd` | same parts assembled, plus head / wire / pin mocks |
| `generated/*.stl` | ready to slice. Written by `generate()` itself, binary, named by `slug()` |

## Naming

`slug()` names the document, the `.FCStd` and the STLs from one place, the way
`derived()` owns the dimensional chain. It records the four things that identify
a connector — positions, which of them are wired, pitch, head shape — because the
earlier `%dway` form recorded only the count, so a partly-wired 6-way silently
overwrote a fully-wired one:

```
DupontClip_6way_p1.3.5_2.54mm_2.5x2.2x14_Clip.stl
```

`used` is canonicalised from the parsed set, so `all`, `1-4` and `4,3,2,1` at
n=4 all produce one name rather than three. Any geometry parameter *not* in the
slug — `bore_comp`, `guide_len`, `snap_reach`, `wire_dia` — folds into a short
`cfgXXXX` tag that appears only when it is off-default, so two different solids
can never share a filename while ordinary names stay readable.

## The two parts

**Clip** — one solid. Front to back: a **front lip**, the **head pocket**, the
**wire channels**; along the sides, two **snap arms** and four **lid stops**.

**Lid** — a flat plate with one **rib** per used channel. No rails, no barbs,
no flexures.

## Assembly

Drop each jumper in from above — head into its pocket, wire into its channel —
then press the lid straight down until both arms click over it. Nothing slides
along anything; nothing is threaded over a head. To open it, push the two arms
outward and the lid lifts.

## How each jumper is held

| Direction | What stops it |
|---|---|
| out the front | the front lip. A head would have to rise 0.60 to clear it, and the lid only lets it rise 0.25. |
| into the back | the guide section's front face — the channel is 1.70 wide where the head is 2.50. This is also the strain relief: pulling the wire loads the head against solid plastic. |
| up | the lid, seated 0.15 over the heads. |
| sideways | the pocket walls, 0.15 a side; on a blanked position, a 2.28 mm rib. |

Measured free float at the defaults: 0.30 along the run, 0.15 up, 0.15 across.

## Driving numbers (4-way, defaults)

Everything below is derived in `derived()`; no builder recomputes the stack-up.

```
head (measured)      2.50 w x 2.20 h x 14.00 long      pitch 2.54, wire 1.60
head row             (n-1)*2.54 + 2.50 = 10.12         <- not n*pitch
pocket               10.42 wide x 2.35 deep            head + head_gap 0.15
clip                 12.82 wide, base 1.00 under the pocket floor
head slot            2.80 each; slots OVERLAP, so a full row is one trough
blanking rib         2*pitch - slot = 2.28  (blocks a 2.50 head)
channel              1.70 wide x 2.05 deep, floor z = 0.30
      floor 0.30  =  head_h/2 - wire_dia/2, which puts the channel axis on the
                     HEAD axis so the wire leaves the head straight
channel wall         (pitch - channel)/2 = 0.42        <- the binding constraint
lid                  12.52 x 26.30 x 1.40, seats on the clip top at z = 2.35
lid rib              0.30 deep, leaves 0.15 over the wire
lid corner r         0.40, clamped so the lid stops keep >= 0.40 of straight
                     overlap -- a stop can only stand on a side wall top, so
                     it engages side_wall - slip, and the radius comes off that
snap arm             26.3 long x 1.20 thick x 5.90 tall, spreads 0.50
                     0.18 N per arm, root strain 0.13%
overall              16.02 wide x 29.50 long x 5.90 tall
```

`front_wall` (1.20) is also how far the heads sit proud of whatever the clip's
front face lands on — a header's plastic base, usually. On a 6 mm header pin
that still leaves ~4.8 mm of engagement. Reduce it to seat the heads deeper.

## Why this shape and not the old one

**The old lid could not be assembled, and no dimension would have fixed it.**
Its snap rails were 1.5 mm thick and about 4 mm tall, and making them spread
1 mm meant straining them near 7 %. Printed PLA yields around 2 %. The joint
was geometrically correct and mechanically impossible.

A snap arm has to be **long** to survive being spread. On the lid, a long arm
can only run along the wire run, and freeing it means cutting it away from the
lid's own plate — which leaves it dangling in mid air once the lid is flipped
onto its plate for printing. Put the same arm on the clip and it stands up off
the build plate along its whole length: supported while printing, free to bend
once printed, joined to the clip only at its root at the rear. That single
change is what moves the strain from 7 % to 0.13 %.

**Retention does not come from arm stiffness.** The barb's retaining face is
horizontal, so pulling the lid loads the arm axially and it cannot cam its way
out. The joint releases only by pushing both arms outward. Very compliant arms
are therefore fine, and are what make the lid easy to press on.

**The collars are gone.** Their job — stopping the heads swinging sideways —
is now done by the pocket walls, so nothing has to be threaded over a head.

**Nothing needs an overhanging feature to hold the heads in.** The front lip
retains them because the lid caps their vertical play; a lip only has to be
taller than that play. So the whole clip prints in one orientation with the
pocket opening upward, and its only downward-facing faces are the two 0.50 mm
barb ledges.

## Clearances — five names, five jobs, no aliases

| name | default | what it controls |
|---|---|---|
| `head_gap` | 0.15 | per side, around the head row (X) and above it (Z) |
| `wire_gap` | 0.05 | per side, around the wire in its channel |
| `rib_clr` | 0.15 | gap the lid rib leaves over the wire |
| `slip` | 0.15 | per side, clip to lid |
| `snap_clr` | 0.10 | lid lift before the barbs catch |
| `bore_comp` | 0.00 | printer compensation, per side, internal openings only |

`bore_comp` is the only one that is a property of the machine rather than the
design. It is still **uncalibrated** — see Open threads.

`wire_gap` is small on purpose: the channel wall is only `(pitch - wire_dia)/2`
to begin with, so every 0.05 of wire clearance costs 0.05 of wall. At the
defaults the wall lands at 0.42, just over one 0.40 nozzle. The report flags it
when a parameter change pushes any thin feature under that.

## Printing

Both parts are posed and seated on Z=0 by the generator, so slice them as
exported and every part starts on layer 1.

- **Clip** — as exported, pocket up. No supports. The only overhangs are the
  two barb ledges, 0.50 mm wide.
- **Lid** — as exported, plate down, ribs up. No overhangs at all.
- 0.4 mm nozzle, 0.2 mm layers. The 0.42 mm channel walls and the 0.40 mm arm
  gaps both want the slicer's thin-wall handling left on.

## Verification

`check_dupont_clip.py` runs 14 configurations — 1 to 15 positions, blanked
patterns including both end positions, a 2.0 mm pitch part, a 2.54 square head,
`bore_comp = 0.1`, the shortest arm the geometry allows, an absurd corner radius
to prove the clamp bites, and thin walls with a deep snap. Every one passes:

- Clip and Lid are each 1 valid solid.
- `clip ∩ lid`, `∩ heads`, `∩ wires` all exactly 0; header pins reach the heads
  unobstructed.
- Each head is measurably blocked in all four escape directions, and its free
  float is measured by bisection rather than assumed.
- The lid is blocked fore and aft by the lid stops, and **nothing but the barbs**
  obstructs it coming down (checked 0.05–2.0 mm above the seat).
- The barbs catch the lid the moment it lifts past `snap_clr`.
- Blanked positions are solid, have no channel, and physically reject a head.
- The clip's only downward faces are the two barb ledges; the lid has none.

The one standing warning is the channel wall dropping under 0.40 when
`bore_comp = 0.1` or the pitch is 2.0 — inherent to those choices, and reported.

## Open threads

1. **`bore_comp` is still uncalibrated.** Print the 4-way, caliper the head
   pocket against the 2.80 the macro reports, and set
   `bore_comp += (model - printed)/2`. Everything internal follows; nothing
   external moves.
2. **`head_len` 14.00 is inherited, not measured** on the jumpers now in use.
   It only sets pocket length, so an error costs end float, not fit.
3. **Head bunching at large `n`.** Heads are 2.50 on a 2.54 pitch, so they
   locate against each other, not against dividers — there is no room for a
   divider. Total slack is `2 * head_gap` across the whole row (0.30), so no
   head is more than 0.15 off nominal. Fine to 15 positions; if a wide row ever
   fights a header, reduce `head_gap` before anything else.
4. **The rear 2 mm of the channels is open to the sky** (the lid stops back
   there, so the wires can be laid in from above). Deliberate: a closed exit
   slot cannot be threaded, because the far end of a jumper is another head.
