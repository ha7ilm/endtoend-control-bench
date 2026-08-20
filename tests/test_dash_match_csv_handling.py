import csv

from dashes.lib_query_runs import (
    MatchCsvRow,
    build_controller_lookup,
    build_run_lookup,
    classify_why_phase,
    load_match_csv_rows,
    parse_sim_run_path,
    read_best_controller_name,
    resolve_last_design_before_tuning_run_paths,
)


def _write_match_csv(tmp_path, header, rows):
    csv_path = tmp_path / "npy_match.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)
    return csv_path


def test_load_match_csv_rows_parses_and_normalizes_status(tmp_path):
    _write_match_csv(
        tmp_path,
        header=["status", "run_path", "controller_path", "note"],
        rows=[
            ["pass", "sim/s1/e1/attempt0/run0.npy", "wp/s1/e1/attempt0/lwp/rlwp/controller_1.py", ""],
            ["warn", "sim/s1/e1/attempt0/run1.npy", "wp/s1/e1/attempt0/lwp/rlwp/controller_2.py", ""],
        ],
    )

    rows, issues = load_match_csv_rows(tmp_path)

    assert issues == []
    assert [row.status for row in rows] == ["PASS", "WARN"]
    assert rows[0].row_number == 2
    assert rows[1].row_number == 3


def test_load_match_csv_rows_reports_missing_required_columns(tmp_path):
    _write_match_csv(
        tmp_path,
        header=["status", "run_path"],
        rows=[["PASS", "sim/s1/e1/attempt0/run0.npy"]],
    )

    rows, issues = load_match_csv_rows(tmp_path)

    assert rows == []
    assert issues
    assert "missing required columns" in issues[0]


def test_load_match_csv_rows_skips_malformed_rows(tmp_path):
    _write_match_csv(
        tmp_path,
        header=["status", "run_path", "controller_path"],
        rows=[
            ["PASS", "sim/s1/e1/attempt0/run0.npy", "wp/s1/e1/attempt0/lwp/rlwp/controller_1.py"],
            ["WARN", "", "wp/s1/e1/attempt0/lwp/rlwp/controller_2.py"],
            ["", "sim/s1/e1/attempt0/run2.npy", "wp/s1/e1/attempt0/lwp/rlwp/controller_3.py"],
        ],
    )

    rows, issues = load_match_csv_rows(tmp_path)

    assert len(rows) == 1
    assert rows[0].status == "PASS"
    assert len(issues) == 2
    assert all("skipped malformed row" in issue for issue in issues)


def test_build_controller_lookup_filters_status_and_uses_last_duplicate_policy():
    rows = [
        MatchCsvRow(
            status="PASS",
            run_path="sim/s1/e1/attempt0/run0.npy",
            controller_path="wp/s1/e1/attempt0/lwp/rlwp/controller_1.py",
            row_number=2,
        ),
        MatchCsvRow(
            status="WARN",
            run_path="sim/s1/e1/attempt0/run1.npy",
            controller_path="wp/s1/e1/attempt0/lwp/rlwp/controller_1.py",
            row_number=3,
        ),
        MatchCsvRow(
            status="FAIL",
            run_path="sim/s1/e1/attempt0/run9.npy",
            controller_path="wp/s1/e1/attempt0/lwp/rlwp/controller_9.py",
            row_number=4,
        ),
    ]

    mapping, issues = build_controller_lookup(
        rows,
        allowed_statuses={"PASS", "WARN"},
        duplicate_policy="last",
    )

    assert "wp/s1/e1/attempt0/lwp/rlwp/controller_9.py" not in mapping
    assert mapping["wp/s1/e1/attempt0/lwp/rlwp/controller_1.py"] == (
        "sim/s1/e1/attempt0/run1.npy",
        "WARN",
    )
    assert any("overriding" in issue for issue in issues)


def test_build_controller_lookup_first_duplicate_policy_keeps_first():
    rows = [
        MatchCsvRow(
            status="PASS",
            run_path="sim/s1/e1/attempt0/run0.npy",
            controller_path="wp/s1/e1/attempt0/lwp/rlwp/controller_1.py",
            row_number=2,
        ),
        MatchCsvRow(
            status="WARN",
            run_path="sim/s1/e1/attempt0/run1.npy",
            controller_path="wp/s1/e1/attempt0/lwp/rlwp/controller_1.py",
            row_number=3,
        ),
    ]

    mapping, issues = build_controller_lookup(rows, duplicate_policy="first")

    assert mapping["wp/s1/e1/attempt0/lwp/rlwp/controller_1.py"] == (
        "sim/s1/e1/attempt0/run0.npy",
        "PASS",
    )
    assert any("keeping first value" in issue for issue in issues)


def test_build_run_lookup_filters_status_and_maps_to_controller():
    rows = [
        MatchCsvRow(
            status="PASS",
            run_path="sim/s1/e1/attempt0/run0.npy",
            controller_path="wp/s1/e1/attempt0/lwp/rlwp/controller_1.py",
            row_number=2,
        ),
        MatchCsvRow(
            status="FAIL",
            run_path="sim/s1/e1/attempt0/run9.npy",
            controller_path="wp/s1/e1/attempt0/lwp/rlwp/controller_9.py",
            row_number=3,
        ),
    ]

    mapping, issues = build_run_lookup(rows, allowed_statuses={"PASS", "WARN"})

    assert issues == []
    assert mapping == {
        "sim/s1/e1/attempt0/run0.npy": (
            "wp/s1/e1/attempt0/lwp/rlwp/controller_1.py",
            "PASS",
        )
    }


def test_read_best_controller_name_valid_and_malformed(tmp_path):
    rlwp_dir = tmp_path / "wp" / "s1" / "case1" / "attempt0" / "lwp" / "rlwp"
    rlwp_dir.mkdir(parents=True)

    (rlwp_dir / "best.txt").write_text("controller_12.py\n", encoding="utf-8")
    controller_name, issue = read_best_controller_name(rlwp_dir)
    assert controller_name == "controller_12.py"
    assert issue is None

    (rlwp_dir / "best.txt").write_text("not_a_controller.py\n", encoding="utf-8")
    controller_name, issue = read_best_controller_name(rlwp_dir)
    assert controller_name is None
    assert issue is not None
    assert "malformed best.txt" in issue


def test_parse_sim_run_path_and_classify_why_phase():
    assert parse_sim_run_path("sim/s1/e1/attempt2/run17.npy") == ("s1", "e1", 2, 17)
    assert parse_sim_run_path("unexpected/path.npy") is None

    assert classify_why_phase("Design to meet specifications: baseline") == "design"
    assert classify_why_phase("  tuning: improve objective ") == "tuning"
    assert classify_why_phase("Some other phase") is None


def test_resolve_last_design_before_tuning_run_paths_selects_transition_runs():
    selected, issues = resolve_last_design_before_tuning_run_paths(
        {
            "sim/s1/e1/attempt0/run0.npy": "Design to meet specifications: initial",
            "sim/s1/e1/attempt0/run1.npy": "Design to meet specifications: refine",
            "sim/s1/e1/attempt0/run2.npy": "Tuning: first tuning run",
            "sim/s1/e1/attempt0/run3.npy": "Tuning: second tuning run",
            "sim/s1/e1/attempt1/run0.npy": "Design to meet specifications: no tuning here",
        }
    )

    assert issues == []
    assert selected == {"sim/s1/e1/attempt0/run1.npy"}


def test_resolve_last_design_before_tuning_run_paths_reports_malformed_or_missing_transition():
    selected, issues = resolve_last_design_before_tuning_run_paths(
        {
            "sim/s1/e1/attempt0/run0.npy": "Tuning: starts directly in tuning",
            "sim/s1/e1/attempt0/run1.npy": "Tuning: still tuning",
            "sim/s1/e1/attempt1/run0.npy": "unknown text",
            "not/a/sim/path.npy": "Design to meet specifications: malformed path",
        }
    )

    assert selected == set()
    assert any("unexpected sim path format" in issue for issue in issues)
    assert any("unrecognized why prefix" in issue for issue in issues)
    assert any("no design run found before first tuning" in issue for issue in issues)
