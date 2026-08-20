TEST_MODULE = "tests/test_machine_client_config.py"

REASONS_BY_TEST = {
    "test_machine_client_requires_setup_description_and_why": (
        "Ensure MachineClient constructor contract remains explicit: mandatory setup/description/why arguments must be "
        "provided, otherwise TypeError is raised."
    ),
    "test_machine_client_allows_empty_description_and_why": (
        "Allow intentionally blank description/why strings so callers can suppress narrative text without breaking "
        "object creation."
    ),
    "test_machine_client_defaults_host_and_port": (
        "Verify fallback behavior when environment is unset: host defaults to 127.0.0.1 and port defaults to 9000. "
        "This protects the client's zero-configuration connection behavior."
    ),
    "test_machine_client_uses_host_env": (
        "Confirm valid URLETRA_MACHINE_HOST/PORT values override the connection defaults. "
        "This protects environment-based configuration used by remote client deployments."
    ),
    "test_machine_client_invalid_port_env_warns_and_defaults": (
        "For invalid port env values ('', bad, 0, 70000), enforce safe fallback to 9000 and warning emission instead of "
        "accepting malformed runtime configuration."
    ),
    "test_machine_client_logs_run_to_files_by_default": (
        "Ensure run file logging defaults to enabled when URLETRA_MACHINECLIENT_LOG_RUN_TO_FILES is unset."
    ),
    "test_machine_client_can_disable_run_file_logging_via_env": (
        "Confirm URLETRA_MACHINECLIENT_LOG_RUN_TO_FILES=0 is the explicit off-switch for per-run file logging."
    ),
    "test_machine_client_nonzero_log_env_keeps_logging_enabled": (
        "Verify nonzero or non-'0' environment values do not accidentally disable automatic run output logging."
    ),
}

REASONS_BY_NODEID = {}
