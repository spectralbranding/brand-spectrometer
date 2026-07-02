# /// script
# requires-python = ">=3.12"
# dependencies = ["numpy>=1.26", "pyyaml>=6.0"]
# ///
"""Tests for preflight.py — pre-flight concordance rule + pre-run version check.

Run:
    uv run python research/brand-spectrometer/code/tests/test_preflight.py

Plain assert-and-report runner, same convention as test_validate_atlas.py.
Exercises the two subcommands end-to-end through their cmd_* entry points
(temp files, no network, no LLM calls).
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

# preflight.py lives one directory up; it inserts research/ itself for
# prism_core.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from preflight import cmd_concordance, cmd_version_floor  # noqa: E402


def _concordant_readings() -> dict:
    """Three operators reading three stimuli near-identically."""
    base = [
        [8.0, 7.0, 6.0, 5.0, 4.0, 3.0, 2.0, 1.0],
        [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0],
        [5.0, 5.0, 5.0, 5.0, 5.0, 5.0, 5.0, 5.0],
    ]
    jitter = {"op_a": 0.0, "op_b": 0.05, "op_c": -0.05}
    return {op: [[x + d for x in vec] for vec in base] for op, d in jitter.items()}


def _discordant_readings() -> dict:
    """op_d systematically reads a different pattern on every stimulus."""
    readings = _concordant_readings()
    readings["op_d"] = [
        [1.0, 8.0, 1.0, 8.0, 1.0, 8.0, 1.0, 8.0],
        [8.0, 1.0, 8.0, 1.0, 8.0, 1.0, 8.0, 1.0],
        [9.0, 0.5, 9.0, 0.5, 9.0, 0.5, 9.0, 0.5],
    ]
    return readings


def _run_concordance(readings: dict, tmp: Path) -> tuple[int, dict]:
    readings_path = tmp / "readings.json"
    readings_path.write_text(json.dumps(readings))
    out_path = tmp / "verdict.json"
    args = argparse.Namespace(
        readings=str(readings_path), multiple=3.0, out=str(out_path)
    )
    rc = cmd_concordance(args)
    return rc, json.loads(out_path.read_text())


def _manifest(tmp: Path) -> Path:
    path = tmp / "version_floor_manifest.json"
    path.write_text(
        json.dumps(
            {
                "epoch": {"id": "VE-1", "date": "2026-07-02"},
                "source": {"doi": "10.5281/zenodo.21128779"},
                "measured_under": {
                    "renderers": ["claude-opus-4-8", "gpt-5.5-2026-04-23"],
                    "extractors": ["gpt-5.4-mini-2026-03-17"],
                },
            }
        )
    )
    return path


def main() -> int:
    results: list[tuple[str, bool, str]] = []

    def check(name: str, cond: bool, msg: str = "") -> None:
        results.append((name, cond, "" if cond else msg))

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)

        # Concordant pilot: no exclusions, exit 0.
        rc, verdict = _run_concordance(_concordant_readings(), tmp)
        check("concordant pilot exits 0", rc == 0, f"rc={rc}")
        check(
            "concordant pilot excludes nobody",
            verdict["excluded"] == [],
            str(verdict["excluded"]),
        )
        check(
            "concordant pilot keeps all",
            verdict["kept"] == ["op_a", "op_b", "op_c"],
            str(verdict["kept"]),
        )

        # Discordant operator: mechanically excluded, exit 1.
        rc, verdict = _run_concordance(_discordant_readings(), tmp)
        check("discordant pilot exits 1", rc == 1, f"rc={rc}")
        excluded_units = [e["unit"] for e in verdict["excluded"]]
        check(
            "op_d mechanically excluded",
            excluded_units == ["op_d"],
            str(excluded_units),
        )
        check(
            "concordant operators kept",
            verdict["kept"] == ["op_a", "op_b", "op_c"],
            str(verdict["kept"]),
        )

        # JSONL record input path.
        jsonl_path = tmp / "readings.jsonl"
        rows = []
        for op, vecs in _discordant_readings().items():
            for i, dims in enumerate(vecs):
                rows.append({"operator": op, "stimulus": f"s{i}", "dims": dims})
        jsonl_path.write_text("\n".join(json.dumps(r) for r in rows))
        rc = cmd_concordance(
            argparse.Namespace(readings=str(jsonl_path), multiple=3.0, out=None)
        )
        check("JSONL input path works (discordant -> 1)", rc == 1, f"rc={rc}")

        # Version check: all configured versions measured -> fresh, exit 0.
        manifest = _manifest(tmp)
        rc = cmd_version_floor(
            argparse.Namespace(
                operators="claude-opus-4-8,gpt-5.4-mini-2026-03-17",
                atlas=None,
                manifest=str(manifest),
            )
        )
        check("fresh versions exit 0", rc == 0, f"rc={rc}")

        # Version check: an unmeasured version -> stale, exit 1.
        rc = cmd_version_floor(
            argparse.Namespace(
                operators="claude-opus-4-9,gpt-5.4-mini-2026-03-17",
                atlas=None,
                manifest=str(manifest),
            )
        )
        check("unmeasured version exits 1 (stale)", rc == 1, f"rc={rc}")

        # Version check via atlas operator ids.
        atlas_path = tmp / "atlas.yaml"
        atlas_path.write_text(
            "cohorts:\n"
            "  c1:\n"
            "    renderer_operator_id: claude-opus-4-8\n"
            "    extractor_operator_id: gpt-5.4-mini-2026-03-17\n"
            "  c2:\n"
            "    renderer_operator_id: gpt-5.5-2026-04-23\n"
            "    extractor_operator_id: brand-new-model-1.0\n"
        )
        rc = cmd_version_floor(
            argparse.Namespace(
                operators=None, atlas=str(atlas_path), manifest=str(manifest)
            )
        )
        check("atlas with unmeasured extractor -> stale", rc == 1, f"rc={rc}")

    # The real shipped manifest parses and covers the VE-1 operator set.
    shipped = (
        Path(__file__).resolve().parents[2] / "data" / "version_floor_manifest.json"
    )
    data = json.loads(shipped.read_text())
    check(
        "shipped manifest carries VE-1 + 11 renderers + 3 extractors",
        data["epoch"]["id"] == "VE-1"
        and len(data["measured_under"]["renderers"]) == 11
        and len(data["measured_under"]["extractors"]) == 3,
        str(data.get("epoch")),
    )

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
