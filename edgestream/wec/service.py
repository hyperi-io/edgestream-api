"""
Project:   edgestream-api
File:      edgestream/wec/service.py
Language:  Python

License:   BUSL-1.1
Copyright: (c) 2026 HYPERI PTY LIMITED
"""

from __future__ import annotations
from typing import List
import anyio

from edgestream.wec import repo
from edgestream.wec.models import SubscriptionRow, SubscriptionPayload


class WecService:
    def __init__(self, db_url: str):
        self.db_url = db_url

    async def list(self) -> List[SubscriptionRow]:
        return await anyio.to_thread.run_sync(repo.list_subscriptions, self.db_url)

    async def create(self, payload: SubscriptionPayload) -> SubscriptionRow:
        return await anyio.to_thread.run_sync(repo.create_subscription, self.db_url, payload)

    async def update(self, sub_id: int, payload: SubscriptionPayload) -> SubscriptionRow:
        return await anyio.to_thread.run_sync(repo.update_subscription, self.db_url, sub_id, payload)

    async def delete(self, sub_id: int) -> None:
        return await anyio.to_thread.run_sync(repo.delete_subscription, self.db_url, sub_id)
