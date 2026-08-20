import csv
import json
import socket
import threading
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from controlclient.machine import MachineClient
from controlserver.server import run_server


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def run_simple_controller_client(gain: float = 1.0) -> dict[str, Any]:
    with MachineClient(
        setup="motorspeed_dt",
        description="P(1) smoke-test controller",
        why="Quick e2e sanity run for protocol and persistence behavior.",
    ) as machine:
        while True:
            ctl_input = machine.read()
            if ctl_input["done"]:
                return ctl_input

            error = ctl_input["ref"] - ctl_input["meas"]
            machine.write({"control": gain * error})


def run_invertedpendulum_x_cart_controller_client() -> dict[str, Any]:
    with MachineClient(
        setup="invertedpendulum_dt",
        description="WP P(1) smoke-test controller",
        why="Use x_cart channel error only to verify map-signal logging columns.",
    ) as machine:
        while True:
            ctl_input = machine.read()
            if ctl_input["done"]:
                return ctl_input

            ref = ctl_input["ref"]
            meas = ctl_input["meas"]
            control = float(ref["x_cart"]) - float(meas["x_cart"])
            machine.write({"control": control})


def test_server_client_two_runs_save_incremented_files(tmp_path, monkeypatch):
    port = find_free_port()
    ready_event = threading.Event()

    server_thread = threading.Thread(
        target=run_server,
        kwargs={
            "port": port,
            "setup_name": "motorspeed_dt",
            "experiment_id": "e2e_case",
            "design_attempt": 3,
            "host": "127.0.0.1",
            "result_root": tmp_path,
            "ready_event": ready_event,
            "max_connections": 2,
        },
        daemon=True,
    )
    server_thread.start()

    ready_event.wait(timeout=5.0)
    assert ready_event.is_set(), "Server did not become ready in time."

    monkeypatch.setenv("URLETRA_MACHINE_PORT", str(port))
    monkeypatch.delenv("URLETRA_MACHINE_HOST", raising=False)
    monkeypatch.setenv("URLETRA_MACHINECLIENT_LOG_RUN_TO_FILES", "0")

    final_run1 = run_simple_controller_client()
    final_run2 = run_simple_controller_client()

    kpis_run1 = final_run1["kpis"]
    kpis_run2 = final_run2["kpis"]

    assert "settling_time_sec" in kpis_run1
    assert "settling_time_sec" in kpis_run2
    assert "output_files" not in final_run1
    assert "output_files" not in final_run2

    server_thread.join(timeout=5.0)
    assert not server_thread.is_alive()

    result_dir = tmp_path / "motorspeed_dt" / "e2e_case" / "attempt3"
    run0_path = result_dir / "run0.npy"
    run1_path = result_dir / "run1.npy"

    assert run0_path.exists()
    assert run1_path.exists()

    run0 = np.load(run0_path, allow_pickle=True).item()
    run1 = np.load(run1_path, allow_pickle=True).item()

    for run_data in (run0, run1):
        assert run_data["setup"] == "motorspeed_dt"
        assert "time_sec" in run_data
        assert "ref" in run_data
        assert "meas" in run_data
        assert "control" in run_data
        assert "disturbance" in run_data
        assert "kpis" in run_data
        assert run_data["llm_said"]["setup"] == "motorspeed_dt"
        assert run_data["llm_said"]["description"] == "P(1) smoke-test controller"
        assert "sanity run" in run_data["llm_said"]["why"]
        assert np.allclose(run_data["disturbance"], 0.0)


def test_machine_client_logs_timeseries_and_kpis_files_by_default(tmp_path, monkeypatch):
    port = find_free_port()
    ready_event = threading.Event()

    server_thread = threading.Thread(
        target=run_server,
        kwargs={
            "port": port,
            "setup_name": "motorspeed_dt",
            "experiment_id": "e2e_logging_default",
            "design_attempt": 0,
            "host": "127.0.0.1",
            "result_root": tmp_path,
            "ready_event": ready_event,
            "max_connections": 1,
        },
        daemon=True,
    )
    server_thread.start()

    ready_event.wait(timeout=5.0)
    assert ready_event.is_set(), "Server did not become ready in time."

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("URLETRA_MACHINE_PORT", str(port))
    monkeypatch.delenv("URLETRA_MACHINE_HOST", raising=False)
    monkeypatch.delenv("URLETRA_MACHINECLIENT_LOG_RUN_TO_FILES", raising=False)

    final_message = run_simple_controller_client()

    assert "kpis" in final_message
    assert "output_files" in final_message

    output_files = final_message["output_files"]
    assert output_files["response_timeseries_csv"].startswith("run_outputs/")
    assert output_files["kpis_json"].startswith("run_outputs/")

    timeseries_path = tmp_path / Path(output_files["response_timeseries_csv"])
    kpis_path = tmp_path / Path(output_files["kpis_json"])

    assert timeseries_path.exists()
    assert kpis_path.exists()

    with timeseries_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        assert reader.fieldnames is not None
        assert reader.fieldnames[0] == "step_index"
        assert {"ref", "meas", "control"}.issubset(set(reader.fieldnames))
        rows = list(reader)

    assert rows
    for step_index, row in enumerate(rows):
        assert int(row["step_index"]) == step_index

    with kpis_path.open("r", encoding="utf-8") as handle:
        kpis_from_file = json.load(handle)

    assert kpis_from_file == final_message["kpis"]

    server_thread.join(timeout=5.0)
    assert not server_thread.is_alive()


def test_machine_client_logs_map_signals_with_prefixed_columns(tmp_path, monkeypatch):
    port = find_free_port()
    ready_event = threading.Event()

    server_thread = threading.Thread(
        target=run_server,
        kwargs={
            "port": port,
            "setup_name": "invertedpendulum_dt",
            "experiment_id": "e2e_logging_map_signals",
            "design_attempt": 0,
            "host": "127.0.0.1",
            "result_root": tmp_path,
            "ready_event": ready_event,
            "max_connections": 1,
        },
        daemon=True,
    )
    server_thread.start()

    ready_event.wait(timeout=5.0)
    assert ready_event.is_set(), "Server did not become ready in time."

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("URLETRA_MACHINE_PORT", str(port))
    monkeypatch.delenv("URLETRA_MACHINE_HOST", raising=False)
    monkeypatch.delenv("URLETRA_MACHINECLIENT_LOG_RUN_TO_FILES", raising=False)

    final_message = run_invertedpendulum_x_cart_controller_client()
    output_files = final_message["output_files"]
    timeseries_path = tmp_path / Path(output_files["response_timeseries_csv"])
    assert timeseries_path.exists()

    with timeseries_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        assert reader.fieldnames is not None
        assert reader.fieldnames[0] == "step_index"
        assert {
            "ref_x_cart",
            "ref_phi_angle",
            "meas_x_cart",
            "meas_phi_angle",
            "control",
        }.issubset(set(reader.fieldnames))
        rows = list(reader)

    assert rows

    server_thread.join(timeout=5.0)
    assert not server_thread.is_alive()


def test_machine_client_logging_disabled_omits_output_files(tmp_path, monkeypatch):
    port = find_free_port()
    ready_event = threading.Event()

    server_thread = threading.Thread(
        target=run_server,
        kwargs={
            "port": port,
            "setup_name": "motorspeed_dt",
            "experiment_id": "e2e_logging_disabled",
            "design_attempt": 0,
            "host": "127.0.0.1",
            "result_root": tmp_path,
            "ready_event": ready_event,
            "max_connections": 1,
        },
        daemon=True,
    )
    server_thread.start()

    ready_event.wait(timeout=5.0)
    assert ready_event.is_set(), "Server did not become ready in time."

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("URLETRA_MACHINE_PORT", str(port))
    monkeypatch.delenv("URLETRA_MACHINE_HOST", raising=False)
    monkeypatch.setenv("URLETRA_MACHINECLIENT_LOG_RUN_TO_FILES", "0")

    final_message = run_simple_controller_client()

    assert "kpis" in final_message
    assert "output_files" not in final_message
    assert not (tmp_path / "run_outputs").exists()

    server_thread.join(timeout=5.0)
    assert not server_thread.is_alive()


def test_server_rejects_client_hello_with_setup_mismatch(tmp_path, monkeypatch):
    port = find_free_port()
    ready_event = threading.Event()

    server_thread = threading.Thread(
        target=run_server,
        kwargs={
            "port": port,
            "setup_name": "motorspeed_dt",
            "experiment_id": "e2e_mismatch",
            "design_attempt": 0,
            "host": "127.0.0.1",
            "result_root": tmp_path,
            "ready_event": ready_event,
            "max_connections": 1,
        },
        daemon=True,
    )
    server_thread.start()
    ready_event.wait(timeout=5.0)
    assert ready_event.is_set(), "Server did not become ready in time."

    monkeypatch.setenv("URLETRA_MACHINE_PORT", str(port))
    monkeypatch.delenv("URLETRA_MACHINE_HOST", raising=False)
    monkeypatch.setenv("URLETRA_MACHINECLIENT_LOG_RUN_TO_FILES", "0")

    with pytest.raises(RuntimeError, match="does not match server setup"):
        with MachineClient(
            setup="motorposition_dt",
            description="Wrong setup test",
            why="Intentional mismatch should be rejected by server.",
        ) as machine:
            machine.read()

    server_thread.join(timeout=5.0)
    assert not server_thread.is_alive()
