# CAT Model ELT Documents

Containerized, deterministic document workflow for a catastrophe ELT primer package.

## Artifacts

- `elt_primer.qmd`: canonical primer document
- `primer_quickstart.qmd`: fast-start operational guide
- `executable_index.qmd`: runnable script and target map

## Deterministic Runtime Config

Runtime controls are in `render.env`:

- `DEV_N_SIMS`
- `FULL_N_SIMS`
- `SEED_R`
- `SEED_PY`
- `OUTPUT_DIR`

## Build and Render

```bash
just image-build
just render-dev-container
just render-full-container
```

## Local Render (without container)

If Quarto + dependencies are already installed locally:

```bash
just render-dev
just render-full
```
