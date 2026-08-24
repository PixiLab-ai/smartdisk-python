"""Agent tools — the read-only lookups, and the shapes they come back in."""

from __future__ import annotations

import json

import pytest

import smartdisk

# --- read one source ---------------------------------------------------- #


def test_read_returns_a_document_body(client, server, disk):
    server.reply(
        {
            "content": {"uuid": "7d2c", "name": "Q2 report", "content_type": "doc", "is_container": True},
            "body": "# Q2 report\n\n...",
            "sections": [{"uuid": "9f31", "name": "Revenue", "status": "processed"}],
            "total": 412903,
            "offset": 0,
            "limit": 200,
            "truncated": True,
        }
    )
    source = client.tools.read(disk, "7d2c")
    assert server.last.suffix == f"/sd/disks/{disk.uuid}/contents/7d2c"
    assert source.body.startswith("# Q2 report")
    assert source.sections[0].name == "Revenue"
    assert source.total == 412903
    assert source.truncated and not source.is_chat


def test_read_pages_a_conversation(client, server, disk):
    server.reply(
        {
            "content": {"uuid": "4a7b", "name": "Planning call", "content_type": "chat"},
            "messages": [
                {
                    "uuid": "c2f8",
                    "role": "user",
                    "text": "What did we decide?",
                    "sort_order": 0,
                    "original_timestamp": "2026-05-31T08:00:00Z",
                    "original_uuid": "your-message-id",
                }
            ],
            "total": 240,
            "offset": 200,
            "limit": 200,
            "truncated": True,
        }
    )
    source = client.tools.read(disk, "4a7b", offset=200, limit=200)
    assert server.last.params == {"offset": "200", "limit": "200"}
    assert source.is_chat
    assert source.messages[0].original_uuid == "your-message-id"


def test_reading_a_source_from_another_disk_is_a_not_found(client, server, disk):
    server.fail(404, "content_not_found")
    with pytest.raises(smartdisk.NotFoundError):
        client.tools.read(disk, "guessed-uuid")


# --- grep --------------------------------------------------------------- #


def test_grep_sends_the_pattern_in_the_query(client, server, disk):
    server.reply(
        {
            "hits": [
                {
                    "content_uuid": "4a7b",
                    "content_name": "Planning call",
                    "content_type": "chat",
                    "message_uuid": "c2f8",
                    "sort_order": 12,
                    "ts": "2026-05-31T08:04:00Z",
                    "snippet": "...ERR_CONN_RESET...",
                }
            ],
            "pattern": "ERR_[A-Z_]+",
            "path": "/",
            "limit": 50,
            "truncated": False,
        }
    )
    result = client.tools.grep(disk, "ERR_[A-Z_]+", limit=50, path="/imports")
    assert server.last.suffix == f"/sd/disks/{disk.uuid}/grep"
    assert server.last.params == {"pattern": "ERR_[A-Z_]+", "limit": "50", "path": "/imports"}
    assert len(result) == 1
    assert result.hits[0].sort_order == 12


def test_grep_sends_the_case_flag_only_when_asked(client, server, disk):
    client.tools.grep(disk, "err", case_insensitive=True)
    assert server.last.params["case_insensitive"] == "1"
    client.tools.grep(disk, "err", case_insensitive=False)
    assert "case_insensitive" not in server.last.params


def test_a_pattern_that_does_not_compile_is_a_bad_request(client, server, disk):
    server.fail(400, "bad_pattern")
    with pytest.raises(smartdisk.BadRequestError) as caught:
        client.tools.grep(disk, "(unclosed")
    assert caught.value.code == "bad_pattern"


# --- export ------------------------------------------------------------- #


def test_export_returns_the_rendered_file_not_an_envelope(client, server, disk):
    server.text("uuid,text\nf1,Alex works at Northwind Trading.\n")
    body = client.tools.export(disk, format="csv", include="facts,edges", path="/research")
    assert server.last.params == {"format": "csv", "include": "facts,edges", "path": "/research"}
    assert body.splitlines()[0] == "uuid,text"


def test_export_defaults_to_the_servers_own_defaults(client, server, disk):
    server.text("{}")
    client.tools.export(disk)
    assert server.last.params == {}


GRAPH = '{"disk": "d1", "facts": [{"uuid": "f1", "text": "Alex works at Northwind."}], "edges": []}'


def test_export_returns_a_bare_graph_untouched(client, server, disk):
    server.text(GRAPH, content_type="application/json")
    body = client.tools.export(disk)
    assert json.loads(body)["facts"][0]["uuid"] == "f1"


def test_export_peels_an_envelope_a_proxy_wrapped_it_in(client, server, disk):
    server.text(f'{{"data": {GRAPH}, "result": "success"}}', content_type="application/json")
    body = client.tools.export(disk)
    parsed = json.loads(body)
    assert sorted(parsed) == ["disk", "edges", "facts"]
    assert parsed["facts"][0]["uuid"] == "f1"


def test_export_leaves_a_json_object_that_is_not_the_envelope_alone(client, server, disk):
    # "data" without "result" is somebody's fact graph, not our envelope.
    server.text('{"data": {"facts": []}}', content_type="application/json")
    assert json.loads(client.tools.export(disk)) == {"data": {"facts": []}}


def test_export_leaves_non_json_formats_alone(client, server, disk):
    server.text("@prefix ex: <http://example.org/> .\n")
    assert client.tools.export(disk, format="turtle").startswith("@prefix")


# --- hubs --------------------------------------------------------------- #


def test_hubs_ranks_entities(client, server, disk):
    server.reply(
        {
            "hubs": [
                {
                    "name": "alex",
                    "category": "career",
                    "facts": 118,
                    "degree_in": 9,
                    "degree_out": 47,
                    "weighted_degree": 56,
                    "pagerank": 0.0731,
                }
            ],
            "nodes": 1284,
            "edges": 3910,
            "top": 20,
            "hubs_total": 612,
            "truncated": True,
            "path": "/",
        }
    )
    hubs = client.tools.hubs(disk, top=20)
    assert server.last.params == {"top": "20"}
    assert len(hubs) == 1
    assert hubs.hubs[0].pagerank == 0.0731
    assert hubs.hubs_total == 612


def test_hubs_refuses_rather_than_truncating_a_huge_graph(client, server, disk):
    server.fail(413, "too_large", edges_total=90210, max_edges=50000)
    with pytest.raises(smartdisk.TooLargeError):
        client.tools.hubs(disk)


# --- lint --------------------------------------------------------------- #


def test_lint_parses_every_section(client, server, disk):
    server.reply(
        {
            "disk": "9c1e",
            "generated_at": "2026-08-23T11:02:41Z",
            "path": "/",
            "limit": 50,
            "sections": {
                "dirty_backlog": {"total": 42, "returned": 42, "items": [], "oldest_age_seconds": 913},
                "fragmented_groups": {"total": 9, "returned": 9, "items": [], "min_facts": 3},
            },
            "totals": {"dirty_backlog": 42},
        }
    )
    report = client.tools.lint(disk, path="/research", limit=50)
    assert server.last.params == {"path": "/research", "limit": "50"}
    assert report.sections["dirty_backlog"].total == 42
    assert report.sections["dirty_backlog"].raw["oldest_age_seconds"] == 913
    assert report.failed_sections == []


def test_a_failed_lint_section_is_visible_without_failing_the_call(client, server, disk):
    # Each section is fenced: a 200 does not mean all seven succeeded.
    server.reply(
        {
            "sections": {
                "bare_relational": {"error": "scan timed out", "total": None},
                "dup_summaries": {"total": 3, "returned": 3, "items": []},
            }
        }
    )
    report = client.tools.lint(disk)
    assert [section.name for section in report.failed_sections] == ["bare_relational"]
    assert report.sections["bare_relational"].ok is False
    assert report.sections["dup_summaries"].ok is True


# --- extract preview ----------------------------------------------------- #


def test_extract_preview_posts_text_and_stores_nothing(client, server, disk):
    server.reply(
        {
            "facts": [
                {
                    "text": "Alex joined Northwind Trading in March 2022.",
                    "subject": "alex",
                    "predicate": "joined",
                    "object": "northwind",
                    "category": "career",
                    "valid_from": "2022-03-01T00:00:00Z",
                    "temporal_confidence": 0.9,
                    "temporal_source_text": "in March 2022",
                }
            ],
            "dropped": 2,
            "chars": 1841,
            "truncated": False,
        }
    )
    preview = client.tools.extract_preview(disk, "Alex joined Northwind in March 2022.")
    assert server.last.method == "POST"
    assert server.last.suffix == f"/sd/disks/{disk.uuid}/extract-preview"
    assert server.last.json == {"text": "Alex joined Northwind in March 2022."}
    assert len(preview) == 1
    assert preview.dropped == 2
    assert preview.facts[0].temporal_source_text == "in March 2022"


def test_extract_preview_takes_an_alias_map(client, server, disk):
    client.tools.extract_preview(disk, "text", aliases={"user": "alex"})
    assert server.last.json["aliases"] == {"user": "alex"}


def test_a_vague_date_is_reported_without_being_rounded_up(client, server, disk):
    server.reply(
        {
            "facts": [
                {
                    "text": "Alex moved recently.",
                    "valid_from": None,
                    "temporal_confidence": 0.35,
                    "temporal_source_text": "recently",
                }
            ],
            "dropped": 0,
            "chars": 20,
        }
    )
    fact = client.tools.extract_preview(disk, "Alex moved recently.").facts[0]
    assert fact.valid_from is None
    assert fact.temporal_confidence == 0.35


# --- consolidation audit -------------------------------------------------- #


def test_consolidation_runs_lists_counts_only(client, server, disk):
    server.reply(
        {
            "runs": [
                {
                    "uuid": "e41a",
                    "seed_fact_uuid": "f1",
                    "duration_ms": 7104,
                    "tier_counts": {"exact": 4, "lexical": 2, "llm": 1},
                    "facts_closed": 6,
                    "facts_rewritten": 1,
                    "clusters": 3,
                }
            ],
            "returned": 1,
            "limit": 20,
        }
    )
    runs = client.tools.consolidation_runs(disk, limit=20)
    assert server.last.suffix == f"/sd/disks/{disk.uuid}/consolidation/runs"
    assert server.last.params == {"limit": "20"}
    assert len(runs) == 1
    assert runs.runs[0].tier_counts["exact"] == 4


def test_one_run_can_include_the_undo_plan(client, server, disk):
    server.reply(
        {"uuid": "e41a", "diff": {"seed": {}, "clusters": []}, "plan": {"reopen": 6, "applicable": True}}
    )
    run = client.tools.consolidation_run(disk, "e41a", plan=True)
    assert server.last.suffix == f"/sd/disks/{disk.uuid}/consolidation/runs/e41a"
    assert server.last.params == {"plan": "1"}
    assert run.plan["applicable"] is True


def test_the_plan_is_not_requested_by_default(client, server, disk):
    server.reply({"uuid": "e41a"})
    client.tools.consolidation_run(disk, "e41a")
    assert server.last.params == {}


def test_an_undeployed_audit_trail_says_so(client, server, disk):
    server.fail(503, "not_migrated")
    with pytest.raises(smartdisk.NotAvailableError) as caught:
        client.tools.consolidation_runs(disk)
    assert caught.value.code == "not_migrated"
