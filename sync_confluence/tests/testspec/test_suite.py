from __future__ import annotations

import argparse
import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from sync_confluence.testspec import TestCase, TestSpecError, run_testspec_sync
from sync_confluence.testspec._args import resolve_suite
from sync_confluence.testspec._suite import (
    SUITE_ID_MAX_LENGTH,
    suite_from_filename,
    validate_suite_id,
)
from sync_confluence.testspec._titles import (
    CONFLUENCE_TITLE_MAX_LENGTH,
    check_title_lengths,
)

_EXAMPLE_NAME = "DEMO-EXAMPLE__format_example.xlsx"


@pytest.mark.parametrize(
    ("file_name", "suite"),
    [
        ("HAAS-493__routing_acceptance.xlsx", "HAAS-493"),
        ("HAAS-ROUTING_CORE-E2E__end_to_end_v2.xlsx", "HAAS-ROUTING_CORE-E2E"),
        ("ORD-CHECKOUT-INT.xlsx", "ORD-CHECKOUT-INT"),
        ("HAAS-L3VPN-CISCO__testes_servico_l3vpn_cisco.xlsx", "HAAS-L3VPN-CISCO"),
        (
            "HAAS-L3VPN-CISCO__testes_servico_l3vpn_cisco_partial_outputs_v2.xlsx",
            "HAAS-L3VPN-CISCO",
        ),
        ("HAAS-493.xlsx", "HAAS-493"),
        ("HAAS-493_ROUTING.xlsx", "HAAS-493_ROUTING"),
        ("HAAS-A-B-C.xlsx", "HAAS-A-B-C"),
        ("AB-1.xlsx", "AB-1"),
        ("HAAS-493__a__b.xlsx", "HAAS-493"),
        ("HAAS-493__v1.2-final.xlsx", "HAAS-493"),
        ("some/dir/HAAS-493__notes.xlsx", "HAAS-493"),
        (_EXAMPLE_NAME, "DEMO-EXAMPLE"),
    ],
)
def test_suite_id_is_read_from_the_start_of_the_file_name(
    file_name: str, suite: str
) -> None:
    assert suite_from_filename(file_name) == suite


def test_the_description_never_changes_the_suite() -> None:
    names = [
        "HAAS-L3VPN-CISCO.xlsx",
        "HAAS-L3VPN-CISCO__v1.xlsx",
        "HAAS-L3VPN-CISCO__partial_outputs_v2.xlsx",
    ]

    assert {suite_from_filename(name) for name in names} == {"HAAS-L3VPN-CISCO"}


@pytest.mark.parametrize(
    ("file_name", "reason"),
    [
        ("Testes serviço L3VPN - Cisco.xlsx", "must not contain spaces"),
        ("HAAS-493 - routing.xlsx", "must not contain spaces"),
        ("HAAS-493__routing notes.xlsx", "must not contain spaces"),
        ("HAAS-L3VPN-CISCO__testes_serviço.xlsx", "found 'ç'"),
        ("HAAS-493__routing(1).xlsx", "found '(' ')'"),
        ("HAAS-493__a,b.xlsx", "found ','"),
        ("haas-493__routing.xlsx", "The ID must be uppercase"),
        ("Haas-493.xlsx", "The ID must be uppercase"),
        ("HAAS__routing.xlsx", "Invalid suite ID 'HAAS'"),
        ("HAAS.xlsx", "Invalid suite ID 'HAAS'"),
        ("H-493.xlsx", "Invalid suite ID 'H-493'"),
        ("HAAS-1-2-3-4.xlsx", "Invalid suite ID 'HAAS-1-2-3-4'"),
        ("1AAS-493.xlsx", "Invalid suite ID '1AAS-493'"),
        ("HAAS-493_.xlsx", "Invalid suite ID 'HAAS-493_'"),
        ("HAAS--493.xlsx", "Invalid suite ID 'HAAS--493'"),
        ("HAAS-493__.xlsx", "description after '__' ('')"),
        ("HAAS-493___x.xlsx", "description after '__' ('_x')"),
        ("HAAS-493__-x.xlsx", "description after '__' ('-x')"),
        ("__notes.xlsx", "Invalid suite ID ''"),
    ],
)
def test_invalid_file_names_are_rejected_with_the_reason(
    file_name: str, reason: str
) -> None:
    with pytest.raises(TestSpecError) as exc_info:
        suite_from_filename(file_name)

    assert reason in str(exc_info.value)


@pytest.mark.parametrize(
    ("file_name", "suggestion"),
    [
        ("HAAS-493_routing.xlsx", "'HAAS-493__routing'"),
        ("HAAS-ROUTING_CORE-e2e.xlsx", "'HAAS-ROUTING__CORE-e2e'"),
    ],
)
def test_a_single_underscore_before_text_suggests_the_double_underscore(
    file_name: str, suggestion: str
) -> None:
    with pytest.raises(TestSpecError) as exc_info:
        suite_from_filename(file_name)

    assert f"Did you mean {suggestion}?" in str(exc_info.value)


def test_a_valid_id_with_a_single_underscore_needs_no_hint() -> None:
    assert suite_from_filename("HAAS-493_ROUTING.xlsx") == "HAAS-493_ROUTING"


def test_the_error_explains_the_expected_shape() -> None:
    with pytest.raises(TestSpecError, match="e.g. HAAS-L3VPN-CISCO"):
        suite_from_filename("HAAS.xlsx")


def test_the_id_may_have_at_most_the_maximum_length() -> None:
    longest = "HAAS-" + "A" * (SUITE_ID_MAX_LENGTH - len("HAAS-"))

    assert validate_suite_id(longest) == longest
    with pytest.raises(TestSpecError, match=f"{SUITE_ID_MAX_LENGTH + 1} characters"):
        validate_suite_id(longest + "A")


class TestResolveSuite:
    def test_comes_from_the_workbook_file_name(self) -> None:
        args = argparse.Namespace(suite=None, xlsx="dir/HAAS-493__notes.xlsx")

        assert resolve_suite(args) == "HAAS-493"

    def test_an_override_wins_over_the_file_name(self) -> None:
        args = argparse.Namespace(suite="HAAS-OTHER", xlsx="Not A Valid Name.xlsx")

        assert resolve_suite(args) == "HAAS-OTHER"

    @pytest.mark.parametrize(
        "suite",
        ["L3VPN", "haas-493", "HAAS-493__notes", " HAAS-493", "a/b", "HAAS-493 "],
    )
    def test_an_override_must_follow_the_same_rule(self, suite: str) -> None:
        args = argparse.Namespace(suite=suite, xlsx="HAAS-493.xlsx")

        with pytest.raises(TestSpecError, match="Invalid suite ID"):
            resolve_suite(args)

    def test_a_bad_file_name_without_override_is_an_error(self) -> None:
        args = argparse.Namespace(suite=None, xlsx="Testes serviço L3VPN - Cisco.xlsx")

        with pytest.raises(TestSpecError, match="must not contain spaces"):
            resolve_suite(args)


def _case(test_id: str, name: str) -> TestCase:
    return TestCase(test_id=test_id, name=name, description="")


class TestTitleLength:
    def test_titles_up_to_the_limit_are_accepted(self) -> None:
        suite = "HAAS-493"
        fixed = len(_case("1.1", "").page_title(suite))
        name = "n" * (CONFLUENCE_TITLE_MAX_LENGTH - fixed)

        check_title_lengths([_case("1.1", name)], suite)

    def test_a_longer_title_names_the_test_and_its_length(self) -> None:
        suite = "HAAS-493"
        fixed = len(_case("1.1", "").page_title(suite))
        name = "n" * (CONFLUENCE_TITLE_MAX_LENGTH - fixed + 1)

        with pytest.raises(TestSpecError) as exc_info:
            check_title_lengths([_case("1.1", "ok"), _case("1.2", name)], suite)

        message = str(exc_info.value)
        assert f"1.2 ({CONFLUENCE_TITLE_MAX_LENGTH + 1} characters)" in message
        assert "1.1 (" not in message


def _args(xlsx: Path, suite: str | None = None) -> argparse.Namespace:
    return argparse.Namespace(
        xlsx=str(xlsx),
        suite=suite,
        space="HaaS",
        parent_id="100",
        dry_run=True,
        page_width=None,
        generated_by=None,
        no_generated_by=False,
        format_json=False,
    )


class TestRunChecksTheFileNameFirst:
    @patch("sync_confluence.testspec._cli.open_confluence_session")
    def test_a_bad_file_name_fails_before_connecting(
        self,
        mock_auth: MagicMock,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        workbook = tmp_path / "Testes serviço L3VPN - Cisco.xlsx"

        with caplog.at_level(logging.ERROR):
            assert run_testspec_sync(_args(workbook)) == 1

        mock_auth.assert_not_called()
        assert "must not contain spaces" in caplog.text
