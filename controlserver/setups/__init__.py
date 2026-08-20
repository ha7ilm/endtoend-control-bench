"""Setup registry for control server."""

from __future__ import annotations

from .aircraftpitch import AircraftPitchSetup
from .ballandbeam import BallAndBeamSetup
from .base import BaseSetup
from .cruisecontrol import CruiseControlSetup
from .invertedpendulum import InvertedPendulumSetup
from .motorposition import MotorPositionSetup
from .motorspeed import MotorSpeedSetup
from .suspension import SuspensionSetup

def create_setup(name: str) -> BaseSetup:
    from ..setup_variants import create_setup_variant

    return create_setup_variant(name)


def available_setup_names() -> tuple[str, ...]:
    from ..setup_variants import available_setup_variant_names

    return available_setup_variant_names()


__all__ = [
    "available_setup_names",
    "create_setup",
    "BaseSetup",
    "AircraftPitchSetup",
    "BallAndBeamSetup",
    "MotorSpeedSetup",
    "MotorPositionSetup",
    "CruiseControlSetup",
    "SuspensionSetup",
    "InvertedPendulumSetup",
]
