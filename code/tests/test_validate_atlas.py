# /// script
# requires-python = ">=3.12"
# dependencies = ["pyyaml>=6.0"]
# ///
"""Tests for validate_atlas.py — schema v0.1 backward-compat + v0.2 valence rules.

Run:
    uv run python research/brand-spectrometer/code/tests/test_validate_atlas.py

Exit 0 if all assertions hold; 1 otherwise. No pytest dependency (the
brand-spectrometer code/ dir has no pytest harness) — this is a plain
assert-and-report runner.
"""

from __future__ import annotations

import sys
from pathlib import Path

# validate_atlas.py lives one directory up.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from validate_atlas import ValidationError, validate  # noqa: E402

SBT = (
    "semiotic",
    "narrative",
    "ideological",
    "experiential",
    "social",
    "economic",
    "cultural",
    "temporal",
)


def _score_block() -> dict:
    return {"score": 5.0, "ci_95_lower": 4.0, "ci_95_upper": 6.0}


def _valence_block() -> dict:
    return {
        "value": 0.3,
        "ci_95_lower": 0.1,
        "ci_95_upper": 0.5,
        "spread": 0.2,
    }


def _base_v01() -> dict:
    """Minimal valid 5-cohort v0.1 atlas (no valence)."""
    cohorts = {}
    for i in range(5):
        cid = f"cohort_{i}"
        cohorts[cid] = {
            "cohort_label": f"Cohort {i}",
            "artifact_subset_observed": ["art_1", "art_2", "art_3"],
            "inferred_spec": {dim: _score_block() for dim in SBT},
            "renderer_operator_id": "claude-opus-4-7",
            "extractor_operator_id": "gpt-4o-2024-11-20",
        }
    return {
        "schema_version": "0.1",
        "brand_name": "Test",
        "atlas_version": "0.1.0",
        "methodology_version": "0.1.0",
        "cohorts": cohorts,
        "variance": {
            "cross_cohort_sigma": {dim: 1.0 for dim in SBT},
            "metameric_degree": 0.3,
            "temporal_drift_window": {"start": "2025-01-01", "end": "2025-06-01"},
        },
        "provenance": {
            "artifact_inventory": [
                {"artifact_id": "art_1", "source_type": "forum_post"},
                {"artifact_id": "art_2", "source_type": "press_article"},
                {"artifact_id": "art_3", "source_type": "social_post"},
            ],
            "llm_call_manifest_path": "../logs/test_llm_calls.jsonl",
        },
    }


def _base_v02_with_valence() -> dict:
    """Valid v0.2 atlas: valence on every dimension + scalar floor."""
    atlas = _base_v01()
    atlas["schema_version"] = "0.2"
    atlas["atlas_version"] = "0.2.0"
    atlas["methodology_version"] = "0.2.0"
    for cid, cohort in atlas["cohorts"].items():
        cohort["valence_extractor_operator_id"] = "qwen3.7-max"
        for dim in SBT:
            cohort["inferred_spec"][dim]["valence"] = _valence_block()
    atlas["variance"]["valence_operator_floor"] = 0.15
    return atlas


def _model_epoch_block() -> dict:
    """Valid v0.3 model_epoch block (VE-1-shaped)."""
    return {
        "epoch_id": "VE-1",
        "epoch_date": "2026-07-02",
        "version_floor_source": "10.5281/zenodo.21128779",
        "measured_under": {
            "renderers": ["claude-opus-4-8", "gpt-5.5-2026-04-23"],
            "extractors": ["gpt-5.4-mini-2026-03-17"],
        },
        "version_floor": [
            {
                "ladder": "anthropic-opus",
                "metric": "cosine",
                "mean": 0.0124,
                "median": 0.0094,
            }
        ],
        "operator_floor_at_epoch": {"mean": 0.0078, "median": 0.0059},
        "stale": False,
    }


def _base_v03_with_epoch() -> dict:
    """Valid v0.3 atlas: v0.1 core + model_epoch block."""
    atlas = _base_v01()
    atlas["schema_version"] = "0.3"
    atlas["atlas_version"] = "0.3.0"
    atlas["methodology_version"] = "0.3.0"
    atlas["model_epoch"] = _model_epoch_block()
    return atlas


def expect_pass(name: str, atlas: dict, results: list) -> None:
    try:
        validate(atlas)
        results.append((name, True, ""))
    except ValidationError as e:
        results.append((name, False, f"unexpected failure: {e.errors}"))


def expect_fail(name: str, atlas: dict, results: list, needle: str = "") -> None:
    try:
        validate(atlas)
        results.append((name, False, "expected failure but validation passed"))
    except ValidationError as e:
        if needle and not any(needle in err for err in e.errors):
            results.append(
                (name, False, f"failed but no error contained {needle!r}: {e.errors}")
            )
        else:
            results.append((name, True, ""))


def main() -> int:
    results: list = []

    # Backward compatibility.
    expect_pass("v0.1 no valence", _base_v01(), results)

    v02 = _base_v02_with_valence()
    expect_pass("v0.2 valence all dims + scalar floor", v02, results)

    # v0.2 schema but no valence anywhere -> rules 13/14 skipped.
    v02_novalence = _base_v01()
    v02_novalence["schema_version"] = "0.2"
    expect_pass("v0.2 schema, no valence", v02_novalence, results)

    # Per-dimension floor form.
    v02_perdim = _base_v02_with_valence()
    v02_perdim["variance"]["valence_operator_floor"] = {dim: 0.1 for dim in SBT}
    expect_pass("v0.2 per-dimension floor", v02_perdim, results)

    # Partial valence (some dims only) still valid.
    v02_partial = _base_v02_with_valence()
    for cohort in v02_partial["cohorts"].values():
        for dim in ("narrative", "ideological", "experiential"):
            cohort["inferred_spec"][dim].pop("valence", None)
    expect_pass("v0.2 partial valence", v02_partial, results)

    # Rule 1 — unsupported version.
    bad_ver = _base_v01()
    bad_ver["schema_version"] = "0.4"
    expect_fail("rule 1 unsupported version", bad_ver, results, "schema_version")

    # Rule 12 — valence value out of [-1, +1].
    val_oor = _base_v02_with_valence()
    val_oor["cohorts"]["cohort_0"]["inferred_spec"]["semiotic"]["valence"][
        "value"
    ] = 1.5
    expect_fail("rule 12 valence out of range", val_oor, results, "out of [-1, +1]")

    # Rule 12 — valence CI ordering violated.
    val_ord = _base_v02_with_valence()
    val_ord["cohorts"]["cohort_0"]["inferred_spec"]["semiotic"]["valence"] = {
        "value": 0.3,
        "ci_95_lower": 0.5,
        "ci_95_upper": 0.1,
        "spread": 0.2,
    }
    expect_fail("rule 12 valence ordering", val_ord, results, "ordering")

    # Rule 12 — negative spread.
    val_spread = _base_v02_with_valence()
    val_spread["cohorts"]["cohort_0"]["inferred_spec"]["semiotic"]["valence"][
        "spread"
    ] = -0.1
    expect_fail("rule 12 negative spread", val_spread, results, "spread")

    # Rule 13 — valence present but floor missing.
    no_floor = _base_v02_with_valence()
    no_floor["variance"].pop("valence_operator_floor")
    expect_fail("rule 13 missing floor", no_floor, results, "valence_operator_floor")

    # Rule 13 — negative scalar floor.
    neg_floor = _base_v02_with_valence()
    neg_floor["variance"]["valence_operator_floor"] = -0.2
    expect_fail("rule 13 negative floor", neg_floor, results, ">= 0")

    # Rule 13 — per-dim floor missing a dimension.
    short_floor = _base_v02_with_valence()
    short_floor["variance"]["valence_operator_floor"] = {
        d: 0.1 for d in SBT if d != "temporal"
    }
    expect_fail("rule 13 per-dim floor short", short_floor, results, "temporal")

    # Rule 14 — valence present but no valence_extractor_operator_id.
    no_vext = _base_v02_with_valence()
    no_vext["cohorts"]["cohort_0"].pop("valence_extractor_operator_id")
    expect_fail(
        "rule 14 missing valence extractor", no_vext, results, "valence_extractor"
    )

    # Rule 15 — stored net_contribution forbidden.
    net = _base_v02_with_valence()
    net["cohorts"]["cohort_0"]["inferred_spec"]["semiotic"]["net_contribution"] = 1.5
    expect_fail("rule 15 stored net_contribution", net, results, "net_contribution")

    # --- v0.3 model_epoch rules (16-18, gated on presence) ---

    expect_pass("v0.3 epoch-stamped atlas", _base_v03_with_epoch(), results)

    # v0.3 schema without a model_epoch block -> rules 16-18 skipped.
    v03_noepoch = _base_v01()
    v03_noepoch["schema_version"] = "0.3"
    expect_pass("v0.3 schema, no model_epoch", v03_noepoch, results)

    # Older schema versions remain valid (backward compatibility).
    expect_pass(
        "v0.2 valence atlas unaffected by v0.3", _base_v02_with_valence(), results
    )

    # Rule 16 — empty epoch_id.
    bad_id = _base_v03_with_epoch()
    bad_id["model_epoch"]["epoch_id"] = ""
    expect_fail("rule 16 empty epoch_id", bad_id, results, "epoch_id")

    # Rule 16 — malformed epoch_date.
    bad_date = _base_v03_with_epoch()
    bad_date["model_epoch"]["epoch_date"] = "July 2026"
    expect_fail("rule 16 bad epoch_date", bad_date, results, "epoch_date")

    # Rule 16 — missing version_floor_source.
    no_src = _base_v03_with_epoch()
    no_src["model_epoch"].pop("version_floor_source")
    expect_fail("rule 16 missing source", no_src, results, "version_floor_source")

    # Rule 16 — empty measured_under.renderers.
    no_rend = _base_v03_with_epoch()
    no_rend["model_epoch"]["measured_under"]["renderers"] = []
    expect_fail("rule 16 empty renderers", no_rend, results, "renderers")

    # Rule 17 — empty version_floor list.
    no_vf = _base_v03_with_epoch()
    no_vf["model_epoch"]["version_floor"] = []
    expect_fail("rule 17 empty version_floor", no_vf, results, "version_floor")

    # Rule 17 — negative floor.
    neg_vf = _base_v03_with_epoch()
    neg_vf["model_epoch"]["version_floor"][0]["mean"] = -0.01
    expect_fail("rule 17 negative version_floor mean", neg_vf, results, ">= 0")

    # Rule 17 — missing ladder name.
    no_ladder = _base_v03_with_epoch()
    no_ladder["model_epoch"]["version_floor"][0].pop("ladder")
    expect_fail("rule 17 missing ladder", no_ladder, results, "ladder")

    # Rule 18 — non-boolean stale.
    bad_stale = _base_v03_with_epoch()
    bad_stale["model_epoch"]["stale"] = "yes"
    expect_fail("rule 18 non-boolean stale", bad_stale, results, "stale")

    # Report.
    ok = sum(1 for _, p, _ in results if p)
    for name, passed, msg in results:
        flag = "PASS" if passed else "FAIL"
        line = f"  [{flag}] {name}"
        if msg:
            line += f" — {msg}"
        print(line)
    print(f"\n{ok}/{len(results)} checks passed")
    return 0 if ok == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
