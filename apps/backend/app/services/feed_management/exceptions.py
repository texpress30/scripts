from __future__ import annotations


class FeedSourceNotFoundError(Exception):
    def __init__(self, source_id: str) -> None:
        super().__init__(f"Feed source not found: {source_id}")
        self.source_id = source_id


class FeedSourceAlreadyExistsError(Exception):
    def __init__(self, name: str, subaccount_id: int) -> None:
        super().__init__(f"Feed source '{name}' already exists for subaccount {subaccount_id}")
        self.name = name
        self.subaccount_id = subaccount_id


class FeedImportInProgressError(Exception):
    def __init__(self, source_id: str) -> None:
        super().__init__(f"An import is already in progress for feed source: {source_id}")
        self.source_id = source_id
