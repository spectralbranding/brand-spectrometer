# Methodology — Brand Spectrometer v0.1 / v0.2 / v0.3

*Companion to `schema/atlas_schema_v0.1.yaml` (v0.1), `schema/atlas_schema_v0.2.yaml` (v0.2, additive valence), and `schema/atlas_schema_v0.3.yaml` (v0.3, additive model epochs) and `SCHEMA_DESIGN_NOTES.md`. Methodology version: 0.3.0.*

*The strength-only protocol (a v0.1 atlas, scores without valence) is unchanged and remains valid; an atlas pinning `methodology_version: 0.2.0` additionally follows the valence extraction protocol (§3) and the valence noise floor (§5). Sections flagged "(v0.2 additive)" apply only to valence-bearing atlases.*

*Methodology 0.3.0 adds run-protocol verification equipment from the PRISM instrument family, none of which forks the reading instrument itself: the pre-flight operator concordance screen with the mechanical exclusion rule (§3, from Zharnikov 2026az), the pre-run version check plus epoch-stamped readings against a measured version floor (§3 and §6, from Zharnikov 2026ba). Sections flagged "(v0.3 additive)" apply to runs performed under methodology 0.3.0 and later; every published v0.1/v0.2 atlas remains valid as-is.*

## 0. Preamble and Ground-Truth-Absence Acknowledgment

This methodology does not assume that a platonic Tier-4 brand specification exists, and it does not attempt to recover one. It records cohort-indexed observer-side reconstructions of an implicit brand spec inferred by structural decomposition of publicly observable artifacts. Metameric variance across cohorts is the primary measurement, not noise around a true value. There is no ground truth against which a single "the brand spec" could be validated, and the protocol is built to make that absence operational rather than to hide it. A study that would collapse to a single point estimate is structurally disallowed by the multi-cohort sampling rule (§1) and structurally penalised by variance reporting (§5). The Brand Spectrometer is therefore a measurement instrument for Spectral Brand Theory metamerism (Zharnikov 2026v), not a verdict machine that pronounces what a brand "really is."

## 1. Multi-Cohort Sampling Protocol

### Cohort identification

A cohort is a distinguishable observer class with a distinct artifact-access pattern. Cohort-identification criteria, all of which must be satisfied:

- The class is publicly nameable in plain English (e.g., "actual Ferrari owners," "Italian press," "Mandarin-language car enthusiasts").
- Members of the class have a documented, distinct subset of publicly observable artifacts available to them (forum membership, language, geographic press market, commercial relationship).
- The class is operationally separable: artifacts retrievable for the class can be enumerated without circular reference to the brand spec that the atlas will infer.

### Cohort-class diversity rule

Where applicable to the brand under study, the cohort set should represent at least one cohort from each of: geographic / linguistic class, engagement-level class, commercial-relationship class, and discourse-register class. Diversity at the class level prevents the atlas from sampling five near-duplicate cohorts and reporting a falsely low metameric_degree.

### Cohort-size estimation

Each cohort's `cohort_size_estimate.value` is an integer population estimate with `cohort_size_estimate.source` naming the sampling-frame reference (forum-active-user count, magazine circulation, community-membership directory, etc.). Estimates need not be precise; they need to be sourced. Cohort-size estimates are reported alongside spec inferences but are not used to weight or rank cohorts: the atlas does not designate a "correct" cohort.

### Minimum and recommended cohort count

A minimum of five cohorts is enforced at the validator (`atlas_schema_v0.1.yaml` rule 2). Five is the floor at which the cross-cohort sigma and pairwise cosine-dissimilarity figures become statistically interpretable rather than dominated by single-pair variance. The recommended range is five to eight cohorts; beyond eight, marginal information per cohort drops while artifact-collection and operator-rotation cost rises. Studies with substantive reason to extend (e.g., multi-region launches with more than three relevant linguistic markets) may exceed eight but should document the rationale in the per-cohort `notes` field.

### Pre-registration

Cohort labels are declared and frozen before any artifact collection begins. Mid-study cohort additions are not permitted within an atlas version; they are handled by minting a new atlas_version (semver minor bump) so that pre- and post-expansion variance figures remain comparable. Pre-registration is recorded in the orchestrator's commit history and surfaced in the atlas YAML's `methodology_version` field.

## 2. Artifact-Inventory Protocol

### What counts as observable signal

Publicly accessible artifacts only: press articles, forum posts, official press releases, social posts, auction records, video reviews, and journalistic commentary on the brand. The controlled vocabulary for `source_type` is locked at the schema layer (`forum_post / press_article / social_post / auction_record / video_review / official_press_release`); extensions require a schema-version bump.

The following are out of scope as input artifacts: trademark assets (logos, wordmarks, monograms, trade dress, fonts, livery colors); confidential materials (leaked internal documents, NDA-bound briefings); private communications (DMs, private forum posts behind closed membership). Reproducing any of these is barred by §4 and by `TRADEMARK_NOTICE.md`.

### Selection-bias declaration

Each atlas declares, per cohort, in the `notes` field: what subset of cohort-accessible signal was sampled, what was systematically excluded, and why. This declaration is mandatory because what is reconstructed from observable signal is the cohort-visible rendering of the spec, not the spec itself; the rendering / spec gap is not measurable from artifacts alone (Weakness 2 in §7). Recording the sampling frame makes the rendering layer auditable.

### Minimum and recommended artifact count

A minimum of three artifacts per cohort is enforced at the validator (`atlas_schema_v0.1.yaml` rule 3). Three is the floor below which inferred-spec scores collapse onto a single source's idiom. The recommended range is five to ten artifacts per cohort; beyond ten, marginal information per artifact within a cohort drops sharply.

### Temporal window

The atlas-level `sample_date.start` / `sample_date.end` declare the retrieval window. Artifacts retrieved outside the window are excluded from the atlas; artifacts retrieved at the window edge are included with explicit retrieval-date provenance. Atlases spanning more than approximately six months must additionally report intra-window drift (§6).

### Provenance fields

Every artifact carries: `artifact_id` (unique within the atlas), `url` (public URL where retrieved), `retrieval_date` (ISO 8601), `source_type` (controlled vocabulary above), `observer_cohort_association` (cohort_id), `language` (ISO 639-1), `sha256` (of the retrieved artifact bytes, for tamper-evidence), and `archive_url_optional` (Wayback Machine or similar permanent-archive snapshot). The optional archive URL is strongly recommended for any artifact at risk of removal — social posts, forum threads, auction listings — because the atlas's reproducibility (§8) depends on the artifact remaining retrievable.

### Trademark guardrails

Per `TRADEMARK_NOTICE.md` and the §7 do/don't checklist in `TRADEMARK_RESEARCH_MEMO.md`:

- *Do not* reproduce any logo, wordmark, monogram, trade dress, livery color, font, or graphic brand asset in any atlas artifact, prompt file, log, or derived figure.
- *Do not* generate cohort prose that imitates the brand's first-person voice or reads as an unauthorised press release.
- *Do* prefix every inferred spec statement with hedging vocabulary ("inferred from observable artifacts," "as visible to cohort X," "consistent with the cohort's artifact subset").
- *Do* cite each public artifact by URL and retrieval date.
- *Do* limit any quoted passage to the length necessary for analytical purpose under nominative and descriptive fair-use doctrines.

These guardrails are protocol requirements, not stylistic suggestions. The TRADEMARK_NOTICE is reproduced in the public mirror root; the Phase 1.3 cohort sub-agents read it as required input before retrieving artifacts.

## 3. LLM Pipeline with Cross-Operator Discipline

### Three-operator pipeline

Each cohort is processed by three operator roles, where an *operator* is a model-version instance treated as a unit of provenance (per Zharnikov 2026ao, the operator role sits above the human-vs-AI instance distinction):

- *Operator A — orchestrator.* The research-protocol owner. Selects cohorts, drafts prompts, fixes seeds, runs the pipeline, and reviews outputs. Need not be the same identity across cohorts but must be recorded per cohort in the LLM-call manifest.
- *Operator B — renderer.* Reads the cohort's artifact subset plus the eight-SBT-dimension schema and produces rendered prose that names what the cohort can plausibly infer of the brand's Tier-4 spec from the artifacts visible to them. The renderer never sees a ground-truth spec; one does not exist.
- *Operator C — extractor.* Reads the renderer's rendered prose plus an extraction schema and emits structured per-dimension scores with 95% confidence intervals. The extractor never sees the source artifacts or the renderer's prompt.

### Cross-operator inequality (HARD RULE)

For each cohort, `renderer_operator_id != extractor_operator_id`. The atlas validator (`code/validate_atlas.py`) rejects any cohort where the two operator IDs match. This replicates the Zharnikov 2026ap Paper B cross-extractor discipline at the cohort level: within-model memory contamination on the rendered prose cannot inflate extracted scores when the extractor is a different model.

### Cross-FAMILY rotation pattern (non-Mandarin cohorts)

To bound within-family training-data co-bias, the renderer and extractor operators rotate across the Anthropic and OpenAI families across the four non-Mandarin cohorts. Within each cohort the renderer and extractor are drawn from different families; across cohorts the renderer-family alternates so that each family appears as renderer in some cohorts and extractor in others. The Ferrari skeleton (`examples/ferrari_luce_skeleton.yaml`) instantiates the rotation against the May 2026 SOTA tier:

- `brand-debaters`: renderer `claude-opus-4-7` (Anthropic, top-tier reasoning) / extractor `gpt-5.4-mini-2026-03-17` (OpenAI, structured-output extraction). Fallback extractor: `gpt-4o-mini-2024-07-18`.
- `actual-owners`: renderer `gpt-5.5-2026-04-23` (OpenAI, top-tier reasoning) / extractor `claude-haiku-4-5-20251001` (Anthropic, structured-output extraction). Fallback renderer: `gpt-4o-2024-11-20`.
- `italian-press`: renderer `claude-opus-4-7` / extractor `gpt-5.4-mini-2026-03-17` (Anthropic → OpenAI; same pairing as brand-debaters to enable a within-family rendering control comparison across cohorts).
- `non-italian-press`: renderer `gpt-5.5-2026-04-23` / extractor `claude-haiku-4-5-20251001` (OpenAI → Anthropic; rotated from italian-press to invert renderer-extractor role assignment across the cohort set).

The pattern combines (a) within-cohort cross-family separation, (b) across-cohort role reversal so each family carries both renderer and extractor load over the cohort set, and (c) renderer-tier reasoning paired with extractor-tier structured-output specialisation to reduce extractor cost without sacrificing JSON/YAML fidelity. Gemini was considered for a third-family cohort but dropped in May 2026 pending user re-evaluation; the two-family rotation across four cohorts still provides cross-family separation per cohort plus within-family control comparison.

### Native-language operator pattern (Mandarin cohort; HARD RULE)

The Mandarin-cohort renderer and extractor must both be native Chinese models — currently `qwen3.7-max` (Alibaba, via DashScope) as renderer and `deepseek-v4-flash` (DeepSeek) as extractor. Rationale: Western-trained LLMs exhibit measurable Mandarin-comprehension drift on car-press idiom, automotive marque framing, and Chinese-internet discourse register (Weibo / Bilibili / Autohome / Dongchedi). Routing Mandarin artifacts to Western-trained operators would conflate language-comprehension variance with spec-interpretation variance and inflate the Chinese cohort's apparent divergence from English-language cohorts on dimensions that are actually identical. Cross-operator inequality is preserved (Qwen-3 ≠ DeepSeek-V3). The Ferrari skeleton sets `renderer_operator_id: qwen3.7-max` and `extractor_operator_id: deepseek-v4-flash` for the `chinese-cohort` row. Fallbacks if the primary IDs are unavailable: renderer `qwen-max` (canonical DashScope alias), extractor `deepseek-v4-pro` (the legacy `deepseek-chat` / `deepseek-reasoner` aliases were RETIRED by DeepSeek — verified 2026-06-20, the `/models` endpoint now exposes only the v4 generation `deepseek-v4-flash` / `deepseek-v4-pro`; do not pin `deepseek-chat` in any new run).

Future extension: as native models for Russian, Arabic, Japanese, Korean, and other non-English markets mature, the same pattern applies — non-English cohorts route to native-language operator pairs while preserving cross-operator inequality.

### Model-version pinning

Operator IDs are exact model-version strings (e.g., `claude-opus-4-7`, `claude-haiku-4-5-20251001`, `gpt-5.5-2026-04-23`, `gpt-5.4-mini-2026-03-17`, `qwen3.7-max`, `deepseek-v4-flash`), never family labels alone. Pinning is required for reproducibility: a re-run six months later against a silently-updated model is a different experiment, and the manifest must allow that distinction to be detected.

### Pre-flight operator concordance (v0.3 additive)

Before any campaign, every configured operator reads the same small pilot stimulus set, and each operator's leave-one-out vector concordance (mean cosine distance between its reading and the mean of the other operators' readings, per stimulus) is scored. The mechanical exclusion rule, fixed ex ante by PRISM-M (Zharnikov 2026az, DOI 10.5281/zenodo.21125785) and replicated in three campaigns since: an operator whose discordance score exceeds 3x the median score of the remaining operators is excluded from every noise floor and every pooled vector, and retained only as a reported exploratory observer. The decision is mechanical — the rule is invoked, never judged case-by-case. Rationale: a single systematically discordant operator inflates every floor it enters and silently destroys the instrument's resolution; the pre-flight screen is the cheap check that prevents it. Run via `code/preflight.py concordance` (which invokes `prism_core.concordance`, the PRISM instrument-family base library — the same code path the PRISM campaigns use). Published atlases predating methodology 0.3.0 are unaffected; the rule applies to runs going forward.

### Pre-run version check (v0.3 additive)

Model-version pinning (above) makes a version change *detectable*; the version check makes it *actionable before spending*. Before a campaign, the configured operator model-version strings are compared against the versions the sealed-panel version floor was last measured under (`data/version_floor_manifest.json`, regenerated at each sealed-panel re-read; measurement source: PRISM-T, Zharnikov 2026ba, DOI 10.5281/zenodo.21128779). Any configured version absent from that manifest means the version floor is not current for this run: the run report must carry the line "version floor stale — re-read the sealed panel." The re-read itself is cheap (the sealed pinned panel is re-read under the new version; tens of dollars of API calls) and is triggered whenever a laddered model family ships a new version. Staleness never invalidates a reading — it gates ACROSS-EPOCH drift attribution only (§6). Run via `code/preflight.py version-floor`.

### LLM-call logging

All renderer, extractor, and orchestrator calls are logged via `llm_call_logger.py` (the fleet utility promoted Session 175). The logger writes a JSONL row per call with fields `log_format_version / phase / operation / operator / model_version / timestamp_utc / system_prompt / user_prompt / parameters / request_id / endpoint / sdk_version / response / response_metadata / tokens / latency_seconds / cost_usd_est / errors / retries / git_sha_caller / python_env_hash / human_in_loop / reconstructed_post_hoc` and applies API-key redaction at write time. Logs land at `<atlas-mirror>/logs/llm_calls.jsonl` per `PUBLIC_MIRROR_STANDARD.md`; the path is recorded in the atlas YAML's `provenance.llm_call_manifest_path` field. See §9 for a noted logger-extension dependency.

### Valence extraction protocol (v0.2 additive)

The strength score (operators B → C above) measures *how loudly* a dimension registers; it does not measure *which way it leans*. A valence-bearing atlas adds a fourth operator role that reads sign:

- *Operator D — valence extractor.* Reads the same renderer prose that operator C reads, plus a valence-extraction schema, and emits a per-dimension signed valence in [−1, +1] with a 95% CI — where −1 is uniformly hostile/negative, 0 is neutral, +1 is uniformly favourable/positive — together with a within-cohort `spread` (the dispersion of the per-reflection valence readings the cohort's artifacts produced). Like operator C, the valence extractor never sees the source artifacts or the renderer's prompt; it reads only the rendered prose. Valence is extracted **per reflection** (per renderer-prose unit) and **averaged per cohort**; `spread` is the standard deviation of those per-reflection valences before averaging.

*Cross-family discipline (HARD RULE).* The valence extractor (operator D) MUST be drawn from a different model family than the strength extractor (operator C) for the same cohort. The rationale is the same as the renderer ≠ extractor rule (§3 cross-operator inequality): a single family's training-data sentiment priors must not set both the strength and the sign of a dimension, or co-bias would masquerade as agreement. The atlas records operator D as `valence_extractor_operator_id` per cohort; the validator requires it to be present whenever a cohort carries valence (schema v0.2 rule 14) and warns when it equals `extractor_operator_id`. For the Mandarin cohort the cross-family pair is drawn from the native-model set (e.g. operator C `deepseek-v4-flash` → operator D `qwen3.7-max`, or the reverse), preserving the native-language pattern.

*Strength ⊥ valence (the orthogonality guard).* Valence is **not approval, and not a re-scaling of strength.** A dimension can register loudly (high score) and lean negative (valence below 0) at the same time — an audience that cares a great deal, against the brand. This high-strength / negative-valence cell is the most decision-relevant read the instrument produces and the one a single blended "brand score" destroys. The valence extractor is prompted to read sign independently of intensity; the extraction schema keeps the two channels separate, and no atlas field combines them (net contribution is derived only — §5, schema v0.2 rule 15).

*Prompt purity (extends §4).* The valence-extractor prompt is a separate file (`prompts/<cohort_id>_valence_extractor.md`), SHA-256 hashed and published like the renderer and extractor prompts. It MUST NOT name the source artifacts, the renderer identity, the strength scores already extracted, or any prior expectation about the sign — it reads the rendered prose and the valence schema alone, so it cannot anchor the sign to a strength reading it was shown.

## 4. Prompt-Purity Protocol

### Separate prompt files per operator role

Renderer prompts and extractor prompts live in separate files per cohort. File layout under `<atlas-mirror>/prompts/`:

```
prompts/<cohort_id>_renderer.md
prompts/<cohort_id>_extractor.md
```

A single combined prompt is not permitted. The separation is structural — it prevents accidental leakage of source-spine identifiers from the renderer's input context into the extractor's input context.

### Renderer prompt constraints

The renderer prompt MUST NOT embed or reference any ground-truth claim about the brand's actual Tier-4 spec ("Ferrari's brand spec is X"). The renderer reads only the cohort's artifact subset and the eight-SBT-dimension schema. The renderer infers; it does not transcribe.

### Extractor prompt constraints

The extractor prompt MUST NOT reference, embed, or hint at the source spine — that is, it must not name the cohort's artifact subset, the renderer's identity, or any prior expectation about the per-dimension scores. The extractor reads only the renderer's rendered prose and the extraction schema (eight dimensions; 0-10 float; 95% CI). This replicates the Paper B 2026ap discipline: the extractor must not be able to short-circuit the inference by recognising the source.

### Hashing and reproducibility

Every prompt file is SHA-256 hashed at experiment-run time; the hash is recorded in the LLM-call manifest under the `user_prompt` and `system_prompt` fields (the logger's redaction pass preserves the visible text; the hash provides tamper-evidence on the verbatim file).

### Publication

All prompt files are published in the public mirror at Zenodo upload per `feedback_publish_all_experiment_prompts.md`. The prompt files are part of the experimental apparatus, not auxiliary documentation: a reviewer must be able to inspect the exact prompt sent to each operator for each cohort.

## 5. Variance Reporting (Primary Output)

### Variance is the measurement

The atlas's primary output is the variance block, not a per-cohort point estimate. Each cohort's `inferred_spec` is a candidate reconstruction; reading any single cohort's eight-dimensional vector as "the brand spec" misuses the atlas. The variance block characterises how much the candidates diverge across cohorts and is what reviewers and downstream consumers should read first.

### What a dimension score measures (strength, not valence)

Each `inferred_spec` dimension score is a **strength** reading — the salience / intensity with which that perceptual dimension registers for the cohort, on a non-negative [0, 10] scale. It is **valence-agnostic**: a high score means the dimension is strongly present in the cohort's reconstruction, not that the cohort regards it positively. A strongly disliked attribute and a strongly admired one can both produce a high score on the same dimension; the score does not separate them.

The score measures dimensional **strength**; it does not encode **cloud-valence** — the positive / negative / ambivalent direction of the perception, an SBT construct owned by Zharnikov 2026a — nor **brand conviction**, the within-cohort polarisation of valence. In a strength-only **v0.1** atlas, direction-bearing signal appears only indirectly, as cross-cohort divergence (`cross_cohort_sigma`, `metameric_degree`); that is divergence in strength, not a per-dimension sign, and no field in a v0.1 atlas should be read as a valence.

A signed, valence-resolved reading is the **v0.2** additive extension: a per-dimension `valence` in [−1, +1] with its own 95% CI and within-cohort `spread`, carried as a first-class (optional) schema field alongside the strength score, extracted by a cross-family operator (§3 valence extraction protocol) and gated by its own noise floor (next subsection). The two channels stay orthogonal: strength on `score`, sign on `valence`. **Brand conviction** — the within-cohort polarisation of valence — is realised as the per-dimension `valence.spread` (a cohort split between admirers and detractors reads high spread, distinct from a cohort that is uniformly neutral at spread ≈ 0); cross-cohort valence divergence is the across-cohort face of the same construct. A v0.1 atlas remains valid and is simply read as strength-only.

### Valence noise floor (v0.2 additive)

The whole instrument rests on one discipline: **report a difference only when it clears a noise floor; below the floor, the honest reading is "can't tell," not a finding.** The strength channel already obeys this — every cross-cohort/cross-brand comparison carries an operator noise floor, and a gap beneath it is reported sub-resolution (§5 transparency item 2; §7 mitigations). Valence is held to the identical standard, and this floor — not the rendering — is the core of the v0.2 extension.

*How the floor is measured.* The valence operator floor is the **operator-heterogeneity wobble on the signed reading**: re-extract per-dimension valence with the valence extractor (operator D) **swapped** across the same operator alt-pairs already run for the strength floor, and take the dispersion of the extracted valence across those swaps as the floor. It is the direct valence analogue of the strength operator floor — same alt-pairs, same heterogeneity logic, applied to sign instead of magnitude. The figure is reported in `variance.valence_operator_floor`, either atlas-wide (a scalar) or per dimension (preferred, when the swap data supports a per-dimension estimate). A valence-bearing atlas without this floor fails validation (schema v0.2 rule 13).

*The resolved / sub-resolution rule (identical in form to strength).* A per-dimension valence is reportable as a **signed reading** only when its magnitude clears the floor: |`valence.value`| ≥ `valence_operator_floor` (for that dimension, in the per-dimension form). Below the floor the reading is **sub-resolution** — reported as "neutral / can't tell," never as a confident lean. The atlas MAY still *carry* a sub-resolution valence (it records what was extracted, with its CI and spread); a consuming surface MUST **gate** it — the spectrum strip greys the valence dot to neutral when it is sub-resolution, exactly as the cohort-distance map greys a sub-resolution distance (§5 distance matrix; the meter's distance-map gate). Presenting a sub-resolution valence as a finding is the failure the floor exists to prevent.

*Expected consequence, and why it is acceptable.* Valence inferred from public artifacts is noisier and more subjective than strength, so a substantial fraction of per-dimension valences will sit **below** their floor and read sub-resolution. That is the correct outcome, not a defect: a half-greyed Sentiment view that abstains where the sign is genuinely unresolved is more honest — and more useful — than an always-on dot that fakes a lean the artifacts do not support. Abstention under the floor is the instrument's whole ethic; the valence channel inherits it rather than carving out an exception. A dimension whose valence clears the floor *and* whose `spread` is high is reported as **polarised** (the brand-conviction signal — the cohort is split), distinct from a dimension at neutral valence with low spread (genuine indifference).

### Per-dimension cross-cohort sigma

`variance.cross_cohort_sigma` reports the sample standard deviation of the cohort score-vector for each of the eight SBT dimensions: *semiotic, narrative, ideological, experiential, social, economic, cultural, temporal* (canonical order, hard-locked at the schema layer). All eight values are required; the validator rejects atlases missing any dimension.

### Composite metameric_degree

`variance.metameric_degree = 1 − mean_pairwise_cosine_similarity` across the C(N, 2) unordered pairs of cohort eight-dimensional spec vectors. The full rationale is documented in `SCHEMA_DESIGN_NOTES.md §4`; the short version is that cosine on non-negative vectors in [0, 10]⁸ is bounded in [0, 1] (so `1 − cosine` is also bounded in [0, 1]), is scale-invariant on the dimensional pattern (separating shape divergence from magnitude divergence), and is well-understood in the SBT corpus (R0, R1, R2, R17, R21 all use cosine on observer-cohort vectors).

### Interpretation rubric

Categorical interpretation of metameric_degree is offered as guidance, not a hard cut-off:

- `metameric_degree < 0.10`: cohorts converge on similar dimensional emphasis; the brand spec is well-defined across the cohort set under study.
- `0.10 ≤ metameric_degree < 0.30`: moderate cohort divergence; some dimensions are stable across cohorts while others differ; report per-dimension sigmas to localise the divergence.
- `metameric_degree ≥ 0.30`: high cohort divergence; the cohort set sees substantively different specs; consistent with luxury / multi-cohort-intentional brand rendering (Weakness 6).

These thresholds will be revisited after Phase 1.3 worked-example experience.

### Per-cohort confidence intervals

The atlas never collapses to a single cohort-averaged spec. Each cohort retains its own 95% CIs on each dimension, and the atlas reports cohort-by-cohort, not in aggregate. Readers who require a single number for downstream use are directed to compute it themselves from the cohort-indexed atlas with their own weighting assumptions — the atlas does not provide weights because it cannot pre-specify what weighting is honest for an unknown downstream use.

### Where a dimension value comes from (transparency)

Each per-dimension value is a **model judgment, not a rubric score**: the extractor emits a 0–10 float per SBT dimension from the rendered prose alone (the eight dimensions are *defined*, but there is no verbal band-anchor that fixes what a given integer "means"). The method therefore does **not** claim a single value is objectively correct. Its trustworthiness rests on three published, re-runnable artifacts rather than on defending the point estimate:

1. **Provenance** — every renderer/extractor prompt is published and SHA-256 hashed, and every model call is logged to JSONL (operator, model version, prompts, parameters, response, tokens, latency, cost, git SHA). The exact computation behind any number is inspectable and reproducible.
2. **Uncertainty** — each value ships with a 95% CI, and each cross-cohort/cross-brand comparison ships with its operator and artifact **noise floors**; a gap below its floor is reported sub-resolution, not as a finding.
3. **Non-collapse** — the primary output is the variance block, not a point estimate; a single cohort's vector is a candidate reconstruction, never "the brand spec."

In short, the honesty is located in reproducibility + measured uncertainty + the refusal to over-claim a point value, not in a rubric anchor.

### Pairwise cohort-distance matrix

In addition to the composite metameric_degree, atlases report the full N × N pairwise cosine-dissimilarity matrix (off-diagonal entries only; diagonal is 0 by construction). The matrix surfaces which cohort pairs drive the composite figure: a moderate metameric_degree with one outlier cohort tells a different story than the same metameric_degree with uniform pairwise divergence.

## 6. Temporal Drift Handling

### Atlas as snapshot

Each atlas is a temporal snapshot with declared `variance.temporal_drift_window.start` and `variance.temporal_drift_window.end`. The window characterises the period over which the variance figures are valid; longer windows raise the question of whether the variance captures cohort-difference or time-drift.

### Cross-snapshot drift measurement

When two atlases exist for the same brand at different windows, drift is computed per dimension as `Δ_dim = score_dim(snapshot_T2) − score_dim(snapshot_T1)`, reported per cohort that appears in both snapshots. Drift is reported alongside cross-cohort variance, never smoothed across temporal snapshots: smoothing would conflate genuine spec evolution (a product launch, a leadership change, a campaign) with cohort sampling noise.

### Snapshot cadence

The recommended cadence is at least one atlas per major brand event — product launch, leadership change, public crisis, major campaign — plus a baseline cadence of one atlas every twelve months at minimum. Cadence richer than twelve months is encouraged when feasible; cadence sparser than twelve months risks aliasing across rapid-iteration brand cycles.

### Methodology versioning across drift

When two snapshots use different methodology versions, drift figures are reported only for dimensions where the methodology change does not materially affect the score (e.g., new artifact-source-type vocabulary on a cohort whose existing artifacts do not use the new type). Methodology changes that would materially affect scores invalidate cross-snapshot drift measurement until both snapshots are rebuilt under the same methodology version.

### Version epochs and the two-panel logic (v0.3 additive)

Cross-snapshot drift (above) assumes the instrument held still between snapshots. It does not hold still by default: the operators are model versions, and vendors ship new ones. Methodology 0.3.0 therefore distinguishes two panels and two floors (measurement source: PRISM-T, Zharnikov 2026ba):

- *The live panel* — the atlas itself: fresh artifacts, read at collection time. This is the measurement.
- *The sealed panel* — a frozen, byte-identical artifact set (SHA-256 manifest), re-read across model versions. It never enters an atlas; it exists solely to measure how much readings move when ONLY the model version changes. That movement is the *version floor* — the across-time counterpart of the within-epoch operator floor.

The nesting rule for longitudinal claims is **operator ⊆ version**: the operator floor is measured *within* a version epoch (contemporaneous operator pairs), so it cannot see version drift; the version floor brackets *across* epochs. A delta between two atlases taken at different epochs is attributable to the brand only if it clears BOTH floors — a delta above the operator floor but within the version floor may be instrument drift, not brand movement.

An atlas built under methodology 0.3.0 MAY carry the optional `model_epoch` block (schema v0.3): the epoch identifier and date, the exact model-version strings the sealed-panel floor was measured under, the per-ladder version floor at that epoch, and a `stale` flag from the pre-run version check (§3). Epoch-stamping is what lets a longitudinal consumer ask the right question of an across-epoch delta — "does this clear the version floor?" — instead of the too-weak "does this clear the operator floor?". The sealed-panel re-read procedure and its trigger (any laddered family ships a new version) are described in §3; existing v0.1/v0.2 atlases remain valid and simply carry no epoch stamp.

## 7. Limitations (Eight-Weakness Inventory)

This section quotes the eight-weakness inventory verbatim from `memory/project_tier_4_reverse_engineering_hype_and_tool_2026-05-29.md` lines 42-51. The inventory is the audit substrate: every claim made by an atlas built under this methodology must remain compatible with these eight named weaknesses. Each weakness is followed by a one-sentence mitigation note pointing to the relevant §1-§6 protocol element and a one-sentence residual-risk acknowledgment. The mitigations are partial; the residuals remain. Section preamble: NO ground truth is assumed to exist; the tool measures observer-side reconstructions; metameric variance IS the measurement.

### Verbatim weakness inventory

> 1. **Metamerism (fundamental)** — multiple distinct Tier-4 structures can produce identical observable signals. Tool sees signals; reverse-engineers a candidate; cannot distinguish from real Tier-4 if metameric. NO ground truth.
> 2. **Selection bias in observable artifacts** — tool sees only PUBLISHED signals, not implicit decisions. Brand owners curate the visible signal. Tool may reverse-engineer the rendering-spec, not the underlying spec.
> 3. **Temporal drift** — Tier-4 specs drift over time. Snapshot reverse-engineering captures a temporal point; different time windows yield different specs.
> 4. **Observer cohort variance** — different observers see different artifact subsets. Their reconstructed specs differ. Whose is "right"? All metameric per R15.
> 5. **LLM rendering homogenization** — tool likely uses LLMs. Jiang Artificial Hivemind contamination applies. Cross-extractor discipline (Paper B 2026ap) helps but doesn't solve.
> 6. **Brands' intentional multi-spec rendering** — luxury brands deliberately render multiple coherent specs to different cohorts. The "spec" is plural; tool may collapse this.
> 7. **Discourse contamination (Goodhart's law)** — if tool becomes popular, brands may optimize for the test. Tool becomes less informative over time.
> 8. **Cohort-purchase gap** — highly engaged "booers" (Ferrari Luce example) may reverse-engineer a different spec than actual buyers. Whose spec is "the brand"?

### Mitigations and residuals

*1. Metamerism.* Mitigation: §5 makes metameric_degree a required output, exposing rather than hiding the fundamental indeterminacy. Residual risk: high metameric_degree is informative about cohort divergence but does not falsify any candidate spec; no atlas claim can ever be "the Tier-4 spec."

*2. Selection bias in observable artifacts.* Mitigation: §2 mandates selection-bias declaration per cohort in the `notes` field plus controlled `source_type` vocabulary in `provenance.artifact_inventory`. Residual risk: what is reconstructed is the cohort-visible rendering of the spec, not the spec itself; the rendering / spec gap is not measurable from observable signals alone.

*3. Temporal drift.* Mitigation: §6 requires `temporal_drift_window` declaration and prohibits smoothing across snapshots. Residual risk: a single atlas is a snapshot and cannot characterise drift; drift requires at least two snapshots and resists pre-specified cadence rules.

*4. Observer cohort variance.* Mitigation: §1 minimum-five-cohort rule plus §5 cohort-indexed variance reporting make divergence the unit of measurement rather than a confound. Residual risk: no cohort is privileged; readers seeking a "correct" answer will not find one in the atlas.

*5. LLM rendering homogenization.* Mitigation: §3 cross-operator inequality (renderer ≠ extractor) plus cross-FAMILY rotation plus native-language operators on Mandarin bound but do not eliminate within-family training-data overlap. Residual risk: multi-family-extractor robustness checks are recommended in any atlas claiming low metameric_degree; cross-family contamination cannot be ruled out by within-atlas discipline alone.

*6. Brands' intentional multi-spec rendering.* Mitigation: §1 + §5 cohort-indexed structure is plural by construction — there is no atlas-level single inferred_spec. Residual risk: the atlas cannot distinguish "brand intentionally renders multiple coherent specs" from "the spec is ambiguous across observers"; both produce high metameric_degree.

*7. Discourse contamination (Goodhart's law).* Mitigation: §6 + atlas_version + methodology_version semver pinning preserve pre-optimisation baseline atlases for time-series comparison. Residual risk: the tool's own publication creates the contamination it warns against; older atlases retain value precisely because they pre-date optimisation.

*8. Cohort-purchase gap.* Mitigation: §1 cohort-class diversity rule mandates representing engagement-level and commercial-relationship classes; `cohort_size_estimate` records relative magnitudes. Residual risk: the atlas does not weight cohorts by purchase share; a high-volume low-purchase cohort appears at the same schema rank as a low-volume high-purchase cohort, and weighting is left to downstream consumers.

## 8. Reproducibility

### reproduce.sh orchestrator

A `reproduce.sh` orchestrator (Phase 1.4 deliverable, scoped here) re-runs an atlas end-to-end:

1. Re-fetches each artifact from `provenance.artifact_inventory.url`, verifying `sha256` against the recorded hash and falling back to `archive_url_optional` if the live URL has changed or been removed.
2. Re-runs the LLM pipeline for each cohort: renderer operator on artifacts → extractor operator on rendered prose → structured per-dimension scores with CIs.
3. Regenerates the atlas YAML, including recomputed `variance.cross_cohort_sigma` and `variance.metameric_degree`.
4. Runs `code/validate_atlas.py` against the regenerated atlas; the orchestrator exits non-zero on validation failure.

### Fixed-seed convention

Every LLM call records its `seed` parameter in the `parameters` field of the llm_call manifest. The orchestrator uses stable seeds across reproduction runs to maximise replicability under inherently non-deterministic API endpoints. Some providers do not honour seed parameters across model-version updates; in those cases the manifest's `model_version` field allows reviewers to detect that a reproduction ran against a different operator than the original.

### Public-mirror discipline

The atlas YAML, all prompt files, the llm_call manifest, and `TRADEMARK_NOTICE.md` are published in the public mirror at Zenodo upload per `PUBLIC_MIRROR_STANDARD.md`. Public-facing references to these artifacts cite them by GitHub URL, not by internal repo path, per `feedback_transparency_docs_must_be_public.md`. Internal-only artifacts (PENDING_UPDATES, session-completion docs, internal audit memos, the `TRADEMARK_RESEARCH_MEMO.md`) stay in the private working repository and are not mirrored.

## 9. Open Questions for Orchestrator Review

1. **Logger operator_role extension.** RESOLVED 2026-05-29: `llm_call_logger.py` v1.1 (commit `baabca20`) adds an `operator_role: str | None = None` field on `_CallLogger`, the `log_call()` + `log_call_post_hoc()` signatures, and the JSONL row schema. Valid values are `"renderer"`, `"extractor"`, `"orchestrator"`. Phase 1.3 cohort sub-agents pass the field explicitly; reproducibility audits can verify cross-operator discipline from the manifest alone via row-level `operator_role` filtering.

2. **Cross-cohort artifact-overlap rule.** RESOLVED 2026-05-29 per user direction: option (a) for storage + (b) for rendering — same artifact stored once in `provenance.artifact_inventory`, referenced by `artifact_id` from each cohort's `artifact_subset_observed` list; renderer is re-run per cohort against that cohort's slice of artifact IDs because each cohort reads the artifact through a different interpretive lens. Variance figures include the overlap by design; no separate include/exclude variant required.

3. **Versioning convention.** Three semvers coexist in the schema: `atlas_version` (this atlas-instance for this brand), `methodology_version` (this METHODOLOGY.md), and `schema_version` (atlas_schema YAML). The interaction rules need clarification: does a methodology-version bump force an atlas-version major bump for all derived atlases? Does a schema-version bump invalidate cross-snapshot drift comparison (per §6 last paragraph) by definition, or only when it changes scoring semantics? Recommend: write a short SEMVER_RULES section in `SCHEMA_DESIGN_NOTES.md` v0.2 covering all three.

---

*Methodology version 0.3.0 — 2026-07-02 (0.1.0 2026-05-29; 0.2.0 valence 2026-06-29; 0.3.0 pre-flight concordance + version epochs 2026-07-02). Companion to `schema/atlas_schema_v0.1.yaml` / `v0.2` / `v0.3`, `SCHEMA_DESIGN_NOTES.md`, `TRADEMARK_NOTICE.md`. Internal companion: `TRADEMARK_RESEARCH_MEMO.md` (not mirrored).*
