"""The HTTP layer: auth, the envelope, retries, timeouts, configuration."""

from __future__ import annotations

import httpx
import pytest

import smartdisk
from smartdisk import SmartDisk
from smartdisk._http import DEFAULT_BASE_URL


def test_api_key_is_sent_as_a_bearer_token(client, server, disk):
    client.memory.contents(disk)
    assert server.last.headers["authorization"] == "Bearer sd_test_key"


def test_user_agent_names_the_sdk_and_version(client, server, disk):
    client.memory.contents(disk)
    assert server.last.headers["user-agent"] == f"smartdisk-python/{smartdisk.__version__}"


def test_envelope_is_peeled(client, server, disk):
    server.reply({"summary": "a planning thread", "facts": [], "tags": []})
    memory = client.memory.facts(disk)
    assert memory.summary == "a planning thread"


def test_unwrapped_body_still_parses(client, server, disk):
    # A body without the envelope is taken as-is rather than lost.
    server.reply({"summary": "direct"}, wrapped=False)
    assert client.memory.facts(disk).summary == "direct"


def test_export_is_returned_raw(client, server, disk):
    server.text("uuid,text\nabc,Alex works at Northwind.\n")
    body = client.tools.export(disk, format="csv")
    assert body.startswith("uuid,text")


def test_missing_api_key_is_refused_before_any_request():
    with pytest.raises(ValueError, match="API key"):
        SmartDisk(api_key="")


def test_api_key_falls_back_to_the_environment(monkeypatch):
    monkeypatch.setenv("SMARTDISK_API_KEY", "sd_from_env")
    sdk = SmartDisk()
    assert sdk._transport.api_key == "sd_from_env"
    sdk.close()


def test_base_url_defaults_to_the_hosted_api(monkeypatch):
    monkeypatch.delenv("SMARTDISK_BASE", raising=False)
    sdk = SmartDisk(api_key="sd_x")
    assert sdk.base_url == DEFAULT_BASE_URL
    sdk.close()


def test_base_url_can_be_overridden_for_a_self_hosted_server(server):
    http = httpx.Client(transport=httpx.MockTransport(server.handler))
    sdk = SmartDisk(api_key="sd_x", base_url="https://memory.example.com/api/", http_client=http)
    sdk.whoami()
    assert server.last.url == "https://memory.example.com/api/sd/whoami"
    sdk.close()


def test_base_url_can_come_from_the_environment(monkeypatch):
    monkeypatch.setenv("SMARTDISK_BASE", "https://memory.example.com/api")
    sdk = SmartDisk(api_key="sd_x")
    assert sdk.base_url == "https://memory.example.com/api"
    sdk.close()


def test_none_valued_parameters_are_dropped_from_the_query(client, server, disk):
    client.memory.subjects(disk)
    assert "limit" not in server.last.params


def test_retries_a_502_and_returns_the_retry(server, disk):
    server.fail(502, "extract_failed").reply({"contents": [], "consolidating": False})
    http = httpx.Client(transport=httpx.MockTransport(server.handler))
    sdk = SmartDisk(api_key="sd_x", http_client=http, max_retries=2)
    listing = sdk.memory.contents(disk)
    assert len(server) == 2
    assert listing.contents == []
    sdk.close()


def test_retries_a_429_and_honours_retry_after(server, disk):
    server.raw(httpx.Response(429, json={"error": "rate_limited"}, headers={"Retry-After": "1"}))
    server.reply({"contents": [], "consolidating": False})
    http = httpx.Client(transport=httpx.MockTransport(server.handler))
    sdk = SmartDisk(api_key="sd_x", http_client=http, max_retries=1)
    sdk.memory.contents(disk)
    assert len(server) == 2
    sdk.close()


def test_gives_up_after_max_retries(server, disk):
    for _ in range(4):
        server.fail(503, "not_migrated")
    http = httpx.Client(transport=httpx.MockTransport(server.handler))
    sdk = SmartDisk(api_key="sd_x", http_client=http, max_retries=2)
    with pytest.raises(smartdisk.NotAvailableError):
        sdk.memory.contents(disk)
    assert len(server) == 3  # the first attempt plus two retries
    sdk.close()


def test_a_500_is_never_retried(server, disk):
    # Its side effects are not visible from the outside, so retrying is a guess.
    server.fail(500, "ingest_failed").reply({"contents": []})
    http = httpx.Client(transport=httpx.MockTransport(server.handler))
    sdk = SmartDisk(api_key="sd_x", http_client=http, max_retries=3)
    with pytest.raises(smartdisk.ServerError):
        sdk.memory.contents(disk)
    assert len(server) == 1
    sdk.close()


def test_a_timeout_becomes_a_typed_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("too slow", request=request)

    http = httpx.Client(transport=httpx.MockTransport(handler))
    sdk = SmartDisk(api_key="sd_x", http_client=http, max_retries=0)
    with pytest.raises(smartdisk.APITimeoutError):
        sdk.whoami()
    sdk.close()


def test_an_unreachable_server_becomes_a_typed_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route", request=request)

    http = httpx.Client(transport=httpx.MockTransport(handler))
    sdk = SmartDisk(api_key="sd_x", http_client=http, max_retries=0)
    with pytest.raises(smartdisk.APIConnectionError):
        sdk.whoami()
    sdk.close()


def test_transport_errors_are_retried_too():
    attempts = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise httpx.ConnectError("no route", request=request)
        return httpx.Response(200, json={"data": {"env": "prod"}, "result": "success"})

    http = httpx.Client(transport=httpx.MockTransport(handler))
    sdk = SmartDisk(api_key="sd_x", http_client=http, max_retries=2)
    assert sdk.whoami().env == "prod"
    assert attempts["n"] == 3
    sdk.close()


def test_the_client_works_as_a_context_manager(server):
    http = httpx.Client(transport=httpx.MockTransport(server.handler))
    with SmartDisk(api_key="sd_x", http_client=http) as sdk:
        sdk.whoami()
    assert len(server) == 1


def test_whoami_reads_the_server_identity(client, server):
    server.reply({"env": "prod", "hostname": "node-1", "bearer": True})
    who = client.whoami()
    assert server.last.suffix == "/sd/whoami"
    assert (who.env, who.hostname, who.bearer) == ("prod", "node-1", True)
