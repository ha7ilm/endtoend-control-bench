TEST_MODULE = "tests/test_protocol.py"

REASONS_BY_TEST = {
    "test_encode_decode_round_trip": (
        "Verify message serialization/deserialization preserves controller protocol payloads exactly in normal operation."
    ),
    "test_read_write_message_round_trip_over_socketpair": (
        "Check framed protocol I/O works correctly over real sockets for end-to-end message transfer behavior."
    ),
    "test_read_message_handles_partial_frames": (
        "Ensure frame parsing tolerates byte-wise fragmented input, preventing broken reads on partial network delivery."
    ),
    "test_decode_message_rejects_non_map_payload": (
        "Enforce protocol schema requirement that decoded payloads must be map-like objects, rejecting incompatible types."
    ),
    "test_read_message_rejects_invalid_frame_length": (
        "Protect framing robustness by rejecting invalid length headers (e.g., zero-length frames) with ProtocolError."
    ),
}

REASONS_BY_NODEID = {}
