TEST_MODULE = "tests/test_packaging_namespace.py"

REASONS_BY_TEST = {
    "test_urletra_namespace_exposes_controlclient": (
        "Confirm the installed namespace package surface exports urletra.controlclient as intended by packaging contract."
    ),
    "test_urletra_controlclient_exports_machine_client": (
        "Ensure MachineClient remains part of the public installed API for downstream consumers."
    ),
}

REASONS_BY_NODEID = {}
