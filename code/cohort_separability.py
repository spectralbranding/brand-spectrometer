#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = ["pyyaml>=6.0", "numpy>=2.0"]
# ///
"""Are cohort reflection CLOUDS separable, even when their MEANS are not?

The cohort-mean cosine metric (metameric degree, per-pair S/N) collapses each
cohort's reflection cloud to a centroid before measuring separation. Averaging many
noisy per-artifact reflections pulls every centroid toward the global mean, shrinking
between-cohort separation -- so a mean-based metric can read "converged" even
when the underlying DISTRIBUTIONS differ. SBT treats a cohort as a perception
cloud (a distribution), not a point, so this asks the distribution-level
question the mean metric cannot: are the clouds separable above chance?

Units are SOURCE-level vectors (one vector per source = mean of that source's
primary reflections), so the test respects signal-source clustering and is not inflated
by pseudo-replication. For each cohort pair:

  - energy distance E between the two source-vector samples, with a permutation
    test over source labels (p = P(E_perm >= E_obs)); 9999 permutations, seeded.
  - leave-one-source-out nearest-centroid classification accuracy (chance .5):
    can we tell which cohort a held-out source belongs to?

Aggregate: between-cohort vs within-cohort variance ratio (eta^2) on source
vectors with a global label-permutation test -- the multivariate "do cohorts
explain reflection variance above chance" question.

This is a DIAGNOSTIC, not yet the instrument's metric: with ~5-8 sources per
cohort the distributional tests are low-powered, so a null here is weaker than a
null from the mean metric, and a positive must survive the permutation p.

Run:
    uv run --with pyyaml --with numpy python \
        research/brand-spectrometer/code/cohort_separability.py \
        --atlas research/brand-spectrometer/atlases/ferrari_luce_fresh_2606 \
        --grain host --perms 9999 --seed 20260621
"""

from __future__ import annotations

import argparse
import json
from itertools import combinations
from pathlib import Path

import numpy as np

from aggregate_reflections import load_reflections, source_mean  # noqa


def energy_distance(X: np.ndarray, Y: np.ndarray) -> float:
    def md(A, B):
        return float(np.mean(np.linalg.norm(A[:, None, :] - B[None, :, :], axis=2)))

    return 2 * md(X, Y) - md(X, X) - md(Y, Y)


def _median_heuristic(X: np.ndarray, Y: np.ndarray) -> float:
    """Median of pairwise Euclidean distances over the pooled sample -> RBF
    bandwidth (the standard median heuristic). Returns sigma; gamma = 1/(2 sigma^2)."""
    pool = np.vstack([X, Y])
    n = len(pool)
    if n < 2:
        return 1.0
    d = np.linalg.norm(pool[:, None, :] - pool[None, :, :], axis=2)
    iu = np.triu_indices(n, k=1)
    med = float(np.median(d[iu]))
    return med if med > 0 else 1.0


def mmd2(X: np.ndarray, Y: np.ndarray, sigma: float) -> float:
    """Unbiased squared MMD with an RBF kernel (median-heuristic bandwidth).

    A second, kernel-based distributional metric (independent of energy distance)
    so the resolution verdict can be shown robust across metrics, not an
    energy-distance artifact. Uses the unbiased U-statistic (diagonal excluded)."""
    g = 1.0 / (2.0 * sigma * sigma)

    def k(A, B):
        return np.exp(-g * np.linalg.norm(A[:, None, :] - B[None, :, :], axis=2) ** 2)

    m, n = len(X), len(Y)
    kxx, kyy, kxy = k(X, X), k(Y, Y), k(X, Y)
    # unbiased: drop the diagonal self-similarity terms
    sxx = (kxx.sum() - np.trace(kxx)) / (m * (m - 1)) if m > 1 else 0.0
    syy = (kyy.sum() - np.trace(kyy)) / (n * (n - 1)) if n > 1 else 0.0
    sxy = kxy.mean()
    return float(sxx + syy - 2 * sxy)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--atlas", required=True, type=Path)
    ap.add_argument(
        "--grain", choices=["source", "outlet", "host", "artifact"], default="host"
    )
    ap.add_argument("--perms", type=int, default=9999)
    ap.add_argument(
        "--draws",
        type=int,
        default=2000,
        help="source-cluster bootstrap draws for distributional S/N",
    )
    ap.add_argument("--seed", type=int, default=20260621)
    args = ap.parse_args()
    rng = np.random.default_rng(args.seed)
    reflections = load_reflections(args.atlas, args.grain)
    cids = sorted(reflections.keys())

    # source-level vectors per cohort, per operator (primary + alts).
    # src_vecs[c]   = primary source vectors (one per source)
    # op_src[c][op] = that operator's source vectors over the SAME sources
    src_vecs, op_src, src_groups = {}, {}, {}
    for c in cids:
        prim = reflections[c]["primary"]
        groups: dict = {}
        for a in sorted(prim.keys()):
            groups.setdefault(prim[a]["src"], []).append(a)
        src_groups[c] = groups
        src_vecs[c] = np.array([source_mean(prim, ids) for ids in groups.values()])
        op_src[c] = {}
        for op, oa in reflections[c].items():
            rows = []
            for ids in groups.values():
                sel = [x for x in ids if x in oa]
                if sel:
                    rows.append(source_mean(oa, sel))
            if rows:
                op_src[c][op] = np.array(rows)

    # ---- per-pair energy distance + MMD + permutation + LOO-source class. ----
    # Energy distance and kernel MMD share ONE permutation null (same shuffles)
    # so the two metrics are compared on identical resampling -- a metric ensemble
    # (#4), not two separate tests.
    pair = {}
    for a, b in combinations(cids, 2):
        X, Y = src_vecs[a], src_vecs[b]
        nX = len(X)
        e_obs = energy_distance(X, Y)
        sigma = _median_heuristic(X, Y)  # bandwidth fixed on the observed pool
        m_obs = mmd2(X, Y, sigma)
        pool = np.vstack([X, Y])
        ge_e, ge_m = 1, 1  # +1 (observed) for unbiased p
        for _ in range(args.perms):
            perm = rng.permutation(len(pool))
            px, py = pool[perm[:nX]], pool[perm[nX:]]
            if energy_distance(px, py) >= e_obs:
                ge_e += 1
            if mmd2(px, py, sigma) >= m_obs:
                ge_m += 1
        p = ge_e / (args.perms + 1)
        p_mmd = ge_m / (args.perms + 1)
        # LOO nearest-centroid accuracy
        correct = 0
        labels = [a] * nX + [b] * len(Y)
        for i in range(len(pool)):
            keep = np.array([j for j in range(len(pool)) if j != i])
            ca = pool[[j for j in keep if labels[j] == a]].mean(axis=0)
            cb = pool[[j for j in keep if labels[j] == b]].mean(axis=0)
            pred = (
                a if np.linalg.norm(pool[i] - ca) < np.linalg.norm(pool[i] - cb) else b
            )
            correct += int(pred == labels[i])
        # magnitude/shape decomposition (#7): split the centroid separation into a
        # MAGNITUDE component (difference of vector norms) and a SHAPE component
        # (cosine distance of the means). owners-vs-press is magnitude-driven.
        ma, mb = src_vecs[a].mean(axis=0), src_vecs[b].mean(axis=0)
        na, nb = float(np.linalg.norm(ma)), float(np.linalg.norm(mb))
        cos_d = 1.0 - float(np.dot(ma, mb) / (na * nb)) if na and nb else 0.0
        pair[f"{a}|{b}"] = {
            "energy_distance": round(e_obs, 4),
            "mmd2": round(m_obs, 6),
            "perm_p": round(p, 4),
            "perm_p_mmd": round(p_mmd, 4),
            "loo_source_accuracy": round(correct / len(pool), 4),
            "magnitude_norm_diff": round(abs(na - nb), 4),
            "shape_cosine_dist": round(cos_d, 4),
            "n_sources": [nX, len(Y)],
        }

    # ---- aggregate between/within (eta^2) + global permutation ----
    all_vecs = np.vstack([src_vecs[c] for c in cids])
    grand = all_vecs.mean(axis=0)
    sizes = {c: len(src_vecs[c]) for c in cids}
    labels = np.array([c for c in cids for _ in range(sizes[c])])

    def eta2(vecs, labs):
        gm = vecs.mean(axis=0)
        ss_tot = float(((vecs - gm) ** 2).sum())
        ss_bet = 0.0
        for c in set(labs):
            grp = vecs[labs == c]
            ss_bet += len(grp) * float(((grp.mean(axis=0) - gm) ** 2).sum())
        return ss_bet / ss_tot if ss_tot else 0.0

    eta_obs = eta2(all_vecs, labels)
    ge = 1
    for _ in range(args.perms):
        if eta2(all_vecs, rng.permutation(labels)) >= eta_obs:
            ge += 1
    eta_p = ge / (args.perms + 1)

    # ---- operator-floored DISTRIBUTIONAL S/N ----
    # distributional operator floor = how far swapping the operator moves the
    # WHOLE cohort cloud (energy distance primary-dist vs alt-dist over the same
    # sources), max over alt operators. The distributional analogue of O.
    op_dist_floor = {}
    for c in cids:
        P = op_src[c]["primary"]
        ds = [energy_distance(P, op_src[c][op]) for op in op_src[c] if op != "primary"]
        op_dist_floor[c] = max(ds) if ds else float("nan")
    dist_sn = {}
    for a, b in combinations(cids, 2):
        D = energy_distance(src_vecs[a], src_vecs[b])
        fl = max(op_dist_floor[a], op_dist_floor[b])
        dist_sn[f"{a}|{b}"] = round(D / fl, 4) if fl > 0 else None
    # source cluster bootstrap for CI + P(S/N>1)/P(>2)
    B = args.draws
    boot_sn = {f"{a}|{b}": [] for a, b in combinations(cids, 2)}
    for _ in range(B):
        boot_P, boot_floor = {}, {}
        for c in cids:
            keys = list(src_groups[c].keys())
            idx = rng.integers(0, len(keys), size=len(keys))
            chosen = [keys[i] for i in idx]
            prim = reflections[c]["primary"]
            boot_P[c] = np.array([source_mean(prim, src_groups[c][s]) for s in chosen])
            ds = []
            for op, oa in reflections[c].items():
                if op == "primary":
                    continue
                rows = []
                for s in chosen:
                    sel = [x for x in src_groups[c][s] if x in oa]
                    if sel:
                        rows.append(source_mean(oa, sel))
                if rows:
                    ds.append(energy_distance(boot_P[c], np.array(rows)))
            boot_floor[c] = max(ds) if ds else np.nan
        for a, b in combinations(cids, 2):
            fl = max(boot_floor[a], boot_floor[b])
            if fl and fl > 0 and not np.isnan(fl):
                boot_sn[f"{a}|{b}"].append(energy_distance(boot_P[a], boot_P[b]) / fl)
    dist_sn_ci = {}
    for k, arr in boot_sn.items():
        a = np.array(arr)
        if len(a):
            lo, med, hi = np.percentile(a, [2.5, 50, 97.5])
            dist_sn_ci[k] = {
                "lo": round(float(lo), 4),
                "median": round(float(med), 4),
                "hi": round(float(hi), 4),
                "p_gt_1": round(float(np.mean(a > 1)), 4),
                "p_gt_2": round(float(np.mean(a > 2)), 4),
            }

    # ---- multiple-comparison correction across the cohort pairs ----
    pair_keys = list(pair.keys())
    m = len(pair_keys)

    def holm_bh(raw_p):
        order = np.argsort(raw_p)
        holm = np.empty(m)
        running = 0.0
        for rank, i in enumerate(order):
            running = max(running, (m - rank) * raw_p[i])
            holm[i] = min(running, 1.0)
        bh = np.empty(m)
        prev = 1.0
        for rank in range(m - 1, -1, -1):
            i = order[rank]
            prev = min(prev, raw_p[i] * m / (rank + 1))
            bh[i] = min(prev, 1.0)
        return holm, bh

    holm, bh = holm_bh(np.array([pair[k]["perm_p"] for k in pair_keys]))
    holm_mmd, bh_mmd = holm_bh(np.array([pair[k]["perm_p_mmd"] for k in pair_keys]))
    for j, k in enumerate(pair_keys):
        pair[k]["perm_p_holm"] = round(float(holm[j]), 4)
        pair[k]["perm_p_bh"] = round(float(bh[j]), 4)
        pair[k]["perm_p_mmd_holm"] = round(float(holm_mmd[j]), 4)
        pair[k]["perm_p_mmd_bh"] = round(float(bh_mmd[j]), 4)

    # ---- triangulation resolution criterion (#3) ----
    # A pair is RESOLVED only when three independent tests agree:
    #   (1) Holm-corrected energy-distance permutation p < .05
    #   (2) operator-floored distributional S/N 95%-CI lower bound > 1
    #   (3) LOO nearest-centroid accuracy > chance (.5)
    # Conservative by construction; reviewer-proof. MMD agreement reported as a
    # robustness flag (metric ensemble) but NOT part of the gate.
    LOO_CHANCE = 0.5
    triangulation = {}
    for k in pair_keys:
        ci = dist_sn_ci.get(k, {})
        c1 = pair[k]["perm_p_holm"] < 0.05
        c2 = ci.get("lo") is not None and ci["lo"] > 1.0
        c3 = pair[k]["loo_source_accuracy"] > LOO_CHANCE
        resolved = bool(c1 and c2 and c3)
        triangulation[k] = {
            "resolved": resolved,
            "holm_p_lt_.05": bool(c1),
            "dist_sn_ci_lower_gt_1": bool(c2),
            "loo_gt_chance": bool(c3),
            "mmd_holm_p_lt_.05": bool(pair[k]["perm_p_mmd_holm"] < 0.05),
        }
        pair[k]["triangulation_resolved"] = resolved

    out = {
        "atlas": args.atlas.name,
        "grain": args.grain,
        "perms": args.perms,
        "seed": args.seed,
        "multiple_comparison": "Holm (FWER) + Benjamini-Hochberg (FDR) over "
        f"{m} cohort pairs (energy distance and MMD)",
        "metrics": ["energy_distance", "mmd2_rbf_median_heuristic"],
        "resolution_criterion": (
            "triangulated: RESOLVED iff Holm-corrected "
            "energy-distance perm p < .05 AND operator-floored "
            "distributional S/N 95%-CI lower > 1 AND LOO "
            "accuracy > .5 (chance)"
        ),
        "aggregate_separability": {
            "eta_squared": round(eta_obs, 4),
            "perm_p": round(eta_p, 4),
        },
        "operator_distributional_floor": {c: round(op_dist_floor[c], 4) for c in cids},
        "distributional_sn": dist_sn,
        "distributional_sn_bootstrap": dist_sn_ci,
        "triangulation": triangulation,
        "resolved_pairs": [k for k in pair_keys if triangulation[k]["resolved"]],
        "pairwise": pair,
        "note": (
            "source-level vectors (signal-source clustered); energy-distance "
            "+ kernel-MMD permutation + LOO nearest-centroid + magnitude/shape "
            "decomposition. Distribution-level complement to the mean-cosine "
            "S/N. Low-powered at this n; resolution verdict is triangulated."
        ),
    }
    (args.atlas / "reflections" / f"cohort_separability_{args.grain}.json").write_text(
        json.dumps(out, indent=2) + "\n"
    )
    print(f"\n=== {args.atlas.name} cohort separability (grain={args.grain}) ===")
    agg = out["aggregate_separability"]
    print(f"aggregate eta^2={agg['eta_squared']} perm_p={agg['perm_p']}")
    print(
        "per-pair (E-p Holm | MMD-p Holm | LOO | dist S/N [CI] P>1 | mag/shape | RESOLVED):"
    )
    for k in sorted(pair, key=lambda k: pair[k]["perm_p"]):
        x = pair[k]
        sn = dist_sn.get(k)
        ci = dist_sn_ci.get(k, {})
        flag = "  <== RESOLVED" if triangulation[k]["resolved"] else ""
        print(
            f"  {k:34s} E={x['perm_p']}/{x['perm_p_holm']} "
            f"MMD={x['perm_p_mmd']}/{x['perm_p_mmd_holm']} acc={x['loo_source_accuracy']} | "
            f"S/N={sn} [{ci.get('lo')},{ci.get('hi')}] P>1={ci.get('p_gt_1')} | "
            f"mag={x['magnitude_norm_diff']} shape={x['shape_cosine_dist']}{flag}"
        )
    print("RESOLVED pairs (triangulated):", out["resolved_pairs"] or "none")


if __name__ == "__main__":
    main()
