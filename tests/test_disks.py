"""Disks: creation, listing, deletion, settings — and how a disk reference resolves."""

from __future__ import annotations

import pytest

import smartdisk

DISK_UUID = "11111111-2222-3333-4444-555555555555"


def test_create_posts_name_and_slug(client, server):
    server.reply({"uuid": DISK_UUID, "name": "Research notes", "slug": "research"})
    disk = client.disks.create(name="Research notes", slug="research")
    assert server.last.method == "POST"
    assert server.last.suffix == "/sd/disks"
    assert server.last.json == {"name": "Research notes", "slug": "research"}
    assert disk.uuid == DISK_UUID


def test_create_omits_what_was_not_given(client, server):
    client.disks.create(name="Research notes")
    assert server.last.json == {"name": "Research notes"}


def test_create_sends_a_description_when_given(client, server):
    client.disks.create(name="Notes", slug="notes", description="everything I read")
    assert server.last.json["description"] == "everything I read"


def test_list_reads_the_disks_key(client, server):
    server.reply({"disks": [{"uuid": DISK_UUID, "slug": "research", "document_count": 12}]})
    disks = client.disks.list()
    assert server.last.method == "GET"
    assert server.last.suffix == "/sd/disks"
    assert len(disks) == 1
    assert disks[0].document_count == 12


def test_list_tolerates_a_bare_array(client, server):
    server.reply([{"uuid": DISK_UUID, "slug": "research"}])
    assert client.disks.list()[0].slug == "research"


def test_find_returns_the_matching_disk(client, server):
    server.reply({"disks": [{"uuid": DISK_UUID, "slug": "research"}]})
    assert client.disks.find("research").uuid == DISK_UUID


def test_find_returns_none_when_absent(client, server):
    server.reply({"disks": [{"uuid": DISK_UUID, "slug": "other"}]})
    assert client.disks.find("research") is None


def test_delete_uses_the_uuid_route(client, server, disk):
    server.reply({"deleted": True})
    assert client.disks.delete(disk) is True
    assert server.last.method == "DELETE"
    assert server.last.suffix == f"/sd/disks/{disk.uuid}"


def test_settings_reads_about_and_paused(client, server, disk):
    server.reply({"about": "a support bot's memory", "paused": True})
    settings = client.disks.settings(disk)
    assert server.last.suffix == f"/sd/disks/{disk.uuid}/settings"
    assert settings.about == "a support bot's memory"
    assert settings.paused is True


def test_update_settings_sends_only_what_changed(client, server, disk):
    client.disks.update_settings(disk, paused=True)
    assert server.last.method == "PUT"
    assert server.last.json == {"paused": True}


def test_update_settings_can_set_the_about_note(client, server, disk):
    client.disks.update_settings(disk, about="notes about the Q2 launch")
    assert server.last.json == {"about": "notes about the Q2 launch"}


# --- disk references ---------------------------------------------------- #


def test_a_uuid_string_is_used_directly(client, server):
    client.memory.contents(DISK_UUID)
    assert len(server) == 1
    assert server.last.suffix == f"/sd/disks/{DISK_UUID}/contents"


def test_a_slug_is_resolved_through_the_disk_listing(client, server):
    server.reply({"disks": [{"uuid": DISK_UUID, "slug": "research"}]})
    server.reply({"contents": []})
    client.memory.contents("research")
    assert len(server) == 2
    assert server.first.suffix == "/sd/disks"
    assert server.last.suffix == f"/sd/disks/{DISK_UUID}/contents"


def test_a_resolved_slug_is_cached(client, server):
    server.reply({"disks": [{"uuid": DISK_UUID, "slug": "research"}]})
    client.memory.contents("research")
    client.memory.contents("research")
    assert len(server) == 3  # one lookup, then two direct calls


def test_an_unknown_slug_raises_not_found(client, server):
    server.reply({"disks": []})
    with pytest.raises(smartdisk.NotFoundError) as caught:
        client.memory.contents("nope")
    assert caught.value.code == "disk_not_found"


def test_an_empty_disk_reference_is_refused(client):
    with pytest.raises(ValueError, match="a disk is required"):
        client.memory.contents("")
