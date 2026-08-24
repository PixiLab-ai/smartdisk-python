"""Every documented error code maps to the exception you would catch for it."""

from __future__ import annotations

import pytest

import smartdisk
from smartdisk.errors import error_from_response


@pytest.mark.parametrize(
    ("status", "code", "expected"),
    [
        (400, "invalid_json", smartdisk.BadRequestError),
        (400, "empty_text", smartdisk.BadRequestError),
        (400, "invalid_since", smartdisk.BadRequestError),
        (400, "bad_pattern", smartdisk.BadRequestError),
        (400, "bad_format", smartdisk.BadRequestError),
        (400, "unsupported_format", smartdisk.BadRequestError),
        (400, "invalid_body_b64", smartdisk.BadRequestError),
        (400, "conversion_failed", smartdisk.BadRequestError),
        (401, "invalid_api_key", smartdisk.AuthenticationError),
        (401, "unauthorized", smartdisk.AuthenticationError),
        (403, "forbidden", smartdisk.ForbiddenError),
        (403, "smartdisk_access_required", smartdisk.AccessRequiredError),
        (403, "session_required", smartdisk.SessionRequiredError),
        (404, "disk_not_found", smartdisk.NotFoundError),
        (404, "content_not_found", smartdisk.NotFoundError),
        (404, "run_not_found", smartdisk.NotFoundError),
        (413, "too_large", smartdisk.TooLargeError),
        (422, "blocked", smartdisk.UnprocessableError),
        (422, "no_content", smartdisk.UnprocessableError),
        (422, "no_transcript", smartdisk.UnprocessableError),
        (422, "unavailable", smartdisk.UnprocessableError),
        (429, "rate_limited", smartdisk.RateLimitError),
        (500, "ingest_failed", smartdisk.ServerError),
        (500, "chat_failed", smartdisk.ServerError),
        (502, "ocr_failed", smartdisk.UpstreamError),
        (502, "extract_failed", smartdisk.UpstreamError),
        (502, "remember_failed", smartdisk.UpstreamError),
        (503, "not_migrated", smartdisk.NotAvailableError),
    ],
)
def test_code_maps_to_exception(client, server, disk, status, code, expected):
    server.fail(status, code)
    with pytest.raises(expected) as caught:
        client.memory.contents(disk)
    assert caught.value.code == code
    assert caught.value.status == status


def test_every_error_is_a_smartdisk_error(client, server, disk):
    server.fail(404, "disk_not_found")
    with pytest.raises(smartdisk.SmartDiskError):
        client.memory.contents(disk)


def test_access_required_is_catchable_as_forbidden(client, server, disk):
    # It is a 403 first and a specific condition second.
    server.fail(403, "smartdisk_access_required")
    with pytest.raises(smartdisk.ForbiddenError):
        client.memory.contents(disk)


def test_detail_is_kept_and_shown(client, server, disk):
    server.fail(400, "invalid_json", detail="unexpected end of input")
    with pytest.raises(smartdisk.BadRequestError) as caught:
        client.memory.contents(disk)
    assert caught.value.detail == "unexpected end of input"
    assert "unexpected end of input" in str(caught.value)


def test_too_large_carries_the_limits_that_would_fix_it(client, server, disk):
    server.fail(413, "too_large", facts_total=48213, max_facts=20000)
    with pytest.raises(smartdisk.TooLargeError) as caught:
        client.tools.export(disk)
    assert caught.value.facts_total == 48213
    assert caught.value.max_facts == 20000
    assert caught.value.edges_total is None


def test_too_large_on_hubs_carries_edge_limits(client, server, disk):
    server.fail(413, "too_large", edges_total=90210, max_edges=50000)
    with pytest.raises(smartdisk.TooLargeError) as caught:
        client.tools.hubs(disk)
    assert caught.value.edges_total == 90210
    assert caught.value.max_edges == 50000


def test_an_error_inside_the_envelope_is_still_found():
    error = error_from_response(403, {"data": {"error": "forbidden"}, "result": "error"})
    assert isinstance(error, smartdisk.ForbiddenError)
    assert error.code == "forbidden"


def test_the_proxy_error_envelope_is_still_typed_by_its_code():
    # A proxy realm answers {"data": null, "result": "error", "message": "<code>"}:
    # the machine code sits at the envelope's top level, and `data` is a literal
    # null rather than an object to reach into.
    error = error_from_response(
        404,
        {"data": None, "result": "error", "message": "disk_not_found", "token": "err_proxy_service"},
    )
    assert isinstance(error, smartdisk.NotFoundError)
    assert error.code == "disk_not_found"


def test_a_human_sentence_in_message_is_not_mistaken_for_a_code():
    error = error_from_response(500, {"message": "Something went badly wrong."})
    assert error.code == ""


def test_a_status_without_a_code_still_raises_something_typed(client, server, disk):
    server.fail(404)
    with pytest.raises(smartdisk.NotFoundError) as caught:
        client.memory.contents(disk)
    assert caught.value.code == ""


def test_a_non_json_error_body_is_reported_verbatim():
    error = error_from_response(500, None, text="upstream reset the connection")
    assert isinstance(error, smartdisk.ServerError)
    assert "upstream reset" in str(error)


def test_the_message_names_the_call_that_failed(client, server, disk):
    server.fail(404, "disk_not_found")
    with pytest.raises(smartdisk.NotFoundError) as caught:
        client.memory.contents(disk)
    assert "GET" in str(caught.value)
    assert "/contents" in str(caught.value)


def test_an_unknown_status_falls_back_without_crashing():
    error = error_from_response(418, {"error": "teapot"})
    assert isinstance(error, smartdisk.APIStatusError)
    assert error.status == 418
