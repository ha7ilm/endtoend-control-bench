"""Compatibility wrapper for local repo imports."""

from __future__ import annotations

import sys
from pathlib import Path

try:
    from urletra._common.protocol import (
        FRAME_HEADER_SIZE,
        MAX_FRAME_BYTES,
        ProtocolError,
        decode_message,
        encode_message,
        read_message,
        write_message,
    )
except ModuleNotFoundError:
    src_root = Path(__file__).resolve().parents[1] / "src"
    src_root_str = str(src_root)
    if src_root_str not in sys.path:
        sys.path.insert(0, src_root_str)
    from urletra._common.protocol import (
        FRAME_HEADER_SIZE,
        MAX_FRAME_BYTES,
        ProtocolError,
        decode_message,
        encode_message,
        read_message,
        write_message,
    )

__all__ = [
    "FRAME_HEADER_SIZE",
    "MAX_FRAME_BYTES",
    "ProtocolError",
    "decode_message",
    "encode_message",
    "read_message",
    "write_message",
]
