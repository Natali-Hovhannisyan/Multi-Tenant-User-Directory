from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class Tenant:
    tenant_id: str
    name: str


@dataclass(frozen=True)
class User:
    user_id: str
    tenant_id: str
    email: str
    full_name: str
    is_active: bool = True


@dataclass(frozen=True)
class BillingAccount:
    tenant_id: str
    user_id: str
    balance: Decimal
    currency: str


@dataclass(frozen=True)
class Session:
    session_id: str
    tenant_id: str
    user_id: str
    payload: str


@dataclass(frozen=True)
class TenantReport:
    tenant_id: str
    active_users: int
    inactive_users: int
    total_balance: Decimal
