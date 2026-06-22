#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = ["pyyaml>=6.0", "numpy>=2.0"]
# ///
"""V1 test-retest reliability from the reflection retest repeats (offline).

reflect.py --retest K re-renders+extracts each primary artifact K times into
reflections_retest/<cohort>/rep_<k>/<aid>.yaml. This tool reads those repeats and
reports, per cohort, the mean within-artifact test-retest cosine distance against
the cohort's operator floor (from bootstrap_reflections_ci_<grain>.json). A cohort
passes when its mean test-retest distance is at or below its operator floor: the
instrument returns the same answer to the same input well inside its own operator
noise. Reflection-consistent counterpart of the legacy whole-cohort V1 arm.

Within-artifact distance = mean over reps of cosine distance(rep_vector,
rep_mean_vector); cohort distance = mean over the cohort's artifacts. No network.

Run:
    uv run --with pyyaml --with numpy python \
        research/brand-spectrometer/code/retest_reliability.py \
        --atlas research/brand-spectrometer/atlases/ferrari_luce_fresh_2606 \
        --grain host
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import yaml

from aggregate_reflections import DIMENSIONS, cosdist, _source_id  # noqa


def _vec(reflection: dict) -> np.ndarray:
    if reflection.get("vector"):
        return np.array([float(x) for x in reflection["vector"]], dtype=float)
    s = reflection["inferred_spec"]
    return np.array([float(s[d]["score"]) for d in DIMENSIONS], dtype=float)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--atlas", required=True, type=Path)
    ap.add_argument("--grain", default="host")
    args = ap.parse_args()
    root = args.atlas / "reflections_retest"
    if not root.exists():
        raise SystemExit(f"no retest reflections at {root} (run reflect.py --retest K)")
    floors = json.load(
        (
            args.atlas / "reflections" / f"bootstrap_reflections_ci_{args.grain}.json"
        ).open()
    )["operator_floor"]

    rng = np.random.default_rng(20260621)

    def cohort_vec(members: dict) -> np.ndarray:
        """Aggregate reflection -> source -> cohort. members: {aid: {'vec','src'}}."""
        by_src: dict = {}
        for rec in members.values():
            by_src.setdefault(rec["src"], []).append(rec["vec"])
        src_means = [np.mean(v, axis=0) for v in by_src.values()]
        return np.mean(src_means, axis=0)

    out_cohorts = {}
    for cdir in sorted(p for p in root.iterdir() if p.is_dir()):
        cohort = cdir.name
        floor = floors.get(cohort)
        floor_r = round(floor, 5) if floor is not None else None
        # rep index k -> {aid: {'vec','src'}} ; and aid -> [{'vec','src'}, ...]
        by_rep: dict[int, dict] = {}
        by_art: dict[str, list] = {}
        for rep_dir in sorted(cdir.glob("rep_*")):
            try:
                k = int(rep_dir.name.split("_")[1])
            except (IndexError, ValueError):
                continue
            for f in rep_dir.glob("*.yaml"):
                reflection = yaml.safe_load(f.read_text())
                rec = {
                    "vec": _vec(reflection),
                    "src": _source_id(reflection, args.grain),
                }
                by_rep.setdefault(k, {})[reflection["artifact_id"]] = rec
                by_art.setdefault(reflection["artifact_id"], []).append(rec)

        # PRIMARY method (aligned-replicates): each rep index k is a replicate cohort
        # vector; test-retest = max replicate distance from the across-replicate mean
        # (mirrors the floor's max-over-alternates). This is FAIR only when the rep
        # indices cover the SAME artifact set (complete K x all artifacts) — otherwise
        # cross-replicate distance conflates re-run noise with artifact-set differences.
        usable_reps = {k: set(m.keys()) for k, m in by_rep.items() if len(m) >= 3}
        all_arts = set(by_art.keys())
        complete = len(usable_reps) >= 2 and all(
            s == all_arts for s in usable_reps.values()
        )
        if complete:
            replicates = [cohort_vec(by_rep[k]) for k in sorted(usable_reps)]
            mean_vec = np.mean(replicates, axis=0)
            dists = [cosdist(v, mean_vec) for v in replicates]
            tr_max, tr_mean = float(np.max(dists)), float(np.mean(dists))
            out_cohorts[cohort] = {
                "method": "aligned-replicates",
                "test_retest_distance_max": round(tr_max, 5),
                "test_retest_distance_mean": round(tr_mean, 5),
                "operator_floor": floor_r,
                "n_replicates": len(replicates),
                "pass": bool(floor is not None and tr_max <= floor),
            }
            continue

        # FALLBACK (sparse cohort, scattered skips): bootstrap one rep per artifact.
        # Re-run variation comes from artifacts with >=2 reps; need >=3 of them for a
        # meaningful cohort test-retest. Single-rep artifacts contribute a fixed vec.
        multi = [a for a, recs in by_art.items() if len(recs) >= 2]
        members_all = {a: recs for a, recs in by_art.items() if recs}
        if len(multi) < 3:
            out_cohorts[cohort] = {
                "insufficient": f"{len(multi)} artifact(s) with >=2 reps "
                f"(need 3); aligned replicates={len(replicates)}",
                "operator_floor": floor_r,
            }
            continue
        B = 2000
        boot_vecs = []
        for _ in range(B):
            draw = {
                a: recs[rng.integers(0, len(recs))] for a, recs in members_all.items()
            }
            boot_vecs.append(cohort_vec(draw))
        mean_vec = np.mean(boot_vecs, axis=0)
        d = np.array([cosdist(v, mean_vec) for v in boot_vecs])
        tr_p95, tr_mean = float(np.percentile(d, 95)), float(np.mean(d))
        out_cohorts[cohort] = {
            "method": "bootstrap-sparse",
            "test_retest_distance_p95": round(tr_p95, 5),
            "test_retest_distance_mean": round(tr_mean, 5),
            "operator_floor": floor_r,
            "n_artifacts_total": len(members_all),
            "n_artifacts_multi_rep": len(multi),
            "bootstrap_draws": B,
            "seed": 20260621,
            # conservative: the 95th-percentile re-draw distance must clear the floor
            "pass": bool(floor is not None and tr_p95 <= floor),
        }

    scored = {c: r for c, r in out_cohorts.items() if "pass" in r}
    n_pass = sum(1 for r in scored.values() if r["pass"])
    out = {
        "atlas": args.atlas.name,
        "grain": args.grain,
        "metric": "cohort-level test-retest: each rep aggregated reflection->source->cohort "
        "into a replicate cohort vector, compared at the operator floor's "
        "aggregation level. PRIMARY (aligned-replicates): max replicate "
        "distance from the across-replicate mean (mirrors max-over-alternates). "
        "FALLBACK for sparse cohorts (bootstrap-sparse): bootstrap one rep per "
        "artifact (>=3 artifacts with >=2 reps), 95th-pct re-draw distance.",
        "criterion": "pass iff test-retest distance (aligned: max; sparse: 95th pct) "
        "<= operator floor",
        "per_cohort": out_cohorts,
        "pass_count": n_pass,
        "n_scored": len(scored),
        "pass": n_pass >= max(1, len(scored)),
    }
    (args.atlas / "reflections" / f"retest_reliability_{args.grain}.json").write_text(
        json.dumps(out, indent=2) + "\n"
    )
    print(f"\n=== {args.atlas.name} V1 test-retest (grain={args.grain}) ===")
    print(f"{'cohort':18s} tr(max/p95) tr_mean  op floor  method            pass")
    for c, r in out_cohorts.items():
        if "insufficient" in r:
            print(f"  {c:16s} {r['insufficient']} (floor {r['operator_floor']})")
            continue
        tr = r.get("test_retest_distance_max", r.get("test_retest_distance_p95"))
        print(
            f"  {c:16s} {tr:.5f}     {r['test_retest_distance_mean']:.5f}  "
            f"{r['operator_floor']:.5f}  {r['method']:17s} {r['pass']}"
        )
    print(
        f"PASS {n_pass}/{len(scored)} scored ({len(out_cohorts) - len(scored)} insufficient)"
    )


if __name__ == "__main__":
    main()
