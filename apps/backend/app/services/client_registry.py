from __future__ import annotations

from dataclasses import dataclass, asdict
from threading import Lock


@dataclass
class ClientRecord:
    id: int
    name: str
    owner_email: str


class ClientRegistryService:
    def __init__(self) -> None:
        self._clients: list[ClientRecord] = []
        self._next_id = 1
        self._lock = Lock()

    def create_client(self, name: str, owner_email: str) -> dict[str, str | int]:
        with self._lock:
            record = ClientRecord(id=self._next_id, name=name, owner_email=owner_email)
            self._next_id += 1
            self._clients.append(record)
        return asdict(record)

    def list_clients(self) -> list[dict[str, str | int]]:
        with self._lock:
            return [asdict(c) for c in self._clients]


client_registry_service = ClientRegistryService()
