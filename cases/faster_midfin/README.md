# Case: `faster_midfin`

**Cylinder with one central fin — full z-span, periodic z.** Same physics and
enlarged x/y domain as [`faster_nofin_full_span`](../faster_nofin_full_span/README.md),
but with a single fin of doubled radius (2R = 6.34) at the axial midpoint (z = 0).
No end caps. The cylinder is effectively infinite in the spanwise direction.

## Body (`geometry.json`)

| | |
|---|---|
| Shape | solid circular cylinder, axis along **z** |
| Radius | 3.17 (diameter D = 6.34) |
| Length | 35.0 (spans full z-domain) |
| End caps | none (`use_disk = 0`) |
| Mid-fin | 1 fin at z-fraction 0.5, radius **6.34** (2R) |
| IB points | 4,549,032 |

## Flow (`input3d`)

| | |
|---|---|
| Fluid | ρ = 1.0, μ = 0.01 |
| Domain | x ∈ [−30, 120], y ∈ [−120, 30], z ∈ [−17.5, 17.5] |
| Grid | 150 × 150 × 35 base, 4 levels, refinement 4·4·2 → finest dx = 0.0625 |
| z BC | **periodic** (`periodic_dimension = 0, 0, 1`) |
| Motion | prescribed: `U_infinity · cos(2πft)` with U = 1.0, **f = 0.6** |
| Constraint | `CONSTRAINT_VELOCITY`; translation tracked in x/y/z |
| Gravity | −981 · δ in y, active from **t = 0** |
| Run | END_TIME = 30, DT_MAX = 5e-4, CFL ≤ 0.3 |

Reynolds number based on diameter, ρUD/μ ≈ **634**.
Keulegan–Carpenter number U/(fD) ≈ **0.26**.
Buoyancy parameter δ = **0.011**.
Rotation frequency f = **0.6**.

## Comparison with sibling cases

| Parameter | `faster_nofin_full_span` | `faster_midfin` |
|-----------|-------------------------|-----------------------|
| Cylinder L | 35.0 | 35.0 |
| z BC | periodic | periodic |
| End caps | none | none |
| Mid-fin | none | **1 × R=6.34 at z=0** |
| IB points | 4,524,800 | 4,549,032 |

## Regenerate

```bash
python3 tools/generate_vertex.py cases/faster_midfin          # rebuild mesh
python3 tools/generate_vertex.py cases/faster_midfin --check  # verify
IBAMR_SCRATCH_DIR=/scratch/$USER/3dRotatingCylinder python3 setup_run.py faster_midfin
```
