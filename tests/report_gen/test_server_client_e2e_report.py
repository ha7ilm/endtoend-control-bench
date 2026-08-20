TEST_MODULE = "tests/test_server_client_e2e.py"

REASONS_BY_TEST = {
    "test_server_client_two_runs_save_incremented_files": (
        "Run a real server/client session twice and verify run index incrementing, persisted trace schema (including llm_said "
        "and disturbance), and orderly server shutdown."
    ),
    "test_machine_client_logs_timeseries_and_kpis_files_by_default": (
        "Validate default MachineClient run logging writes response/kpi files, exposes their paths in output_files, and "
        "persists expected CSV/JSON content."
    ),
    "test_machine_client_logs_map_signals_with_prefixed_columns": (
        "Confirm map-valued ref/meas channels are flattened to deterministic ref_* and meas_* CSV columns for run logging."
    ),
    "test_machine_client_logging_disabled_omits_output_files": (
        "Ensure URLETRA_MACHINECLIENT_LOG_RUN_TO_FILES=0 disables run-output file emission and keeps the terminal payload "
        "free of output_files metadata."
    ),
    "test_server_rejects_client_hello_with_setup_mismatch": (
        "Ensure handshake validation rejects clients whose setup name does not match server setup, returning a runtime error "
        "instead of silently running mismatched plants."
    ),
}

REASONS_BY_NODEID = {}
