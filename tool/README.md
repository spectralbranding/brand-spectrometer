# Brand Spectrometer — tool snapshot

This directory is a **published snapshot** of the live Brand Spectrometer tool, which runs at:

**https://meter.spectralbranding.com**

The canonical deployment lives elsewhere; this copy is included in this repository for
**transparency** and as a **worked example** of the renderer and the atlas data format. It is not
the deployment itself — website-deploy artifacts (Open Graph images, `_headers`/`_redirects`,
favicons, sitemap, build scripts, etc.) are intentionally excluded.

## Contents

| File | What it is |
|---|---|
| `spectrometer.html` | The in-browser renderer (open it directly, or serve this directory). |
| `spectrum_strip.js` | The shared spectrum-strip rendering module used by the page. |
| `how-to-read.html` | Plain-language guide to reading a spectrum strip. |
| `faq.html` | Frequently asked questions. |
| `data/ferrari_luce.json` | The default worked-example atlas loaded by the tool. |
| `atlas.schema.json` | JSON Schema for the atlas data format the tool ingests. |
| `atlas_template.json` | A filled example atlas you can adapt. |
| `CONVERT_WITH_YOUR_AI.md` | Step-by-step guide to building your own atlas with any capable AI. |

## Run it locally

```bash
python3 -m http.server --directory tool
# then open http://localhost:8000/spectrometer.html
```

The page runs entirely client-side; nothing you load is uploaded.
