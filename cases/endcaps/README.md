# Case: `endcaps`

**Cylinder with two end caps.** The same oscillating cylinder as `faster_nofin`,
but with a wide disc capping each end of the body. This is the simplest step away
from the bare baseline: it adds bluff, flow-normal area at the two extremities
only, with nothing in between.

Previously the repo-root `input3d` / `Cylinder.py` pair, moved into the case layout.

## Body (`geometry.json`)

| | |
|---|---|
| Shape | solid circular cylinder, axis along **z** |
| Radius | 3.17 (diameter D = 6.34) |
| Length | 25.5 |
| End caps | **2**, radius 7.0, at the first and last z-layer (`use_disk = 1`, `total_disks = 2`) |
| Fins | none — `total_disks = 2` means both discs are consumed by the end caps |
| IB points | 3,359,238 — one per finest Eulerian cell, spacing 0.0625 |

The end caps are one cell thick (a single z-layer each) and stick out to more
than twice the cylinder radius.

## Flow (`input3d`)

| | |
|---|---|
| Fluid | ρ = 1.0, μ = 0.01 |
| Domain | x ∈ [−20, 80], y ∈ [−72, 18], z ∈ [−17.5, 17.5] |
| Grid | 100 × 90 × 35 base, 4 levels, refinement 4·2·2 → finest dx = 0.0625 |
| Motion | prescribed: `U_infinity · cos(2πft)` with U = 1.0, **f = 0.3333** |
| Constraint | `CONSTRAINT_VELOCITY`; translation tracked in x/y/z, **no rotation** |
| Gravity | −981 · 0.00355 in y, active from **t = 3.0** |
| Upper-y BC | **closed** (Dirichlet: a = 1, b = 0) |
| Run | END_TIME = 30, DT_MAX = 5e-4, CFL ≤ 0.3 |

Reynolds number based on diameter, ρUD/μ ≈ **634**.
Keulegan–Carpenter number U/(fD) ≈ **0.47**.

## Differences from `faster_nofin`

Not just the geometry — the flow setup differs too, so the two are **not** a
clean controlled comparison as they stand:

| | `faster_nofin` | `endcaps` |
|---|---|---|
| End caps | none | 2 × R=7.0 |
| Oscillation frequency | 0.6 | 0.3333 |
| Gravity multiplier | 0.011 | 0.00355 |
| Gravity onset | t = 0 | t = 3.0 |
| Upper-y boundary | open (traction) | closed (Dirichlet) |

The delayed gravity (`gravity_start_time = 3.0`) lets the oscillatory flow
establish itself before the body is allowed to settle under the net body force.

## Notes

As in the baseline, the body is **oscillated, not rotated**
(`calculate_rotational_momentum = 0,0,0`), and it is neutrally buoyant
(`rho_solid = rho_fluid`) with the gravity multiplier supplying the net body
force as a reduced/effective gravity.

## Regenerate

```bash
python3 tools/generate_vertex.py cases/endcaps          # rebuild the mesh
python3 tools/generate_vertex.py cases/endcaps --check  # verify, don't write
python3 setup_run.py endcaps                            # stage + submit
```
