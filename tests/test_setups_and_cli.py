import pytest
import numpy as np

from controlserver.config import get_setup_config, get_setup_signal_metadata
from controlserver.server import build_parser
from controlserver.setups import available_setup_names, create_setup

BASE_SETUPS = (
    "motorspeed",
    "motorposition",
    "aircraftpitch",
    "ballandbeam",
    "cruisecontrol",
    "suspension",
    "invertedpendulum",
)

EXTRA_DT_VARIANTS = {
    "motorspeed_dt_lim": "motorspeed",
    "motorspeed_dt_lim_maxonre30": "motorspeed",
    "cruisecontrol_dt_lim_hondajazz": "cruisecontrol",
    "ballandbeam_dt_nl": "ballandbeam",
    "ballandbeam_dt_nl_act": "ballandbeam",
    "ballandbeam_dt_nl_act_mg996r": "ballandbeam",
    "invertedpendulum_dt_nl": "invertedpendulum",
    "invertedpendulum_dt_nl_quanserip02": "invertedpendulum",
    "invertedpendulum_dt_nl_lim_quanserip02": "invertedpendulum",
}

EXTRA_DT_VARIANT_DT_OVERRIDES = {
    "motorspeed_dt_lim_maxonre30": 0.001,
}

EXTRA_DT_VARIANT_HORIZON_OVERRIDES = {
    "motorspeed_dt_lim_maxonre30": 5.0,
}

EXTRA_DT_VARIANT_STEP_REF_OVERRIDES = {
    "motorspeed_dt_lim_maxonre30": 100.0,
}

DT_VARIANT_DT = {
    "motorspeed": 0.05,
    "motorposition": 0.001,
    "aircraftpitch": 0.01,
    "ballandbeam": 0.02,
    "cruisecontrol": 0.02,
    "suspension": 0.0005,
    "invertedpendulum": 0.01,
}

EXPECTED_SIGNALS = {
    "motorspeed": {
        "ref": {"display_name": "Speed reference", "unit": "rad/sec"},
        "meas": {"display_name": "Measured speed", "unit": "rad/sec"},
        "control": {"display_name": "Armature voltage", "unit": "V"},
    },
    "motorposition": {
        "ref": {"display_name": "Position reference", "unit": "rad"},
        "meas": {"display_name": "Measured position", "unit": "rad"},
        "control": {"display_name": "Armature voltage", "unit": "V"},
    },
    "aircraftpitch": {
        "ref": {"display_name": "Pitch reference", "unit": "rad"},
        "meas": {"display_name": "Measured pitch angle", "unit": "rad"},
        "control": {"display_name": "Elevator deflection", "unit": "rad"},
    },
    "ballandbeam": {
        "ref": {"display_name": "Ball position reference", "unit": "m"},
        "meas": {"display_name": "Measured ball position", "unit": "m"},
        "control": {"display_name": "Gear angle command", "unit": "rad"},
    },
    "cruisecontrol": {
        "ref": {"display_name": "Speed reference", "unit": "m/s"},
        "meas": {"display_name": "Measured speed", "unit": "m/s"},
        "control": {"display_name": "Traction force", "unit": "N"},
    },
    "suspension": {
        "ref": {"display_name": "Suspension travel target", "unit": "m"},
        "meas": {"display_name": "Suspension travel X1-X2", "unit": "m"},
        "control": {"display_name": "Actuator force", "unit": "N"},
    },
    "invertedpendulum": {
        "ref": {"display_name": "Cart/Pendulum reference", "unit": "mixed"},
        "meas": {"display_name": "Cart/Pendulum measurement", "unit": "mixed"},
        "control": {"display_name": "Cart force", "unit": "N"},
    },
}


def _dt_variant(base_setup: str) -> str:
    return f"{base_setup}_dt"


def _ct_variant(base_setup: str) -> str:
    return f"{base_setup}_ct"


def _step_once(setup_name: str, control: float) -> np.ndarray:
    setup = create_setup(setup_name)
    dt = float(get_setup_config(setup_name)["dt"])
    state = setup.initial_state()
    return setup.integrate_one_step(state, control, 0.0, dt)


def test_setup_registry_includes_all_supported_variants():
    names = available_setup_names()
    expected = {_dt_variant(base) for base in BASE_SETUPS} | {
        _ct_variant(base) for base in BASE_SETUPS
    } | set(EXTRA_DT_VARIANTS)

    assert set(names) == expected
    for base in BASE_SETUPS:
        assert base not in names


def test_variant_configs_have_expected_sampling_and_shared_fields():
    for base, dt_value in DT_VARIANT_DT.items():
        cfg_dt = get_setup_config(_dt_variant(base))
        cfg_ct = get_setup_config(_ct_variant(base))

        expected_ct_dt = min(float(dt_value) / 10.0, 0.001)

        assert float(cfg_dt["dt"]) == float(dt_value)
        assert float(cfg_ct["dt"]) == expected_ct_dt
        assert float(cfg_ct["horizon_sec"]) == float(cfg_dt["horizon_sec"])
        assert int(cfg_ct["warmup_samples"]) == int(cfg_dt["warmup_samples"])
        assert float(cfg_ct["step_ref"]) == float(cfg_dt["step_ref"])

    for variant_name, base in EXTRA_DT_VARIANTS.items():
        cfg_dt = get_setup_config(_dt_variant(base))
        cfg_nl = get_setup_config(variant_name)
        expected_dt = EXTRA_DT_VARIANT_DT_OVERRIDES.get(variant_name, cfg_dt["dt"])
        expected_horizon = EXTRA_DT_VARIANT_HORIZON_OVERRIDES.get(
            variant_name,
            cfg_dt["horizon_sec"],
        )
        expected_step_ref = EXTRA_DT_VARIANT_STEP_REF_OVERRIDES.get(
            variant_name,
            cfg_dt["step_ref"],
        )
        assert float(cfg_nl["dt"]) == float(expected_dt)
        assert float(cfg_nl["horizon_sec"]) == float(expected_horizon)
        assert int(cfg_nl["warmup_samples"]) == int(cfg_dt["warmup_samples"])
        assert float(cfg_nl["step_ref"]) == float(expected_step_ref)


@pytest.mark.parametrize(
    "setup_name",
    [f"{base}_{mode}" for base in BASE_SETUPS for mode in ("dt", "ct")]
    + list(EXTRA_DT_VARIANTS),
)
def test_create_setup_returns_expected_variant_name(setup_name: str):
    setup = create_setup(setup_name)
    assert setup.name == setup_name


def test_invertedpendulum_dt_nl_quanserip02_applies_params_and_nonlinear_mode():
    setup = create_setup("invertedpendulum_dt_nl_quanserip02")

    assert setup.M == pytest.approx(0.57)
    assert setup.m == pytest.approx(0.230)
    assert setup.b == pytest.approx(5.4)
    assert setup.I == pytest.approx(7.88e-3)
    assert setup.g == pytest.approx(9.81)
    assert setup.l == pytest.approx(0.3302)
    assert setup._use_nonlinear is True


def test_invertedpendulum_dt_nl_lim_quanserip02_applies_params_nonlinear_and_limit():
    setup = create_setup("invertedpendulum_dt_nl_lim_quanserip02")

    assert setup.M == pytest.approx(0.57)
    assert setup.m == pytest.approx(0.230)
    assert setup.b == pytest.approx(5.4)
    assert setup.I == pytest.approx(7.88e-3)
    assert setup.g == pytest.approx(9.81)
    assert setup.l == pytest.approx(0.3302)
    assert setup.actuator_force_limit_n == pytest.approx(13.44)
    assert setup._use_nonlinear is True


def test_invertedpendulum_dt_nl_lim_quanserip02_clamps_to_pm_13_44_newton():
    limited_hi = _step_once("invertedpendulum_dt_nl_lim_quanserip02", 1e6)
    expected_hi = _step_once("invertedpendulum_dt_nl_lim_quanserip02", 13.44)
    assert np.allclose(limited_hi, expected_hi, rtol=1e-12, atol=1e-12)

    limited_lo = _step_once("invertedpendulum_dt_nl_lim_quanserip02", -1e6)
    expected_lo = _step_once("invertedpendulum_dt_nl_lim_quanserip02", -13.44)
    assert np.allclose(limited_lo, expected_lo, rtol=1e-12, atol=1e-12)


def test_invertedpendulum_dt_nl_quanserip02_variant_remains_unclamped():
    at_limit = _step_once("invertedpendulum_dt_nl_quanserip02", 13.44)
    above_limit = _step_once("invertedpendulum_dt_nl_quanserip02", 14.0)
    assert float(above_limit[1]) > float(at_limit[1])


def test_signal_metadata_is_defined_for_all_required_series():
    for base, expected_meta in EXPECTED_SIGNALS.items():
        assert get_setup_signal_metadata(_dt_variant(base)) == expected_meta
        assert get_setup_signal_metadata(_ct_variant(base)) == expected_meta
    for variant_name, base in EXTRA_DT_VARIANTS.items():
        assert get_setup_signal_metadata(variant_name) == EXPECTED_SIGNALS[base]


def test_server_cli_accepts_variant_setup_names():
    parser = build_parser()
    args = parser.parse_args(
        ["--port", "9000", "-s", "suspension_ct", "-i", "exp_a", "-a", "2"]
    )
    assert args.setup == "suspension_ct"
    assert args.experiment_id == "exp_a"
    assert args.design_attempt == 2


def test_server_cli_rejects_legacy_setup_names():
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["--port", "9000", "-s", "motorspeed", "-i", "exp_a", "-a", "0"])


def test_server_cli_rejects_negative_design_attempt():
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(
            ["--port", "9000", "-s", "motorspeed_dt", "-i", "exp_a", "-a", "-1"]
        )
