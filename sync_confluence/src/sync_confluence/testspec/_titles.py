"""Page titles must fit Confluence's title length limit."""

from __future__ import annotations

from sync_confluence.testspec._model import TestCase, TestSpecError

CONFLUENCE_TITLE_MAX_LENGTH = 255


def check_title_lengths(cases: list[TestCase], suite: str) -> None:
    """Fail when a page title would exceed Confluence's title length limit."""
    lengths = {case.test_id: len(case.page_title(suite)) for case in cases}
    too_long = [
        f"{test_id} ({length} characters)"
        for test_id, length in lengths.items()
        if length > CONFLUENCE_TITLE_MAX_LENGTH
    ]
    if too_long:
        tests = ", ".join(too_long)
        raise TestSpecError(
            f"Page title longer than Confluence's {CONFLUENCE_TITLE_MAX_LENGTH} "
            f"characters for test(s): {tests}. Shorten their Name"
        )
