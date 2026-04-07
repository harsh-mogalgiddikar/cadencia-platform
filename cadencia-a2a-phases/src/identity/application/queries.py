from __future__ import annotations

import uuid
from dataclasses import dataclass


@dataclass(frozen=True)
class GetEnterpriseQuery:
    enterprise_id: uuid.UUID
    requesting_user_id: uuid.UUID


@dataclass(frozen=True)
class GetUserQuery:
    user_id: uuid.UUID


@dataclass(frozen=True)
class ListAPIKeysQuery:
    enterprise_id: uuid.UUID
    requesting_user_id: uuid.UUID
