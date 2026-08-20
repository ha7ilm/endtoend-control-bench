"""Setup variant registry for control server configuration and instantiation."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from .setups.aircraftpitch import AircraftPitchSetup
from .setups.ballandbeam import BallAndBeamSetup
from .setups.base import BaseSetup
from .setups.cruisecontrol import CruiseControlSetup
from .setups.invertedpendulum import InvertedPendulumSetup
from .setups.motorposition import MotorPositionSetup
from .setups.motorspeed import MotorSpeedSetup
from .setups.suspension import SuspensionSetup

_CT_DT_SCALE = 10.0
_CT_DT_MAX_SEC = 0.001

_MOTORSPEED_DT_CONFIG = {
    # motorspeed_digital.m uses Ts=0.05 and evaluates the final design over 8 seconds.
    "dt": 0.05,
    "horizon_sec": 8.0,
    "warmup_samples": 2,
    "step_ref": 1.0,
    "signals": {
        "ref": {"display_name": "Speed reference", "unit": "rad/sec"},
        "meas": {"display_name": "Measured speed", "unit": "rad/sec"},
        "control": {"display_name": "Armature voltage", "unit": "V"},
    },
}

_MOTORSPEED_DT_LIM_MAXONRE30_CONFIG = {
    # Maxon RE30 variant with added payload inertia:
    # - faster sample time than CTMS motor
    # - shorter horizon to keep runtime manageable while preserving KPI evaluation window
    # - larger speed reference step for this high-capability variant
    **_MOTORSPEED_DT_CONFIG,
    "dt": 0.001,
    "horizon_sec": 5.0,
    "step_ref": 100.0,
}

_CRUISECONTROL_DT_CONFIG = {
    # cruisecontrol_digital.m uses Ts=1/50 and evaluates the final design over 10 seconds.
    "dt": 0.02,
    "horizon_sec": 10.0,
    "warmup_samples": 2,
    "step_ref": 10.0,
    "signals": {
        "ref": {"display_name": "Speed reference", "unit": "m/s"},
        "meas": {"display_name": "Measured speed", "unit": "m/s"},
        "control": {"display_name": "Traction force", "unit": "N"},
    },
}

# Maxon RE 30 (part 310008, 36 V winding) from:
# https://www.maxongroup.com/medias/sys_master/root/9398013132830/Cataloge-Page-EN-160.pdf
# b is estimated from no-load data: b ~= K * I0 / omega0.
#
# Added load for this setup: 200 g at 20 mm radius (directly reflected to shaft):
# J_load = m * r^2 = 0.2 * 0.02^2 = 8.0e-5 kg*m^2
_MOTORSPEED_RE30_ROTOR_INERTIA = 3.31e-6
_MOTORSPEED_RE30_PAYLOAD_INERTIA = 0.2 * (0.02**2)
_MOTORSPEED_RE30_MODEL_PARAMS = {
    "J": _MOTORSPEED_RE30_ROTOR_INERTIA + _MOTORSPEED_RE30_PAYLOAD_INERTIA,  # kg*m^2
    "b": 4.6899385838143515e-6,  # N*m*s/rad (estimated)
    "K": 0.0398,  # N*m/A (39.8 mNm/A)
    "R": 1.43,  # Ohm
    "L": 0.281e-3,  # H (0.281 mH)
    "actuator_voltage_limit_volts": 36.0,  # V
}


@dataclass(frozen=True)
class SetupVariantSpec:
    """Concrete variant specification that maps to one setup class instance."""

    setup_cls: type[BaseSetup]
    config: dict[str, Any]
    model_params: dict[str, float]


def _ct_dt_from_dt_variant(dt_variant: float) -> float:
    return min(float(dt_variant) / _CT_DT_SCALE, _CT_DT_MAX_SEC)


def _build_pair(
    base_name: str,
    setup_cls: type[BaseSetup],
    dt_config: dict[str, Any],
    *,
    model_params: dict[str, float] | None = None,
) -> dict[str, SetupVariantSpec]:
    dt_name = f"{base_name}_dt"
    ct_name = f"{base_name}_ct"

    dt_variant_config = deepcopy(dt_config)
    ct_variant_config = deepcopy(dt_variant_config)
    ct_variant_config["dt"] = _ct_dt_from_dt_variant(float(dt_variant_config["dt"]))

    params = dict(model_params or {})
    return {
        dt_name: SetupVariantSpec(
            setup_cls=setup_cls,
            config=dt_variant_config,
            model_params=dict(params),
        ),
        ct_name: SetupVariantSpec(
            setup_cls=setup_cls,
            config=ct_variant_config,
            model_params=dict(params),
        ),
    }


def _build_dt_only(
    variant_name: str,
    setup_cls: type[BaseSetup],
    dt_config: dict[str, Any],
    *,
    model_params: dict[str, float] | None = None,
) -> dict[str, SetupVariantSpec]:
    dt_variant_config = deepcopy(dt_config)
    params = dict(model_params or {})
    return {
        variant_name: SetupVariantSpec(
            setup_cls=setup_cls,
            config=dt_variant_config,
            model_params=dict(params),
        )
    }


SETUP_VARIANTS: dict[str, SetupVariantSpec] = {
    **_build_pair(
        base_name="motorspeed",
        setup_cls=MotorSpeedSetup,
        dt_config=_MOTORSPEED_DT_CONFIG,
    ),
    **_build_dt_only(
        variant_name="motorspeed_dt_lim",
        setup_cls=MotorSpeedSetup,
        dt_config=_MOTORSPEED_DT_CONFIG,
    ),
    **_build_dt_only(
        variant_name="motorspeed_dt_lim_maxonre30",
        setup_cls=MotorSpeedSetup,
        dt_config=_MOTORSPEED_DT_LIM_MAXONRE30_CONFIG,
        model_params=_MOTORSPEED_RE30_MODEL_PARAMS,
    ),
    **_build_pair(
        base_name="motorposition",
        setup_cls=MotorPositionSetup,
        dt_config={
            # motorposition_digital.m uses Ts=0.001 and checks disturbance response over 0.25 seconds.
            "dt": 0.001,
            "horizon_sec": 0.25,
            "warmup_samples": 2,
            "step_ref": 1.0,
            "signals": {
                "ref": {"display_name": "Position reference", "unit": "rad"},
                "meas": {"display_name": "Measured position", "unit": "rad"},
                "control": {"display_name": "Armature voltage", "unit": "V"},
            },
        },
    ),
    **_build_pair(
        base_name="aircraftpitch",
        setup_cls=AircraftPitchSetup,
        dt_config={
            # aircraftpitch_digital.m uses Ts=1/100 and evaluates over 10 seconds.
            "dt": 0.01,
            "horizon_sec": 10.0,
            "warmup_samples": 2,
            "step_ref": 0.2,
            "signals": {
                "ref": {"display_name": "Pitch reference", "unit": "rad"},
                "meas": {"display_name": "Measured pitch angle", "unit": "rad"},
                "control": {"display_name": "Elevator deflection", "unit": "rad"},
            },
        },
    ),
    **_build_pair(
        base_name="ballandbeam",
        setup_cls=BallAndBeamSetup,
        dt_config={
            # ballandbeam_digital.m uses Ts=1/50 and step(..., 5).
            "dt": 0.02,
            "horizon_sec": 5.0,
            "warmup_samples": 2,
            "step_ref": 0.25,
            "signals": {
                "ref": {"display_name": "Ball position reference", "unit": "m"},
                "meas": {"display_name": "Measured ball position", "unit": "m"},
                "control": {"display_name": "Gear angle command", "unit": "rad"},
            },
        },
    ),
    **_build_dt_only(
        variant_name="ballandbeam_dt_nl",
        setup_cls=BallAndBeamSetup,
        dt_config={
            # Nonlinear DT variant keeps the same sample-time and reference config as CTMS.
            "dt": 0.02,
            "horizon_sec": 5.0,
            "warmup_samples": 2,
            "step_ref": 0.25,
            "signals": {
                "ref": {"display_name": "Ball position reference", "unit": "m"},
                "meas": {"display_name": "Measured ball position", "unit": "m"},
                "control": {"display_name": "Gear angle command", "unit": "rad"},
            },
        },
    ),
    **_build_dt_only(
        variant_name="ballandbeam_dt_nl_act",
        setup_cls=BallAndBeamSetup,
        dt_config={
            # Nonlinear DT + actuator variant keeps the same sample-time/reference config.
            "dt": 0.02,
            "horizon_sec": 5.0,
            "warmup_samples": 2,
            "step_ref": 0.25,
            "signals": {
                "ref": {"display_name": "Ball position reference", "unit": "m"},
                "meas": {"display_name": "Measured ball position", "unit": "m"},
                "control": {"display_name": "Gear angle command", "unit": "rad"},
            },
        },
    ),
    **_build_dt_only(
        variant_name="ballandbeam_dt_nl_act_mg996r",
        setup_cls=BallAndBeamSetup,
        dt_config={
            # MG996R-like nonlinear DT + actuator variant keeps the same sample-time/reference config.
            "dt": 0.02,
            "horizon_sec": 5.0,
            "warmup_samples": 2,
            "step_ref": 0.25,
            "signals": {
                "ref": {"display_name": "Ball position reference", "unit": "m"},
                "meas": {"display_name": "Measured ball position", "unit": "m"},
                "control": {"display_name": "Gear angle command", "unit": "rad"},
            },
        },
        model_params={
            # MG996R-style approximation:
            # - speed limit around 5.5..7.0 rad/s
            # - first-order actuator lag around 0.10..0.15 s
            # - positional travel around +/-60 deg (120 deg total)
            "actuator_theta_dot_limit_rad_per_sec": 6.0,
            "actuator_tau_sec": 0.12,
            "actuator_theta_limit_rad": 1.0471975511965976,
            # Requested geometry adjustments for this setup.
            "d": 0.035,
            "L": 0.5,
        },
    ),
    **_build_pair(
        base_name="cruisecontrol",
        setup_cls=CruiseControlSetup,
        dt_config=_CRUISECONTROL_DT_CONFIG,
    ),
    **_build_dt_only(
        variant_name="cruisecontrol_dt_lim_hondajazz",
        setup_cls=CruiseControlSetup,
        dt_config=_CRUISECONTROL_DT_CONFIG,
        model_params={
            "m": 1240.0,
            "b": 50.0,
            "traction_force_max_n": 2480.0,
            "traction_force_min_n": -4340.0,
        },
    ),
    **_build_pair(
        base_name="suspension",
        setup_cls=SuspensionSetup,
        dt_config={
            # suspension_digital.m selects T=0.0005 and simulates 5-second responses.
            "dt": 0.0005,
            "horizon_sec": 5.0,
            "warmup_samples": 2,
            "step_ref": 0.1,
            "signals": {
                "ref": {"display_name": "Suspension travel target", "unit": "m"},
                "meas": {"display_name": "Suspension travel X1-X2", "unit": "m"},
                "control": {"display_name": "Actuator force", "unit": "N"},
            },
        },
    ),
    **_build_pair(
        base_name="invertedpendulum",
        setup_cls=InvertedPendulumSetup,
        dt_config={
            # invertedpendulum_digital.m uses Ts=1/100 and evaluates over 5 seconds.
            "dt": 0.01,
            "horizon_sec": 5.0,
            "warmup_samples": 2,
            "step_ref": 0.2,
            "signals": {
                "ref": {"display_name": "Cart/Pendulum reference", "unit": "mixed"},
                "meas": {"display_name": "Cart/Pendulum measurement", "unit": "mixed"},
                "control": {"display_name": "Cart force", "unit": "N"},
            },
        },
    ),
    **_build_dt_only(
        variant_name="invertedpendulum_dt_nl",
        setup_cls=InvertedPendulumSetup,
        dt_config={
            # Nonlinear DT variant keeps the same sample-time and reference config as CTMS.
            "dt": 0.01,
            "horizon_sec": 5.0,
            "warmup_samples": 2,
            "step_ref": 0.2,
            "signals": {
                "ref": {"display_name": "Cart/Pendulum reference", "unit": "mixed"},
                "meas": {"display_name": "Cart/Pendulum measurement", "unit": "mixed"},
                "control": {"display_name": "Cart force", "unit": "N"},
            },
        },
    ),
    **_build_dt_only(
        variant_name="invertedpendulum_dt_nl_quanserip02",
        setup_cls=InvertedPendulumSetup,
        dt_config={
            # Quanser IP02 nonlinear DT variant keeps the same sample-time/reference config.
            "dt": 0.01,
            "horizon_sec": 5.0,
            "warmup_samples": 2,
            "step_ref": 0.2,
            "signals": {
                "ref": {"display_name": "Cart/Pendulum reference", "unit": "mixed"},
                "meas": {"display_name": "Cart/Pendulum measurement", "unit": "mixed"},
                "control": {"display_name": "Cart force", "unit": "N"},
            },
        },
        model_params={
            # Quanser IP02 + SIP (long pendulum) parameterization.
            "M": 0.57,
            "m": 0.230,
            "b": 5.4,
            "I": 7.88e-3,
            "g": 9.81,
            "l": 0.3302,
        },
    ),
    **_build_dt_only(
        variant_name="invertedpendulum_dt_nl_lim_quanserip02",
        setup_cls=InvertedPendulumSetup,
        dt_config={
            # Quanser IP02 nonlinear DT variant with actuator force limitation.
            "dt": 0.01,
            "horizon_sec": 5.0,
            "warmup_samples": 2,
            "step_ref": 0.2,
            "signals": {
                "ref": {"display_name": "Cart/Pendulum reference", "unit": "mixed"},
                "meas": {"display_name": "Cart/Pendulum measurement", "unit": "mixed"},
                "control": {"display_name": "Cart force", "unit": "N"},
            },
        },
        model_params={
            # Quanser IP02 + SIP (long pendulum) parameterization.
            "M": 0.57,
            "m": 0.230,
            "b": 5.4,
            "I": 7.88e-3,
            "g": 9.81,
            "l": 0.3302,
            # Approximate peak actuator force from 3 A peak current.
            "actuator_force_limit_n": 13.44,
        },
    ),
}


def get_setup_variant_spec(name: str) -> SetupVariantSpec:
    spec = SETUP_VARIANTS.get(name)
    if spec is None:
        raise ValueError(f"Unknown setup '{name}'.")
    return spec


def available_setup_variant_names() -> tuple[str, ...]:
    return tuple(sorted(SETUP_VARIANTS))


def create_setup_variant(name: str) -> BaseSetup:
    spec = get_setup_variant_spec(name)
    return spec.setup_cls(variant_name=name, model_params=spec.model_params)
