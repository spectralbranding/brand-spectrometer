# Brand Spectrometer

[![License: MIT](https://img.shields.io/badge/Code-MIT-blue.svg)](LICENSE)
[![Docs & Schema: CC BY 4.0](https://img.shields.io/badge/Docs%20%26%20Schema-CC%20BY%204.0-lightgrey.svg)](LICENSE-data)
[![Live tool](https://img.shields.io/badge/Live-meter.spectralbranding.com-14B8A6.svg)](https://meter.spectralbranding.com)

The open renderer and method of the **Brand Spectrometer** — an instrument that reads how
different audiences perceive a brand, cohort by cohort, across eight dimensions, and tells you
which differences between audiences are *real* versus within the margin of error.

Live, ready to use: **[meter.spectralbranding.com](https://meter.spectralbranding.com)**.

This repository contains the in-browser renderer, the atlas data format and its validator, the
**offline reproduction battery** that re-derives the methods-paper numbers from a bundled published
atlas, and the published methodology — everything needed to use the instrument and to reproduce the
paper's results.

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
independent operator runs (the noise floor).

## 4. The eight dimensions

Semiotic · Narrative · Ideological · Experiential · Social · Economic · Cultural · Temporal —
each scored 0–10 per audience. A brand's "shape" is its profile across all eight. Full definitions
in [`docs/METHODOLOGY.md`](docs/METHODOLOGY.md).

## 5. Reproduce the methods paper

The published methods paper (2026; see §8) reports its headline measurement properties from one
published worked-example atlas — the Ferrari *Luce* fresh-window read. This repository bundles that
atlas and the eight offline battery scripts that compute every headline number, so the paper is
reproducible **with no API keys and no network access** — only `numpy` and `pyyaml`.

```bash
bash reproduce.sh
```

It runs the battery against `data/ferrari_luce_fresh_2606/` at the canonical grain (`host`) and
fixed seed (`20260621`) and prints the headline numbers, including:

- **Distributional signal-to-noise**, actual-owners vs non-italian-press: **≈ 3.56**.
- **Aggregate mean-cosine signal-to-noise** (operator floor): **≈ 0.86**.
- **Dimension attribution** (actual-owners vs pooled press): large Cohen's *d* on the semiotic,
  ideological, experiential, economic, cultural, and temporal dimensions (Holm-corrected
  permutation *p* < .05).
- **Reliability battery** (V2 cross-operator / V3 split-half / V5 reproducibility): pass.

The battery reads only the offline reflection records (model-produced 8-vectors and their public
provenance metadata); the renders re-derive deterministically. The bundled `atlas.yaml` is a
sanitized stub (derived variance statistics only — no raw artifact text).

## 6. Repository layout

```
reproduce.sh   key-free orchestrator that re-derives the methods-paper headline numbers
tool/          the in-browser renderer + assets + a demo atlas
schema/        atlas_schema_v0.1.yaml — the atlas data format
code/          the offline reproduction battery + validate_atlas.py (format validator)
data/          ferrari_luce_fresh_2606 — the published worked-example atlas the battery reads
docs/          METHODOLOGY.md, SCHEMA_DESIGN_NOTES.md, TRADEMARK_NOTICE.md
```

The `tool/` directory is a published **snapshot** of the live tool at
[meter.spectralbranding.com](https://meter.spectralbranding.com) (the canonical deploy lives
elsewhere; this copy is for transparency and as a worked example). See `tool/README.md`.

Validate an atlas:

```bash
uv run --with "pyyaml>=6.0" --with "pydantic>=2.0" python code/validate_atlas.py path/to/atlas.yaml
```

## 7. The science

The Brand Spectrometer is the measurement layer of **Spectral Brand Theory**. Read the research at
[spectralbranding.com](https://spectralbranding.com).

- **Methods paper** (this instrument): Zharnikov, D. (2026), *The Brand Spectrometer: A Reproducible
  Instrument for Cohort-Resolved, Multi-Dimensional Brand-Perception Measurement from Public
  Artifacts*, DOI [10.5281/zenodo.20775963](https://doi.org/10.5281/zenodo.20775963)
  (concept DOI — resolves to the latest version).
- **Validation dataset** (the V1–V6 reliability/reproducibility outputs): Hugging Face
  `spectralbranding/brand-spectrometer-validation`, DOI
  [10.57967/hf/9249](https://doi.org/10.57967/hf/9249).
- **Cohort/metamerism foundation**: Zharnikov, D. (2026), *Dimensional Collapse in AI Brand
  Perception*, DOI [10.5281/zenodo.19422427](https://doi.org/10.5281/zenodo.19422427).

## 8. License & citation

- **Code** (the tool, the validator, the reproduction battery): MIT — see [`LICENSE`](LICENSE).
- **Docs, schema, methodology, and bundled atlas data**: CC BY 4.0 — see
  [`LICENSE-data`](LICENSE-data).
- Please cite via [`CITATION.cff`](CITATION.cff).

## 9. Trademark

Brand names appear only as nominative references for analysis. No logos, wordmarks, or trade dress
are reproduced. See [`docs/TRADEMARK_NOTICE.md`](docs/TRADEMARK_NOTICE.md).
