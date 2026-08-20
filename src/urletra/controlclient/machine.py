"""TCP client library for the feedback loop server."""

from __future__ import annotations

import csv
import json
import math
import os
import socket
import time
from pathlib import Path
from typing import Any, Mapping

from urletra._common.protocol import read_message, write_message


class MachineClient:
    """Small client API to exchange controller I/O with the server."""

    _DEFAULT_HOST = "127.0.0.1"
    _DEFAULT_PORT = 9000
    _TIMEOUT_SEC = 30.0
    _OUTPUT_DIR_NAME = "run_outputs"

    def __init__(self, setup: str, description: str, why: str):
        self.setup = self._require_non_empty_text(setup, "setup")
        self.description = self._require_text(description, "description")
        self.why = self._require_text(why, "why")
        self.host = self._resolve_host()
        self.port = self._resolve_port()
        self.log_run_to_files = self._resolve_log_run_to_files()
        self.timeout_sec = self._TIMEOUT_SEC
        self._sock: socket.socket | None = None
        self._hello_sent = False
        self._input_samples: list[dict[str, Any]] = []
        self._control_samples: list[float] = []

    @staticmethod
    def _require_non_empty_text(value: str, field: str) -> str:
        if not isinstance(value, str):
            raise TypeError(f"{field} must be a string.")
        stripped = value.strip()
        if not stripped:
            raise ValueError(f"{field} must be a non-empty string.")
        return stripped

    @staticmethod
    def _require_text(value: str, field: str) -> str:
        if not isinstance(value, str):
            raise TypeError(f"{field} must be a string.")
        return value

    def _resolve_host(self) -> str:
        host = os.getenv("URLETRA_MACHINE_HOST")
        if host is None:
            return self._DEFAULT_HOST
        host = host.strip()
        if not host:
            return self._DEFAULT_HOST
        return host

    def _resolve_port(self) -> int:
        raw_port = os.getenv("URLETRA_MACHINE_PORT")
        if raw_port is None:
            return self._DEFAULT_PORT

        raw_port = raw_port.strip()
        if not raw_port:
            print(
                "[controlclient] Warning: URLETRA_MACHINE_PORT is empty; defaulting to 9000."
            )
            return self._DEFAULT_PORT

        try:
            port = int(raw_port)
        except ValueError:
            print(
                "[controlclient] Warning: URLETRA_MACHINE_PORT must be an integer; "
                "defaulting to 9000."
            )
            return self._DEFAULT_PORT

        if port < 1 or port > 65535:
            print(
                "[controlclient] Warning: URLETRA_MACHINE_PORT must be in [1, 65535]; "
                "defaulting to 9000."
            )
            return self._DEFAULT_PORT
        return port

    def _resolve_log_run_to_files(self) -> bool:
        raw_value = os.getenv("URLETRA_MACHINECLIENT_LOG_RUN_TO_FILES")
        if raw_value is None:
            return True
        return raw_value.strip() != "0"

    def _reset_run_buffers(self) -> None:
        self._input_samples.clear()
        self._control_samples.clear()

    def connect(self) -> "MachineClient":
        if self._sock is None:
            sock = socket.create_connection((self.host, self.port), timeout=self.timeout_sec)
            sock.settimeout(self.timeout_sec)
            self._sock = sock
            self._send_client_hello()
        return self

    def close(self) -> None:
        if self._sock is not None:
            self._sock.close()
            self._sock = None
            self._hello_sent = False
        self._reset_run_buffers()

    def _send_client_hello(self) -> None:
        if self._hello_sent:
            return
        sock = self._ensure_connected()
        write_message(
            sock,
            {
                "type": "client_hello",
                "setup": self.setup,
                "description": self.description,
                "why": self.why,
            },
        )
        self._hello_sent = True

    def __enter__(self) -> "MachineClient":
        return self.connect()

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def _ensure_connected(self) -> socket.socket:
        if self._sock is None:
            self.connect()
        assert self._sock is not None
        return self._sock

    def read(self) -> dict[str, Any]:
        """Read one controller input message from server."""
        sock = self._ensure_connected()
        message = read_message(sock)

        msg_type = message.get("type")
        if msg_type == "error":
            raise RuntimeError(f"Server error: {message.get('message', '')}")
        if msg_type != "controller_input":
            raise RuntimeError(f"Unexpected message type '{msg_type}'.")

        done = bool(message.get("done", False))
        if done:
            final_message = dict(message)
            try:
                if self.log_run_to_files:
                    output_files = self._write_run_outputs(final_message)
                    final_message["output_files"] = output_files
            except Exception as exc:
                raise RuntimeError(f"Failed to write run log files: {exc}") from exc
            finally:
                self._reset_run_buffers()
            return final_message

        self._record_input_sample(message)
        return message

    def write(self, controller_output: Mapping[str, Any]) -> None:
        """Write one controller output message to server."""
        sock = self._ensure_connected()

        if "type" in controller_output and controller_output["type"] != "controller_output":
            raise ValueError("Controller output message type must be 'controller_output'.")

        message = dict(controller_output)
        message["type"] = "controller_output"
        write_message(sock, message)
        if self.log_run_to_files:
            self._record_control_sample(message)

    @staticmethod
    def _normalize_signal_value(
        value: Any,
        field: str,
    ) -> tuple[str, dict[str, float]]:
        if isinstance(value, Mapping):
            if not value:
                raise RuntimeError(f"Controller input '{field}' map must not be empty.")
            normalized: dict[str, float] = {}
            for key, raw_value in value.items():
                if not isinstance(key, str):
                    raise RuntimeError(f"Controller input '{field}' map keys must be strings.")
                key = key.strip()
                if not key:
                    raise RuntimeError(
                        f"Controller input '{field}' map keys must be non-empty strings."
                    )
                parsed = float(raw_value)
                if not math.isfinite(parsed):
                    raise RuntimeError(f"Controller input '{field}.{key}' must be finite.")
                normalized[key] = parsed
            return "map", normalized

        parsed = float(value)
        if not math.isfinite(parsed):
            raise RuntimeError(f"Controller input '{field}' must be finite.")
        return "scalar", {"": parsed}

    def _record_input_sample(self, message: Mapping[str, Any]) -> None:
        if "ref" not in message or "meas" not in message:
            raise RuntimeError("Controller input message must contain 'ref' and 'meas'.")
        ref_mode, ref_values = self._normalize_signal_value(message["ref"], "ref")
        meas_mode, meas_values = self._normalize_signal_value(message["meas"], "meas")
        self._input_samples.append(
            {
                "ref_mode": ref_mode,
                "ref_values": ref_values,
                "meas_mode": meas_mode,
                "meas_values": meas_values,
            }
        )

    def _record_control_sample(self, message: Mapping[str, Any]) -> None:
        if "control" not in message:
            raise ValueError("Controller output missing 'control'.")
        control = float(message["control"])
        if not math.isfinite(control):
            raise ValueError("Controller output 'control' must be finite.")
        self._control_samples.append(control)

    @staticmethod
    def _next_unique_file_pair() -> tuple[Path, Path, str]:
        output_dir = Path(MachineClient._OUTPUT_DIR_NAME)
        output_dir.mkdir(parents=True, exist_ok=True)

        while True:
            timestamp_ms = str(int(time.time() * 1000.0))
            timeseries_name = f"run_response_timeseries_{timestamp_ms}.csv"
            kpis_name = f"run_kpis_{timestamp_ms}.json"
            timeseries_path = output_dir / timeseries_name
            kpis_path = output_dir / kpis_name
            if not timeseries_path.exists() and not kpis_path.exists():
                return timeseries_path, kpis_path, timestamp_ms
            time.sleep(0.001)

    def _write_run_outputs(self, final_message: Mapping[str, Any]) -> dict[str, str]:
        if "kpis" not in final_message:
            raise RuntimeError("Final controller input is missing 'kpis'.")
        if len(self._input_samples) != len(self._control_samples):
            raise RuntimeError(
                "Controller input/output sample count mismatch while writing run outputs."
            )
        if not self._input_samples:
            raise RuntimeError("No controller I/O samples available to write.")

        timeseries_path, kpis_path, _timestamp_ms = self._next_unique_file_pair()
        self._write_timeseries_csv(timeseries_path)
        self._write_kpis_json(kpis_path, final_message["kpis"])
        return {
            "response_timeseries_csv": timeseries_path.as_posix(),
            "kpis_json": kpis_path.as_posix(),
        }

    def _resolve_signal_layout(self, field: str) -> tuple[str, tuple[str, ...]]:
        mode_key = f"{field}_mode"
        values_key = f"{field}_values"

        field_mode: str | None = None
        field_keys: tuple[str, ...] | None = None

        for sample in self._input_samples:
            sample_mode = str(sample[mode_key])
            sample_values = sample[values_key]
            if not isinstance(sample_values, dict):
                raise RuntimeError(
                    f"Internal controller input sample '{field}' values must be a dict."
                )

            if sample_mode == "scalar":
                sample_keys = ("",)
            elif sample_mode == "map":
                sample_keys = tuple(sorted(str(key) for key in sample_values))
            else:
                raise RuntimeError(f"Unexpected controller input sample mode '{sample_mode}'.")

            if field_mode is None:
                field_mode = sample_mode
                field_keys = sample_keys
                continue

            if sample_mode != field_mode:
                raise RuntimeError(
                    f"Controller input '{field}' changed between scalar and map within one run."
                )
            if sample_keys != field_keys:
                raise RuntimeError(
                    f"Controller input '{field}' map keys changed within one run."
                )

        if field_mode is None or field_keys is None:
            raise RuntimeError(f"No controller input samples available for field '{field}'.")
        return field_mode, field_keys

    @staticmethod
    def _columns_for_signal(prefix: str, mode: str, keys: tuple[str, ...]) -> list[str]:
        if mode == "scalar":
            return [prefix]
        return [f"{prefix}_{key}" for key in keys]

    @staticmethod
    def _fill_signal_row(
        row: dict[str, float | int],
        prefix: str,
        mode: str,
        keys: tuple[str, ...],
        values: Mapping[str, float],
    ) -> None:
        if mode == "scalar":
            row[prefix] = float(values[""])
            return
        for key in keys:
            row[f"{prefix}_{key}"] = float(values[key])

    def _write_timeseries_csv(self, path: Path) -> None:
        ref_mode, ref_keys = self._resolve_signal_layout("ref")
        meas_mode, meas_keys = self._resolve_signal_layout("meas")

        fieldnames = (
            ["step_index"]
            + self._columns_for_signal("ref", ref_mode, ref_keys)
            + self._columns_for_signal("meas", meas_mode, meas_keys)
            + ["control"]
        )

        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()

            for step_index, (sample, control) in enumerate(
                zip(self._input_samples, self._control_samples)
            ):
                row: dict[str, float | int] = {"step_index": step_index, "control": float(control)}
                self._fill_signal_row(
                    row=row,
                    prefix="ref",
                    mode=ref_mode,
                    keys=ref_keys,
                    values=sample["ref_values"],
                )
                self._fill_signal_row(
                    row=row,
                    prefix="meas",
                    mode=meas_mode,
                    keys=meas_keys,
                    values=sample["meas_values"],
                )
                writer.writerow(row)

    @staticmethod
    def _write_kpis_json(path: Path, kpis: Any) -> None:
        with path.open("w", encoding="utf-8") as handle:
            json.dump(kpis, handle, indent=2, sort_keys=True)
