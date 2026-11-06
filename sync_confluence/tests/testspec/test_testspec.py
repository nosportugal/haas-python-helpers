from __future__ import annotations

import argparse
import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import openpyxl
import pytest
from lxml import etree

from sync_confluence.confluence import FolderConflictError, FolderNotOwnedError
from sync_confluence.confluence._page_metadata import _apply_page_metadata
from sync_confluence.confluence._types import PageUpsertRequest
from sync_confluence.confluence.sync_cli import new_sync_result
from sync_confluence.testspec import (
    SheetTable,
    TestCase,
    TestSpecError,
    TestSpecSyncConfig,
    page_labels,
    parse_testspec_sync_args,
    read_workbook,
    render_test_case,
    run_testspec_sync,
    sync_test_cases,
)
from sync_confluence.testspec._args import resolve_suite
from sync_confluence.testspec._sync import _sort_key

_MACRO = "{http://atlassian.com/content}structured-macro"

# Mandatory columns (ID, Name, Description, Tags) plus two additional ones.
INDEX_HEADERS = ["ID", "Name", "Vendor", "Description", "Tags", "Priority"]
_EXAMPLE = (
    Path(__file__).resolve().parents[2] / "examples" / "testspec_format_example.xlsx"
)


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
            ["1.1", "Create leg", "Cisco", "Line one\nLine two", "L3VPN; Hub", "High"],
            ["1.2", "Delete leg", "Nokia", "", "", ""],
        ],
        "1.1 - Inputs": [
            ["Characteristic", "Type", "Value"],
            ["mtu", "integer", 9000],
            ["vrfName", "string", "A"],
        ],
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

        assert first.page_title("L3VPN") == "1.1 - Create leg (L3VPN)"
        assert first.tags == ["L3VPN", "Hub"]
        assert first.description == "Line one\nLine two"
        assert first.extra_fields == [("Vendor", "Cisco"), ("Priority", "High")]
        assert second.tags == []

    def test_example_workbook_follows_the_format(self) -> None:
        cases = read_workbook(_EXAMPLE)
        header = [
            cell.value for cell in openpyxl.load_workbook(_EXAMPLE).worksheets[0][1]
        ]

        assert header[:4] == ["ID", "Name", "Description", "Tags"]
        assert header[4:] == ["Type", "Component", "Priority"]
        assert [case.test_id for case in cases] == ["1.1", "1.1.3", "1.2", "2.1", "2.2"]
        assert [name for name, _ in cases[0].extra_fields] == header[4:]

    def test_example_workbook_shows_different_output_layouts(self) -> None:
        by_id = {case.test_id: case for case in read_workbook(_EXAMPLE)}

        assert by_id["1.1"].outputs.headers == ["JSON"]
        assert by_id["2.1"].outputs.headers == ["Parameter", "Value"]
        assert by_id["1.1.3"].outputs.headers == ["Check", "Expected (partial)"]

    def test_example_workbook_json_column_is_the_only_code_block(self) -> None:
        by_id = {case.test_id: case for case in read_workbook(_EXAMPLE)}

        bodies = {
            test_id: render_test_case(case, Path("x.xlsx"), "").count('ac:name="code"')
            for test_id, case in by_id.items()
        }

        assert bodies == {"1.1": 1, "1.1.3": 0, "1.2": 0, "2.1": 0, "2.2": 0}

    def test_inputs_are_a_plain_table_with_any_columns(
        self, workbook_path: Path
    ) -> None:
        first, _ = read_workbook(workbook_path)

        assert first.inputs is not None
        assert first.inputs.headers == ["Characteristic", "Type", "Value"]
        assert first.inputs.rows == [
            ["mtu", "integer", "9000"],
            ["vrfName", "string", "A"],
        ]

    def test_outputs_are_kept_exactly_as_written(self, workbook_path: Path) -> None:
        first, _ = read_workbook(workbook_path)

        assert first.outputs is not None
        assert first.outputs.headers == ["Target", "CLI", "JSON"]
        assert first.outputs.rows == [
            ["/vrfs", "vrf A\n address-family ipv4", '{"vrf-name":"A"}']
        ]

    def test_missing_per_test_sheets_are_none(self, workbook_path: Path) -> None:
        _, second = read_workbook(workbook_path)

        assert second.inputs is None
        assert second.outputs is None

    @pytest.mark.parametrize(
        ("index_row", "message"),
        [
            (["1.x", "Name", "Cisco", "", "", ""], "dot-separated numbers"),
            (["1.1", "", "Cisco", "", "", ""], "needs a Name"),
            ([1.1, "Name", "Cisco", "", "", ""], "format the ID column"),
        ],
    )
    def test_rejects_invalid_index_rows(
        self, tmp_path: Path, index_row: list, message: str
    ) -> None:
        with pytest.raises(TestSpecError, match=message):
            _read_with(tmp_path, Index=[INDEX_HEADERS, index_row])

    def test_rejects_duplicate_test_ids(self, tmp_path: Path) -> None:
        row = ["1.1", "Name", "Cisco", "", "", ""]

        with pytest.raises(TestSpecError, match="duplicate ID 1.1"):
            _read_with(tmp_path, Index=[INDEX_HEADERS, row, row])

    @pytest.mark.parametrize(
        ("sheet_name", "reason"),
        [
            ("1.1.3 - Inputs", "refers to ID '1.1.3', which is not in the Index"),
            ("9.9 - Outputs", "refers to ID '9.9', which is not in the Index"),
            ("1.1- Inputs", "must be named exactly '1.1 - Inputs'"),
            ("1.1 -Outputs", "must be named exactly '1.1 - Outputs'"),
            ("Notes", "is neither the Index (first sheet) nor named"),
            ("Parameters", "is neither the Index (first sheet) nor named"),
        ],
    )
    def test_rejects_stray_sheets_with_the_reason(
        self, tmp_path: Path, sheet_name: str, reason: str
    ) -> None:
        sheets = _valid_sheets()
        sheets[sheet_name] = [["Name", "Value"], ["mtu", 1]]

        with pytest.raises(TestSpecError) as exc_info:
            read_workbook(_write_workbook(tmp_path / "spec.xlsx", sheets))

        message = str(exc_info.value)
        assert f"'{sheet_name}' {reason}" in message
        assert "IDs: 1.1, 1.2" in message

    def test_lists_every_stray_sheet_in_one_error(self, tmp_path: Path) -> None:
        sheets = {**_valid_sheets(), "Notes": [["a"]], "7.7 - Inputs": [["a"]]}

        with pytest.raises(TestSpecError) as exc_info:
            read_workbook(_write_workbook(tmp_path / "spec.xlsx", sheets))

        assert "'Notes'" in str(exc_info.value)
        assert "'7.7 - Inputs'" in str(exc_info.value)

    def test_per_test_sheet_names_ignore_case_and_outer_spaces(
        self, tmp_path: Path
    ) -> None:
        sheets = _valid_sheets()
        sheets["1.2 - INPUTS "] = [["Name"], ["x"]]

        _, second = read_workbook(_write_workbook(tmp_path / "spec.xlsx", sheets))

        assert second.inputs is not None

    @pytest.mark.parametrize("test_id", ["1", "1.1", "1.1.3", "2.10.4.7"])
    def test_accepts_ids_of_any_depth(self, tmp_path: Path, test_id: str) -> None:
        index = [INDEX_HEADERS, [test_id, "Leg", "Cisco", "", "", ""]]

        (case,) = read_workbook(_write_workbook(tmp_path / "s.xlsx", {"Index": index}))

        assert case.test_id == test_id

    def test_deep_ids_attach_their_own_sheets(self, tmp_path: Path) -> None:
        sheets = {
            "Index": [INDEX_HEADERS, ["1.1.3", "Leg", "Cisco", "", "", ""]],
            "1.1.3 - Inputs": [["Name", "Value"], ["mtu", 1]],
        }

        (case,) = read_workbook(_write_workbook(tmp_path / "s.xlsx", sheets))

        assert case.inputs is not None
        assert case.inputs.rows == [["mtu", "1"]]

    @pytest.mark.parametrize("test_id", ["", "1.", ".1", "1..2", "1.x", "v1.2"])
    def test_rejects_malformed_ids(self, tmp_path: Path, test_id: str) -> None:
        index = [INDEX_HEADERS, [test_id, "Leg", "Cisco", "", "", ""]]

        with pytest.raises(TestSpecError, match="dot-separated numbers"):
            read_workbook(_write_workbook(tmp_path / "s.xlsx", {"Index": index}))

    def test_deep_ids_sort_numerically(self) -> None:
        ids = ["1.10", "1.2", "1.1.3", "1.1", "1"]

        ordered = sorted(ids, key=lambda i: _sort_key(_case(i)))

        assert ordered == ["1", "1.1", "1.1.3", "1.2", "1.10"]

    @pytest.mark.parametrize(
        "outputs",
        [
            # a single column of full JSON documents
            [["Expected"], ['{"a": 1, "b": [1, 2]}']],
            # a partial / not even valid JSON fragment is fine too
            [["Expected"], ['"b": [1, 2'], ["..."]],
            # a parameter | value table
            [["Parameter", "Value"], ["mtu", 9000], ["vrf", "A"]],
            # free text with no recognisable header
            [["Check"], ["Interface is up"]],
        ],
    )
    def test_outputs_may_have_any_layout(
        self, tmp_path: Path, outputs: list[list]
    ) -> None:
        sheets = _valid_sheets()
        sheets["1.1 - Outputs"] = outputs

        first, _ = read_workbook(_write_workbook(tmp_path / "spec.xlsx", sheets))

        assert first.outputs is not None
        assert first.outputs.headers == [str(h) for h in outputs[0]]
        assert len(first.outputs.rows) == len(outputs) - 1

    def test_data_under_a_blank_header_is_kept(self, tmp_path: Path) -> None:
        sheets = _valid_sheets()
        sheets["1.1 - Inputs"] = [["Name", "Value", None], ["mtu", 1, "extra"]]

        first, _ = read_workbook(_write_workbook(tmp_path / "spec.xlsx", sheets))

        assert first.inputs is not None
        assert first.inputs.headers == ["Name", "Value", ""]
        assert first.inputs.rows == [["mtu", "1", "extra"]]

    def test_empty_trailing_columns_are_trimmed(self, tmp_path: Path) -> None:
        sheets = _valid_sheets()
        sheets["1.1 - Inputs"] = [["Name", "Value", None, None], ["mtu", 1, None, None]]

        first, _ = read_workbook(_write_workbook(tmp_path / "spec.xlsx", sheets))

        assert first.inputs is not None
        assert first.inputs.headers == ["Name", "Value"]

    @pytest.mark.parametrize("missing", ["ID", "Name", "Description", "Tags"])
    def test_requires_every_mandatory_column(
        self, tmp_path: Path, missing: str
    ) -> None:
        headers = [h for h in ["ID", "Name", "Description", "Tags"] if h != missing]

        with pytest.raises(TestSpecError, match=f"no '{missing}' column"):
            _read_with(tmp_path, Index=[[*headers, "Vendor"], ["1.1"] * 4])

    def test_mandatory_headers_are_case_insensitive_and_any_order(
        self, tmp_path: Path
    ) -> None:
        index = [
            ["tags", "Notes", "NAME", "id", "description"],
            ["a; b", "n1", "Leg", "1.1", "Desc"],
        ]

        (case,) = _read_with(tmp_path, Index=index)

        assert (case.test_id, case.name, case.description) == ("1.1", "Leg", "Desc")
        assert case.tags == ["a", "b"]
        assert case.extra_fields == [("Notes", "n1")]

    def test_additional_columns_keep_table_order(self, tmp_path: Path) -> None:
        index = [
            ["Zeta", "ID", "Name", "Alpha", "Description", "Tags", "Mid"],
            ["z", "1.1", "Leg", "a", "", "", "m"],
        ]

        (case,) = _read_with(tmp_path, Index=index)

        assert case.extra_fields == [("Zeta", "z"), ("Alpha", "a"), ("Mid", "m")]

    def test_index_is_the_first_sheet_whatever_its_name(self, tmp_path: Path) -> None:
        sheets = {"Test cases": _valid_sheets()["Index"], **_valid_sheets()}
        del sheets["Index"]

        cases = read_workbook(_write_workbook(tmp_path / "spec.xlsx", sheets))

        assert [case.test_id for case in cases] == ["1.1", "1.2"]

    @pytest.mark.parametrize(
        ("headers", "message"),
        [
            (
                ["ID", "Name", "Description", "Tags", "", "Extra"],
                "column 5 has no header",
            ),
            (["ID", "Name", "Description", "Tags", "name"], "duplicate column 'name'"),
        ],
    )
    def test_rejects_blank_or_repeated_headers(
        self, tmp_path: Path, headers: list[str], message: str
    ) -> None:
        with pytest.raises(TestSpecError, match=message):
            _read_with(tmp_path, Index=[headers, ["1.1", "Leg", "", "", "", ""]])

    def test_rejects_index_without_test_cases(self, tmp_path: Path) -> None:
        sheets = {"Index": [INDEX_HEADERS]}

        with pytest.raises(TestSpecError, match="'Index' has no test cases"):
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
        sheets["1.1 - Inputs"] = [["Name", "Value"], ["mtu", cell_value]]

        first, _ = read_workbook(_write_workbook(tmp_path / "spec.xlsx", sheets))

        assert first.inputs is not None
        assert first.inputs.rows[0][-1] == expected


class TestRenderTestCase:
    @staticmethod
    def _macro_body(macro: etree._Element) -> str:
        return macro.findtext("{http://atlassian.com/content}plain-text-body")

    @staticmethod
    def _macro_language(macro: etree._Element) -> str:
        return macro.findtext("{http://atlassian.com/content}parameter")

    @staticmethod
    def _rows(table: etree._Element) -> list[list[str]]:
        """Cell text of every row, line breaks collapsed to a space."""
        return [
            [" ".join("".join(cell.itertext()).split()) for cell in row]
            for row in table.iter("tr")
        ]

    @staticmethod
    def _details(root: etree._Element) -> list[str]:
        """Text of the paragraphs that come before the Description heading."""
        details = []
        for child in root:
            if child.tag == "h2":
                break
            if child.tag == "p":
                details.append("".join(child.itertext()))
        return details

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

    def test_renders_tags_first_then_additional_columns_in_table_order(
        self, workbook_path: Path
    ) -> None:
        assert self._details(self._render(workbook_path, 0)) == [
            "Tags: L3VPN, Hub",
            "Vendor: Cisco",
            "Priority: High",
        ]

    def test_empty_fields_render_a_dash(self, workbook_path: Path) -> None:
        assert self._details(self._render(workbook_path, 1)) == [
            "Tags: -",
            "Vendor: Nokia",
            "Priority: -",
        ]

    def test_multiline_additional_values_use_line_breaks(self) -> None:
        case = _case("1.1", extra_fields=[("Notes", "first\nsecond")])

        body = render_test_case(case, Path("spec.xlsx"), generated_by="")
        root = etree.fromstring(f"<root>{body}</root>")
        notes = root.findall("p")[1]

        assert notes.find("strong").tail == " first"
        assert notes.find("br").tail == "second"

    def test_tables_render_as_written(self, workbook_path: Path) -> None:
        root = self._render(workbook_path, 0, generated_by="")
        inputs, outputs = root.findall("table")

        assert self._rows(inputs) == [
            ["Characteristic", "Type", "Value"],
            ["mtu", "integer", "9000"],
            ["vrfName", "string", "A"],
        ]
        assert self._rows(outputs)[0] == ["Target", "CLI", "JSON"]
        assert self._rows(outputs)[1][:2] == ["/vrfs", "vrf A address-family ipv4"]

    def test_only_json_columns_become_code_blocks(self, workbook_path: Path) -> None:
        root = self._render(workbook_path, 0, generated_by="")

        assert not list(root.findall("table")[0].iter(_MACRO))
        macros = list(root.findall("table")[1].iter(_MACRO))
        assert [self._macro_body(m) for m in macros] == ['{"vrf-name":"A"}']
        assert [self._macro_language(m) for m in macros] == ["json"]

    def test_multiline_cells_keep_their_line_breaks(self, workbook_path: Path) -> None:
        outputs = self._render(workbook_path, 0).findall("table")[1]
        cell = outputs.findall(".//tr")[1].findall("td")[1]

        assert cell.text == "vrf A"
        assert cell.find("br").tail == " address-family ipv4"

    @pytest.mark.parametrize(
        "table",
        [
            [["Expected"], ['{"a": {"b": 1}}']],
            [["Parameter", "Value"], ["mtu", "9000"], ["vrf", "A"]],
            [["x"], ["<b>&amp; not markup</b>"]],
        ],
    )
    def test_any_table_round_trips(self, table: list[list[str]]) -> None:
        case = _case("1.1")
        case.outputs = SheetTable(headers=table[0], rows=table[1:])

        body = render_test_case(case, Path("spec.xlsx"), generated_by="")
        root = etree.fromstring(f"<root>{body}</root>")

        assert self._rows(root.findall("table")[0]) == table

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


def _case(
    test_id: str,
    tags: list[str] | None = None,
    extra_fields: list[tuple[str, str]] | None = None,
) -> TestCase:
    return TestCase(
        test_id=test_id,
        name=f"Test {test_id}",
        description="",
        tags=tags or [],
        extra_fields=extra_fields or [],
    )


def test_page_labels_are_only_the_tags_made_confluence_safe_and_unique() -> None:
    case = _case(
        "1.1",
        ["Active/Active", "L3VPN", "l3vpn", "  "],
        extra_fields=[("Vendor", "Cisco")],
    )

    assert page_labels(case) == ["active-active", "l3vpn"]


def _config(**overrides: object) -> TestSpecSyncConfig:
    values: dict = {
        "space_key": "HaaS",
        "parent_id": "100",
        "source_file": Path("spec.xlsx"),
        "suite": "L3VPN",
    }
    values.update(overrides)
    return TestSpecSyncConfig(**values)


class TestSyncTestCases:
    @patch("sync_confluence.testspec._sync.build_source_path_map", return_value={})
    @patch("sync_confluence.testspec._sync.upsert_page")
    @patch("sync_confluence.testspec._sync.upsert_folder")
    def test_one_suite_folder_and_pages_sorted_by_id(
        self,
        mock_folder: MagicMock,
        mock_page: MagicMock,
        mock_path_map: MagicMock,
    ) -> None:
        mock_folder.return_value = ("f-suite", "created")
        mock_page.return_value = ("p", "created")
        cases = [_case("1.10", ["a"]), _case("1.2"), _case("1.1")]

        result = sync_test_cases(MagicMock(), cases, _config())

        (folder,) = [c.args[1] for c in mock_folder.call_args_list]
        assert (folder.title, folder.parent_id) == ("L3VPN", "100")
        assert folder.source_path == "testspec/L3VPN"
        pages = [c.args[1] for c in mock_page.call_args_list]
        assert [(p.title, p.parent_id, p.source_path) for p in pages] == [
            ("1.1 - Test 1.1 (L3VPN)", "f-suite", "testspec/L3VPN/1.1"),
            ("1.2 - Test 1.2 (L3VPN)", "f-suite", "testspec/L3VPN/1.2"),
            ("1.10 - Test 1.10 (L3VPN)", "f-suite", "testspec/L3VPN/1.10"),
        ]
        assert pages[2].labels == ["a"]
        assert result.stats["created"] == 3
        assert result.expected_titles == {
            "L3VPN",
            "1.1 - Test 1.1 (L3VPN)",
            "1.2 - Test 1.2 (L3VPN)",
            "1.10 - Test 1.10 (L3VPN)",
        }
        assert result.expected_paths == {
            "testspec/L3VPN",
            "testspec/L3VPN/1.1",
            "testspec/L3VPN/1.2",
            "testspec/L3VPN/1.10",
        }
        assert mock_path_map.call_count == 1
        assert mock_path_map.call_args.args[1] == "f-suite"

    @patch("sync_confluence.testspec._sync.build_source_path_map")
    @patch("sync_confluence.testspec._sync.upsert_page", return_value=(None, "skipped"))
    @patch(
        "sync_confluence.testspec._sync.upsert_folder",
        return_value=("DRY-RUN", "created"),
    )
    @patch(
        "sync_confluence.confluence._folder_ownership.find_folder_under_parent",
        return_value=None,
    )
    def test_skipped_pages_are_reported_and_dry_run_skips_path_map(
        self,
        mock_find: MagicMock,
        mock_folder: MagicMock,
        mock_page: MagicMock,
        mock_path_map: MagicMock,
    ) -> None:
        result = sync_test_cases(MagicMock(), [_case("1.1")], _config(dry_run=True))

        assert result.skipped == ["1.1 - Test 1.1 (L3VPN)"]
        assert result.stats["skipped"] == 1
        assert "1.1 - Test 1.1 (L3VPN)" not in result.expected_titles
        mock_path_map.assert_not_called()

    @patch("sync_confluence.testspec._sync.build_source_path_map", return_value={})
    @patch("sync_confluence.testspec._sync.upsert_page", return_value=("7", "updated"))
    @patch("sync_confluence.testspec._sync.upsert_folder")
    @patch(
        "sync_confluence.confluence._folder_ownership.find_folder_under_parent",
        return_value={"id": "f-suite"},
    )
    def test_dry_run_uses_existing_suite_folder_for_page_lookups(
        self,
        mock_find: MagicMock,
        mock_folder: MagicMock,
        mock_page: MagicMock,
        mock_path_map: MagicMock,
    ) -> None:
        result = sync_test_cases(MagicMock(), [_case("1.1")], _config(dry_run=True))

        mock_folder.assert_not_called()
        assert mock_find.call_args.args[2] == "L3VPN"
        assert mock_page.call_args.args[1].parent_id == "f-suite"
        assert mock_path_map.call_args.args[1] == "f-suite"
        assert result.stats["updated"] == 1

    @patch(
        "sync_confluence.confluence._folder_ownership._page_has_label",
        return_value=False,
    )
    @patch("sync_confluence.testspec._sync.upsert_page")
    @patch(
        "sync_confluence.confluence._folder_ownership.find_folder_under_parent",
        return_value={"id": "f-user"},
    )
    def test_dry_run_refuses_unowned_suite_folder(
        self,
        mock_find: MagicMock,
        mock_page: MagicMock,
        mock_has_label: MagicMock,
    ) -> None:
        config = _config(dry_run=True, managed_by_label="managed-by-repo-testspec")

        with pytest.raises(FolderNotOwnedError, match="f-user"):
            sync_test_cases(MagicMock(), [_case("1.1")], config)

        mock_page.assert_not_called()

    @patch("sync_confluence.testspec._sync.build_source_path_map", return_value={})
    @patch("sync_confluence.testspec._sync.upsert_page", return_value=("p", "created"))
    @patch(
        "sync_confluence.testspec._sync.upsert_folder", return_value=("f", "created")
    )
    def test_suite_folder_requires_ownership(
        self, mock_folder: MagicMock, mock_page: MagicMock, mock_map: MagicMock
    ) -> None:
        sync_test_cases(MagicMock(), [_case("1.1")], _config())

        assert mock_folder.call_args.args[1].require_ownership is True


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
        format_json=False,
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


def _render_json_table(
    cells: list[str], header: str = "JSON", reformat: bool = False
) -> etree._Element:
    case = _case("1.1")
    case.outputs = SheetTable(headers=[header], rows=[[cell] for cell in cells])
    body = render_test_case(case, Path("spec.xlsx"), "", reformat_json=reformat)
    root = etree.fromstring(
        f'<root xmlns:ac="http://atlassian.com/content">{body}</root>'
    )
    return root.find("table")


def _bodies(table: etree._Element) -> list[str]:
    return [
        m.findtext("{http://atlassian.com/content}plain-text-body")
        for m in table.iter(_MACRO)
    ]


class TestJsonColumns:
    PRETTY = '{\n  "a": 1\n}'

    @pytest.mark.parametrize("header", ["JSON", "json", " Json "])
    def test_header_is_matched_ignoring_case_and_spaces(self, header: str) -> None:
        table = _render_json_table(['{"a":1}'], header=header)

        assert _bodies(table) == ['{"a":1}']

    def test_other_headers_are_plain_text(self) -> None:
        table = _render_json_table(['{"a":1}'], header="Response")

        assert _bodies(table) == []
        assert "".join(table.findall(".//td")[0].itertext()) == '{"a":1}'

    def test_text_is_kept_as_written_by_default(self) -> None:
        written = '{"b":1,   "a":[1,2]}'

        assert _bodies(_render_json_table([written])) == [written]

    @pytest.mark.parametrize(
        "invalid",
        ['"items": [ {"sku": "A"} ]', '{"a": 1, ...}', '{"a":1}\n{"b":2}', "n/a"],
    )
    def test_invalid_json_is_shown_unchanged_and_logged(
        self, invalid: str, caplog: pytest.LogCaptureFixture
    ) -> None:
        with caplog.at_level("WARNING"):
            table = _render_json_table(["{}", invalid], reformat=True)

        assert _bodies(table) == ["{}", invalid]
        (record,) = caplog.records
        assert "Sheet '1.1 - Outputs' data row 2: not valid JSON" in record.message

    def test_valid_json_does_not_warn(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level("WARNING"):
            _render_json_table(['{"a":1}', "9000"])

        assert not caplog.records

    def test_empty_cells_are_not_code_blocks(self) -> None:
        table = _render_json_table(["", '{"a":1}'])

        assert _bodies(table) == ['{"a":1}']

    def test_reformat_pretty_prints_valid_json_only(self) -> None:
        table = _render_json_table(['{"a":1}', "not json"], reformat=True)

        assert _bodies(table) == [self.PRETTY, "not json"]

    def test_reformat_keeps_unicode_and_big_numbers(self) -> None:
        table = _render_json_table(
            ['{"n": 12345678901234567890, "u": "caf\\u00e9"}'], reformat=True
        )

        assert _bodies(table) == [
            '{\n  "n": 12345678901234567890,\n  "u": "caf\u00e9"\n}'
        ]

    def test_reformat_drops_duplicate_keys_which_is_why_it_is_opt_in(self) -> None:
        table = _render_json_table(['{"d": 1, "d": 2}'], reformat=True)

        assert _bodies(table) == ['{\n  "d": 2\n}']

    def test_flag_and_env_turn_reformatting_on(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("TESTSPEC_FORMAT_JSON", raising=False)
        assert parse_testspec_sync_args([]).format_json is False
        assert parse_testspec_sync_args(["--format-json"]).format_json is True
        monkeypatch.setenv("TESTSPEC_FORMAT_JSON", "true")
        assert parse_testspec_sync_args([]).format_json is True
        monkeypatch.setenv("TESTSPEC_FORMAT_JSON", "no")
        assert parse_testspec_sync_args([]).format_json is False

    @patch("sync_confluence.testspec._sync.build_source_path_map", return_value={})
    @patch("sync_confluence.testspec._sync.upsert_page", return_value=("p", "created"))
    @patch(
        "sync_confluence.testspec._sync.upsert_folder", return_value=("f", "created")
    )
    def test_sync_passes_the_setting_to_the_page_body(
        self, mock_folder: MagicMock, mock_page: MagicMock, mock_map: MagicMock
    ) -> None:
        case = _case("1.1")
        case.outputs = SheetTable(headers=["JSON"], rows=[['{"a":1}']])

        sync_test_cases(MagicMock(), [case], _config(reformat_json=True))

        assert self.PRETTY in mock_page.call_args.args[1].body
