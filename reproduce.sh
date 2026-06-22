#!/usr/bin/env bash
# =============================================================================
# reproduce.sh -- key-free offline reproduction of the Brand Spectrometer
#                 methods-paper (2026ax) headline numbers.
#
# RUN:
#   bash reproduce.sh
#
# REQUIREMENTS: only Python 3.12 + numpy + pyyaml (no API keys, no network).
#   - If `uv` is installed (https://docs.astral.sh/uv/) this script uses
#     `uv run --with numpy --with pyyaml` and needs nothing else.
#   - Otherwise install the two deps yourself: `pip install numpy pyyaml`
#     then set USE_UV=0 (e.g. `USE_UV=0 bash reproduce.sh`).
#
# WHAT IT DOES: replays the eight offline battery scripts in code/ against the
# bundled published fresh-window atlas (data/ferrari_luce_fresh_2606/), at the
# canonical grain=host and fixed seed=20260621, then prints the headline
# numbers. It regenerates the *_host.json outputs in the bundled data dir
# (deterministic -- re-running yields byte-identical results).
#
# EXPECTED KEY OUTPUTS (grain=host, seed=20260621):
#   - Distributional signal-to-noise, actual-owners vs non-italian-press: ~3.56
#     (cohort_separability_host.json -> distributional_sn)
#   - Aggregate mean-cosine signal-to-noise (current operator floor): ~0.82-0.86
#     (operator_tightness_host.json / resolution_scaling_host.json)
#   - Dimension attribution actual-owners vs pooled press: large Cohen's d on
#     semiotic / ideological / experiential, Holm-corrected permutation p < .05
#   - V2/V3/V5 reliability battery: pass (battery_from_reflections_host.json)
# =============================================================================
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CODE="$HERE/code"
ATLAS="$HERE/data/ferrari_luce_fresh_2606"
GRAIN="host"
SEED="20260621"

USE_UV="${USE_UV:-1}"
if [[ "$USE_UV" == "1" ]] && command -v uv >/dev/null 2>&1; then
  PY=(uv run --with numpy --with pyyaml python)
else
  PY=(python3)
fi

run() {
  echo ""
  echo ">>> $1"
  shift
  ( cd "$CODE" && "${PY[@]}" "$@" )
}

echo "============================================================"
echo " Brand Spectrometer -- offline reproduction"
echo " atlas: $ATLAS"
echo " grain: $GRAIN   seed: $SEED"
echo "============================================================"

# 1. Source-clustered aggregation -> bootstrap operator floors + atlas_reflections_host.yaml.
#    (Must run first: retest_reliability reads bootstrap_reflections_ci_host.json.)
run "aggregate_reflections (cohort cloud + bootstrap operator floor)" \
  aggregate_reflections.py --atlas "$ATLAS" --grain "$GRAIN" --seed "$SEED"

# 2. Cohort separability -> distributional S/N (the 3.56 headline) + permutation MMD + LOO.
run "cohort_separability (distributional S/N; the 3.56 owners-vs-press headline)" \
  cohort_separability.py --atlas "$ATLAS" --grain "$GRAIN" --seed "$SEED"

# 3. Dimension attribution -> which of the 8 dimensions separate owners from press.
run "dimension_attribution (per-dimension Cohen's d + Holm permutation p)" \
  dimension_attribution.py --atlas "$ATLAS" --grain "$GRAIN" --seed "$SEED"

# 4. Operator tightness -> aggregate mean-cosine S/N (the ~0.82-0.86 headline).
run "operator_tightness (aggregate mean-cosine S/N)" \
  operator_tightness.py --atlas "$ATLAS" --grain "$GRAIN"

# 5. Resolution scaling -> learning curve + n* sources for S/N>1.
run "resolution_scaling (resolution levers + learning curve)" \
  resolution_scaling.py --atlas "$ATLAS" --grain "$GRAIN" --seed "$SEED"

# 6. Controls calibration -> synthetic-perturbation calibration of the separability metric.
run "controls_calibration (synthetic-shift calibration)" \
  controls_calibration.py --atlas "$ATLAS" --grain "$GRAIN" --seed "$SEED"

# 7. Reliability battery (V2 cross-operator / V3 split-half / V5 reproducibility / V1 retest).
run "battery_from_reflections (V2/V3/V5 reliability battery)" \
  battery_from_reflections.py --atlas "$ATLAS" --grain "$GRAIN" --seed "$SEED"

# 8. Test-retest reliability (reads bootstrap_reflections_ci_host.json from step 1).
run "retest_reliability (V1 test-retest vs operator floor)" \
  retest_reliability.py --atlas "$ATLAS" --grain "$GRAIN"

echo ""
echo "============================================================"
echo " HEADLINE NUMBERS"
echo "============================================================"
"${PY[@]}" - "$ATLAS" <<'PYEOF'
import json, sys
from pathlib import Path
refl = Path(sys.argv[1]) / "reflections"

sep = json.loads((refl / "cohort_separability_host.json").read_text())
sn = sep.get("distributional_sn", {})
key = "actual-owners|non-italian-press"
print(f"Distributional S/N  actual-owners vs non-italian-press : {sn.get(key)}")
boot = sep.get("distributional_sn_bootstrap", {}).get(key, {})
if boot:
    print(f"   bootstrap median={boot.get('median')}  P(S/N>1)={boot.get('p_gt_1')}")

ot = json.loads((refl / "operator_tightness_host.json").read_text())
print(f"Aggregate mean-cosine S/N (operator floor)            : "
      f"{ot.get('aggregate_sn', {}).get('current_max_pairwise')}")

rs = json.loads((refl / "resolution_scaling_host.json").read_text())
print(f"Aggregate S/N (full sample, resolution_scaling)       : "
      f"{rs.get('resolution_levers', {}).get('aggregate_sn_full_sample')}")

da = json.loads((refl / "dimension_attribution_host.json").read_text())
fp = da.get("focal_vs_pooled_press", {})
print("Dimension attribution (actual-owners vs pooled press, Cohen's d / Holm p):")
for dim, v in fp.items():
    print(f"   {dim:13s} d={v.get('cohens_d'):>6}  perm_p_holm={v.get('perm_p_holm')}")

bat = json.loads((refl / "battery_from_reflections_host.json").read_text())
print("Reliability battery:")
print(f"   V2 cross-operator pass : {bat.get('V2_cross_operator', {}).get('pass')}")
print(f"   V3 split-half pass     : {bat.get('V3_split_half', {}).get('pass')}")
print(f"   V5 deterministic       : {bat.get('V5_reproducibility', {}).get('deterministic')}")
PYEOF

echo ""
echo "Done. Regenerated *_host.json live in: $ATLAS/reflections/"
