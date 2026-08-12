# -*- coding: utf-8 -*-
"""Headless verification harness for DupontClipGen.

Run it -- about a minute, no GUI, so it never trips the MCP GUI-dispatch
timeout:

    ~/projects/freecad/build/release/bin/FreeCADCmd check_dupont_clip.py 2>&1 \
        | tr '\r' '\n' | grep -v Processing | grep -E 'FAIL|WARN|params|URES'

Add a configuration by editing the `cases` list at the bottom.  Nothing here is
asserted from the parameters: every number is measured on the real solids --
booleans for interference and retention, bisection for how far a head or the lid
can actually move, isInside() probes for blanking, and a face-normal scan for
overhangs.
"""

import os
import sys
import math
import FreeCAD as App
import Part
from FreeCAD import Vector as V

HERE = os.path.dirname(os.path.realpath(__file__))
MACRO = os.path.join(HERE, "macros", "DupontClipGen.FCMacro")
if not os.path.exists(MACRO):            # before the macros moved into the repo
    MACRO = os.path.expanduser(
        "~/Library/Application Support/FreeCAD/Macro/DupontClipGen.FCMacro")

mod = type(sys)("dcg")
mod.__file__ = MACRO
exec(compile(open(MACRO).read(), MACRO, "exec"), mod.__dict__)

FAIL = []
WARN = []


def ok(cond, label, detail=""):
    tag = "PASS" if cond else "FAIL"
    if not cond:
        FAIL.append(label)
    print("  [%s] %-52s %s" % (tag, label, detail))


def warn(cond, label, detail=""):
    if not cond:
        WARN.append(label)
    print("  [%s] %-52s %s" % ("ok  " if cond else "WARN", label, detail))


def vol(sh):
    return 0.0 if sh is None else sh.Volume


def common_vol(a, b):
    try:
        return a.common(b).Volume
    except Exception as exc:                        # pragma: no cover
        return float("nan")


def compound(shapes):
    return Part.Compound(shapes)


def overhangs(shape, limit_deg=45.0, bed_z=None, sample=None):
    """Faces whose outward normal points downward by more than limit_deg.

    Orientation comes from probing isInside just off the face -- face.Orientation
    is not trustworthy after boolean work.  Planar faces are sampled at their
    centre of mass when that point actually lies on the face, otherwise at the
    middle of the parameter range, which is where the known false-positive mode
    on trimmed planar faces comes from.
    """
    out = []
    # the epsilon matters: a face at exactly the limit (every 45 deg relief in
    # this part) must not be flagged, or the scan reports its own convention
    cos_lim = math.cos(math.radians(limit_deg)) + 1e-6
    for i, f in enumerate(shape.Faces):
        pts = []
        com = f.CenterOfMass
        if f.isInside(com, 1e-6, True):
            u, v = f.Surface.parameter(com) if hasattr(f.Surface, "parameter") else (None, None)
            pts.append((com, u, v))
        if not pts:
            umin, umax, vmin, vmax = f.ParameterRange
            u, v = (umin + umax) / 2.0, (vmin + vmax) / 2.0
            pts.append((f.valueAt(u, v), u, v))
        p, u, v = pts[0]
        if u is None:
            umin, umax, vmin, vmax = f.ParameterRange
            u, v = (umin + umax) / 2.0, (vmin + vmax) / 2.0
        n = f.normalAt(u, v)
        n.normalize()
        if shape.isInside(p + n * 0.02, 1e-7, True):
            n = n * -1.0
        if bed_z is not None and abs(p.z - bed_z) < 1e-6 and n.z < 0:
            continue                                 # the bed face itself
        if n.z < -cos_lim:
            out.append((i, f.Area, p, n))
    return out


def run(params):
    P = dict(mod.DEFAULTS)
    P.update(params)
    n = int(P["n_positions"])
    used = mod.parse_used(P["used"], n)
    D = mod.derived(P)

    print("=" * 78)
    print("params: " + ", ".join("%s=%s" % kv for kv in sorted(params.items()))
          or "params: defaults")
    mod.report(P, D, used)

    clip = mod.build_clip(P, D, used)
    lid = mod.build_lid(P, D, used)
    heads = compound(mod.build_heads(P, D, used))
    wires = compound(mod.build_wires(P, D, used))
    pins = compound(mod.build_pins(P, D, used))
    asm = clip.fuse(lid)

    print("  --- solids ---")
    for name, sh in (("Clip", clip), ("Lid", lid)):
        bb = sh.BoundBox
        ok(len(sh.Solids) == 1 and sh.isValid(),
           "%s is 1 valid solid" % name,
           "vol %8.2f  %5.2f x %5.2f x %5.2f"
           % (sh.Volume, bb.XLength, bb.YLength, bb.ZLength))

    print("  --- assembly interference (nominal) ---")
    ok(common_vol(clip, lid) < 1e-6, "clip n lid == 0",
       "%.4f mm3" % common_vol(clip, lid))
    ok(common_vol(clip, heads) < 1e-6, "clip n heads == 0",
       "%.4f mm3" % common_vol(clip, heads))
    ok(common_vol(lid, heads) < 1e-6, "lid n heads == 0",
       "%.4f mm3" % common_vol(lid, heads))
    ok(common_vol(clip, wires) < 1e-6, "clip n wires == 0",
       "%.4f mm3" % common_vol(clip, wires))
    ok(common_vol(lid, wires) < 1e-6, "lid n wires == 0",
       "%.4f mm3" % common_vol(lid, wires))
    ok(common_vol(asm, pins) < 1e-6, "header pins reach the heads unobstructed",
       "%.4f mm3" % common_vol(asm, pins))

    print("  --- head retention (each direction must be blocked) ---")
    for label, d, target in (
            ("forward, out the front", V(0, -0.6, 0), asm),
            ("backward, into the guide", V(0, 0.6, 0), asm),
            ("upward, past the lid", V(0, 0, D["head_clr_z"] + 0.15), asm),
            ("sideways", V(0.6, 0, 0), asm)):
        moved = heads.copy()
        moved.translate(d)
        v = common_vol(moved, target)
        ok(v > 1e-3, "heads blocked %s" % label, "%.3f mm3 of interference" % v)

    print("  --- head float (how much it can actually move) ---")
    for label, axis, limit in (("along the run", V(0, 1, 0),
                                P["head_slack"] + 0.05),
                               ("vertically", V(0, 0, 1), D["head_clr_z"] + 0.05),
                               ("across the row", V(1, 0, 0), 2 * D["hx"] + 0.05)):
        lo, hi = 0.0, 2.0
        for _ in range(24):                          # bisect the free travel
            mid = (lo + hi) / 2.0
            m = heads.copy()
            m.translate(axis * mid)
            if common_vol(m, asm) > 1e-4:
                hi = mid
            else:
                lo = mid
        warn(lo <= limit, "head float %s" % label,
             "%.3f mm free (design allows %.3f)" % (lo, limit))

    print("  --- lid seat and snap ---")
    seat = D["ph"]
    lid_bottom = lid.BoundBox.ZMin
    ok(abs(lid_bottom - (seat - D["rib_d"])) < 1e-6,
       "lid ribs reach z=%.3f" % (seat - D["rib_d"]),
       "lid ZMin %.3f" % lid_bottom)
    clip_top_faces = [f for f in clip.Faces
                      if abs(f.BoundBox.ZMin - seat) < 1e-6
                      and abs(f.BoundBox.ZMax - seat) < 1e-6]
    seat_area = sum(f.Area for f in clip_top_faces)
    ok(seat_area > 5.0, "clip presents a lid seat at z=%.3f" % seat,
       "%.2f mm2 over %d faces" % (seat_area, len(clip_top_faces)))
    # the barb must overhang the lid, and the lid must be admitted by spreading
    # exactly snap_reach
    lifted = lid.copy()
    lifted.translate(V(0, 0, P["snap_clr"] + 0.2))
    ok(common_vol(clip, lifted) > 1e-3, "barbs catch the lid when it lifts",
       "%.3f mm3 at +%.2f" % (common_vol(clip, lifted), P["snap_clr"] + 0.2))
    ok(abs((D["lid_w"] / 2.0 - D["barb_tip"]) - P["snap_reach"]) < 1e-9,
       "barb overhangs the lid by snap_reach",
       "%.3f mm" % (D["lid_w"] / 2.0 - D["barb_tip"]))
    # the arm has to be free to bend: air gap all the way to the bed
    for sgn in (-1, 1):
        xm = sgn * (D["bw"] / 2.0 + P["arm_gap"] / 2.0)
        free = all(not clip.isInside(V(xm, y, z), 1e-7, True)
                   for y in (D["arm_y0"] + 0.5, (D["arm_y0"] + D["arm_y1"]) / 2.0,
                             D["arm_y1"] - 0.5)
                   for z in (-D["base_thk"] + 0.2, 0.5, D["ph"] - 0.2,
                             D["lid_top"]))
        ok(free, "arm gap is clear of the clip (x=%+.2f)" % xm,
           "%.2f mm" % P["arm_gap"])
    m = mod.arm_mechanics(P, D)
    warn(m["strain"] < 0.015, "snap arm root strain",
         "%.2f%% at %.2f mm spread, %.2f N" % (100 * m["strain"], m["spread"],
                                               m["force"]))

    print("  --- lid located along the wire run ---")
    # the stops can only stand on the side wall tops, so their engagement is
    # side_wall - slip minus the lid's corner radius; guard the whole chain
    ok(D["stop_overlap"] >= 0.4 - 1e-9, "lid stop engagement survives the "
       "corner radius", "%.3f mm straight overlap, r=%.2f"
       % (D["stop_overlap"], D["lid_r"]))
    for label, d in (("forward", V(0, -(D["g"] + 0.15), 0)),
                     ("backward", V(0, D["g"] + 0.15, 0))):
        m2 = lid.copy()
        m2.translate(d)
        v = common_vol(clip, m2)
        ok(v > 0.05, "lid stops block it sliding %s" % label, "%.3f mm3" % v)
    lo, hi = 0.0, 3.0
    for _ in range(24):
        mid = (lo + hi) / 2.0
        m2 = lid.copy()
        m2.translate(V(0, mid, 0))
        if common_vol(clip, m2) > 1e-4:
            hi = mid
        else:
            lo = mid
    warn(lo <= D["g"] + 0.02, "lid float along the run",
         "%.3f mm free (design allows %.3f)" % (lo, D["g"]))

    print("  --- lid descent path (only the barbs may be in the way) ---")
    clean = True
    for dz in (0.05, 0.2, 0.5, 1.0, 1.5, 2.0):
        m2 = lid.copy()
        m2.translate(V(0, 0, dz))
        c = clip.common(m2)
        if c.Volume < 1e-9:
            continue
        for sol in c.Solids:
            bb = sol.BoundBox
            inner = min(abs(bb.XMin), abs(bb.XMax))
            if inner < D["barb_tip"] - 1e-6:
                clean = False
                print("        dz=%.2f obstruction at x %.2f..%.2f z %.2f..%.2f"
                      % (dz, bb.XMin, bb.XMax, bb.ZMin, bb.ZMax))
    ok(clean, "nothing but the barbs obstructs the lid coming down",
       "checked 0.05..2.0 mm above the seat")

    print("  --- blanking ---")
    blanked = sorted(set(range(n)) - used)
    if not blanked:
        print("      (none)")
    for i in blanked:
        p = V(D["x_pos"][i], (D["y_fw"] + D["y_p1"]) / 2.0, D["ph"] / 2.0)
        ok(clip.isInside(p, 1e-7, True),
           "position %d is solid in the pocket" % (i + 1),
           "probe %s" % (p,))
        pg = V(D["x_pos"][i], D["y_p1"] + 1.0, D["z_cf"] + 0.3)
        ok(clip.isInside(pg, 1e-7, True),
           "position %d has no wire channel" % (i + 1), "")
        head = mod.build_heads(P, D, [i])[0]
        ok(common_vol(head, clip) > 1e-3,
           "position %d rejects a head" % (i + 1),
           "%.2f mm3 of interference" % common_vol(head, clip))
    if blanked:
        ok(mod.blank_residual(P, D) < P["head_w"], "blanking rib narrower than a head",
           "%.3f vs %.3f" % (mod.blank_residual(P, D), P["head_w"]))

    print("  --- printability (print pose, 45 deg limit) ---")
    # the clip's only allowed downward face is the barb's retaining ledge, at a
    # known height and no wider than snap_reach; the lid must have none at all
    ledge_z = D["barb_z0"] + D["base_thk"]
    ledge_a = P["snap_reach"] * D["arm_len"] + 1e-6
    for name, sh in (("Clip", clip), ("Lid", lid)):
        axis, angle = mod.PRINT_POSE[name]
        posed = mod.pose_for_print(sh, axis, angle)
        oh = overhangs(posed, 45.0, bed_z=0.0)
        for _, a, p, nv in sorted(oh, key=lambda t: -t[1]):
            print("        %6.2f mm2 at (%6.2f,%6.2f,%5.2f) n=(%.2f,%.2f,%.2f)"
                  % (a, p.x, p.y, p.z, nv.x, nv.y, nv.z))
        if name == "Lid":
            ok(not oh, "lid has no downward faces at all", "%d found" % len(oh))
        else:
            stray = [(a, p) for _, a, p, _ in oh
                     if abs(p.z - ledge_z) > 1e-6 or a > ledge_a]
            ok(not stray and len(oh) <= 2,
               "clip's only downward faces are the 2 barb ledges",
               "%d face(s), %.2f mm2 each at z=%.2f"
               % (len(oh), oh[0][1] if oh else 0.0, ledge_z))

    print("  --- thin walls ---")
    wall = (P["pitch"] - D["ch_w"]) / 2.0
    warn(wall >= 0.40, "channel wall", "%.3f mm" % wall)
    warn(D["rib_w"] >= 0.40, "lid rib width", "%.3f mm" % D["rib_w"])
    warn(P["arm_gap"] >= 0.40, "arm air gap", "%.3f mm" % P["arm_gap"])
    return clip, lid


def main():
    cases = [
        {},
        {"n_positions": 1},
        {"n_positions": 2},
        {"n_positions": 6, "used": "1,3,5"},
        {"n_positions": 10},
        {"n_positions": 15, "used": "1-13"},
        {"n_positions": 4, "bore_comp": 0.1},
        {"n_positions": 8, "head_w": 2.54, "head_h": 2.54, "wire_dia": 1.4,
         "guide_len": 20.0},
        {"n_positions": 6, "used": "2-5"},          # both end positions blanked
        {"n_positions": 6, "used": "1"},            # one head in a six-wide row
        {"n_positions": 4, "head_len": 8.0, "guide_len": 6.0},  # shortest arm
        {"n_positions": 3, "pitch": 2.0, "wire_dia": 1.2, "head_w": 1.9,
         "head_h": 1.9, "head_len": 10.0},          # 2.0 mm pitch parts
        {"n_positions": 4, "lid_corner_r": 3.0},    # radius clamp must bite
        {"n_positions": 4, "side_wall": 0.9, "snap_reach": 0.8,
         "head_gap": 0.25},                         # thin walls, deep snap
    ]
    for c in cases:
        run(c)
    print("=" * 78)
    print("FAILURES: %d  %s" % (len(FAIL), FAIL))
    print("WARNINGS: %d  %s" % (len(WARN), WARN))


main()
