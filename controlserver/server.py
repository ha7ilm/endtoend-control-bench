"""TCP feedback loop server with a remote controller client."""

from __future__ import annotations

import argparse
import socket
import threading
from pathlib import Path

from .config import RESULTS_ROOT, get_setup_config
from .session import run_socket_session
from .setups import available_setup_names, create_setup
from .setups.base import SimulationConfig


def _non_negative_int(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("design_attempt must be >= 0.")
    return parsed


def run_server(
    port: int,
    setup_name: str,
    experiment_id: str,
    design_attempt: int,
    *,
    host: str = "127.0.0.1",
    result_root: Path | str = RESULTS_ROOT,
    stop_event: threading.Event | None = None,
    ready_event: threading.Event | None = None,
    max_connections: int | None = None,
) -> int:
    """Run the feedback loop server until interrupted or max_connections reached."""
    setup = create_setup(setup_name)
    config = SimulationConfig.from_dict(get_setup_config(setup_name))
    result_root = Path(result_root)

    if stop_event is None:
        stop_event = threading.Event()

    connection_count = 0

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind((host, port))
        server_socket.listen()
        server_socket.settimeout(0.5)

        actual_port = int(server_socket.getsockname()[1])

        print(
            f"[controlserver] Feedback loop server with remote controller (client) "
            f"listening on {host}:{actual_port}."
        )
        print(
            f"[controlserver] Setup='{setup_name}', experiment='{experiment_id}', "
            f"attempt={design_attempt}, dt={config.dt}, horizon={config.horizon_sec}s."
        )

        if ready_event is not None:
            ready_event.set()

        while not stop_event.is_set():
            if max_connections is not None and connection_count >= max_connections:
                break

            try:
                conn, addr = server_socket.accept()
            except socket.timeout:
                continue

            connection_count += 1
            print(
                "[controlserver] Accepted remote controller client "
                f"{addr[0]}:{addr[1]} (connection {connection_count})."
            )

            with conn:
                try:
                    run_index = connection_count - 1
                    result_dir, run_index, _kpis = run_socket_session(
                        conn=conn,
                        setup=setup,
                        config=config,
                        result_root=result_root,
                        experiment_id=experiment_id,
                        design_attempt=design_attempt,
                        run_index=run_index,
                    )
                    print(
                        f"[controlserver] Feedback loop run{run_index} completed. "
                        f"Saved results to {result_dir}."
                    )
                except Exception as exc:
                    print(f"[controlserver] Session failed: {exc}")

        print("[controlserver] Server stopped.")
        return actual_port


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run a feedback loop simulation server where the physical plant runs "
            "on the server and the controller runs remotely as a TCP client."
        )
    )
    parser.add_argument("--port", type=int, required=True, help="TCP port to listen on")
    parser.add_argument(
        "--setup",
        "-s",
        type=str,
        required=True,
        choices=available_setup_names(),
        help="Physical setup to simulate",
    )
    parser.add_argument(
        "--experiment_id",
        "-i",
        type=str,
        required=True,
        help="Experiment id under results/current_run/sim/<setup>/<experiment_id>/attemptN/",
    )
    parser.add_argument(
        "--design_attempt",
        "-a",
        type=_non_negative_int,
        required=True,
        help="Numeric design attempt N used as results/current_run/sim/.../attemptN/",
    )
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Bind host")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    run_server(
        port=args.port,
        setup_name=args.setup,
        experiment_id=args.experiment_id,
        design_attempt=args.design_attempt,
        host=args.host,
        result_root=RESULTS_ROOT,
    )


if __name__ == "__main__":
    main()
