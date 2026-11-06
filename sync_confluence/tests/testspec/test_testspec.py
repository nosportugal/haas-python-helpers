from __future__ import annotations

import argparse
import datetime
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import openpyxl
import pytest
from lxml import etree

from sync_confluence.confluence import FolderConflictError
from sync_confluence.confluence._page_metadata import _apply_page_metadata
from sync_confluence.confluence._types import PageUpsertRequest
from sync_confluence.confluence.sync_cli import new_sync_result
from sync_confluence.testspec import (
    TestCase,
    TestSpecError,
    TestSpecSyncConfig,
    page_labels,
    read_workbook,
    render_test_case,
    run_testspec_sync,
    sync_test_cases,
)
from sync_confluence.testspec._args import resolve_suite

INDEX_HEADERS = ["Test ID", "Name", "Description", "Type", "Vendor", "Tags"]


def _write_workbook(path: Path, sheets: dict[str, list[list]]) -> Path:
    workbook = openpyxl.Workbook()
    workbook.remove(workbook.active)
    for title, rows in sheets.items():
        worksheet = workbook.create_sheet(title)
        for row in rows:
            worksheet.append(row)
    workbook.save(path)
    return path


def _valid_sheets() -> dict[str, list[list]]:
    return {
        "Index": [
            INDEX_HEADERS,
            [
                "1.1",
                "Create leg",
                "Line one\nLine two",
                "create",
                "Cisco",
                "L3VPN; Hub",
            ],
            ["1.2", "Delete leg", "", "Delete", "Cisco", ""],
        ],
        "Parameters": [
            ["Parameter", "Type", "Default"],
            ["vrfName", "string", ""],
            ["mtu", "integer", 1500],
        ],
        "1.1 - Inputs": [["Parameter", "Value", "Notes"], ["mtu", 9000, "bytes"]],
        "1.1 - Outputs": [
            ["Target", "CLI", "JSON"],
            ["/vrfs", "vrf A\n address-family ipv4", '{"vrf-name":"A"}'],
        ],
    }


@pytest.fixture
def workbook_path(tmp_path: Path) -> Path:
    return _write_workbook(tmp_path / "spec.xlsx", _valid_sheets())


def _read_with(tmp_path: Path, **overrides: list[list]) -> list[TestCase]:
    sheets = _valid_sheets()
    sheets.update({name.replace("_", " "): rows for name, rows in overrides.items()})
    return read_workbook(_write_workbook(tmp_path / "spec.xlsx", sheets))


class TestReadWorkbook:
    def test_reads_index_fields_and_title(self, workbook_path: Path) -> None:
        first, second = read_workbook(workbook_path)

        assert first.page_title("L3VPN") == "1.1 - Create leg (Cisco, L3VPN)"
        assert first.test_type == "Create"
        assert first.tags == ["L3VPN", "Hub"]
        assert first.description == "Line one\nLine two"
        assert second.tags == []

    def test_joins_all_catalog_parameters_with_values(
        self, workbook_path: Path
    ) -> None:
        first, _ = read_workbook(workbook_path)

        assert first.inputs is not None
        assert first.inputs.headers == [
            "Parameter",
            "Type",
            "Default",
            "Value",
            "Notes",
        ]
        assert first.inputs.rows == [
            ["vrfName", "string", "", "", ""],
            ["mtu", "integer", "1500", "9000", "bytes"],
        ]

    def test_pretty_prints_json_outputs(self, workbook_path: Path) -> None:
        first, _ = read_workbook(workbook_path)

        assert first.outputs is not None
        assert first.outputs.rows[0][2] == json.dumps({"vrf-name": "A"}, indent=2)

    def test_missing_per_test_sheets_are_none(self, workbook_path: Path) -> None:
        _, second = read_workbook(workbook_path)

        assert second.inputs is None
        assert second.outputs is None

    @pytest.mark.parametrize(
        ("index_row", "message"),
        [
            (["1.x", "Name", "", "Create", "Cisco", ""], "n.n format"),
            (["1.1", "Name", "", "Upgrade", "Cisco", ""], "expected one of"),
            (["1.1", "Name", "", "Create", "", ""], "needs a Name and a Vendor"),
            ([1.1, "Name", "", "Create", "Cisco", ""], "format the Test ID column"),
        ],
    )
    def test_rejects_invalid_index_rows(
        self, tmp_path: Path, index_row: list, message: str
    ) -> None:
        with pytest.raises(TestSpecError, match=message):
            _read_with(tmp_path, Index=[INDEX_HEADERS, index_row])

    def test_rejects_duplicate_test_ids(self, tmp_path: Path) -> None:
        row = ["1.1", "Name", "", "Create", "Cisco", ""]

        with pytest.raises(TestSpecError, match="duplicate Test ID 1.1"):
            _read_with(tmp_path, Index=[INDEX_HEADERS, row, row])

    def test_rejects_sheets_without_matching_test(self, tmp_path: Path) -> None:
        sheets = _valid_sheets()
        sheets["1.1- Inputs"] = [["Parameter", "Value"]]

        with pytest.raises(TestSpecError, match="1.1- Inputs"):
            read_workbook(_write_workbook(tmp_path / "spec.xlsx", sheets))

    def test_rejects_inputs_not_in_catalog(self, tmp_path: Path) -> None:
        sheets = _valid_sheets()
        sheets["1.1 - Inputs"] = [["Parameter", "Value"], ["mtuu", 1]]

        with pytest.raises(TestSpecError, match="not in the Parameters sheet: mtuu"):
            read_workbook(_write_workbook(tmp_path / "spec.xlsx", sheets))

    def test_rejects_invalid_json(self, tmp_path: Path) -> None:
        sheets = _valid_sheets()
        sheets["1.1 - Outputs"] = [["CLI", "JSON"], ["vrf A", "{not json"]]

        with pytest.raises(TestSpecError, match="data row 1: invalid JSON"):
            read_workbook(_write_workbook(tmp_path / "spec.xlsx", sheets))

    def test_accepts_json_only_outputs_without_parameters_sheet(
        self, tmp_path: Path
    ) -> None:
        sheets = _valid_sheets()
        del sheets["Parameters"]
        sheets["1.1 - Outputs"] = [["JSON"], ['{"mtu": 9000}']]

        first, _ = read_workbook(_write_workbook(tmp_path / "spec.xlsx", sheets))

        assert first.inputs is not None
        assert first.inputs.rows == [["mtu", "9000", "bytes"]]
        assert first.outputs is not None
        assert first.outputs.headers == ["JSON"]
        assert first.outputs.rows == [[json.dumps({"mtu": 9000}, indent=2)]]

    def test_requires_json_column_in_outputs(self, tmp_path: Path) -> None:
        sheets = _valid_sheets()
        sheets["1.1 - Outputs"] = [["CLI"], ["vrf A"]]

        with pytest.raises(TestSpecError, match="no 'JSON' column"):
            read_workbook(_write_workbook(tmp_path / "spec.xlsx", sheets))

    def test_requires_index_columns(self, tmp_path: Path) -> None:
        with pytest.raises(TestSpecError, match="no 'Vendor' column"):
            _read_with(tmp_path, Index=[["Test ID", "Name", "Description", "Type"]])

    def test_rejects_index_without_test_cases(self, tmp_path: Path) -> None:
        sheets = {"Index": [INDEX_HEADERS]}

        with pytest.raises(TestSpecError, match="'Index' has no test cases"):
            read_workbook(_write_workbook(tmp_path / "spec.xlsx", sheets))

    def test_rejects_blank_parameter_name(self, tmp_path: Path) -> None:
        sheets = _valid_sheets()
        sheets["1.1 - Inputs"] = [["Parameter", "Value"], ["mtu", 1], [None, 9000]]

        with pytest.raises(TestSpecError, match="data row 2: blank Parameter name"):
            read_workbook(_write_workbook(tmp_path / "spec.xlsx", sheets))

    @pytest.mark.parametrize(
        ("cell_value", "expected"),
        [
            (datetime.datetime(2026, 11, 6), "2026-11-06"),
            (datetime.datetime(2026, 11, 6, 9, 30, 45), "2026-11-06 09:30:45"),
        ],
    )
    def test_datetime_cells_keep_non_midnight_time(
        self, tmp_path: Path, cell_value: datetime.datetime, expected: str
    ) -> None:
        sheets = _valid_sheets()
        sheets["1.1 - Inputs"] = [["Parameter", "Value"], ["mtu", cell_value]]

        first, _ = read_workbook(_write_workbook(tmp_path / "spec.xlsx", sheets))

        assert first.inputs is not None
        assert first.inputs.rows[1][-1] == expected


class TestRenderTestCase:
    def _render(
        self, workbook_path: Path, position: int, **kwargs: str
    ) -> etree._Element:
        case = read_workbook(workbook_path)[position]
        body = render_test_case(case, Path("spec.xlsx"), **kwargs)
        return etree.fromstring(
            '<root xmlns:ac="http://atlassian.com/content" '
            f'xmlns:ri="http://atlassian.com/resource/identifier">{body}</root>'
        )

    def test_renders_sections_in_order(self, workbook_path: Path) -> None:
        root = self._render(workbook_path, 0)

        assert [h2.text for h2 in root.iter("h2")] == [
            "Description",
            "Inputs",
            "Outputs",
        ]
        assert "Vendor: Cisco" in "".join(root.find("p").itertext())

    def test_renders_cli_and_json_as_code_macros(self, workbook_path: Path) -> None:
        root = self._render(workbook_path, 0)
        ac_ns = "{http://atlassian.com/content}"
        macros = [
            m
            for m in root.iter(f"{ac_ns}structured-macro")
            if m.get(f"{ac_ns}name") == "code"
        ]

        languages = [m.findtext(f"{ac_ns}parameter") for m in macros]
        bodies = [m.findtext(f"{ac_ns}plain-text-body") for m in macros]
        assert languages == [None, "json"]
        assert bodies[0] == "vrf A\n address-family ipv4"

    def test_multiline_description_uses_line_breaks(self, workbook_path: Path) -> None:
        root = self._render(workbook_path, 0)
        description = root.find("h2").getnext()

        assert description.text == "Line one"
        assert description.find("br").tail == "Line two"

    def test_missing_tables_render_placeholder(self, workbook_path: Path) -> None:
        root = self._render(workbook_path, 1)

        assert [em.text for em in root.iter("em")] == [
            "Not specified yet.",
            "Not specified yet.",
        ]
        assert root.find("table") is None

    def test_generated_by_banner_can_be_suppressed(self, workbook_path: Path) -> None:
        with_banner = self._render(workbook_path, 0)
        without_banner = self._render(workbook_path, 0, generated_by="")

        assert with_banner[0].tag.endswith("structured-macro")
        assert without_banner[0].tag == "p"


def _case(test_id: str, vendor: str, tags: list[str] | None = None) -> TestCase:
    return TestCase(
        test_id=test_id,
        name=f"Test {test_id}",
        description="",
        test_type="Create",
        vendor=vendor,
        tags=tags or [],
    )


def test_page_labels_are_confluence_safe_and_unique() -> None:
    case = _case("1.1", "Cisco", ["Active/Active", "L3VPN", "cisco", "  "])

    assert page_labels(case) == ["cisco", "create", "active-active", "l3vpn"]


class TestSyncTestCases:
    @patch("sync_confluence.testspec._sync.build_source_path_map", return_value={})
    @patch("sync_confluence.testspec._sync.upsert_page")
    @patch("sync_confluence.testspec._sync.upsert_folder")
    def test_one_folder_per_vendor_and_pages_sorted_by_id(
        self,
        mock_folder: MagicMock,
        mock_page: MagicMock,
        mock_path_map: MagicMock,
    ) -> None:
        mock_folder.side_effect = [("f-cisco", "created"), ("f-nokia", "unchanged")]
        mock_page.return_value = ("p", "created")
        cases = [_case("1.10", "Cisco"), _case("1.2", "Cisco"), _case("1.1", "Nokia")]
        config = TestSpecSyncConfig(
            space_key="HaaS",
            parent_id="100",
            source_file=Path("spec.xlsx"),
            suite="L3VPN",
        )

        result = sync_test_cases(MagicMock(), cases, config)

        folders = [c.args[1] for c in mock_folder.call_args_list]
        assert [(f.title, f.parent_id) for f in folders] == [
            ("Cisco (L3VPN)", "100"),
            ("Nokia (L3VPN)", "100"),
        ]
        pages = [c.args[1] for c in mock_page.call_args_list]
        assert [(p.title, p.parent_id, p.source_path) for p in pages] == [
            ("1.2 - Test 1.2 (Cisco, L3VPN)", "f-cisco", "testspec/L3VPN/Cisco/1.2"),
            ("1.10 - Test 1.10 (Cisco, L3VPN)", "f-cisco", "testspec/L3VPN/Cisco/1.10"),
            ("1.1 - Test 1.1 (Nokia, L3VPN)", "f-nokia", "testspec/L3VPN/Nokia/1.1"),
        ]
        assert pages[0].labels == ["cisco", "create"]
        assert result.stats["created"] == 3
        assert result.expected_titles == {
            "Cisco (L3VPN)",
            "Nokia (L3VPN)",
            "1.2 - Test 1.2 (Cisco, L3VPN)",
            "1.10 - Test 1.10 (Cisco, L3VPN)",
            "1.1 - Test 1.1 (Nokia, L3VPN)",
        }
        assert result.expected_paths == {
            "testspec/L3VPN/Cisco",
            "testspec/L3VPN/Nokia",
            "testspec/L3VPN/Cisco/1.2",
            "testspec/L3VPN/Cisco/1.10",
            "testspec/L3VPN/Nokia/1.1",
        }
        assert folders[0].source_path == "testspec/L3VPN/Cisco"
        assert [c.args[1] for c in mock_path_map.call_args_list] == [
            "f-cisco",
            "f-nokia",
        ]

    @patch("sync_confluence.testspec._sync.build_source_path_map")
    @patch("sync_confluence.testspec._sync.upsert_page", return_value=(None, "skipped"))
    @patch(
        "sync_confluence.testspec._sync.upsert_folder",
        return_value=("DRY-RUN", "created"),
    )
    @patch("sync_confluence.testspec._sync.find_folder_under_parent", return_value=None)
    def test_skipped_pages_are_reported_and_dry_run_skips_path_map(
        self,
        mock_find: MagicMock,
        mock_folder: MagicMock,
        mock_page: MagicMock,
        mock_path_map: MagicMock,
    ) -> None:
        config = TestSpecSyncConfig(
            space_key="HaaS",
            parent_id="100",
            source_file=Path("spec.xlsx"),
            suite="L3VPN",
            dry_run=True,
        )

        result = sync_test_cases(MagicMock(), [_case("1.1", "Cisco")], config)

        assert result.skipped == ["1.1 - Test 1.1 (Cisco, L3VPN)"]
        assert result.stats["skipped"] == 1
        assert "1.1 - Test 1.1 (Cisco, L3VPN)" not in result.expected_titles
        mock_path_map.assert_not_called()

    @patch("sync_confluence.testspec._sync.build_source_path_map", return_value={})
    @patch("sync_confluence.testspec._sync.upsert_page", return_value=("7", "updated"))
    @patch("sync_confluence.testspec._sync.upsert_folder")
    @patch(
        "sync_confluence.testspec._sync.find_folder_under_parent",
        return_value={"id": "f-cisco"},
    )
    def test_dry_run_uses_existing_vendor_folder_for_page_lookups(
        self,
        mock_find: MagicMock,
        mock_folder: MagicMock,
        mock_page: MagicMock,
        mock_path_map: MagicMock,
    ) -> None:
        config = TestSpecSyncConfig(
            space_key="HaaS",
            parent_id="100",
            source_file=Path("spec.xlsx"),
            suite="L3VPN",
            dry_run=True,
        )

        result = sync_test_cases(MagicMock(), [_case("1.1", "Cisco")], config)

        mock_folder.assert_not_called()
        assert mock_find.call_args.args[2] == "Cisco (L3VPN)"
        assert mock_page.call_args.args[1].parent_id == "f-cisco"
        assert mock_path_map.call_args.args[1] == "f-cisco"
        assert result.stats["updated"] == 1


@patch("sync_confluence.confluence._page_metadata._apply_label")
@patch("sync_confluence.confluence._page_metadata._try_property_set")
def test_page_metadata_applies_extra_labels(
    mock_property: MagicMock, mock_label: MagicMock
) -> None:
    confluence = MagicMock()
    request = PageUpsertRequest(
        space_key="HaaS",
        parent_id="1",
        title="T",
        body="",
        managed_by_label="managed-by-x",
        labels=["cisco", "create"],
    )

    _apply_page_metadata(confluence, "42", request, "hash")

    assert [c.args[2] for c in mock_label.call_args_list] == [
        "managed-by-x",
        "cisco",
        "create",
    ]


@patch("sync_confluence.testspec._cli.open_confluence_session")
def test_run_fails_before_connecting_when_workbook_is_invalid(
    mock_auth: MagicMock, tmp_path: Path
) -> None:
    path = _write_workbook(tmp_path / "bad.xlsx", {"Sheet": [["x"]]})
    args = MagicMock(xlsx=str(path), suite=None)

    assert run_testspec_sync(args) == 1
    mock_auth.assert_not_called()


class TestResolveSuite:
    def test_defaults_to_workbook_stem(self) -> None:
        args = argparse.Namespace(suite=None, xlsx="dir/L3VPN - Cisco.xlsx")

        assert resolve_suite(args) == "L3VPN - Cisco"

    def test_explicit_suite_wins(self) -> None:
        args = argparse.Namespace(suite=" L3VPN ", xlsx="spec.xlsx")

        assert resolve_suite(args) == "L3VPN"

    @pytest.mark.parametrize("suite", ["a/b", "   "])
    def test_rejects_invalid_suite(self, suite: str) -> None:
        args = argparse.Namespace(suite=suite, xlsx="spec.xlsx")

        with pytest.raises(TestSpecError, match="Invalid suite name"):
            resolve_suite(args)


def _run_args(workbook_path: Path) -> argparse.Namespace:
    return argparse.Namespace(
        xlsx=str(workbook_path),
        suite="L3VPN",
        space="HaaS",
        parent_id="100",
        dry_run=False,
        page_width=None,
        generated_by=None,
        no_generated_by=False,
    )


class TestRunTestspecSync:
    @patch("sync_confluence.testspec._cli.finalise_sync_run")
    @patch("sync_confluence.testspec._cli.sync_test_cases")
    @patch("sync_confluence.testspec._cli.open_confluence_session")
    def test_uses_testspec_label_and_suite_scoped_cleanup(
        self,
        mock_auth: MagicMock,
        mock_sync: MagicMock,
        mock_finalise: MagicMock,
        workbook_path: Path,
    ) -> None:
        mock_sync.return_value = new_sync_result()

        assert run_testspec_sync(_run_args(workbook_path)) == 0

        assert mock_auth.call_args.kwargs == {"label_suffix": "-testspec"}
        assert mock_sync.call_args.args[2].suite == "L3VPN"
        assert mock_finalise.call_args.kwargs == {
            "source_path_prefix": "testspec/L3VPN/"
        }

    @patch("sync_confluence.testspec._cli.finalise_sync_run")
    @patch(
        "sync_confluence.testspec._cli.sync_test_cases",
        side_effect=FolderConflictError("Folder 'Cisco (L3VPN)' already exists."),
    )
    @patch("sync_confluence.testspec._cli.open_confluence_session")
    def test_folder_conflict_fails_without_cleanup(
        self,
        mock_auth: MagicMock,
        mock_sync: MagicMock,
        mock_finalise: MagicMock,
        workbook_path: Path,
    ) -> None:
        assert run_testspec_sync(_run_args(workbook_path)) == 1

        mock_finalise.assert_not_called()
