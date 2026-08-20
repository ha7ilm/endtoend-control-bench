TEST_MODULE = "tests/test_mkresultsexplorer.py"

REASONS_BY_TEST = {
    "test_match_lookups_accept_pass_warn_and_exclude_fail": (
        "Verify the static results explorer uses reviewed PASS and WARN controller/run mappings while rejecting FAIL rows. "
        "Added while documenting every downstream npy_match.csv consumer, when that audit found the explorer's declared "
        "accepted-status policy was not actually applied to its lookup construction."
    ),
    "test_build_site_sanitizes_prompt_and_log_text": (
        "Added while redacting absolute workspace paths from the results explorer export, then updated when the "
        "repository path became runtime-derived instead of machine-specific. It locks the sanitization contract "
        "for prompt markdown, normalized LLM thinking logs, and exported llm_said metadata."
    ),
    "test_build_site_copies_math_delimiter_preserving_doc_renderer": (
        "Added while fixing results explorer math rendering for prompt and summary markdown, after spotting that "
        "the markdown parser stripped the backslashes from \\\\( ... \\\\) and \\\\[ ... \\\\] delimiters before "
        "MathJax could typeset them."
    ),
}

REASONS_BY_NODEID = {}
