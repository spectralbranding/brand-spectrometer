#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = ["pyyaml>=6.0", "numpy>=2.0"]
# ///
"""Aggregate per-artifact REFLECTIONS into a source-clustered atlas with COMPUTED CIs.

Reads the reflections produced by reflect.py (reflections/<cohort>/<op>/<artifact>.yaml) and
computes, deterministically and with no network, a cohort estimate that is honest
about SIGNAL-SOURCE independence.

SIGNAL-SOURCE CLUSTERING (coexists with "SBT measures cohorts, not individuals")
-------------------------------------------------------------------------------
A cohort estimate aggregates SIGNALS (reflections), and signals have SOURCES. If one
source emits several artifacts, a flat mean over reflections over-weights it and falsely
narrows the cohort's uncertainty (pseudo-replication). We therefore aggregate
HIERARCHICALLY: reflection -> source (mean within a source) -> cohort (mean over
distinct sources), and we cluster-bootstrap over SOURCES, not reflections.

This does NOT track or profile individuals. The `source_id` is a pseudonymous
provenance key derived from PUBLIC metadata (verbatim outlet/venue, falling back
to URL host), used only inside this computation and not retained as an identity.
The unit of inference/output stays the cohort distribution; clustering is a
within-cohort estimator correction on the SOURCES of signal. SBT's stance --
never measure, report, or store an individual -- is preserved: we cluster sources
to estimate the cohort cloud without bias, we do not identify anyone.

COMPUTED QUANTITIES
-------------------
- cohort vector = mean over the cohort's distinct PRIMARY-operator sources;
- per-dimension ci_95 = cohort mean +/- t_{.975, n_sources-1} * SE over sources
  (the COMPUTED interval that replaces the LLM-emitted per-dimension band);
- operator floor = max over alt-operator pairs of cosine-distance between the
  primary source-mean and that operator's source-mean cohort vector;
- source floor (was "artifact floor") = full leave-one-out jackknife max over
  SOURCES (drop each source, recompute the cohort mean, largest cosine-distance);
- per-pair S/N = cohort distance / max endpoint operator floor;
- bootstrap CIs (seeded) for floors, distances, S/N via SOURCE cluster bootstrap,
  plus P(S/N > 1) / P(S/N > 2) -- the robustness of each resolution verdict.

Output: atlas_reflections.yaml + reflections/bootstrap_reflections_ci.json; prints a comparison
against the existing atlas.yaml. The existing atlas.yaml is left untouched.

Run:
    uv run --with pyyaml --with numpy python \
        research/brand-spectrometer/code/aggregate_reflections.py \
        --atlas research/brand-spectrometer/atlases/ferrari_luce_fresh_2606 \
        --draws 20000 --seed 20260621
"""

from __future__ import annotations

import argparse
import json
import re
from itertools import combinations
from pathlib import Path

import numpy as np
import yaml

DIMENSIONS = [
    "semiotic",
    "narrative",
    "ideological",
    "experiential",
    "social",
    "economic",
    "cultural",
    "temporal",
]
_T975 = {
    1: 12.706,
    2: 4.303,
    3: 3.182,
    4: 2.776,
    5: 2.571,
    6: 2.447,
    7: 2.365,
    8: 2.306,
    9: 2.262,
    10: 2.228,
    11: 2.201,
    12: 2.179,
    13: 2.160,
    14: 2.145,
    15: 2.131,
    16: 2.120,
    17: 2.110,
    18: 2.101,
    19: 2.093,
    20: 2.086,
}


def t975(df: int) -> float:
    if df <= 0:
        return float("nan")
    return _T975.get(df, 1.96 if df >= 30 else _T975[20])


def cosdist(a: np.ndarray, b: np.ndarray) -> float:
    n = float(np.linalg.norm(a) * np.linalg.norm(b))
    return 1.0 - (float(np.dot(a, b)) / n if n else 0.0)


def _vec(reflection: dict) -> np.ndarray:
    if reflection.get("vector"):
        return np.array([float(x) for x in reflection["vector"]], dtype=float)
    s = reflection["inferred_spec"]
    return np.array([float(s[d]["score"]) for d in DIMENSIONS], dtype=float)


def _host(reflection: dict) -> str:
    url = str(reflection.get("url") or "").strip()
    if url:
        return re.sub(r"^https?://(www\.)?", "", url).split("/")[0]
    return ""


def _manual_source(reflection: dict) -> str:
    """The analyst-/contract-supplied provenance label, if any.

    Held in a `source` (preferred) or legacy `outlet` field. Collection-mode
    dependent: for scraped artifacts it is the verbatim outlet/venue; for
    first-party panels/polls it is the unit of independent sampling
    (respondent-pseudonym, survey wave, panel vendor, locale instrument) -- a
    pseudonymous token, never an identity. Empty when not supplied.
    """
    for k in ("source", "outlet"):
        v = (reflection.get(k) or "").strip()
        if v:
            return v
    return ""


def _source_id(reflection: dict, grain: str = "source") -> str:
    """Pseudonymous provenance key from PUBLIC metadata (not an identity).

    Every reflection carries BOTH an automatic `url` and an optional manual `source`
    field; `grain` selects which one the cohort aggregation clusters by -- the
    unit treated as ONE source:
      - 'artifact'      : each reflection is its own source (finest; no clustering).
      - 'host'          : the URL host (objective, identical rule everywhere).
      - 'source'/'outlet': the MANUAL source field when supplied, else host,
                           else artifact (semantic grain; the canonical default).
    A consistent grain across windows is required for an apples-to-apples
    cross-window contrast -- see the two-window S/N comparison.
    """
    if grain == "artifact":
        return reflection.get("artifact_id", "unknown")
    if grain == "host":
        return _host(reflection) or reflection.get("artifact_id", "unknown")
    # source/outlet (default): manual label, then host, then artifact
    return (
        _manual_source(reflection)
        or _host(reflection)
        or reflection.get("artifact_id", "unknown")
    )


def load_reflections(atlas: Path, grain: str = "outlet") -> dict:
    """-> {cohort: {op: {artifact_id: {'vec':.., 'src':..}}}}"""
    root = atlas / "reflections"
    out: dict = {}
    for cdir in sorted(p for p in root.iterdir() if p.is_dir()):
        out[cdir.name] = {}
        for odir in sorted(p for p in cdir.iterdir() if p.is_dir()):
            d = {}
            for f in sorted(odir.glob("*.yaml")):
                reflection = yaml.safe_load(f.read_text())
                d[reflection["artifact_id"]] = {
                    "vec": _vec(reflection),
                    "src": _source_id(reflection, grain),
                }
            out[cdir.name][odir.name] = d
    return out


def source_mean(op_reflections: dict, ids: list) -> np.ndarray:
    """Hierarchical mean: reflection -> source -> cohort. ids restrict the artifacts."""
    by_src: dict = {}
    for a in ids:
        if a in op_reflections:
            by_src.setdefault(op_reflections[a]["src"], []).append(
                op_reflections[a]["vec"]
            )
    src_means = [np.mean(v, axis=0) for v in by_src.values()]
    return np.mean(src_means, axis=0)


def sources_of(op_reflections: dict, ids: list) -> list:
    seen = []
    for a in ids:
        s = op_reflections[a]["src"]
        if s not in seen:
            seen.append(s)
    return seen


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--atlas", required=True, type=Path)
    ap.add_argument("--draws", type=int, default=20000)
    ap.add_argument("--seed", type=int, default=20260621)
    ap.add_argument(
        "--grain",
        choices=["source", "outlet", "host", "artifact"],
        default="source",
        help="which field to cluster sources by: 'source'/'outlet' "
        "(manual field, host fallback; canonical default), "
        "'host' (URL host always), or 'artifact' (no "
        "clustering). Must match across windows for an "
        "apples-to-apples cross-window S/N contrast.",
    )
    args = ap.parse_args()
    rng = np.random.default_rng(args.seed)
    atlas, B, grain = args.atlas, args.draws, args.grain
    reflections = load_reflections(atlas, grain)
    cids = sorted(reflections.keys())

    cohort_vec, per_dim_ci, op_floor, src_floor = {}, {}, {}, {}
    art_ids, src_groups = {}, {}
    for c in cids:
        prim = reflections[c]["primary"]
        ids = sorted(prim.keys())
        art_ids[c] = ids
        # group primary reflections by source
        groups: dict = {}
        for a in ids:
            groups.setdefault(prim[a]["src"], []).append(a)
        src_groups[c] = groups
        src_keys = list(groups.keys())
        n_src = len(src_keys)
        # source-level vectors -> cohort mean
        src_vecs = np.array(
            [np.mean([prim[a]["vec"] for a in groups[s]], axis=0) for s in src_keys]
        )  # (n_src, 8)
        mean = src_vecs.mean(axis=0)
        cohort_vec[c] = mean
        sd = src_vecs.std(axis=0, ddof=1) if n_src > 1 else np.zeros(8)
        se = sd / np.sqrt(n_src)
        half = t975(n_src - 1) * se
        per_dim_ci[c] = {
            DIMENSIONS[i]: {
                "score": round(float(mean[i]), 3),
                "ci_95_lower": round(float(max(0.0, mean[i] - half[i])), 3),
                "ci_95_upper": round(float(min(10.0, mean[i] + half[i])), 3),
                "se": round(float(se[i]), 4),
                "n_reflections": len(ids),
                "n_sources": n_src,
            }
            for i in range(8)
        }
        # operator floor (alt source-means)
        alt_ds = []
        for op, oa in reflections[c].items():
            if op == "primary":
                continue
            aids = [a for a in ids if a in oa]
            if aids:
                alt_ds.append(cosdist(mean, source_mean(oa, aids)))
        op_floor[c] = round(max(alt_ds), 4) if alt_ds else None
        # source floor: LOO jackknife over SOURCES
        loo = []
        for drop in src_keys:
            keep = [a for a in ids if prim[a]["src"] != drop]
            if keep:
                loo.append(cosdist(mean, source_mean(prim, keep)))
        src_floor[c] = round(max(loo), 4) if loo else None

    pair_dist = {
        f"{a}|{b}": round(cosdist(cohort_vec[a], cohort_vec[b]), 4)
        for a, b in combinations(cids, 2)
    }
    pair_sn = {}
    for a, b in combinations(cids, 2):
        fl = max(op_floor[a], op_floor[b])
        pair_sn[f"{a}|{b}"] = round(pair_dist[f"{a}|{b}"] / fl, 4) if fl else None
    mean_pair = float(np.mean(list(pair_dist.values())))
    mean_opf = float(np.mean([op_floor[c] for c in cids if op_floor[c]]))
    agg_sn = round(mean_pair / mean_opf, 4) if mean_opf else None

    # ---- SOURCE cluster bootstrap ----
    boot_vec = {c: np.zeros((B, 8)) for c in cids}
    boot_opf = {c: np.zeros(B) for c in cids}
    boot_srcf = {c: np.zeros(B) for c in cids}
    for c in cids:
        prim = reflections[c]["primary"]
        src_keys = list(src_groups[c].keys())
        ns = len(src_keys)
        idx = rng.integers(0, ns, size=(B, ns))
        for bi in range(B):
            sampled_srcs = [src_keys[k] for k in idx[bi]]
            ids = [a for s in sampled_srcs for a in src_groups[c][s]]
            m = source_mean(prim, ids)
            boot_vec[c][bi] = m
            alt_ds = []
            for op, oa in reflections[c].items():
                if op == "primary":
                    continue
                sel = [a for a in ids if a in oa]
                if sel:
                    alt_ds.append(cosdist(m, source_mean(oa, sel)))
            boot_opf[c][bi] = max(alt_ds) if alt_ds else np.nan
            boot_srcf[c][bi] = cosdist(m, cohort_vec[c])

    def pct(x):
        x = x[~np.isnan(x)]
        lo, med, hi = np.percentile(x, [2.5, 50, 97.5])
        return {
            "lo": round(float(lo), 4),
            "median": round(float(med), 4),
            "hi": round(float(hi), 4),
        }

    boot = {
        "operator_floor": {c: pct(boot_opf[c]) for c in cids},
        "source_floor": {c: pct(boot_srcf[c]) for c in cids},
        "pair_signal_to_noise": {},
        "pair_verdict_robustness": {},
    }
    for a, b in combinations(cids, 2):
        d = np.array([cosdist(boot_vec[a][bi], boot_vec[b][bi]) for bi in range(B)])
        fl = np.maximum(boot_opf[a], boot_opf[b])
        sn = np.divide(d, fl, out=np.full_like(d, np.nan), where=fl > 0)
        key = f"{a}|{b}"
        boot["pair_signal_to_noise"][key] = pct(sn)
        valid = sn[~np.isnan(sn)]
        boot["pair_verdict_robustness"][key] = {
            "p_gt_1": round(float(np.mean(valid > 1.0)), 4),
            "p_gt_2": round(float(np.mean(valid > 2.0)), 4),
        }
    mp = np.array(
        [
            np.mean(
                [
                    cosdist(boot_vec[a][bi], boot_vec[b][bi])
                    for a, b in combinations(cids, 2)
                ]
            )
            for bi in range(B)
        ]
    )
    mof = np.nanmean(np.vstack([boot_opf[c] for c in cids]), axis=0)
    boot["aggregate_signal_to_noise"] = pct(
        np.divide(mp, mof, out=np.full_like(mp, np.nan), where=mof > 0)
    )

    result = {
        "atlas": atlas.name,
        "draws": B,
        "seed": args.seed,
        "grain": grain,
        "aggregation": "reflection -> source -> cohort (signal-source clustered; "
        f"source grain = {grain}; pseudonymous provenance, "
        "not an individual identity)",
        "n_reflections": {c: len(art_ids[c]) for c in cids},
        "n_sources": {c: len(src_groups[c]) for c in cids},
        "sources": {c: list(src_groups[c].keys()) for c in cids},
        "operators_per_cohort": {c: sorted(reflections[c].keys()) for c in cids},
        "cohort_vectors": {
            c: [round(float(x), 4) for x in cohort_vec[c]] for c in cids
        },
        "per_dimension_ci": per_dim_ci,
        "operator_floor": op_floor,
        "source_floor": src_floor,
        "pair_distance": pair_dist,
        "pair_signal_to_noise": pair_sn,
        "aggregate_signal_to_noise": agg_sn,
        "bootstrap": boot,
    }
    # canonical manual-source grain writes the canonical filenames; other grains
    # are suffixed so the investigation does not clobber the canonical results.
    sfx = "" if grain in ("source", "outlet") else f"_{grain}"
    (atlas / "reflections" / f"bootstrap_reflections_ci{sfx}.json").write_text(
        json.dumps(result, indent=2) + "\n"
    )
    (atlas / f"atlas_reflections{sfx}.yaml").write_text(
        yaml.safe_dump(result, sort_keys=False, allow_unicode=True)
    )

    old = yaml.safe_load((atlas / "atlas.yaml").read_text())
    osens = old.get("variance", {}).get("operator_sensitivity", {})
    print(
        f"\n=== {atlas.name}: SOURCE-CLUSTERED REFLECTION atlas (grain={grain}) vs OLD ==="
    )
    print(
        "n_reflections / n_sources:",
        {c: f"{len(art_ids[c])}/{len(src_groups[c])}" for c in cids},
    )
    print(
        f"aggregate S/N: old={old.get('variance', {}).get('operator_sensitivity_summary', {}).get('signal_to_noise_ratio')} "
        f"reflection={agg_sn}  bootCI {boot['aggregate_signal_to_noise']}"
    )
    print("operator floor (old -> reflection, bootCI):")
    for c in cids:
        print(
            f"  {c:18s} {osens.get(c, {}).get('max_alt_distance')} -> {op_floor[c]}  {boot['operator_floor'][c]}"
        )
    print("per-pair S/N (reflection | bootCI | P>1 P>2):")
    for k in sorted(pair_sn, key=lambda k: (pair_sn[k] is None, pair_sn[k])):
        r = boot["pair_verdict_robustness"][k]
        print(
            f"  {k:40s} {pair_sn[k]}  {boot['pair_signal_to_noise'][k]}  P>1={r['p_gt_1']} P>2={r['p_gt_2']}"
        )


if __name__ == "__main__":
    main()
