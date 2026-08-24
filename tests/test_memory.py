"""Memory: the grounded answer, the derived views, organising, and the write verbs."""

from __future__ import annotations

import pytest

# --- ask ---------------------------------------------------------------- #


def test_ask_posts_to_the_chat_route(client, server, disk):
    server.reply({"answer": "We moved it to March.", "citations": [], "tokens_used": 900,
                  "retrieve_ms": 320, "answer_ms": 1400})
    answer = client.memory.ask(disk, "when did we move the launch?")
    assert server.last.suffix == f"/sd/disks/{disk.uuid}/chat"
    assert server.last.json == {"query": "when did we move the launch?"}
    assert answer.answer == "We moved it to March."
    assert str(answer) == "We moved it to March."
    assert answer.answer_ms == 1400


def test_ask_passes_the_model_tier_and_language(client, server, disk):
    client.memory.ask(disk, "q", model="fast", language="fr")
    assert server.last.json["model"] == "fast"
    assert server.last.json["language"] == "fr"


def test_ask_carries_prior_turns(client, server, disk):
    history = [{"role": "user", "content": "and before that?"},
               {"role": "assistant", "content": "it was February."}]
    client.memory.ask(disk, "why?", history=history)
    assert server.last.json["history"] == history


def test_ask_takes_the_same_filters_as_retrieval(client, server, disk):
    client.memory.ask(disk, "q", path="/research", categories=["health"], tags=["work"],
                      since="2026-01-01T00:00:00Z", expand=True)
    body = server.last.json
    assert body["path"] == "/research"
    assert body["categories"] == ["health"]
    assert body["tags"] == ["work"]
    assert body["since"] == "2026-01-01T00:00:00Z"
    assert body["expand"] is True


# --- reading ------------------------------------------------------------ #


def test_contents_lists_sources_with_their_status(client, server, disk):
    server.reply({"contents": [{"uuid": "4a7b", "name": "Planning call", "content_type": "chat",
                                "status": "processed", "message_count": 24, "stale": True,
                                "content_hash": "-2425632407680798700"}],
                  "consolidating": False})
    listing = client.memory.contents(disk)
    assert server.last.suffix == f"/sd/disks/{disk.uuid}/contents"
    assert len(listing) == 1
    row = listing.contents[0]
    assert row.is_chat and row.is_processed and row.stale
    assert row.content_hash == "-2425632407680798700"  # a string, never coerced


def test_facts_reads_the_derived_memory_view(client, server, disk):
    server.reply({"facts": [{"text": "The launch is in March.", "category": "schedule",
                             "reinforced_count": 2, "origin": "chat", "tags": ["launch"]}],
                  "summary": "A planning thread.",
                  "tags": [{"slug": "launch", "text": "launch", "uses": 5}]})
    memory = client.memory.facts(disk)
    assert server.last.suffix == f"/sd/disks/{disk.uuid}/memory"
    assert memory.facts[0].origin == "chat"
    assert memory.summary == "A planning thread."
    assert memory.tags[0].uses == 5


def test_groups_reads_current_values_and_their_history(client, server, disk):
    server.reply({
        "groups": [{
            "subject": "alex", "predicate": "works_at", "kind": "functional",
            "current": [{"uuid": "c1", "text": "Alex works at Northwind Trading."}],
            "history": [{"uuid": "h1", "text": "Alex works at Harbor Labs.",
                         "invalidated": True, "close_kind": "superseded", "superseded_by": "c1"}],
            "history_count": 1,
        }],
        "total_groups": 612, "ungrouped": 44,
    })
    groups = client.memory.groups(disk)
    assert server.last.suffix == f"/sd/disks/{disk.uuid}/groups"
    assert groups.total_groups == 612
    assert groups.ungrouped == 44
    assert groups.truncated is True
    group = groups.groups[0]
    assert group.current[0].close_kind == ""       # absent on a current fact
    assert group.history[0].close_kind == "superseded"
    assert group.history[0].superseded_by == "c1"


def test_subjects_returns_nodes_edges_and_its_own_truncation(client, server, disk):
    server.reply({"subjects": [{"name": "alex", "category": "career", "facts": 118}],
                  "edges": [{"subject": "alex", "predicate": "works_at",
                             "object": "northwind", "weight": 3}],
                  "subjects_total": 1284, "subjects_returned": 300,
                  "edges_total": 3910, "edges_returned": 1500, "edges_cap": 1500,
                  "truncated": True})
    graph = client.memory.subjects(disk, limit=0)
    assert server.last.params["limit"] == "0"
    assert graph.subjects[0].facts == 118
    assert graph.edges[0].weight == 3
    assert graph.truncated and graph.subjects_total == 1284


def test_tags_can_be_scoped_to_a_folder(client, server, disk):
    server.reply({"tags": [{"slug": "launch", "text": "launch", "uses": 5}], "path": "/research"})
    tags = client.memory.tags(disk, path="/research")
    assert server.last.params["path"] == "/research"
    assert tags[0].slug == "launch"


def test_profile_and_index_are_both_parsed(client, server, disk):
    server.reply({"profile": {"body": "## Identity", "headline": "one line",
                              "facts_at_gen": 4213, "gen_count": 3, "hash": "749cf4a0"},
                  "index": {"body": "Disk: 214 documents", "hash": "b03c11d2"}})
    view = client.memory.profile(disk)
    assert view.profile.gen_count == 3
    assert view.index.hash == "b03c11d2"


def test_a_young_disk_has_neither_profile_nor_index(client, server, disk):
    server.reply({"profile": None, "index": None})
    view = client.memory.profile(disk)
    assert view.profile is None and view.index is None


def test_regenerate_profile_posts(client, server, disk):
    server.reply({"profile": {"body": "## Identity", "hash": "new"}})
    view = client.memory.regenerate_profile(disk)
    assert server.last.method == "POST"
    assert server.last.suffix == f"/sd/disks/{disk.uuid}/profile/regen"
    assert view.profile.hash == "new"


def test_ecosystem_reports_its_cap(client, server, disk):
    server.reply({"sources": [{"uuid": "s1", "name": "Planning call"}],
                  "tags": [{"slug": "launch"}], "facts": [{"uuid": "f1", "text": "March."}],
                  "links": {"source_fact": [["s1", "f1"]]},
                  "facts_total": 4213, "facts_returned": 100, "facts_cap": 100, "truncated": True})
    eco = client.memory.ecosystem(disk, limit=0)
    assert server.last.params["limit"] == "0"
    assert eco.truncated and eco.facts_total == 4213
    assert eco.links["source_fact"] == [["s1", "f1"]]


def test_graph_query_sends_q_and_depth(client, server, disk):
    server.reply({"mode": "path", "query": "alex..northwind",
                  "edges": [{"subject": "alex", "predicate": "works_at", "object": "northwind",
                             "object_text": "Northwind Trading", "fact_uuid": "f1"}]})
    result = client.memory.graph(disk, "alex..northwind", depth=4)
    assert server.last.suffix == f"/sd/disks/{disk.uuid}/graph-query"
    assert server.last.params == {"q": "alex..northwind", "depth": "4"}
    assert result.mode == "path"
    assert result.edges[0].object_text == "Northwind Trading"
    assert result


def test_an_unknown_entity_gives_an_empty_falsy_result(client, server, disk):
    server.reply({"mode": "neighbors", "query": "nobody", "edges": []})
    assert not client.memory.graph(disk, "nobody")


# --- organising --------------------------------------------------------- #


def test_delete_content_reports_the_chunks_that_went_with_it(client, server, disk):
    server.reply({"deleted": True, "chunks_removed": 18})
    assert client.memory.delete_content(disk, "4a7b") == 18
    assert server.last.method == "DELETE"
    assert server.last.suffix == f"/sd/disks/{disk.uuid}/contents/4a7b"


def test_move_content_posts_the_destination(client, server, disk):
    server.reply({"moved": True})
    assert client.memory.move_content(disk, "4a7b", "/research") is True
    assert server.last.json == {"folder_path": "/research"}


def test_folders_are_listed_with_counts(client, server, disk):
    server.reply({"folders": [{"path": "/research", "name": "research", "content_count": 3}]})
    folders = client.memory.folders(disk)
    assert folders[0].path == "/research"
    assert folders[0].content_count == 3


def test_create_folder_posts_a_path(client, server, disk):
    client.memory.create_folder(disk, "research/papers")
    assert server.last.method == "POST"
    assert server.last.json == {"path": "research/papers"}


def test_delete_folder_puts_the_path_in_the_query(client, server, disk):
    client.memory.delete_folder(disk, "/research/papers")
    assert server.last.method == "DELETE"
    assert server.last.suffix == f"/sd/disks/{disk.uuid}/folders"
    assert server.last.params == {"path": "/research/papers"}


# --- aliases ------------------------------------------------------------ #


def test_disk_aliases_round_trip(client, server, disk):
    server.reply({"aliases": {"user": "alex", "al": "alex"}})
    assert client.memory.aliases(disk) == {"user": "alex", "al": "alex"}
    assert server.last.suffix == f"/sd/disks/{disk.uuid}/aliases"


def test_setting_disk_aliases_uses_put(client, server, disk):
    server.reply({"status": "ok", "aliases": {"user": "alex"}})
    result = client.memory.set_aliases(disk, {"user": "alex"})
    assert server.last.method == "PUT"
    assert server.last.json == {"aliases": {"user": "alex"}}
    assert result == {"user": "alex"}


def test_content_aliases_target_one_conversation(client, server, disk):
    server.reply({"aliases": {"user": "Alex", "assistant": "Aria"}})
    client.memory.content_aliases(disk, "4a7b")
    assert server.last.suffix == f"/sd/disks/{disk.uuid}/contents/4a7b/aliases"


def test_setting_content_aliases_uses_put(client, server, disk):
    server.reply({"status": "ok", "aliases": {"user": "Alex"}})
    client.memory.set_content_aliases(disk, "4a7b", {"user": "Alex"})
    assert server.last.method == "PUT"
    assert server.last.json == {"aliases": {"user": "Alex"}}


def test_an_empty_alias_map_clears_it(client, server, disk):
    server.reply({"status": "ok", "aliases": {}})
    assert client.memory.set_aliases(disk, {}) == {}
    assert server.last.json == {"aliases": {}}


# --- writing ------------------------------------------------------------ #


def test_remember_returns_the_new_fact_uuid(client, server, disk):
    server.reply({"fact_uuid": "f-123"})
    uuid = client.memory.remember(disk, "Alex works at Northwind Trading.",
                                  subject="alex", predicate="works_at", object="northwind",
                                  category="career", priority=80)
    assert server.last.suffix == f"/sd/disks/{disk.uuid}/remember"
    assert server.last.json == {"text": "Alex works at Northwind Trading.", "subject": "alex",
                                "predicate": "works_at", "object": "northwind",
                                "category": "career", "priority": 80}
    assert uuid == "f-123"


def test_remember_can_be_just_a_sentence(client, server, disk):
    client.memory.remember(disk, "The launch is in March.")
    assert server.last.json == {"text": "The launch is in March."}


def test_forget_reports_how_many_were_closed(client, server, disk):
    server.reply({"closed": 1})
    assert client.memory.forget(disk, "f-123") == 1
    assert server.last.json == {"fact_uuid": "f-123"}


def test_forgetting_an_already_retired_fact_closes_nothing(client, server, disk):
    server.reply({"closed": 0})
    assert client.memory.forget(disk, "f-123") == 0


def test_feedback_rates_facts_by_uuid(client, server, disk):
    server.reply({"updated": 2})
    assert client.memory.feedback(disk, ["b18f", "27a4"], 1.0) == 2
    assert server.last.json == {"fact_uuids": ["b18f", "27a4"], "score": 1.0}


def test_feedback_needs_at_least_one_fact(client, server, disk):
    with pytest.raises(ValueError, match="at least one fact uuid"):
        client.memory.feedback(disk, ["  "], 1.0)
    assert len(server) == 0


def test_reprioritize_sends_the_new_standing(client, server, disk):
    server.reply({"updated": 1})
    assert client.memory.reprioritize(disk, "f-123", 90) == 1
    assert server.last.json == {"fact_uuid": "f-123", "priority": 90}


@pytest.mark.parametrize("priority", [0, 101, -5])
def test_reprioritize_refuses_a_priority_outside_the_range(client, server, disk, priority):
    with pytest.raises(ValueError, match="between 1 and 100"):
        client.memory.reprioritize(disk, "f-123", priority)
    assert len(server) == 0
