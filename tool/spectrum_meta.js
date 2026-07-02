/* Shared Brand Spectrometer settings — the single source of the detail-dial ladder,
 * the encoding-legend explainers, and the canonical eight dimensions. Loaded by BOTH
 * spectrometer.html (the tool) AND how-to-read.html (the teaching page) so their level
 * names, audience labels, captions, legend tooltips and dimension canon can never drift
 * apart (the renderer is already shared via spectrum_strip.js; this shares the DATA).
 *
 * Pages derive their own local shapes from this:
 *   - the tool uses levels 0–4 (LVL_NAMES / LVL_AUD / LVL_CAP = the n>=0 slice);
 *   - the guide uses the whole ladder incl. n=-1 "one number" prelude.
 * The caption is rendered by spectrum_strip.js, which prepends "This view: " itself.
 */
(function (root) {
  "use strict";

  // The detail-dial ladder. n is the level index the renderer understands; the tool
  // exposes 0..4, the guide adds the -1 "one number" origin as a teaching prelude.
  var levels = [
    { n: -1, name: "One number", audience: "the old way",
      caption: "one number — the average across every dimension and audience; it hides everything below. Turn the dial up" },
    { n: 0, name: "Headline", audience: "CEO / CMO",
      caption: "eight dimensions now — one consensus line each (mean across audiences); no spread, sentiment or noise floor yet" },
    { n: 1, name: "Compare", audience: "brand lead",
      caption: "audiences and their spread — scores only, no sentiment or noise floor yet (see the distance map below for what's real)" },
    { n: 2, name: "Sentiment", audience: "insights",
      caption: "now showing sentiment — height = strength, dot = valence; a hollow grey dot means below the noise floor (direction can’t be told); still no per-dimension uncertainty" },
    { n: 3, name: "Resolve", audience: "analyst",
      caption: "now showing per-dimension uncertainty (the 95% CI halo) — whether each gap is real is in the distance map below" },
    { n: 4, name: "Cloud", audience: "researcher",
      caption: "the full distribution — emission strength (line weight) and every signal source" }
  ];

  // Encoding-legend explainers (hover text under the chart). Interpret, don't just label.
  var legendTips = {
    band: "The shaded band spans the lowest to the highest cohort on this dimension — the size of the disagreement across audiences.",
    dot: "Strength (the line's height) is how loudly the dimension registers; valence is which way it leans. The dot slides left (hostile/negative) to right (favourable/positive). A high line with a left-sitting dot is the dangerous one: an audience that cares a lot, against you. A hollow grey dot pinned at centre means the valence is below its noise floor — sub-resolution, so the direction can't be told (the instrument abstains rather than fake a lean). Hover a solid dot for its net contribution (strength×valence) — a convenience read of how much that dimension pulls the cohort's overall lean, not a separate axis.",
    vsub: "A hollow, dashed grey dot at centre: this dimension's valence is below the operator noise floor. The instrument can't resolve which way the audience leans here, so it abstains — “can't tell” is a real answer, not a zero.",
    ci: "The faint band around each line is the 95% confidence interval — how precisely the instrument pins that score. Wider = less certain.",
    cloud: "At full detail valence is a distribution, not a point: the cloud is densest at the typical sentiment and stretches as sources disagree about how an audience feels.",
    emis: "Thicker line = the brand emits more strongly on that dimension for that cohort (more salient across its sources).",
    src: "Each faint dot is one signal source's reading — the raw spread the line summarizes."
  };

  // The canonical eight dimensions: label/desc/color keyed by dimension key. These are
  // HARDCODED here and override whatever an uploaded atlas supplies, so a BYO atlas need
  // only carry the keys (in any order) — users cannot substitute names, descriptions, or
  // colours. Order of the eight (Semiotic … Temporal) is the corpus-canonical order.
  var dims = {
    semiotic:    { label: "Semiotic",    desc: "signs, symbols, codes",     color: "#e64a3b" },
    narrative:   { label: "Narrative",   desc: "the story it tells",        color: "#e8842b" },
    ideological: { label: "Ideological", desc: "what it stands for",        color: "#e8c531" },
    experiential:{ label: "Experiential",desc: "what it feels like to use", color: "#7bc043" },
    social:      { label: "Social",      desc: "who you're seen as",        color: "#2fb3a8" },
    economic:    { label: "Economic",    desc: "value, price, worth",       color: "#3a8dde" },
    cultural:    { label: "Cultural",    desc: "its place in the world",    color: "#7a5cd0" },
    temporal:    { label: "Temporal",    desc: "heritage & momentum",       color: "#c44fa8" }
  };

  root.SPECTRUM_META = { levels: levels, legendTips: legendTips, dims: dims };
})(typeof window !== "undefined" ? window : this);
