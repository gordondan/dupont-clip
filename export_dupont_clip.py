# -*- coding: utf-8 -*-
"""Build the Dupont clip documents and STLs, headless.

    ~/projects/freecad/build/release/bin/FreeCADCmd export_dupont_clip.py

STLs land in `generated/` and are named by DupontClipGen's slug(), so a
configuration's identity -- which positions are wired, and the head shape -- is
in the filename.  generate() writes them itself; this script exists to build the
set of configurations worth keeping around, plus the two reference documents.

CONFIGS is a list of parameter dicts, not a list of sizes: `used` and the head
dimensions have to be able to vary, or the naming has nothing to distinguish.
"""

import os
import sys
import FreeCAD as App
import Mesh

HERE = os.path.dirname(os.path.realpath(__file__))
MACRO = os.path.join(HERE, "macros", "DupontClipGen.FCMacro")
if not os.path.exists(MACRO):            # before the macros moved into the repo
    MACRO = os.path.expanduser(
        "~/Library/Application Support/FreeCAD/Macro/DupontClipGen.FCMacro")
OUT = os.path.join(HERE, "generated")

mod = type(sys)("dcg")
mod.__file__ = MACRO
exec(compile(open(MACRO).read(), MACRO, "exec"), mod.__dict__)

# what to leave in generated/ ready to slice
CONFIGS = [
    {"n_positions": 2},
    {"n_positions": 4},
    {"n_positions": 6},
    {"n_positions": 8},
    {"n_positions": 10},
    # partly wired rows: same n as above, and they must NOT collide with them
    {"n_positions": 6, "used": "1,3,5"},
    {"n_positions": 8, "used": "1-4"},
    # square-head jumpers: same n as above, must not collide either
    {"n_positions": 4, "head_w": 2.54, "head_h": 2.54},
]

# the two reference documents, kept in the repo root
REFERENCE = [("DupontClip", dict(n_positions=4), False, True),
             ("DupontClipAssembly", dict(n_positions=4), True, False)]


def main():
    # The STLs are reproducible -- a fresh clone regenerates them byte for byte.
    # The .FCStd files are NOT: FreeCAD stamps every save, so rewriting them
    # dirties two binary files in git on every export with no real change.  So
    # only rebuild them when asked, or when they are missing.
    for name, params, mocks, posed in REFERENCE:
        path = os.path.join(HERE, name + ".FCStd")
        if os.path.exists(path) and not os.environ.get("REBUILD_DOCS"):
            print("kept   %s  (REBUILD_DOCS=1 to rebuild)" % path)
            continue
        doc = App.newDocument(name)
        p = dict(params)
        p["export"] = False                      # the loop below owns generated/
        mod.generate(p, doc=doc, mocks=mocks, posed=posed)
        doc.saveAs(path)
        print("saved %s" % doc.FileName)

    written, bad = [], []
    for params in CONFIGS:
        p = dict(params)
        p["out_dir"] = OUT
        doc = App.newDocument("build_%d" % len(written))
        mod.generate(p, doc=doc)                 # generate() does the exporting
        used = mod.parse_used(p.get("used", mod.DEFAULTS["used"]),
                              int(p["n_positions"]))
        for part in ("Clip", "Lid"):
            name = mod.slug(dict(mod.DEFAULTS, **p), used, part) + ".stl"
            written.append(name)
            # check the FILE, not the solid it came from: a mesh can be
            # unprintable -- open, non-manifold, self-intersecting -- while the
            # solid behind it was perfectly valid
            m = Mesh.Mesh(os.path.join(OUT, name))
            solid_vol = doc.getObject(part).Shape.Volume
            # RELATIVE tolerance.  An absolute one has no meaning here: the
            # tessellation is exact on planar faces but still accumulates
            # floating-point noise across a few hundred facets.
            vol_err = abs(m.Volume - solid_vol) / solid_vol
            if not (m.isSolid() and not m.hasNonManifolds()
                    and not m.hasSelfIntersections() and vol_err < 1e-3):
                bad.append("%s (solid=%s manifold=%s clean=%s vol %+.4f%%)"
                           % (name, m.isSolid(), not m.hasNonManifolds(),
                              not m.hasSelfIntersections(), 100 * vol_err))

    # flush explicitly: FreeCADCmd does not flush Python's stdout if the script
    # leaves via SystemExit, so an unflushed failure message vanishes entirely
    # and all you get is exit code 1
    def say(s):
        sys.stdout.write(s + "\n")
        sys.stdout.flush()

    say("\n%d STLs in %s" % (len(written), OUT))
    dupes = sorted(set(n for n in written if written.count(n) > 1))
    say("colliding filenames: %s" % (dupes or "none"))
    say("unprintable meshes:  %s" % (bad or "none"))
    for n in sorted(set(written)):
        say("  %-58s %7d bytes" % (n, os.path.getsize(os.path.join(OUT, n))))
    if dupes or bad:
        raise SystemExit("export failed: collisions %s, bad meshes %s"
                         % (dupes, bad))


main()
