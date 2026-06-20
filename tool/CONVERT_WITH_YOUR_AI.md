# Format your data with your own AI

You don't need our pipeline to try the Brand Spectrometer tool on your own brand. Use
**your own AI** (Claude, ChatGPT, Gemini, …) to convert raw material into a valid standard
atlas, then load it into the tool.

The AI does only the part it's good at — **reading text and scoring the eight dimensions per
cohort**. The tool does the geometry (cohort distances, metameric degree) deterministically,
so you don't rely on an LLM to do arithmetic.

## Steps

1. **Copy the prompt below** (or click "Copy the AI prompt" in the tool). It is self-contained —
   you do not attach or download anything.
2. **Paste it into your AI** (Claude, ChatGPT, Gemini, …) together with your raw material —
   public reviews, forum threads, press, listings, etc., ideally with a note on which audience
   (cohort) each piece comes from. The prompt carries the full output format, and if your AI can
   open links it also points it at the format and a worked example online.
3. The AI returns either a **valid atlas JSON** or an **error object** listing what's missing —
   it will not emit an invalid atlas.
4. **Bring it back** to the tool (drag-drop, file picker, or host it and paste the URL).

The tool re-validates on load and **recomputes the checksum**; a mismatch warns you the data
may have been truncated or hand-edited.

## The prompt (copy verbatim)

```
You are a data-formatting operator for the Brand Spectrometer. The required output format is
specified in full below — nothing is attached, you have everything you need here. (If you can
open links, you may also fetch the exact format from
https://meter.spectralbranding.com/atlas.schema.json and a filled example from
https://meter.spectralbranding.com/atlas_template.json, but this prompt is self-contained.)
Convert the raw data I provide into a single JSON object that strictly conforms to it.

RULES
- Output ONLY the JSON object (or the ERROR object described below). No prose, no markdown.
- Use these eight dimensions, in this exact order, as `dims` (keys/labels/colors verbatim):
  1 semiotic     "Semiotic"     "signs, symbols, codes"        #e64a3b
  2 narrative    "Narrative"    "the story it tells"           #e8842b
  3 ideological  "Ideological"  "what it stands for"           #e8c531
  4 experiential "Experiential" "what it feels like to use"    #7bc043
  5 social       "Social"       "who you're seen as"           #2fb3a8
  6 economic     "Economic"     "value, price, worth"          #3a8dde
  7 cultural     "Cultural"     "its place in the world"       #7a5cd0
  8 temporal     "Temporal"     "heritage & momentum"          #c44fa8
- Group the raw data into the audience cohorts it implies (>=2). Give each cohort an id,
  a short label, a distinct hex color, and a `vector` of eight numbers (0-10) scoring how
  STRONGLY each dimension registers for that cohort (size of the meaning, NOT approval).
- Do NOT compute `distances` — omit it. The tool computes geometry from the vectors.
- Fill `meta` (brand, atlas slug, window, generation:"byo", a short notes line). Put any
  evidence caveats in notes. Do not reproduce brand logos/wordmarks/trade-dress.
- Compute `meta.checksum` = "BSx-" + (number of cohorts) + "-8-" + round(10 * sum of every
  number across all cohort vectors). Example: 2 cohorts, vector sums 40.0 and 36.0 ->
  10*76.0 = 760 -> "BSx-2-8-760".
- GATING: if the raw data cannot support at least two distinct cohorts, or cannot ground the
  eight dimensions at all, do NOT invent data. Instead output exactly:
  {"ERROR": "reason", "missing": ["what evidence is needed"]}

Everything you need is specified above — nothing is attached. The raw data follows.
```

## What the tool needs vs. computes

| You / your AI provide | The tool computes |
|---|---|
| `meta`, `dims` (the 8), `cohorts[].vector` (0–10) | pairwise `distances` (1 − cosine) if omitted |
| optional `provenance`, `notes` | `metameric_degree` if omitted |
| `meta.checksum` (integrity token) | re-checks the checksum; warns on mismatch |

Noise floors and per-pair signal-to-noise (the "is this difference real?" gate) require
**multiple independent operator runs** — that's what our pipeline adds and a single-AI
conversion can't. A BYO atlas renders fully; it just won't show the noise-floor gate.
