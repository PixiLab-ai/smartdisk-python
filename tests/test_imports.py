"""Import: conversations, documents, URLs, OCR, the sync cursor, and waiting."""

from __future__ import annotations

import base64

import pytest

MESSAGES = [
    {"role": "user", "content": "What did we decide about the schedule?"},
    {"role": "assistant", "content": "We moved the launch to March."},
]


# --- conversations ------------------------------------------------------ #


def test_chat_by_slug_uses_the_disk_creating_route(client, server):
    server.reply({"disk_uuid": "d", "content_uuid": "c", "messages_added": 2, "status": "queued"})
    result = client.imports.chat("support-bot", MESSAGES)
    assert server.last.suffix == "/sd/import/chatml"
    assert server.last.json["disk_slug"] == "support-bot"
    assert server.last.json["messages"] == MESSAGES
    assert result.messages_added == 2
    assert result.skipped is False


def test_chat_by_uuid_uses_the_per_disk_route(client, server, disk):
    client.imports.chat(disk, MESSAGES)
    assert server.last.suffix == f"/sd/disks/{disk.uuid}/import/chatml"
    assert "disk_slug" not in server.last.json


def test_chat_sends_the_optional_labels(client, server):
    client.imports.chat(
        "support-bot",
        MESSAGES,
        name="ticket-4471",
        folder_path="/tickets",
        persona="agent",
        source="zendesk",
        disk_name="Support bot",
    )
    body = server.last.json
    assert body["name"] == "ticket-4471"
    assert body["folder_path"] == "/tickets"
    assert body["persona"] == "agent"
    assert body["source"] == "zendesk"
    assert body["disk_name"] == "Support bot"


def test_chat_keeps_per_message_timestamps_and_ids(client, server, disk):
    client.imports.chat(
        disk,
        [{"role": "user", "content": "hi", "timestamp": "2026-05-31T08:00:00Z", "uuid": "m-1"}],
    )
    assert server.last.json["messages"][0]["timestamp"] == "2026-05-31T08:00:00Z"
    assert server.last.json["messages"][0]["uuid"] == "m-1"


def test_chat_drops_messages_without_a_role(client, server, disk):
    client.imports.chat(disk, [{"content": "orphan"}, {"role": "user", "content": "kept"}])
    assert server.last.json["messages"] == [{"role": "user", "content": "kept"}]


def test_chat_with_nothing_importable_fails_before_the_request(client, server, disk):
    with pytest.raises(ValueError, match="nothing to import"):
        client.imports.chat(disk, [{"content": "no role"}])
    assert len(server) == 0


def test_chat_sends_an_alias_map_when_given(client, server, disk):
    client.imports.chat(disk, MESSAGES, aliases={"user": "alex", "assistant": "aria"})
    assert server.last.json["aliases"] == {"user": "alex", "assistant": "aria"}


# --- documents ---------------------------------------------------------- #


def test_document_posts_a_text_body(client, server, disk):
    server.reply({"content_uuid": "7d2c", "skipped": False, "status": "queued"})
    result = client.imports.document(disk, body="# Q2 report", name="q2.md", folder_path="/reports")
    assert server.last.suffix == f"/sd/disks/{disk.uuid}/import/doc"
    assert server.last.json == {"body": "# Q2 report", "name": "q2.md", "folder_path": "/reports"}
    assert result.content_uuid == "7d2c"


def test_document_reads_a_text_file_and_infers_its_name(client, server, disk, tmp_path):
    note = tmp_path / "planning.md"
    note.write_text("# Planning\n\nWe moved the launch.", encoding="utf-8")
    client.imports.document(disk, path=note)
    assert server.last.json["name"] == "planning.md"
    assert server.last.json["body"].startswith("# Planning")
    assert "body_b64" not in server.last.json


def test_document_base64s_a_binary_file_and_names_its_format(client, server, disk, tmp_path):
    pdf = tmp_path / "report.pdf"
    pdf.write_bytes(b"%PDF-1.7 not really")
    client.imports.document(disk, path=pdf, folder_path="/reports")
    body = server.last.json
    assert body["format"] == "pdf"
    assert base64.b64decode(body["body_b64"]) == b"%PDF-1.7 not really"
    assert "body" not in body


def test_document_ocrs_an_image_by_extension(client, server, disk, tmp_path):
    shot = tmp_path / "invoice.png"
    shot.write_bytes(b"\x89PNG fake")
    client.imports.document(disk, path=shot)
    assert server.last.json["format"] == "png"
    assert "body_b64" in server.last.json


def test_document_accepts_raw_bytes_with_a_format(client, server, disk):
    client.imports.document(disk, data=b"binary", format="xlsx", name="sheet.xlsx")
    assert server.last.json["format"] == "xlsx"
    assert base64.b64decode(server.last.json["body_b64"]) == b"binary"


def test_document_refuses_bytes_without_a_format(client, server, disk):
    with pytest.raises(ValueError, match="format is required"):
        client.imports.document(disk, data=b"binary")
    assert len(server) == 0


def test_document_refuses_two_sources_of_content(client, server, disk):
    with pytest.raises(ValueError, match="exactly one"):
        client.imports.document(disk, body="text", data=b"bytes")
    assert len(server) == 0


def test_document_refuses_no_content_at_all(client, server, disk):
    with pytest.raises(ValueError, match="exactly one"):
        client.imports.document(disk)


def test_document_reports_an_auto_detected_chat_export(client, server, disk):
    server.reply(
        {
            "mode": "chat-export",
            "format": "claude-export",
            "conversations": 97,
            "messages": 2281,
            "status": "queued",
        }
    )
    result = client.imports.document(disk, body="{...}", name="conversations.json")
    assert result.is_chat_export
    assert result.conversations == 97


def test_document_reports_a_skip(client, server, disk):
    server.reply({"content_uuid": "7d2c", "skipped": True, "status": "processed"})
    assert client.imports.document(disk, body="same as before").skipped is True


# --- urls and OCR -------------------------------------------------------- #


def test_url_import_posts_the_link(client, server, disk):
    server.reply({"content_uuid": "e91a", "status": "queued", "source_type": "web", "title": "Example"})
    result = client.imports.url(disk, "https://example.com/article")
    assert server.last.suffix == f"/sd/disks/{disk.uuid}/import/url"
    assert server.last.json == {"url": "https://example.com/article"}
    assert result.source_type == "web"


def test_url_import_can_name_the_document(client, server, disk):
    client.imports.url(disk, "https://example.com/a", name="The article")
    assert server.last.json["name"] == "The article"


def test_ocr_is_disk_independent(client, server):
    server.reply({"text": "Solar Open 2 Technical Report", "chars": 2466})
    result = client.imports.ocr(data=b"\x89PNG", format="png")
    assert server.last.suffix == "/sd/ocr"
    assert base64.b64decode(server.last.json["image_b64"]) == b"\x89PNG"
    assert result.chars == 2466


def test_ocr_infers_the_format_from_a_path(client, server, tmp_path):
    shot = tmp_path / "scan.jpeg"
    shot.write_bytes(b"jpegbytes")
    client.imports.ocr(path=shot)
    assert server.last.json["format"] == "jpeg"


def test_ocr_refuses_two_sources(client, server):
    with pytest.raises(ValueError, match="exactly one"):
        client.imports.ocr(data=b"x", image_b64="eA==")


# --- sync and processing -------------------------------------------------- #


def test_last_reads_the_sync_cursor(client, server, disk):
    server.reply(
        {
            "content_uuid": "4a7b",
            "original_uuid": "m-9",
            "original_timestamp": "2026-05-31T08:00:00Z",
            "name": "chat",
            "empty": False,
        }
    )
    cursor = client.imports.last(disk)
    assert server.last.suffix == f"/sd/disks/{disk.uuid}/import/last"
    assert cursor.empty is False
    assert cursor.original_uuid == "m-9"


def test_an_untouched_disk_reports_an_empty_cursor(client, server, disk):
    server.reply({"empty": True})
    assert client.imports.last(disk).empty is True


def test_retry_requeues_one_source(client, server, disk):
    server.reply({"status": "queued"})
    assert client.imports.retry(disk, "4a7b") == "queued"
    assert server.last.method == "POST"
    assert server.last.suffix == f"/sd/disks/{disk.uuid}/contents/4a7b/retry"


def test_wait_polls_until_everything_is_processed(client, server, disk):
    server.reply({"contents": [{"uuid": "a", "status": "processing"}], "consolidating": False})
    server.reply({"contents": [{"uuid": "a", "status": "processed"}], "consolidating": False})
    listing = client.imports.wait_until_processed(disk, poll_interval=0)
    assert len(server) == 2
    assert listing.all_processed


def test_wait_ignores_consolidation_unless_asked(client, server, disk):
    server.reply({"contents": [{"uuid": "a", "status": "processed"}], "consolidating": True})
    client.imports.wait_until_processed(disk, poll_interval=0)
    assert len(server) == 1


def test_wait_can_also_wait_out_consolidation(client, server, disk):
    server.reply({"contents": [{"uuid": "a", "status": "processed"}], "consolidating": True})
    server.reply({"contents": [{"uuid": "a", "status": "processed"}], "consolidating": False})
    client.imports.wait_until_processed(disk, poll_interval=0, wait_for_consolidation=True)
    assert len(server) == 2


def test_wait_raises_on_a_failed_source(client, server, disk):
    server.reply({"contents": [{"uuid": "a", "name": "broken.pdf", "status": "failed"}]})
    with pytest.raises(RuntimeError, match="broken.pdf"):
        client.imports.wait_until_processed(disk, poll_interval=0)


def test_wait_times_out_rather_than_hanging(client, server, disk):
    for _ in range(3):
        server.reply({"contents": [{"uuid": "a", "status": "queued"}]})
    with pytest.raises(TimeoutError):
        client.imports.wait_until_processed(disk, poll_interval=0, timeout=-1)


def test_wait_reports_progress_when_asked(client, server, disk):
    server.reply({"contents": [{"uuid": "a", "status": "processing"}]})
    server.reply({"contents": [{"uuid": "a", "status": "processed"}]})
    lines: list[str] = []
    client.imports.wait_until_processed(disk, poll_interval=0, on_progress=lines.append)
    assert lines == ["0/1 processed", "1/1 processed"]
