"""Disks — a disk is a container for one body of memory."""

from __future__ import annotations

from .._util import DiskRef, prune
from ..models import Disk, DiskSettings
from ._base import Resource

__all__ = ["Disks"]


class Disks(Resource):
    """``client.disks`` — create, list, delete, and configure disks."""

    def create(self, name: str, *, slug: str | None = None, description: str | None = None) -> Disk:
        """Create a disk, or return the existing one with that slug.

        Idempotent on ``slug``: a disk whose slug already exists for you comes
        back unchanged, so this is safe to call at every start-up. The slug is
        derived from ``name`` when omitted, and normalised either way — ``My_Disk``,
        ``my disk`` and ``my-disk`` all name the same disk.

        ``POST /sd/disks``
        """
        body = prune({"name": name, "slug": slug, "description": description})
        return Disk.from_dict(self._map(self._t.post(self._t.url("disks"), json=body)))

    def list(self) -> list[Disk]:
        """Every disk this key can reach.

        ``GET /sd/disks``
        """
        payload = self._t.get(self._t.url("disks"))
        return [Disk.from_dict(row) for row in self._rows(payload, "disks")]

    def find(self, slug: str) -> Disk | None:
        """The disk with this slug, or ``None``. A client-side filter over ``list()``."""
        for disk in self.list():
            if disk.slug == slug:
                return disk
        return None

    def delete(self, disk: DiskRef) -> bool:
        """Remove a disk and everything under it. Irreversible.

        ``DELETE /sd/disks/:uuid``
        """
        payload = self._map(self._t.delete(self._disk_url(disk)))
        return bool(payload.get("deleted", True))

    def settings(self, disk: DiskRef) -> DiskSettings:
        """The disk's ``about`` note and whether processing is paused.

        ``GET /sd/disks/:uuid/settings``
        """
        return DiskSettings.from_dict(self._map(self._t.get(self._disk_url(disk, "settings"))))

    def update_settings(
        self, disk: DiskRef, *, about: str | None = None, paused: bool | None = None
    ) -> DiskSettings:
        """Set the ``about`` note, pause or resume background processing, or both.

        The ``about`` note rides along with every AI stage as the disk's context,
        so it is the cheapest way to disambiguate who and what a disk is about.
        Omitted fields are left alone.

        ``PUT /sd/disks/:uuid/settings``
        """
        body = prune({"about": about, "paused": paused})
        return DiskSettings.from_dict(self._map(self._t.put(self._disk_url(disk, "settings"), json=body)))
