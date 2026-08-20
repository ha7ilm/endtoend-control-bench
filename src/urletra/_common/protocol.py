"""Length-prefixed MessagePack protocol for controller-server communication."""

from __future__ import annotations

import struct
from typing import Any, Mapping

import msgpack

FRAME_HEADER_SIZE = 4
MAX_FRAME_BYTES = 8 * 1024 * 1024


class ProtocolError(RuntimeError):
    """Raised when the wire protocol is violated."""


def encode_message(message: Mapping[str, Any]) -> bytes:
    """Serialize a message map to MessagePack bytes."""
    try:
        return msgpack.packb(dict(message), use_bin_type=True)
    except Exception as exc:  # pragma: no cover - defensive
        raise ProtocolError(f"Failed to encode message: {exc}") from exc


def decode_message(payload: bytes) -> dict[str, Any]:
    """Deserialize a MessagePack payload into a message map."""
    try:
        decoded = msgpack.unpackb(payload, raw=False)
    except Exception as exc:
        raise ProtocolError(f"Failed to decode message: {exc}") from exc

    if not isinstance(decoded, dict):
        raise ProtocolError("Protocol message must decode to a map.")
    return decoded


def _recv_exact(sock, num_bytes: int) -> bytes:
    """Read exactly num_bytes from a socket or raise if closed."""
    chunks = bytearray()
    while len(chunks) < num_bytes:
        chunk = sock.recv(num_bytes - len(chunks))
        if not chunk:
            raise ProtocolError("Connection closed while reading protocol frame.")
        chunks.extend(chunk)
    return bytes(chunks)


def write_message(sock, message: Mapping[str, Any]) -> None:
    """Write one framed MessagePack message to a socket."""
    payload = encode_message(message)
    frame_size = len(payload)
    if frame_size <= 0 or frame_size > MAX_FRAME_BYTES:
        raise ProtocolError(f"Invalid frame payload size: {frame_size}")

    header = struct.pack(">I", frame_size)
    sock.sendall(header + payload)


def read_message(sock) -> dict[str, Any]:
    """Read one framed MessagePack message from a socket."""
    header = _recv_exact(sock, FRAME_HEADER_SIZE)
    (frame_size,) = struct.unpack(">I", header)

    if frame_size <= 0 or frame_size > MAX_FRAME_BYTES:
        raise ProtocolError(f"Invalid frame length: {frame_size}")

    payload = _recv_exact(sock, frame_size)
    return decode_message(payload)


__all__ = [
    "FRAME_HEADER_SIZE",
    "MAX_FRAME_BYTES",
    "ProtocolError",
    "decode_message",
    "encode_message",
    "read_message",
    "write_message",
]
