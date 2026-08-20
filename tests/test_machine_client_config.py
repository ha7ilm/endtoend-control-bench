import pytest

from controlclient.machine import MachineClient


def _new_client() -> MachineClient:
    return MachineClient(
        setup="motorspeed_dt",
        description="P(100) controller",
        why="Configuration test client.",
    )


def test_machine_client_requires_setup_description_and_why():
    with pytest.raises(TypeError):
        MachineClient()  # type: ignore[call-arg]


def test_machine_client_allows_empty_description_and_why():
    client = MachineClient(
        setup="motorspeed_dt",
        description="",
        why="",
    )
    assert client.description == ""
    assert client.why == ""


def test_machine_client_defaults_host_and_port(monkeypatch):
    monkeypatch.delenv("URLETRA_MACHINE_HOST", raising=False)
    monkeypatch.delenv("URLETRA_MACHINE_PORT", raising=False)

    client = _new_client()

    assert client.host == "127.0.0.1"
    assert client.port == 9000


def test_machine_client_uses_host_env(monkeypatch):
    monkeypatch.setenv("URLETRA_MACHINE_HOST", "192.0.2.10")
    monkeypatch.setenv("URLETRA_MACHINE_PORT", "9100")

    client = _new_client()

    assert client.host == "192.0.2.10"
    assert client.port == 9100


@pytest.mark.parametrize("value", ["", "bad", "0", "70000"])
def test_machine_client_invalid_port_env_warns_and_defaults(monkeypatch, capsys, value):
    monkeypatch.delenv("URLETRA_MACHINE_HOST", raising=False)
    monkeypatch.setenv("URLETRA_MACHINE_PORT", value)

    client = _new_client()
    out = capsys.readouterr().out

    assert client.port == 9000
    assert "URLETRA_MACHINE_PORT" in out


def test_machine_client_logs_run_to_files_by_default(monkeypatch):
    monkeypatch.delenv("URLETRA_MACHINECLIENT_LOG_RUN_TO_FILES", raising=False)

    client = _new_client()

    assert client.log_run_to_files is True


def test_machine_client_can_disable_run_file_logging_via_env(monkeypatch):
    monkeypatch.setenv("URLETRA_MACHINECLIENT_LOG_RUN_TO_FILES", "0")

    client = _new_client()

    assert client.log_run_to_files is False


@pytest.mark.parametrize("value", ["1", "", "false", "00", " 1 "])
def test_machine_client_nonzero_log_env_keeps_logging_enabled(monkeypatch, value):
    monkeypatch.setenv("URLETRA_MACHINECLIENT_LOG_RUN_TO_FILES", value)

    client = _new_client()

    assert client.log_run_to_files is True
