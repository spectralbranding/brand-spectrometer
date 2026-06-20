# Brand Spectrometer

[![License: MIT](https://img.shields.io/badge/Code-MIT-blue.svg)](LICENSE)
[![Docs & Schema: CC BY 4.0](https://img.shields.io/badge/Docs%20%26%20Schema-CC%20BY%204.0-lightgrey.svg)](LICENSE-data)
[![Live tool](https://img.shields.io/badge/Live-meter.spectralbranding.com-14B8A6.svg)](https://meter.spectralbranding.com)

The open renderer and method of the **Brand Spectrometer** — an instrument that reads how
different audiences perceive a brand, cohort by cohort, across eight dimensions, and tells you
which differences between audiences are *real* versus within the margin of error.

Live, ready to use: **[meter.spectralbranding.com](https://meter.spectralbranding.com)**.

This repository is the **open core**: the in-browser renderer, the atlas data format and its
validator, and the published methodology. It is the free tier and the scientific record. The
proprietary data-collection panel and the at-scale production service are not part of this
repository (see §6).

## 1. What it is

Most brand measurement averages every audience into one number and reports a single score. That
average hides the most useful thing — that different audiences can perceive the same brand as
almost different brands. The Brand Spectrometer keeps audiences apart, shows the eight-dimension
*shape* of each, and marks which gaps between them clear the instrument's own noise floor.

It is **ground-truth absent** by design: there is no single "true" brand spec to recover. The
variance across audiences *is* the measurement. The instrument reports measurement properties
(reliability, reproducibility, structural validity) against its own noise floors — never a verdict.

## 2. Try it

- **Online (nothing to install):** open [meter.spectralbranding.com](https://meter.spectralbranding.com).
  A worked-example atlas is loaded by default.
- **Locally:** open `tool/spectrometer.html` in a browser, or serve the `tool/` directory
  (`python3 -m http.server --directory tool`) and visit it. The page runs entirely client-side;
  nothing you load is uploaded.

## 3. Bring your own brand

The tool ingests any atlas conforming to the published format. The easiest way to make one is to
let your own AI build it:

1. In the tool, click **Copy the AI prompt**.
2. Paste it into any capable model (Claude, ChatGPT, Gemini) together with your material.
3. Paste the result back. The page renders the full read.

The prompt is self-contained and references the format at `tool/atlas.schema.json`
(`tool/atlas_template.json` is a filled example; `tool/CONVERT_WITH_YOUR_AI.md` is the step guide).
A single-AI atlas is a useful *shape*, not yet a measurement — a measurement requires multiple
independent operator runs (the noise floor), which is what the production pipeline adds.

## 4. The eight dimensions

Semiotic · Narrative · Ideological · Experiential · Social · Economic · Cultural · Temporal —
each scored 0–10 per audience. A brand's "shape" is its profile across all eight. Full definitions
in [`docs/METHODOLOGY.md`](docs/METHODOLOGY.md).

## 5. Repository layout

```
tool/      the in-browser renderer (the free tier) + assets + a demo atlas
schema/    atlas_schema_v0.1.yaml — the atlas data format
code/      validate_atlas.py — a standalone validator for the format
docs/      METHODOLOGY.md, SCHEMA_DESIGN_NOTES.md, TRADEMARK_NOTICE.md
```

Validate an atlas:

```bash
uv run --with "pyyaml>=6.0" --with "pydantic>=2.0" python code/validate_atlas.py path/to/atlas.yaml
```

## 6. Open-core boundary

Public (this repo): the **renderer**, the **method**, the **format + validator**, and published
worked examples. Private (not here): the **data-collection panel**, the **at-scale production
service**, and any **customer atlases**. What a paying customer gets is resolution and
reproducibility — the noise floor produced by the private pipeline — not the open renderer.

## 7. The science

The Brand Spectrometer is the measurement layer of **Spectral Brand Theory**. Read the research at
[spectralbranding.com](https://spectralbranding.com). The cohort/metamerism foundation:
Zharnikov, D. (2026), *Dimensional Collapse in AI Brand Perception*,
DOI [10.5281/zenodo.19422427](https://doi.org/10.5281/zenodo.19422427).

## 8. License & citation

- **Code** (the tool, the validator): MIT — see [`LICENSE`](LICENSE).
- **Docs, schema, and methodology**: CC BY 4.0 — see [`LICENSE-data`](LICENSE-data).
- Please cite via [`CITATION.cff`](CITATION.cff).

## 9. Trademark

Brand names appear only as nominative references for analysis. No logos, wordmarks, or trade dress
are reproduced. See [`docs/TRADEMARK_NOTICE.md`](docs/TRADEMARK_NOTICE.md).
