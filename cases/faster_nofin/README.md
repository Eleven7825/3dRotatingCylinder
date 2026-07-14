# Case: `faster_nofin`

**Bare cylinder — the baseline.** A smooth circular cylinder with no end caps and
no fins, oscillating horizontally in an otherwise quiescent viscous fluid. This
is the control case: whatever the fins do in the other cases, it is measured
against this one.

Imported from `/media/shiyi/vast/3dRotatingCylinder/Jun22_faster_nofin`.

## Body (`geometry.json`)

| | |
|---|---|
| Shape | solid circular cylinder, axis along **z** |
| Radius | 3.17 (diameter D = 6.34) |
| Length | 25.5 |
| End caps | none (`use_disk = 0`) |
| Fins | none |
| IB points | 3,296,640 — one per finest Eulerian cell, spacing 0.0625 |

## Flow (`input3d`)

| | |
|---|---|
| Fluid | ρ = 1.0, μ = 0.01 |
| Domain | x ∈ [−20, 80], y ∈ [−72, 18], z ∈ [−17.5, 17.5] |
| Grid | 100 × 90 × 35 base, 4 levels, refinement 4·2·2 → finest dx = 0.0625 |
| Motion | prescribed: `U_infinity · cos(2πft)` with U = 1.0, **f = 0.6** |
| Constraint | `CONSTRAINT_VELOCITY`; translation tracked in x/y/z, **no rotation** |
| Gravity | −981 · 0.011 in y, active from **t = 0** |
| Upper-y BC | **open** (traction: a = 0, b = 1) |
| Run | END_TIME = 30, DT_MAX = 5e-4, CFL ≤ 0.3 |

Reynolds number based on diameter, ρUD/μ ≈ **634**.
Keulegan–Carpenter number U/(fD) ≈ **0.26**.

## Notes

Despite the repository name, the body here is **oscillated, not rotated** —
`calculate_rotational_momentum` is `0,0,0` and the kinematics are a pure
translational cosine.

The gravity vector carries a multiplier (`0.011`), so it acts as a reduced /
effective gravity rather than full 981; the solid and fluid densities are set
equal (`rho_solid = rho_fluid`), i.e. the body is neutrally buoyant and this term
supplies the net body force directly.

> **Provenance:** the `cylinder3d.vertex` on vast was generated with
> `use_disk = 0`, but the `Cylinder3d.py` sitting beside it had `use_disk = 1`
> (which would have produced end caps and 3,345,104 points), and its `indices`
> file was stale from a `use_disk = 1` run. The mesh here reproduces the vast
> vertex file **byte for byte** (SHA-256 `ad5ad5f1aa39…`); `geometry.json`
> records the `use_disk = 0` that actually produced it, and `indices` is
> regenerated correctly as `8079 / 3296639`.

## Regenerate

```bash
python3 tools/generate_vertex.py cases/faster_nofin          # rebuild the mesh
python3 tools/generate_vertex.py cases/faster_nofin --check  # verify, don't write
python3 setup_run.py faster_nofin                            # stage + submit
```
