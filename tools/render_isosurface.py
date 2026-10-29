#!/usr/bin/env python3
"""Render flow-field iso-surface PNGs from a run's SAMRAI viz database, headless.

VisIt's own bundled libs are missing libpcre2-16.so.0, and no module on this
cluster provides it either -- it happens to exist inside the anaconda3/2025.06
install tree, so point LD_LIBRARY_PATH at it (no `module load` needed):

    export LD_LIBRARY_PATH=/share/apps/anaconda3/2025.06/lib:$LD_LIBRARY_PATH

Then run with VisIt's own Python interpreter via its -cli driver (not plain python3):

    visit -cli -nowin -s tools/render_isosurface.py -- <run_dir> [options]

Example, from this project's root, for case faster_nofin_full_span_2026-08-03_16-47-23:

    export LD_LIBRARY_PATH=/share/apps/anaconda3/2025.06/lib:$LD_LIBRARY_PATH
    VISIT=/scratch/sc7825/software/visit/bin/visit
    RUN=/scratch/sc7825/3dRotatingCylinder/runs/faster_nofin_full_span_2026-08-03_16-47-23
    $VISIT -cli -nowin -s tools/render_isosurface.py -- "$RUN" --out "$RUN/frames"

Everything after a literal "--" is this script's own argv (VisIt eats anything
before it). Submit this as a quick sbatch/srun job (with the export above in
the job script) rather than an OOD desktop session -- it never opens a
display, so it only needs CPU + RAM, not a GUI.

You'll see one harmless warning on startup:
`Error opening plugin file: .../libMGDALDatabase.so (libpcre.so.1: ...)` --
that's VisIt's GDAL raster-database plugin (unrelated pcre v1, not v2),
irrelevant to SAMRAI/IB data; it fails to load and VisIt moves on.

The database exposes (confirmed via the SAMRAI summary.samrai HDF5 headers):
    U       vector, 3 components  -- velocity
    P       scalar                -- pressure
    Omega   vector, 3 components  -- vorticity
    Div U   scalar                -- velocity divergence (~0, diagnostic only)

Default iso-surface variable is vorticity magnitude (the usual choice for
picking out flow structures); switch with --variable.

Camera frames are named presets in CAMERAS below -- edit the dict to add your
own, then rerun; each preset is rendered to its own PNG so you can compare
several candidate views from one job and just look at the PNGs via OOD's
file browser. Every preset except gui_match auto-centers on the body: it
queries viz_cylinder3d/lag_data.visit for the body mesh's actual current
position/size (it moves -- e.g. in one case here, x in [-3,3] at t=0 vs
x in [109,116] at t=60) and frames around that, so the same presets work
unmodified for a different timestep, run, or body shape, instead of needing
re-tuned focus/parallelScale numbers hand-picked per case.

--session lets you skip all of the above and just replay a GUI-recorded
session file (Controls -> Command -> or File -> Save Session from VisIt's
interactive GUI, e.g. launched via `visit-gl` on an OOD desktop with working
GLX). It calls RestoreSession() to recreate exactly the plots/operators/
colors you built by hand, then only changes the time state and camera
before saving PNGs -- it does not touch variable/contour/resample/lag-point
options above, all of which are ignored in this mode. Use --cameras keep
(the default when --session is given) to render from whatever view the
session itself had, instead of one of the named CAMERAS presets.

All built-in annotations are stripped (no "user: ..."/timestamp, no
"DB: ..." / "Cycle: ... Time: ..." line, no contour legend). The only thing
drawn is a small X/Y/Z orientation triad, anchored to the right side of the
frame (TRIAD_ANCHOR/TRIAD_LENGTH below) -- VisIt's own native triad has no
position attribute (it's hardcoded bottom-left), so this is a custom
Line2D/Text2D triad recomputed from the camera's basis each render instead.
--format lets you save vector output (eps, or pdf via ps2pdf) instead of a
PNG raster; note a complex iso-surface has a lot of polygons, so vector
files can be large and slow to open.
"""

import argparse
import os
import subprocess
import sys

# VisIt's CLI prepends its own args; the user's args come after a literal "--".
if "--" in sys.argv:
    argv = sys.argv[sys.argv.index("--") + 1:]
else:
    argv = []

# Full-saturation colors matching VisIt's own default discrete color table
# (what a plain GUI contour plot uses) -- the muted tones tried earlier looked
# visibly darker/duller than that, which read as "wrong lighting" even though
# the actual light/shading setup was identical (VisIt's default single
# headlight, no specular). Bright, fully-saturated base colors catch more of
# that headlight's reflection, which is what made the session's render look
# better-lit.
COLOR_PRESETS = {
    "red": (255, 0, 0, 255),
    "blue": (0, 0, 255, 255),
    "green": (0, 255, 0, 255),
    "yellow": (255, 255, 0, 255),
    "orange": (255, 135, 0, 255),
    "purple": (255, 0, 135, 255),
    "black": (20, 20, 20, 255),
}

# Every camera gets a generous nearPlane/farPlane by default (see
# DEFAULT_NEAR_FAR below) -- this was the actual cause of renders looking
# "fragmented"/cropped no matter how wide parallelScale was set: VisIt's
# auto-computed near/far clipping planes were slicing through the coiled
# wake in DEPTH (along the camera's view direction), not cropping it in the
# screen plane, so neither a wider parallelScale nor a full-content bounding
# box fixed it -- only explicit near/far planes covering the whole domain did
# (confirmed empirically: identical parallelScale/focus, only difference
# being explicit nearPlane=-215/farPlane=215, took a render from a handful of
# fragments to the full tube).
#
# Cameras otherwise define ORIENTATION only (viewNormal/viewUp/imageZoom)
# plus a "scale" factor. focus and parallelScale are computed at render time
# from the body's actual current position/size (queried from
# viz_cylinder3d/lag_data.visit -- see open_body_mesh() below), not
# hardcoded -- so these work unchanged for a body that has moved since the
# run started, or for a different run/body entirely, instead of needing
# hand-tuned numbers re-picked per case. "scale" is how many body
# half-widths of margin to frame around it: a small number (near_body/front)
# crops tight on the body + immediate wake; a large number (default/side/
# top) pulls back for a wide establishing view.
CAMERAS = {
    "default": dict(viewNormal=(-0.5, -0.3, 0.8), viewUp=(0.3, 0.9, 0.2),
                     imageZoom=1.0, scale=15),
    "side": dict(viewNormal=(0, 0, 1), viewUp=(0, 1, 0), imageZoom=1.0, scale=15),
    "top": dict(viewNormal=(0, -1, 0), viewUp=(0, 0, 1), imageZoom=1.0, scale=15),
    "near_body": dict(viewNormal=(-0.5, -0.3, 0.8), viewUp=(0.3, 0.9, 0.2),
                       imageZoom=1.0, scale=20),
    # Straight down the X (streamwise/flow) direction -- looking at the body
    # head-on, perpendicular to X, into the Y-Z plane (cross-flow x spanwise).
    # Not to be confused with 'side', which looks down Z instead. Framed off
    # the body's Y/Z extent (extent_axes), not the default X/Y: every body
    # here is full-span in Z (~35 units, constant across fin/no-fin cases),
    # which dwarfs its X/Y cross-section (6-13 units depending on fins) --
    # framing off X/Y zoomed in by up to 2x too much for the thinner no-fin
    # body specifically. Z being the same for every case also means this one
    # scale value frames consistently across cases instead of swinging with
    # fin size.
    "front": dict(viewNormal=(1, 0, 0), viewUp=(0, 1, 0), imageZoom=1.0, scale=1.15,
                   extent_axes=(1, 2)),
    # Same orientation as gui_match (below) -- this specific diagonal, not
    # pure-Z like 'front' and not near_body's angle, is what "unwinds" a
    # spanwise-coiled wake into a readable tube instead of collapsing it
    # edge-on (front) or cutting across it (near_body); found by comparing
    # against the gui_match reference render on this case. Framed by the
    # same body-proportional "scale" as the others now that near/far planes
    # are fixed (a full-content bounding-box fit was tried instead, but a
    # single far-flung debris fragment can dominate it and zoom out far more
    # than useful -- body-proportional framing is more predictable).
    "tube": dict(viewNormal=(0.354832220408498, 0.364890237525538, 0.860784066952062),
                  viewUp=(0.0171955769903626, 0.917990778094482, -0.396228776675113),
                  imageZoom=1.0, scale=8),
    # The one exception: exact numbers copied from runs/visit0000.session's
    # View3DAttributes, so manual-flag renders can reproduce that one
    # GUI-recorded view without --session. This is intentionally NOT
    # auto-centered -- it exists to pin one specific recorded camera, not to
    # generalize across bodies/cases; has its own focus/parallelScale instead
    # of "scale", so the loop below leaves it untouched.
    "gui_match": dict(viewNormal=(0.354832220408498, 0.364890237525538, 0.860784066952062),
                       focus=(45, -45, 0),
                       viewUp=(0.0171955769903626, 0.917990778094482, -0.396228776675113),
                       parallelScale=107.5, imageZoom=6.72749994932562,
                       viewAngle=30, nearPlane=-215, farPlane=215,
                       imagePan=(0.0245725505680152, -0.024160445798989),
                       perspective=1),
}

# Fallback half-extent (world units) for the "scale" cameras above, only used
# if no viz_cylinder3d/lag_data.visit body mesh can be found at all (so there
# is nothing to measure) -- an arbitrary wide-ish guess, not a real default.
FALLBACK_HALF_EXTENT = 50.0

# Applied as nearPlane=-DEFAULT_NEAR_FAR/farPlane=+DEFAULT_NEAR_FAR on every
# camera unless a preset overrides it -- this project's domain diagonal
# (x in [-30,120], y in [-120,30], z in [-17.5,17.5]), generous enough to
# never depth-clip real geometry regardless of focus/zoom. See the CAMERAS
# comment above for why this matters.
DEFAULT_NEAR_FAR = 215.0


def parse_args():
    p = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("run_dir", help="run folder containing viz_cylinder3d/dumps.visit")
    p.add_argument("--session", default=None,
                   help="path to a VisIt-GUI-recorded .session file; if given, "
                        "RestoreSession() replays it verbatim (plots, operators, "
                        "colors, databases) and every --variable/--contour-*/"
                        "--values/--colors/--resample-*/--lag-point-* option below "
                        "is ignored. --cameras defaults to 'keep' in this mode.")
    p.add_argument("--label", default=None,
                   help="output filename prefix (default: --variable, or the "
                        "session file's basename when --session is given)")
    p.add_argument("--variable", default="vort_mag",
                   help="vort_mag (default, =magnitude(Omega)), vel_mag (=magnitude(U)), "
                        "omega_z (=Omega[2], signed spanwise vorticity), "
                        "or any raw scalar: P, 'Div U'")
    p.add_argument("--contour-value", type=float, default=None,
                   help="iso-surface value; if omitted, uses --contour-percent instead")
    p.add_argument("--contour-percent", type=float, default=15.0,
                   help="iso-surface value as %% of the field's min-max RANGE, not a "
                        "statistical percentile (default 15 -- for a peaked field like "
                        "vorticity magnitude, 50%% of the range is close to the extreme "
                        "max and only catches tiny isolated cores; lower values enclose "
                        "more of the structure)")
    p.add_argument("--values", nargs="+", type=float, default=None,
                   help="one or more explicit iso-surface values, each its own Contour "
                        "plot colored per --colors (e.g. --values -2 2 --colors blue red "
                        "for signed vorticity). Overrides --contour-value/--contour-percent.")
    p.add_argument("--colors", nargs="+", default=None,
                   help="color name per --values entry: " + ", ".join(COLOR_PRESETS))
    p.add_argument("--cameras", nargs="+", default=None,
                   help="which named presets from CAMERAS to render, or 'keep' to "
                        "leave the current/restored view untouched (default: all "
                        "CAMERAS presets normally, or just 'keep' when --session "
                        "is given)")
    p.add_argument("--cycle", type=int, default=None,
                   help="timestep index to render. Default: last available, or "
                        "-- when --session is given -- whatever state the session "
                        "was saved at (its camera was tuned for that state's body "
                        "position, so jumping elsewhere may frame empty space). "
                        "Pass -1 explicitly for 'last' even with --session.")
    p.add_argument("--out", default=None,
                   help="output directory for PNGs (default: <run_dir>/frames)")
    p.add_argument("--width", type=int, default=1280)
    p.add_argument("--height", type=int, default=960)
    p.add_argument("--format", choices=["png", "eps", "pdf"], default="png",
                   help="png (default, raster) or eps/pdf (vector, via VisIt's "
                        "POSTSCRIPT writer; pdf additionally runs ps2pdf on the "
                        "saved .eps). Vector files can be large/slow for a dense "
                        "iso-surface mesh.")
    p.add_argument("--no-resample", dest="resample", action="store_false",
                   help="skip the Resample operator entirely and contour the raw "
                        "native AMR mesh (what a plain GUI session without a "
                        "Resample operator does -- full native resolution, but "
                        "can show jagged lines at patch-refinement boundaries)")
    p.add_argument("--resample-samples", type=int, default=200,
                   help="samples per axis for the Resample operator (default 200). "
                        "AMRStitchCell doesn't work with this SAMRAI reader plugin "
                        "(errors: 'Database plugin did not properly set level cell "
                        "sizes'), so contouring the raw multiresolution hierarchy "
                        "shows jagged lines at patch-refinement boundaries. "
                        "Resampling onto one uniform grid first avoids that; higher "
                        "values trade more memory/time for finer detail.")
    p.add_argument("--resample-bounds", type=float, nargs=6, default=None,
                   metavar=("XMIN", "XMAX", "YMIN", "YMAX", "ZMIN", "ZMAX"),
                   help="restrict the Resample grid to this box instead of the full "
                        "domain (x in [-30,120], y in [-120,30], z in [-17.5,17.5] for "
                        "this project's cases) -- same --resample-samples spread over "
                        "a smaller box gives much finer effective resolution where you "
                        "actually need it (e.g. around the body), instead of wasting "
                        "samples resolving empty far-field domain.")
    p.add_argument("--wall-margin", type=float, default=3.0,
                   help="clip this many world units off every side of the domain "
                        "before contouring (default 10), to drop contour fragments "
                        "coincident with a domain wall (an apparent BC artifact on "
                        "some cases, not real flow structure) -- see DOMAIN_BOUNDS. "
                        "Set to 0 to disable.")
    p.add_argument("--no-lag-points", dest="lag_points", action="store_false",
                   help="don't overlay the cylinder's Lagrangian (IB) points from "
                        "viz_cylinder3d/lag_data.visit -- on by default")
    p.add_argument("--lag-point-size", type=float, default=2.0,
                   help="point size for the Lagrangian point overlay (default 2.0)")
    p.add_argument("--lag-point-color", default="black",
                   help="color for the Lagrangian point overlay: " + ", ".join(COLOR_PRESETS) +
                        ", or black (default black)")
    args = p.parse_args(argv)
    if args.cameras is None:
        args.cameras = ["keep"] if args.session else list(CAMERAS.keys())
    return args


def open_body_mesh(run_dir):
    """Open the Lagrangian/IB body-point database, used both to overlay the
    body and to auto-center the camera on it. Returns (db_path, mesh_name),
    or (None, None) if run_dir has no viz_cylinder3d/lag_data.visit -- the
    mesh name itself is read from its metadata rather than hardcoded, so a
    future case with a differently-named body mesh still works."""
    lag_db = os.path.join(run_dir, "viz_cylinder3d", "lag_data.visit")
    if not os.path.exists(lag_db) or not OpenDatabase(lag_db):
        return None, None
    md = GetMetaData(lag_db)
    if md.GetNumMeshes() == 0:
        CloseDatabase(lag_db)
        return None, None
    return lag_db, md.GetMeshes(0).name


# This project's domain (from input3d for the faster_* cases: Nx=150,
# Ny=150, Nz=35, Lx=Ly=150, Lz=35, x_lo=-2*Lx/10, y_lo=-12*Ly/15, z_lo=-Lz/2).
DOMAIN_BOUNDS = (-30.0, 120.0, -120.0, 30.0, -17.5, 17.5)


def add_wall_clip_operator(margin):
    """Clip the contour to DOMAIN_BOUNDS shrunk by `margin` on every side.
    Some cases' vorticity field hits the contour threshold exactly at a
    domain wall (seemingly a boundary-condition artifact, not real flow
    structure) producing a big flat sheet coincident with that wall -- it
    doesn't shrink away by zooming in since it's not a stray distant blob,
    it's the wall itself. Clipping it out directly is more robust than
    trying to frame around it."""
    AddOperator("Box")
    b = BoxAttributes()
    b.amount = b.Some
    xmin, xmax, ymin, ymax, zmin, zmax = DOMAIN_BOUNDS
    b.minx, b.maxx = xmin + margin, xmax - margin
    b.miny, b.maxy = ymin + margin, ymax - margin
    b.minz, b.maxz = zmin + margin, zmax - margin
    SetOperatorOptions(b)


def add_resample_operator(args):
    AddOperator("Resample")
    ra = ResampleAttributes()
    ra.is3D = 1
    ra.samplesX = ra.samplesY = ra.samplesZ = args.resample_samples
    if args.resample_bounds:
        xmin, xmax, ymin, ymax, zmin, zmax = args.resample_bounds
        ra.useExtents = 0
        ra.startX, ra.endX = xmin, xmax
        ra.startY, ra.endY = ymin, ymax
        ra.startZ, ra.endZ = zmin, zmax
    else:
        ra.useExtents = 1
    SetOperatorOptions(ra)


# VisIt's native 3D orientation triad (axes3D) has no position attribute --
# it's a fixed bottom-left screen overlay with no way to move it to another
# corner via AnnotationAttributes (checked: axes3D exposes triadColor/Font/
# Bold/Italic/SetManually but no x/y). So instead we disable it entirely and
# draw our own triad from plain Line2D/Text2D annotation objects, which DO
# take normalized (0-1) screen positions -- recomputed from the camera's own
# basis each render so it still points the right way for whatever view is
# active.
TRIAD_ANCHOR = (0.90, 0.14)
TRIAD_LENGTH = 0.07


def _normalize(v):
    n = sum(c * c for c in v) ** 0.5
    return tuple(c / n for c in v) if n else v


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def _dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def make_triad():
    lines, labels = {}, {}
    for axis in "XYZ":
        line = CreateAnnotationObject("Line2D")
        line.color = (0, 0, 0, 255)
        line.width = 2
        line.endArrow = line.Solid
        lines[axis] = line
        label = CreateAnnotationObject("Text2D")
        label.textColor = (0, 0, 0, 255)
        label.fontBold = 1
        label.fontItalic = 1
        label.height = 0.025
        label.text = axis
        labels[axis] = label
    return lines, labels


#  Axis pointing (near) straight into/out of the screen (e.g. X in the
# 'front' camera, which looks down the X axis) projects to a near-zero-
# length line -- normalizing it to a direction would be meaningless, and
# leaving it zero-length makes that axis invisible with its label sitting
# on top of whichever other arrow happens to share the anchor point. Below
# this projected length, treat it as degenerate and instead point it away
# from the other two (still-visible) arrows, shortened, so every axis
# always gets its own clearly separated, visible label.
TRIAD_MIN_PROJECTION = 0.2


def axis_half_extent(bbox, axes=(0, 1)):
    """Half-extent of `bbox` (xmin,xmax,ymin,ymax,zmin,zmax) along whichever
    pair of world axes a camera preset names via extent_axes (0=x,1=y,2=z;
    defaults to x,y). Lets a preset like 'front' -- which looks down X, so
    its screen plane is Y-Z rather than the usual X-Y -- frame off the axes
    it actually shows, instead of a body dimension (here, X/Y cross-section)
    that isn't even in view for that camera."""
    spans = [bbox[2 * a + 1] - bbox[2 * a] for a in axes]
    return (max(spans) / 2) or FALLBACK_HALF_EXTENT


def update_triad(lines, labels, view_normal, view_up):
    n = _normalize(view_normal)
    right = _normalize(_cross(view_up, n))
    up = _cross(n, right)
    ax, ay = TRIAD_ANCHOR

    raw = {axis: (_dot(world_vec, right), _dot(world_vec, up))
           for axis, world_vec in zip("XYZ", ((1, 0, 0), (0, 1, 0), (0, 0, 1)))}

    directions, degenerate = {}, []
    for axis, (dx, dy) in raw.items():
        d = (dx * dx + dy * dy) ** 0.5
        if d >= TRIAD_MIN_PROJECTION:
            directions[axis] = (dx / d, dy / d)
        else:
            degenerate.append(axis)

    for axis in degenerate:
        others = list(directions.values())
        sx, sy = sum(v[0] for v in others), sum(v[1] for v in others)
        directions[axis] = _normalize((-sx, -sy)) if (sx or sy) else (1.0, 0.0)

    for axis in "XYZ":
        dx, dy = directions[axis]
        length = TRIAD_LENGTH * (0.6 if axis in degenerate else 1.0)
        ex, ey = ax + length * dx, ay + length * dy
        lines[axis].position = (ax, ay)
        lines[axis].position2 = (ex, ey)
        labels[axis].position = (ex + (0.015 if dx >= 0 else -0.03),
                                  ey + (0.012 if dy >= 0 else -0.03))


def main():
    args = parse_args()
    out_dir = args.out or os.path.join(args.run_dir, "frames")
    os.makedirs(out_dir, exist_ok=True)

    db = lag_db = body_plot_index = None

    if args.session:
        # Replays exactly what was built by hand in the GUI -- same databases,
        # plots, operators, colors, contour method/levels. All of the manual
        # plot-construction options above are irrelevant here.
        RestoreSession(args.session, 0)
        label = args.label or os.path.splitext(os.path.basename(args.session))[0]
    else:
        db = os.path.join(args.run_dir, "viz_cylinder3d", "dumps.visit")
        if not OpenDatabase(db):
            sys.exit(f"could not open database: {db}")

        DefineScalarExpression("vort_mag", "magnitude(Omega)")
        DefineScalarExpression("vel_mag", "magnitude(U)")
        DefineScalarExpression("omega_z", "Omega[2]")

        # Opening a SAMRAI AMR database auto-adds a "Subset" plot (Var: levels)
        # colored by patch refinement level -- that's the red/green/blue/cyan
        # patchwork with its own legend seen alongside the real contour. Drop it
        # before adding our own plot so only the iso-surface remains.
        pl = GetPlotList()
        if pl.GetNumPlots() > 0:
            SetActivePlots(tuple(range(pl.GetNumPlots())))
            DeleteActivePlots()

        if args.values:
            colors = args.colors or ["red"] * len(args.values)
            if len(colors) != len(args.values):
                sys.exit("--colors must have the same number of entries as --values")
            for value, color_name in zip(args.values, colors):
                AddPlot("Contour", args.variable)
                if args.wall_margin > 0:
                    add_wall_clip_operator(args.wall_margin)
                if args.resample:
                    add_resample_operator(args)
                contour = ContourAttributes()
                contour.contourMethod = contour.Value
                contour.contourValue = (value,)
                contour.colorType = contour.ColorBySingleColor
                contour.singleColor = COLOR_PRESETS.get(color_name, COLOR_PRESETS["red"])
                contour.legendFlag = 1
                SetPlotOptions(contour)
        else:
            AddPlot("Contour", args.variable)
            if args.wall_margin > 0:
                add_wall_clip_operator(args.wall_margin)
            if args.resample:
                add_resample_operator(args)
            contour = ContourAttributes()
            if args.contour_value is not None:
                contour.contourMethod = contour.Value
                contour.contourValue = (args.contour_value,)
            else:
                contour.contourMethod = contour.Percent
                contour.contourPercent = (args.contour_percent,)
            # Force a single solid color (rather than VisIt's default per-patch/level
            # coloring) so the surface reads as one coherent shape.
            contour.colorType = contour.ColorBySingleColor
            contour.singleColor = COLOR_PRESETS["red"]
            contour.legendFlag = 1
            SetPlotOptions(contour)

        # Always open the body mesh (if present) -- needed to auto-center the
        # camera on it even when --no-lag-points means not drawing it visibly.
        lag_db, mesh_name = open_body_mesh(args.run_dir)
        if lag_db:
            body_plot_index = GetPlotList().GetNumPlots()
            AddPlot("Mesh", mesh_name)
            ma = MeshAttributes()
            ma.pointSize = args.lag_point_size
            ma.pointSizePixels = int(args.lag_point_size)
            ma.meshColor = COLOR_PRESETS.get(args.lag_point_color, COLOR_PRESETS["black"])
            ma.meshColorSource = ma.MeshCustom
            ma.legendFlag = 0
            SetPlotOptions(ma)
        elif args.lag_points:
            print(f"warning: no viz_cylinder3d/lag_data.visit under {args.run_dir}, "
                  f"skipping Lagrangian overlay and camera auto-centering")

        label = args.label or args.variable

    DrawPlots()

    # Strip every built-in annotation (user/timestamp, DB/cycle/time, legend,
    # native axes3D triad) -- only our own right-anchored triad (below) draws.
    aa = AnnotationAttributes()
    aa.userInfoFlag = 0
    aa.databaseInfoFlag = 0
    aa.timeInfoFlag = 0
    aa.legendInfoFlag = 0
    aa.axes3D.visible = 0
    aa.axes3D.triadFlag = 0
    aa.axes3D.bboxFlag = 0
    SetAnnotationAttributes(aa)

    lines, labels = make_triad()

    if args.cycle is not None:
        n_states = TimeSliderGetNStates()
        cycle = n_states - 1 if args.cycle < 0 else args.cycle
        SetTimeSliderState(cycle)
    elif not args.session:
        SetTimeSliderState(TimeSliderGetNStates() - 1)
    # else: --session given and --cycle omitted -- keep the state the session
    # itself was saved at (see --cycle help above).

    # Measure the body's actual position/size AT THIS TIMESTEP (it moves --
    # see module docstring numbers) so the "scale" cameras can center on it.
    # Keep the full bbox; each preset picks which two world axes to frame
    # off via extent_axes (defaults to x,y -- see axis_half_extent), since
    # that depends on which axes are actually that camera's screen plane.
    body_center = body_bbox = None
    if body_plot_index is not None:
        SetActivePlots((body_plot_index,))
        Query("SpatialExtents", use_actual_data=1)
        xmin, xmax, ymin, ymax, zmin, zmax = GetQueryOutputValue()
        body_center = ((xmin + xmax) / 2, (ymin + ymax) / 2, (zmin + zmax) / 2)
        body_bbox = (xmin, xmax, ymin, ymax, zmin, zmax)
        # Hide the body plot now -- SpatialExtents above needed it visible
        # (VisIt refuses to query a hidden plot), but --no-lag-points means
        # it shouldn't actually show up in the saved images.
        if not args.lag_points:
            SetActivePlots((body_plot_index,))
            HideActivePlots()

    swa = SaveWindowAttributes()
    swa.format = swa.PNG if args.format == "png" else swa.POSTSCRIPT
    swa.width, swa.height = args.width, args.height
    swa.screenCapture = 0
    swa.outputToCurrentDirectory = 0
    swa.outputDirectory = out_dir

    for name in args.cameras:
        if name != "keep":
            preset = CAMERAS[name]
            view = View3DAttributes()
            view.viewNormal = preset["viewNormal"]
            view.viewUp = preset["viewUp"]
            view.imageZoom = preset["imageZoom"]
            view.nearPlane, view.farPlane = -DEFAULT_NEAR_FAR, DEFAULT_NEAR_FAR
            if "scale" in preset:
                if body_center is None:
                    print(f"{name}: no body mesh found, centering on the origin instead")
                view.focus = body_center or (0.0, 0.0, 0.0)
                half_extent = (axis_half_extent(body_bbox, preset.get("extent_axes", (0, 1)))
                               if body_bbox else FALLBACK_HALF_EXTENT)
                view.parallelScale = preset["scale"] * half_extent
            else:
                view.focus = (body_center if preset.get("auto_focus") and body_center else
                               preset["focus"])
                view.parallelScale = preset["parallelScale"]
            for optional_field in ("viewAngle", "nearPlane", "farPlane", "imagePan", "perspective"):
                if optional_field in preset:
                    setattr(view, optional_field, preset[optional_field])
            SetView3D(view)
            update_triad(lines, labels, preset["viewNormal"], preset["viewUp"])
        else:
            current_view = GetView3D()
            update_triad(lines, labels, current_view.viewNormal, current_view.viewUp)

        swa.fileName = f"{label}_{name}"
        SetSaveWindowAttributes(swa)
        saved = SaveWindow()
        print(f"{name}: saved {saved}")

        if args.format == "pdf":
            pdf_path = os.path.splitext(saved)[0] + ".pdf"
            try:
                subprocess.run(["ps2pdf", saved, pdf_path], check=True)
                print(f"{name}: converted to {pdf_path}")
            except Exception as exc:
                print(f"{name}: ps2pdf conversion failed ({exc}), keeping {saved}")

    DeleteAllPlots()
    if db:
        CloseDatabase(db)
    if lag_db:
        CloseDatabase(lag_db)


if __name__ == "__main__":
    main()
