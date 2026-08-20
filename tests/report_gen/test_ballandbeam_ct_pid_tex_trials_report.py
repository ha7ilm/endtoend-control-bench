TEST_MODULE = "tests/test_ballandbeam_ct_pid_tex_trials.py"

REASONS_BY_TEST = {
    "test_ballandbeam_tex_ct_pid_trials_have_finite_signals": (
        "Ensure all textbook Ball-and-Beam continuous-time trial gains (P and PD variants) execute with finite "
        "signals, providing a stable baseline for comparative KPI assertions."
    ),
    "test_ballandbeam_tex_ct_pd_trials_improve_baseline_characteristics": (
        "Guard the expected PD tuning trend from BallAndBeam.tex: PD(10,10) should reduce steady-state error versus "
        "P-only, and PD(10,20) should not increase overshoot relative to PD(10,10)."
    ),
}

REASONS_BY_NODEID = {}
