# Format your data with your own AI

You don't need our pipeline to try the Brand Spectrometer tool on your own brand. Use
**your own AI** (Claude, ChatGPT, Gemini, …) to convert raw material into a valid standard
atlas, then load it into the tool.

The AI does only the part it's good at — **reading text and scoring the eight dimensions (and,
optionally, their sentiment) per cohort**. The tool does the geometry (cohort distances,
metameric degree) deterministically, so you don't rely on an LLM to do arithmetic.

## Steps

1. **Copy the prompt below** (or click "Copy the AI prompt" in the tool). It is self-contained —
   you do not attach or download anything.
2. **Paste it into your AI** (Claude, ChatGPT, Gemini, …) together with your raw material — public
   reviews, forum threads, press, listings, **or your own first-party data (survey, poll, or panel
   results, interview notes)** — ideally with a note on which audience (cohort) each piece comes
   from. The prompt carries the full output format, and if your AI can open links it also points it
   at the format and a worked example online.
3. The AI returns either a **valid atlas JSON** or an **error object** listing what's missing —
   it will not emit an invalid atlas.
4. **Bring it back** to the tool (drag-drop, file picker, or host it and paste the URL).

The tool re-validates on load and **recomputes the checksum**; a mismatch warns you the data
may have been truncated or hand-edited.

## The prompt (copy verbatim)

````
You are a data-formatting operator for the Brand Spectrometer. The required output format is
specified in full below — nothing is attached, you have everything you need here. (If you can
open links, you may also fetch the exact format from
https://meter.spectralbranding.com/atlas.schema.json and a filled example from
https://meter.spectralbranding.com/atlas_template.json, but this prompt is self-contained.)
Convert the raw data I provide into a single JSON object that strictly conforms to it.

RULES
- Output the JSON object (or the ERROR object described below) wrapped in a single ```json fenced code block, and nothing else — no prose before or after. (A code block keeps the quotes straight so it pastes back cleanly.)
- Use these eight dimension KEYS, in this exact order, as `dims`, and provide ONLY the keys —
  the tool supplies the labels, descriptions, and colours (you cannot change them):
  semiotic, narrative, ideological, experiential, social, economic, cultural, temporal.
  Emit `dims` as `[{"key":"semiotic"},{"key":"narrative"}, … ,{"key":"temporal"}]` in that order.
- Group the raw data into the audience cohorts it implies (>=2). Give each cohort an `id`,
  a short `label`, and a `vector` of eight numbers (0-10) scoring how STRONGLY each dimension
  registers for that cohort (size of the meaning, NOT approval), in the dimension order above.
  Do NOT set a cohort colour — the tool assigns one.
- RECOMMENDED: also add `valence` — eight numbers (-1..+1), same dimension order, the
  SENTIMENT of each dimension for that cohort: -1 hostile/negative, 0 neutral, +1 favourable.
  This is DISTINCT from `vector` (strength, not approval) and lights up the tool's Sentiment
  view (the dot's position on each line). Omit only if the raw data gives no read on sentiment.
- Do NOT invent `ci_95` (uncertainty intervals) or `reflections` (per-source readings) —
  those come from the multi-run pipeline, not a single read; omit them.
- Do NOT compute `distances` — omit it. The tool computes geometry from the vectors.
- Fill `meta` (brand, atlas slug, window, generation:"byo", a short notes line). Put any
  evidence caveats in notes. Do not reproduce brand logos/wordmarks/trade-dress.
- Compute `meta.checksum` = "BSx-" + (number of cohorts) + "-8-" + round(10 * sum of every
  number across all cohort `vector` arrays ONLY — not valence). Example: 2 cohorts, vector
  sums 40.0 and 36.0 -> 10*76.0 = 760 -> "BSx-2-8-760".
- GATING: if the raw data cannot support at least two distinct cohorts, or cannot ground the
  eight dimensions at all, do NOT invent data. Instead output exactly:
  {"ERROR": "reason", "missing": ["what evidence is needed"]}

Everything you need is specified above — nothing is attached. The raw data follows.
````

## What the tool needs vs. computes

| You / your AI provide | The tool computes / adds |
|---|---|
| `meta`, `dims` (the 8), `cohorts[].vector` (0–10) | pairwise `distances` (1 − cosine) if omitted |
| optional `cohorts[].valence` (−1..+1) → Sentiment view | `metameric_degree` if omitted |
| optional `provenance`, `notes` | re-checks `meta.checksum`; warns on mismatch |
| `meta.checksum` (integrity token) | — |

The dial's higher rungs map to optional fields: **`valence`** lights up the Sentiment view (a
single AI read can provide it); **`ci_95`** (per-dimension uncertainty) and **`reflections`**
(per-source readings) light up Resolve and Cloud but come from the **multi-run pipeline**, not a
single read — don't fabricate them. Noise floors and per-pair signal-to-noise (the "is this
difference real?" gate) likewise require **multiple independent operator runs** — that's what
our pipeline adds. A BYO atlas renders fully (with valence if you provide it); it just won't show
the uncertainty halo or the noise-floor gate.
