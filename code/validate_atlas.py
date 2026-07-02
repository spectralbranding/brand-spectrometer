# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "pyyaml>=6.0",
# ]
# ///
"""
validate_atlas.py — Brand Spectrometer schema v0.1 / v0.2 / v0.3 validator.

Run:
    uv run python validate_atlas.py <atlas.yaml>

Exit codes:
    0  on validation pass
    1  on validation failure (errors printed to stderr)
    2  on invocation error (missing file, malformed YAML)

Validation rules (per atlas_schema_v0.{1,2,3}.yaml end-of-file summaries).
A v0.1 atlas is checked under rules 1-11; a v0.2 atlas adds the
additive valence rules 12-15, which are gated on presence (an atlas with
no valence anywhere is checked under 1-11 even at schema_version 0.2);
a v0.3 atlas adds the additive model_epoch rules 16-18, gated the same
way (an atlas without a model_epoch block is unaffected):

    1.  schema_version in {"0.1", "0.2", "0.3"}
    2.  >= 5 cohorts under `cohorts`
    3.  each cohort references >= 3 artifact_ids
    4.  renderer_operator_id != extractor_operator_id per cohort
        (cross-operator discipline per 2026ap)
    5.  inferred_spec has all 8 SBT dimensions in canonical order,
        with score and 95% CI in [0, 10] and lower <= score <= upper
    6.  variance.cross_cohort_sigma has all 8 dimensions, sigma >= 0
    7.  variance.metameric_degree in [0, 1]
    8.  temporal_drift_window dates parse as ISO 8601
    9.  every artifact_id referenced from any cohort exists in
        provenance.artifact_inventory
    10. provenance.llm_call_manifest_path is non-empty
    11. each artifact source_type is in the allowed list
    12. (v0.2) a per-dimension `valence` block, when present, has value,
        ci_95_lower, ci_95_upper all in [-1, +1] with lower <= value <=
        upper, and spread >= 0
    13. (v0.2) if ANY valence is present, variance.valence_operator_floor
        is present — scalar float >= 0, or a map of all 8 SBT dimensions
        to floats >= 0
    14. (v0.2) a cohort carrying any valence MUST declare a non-empty
        valence_extractor_operator_id (advisory warning if it equals the
        strength extractor_operator_id — cross-family discipline)
    15. (v0.2) net contribution (score x valence) is NEVER stored: a
        `net_contribution` / `signed_score` key under any inferred_spec
        dimension is an error (derived projection only)
    16. (v0.3) a `model_epoch` block, when present, carries a non-empty
        epoch_id, an ISO 8601 epoch_date, a non-empty
        version_floor_source, and measured_under.renderers/extractors
        as non-empty lists of non-empty strings
    17. (v0.3) model_epoch.version_floor is a non-empty list whose
        entries carry a non-empty `ladder` and numeric mean/median
        >= 0; operator_floor_at_epoch, when present, carries numeric
        floats >= 0
    18. (v0.3) model_epoch.stale, when present, is a boolean

The validator is intentionally strict; the schema YAML is the
authoritative reference.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import yaml

SBT_DIMENSIONS: tuple[str, ...] = (
    "semiotic",
    "narrative",
    "ideological",
    "experiential",
    "social",
    "economic",
    "cultural",
    "temporal",
)

ALLOWED_SOURCE_TYPES: frozenset[str] = frozenset(
    {
        "forum_post",
        "press_article",
        "social_post",
        "auction_record",
        "video_review",
        "official_press_release",
        "opinion_column",
    }
)

MIN_COHORTS: int = 5
MIN_ARTIFACTS_PER_COHORT: int = 3
SUPPORTED_SCHEMA_VERSIONS: frozenset[str] = frozenset({"0.1", "0.2", "0.3"})

# Keys forbidden under an inferred_spec dimension: net contribution
# (score x valence) is a DERIVED projection, never a stored field
# (schema v0.2 rule 15; mirrors the signed-profile-8d explorable's
# "net contribution is a convenience, not a third axis").
FORBIDDEN_SPEC_DIM_KEYS: frozenset[str] = frozenset(
    {"net_contribution", "signed_score", "net_signed_contribution"}
)


class ValidationError(Exception):
    """Raised on any schema violation; carries an errors list."""

    def __init__(self, errors: list[str]) -> None:
        super().__init__(f"{len(errors)} validation error(s)")
        self.errors = errors


def _check_valence_block(
    cohort_id: str,
    dim: str,
    valence: object,
    errors: list[str],
) -> None:
    """Validate an OPTIONAL per-dimension valence block (schema v0.2 rule 12).

    value, ci_95_lower, ci_95_upper in [-1, +1] with lower <= value <=
    upper; spread >= 0. A null placeholder for any numeric field is
    permitted (skeleton-friendly, same as the score block).
    """
    if not isinstance(valence, dict):
        errors.append(
            f"cohort '{cohort_id}': inferred_spec.{dim}.valence must be a mapping"
        )
        return
    for key in ("value", "ci_95_lower", "ci_95_upper", "spread"):
        if key not in valence:
            errors.append(
                f"cohort '{cohort_id}': inferred_spec.{dim}.valence missing '{key}'"
            )
            return
    for key in ("value", "ci_95_lower", "ci_95_upper"):
        val = valence[key]
        if val is None:
            continue
        if not isinstance(val, (int, float)) or isinstance(val, bool):
            errors.append(
                f"cohort '{cohort_id}': inferred_spec.{dim}.valence.{key} must be "
                f"numeric (got {type(val).__name__})"
            )
            return
        if not (-1.0 <= float(val) <= 1.0):
            errors.append(
                f"cohort '{cohort_id}': inferred_spec.{dim}.valence.{key} = {val} "
                f"out of [-1, +1]"
            )
    spread = valence["spread"]
    if spread is not None:
        if not isinstance(spread, (int, float)) or isinstance(spread, bool):
            errors.append(
                f"cohort '{cohort_id}': inferred_spec.{dim}.valence.spread must "
                f"be numeric (got {type(spread).__name__})"
            )
        elif float(spread) < 0:
            errors.append(
                f"cohort '{cohort_id}': inferred_spec.{dim}.valence.spread = "
                f"{spread} must be >= 0"
            )
    lower = valence.get("ci_95_lower")
    value = valence.get("value")
    upper = valence.get("ci_95_upper")
    if all(
        isinstance(x, (int, float)) and not isinstance(x, bool)
        for x in (lower, value, upper)
    ):
        if not (float(lower) <= float(value) <= float(upper)):
            errors.append(
                f"cohort '{cohort_id}': inferred_spec.{dim}.valence ordering "
                f"violated (ci_95_lower <= value <= ci_95_upper required)"
            )


def _is_iso8601_date(value: object) -> bool:
    if not isinstance(value, (str, date)):
        return False
    if isinstance(value, date):
        return True
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def _check_score_block(
    cohort_id: str,
    dim: str,
    block: object,
    errors: list[str],
) -> bool:
    """Validate a single inferred_spec dimension block.

    Returns True when the block carries a (structurally present) valence
    block, so the caller can enforce the atlas-level v0.2 rules 13/14.
    """
    if not isinstance(block, dict):
        errors.append(f"cohort '{cohort_id}': inferred_spec.{dim} must be a mapping")
        return False
    # Rule 15 — net contribution is derived, never stored.
    for forbidden in FORBIDDEN_SPEC_DIM_KEYS:
        if forbidden in block:
            errors.append(
                f"cohort '{cohort_id}': inferred_spec.{dim}.{forbidden} is "
                f"forbidden — net contribution (score x valence) is a derived "
                f"projection, never a stored field"
            )
    for key in ("score", "ci_95_lower", "ci_95_upper"):
        if key not in block:
            errors.append(f"cohort '{cohort_id}': inferred_spec.{dim} missing '{key}'")
            return False
        val = block[key]
        if val is None:
            # null placeholder permitted in skeleton; treated as
            # "not-yet-populated" but does not error so that
            # skeletons remain schema-valid.
            continue
        if not isinstance(val, (int, float)) or isinstance(val, bool):
            errors.append(
                f"cohort '{cohort_id}': inferred_spec.{dim}.{key} must be "
                f"numeric (got {type(val).__name__})"
            )
            return False
        if not (0.0 <= float(val) <= 10.0):
            errors.append(
                f"cohort '{cohort_id}': inferred_spec.{dim}.{key} = {val} "
                f"out of [0, 10]"
            )
    lower = block.get("ci_95_lower")
    score = block.get("score")
    upper = block.get("ci_95_upper")
    if all(
        isinstance(x, (int, float)) and not isinstance(x, bool)
        for x in (lower, score, upper)
    ):
        if not (float(lower) <= float(score) <= float(upper)):
            errors.append(
                f"cohort '{cohort_id}': inferred_spec.{dim} ordering "
                f"violated (ci_95_lower <= score <= ci_95_upper required)"
            )

    # OPTIONAL valence block (schema v0.2 rule 12).
    if "valence" in block:
        _check_valence_block(cohort_id, dim, block["valence"], errors)
        return True
    return False


def _check_valence_operator_floor(floor: object, errors: list[str]) -> None:
    """Validate variance.valence_operator_floor (schema v0.2 rule 13).

    Accepts either a scalar float >= 0 (atlas-wide floor) or a map of all
    8 SBT dimensions to floats >= 0 (per-dimension floor).
    """
    if isinstance(floor, dict):
        for dim in SBT_DIMENSIONS:
            if dim not in floor:
                errors.append(
                    f"variance.valence_operator_floor (per-dimension form) "
                    f"missing '{dim}'"
                )
                continue
            val = floor[dim]
            if val is None:
                continue
            if not isinstance(val, (int, float)) or isinstance(val, bool):
                errors.append(f"variance.valence_operator_floor.{dim} must be numeric")
            elif float(val) < 0:
                errors.append(f"variance.valence_operator_floor.{dim} must be >= 0")
        return
    if isinstance(floor, (int, float)) and not isinstance(floor, bool):
        if float(floor) < 0:
            errors.append("variance.valence_operator_floor (scalar) must be >= 0")
        return
    errors.append(
        "variance.valence_operator_floor must be a float >= 0 or a map of all "
        "8 SBT dimensions to floats >= 0"
    )


def _check_model_epoch(block: object, errors: list[str]) -> None:
    """Validate an OPTIONAL top-level model_epoch block (v0.3 rules 16-18).

    Gated on presence: an atlas without the block is unaffected. Numeric
    null placeholders are permitted (skeleton-friendly, like the score
    block); structural fields (epoch_id, source, measured_under lists,
    ladder names) are not nullable — an epoch stamp without them is
    meaningless.
    """
    if not isinstance(block, dict):
        errors.append("`model_epoch` must be a mapping")
        return

    # Rule 16 — identity + source + measured_under.
    eid = block.get("epoch_id")
    if not isinstance(eid, str) or not eid:
        errors.append("model_epoch.epoch_id must be a non-empty string")
    if not _is_iso8601_date(block.get("epoch_date")):
        errors.append(
            f"model_epoch.epoch_date = {block.get('epoch_date')!r} "
            f"is not a valid ISO 8601 date"
        )
    src = block.get("version_floor_source")
    if not isinstance(src, str) or not src:
        errors.append("model_epoch.version_floor_source must be a non-empty string")
    mu = block.get("measured_under")
    if not isinstance(mu, dict):
        errors.append("model_epoch.measured_under must be a mapping")
    else:
        for role in ("renderers", "extractors"):
            lst = mu.get(role)
            if (
                not isinstance(lst, list)
                or not lst
                or not all(isinstance(s, str) and s for s in lst)
            ):
                errors.append(
                    f"model_epoch.measured_under.{role} must be a non-empty "
                    f"list of non-empty model-version strings"
                )

    # Rule 17 — version floor entries + optional operator floor copy.
    vf = block.get("version_floor")
    if not isinstance(vf, list) or not vf:
        errors.append("model_epoch.version_floor must be a non-empty list")
    else:
        for i, entry in enumerate(vf):
            if not isinstance(entry, dict):
                errors.append(f"model_epoch.version_floor[{i}] must be a mapping")
                continue
            ladder = entry.get("ladder")
            if not isinstance(ladder, str) or not ladder:
                errors.append(
                    f"model_epoch.version_floor[{i}].ladder must be a "
                    f"non-empty string"
                )
            for key in ("mean", "median"):
                val = entry.get(key)
                if val is None:
                    continue
                if not isinstance(val, (int, float)) or isinstance(val, bool):
                    errors.append(
                        f"model_epoch.version_floor[{i}].{key} must be numeric"
                    )
                elif float(val) < 0:
                    errors.append(f"model_epoch.version_floor[{i}].{key} must be >= 0")
    of = block.get("operator_floor_at_epoch")
    if of is not None:
        if not isinstance(of, dict):
            errors.append("model_epoch.operator_floor_at_epoch must be a mapping")
        else:
            for key, val in of.items():
                if val is None:
                    continue
                if not isinstance(val, (int, float)) or isinstance(val, bool):
                    errors.append(
                        f"model_epoch.operator_floor_at_epoch.{key} must be numeric"
                    )
                elif float(val) < 0:
                    errors.append(
                        f"model_epoch.operator_floor_at_epoch.{key} must be >= 0"
                    )

    # Rule 18 — stale flag is boolean when present.
    stale = block.get("stale")
    if stale is not None and not isinstance(stale, bool):
        errors.append("model_epoch.stale must be a boolean when present")


def validate(atlas: dict) -> None:
    """Validate the loaded atlas dict; raise ValidationError on failure."""
    errors: list[str] = []

    # v0.3 rules 16-18 — model_epoch block, gated on presence.
    if "model_epoch" in atlas:
        _check_model_epoch(atlas["model_epoch"], errors)

    # Tracks whether ANY cohort carried a valence block (gates v0.2
    # rules 13/14, which are skipped for valence-free atlases).
    atlas_has_valence: bool = False

    # Rule 1 — schema version
    sv = atlas.get("schema_version")
    if sv not in SUPPORTED_SCHEMA_VERSIONS:
        errors.append(
            f"schema_version must be one of "
            f"{sorted(SUPPORTED_SCHEMA_VERSIONS)} (got {sv!r})"
        )

    # Top-level structural presence
    cohorts = atlas.get("cohorts")
    if not isinstance(cohorts, dict):
        errors.append("`cohorts` must be a mapping of cohort_id -> record")
        raise ValidationError(errors)

    # Rule 2 — cohort count
    if len(cohorts) < MIN_COHORTS:
        errors.append(
            f"`cohorts` must contain >= {MIN_COHORTS} entries "
            f"(got {len(cohorts)}); single-cohort atlases are disallowed"
        )

    # Collect artifact_ids referenced for Rule 9
    referenced_artifact_ids: set[str] = set()

    # Per-cohort checks (Rules 3, 4, 5)
    for cohort_id, cohort in cohorts.items():
        if not isinstance(cohort, dict):
            errors.append(f"cohort '{cohort_id}': must be a mapping")
            continue

        # Rule 3 — artifact_subset_observed cardinality
        subset = cohort.get("artifact_subset_observed", [])
        if not isinstance(subset, list):
            errors.append(
                f"cohort '{cohort_id}': artifact_subset_observed must be a list"
            )
        else:
            if len(subset) < MIN_ARTIFACTS_PER_COHORT:
                errors.append(
                    f"cohort '{cohort_id}': artifact_subset_observed has "
                    f"{len(subset)} entries; minimum {MIN_ARTIFACTS_PER_COHORT} required"
                )
            for aid in subset:
                if isinstance(aid, str) and aid:
                    referenced_artifact_ids.add(aid)

        # Rule 4 — cross-operator discipline
        renderer = cohort.get("renderer_operator_id")
        extractor = cohort.get("extractor_operator_id")
        if not isinstance(renderer, str) or not renderer:
            errors.append(
                f"cohort '{cohort_id}': renderer_operator_id missing or empty"
            )
        if not isinstance(extractor, str) or not extractor:
            errors.append(
                f"cohort '{cohort_id}': extractor_operator_id missing or empty"
            )
        if isinstance(renderer, str) and isinstance(extractor, str):
            if renderer == extractor:
                errors.append(
                    f"cohort '{cohort_id}': renderer_operator_id and "
                    f"extractor_operator_id must differ (cross-operator "
                    f"discipline per 2026ap); both = '{renderer}'"
                )

        # Rule 5 — inferred_spec on all 8 dimensions in canonical order
        spec = cohort.get("inferred_spec")
        if not isinstance(spec, dict):
            errors.append(f"cohort '{cohort_id}': inferred_spec must be a mapping")
        else:
            spec_keys = list(spec.keys())
            if spec_keys != list(SBT_DIMENSIONS):
                # Order matters per HARD-LOCK; report both presence
                # and order.
                missing = [d for d in SBT_DIMENSIONS if d not in spec]
                extra = [d for d in spec_keys if d not in SBT_DIMENSIONS]
                if missing:
                    errors.append(
                        f"cohort '{cohort_id}': inferred_spec missing "
                        f"dimensions {missing}"
                    )
                if extra:
                    errors.append(
                        f"cohort '{cohort_id}': inferred_spec has unknown "
                        f"keys {extra}"
                    )
                if not missing and not extra:
                    errors.append(
                        f"cohort '{cohort_id}': inferred_spec dimension "
                        f"order must be {list(SBT_DIMENSIONS)} (got {spec_keys})"
                    )
            cohort_has_valence = False
            for dim in SBT_DIMENSIONS:
                if dim in spec:
                    if _check_score_block(cohort_id, dim, spec[dim], errors):
                        cohort_has_valence = True
            if cohort_has_valence:
                atlas_has_valence = True
                # Rule 14 — cross-family valence extractor required.
                vext = cohort.get("valence_extractor_operator_id")
                if not isinstance(vext, str) or not vext:
                    errors.append(
                        f"cohort '{cohort_id}': carries valence but "
                        f"valence_extractor_operator_id is missing or empty "
                        f"(cross-family discipline, schema v0.2 rule 14)"
                    )
                elif isinstance(extractor, str) and vext == extractor:
                    # Advisory: family membership is not machine-checkable,
                    # so an identical id is a warning, not a hard error.
                    print(
                        f"WARNING: cohort '{cohort_id}': "
                        f"valence_extractor_operator_id == extractor_operator_id "
                        f"('{vext}'); cross-family discipline expects distinct "
                        f"model families for strength vs valence extraction",
                        file=sys.stderr,
                    )

    # Variance block (Rules 6, 7, 8)
    variance = atlas.get("variance")
    if not isinstance(variance, dict):
        errors.append("`variance` must be a mapping")
    else:
        sigma = variance.get("cross_cohort_sigma")
        if not isinstance(sigma, dict):
            errors.append("variance.cross_cohort_sigma must be a mapping")
        else:
            for dim in SBT_DIMENSIONS:
                if dim not in sigma:
                    errors.append(f"variance.cross_cohort_sigma missing '{dim}'")
                    continue
                val = sigma[dim]
                if val is None:
                    continue
                if not isinstance(val, (int, float)) or isinstance(val, bool):
                    errors.append(f"variance.cross_cohort_sigma.{dim} must be numeric")
                elif float(val) < 0:
                    errors.append(f"variance.cross_cohort_sigma.{dim} must be >= 0")

        md = variance.get("metameric_degree")
        if md is not None:
            if not isinstance(md, (int, float)) or isinstance(md, bool):
                errors.append("variance.metameric_degree must be numeric")
            elif not (0.0 <= float(md) <= 1.0):
                errors.append(f"variance.metameric_degree = {md} out of [0, 1]")

        # Rule 13 — valence operator floor required iff any valence present.
        floor = variance.get("valence_operator_floor")
        if atlas_has_valence:
            if floor is None:
                errors.append(
                    "variance.valence_operator_floor is required when any "
                    "cohort carries a valence block (schema v0.2 rule 13)"
                )
            else:
                _check_valence_operator_floor(floor, errors)
        elif floor is not None:
            # Floor present without any valence — validate it anyway so a
            # mis-keyed floor does not pass silently.
            _check_valence_operator_floor(floor, errors)

        tdw = variance.get("temporal_drift_window")
        if not isinstance(tdw, dict):
            errors.append("variance.temporal_drift_window must be a mapping")
        else:
            for key in ("start", "end"):
                if key not in tdw:
                    errors.append(f"variance.temporal_drift_window missing '{key}'")
                elif not _is_iso8601_date(tdw[key]):
                    errors.append(
                        f"variance.temporal_drift_window.{key} = {tdw[key]!r} "
                        f"is not a valid ISO 8601 date"
                    )

    # Provenance block (Rules 9, 10, 11)
    provenance = atlas.get("provenance")
    if not isinstance(provenance, dict):
        errors.append("`provenance` must be a mapping")
    else:
        inventory = provenance.get("artifact_inventory")
        if not isinstance(inventory, list):
            errors.append("provenance.artifact_inventory must be a list")
            inventory = []

        inventory_ids: set[str] = set()
        for i, art in enumerate(inventory):
            if not isinstance(art, dict):
                errors.append(f"provenance.artifact_inventory[{i}] must be a mapping")
                continue
            aid = art.get("artifact_id")
            if isinstance(aid, str) and aid:
                inventory_ids.add(aid)
            else:
                errors.append(f"provenance.artifact_inventory[{i}] missing artifact_id")
            st = art.get("source_type")
            if st is not None and st not in ALLOWED_SOURCE_TYPES:
                errors.append(
                    f"provenance.artifact_inventory[{i}] source_type "
                    f"'{st}' not in allowed list {sorted(ALLOWED_SOURCE_TYPES)}"
                )

        # Rule 9 — no dangling artifact_id refs
        # (Skip dangling-check when inventory is intentionally empty
        # and atlas is clearly a skeleton with no artifact refs yet.)
        if inventory_ids or referenced_artifact_ids:
            dangling = referenced_artifact_ids - inventory_ids
            if dangling:
                errors.append(
                    f"cohorts reference artifact_id(s) not present in "
                    f"provenance.artifact_inventory: {sorted(dangling)}"
                )

        # Rule 10 — llm_call_manifest_path non-empty
        mp = provenance.get("llm_call_manifest_path")
        if not isinstance(mp, str) or not mp:
            errors.append(
                "provenance.llm_call_manifest_path must be a non-empty string"
            )

    if errors:
        raise ValidationError(errors)


def _summary(atlas: dict) -> str:
    """Build a human-readable success summary."""
    lines: list[str] = []
    brand = atlas.get("brand_name", "<unknown>")
    av = atlas.get("atlas_version", "<unknown>")
    mv = atlas.get("methodology_version", "<unknown>")
    cohorts = atlas.get("cohorts", {}) or {}
    lines.append(f"Brand            : {brand}")
    lines.append(f"Atlas version    : {av}")
    lines.append(f"Methodology      : {mv}")
    lines.append(f"Cohort count     : {len(cohorts)}")
    me = atlas.get("model_epoch")
    if isinstance(me, dict):
        stale = me.get("stale")
        stale_note = " [version floor STALE]" if stale else ""
        lines.append(
            f"Model epoch      : {me.get('epoch_id')} "
            f"({me.get('epoch_date')}){stale_note}"
        )
    lines.append("")
    lines.append("Per-cohort summary:")
    lines.append(
        f"  {'cohort_id':<28} {'#dims':>6} {'#arts':>6}  "
        f"{'renderer':<26} {'extractor':<26}"
    )
    for cid, cohort in cohorts.items():
        spec = cohort.get("inferred_spec", {}) or {}
        n_dims = sum(
            1
            for d in SBT_DIMENSIONS
            if isinstance(spec.get(d), dict) and spec[d].get("score") is not None
        )
        n_arts = len(cohort.get("artifact_subset_observed", []) or [])
        renderer = cohort.get("renderer_operator_id", "")
        extractor = cohort.get("extractor_operator_id", "")
        lines.append(
            f"  {cid:<28} {n_dims:>6} {n_arts:>6}  " f"{renderer:<26} {extractor:<26}"
        )
    lines.append("")
    variance = atlas.get("variance", {}) or {}
    md = variance.get("metameric_degree")
    if md is not None:
        lines.append(f"metameric_degree : {md}")
    sigma = variance.get("cross_cohort_sigma", {}) or {}
    if sigma:
        sigma_summary = ", ".join(
            f"{d}={sigma.get(d)}" for d in SBT_DIMENSIONS if d in sigma
        )
        lines.append(f"cross_cohort_σ   : {sigma_summary}")
    tdw = variance.get("temporal_drift_window", {}) or {}
    if tdw:
        lines.append(f"drift window     : {tdw.get('start')} → {tdw.get('end')}")
    # Valence summary (v0.2).
    n_val_cohorts = sum(
        1
        for c in cohorts.values()
        if isinstance(c, dict)
        and isinstance(c.get("inferred_spec"), dict)
        and any(
            isinstance(c["inferred_spec"].get(d), dict)
            and "valence" in c["inferred_spec"][d]
            for d in SBT_DIMENSIONS
        )
    )
    if n_val_cohorts:
        vfloor = variance.get("valence_operator_floor")
        lines.append(f"cohorts w/ valence : {n_val_cohorts}/{len(cohorts)}")
        lines.append(f"valence_operator_floor : {vfloor}")
    pairs_ok = sum(
        1
        for c in cohorts.values()
        if isinstance(c, dict)
        and c.get("renderer_operator_id")
        and c.get("extractor_operator_id")
        and c.get("renderer_operator_id") != c.get("extractor_operator_id")
    )
    lines.append(f"cross-extractor pairs OK : {pairs_ok}/{len(cohorts)}")
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(
            "usage: uv run python validate_atlas.py <atlas.yaml>",
            file=sys.stderr,
        )
        return 2
    path = Path(argv[1])
    if not path.is_file():
        print(f"error: file not found: {path}", file=sys.stderr)
        return 2
    try:
        with path.open("r", encoding="utf-8") as f:
            atlas = yaml.safe_load(f)
    except yaml.YAMLError as e:
        print(f"error: malformed YAML: {e}", file=sys.stderr)
        return 2
    if not isinstance(atlas, dict):
        print("error: top-level document must be a mapping", file=sys.stderr)
        return 2

    try:
        validate(atlas)
    except ValidationError as e:
        print(f"VALIDATION FAILED ({len(e.errors)} error(s)):", file=sys.stderr)
        for err in e.errors:
            print(f"  - {err}", file=sys.stderr)
        return 1

    print("VALIDATION PASSED")
    print()
    print(_summary(atlas))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
