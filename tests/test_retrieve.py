"""Retrieval — the core call. Options in, context out."""

from __future__ import annotations

RESPONSE = {
    "block": "[1] Planning call > Schedule\nWe moved the launch to March.",
    "citations": [
        {
            "n": 1,
            "type": "message_chunk",
            "content_uuid": "4a7b",
            "content_name": "Planning call",
            "heading_path": "Schedule",
            "snippet": "We moved the launch to March.",
            "score": 0.91,
            "object_uuid": "b18f",
        }
    ],
    "tokens_used": 1840,
    "drilled": True,
    "expanded": False,
    "stable": {"block": "# Disk profile", "hash": "749cf4a0", "tokens": 512},
    "retrieve_ms": 320,
}


def test_retrieve_posts_the_query(client, server, disk):
    server.reply(RESPONSE)
    result = client.retrieve(disk, "when did we move the launch?")
    assert server.last.method == "POST"
    assert server.last.suffix == f"/sd/disks/{disk.uuid}/retrieve"
    assert server.last.json == {"query": "when did we move the launch?"}
    assert result.block.startswith("[1]")
    assert result.tokens_used == 1840
    assert result.drilled is True


def test_a_bare_query_sends_no_other_knobs(client, server, disk):
    # Omitted options must reach the server as absent, not as zeroes — `0` means
    # "the calibrated default" for min_score and context_tokens.
    client.retrieve(disk, "q")
    assert list(server.last.json) == ["query"]


def test_scoping_and_filters_are_sent_as_given(client, server, disk):
    client.retrieve(
        disk,
        "what are the current health conditions?",
        path="/research",
        categories=["health"],
        tags=["Health", "work"],
        since="2026-01-01T00:00:00Z",
        until="2026-06-01T00:00:00Z",
        context_tokens=4000,
    )
    body = server.last.json
    assert body["path"] == "/research"
    assert body["categories"] == ["health"]
    assert body["tags"] == ["Health", "work"]
    assert body["since"] == "2026-01-01T00:00:00Z"
    assert body["until"] == "2026-06-01T00:00:00Z"
    assert body["context_tokens"] == 4000


def test_a_negative_floor_survives_the_prune(client, server, disk):
    client.retrieve(disk, "q", min_score=-1)
    assert server.last.json["min_score"] == -1


def test_a_zero_floor_is_still_sent_explicitly(client, server, disk):
    client.retrieve(disk, "q", min_score=0)
    assert server.last.json["min_score"] == 0


def test_expansion_and_graph_walking_are_opt_in(client, server, disk):
    client.retrieve(disk, "q", expand=True, expand_max=6, graph_expand=True, graph_hops=2)
    body = server.last.json
    assert body["expand"] is True
    assert body["expand_max"] == 6
    assert body["graph_expand"] is True
    assert body["graph_hops"] == 2


def test_exclude_carries_object_uuids_forward(client, server, disk):
    client.retrieve(disk, "what else?", exclude=["b18f", "27a4"])
    assert server.last.json["exclude"] == ["b18f", "27a4"]


def test_the_server_side_ledger_needs_both_halves(client, server, disk):
    client.retrieve(disk, "what else?", session_id="chat-8412", dedup_turns=8)
    assert server.last.json["session_id"] == "chat-8412"
    assert server.last.json["dedup_turns"] == 8


def test_recency_can_be_forced_off(client, server, disk):
    # False is a real instruction here, not an omission.
    client.retrieve(disk, "q", recency=False)
    assert server.last.json["recency"] is False


def test_drill_can_be_turned_off_for_a_hot_path(client, server, disk):
    client.retrieve(disk, "q", drill=False, candidates=12)
    assert server.last.json["drill"] is False
    assert server.last.json["candidates"] == 12


def test_explain_is_passed_through(client, server, disk):
    client.retrieve(disk, "q", explain=True)
    assert server.last.json["explain"] is True


def test_citations_and_the_stable_block_are_parsed(client, server, disk):
    server.reply(RESPONSE)
    result = client.retrieve(disk, "q")
    assert result.citations[0].content_name == "Planning call"
    assert result.citations[0].score == 0.91
    assert result.stable.hash == "749cf4a0"
    assert result.object_uuids == ["b18f"]
    assert result.content_uuids == ["4a7b"]


def test_an_empty_result_is_falsy(client, server, disk):
    server.reply({"block": "", "citations": [], "tokens_used": 0})
    result = client.retrieve(disk, "something never stored")
    assert not result
    assert result.citations == []


def test_a_result_with_passages_is_truthy(client, server, disk):
    server.reply(RESPONSE)
    assert client.retrieve(disk, "q")


def test_the_ledger_block_is_parsed_when_present(client, server, disk):
    server.reply(
        {**RESPONSE, "ledger": {"session_id": "chat-8412", "dedup_turns": 8, "excluded": 37, "recorded": 24}}
    )
    result = client.retrieve(disk, "q", session_id="chat-8412", dedup_turns=8)
    assert result.ledger.excluded == 37
    assert result.ledger.recorded == 24


def test_the_ledger_is_none_when_it_did_not_engage(client, server, disk):
    server.reply(RESPONSE)
    assert client.retrieve(disk, "q").ledger is None


def test_an_explain_trace_is_parsed(client, server, disk):
    citation = dict(RESPONSE["citations"][0])
    citation["explain"] = {
        "lanes": ["dense", "summary"],
        "lane_ranks": {"dense": 0, "summary": 4},
        "rrf": 0.0327,
        "rerank": 0.83,
        "priors": {"recency": 1.06},
        "final_rank": 2,
    }
    server.reply({**RESPONSE, "citations": [citation]})
    trace = client.retrieve(disk, "q", explain=True).citations[0].explain
    assert trace.lanes == ["dense", "summary"]
    assert trace.lane_ranks["summary"] == 4
    assert trace.final_rank == 2
    assert trace.priors == {"recency": 1.06}


def test_retrieval_works_from_a_slug(client, server):
    server.reply({"disks": [{"uuid": "11111111-2222-3333-4444-555555555555", "slug": "research"}]})
    server.reply(RESPONSE)
    client.retrieve("research", "q")
    assert server.last.suffix == "/sd/disks/11111111-2222-3333-4444-555555555555/retrieve"
