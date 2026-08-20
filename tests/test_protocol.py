import socket
import struct

import msgpack
import pytest

from controlserver.protocol import ProtocolError, decode_message, encode_message, read_message, write_message


def test_encode_decode_round_trip():
    message = {
        "type": "controller_input",
        "done": False,
        "ref": 1.0,
        "meas": 0.25,
    }

    payload = encode_message(message)
    decoded = decode_message(payload)

    assert decoded == message


def test_read_write_message_round_trip_over_socketpair():
    left, right = socket.socketpair()
    try:
        message = {"type": "controller_output", "control": 3.14}
        write_message(left, message)
        received = read_message(right)
        assert received == message
    finally:
        left.close()
        right.close()


def test_read_message_handles_partial_frames():
    left, right = socket.socketpair()
    try:
        message = {"type": "controller_output", "control": 2.0}
        payload = encode_message(message)
        frame = struct.pack(">I", len(payload)) + payload

        for byte in frame:
            left.send(bytes([byte]))

        received = read_message(right)
        assert received == message
    finally:
        left.close()
        right.close()


def test_decode_message_rejects_non_map_payload():
    payload = msgpack.packb(["not", "a", "map"], use_bin_type=True)
    with pytest.raises(ProtocolError):
        decode_message(payload)


def test_read_message_rejects_invalid_frame_length():
    left, right = socket.socketpair()
    try:
        left.sendall(struct.pack(">I", 0))
        with pytest.raises(ProtocolError):
            read_message(right)
    finally:
        left.close()
        right.close()
