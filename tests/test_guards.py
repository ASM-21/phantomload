"""Guard tests. These cover the things that protect the prose and the parameters,
including a deliberately broken README to prove the guard can actually fail."""

from __future__ import annotations

import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

import pytest

from phantomload.shared.calibration import ALL_PARAMS, PEAKER_CONE, Param
from phantomload.shared.dr_program import Provenance

ROOT = pathlib.Path(__file__).resolve().parents[1]


# --- calibration discipline -------------------------------------------------
def test_every_param_has_a_range_and_a_note():
    for p in ALL_PARAMS:
        assert p.lo < p.hi, p.name
        assert p.lo <= p.central <= p.hi, p.name
        assert p.note.strip(), p.name
        assert p.units.strip(), p.name


def test_literature_params_require_a_citation():
    for p in ALL_PARAMS:
        if p.provenance is Provenance.LITERATURE:
            assert p.citation, p.name


def test_uncited_params_are_flagged_not_promoted():
    """Nothing may sit at LITERATURE without a reference, and anything that is
    only field familiarity must carry needs_citation so README can list it."""
    for p in ALL_PARAMS:
        if p.provenance is Provenance.ASSUMPTION:
            assert p.needs_citation is True, p.name
            assert p.citation is None, p.name


def test_param_rejects_central_outside_range():
    with pytest.raises(ValueError):
        Param(
            name="bad",
            lo=1.0,
            central=5.0,
            hi=2.0,
            units="x",
            provenance=Provenance.ASSUMPTION,
            note="n",
            needs_citation=True,
        )


def test_param_rejects_uncited_literature():
    with pytest.raises(ValueError):
        Param(
            name="bad",
            lo=1.0,
            central=1.5,
            hi=2.0,
            units="x",
            provenance=Provenance.LITERATURE,
            note="n",
        )


def test_sweep_spans_the_full_range():
    s = PEAKER_CONE.sweep(5)
    assert s[0] == PEAKER_CONE.lo
    assert s[-1] == PEAKER_CONE.hi
    assert len(s) == 5


def test_comparator_range_straddles_the_breakeven():
    """If a future cost vintage moves DR clear of the comparator range, the
    README's central framing stops being true and this fails first."""
    from phantomload.tracks import t2_cost as t2

    s = t2.summary()
    assert PEAKER_CONE.lo < s["cost_per_kw_delivered"]
    assert PEAKER_CONE.hi > s["cost_per_kw_enrolled"]


# --- claims guard -----------------------------------------------------------
def _flexible(phrase: str) -> re.Pattern:
    """Match a phrase however the prose happens to be wrapped."""
    return re.compile(r"\s+".join(re.escape(w) for w in phrase.split()))


def _run_guard(cwd: pathlib.Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(cwd / "tools" / "check_claims.py")],
        cwd=cwd,
        capture_output=True,
        text=True,
    )


def test_guard_passes_on_the_real_docs():
    res = _run_guard(ROOT)
    assert res.returncode == 0, res.stdout + res.stderr


def _sandbox(tmp: pathlib.Path) -> pathlib.Path:
    """Copy just enough of the repo for the guard to run."""
    dst = tmp / "repo"
    dst.mkdir()
    # The guard checks relative links, so every link target must exist. Copy by
    # discovery rather than by list: a hard-coded list goes stale the moment a
    # doc is added, and the failure looks like a guard bug rather than a fixture
    # gap, which is exactly how this was found.
    for path in ROOT.glob("*.md"):
        shutil.copy(path, dst / path.name)
    for name in ("LICENSE", "NOTICE"):
        shutil.copy(ROOT / name, dst / name)
    for d in ("tools", "phantomload", "data", "figures"):
        shutil.copytree(ROOT / d, dst / d)
    return dst


def test_guard_fails_on_a_drifted_number():
    with tempfile.TemporaryDirectory() as tmp:
        repo = _sandbox(pathlib.Path(tmp))
        for path in repo.glob("*.md"):
            path.write_text(path.read_text().replace("39.2%", "72.0%"))
        res = _run_guard(repo)
        assert res.returncode == 1
        assert "drifted claim" in res.stdout


def test_guard_fails_when_a_caveat_is_deleted():
    with tempfile.TemporaryDirectory() as tmp:
        repo = _sandbox(pathlib.Path(tmp))
        pattern = _flexible(
            "demand response costs are not netted of avoided energy purchases"
        )
        replaced = 0
        for path in repo.glob("*.md"):
            body, n = pattern.subn("both sides are priced on the same basis",
                                   path.read_text())
            replaced += n
            path.write_text(body)
        assert replaced, "test did not actually delete the caveat"
        res = _run_guard(repo)
        assert res.returncode == 1
        assert "missing required caveat" in res.stdout


def test_guard_fails_on_overclaiming_language():
    with tempfile.TemporaryDirectory() as tmp:
        repo = _sandbox(pathlib.Path(tmp))
        readme = repo / "README.md"
        readme.write_text(
            readme.read_text() + "\n\nThis analysis proves the capacity is wasted.\n"
        )
        res = _run_guard(repo)
        assert res.returncode == 1
        assert "overclaim" in res.stdout


def test_guard_allows_strong_language_inside_a_retraction_quote():
    with tempfile.TemporaryDirectory() as tmp:
        repo = _sandbox(pathlib.Path(tmp))
        readme = repo / "README.md"
        readme.write_text(
            readme.read_text()
            + "\n\n> RETRACTED: an earlier draft said this proves the capacity"
            " is wasted. It does not.\n"
        )
        res = _run_guard(repo)
        assert res.returncode == 0, res.stdout


def test_guard_fails_if_a_doc_goes_missing():
    with tempfile.TemporaryDirectory() as tmp:
        repo = _sandbox(pathlib.Path(tmp))
        (repo / "FALSIFICATION.md").unlink()
        res = _run_guard(repo)
        assert res.returncode == 1
        assert "missing doc" in res.stdout


# --- packaging sanity -------------------------------------------------------
def test_readme_test_count_matches_reality():
    """The close-out check that catches a stale count in the README."""
    res = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    # pytest -q prints "path.py: N" per file; without -q it prints node ids.
    # Handle both so the check does not depend on the pytest version.
    per_file = re.findall(r"^\S+\.py: (\d+)$", res.stdout, flags=re.M)
    collected = sum(int(n) for n in per_file) or sum(
        1 for ln in res.stdout.splitlines() if "::" in ln
    )
    assert collected > 0, res.stdout + res.stderr
    readme = (ROOT / "README.md").read_text()
    assert f"{collected} tests" in readme, (
        f"README does not say '{collected} tests'"
    )


def test_no_placeholder_text_left_in_docs():
    for name in ("README.md", "FINDINGS.md", "FALSIFICATION.md", "DATA.md"):
        body = (ROOT / name).read_text()
        for bad in ("TODO", "TKTK", "FIXME", "XXX", "lorem"):
            assert bad not in body, f"{name} contains {bad}"


# --- source checker ---------------------------------------------------------
def test_source_parser_reads_the_published_table_shape():
    sys.path.insert(0, str(ROOT / "tools"))
    import check_source

    html = (
        "<table><tr><td>Table 10.3</td></tr>"
        "<tr><td>Potential Peak Demand Savings (MW)</td><td></td></tr>"
        "<tr><td>2024</td><td>9,706</td><td>7,346</td><td>14,439</td>"
        "<td>--</td><td>31,491</td></tr>"
        "<tr><td>Actual Peak Demand Savings (MW)</td></tr>"
        "<tr><td>2024</td><td>4,785</td><td>2,457</td><td>5,080</td>"
        "<td>--</td><td>12,322</td></tr></table>"
    )
    out = check_source.parse(
        html,
        {
            "Potential Peak Demand Savings (MW)": "potential_peak_mw",
            "Actual Peak Demand Savings (MW)": "actual_peak_mw",
        },
    )
    assert out[(2024, "residential", "potential_peak_mw")] == 9706
    assert out[(2024, "total", "actual_peak_mw")] == 12322
    # "--" must not become a zero
    assert (2024, "transportation", "potential_peak_mw") not in out


def test_source_checker_skips_rather_than_fails_when_offline():
    """CI must not go red because a government website is down."""
    sys.path.insert(0, str(ROOT / "tools"))
    import check_source

    original = check_source.fetch
    check_source.fetch = lambda url, timeout=20: None
    try:
        sys.argv = ["check_source.py"]
        assert check_source.main() == 0
        sys.argv = ["check_source.py", "--require"]
        assert check_source.main() == 1
    finally:
        check_source.fetch = original
        sys.argv = ["pytest"]


def test_guard_fails_on_a_dead_link():
    with tempfile.TemporaryDirectory() as tmp:
        repo = _sandbox(pathlib.Path(tmp))
        readme = repo / "README.md"
        readme.write_text(readme.read_text() + "\n\nSee [the plan](PLAN.md).\n")
        res = _run_guard(repo)
        assert res.returncode == 1
        assert "dead link" in res.stdout


def test_every_vendored_dataset_is_documented():
    """A data file with no provenance entry is the failure this repo exists to
    avoid, so adding one without documenting it breaks the build."""
    data_md = (ROOT / "DATA.md").read_text()
    notice = (ROOT / "NOTICE").read_text()
    files = [
        p for p in (ROOT / "data").rglob("*")
        if p.is_file() and p.suffix in {".csv"}
    ]
    assert files
    for f in files:
        rel = f.relative_to(ROOT).as_posix()
        assert rel in data_md, f"{rel} not documented in DATA.md"
        assert rel in notice or "eia861" in rel or "pjm" in rel, rel
    assert len(files) >= 7, "a dataset went missing from data/"


def test_rename_script_is_executable_and_current():
    """The rename script hard-codes the current names. If the package is renamed
    by any other route, this fails rather than leaving a stale script behind."""
    script = ROOT / "tools" / "rename.sh"
    assert script.exists()
    assert os.access(script, os.X_OK), "rename.sh lost its exec bit"
    body = script.read_text()
    pkg = next(
        p.name
        for p in ROOT.iterdir()
        if p.is_dir() and (p / "__init__.py").exists() and p.name != "tests"
    )
    assert f'OLD_PKG="{pkg}"' in body
    assert f'OLD_DIST="{pkg}"' in body


def test_readme_documents_the_naming_problem():
    """The name overstates the findings and collides with established usage.
    That has to stay said until the rename actually happens."""
    readme = (ROOT / "README.md").read_text()
    assert "## About the name" in readme
    assert "standby draw" in readme
    assert "tools/rename.sh" in readme


def test_guard_tolerates_line_wrapping_but_not_drift():
    """A required phrase split across a line break is still present. A changed
    number is not. The guard must distinguish those, or reflowing prose starts
    breaking the build for no reason and people learn to ignore it."""
    with tempfile.TemporaryDirectory() as tmp:
        repo = _sandbox(pathlib.Path(tmp))
        findings = repo / "FINDINGS.md"
        body = findings.read_text()
        assert _flexible("tariff not read").search(body)
        findings.write_text(
            _flexible("tariff not read").sub("tariff not\nread", body)
        )
        assert _run_guard(repo).returncode == 0, "wrapping should not fail the guard"

        findings.write_text(
            _flexible("tariff not read").sub("tariff read in full", body)
        )
        res = _run_guard(repo)
        assert res.returncode == 1
        assert "missing required caveat" in res.stdout


def test_method_rules_reference_real_tests():
    """METHOD.md claims specific tests enforce specific rules. If a named test
    is renamed or deleted, the claim silently becomes false, so check it."""
    method = (ROOT / "METHOD.md").read_text()
    named = set(re.findall(r"`(test_[a-z0-9_]+)`", method))
    assert len(named) >= 10, f"only {len(named)} tests cited in METHOD.md"
    existing = set()
    for path in (ROOT / "tests").glob("test_*.py"):
        existing |= set(re.findall(r"^def (test_[a-z0-9_]+)", path.read_text(), re.M))
    missing = named - existing
    assert not missing, f"METHOD.md cites tests that do not exist: {sorted(missing)}"


def test_verify_script_cleans_up_after_itself():
    """It leaked a 400 MB venv per run until the disk filled. The trap is the
    fix and it must not be edited away."""
    body = (ROOT / "verify.sh").read_text()
    assert "trap cleanup EXIT" in body
    assert "rm -rf" in body


def test_docs_state_the_question_before_the_answer():
    """The README lost its spine once and this keeps it. A reader should meet
    the question, then the answer, then the evidence, in that order."""
    readme = (ROOT / "README.md").read_text()
    for heading in ("## The question", "## The answer", "## The evidence in one screen"):
        assert heading in readme, heading
    assert readme.index("## The question") < readme.index("## The answer")
    assert readme.index("## The answer") < readme.index("## The evidence in one screen")


def test_literature_gap_is_disclosed():
    """No literature review was done. That is the first thing a reviewer would
    raise, so it has to stay stated rather than drift out during an edit."""
    readme = (ROOT / "README.md").read_text()
    assert "No systematic literature review has been performed" in readme
    assert "should be presented as novel" in readme
    roadmap = (ROOT / "ROADMAP.md").read_text()
    assert "A literature review" in roadmap
    prior = (ROOT / "PRIOR_WORK.md").read_text()
    assert "still unsearched" in prior


def test_findings_sections_are_questions():
    findings = (ROOT / "FINDINGS.md").read_text()
    numbered = re.findall(r"^## \d+\..*$", findings, re.M)
    assert len(numbered) >= 9
    questions = [h for h in numbered if h.rstrip().endswith("?")]
    assert len(questions) >= 8, f"only {len(questions)} of {len(numbered)} are questions"


def test_prior_work_is_documented_and_credited():
    """The headline is a reproduction of a 2017 result. If that ever stops being
    said, the repo is overclaiming again."""
    prior = (ROOT / "PRIOR_WORK.md").read_text()
    assert "Nadel" in prior and "2017" in prior
    assert "not a discovery" in (ROOT / "README.md").read_text()
    assert "PRIOR_WORK.md" in (ROOT / "README.md").read_text()


def test_independence_and_identity_are_declared():
    """This is a power systems repo written by someone employed in the industry.
    The independence statement and the public-data-only claim are not optional
    and must not drift out during an edit."""
    readme = (ROOT / "README.md").read_text()
    assert "## Independence" in readme
    assert _flexible(
        "not affiliated with, funded by, reviewed by or endorsed by any employer"
    ).search(readme)
    assert _flexible("No non-public, confidential or employer data").search(readme)
    assert "0009-0004-8758-2687" in readme
    cff = (ROOT / "CITATION.cff").read_text()
    assert "Morrissey" in cff and "0009-0004-8758-2687" in cff
    assert "Apache-2.0" in cff
    assert "Apache" in (ROOT / "LICENSE").read_text()
    assert "Copyright 2026 Andrew Morrissey" in (ROOT / "LICENSE").read_text()


def test_no_employer_or_private_data_in_the_tree():
    """Every input must be public. A file naming an employer system, an internal
    path or a credential would fail the independence claim above."""
    # The scan covers what actually ships as code and data. tests/ is excluded
    # because this function necessarily contains the banned strings itself, and
    # README is excluded because the independence clause legitimately uses the
    # word while promising the opposite.
    banned = ("internal use only", "proprietary and confidential",
              "BEGIN PRIVATE KEY", "BEGIN RSA", "AKIA", "password=",
              "api_key=", "secret_key")
    hits = []
    roots = [ROOT / d for d in ("phantomload", "data", "tools", "results")]
    for root in roots:
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix in {".png", ".gz"}:
                continue
            try:
                body = path.read_text(errors="ignore")
            except OSError:
                continue
            for term in banned:
                if term.lower() in body.lower():
                    hits.append((path.name, term))
    assert not hits, f"non-public markers found: {hits[:5]}"


def test_guard_catches_a_stale_value_beside_its_replacement():
    """The blind spot that let four stale figures survive one audit: the drift
    check passes as long as the new value appears somewhere, even if the old one
    is still stated as current elsewhere. Inject exactly that and require a
    failure, then confirm the same value is allowed when marked historical."""
    with tempfile.TemporaryDirectory() as tmp:
        repo = _sandbox(pathlib.Path(tmp))
        findings = repo / "FINDINGS.md"
        body = findings.read_text()
        findings.write_text(body + "\n\nThe overcredit exceeds it by a factor of 5.0x.\n")
        res = _run_guard(repo)
        assert res.returncode == 1
        assert "retired value" in res.stdout

        findings.write_text(
            body + "\n\nAn earlier version said a factor of 5.0x; it was corrected.\n"
        )
        assert _run_guard(repo).returncode == 0


def test_guard_keeps_modeled_claims_out_of_citable_docs():
    """The standard refuses generated results in the citable findings. Inject a
    modeled figure into FINDINGS and require a failure."""
    with tempfile.TemporaryDirectory() as tmp:
        repo = _sandbox(pathlib.Path(tmp))
        findings = repo / "FINDINGS.md"
        findings.write_text(
            findings.read_text()
            + "\n\nThe overcredit is 22% more than its marginal contribution.\n"
        )
        res = _run_guard(repo)
        assert res.returncode == 1
        assert "modeled claim in citable doc" in res.stdout


def test_claim_ledger_classifies_every_claim():
    """Every quoted figure has a provenance route and a kind, and nothing that
    reads data does so without a slice digest."""
    sys.path.insert(0, str(ROOT / "tools"))
    import claim_ledger

    rows = claim_ledger.build()
    assert len(rows) >= 100
    kinds = {r["kind"] for r in rows}
    assert kinds <= {"measured", "modeled", "identity", "cited"}
    for r in rows:
        if r["kind"] == "measured":
            assert r["slice_digests"], f"{r['id']} {r['label']} measured but no digest"
    assert sum(r["kind"] == "modeled" for r in rows) >= 10


def test_slice_digest_is_order_invariant_and_value_sensitive():
    """A digest of the slice, not the file: reordering must not change it, and
    changing one value must."""
    import pandas as pd
    from phantomload.shared.provenance import slice_digest

    a = pd.DataFrame({"x": [1, 2, 3], "y": [0.5, 0.25, 0.125]})
    shuffled = a.iloc[[2, 0, 1]][["y", "x"]]
    assert slice_digest(a) == slice_digest(shuffled)
    changed = a.copy()
    changed.loc[1, "y"] = 0.26
    assert slice_digest(a) != slice_digest(changed)


def test_nothing_that_ships_contains_a_machine_path():
    """Absolute paths from the build machine leak the environment and break for
    everyone else. Bytecode caches embed them legitimately and are gitignored."""
    patterns = ("/home/claude", "/mnt/user-data", "C:\\\\Users\\\\")
    hits = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or "__pycache__" in path.parts or ".git" in path.parts:
            continue
        if path.suffix in {".png", ".gz", ".pyc"} or path.name == "test_guards.py":
            continue
        body = path.read_text(errors="ignore")
        hits += [(path.name, p) for p in patterns if p in body]
    assert not hits, hits[:5]
    assert "__pycache__" in (ROOT / ".gitignore").read_text()


def test_ledger_header_and_rows_record_the_same_provenance():
    """Both artifacts come from one run and must agree. They once did not: the
    header was captured after the CSV was written and reported a dirty tree."""
    import csv

    claims_md = (ROOT / "CLAIMS.md").read_text()
    header = re.search(r"Commit `([0-9a-f]+|unversioned)`, dirty `(\w+)`", claims_md)
    assert header, "CLAIMS.md has no provenance header"
    rows = list(csv.DictReader(open(ROOT / "results" / "claim_ledger.csv")))
    assert rows[0]["commit"].startswith(header.group(1)[:12]) or header.group(1) == "unversioned"
    assert str(rows[0]["dirty"]) == header.group(2)
