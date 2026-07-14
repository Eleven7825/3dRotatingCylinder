# Cases

Each subdirectory is one simulation case — a matched pair of *flow* parameters
(`input3d`) and *body* parameters (`geometry.json`), plus the point cloud
generated from the latter.

```
cases/<case-name>/
    input3d            flow / solver parameters      (hand-edited, committed)
    geometry.json      body parameters               (hand-edited, committed)
    cylinder3d.vertex  IB point cloud                (generated, committed via LFS)
    indices            end-cap / fin point markers   (generated, committed)
```

`cylinder3d.vertex` and `indices` are **derived** from `geometry.json`. Never
hand-edit them — regenerate:

```bash
python3 tools/generate_vertex.py cases/<case-name>
```

To confirm a committed vertex file still matches its `geometry.json` (i.e. that
they have not drifted apart):

```bash
python3 tools/generate_vertex.py cases/<case-name> --check
```

## Adding a case

```bash
cp -r cases/faster_nofin cases/my-new-case
# edit cases/my-new-case/geometry.json and input3d
python3 tools/generate_vertex.py cases/my-new-case
python3 setup_run.py my-new-case
```

## Existing cases

| Case | Body | Points | Notes |
|------|------|--------|-------|
| `faster_nofin` | bare cylinder, R=3.17, L=25.5 | 3,296,640 | no end caps, no fins. Oscillation f=0.6, open top BC, gravity on from t=0, END_TIME=30 |
| `endcaps` | 2 end caps, R=7.0 | 3,359,238 | no internal fins. Oscillation f=0.3333, closed top BC, gravity from t=3.0 |

## Keeping geometry.json and input3d consistent

The IB point cloud must be one point per *finest* Eulerian cell, so the spacing
implied by `geometry.json` has to equal the finest spacing implied by `input3d`:

- `geometry.json`: `dx = mesh.Lx / mesh.Nx` — currently `100.0 / 1600 = 0.0625`
- `input3d`: `dx = Lx / Nx / (REF_RATIO^(MAX_LEVELS-2) * REF_RATIO_FINEST...)`
  — currently `100.0 / 100 / (4·2·2) = 0.0625`

If you change the refinement in `input3d`, change `mesh.N*` in `geometry.json`
to match and regenerate the vertex file.

> Note: `mesh.Ly = 45.0` while `input3d` uses `Ly = 90.0`. This is intentional
> and harmless — only the *ratio* `Ly/Ny` (the spacing) matters to the point
> cloud, and `45.0/720` equals `90.0/1440`, i.e. 0.0625 either way. The domain
> extent that the solver actually uses comes from `input3d` alone.
