"""Write CLAIMS.md and results/claim_ledger.csv: one provenance record per claim.

Every figure quoted in the prose is already recomputed by check_claims.py. This
adds what the publication standard asks each claim to carry: what it rests on,
how to reproduce it, and a record of commit, dirty flag, environment and a
digest of the exact data slice used after subsetting.

    python tools/claim_ledger.py
"""

from __future__ import annotations

import csv
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import check_claims  # noqa: E402
from phantomload.shared import provenance  # noqa: E402

# Ordered: first matching prefix wins, so specific prefixes come before general.
SLICE_MAP: list[tuple[str, list[str], str]] = [
    ("checklist basis", ["eia_cost_years"], "t2_cost.summary"),
    ("checklist", ["eia_national_total"], "t1_utilization.national_summary"),
    ("t1 utility", ["aceee_2015_28_utilities"], "t1_utilization.utility_dispersion"),
    ("t1 largest zero", ["aceee_2015_28_utilities"], "t1_utilization.utility_dispersion"),
    ("t1 panel", ["eia_utility_2016_2018_positive"], "t1_utilization.utility_panel_summary"),
    ("t1 regional", ["ferc_regional", "eia_national_by_sector"], "t1_utilization.regional_summary"),
    ("t1 composition", ["eia_national_by_sector"], "t1_utilization.composition_summary"),
    ("t1 within", ["eia_national_by_sector"], "t1_utilization.composition_summary"),
    ("t1 frozen", ["eia_national_by_sector"], "t1_utilization.composition_summary"),
    ("t1 commercial", ["eia_national_by_sector"], "t1_utilization.composition_summary"),
    ("t1 dispersion", ["eia_national_by_sector"], "t1_utilization.composition_summary"),
    ("t1 persistence", [], "t1_utilization.persistence_summary"),
    ("t1 design", [], "t1_utilization.persistence_summary"),
    ("t1 min window", [], "t1_utilization.min_window"),
    ("t1 max identifiable", [], "t1_utilization.max_identifiable_return_period"),
    ("t1 rotation", ["eia_utility_2016_2018_positive"], "t1_utilization.rotation_summary"),
    ("t1", ["eia_national_total"], "t1_utilization.national_summary"),
    ("t2 xcheck", ["eia_cost_years", "pjm_lmp_annual"], "t2_cost.netting_cross_check"),
    ("t2 price", ["eia_cost_years", "pjm_cone_2027_28", "pjm_lmp_annual"], "t2_cost.netting_summary"),
    ("t2 credit", ["eia_cost_years", "pjm_cone_2027_28", "pjm_lmp_annual"], "t2_cost.netting_summary"),
    ("t2 netting", ["eia_cost_years", "pjm_cone_2027_28"], "t2_cost.netting_summary"),
    ("t2 pjm", ["eia_cost_years", "pjm_cone_2027_28"], "t2_cost.summary"),
    ("t2 eas", ["pjm_cone_2027_28"], "t2_cost.summary"),
    ("t2 breakeven", ["eia_cost_years", "pjm_cone_2027_28"], "t2_cost.summary"),
    ("t2 lda", ["eia_cost_years", "pjm_cone_2027_28"], "t2_cost.pjm_comparison"),
    ("t2 pl", ["pjm_cone_2027_28"], "t2_cost.summary"),
    ("t2 dearer", ["eia_cost_years", "pjm_cone_2027_28"], "t2_cost.summary"),
    ("t2 basis", ["eia_cost_years", "pjm_cone_2027_28"], "t2_cost.basis_sensitivity"),
    ("t2 years", ["eia_cost_years", "pjm_cone_2027_28"], "t2_cost.years_that_beat_gross_cone"),
    ("t2", ["eia_cost_years"], "t2_cost.summary"),
    ("t3", ["eia_national_by_sector"], "t3_behavioral.inversion_summary"),
    ("t4", ["carboncast_hourly"], "t4_curtailment.summary"),
    ("t5 dynamic", ["ferc_regional"], "t5_double_count.exposure_bounds"),
    ("t5 overlap", ["ferc_regional"], "t5_double_count.exposure_bounds"),
    ("t5 exposed", ["ferc_regional", "eia_national_by_sector"], "t5_double_count.exposed_mw"),
    ("t5 top", ["ferc_regional"], "t5_double_count.regional_exposure"),
    ("t5", [], "t5_double_count.summary"),
    ("t6", ["eia_cost_years"], "t6_overhead.summary"),
    ("t7 wholesale", ["ferc_rto_wholesale", "eia_national_total"], "t7_crossval.summary"),
    ("t7 pjm", ["ferc_rto_wholesale", "eia_national_total"], "t7_crossval.pjm_event_utilization"),
    ("t7 enforcement", [], "t7_crossval.enforcement_cases"),
    ("t7", ["eia_national_by_sector"], "t7_crossval.summary"),
    ("t8d", ["ferc_regional", "eia_national_by_sector"], "t8_falsification.attack_d"),
    ("t9 class", ["eia_utility_class_2016_2018"], "t9_mechanisms.class_gradient_summary"),
    ("t9 spec", ["eia_utility_2016_2018_positive"], "t9_mechanisms.specification_summary"),
    ("t9 exact", ["eia_utility_2016_2018_positive"], "t9_mechanisms.exact_equality"),
    ("t9 measured", ["eia_utility_2016_2018_positive"], "t9_mechanisms.size_gradient_measured_only"),
    ("t9 footprint", ["eia_utility_2016_2018_footprint"], "t9_mechanisms.footprint_grid_summary"),
    ("t9 outside", ["eia_utility_2016_2018_footprint"], "t9_mechanisms.wholesale_accounting_test"),
    ("t9", ["eia_utility_2016_2018_positive"], "t9_mechanisms.summary"),
    ("t8", ["eia_cost_years", "pjm_cone_2027_28"], "t8_falsification.run"),
    ("synthesis sweep", ["eia_cost_years"], "synthesis.headline_sweep_summary"),
    ("synthesis winter", ["eia_cost_years", "pjm_cone_2027_28"], "synthesis.elcc_summary"),
    ("synthesis", ["eia_cost_years", "pjm_cone_2027_28", "pjm_lmp_annual"], "synthesis.summary"),
]

# Claims resting on no data slice at all are identities, simulations or cited
# constants. They are recorded as such rather than given a fake digest.
NO_SLICE_REASON = {
    "t1 persistence": "identity (two-state Markov chain)",
    "t1 design": "identity (design effect of the chain)",
    "t1 min window": "identity (rule of three)",
    "t1 max identifiable": "identity (rule of three)",
    "t5": "simulated (attribution algebra over a swept range)",
    "t7 enforcement": "cited constants (FERC enforcement record)",
}


def route(label: str) -> tuple[list[str], str, str]:
    for prefix, slices, fn in SLICE_MAP:
        if label.startswith(prefix):
            reason = next(
                (r for p, r in NO_SLICE_REASON.items() if label.startswith(p) and not slices),
                "",
            )
            return slices, fn, reason
    raise KeyError(f"claim '{label}' has no provenance route; add it to SLICE_MAP")


def build() -> list[dict]:
    m = check_claims._load_summaries()
    claims = check_claims.build_claims(m)
    slices = provenance.slice_records()
    git = provenance.git_state(ROOT)
    env = provenance.environment()
    env_str = ", ".join(f"{k} {v}" for k, v in env.items())
    rows = []
    for i, (label, quoted) in enumerate(claims, 1):
        names, fn, reason = route(label)
        rows.append(
            {
                "id": f"C{i:03d}",
                "kind": (
                    "modeled" if label in check_claims.MODELED
                    else "identity" if reason.startswith("identity")
                    else "cited" if reason.startswith("cited")
                    else "measured"
                ),
                "label": label,
                "quoted": quoted,
                "computed_by": f"phantomload.{fn}",
                "rests_on": "; ".join(names) if names else reason or "none",
                "slice_digests": "; ".join(
                    f"{n}:{slices[n]['digest'][:16]}" for n in names
                ),
                "slice_rows": "; ".join(f"{n}:{slices[n]['rows']}" for n in names),
                "commit": git["commit"],
                "dirty": git["dirty"],
                "environment": env_str,
                "reproduce": "python tools/check_claims.py",
            }
        )
    return rows


def main() -> int:
    # Provenance is captured ONCE, inside build(), before anything is written.
    # An earlier version wrote the CSV and then queried git again for the
    # CLAIMS.md header, so the header saw its own sibling file as a change and
    # recorded dirty=True while every CSV row recorded dirty=False. Two
    # provenance records for one run disagreed. Both now read the same capture.
    rows = build()
    git = {"commit": rows[0]["commit"], "dirty": rows[0]["dirty"]}
    out = ROOT / "results" / "claim_ledger.csv"
    with out.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    slices = provenance.slice_records()
    lines = [
        "# Claims",
        "",
        "Every figure quoted in README, FINDINGS, FALSIFICATION and PRIOR_WORK, with",
        "what it rests on and how to reproduce it. Generated by",
        "`tools/claim_ledger.py`; do not edit by hand. `tools/check_claims.py`",
        "recomputes every value and fails the build on drift.",
        "",
        f"Commit `{git['commit'][:12]}`, dirty `{git['dirty']}`. "
        f"Environment: {rows[0]['environment']}.",
        "",
        "Kinds: **measured** rests only on vendored data; **cited** rests on a",
        "published constant; **identity** is true by construction; **modeled**",
        "depends on a simulation or an assumed parameter and appears only in",
        "MODELED.md, never in the citable documents, which the guard enforces.",
        "",
        "## Data slices",
        "",
        "Each digest is sha256 of the exact subset a claim is computed from, after",
        "filtering, in canonical form (columns and rows sorted). It changes if any",
        "value a claim rests on changes, and only then.",
        "",
        "| Slice | Rows | Digest |",
        "| --- | --- | --- |",
    ]
    for name, rec in slices.items():
        lines.append(f"| `{name}` | {rec['rows']:,} | `{rec['digest'][:16]}` |")
    lines += [
        "",
        "## Claims",
        "",
        "| ID | Kind | Claim | Computed by | Rests on |",
        "| --- | --- | --- | --- | --- |",
    ]
    for r in rows:
        quoted = r["quoted"].replace("|", "\\|")
        lines.append(
            f"| {r['id']} | {r['kind']} | {quoted} | `{r['computed_by']}` | {r['rests_on']} |"
        )
    (ROOT / "CLAIMS.md").write_text("\n".join(lines) + "\n")
    print(f"wrote {len(rows)} claim records and {len(slices)} slice digests")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
