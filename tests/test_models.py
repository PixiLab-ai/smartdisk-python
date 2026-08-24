"""Parsing: forgiving where the wire is loose, exact where it matters."""

from __future__ import annotations

from smartdisk import Content, ContentList, Disk, Fact, Freshness, Memory, Retrieval
from smartdisk._util import format_for_path, is_binary_format, is_uuid


def test_unknown_fields_survive_on_raw():
    disk = Disk.from_dict({"uuid": "u", "name": "n", "something_new": 42})
    assert disk.raw["something_new"] == 42


def test_missing_fields_take_their_defaults():
    disk = Disk.from_dict({})
    assert disk.uuid == "" and disk.document_count is None


def test_a_null_where_a_number_belongs_does_not_crash():
    fact = Fact.from_dict({"text": "x", "reinforced_count": None, "priority": None})
    assert fact.reinforced_count == 0
    assert fact.priority is None


def test_a_string_number_is_read_as_a_number():
    assert Fact.from_dict({"reinforced_count": "3"}).reinforced_count == 3


def test_empty_optional_timestamps_become_none():
    fact = Fact.from_dict({"valid_from": "2022-03-01T00:00:00Z", "valid_to": ""})
    assert fact.valid_from == "2022-03-01T00:00:00Z"
    assert fact.valid_to is None


def test_a_content_hash_is_never_coerced_to_an_int():
    row = Content.from_dict({"content_hash": "-2425632407680798700"})
    assert row.content_hash == "-2425632407680798700"
    assert isinstance(row.content_hash, str)


def test_freshness_is_none_until_a_first_summary_lands():
    row = Content.from_dict({"uuid": "a", "status": "processed", "freshness": None, "stale": False})
    assert row.freshness is None and row.stale is False


def test_freshness_reports_what_the_summary_covered():
    row = Content.from_dict({"freshness": {"source_count": 200, "window_count": 4, "pending": True}})
    assert isinstance(row.freshness, Freshness)
    assert row.freshness.source_count == 200 and row.freshness.pending is True


def test_a_content_list_is_iterable_and_sized():
    listing = ContentList.from_dict({"contents": [{"uuid": "a", "status": "processed"},
                                                  {"uuid": "b", "status": "queued"}]})
    assert len(listing) == 2
    assert [row.uuid for row in listing] == ["a", "b"]
    assert listing.all_processed is False


def test_an_empty_disk_is_not_all_processed():
    assert ContentList.from_dict({"contents": []}).all_processed is False


def test_failed_rows_are_easy_to_find():
    listing = ContentList.from_dict({"contents": [{"uuid": "a", "status": "failed"},
                                                  {"uuid": "b", "status": "processed"}]})
    assert [row.uuid for row in listing.failed] == ["a"]


def test_rows_that_are_not_objects_are_skipped():
    listing = ContentList.from_dict({"contents": [None, "junk", {"uuid": "a"}]})
    assert len(listing) == 1


def test_a_missing_list_is_an_empty_list():
    assert Memory.from_dict({}).facts == []


def test_object_uuids_are_deduplicated_in_rank_order():
    result = Retrieval.from_dict({"citations": [{"object_uuid": "a", "content_uuid": "c1"},
                                                {"object_uuid": "b", "content_uuid": "c1"},
                                                {"object_uuid": "a", "content_uuid": "c2"}]})
    assert result.object_uuids == ["a", "b"]
    assert result.content_uuids == ["c1", "c2"]


def test_a_citation_without_a_trace_has_no_explain():
    result = Retrieval.from_dict({"citations": [{"n": 1}]})
    assert result.citations[0].explain is None


# --- helpers ------------------------------------------------------------ #


def test_uuids_are_told_apart_from_slugs():
    assert is_uuid("11111111-2222-3333-4444-555555555555")
    assert not is_uuid("research")
    assert not is_uuid("")


def test_formats_are_inferred_from_the_filename():
    assert format_for_path("q2.pdf") == "pdf"
    assert format_for_path("notes.md") == "markdown"
    assert format_for_path("scan.TIFF") == "tiff"
    assert format_for_path("paper.tex") == "latex"
    assert format_for_path("mystery.zzz") == ""


def test_binary_and_image_formats_travel_as_base64():
    assert is_binary_format("pdf")
    assert is_binary_format("png")
    assert not is_binary_format("markdown")
    assert not is_binary_format("html")
