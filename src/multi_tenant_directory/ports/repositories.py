from __future__ import annotations

from abc import ABC, abstractmethod
from decimal import Decimal

from src.multi_tenant_directory.domain.models import (
    BillingAccount,
    Session,
    TenantReport,
    User,
)


class UserRepository(ABC):
    @abstractmethod
    def add(self, user: User) -> None:
        raise NotImplementedError

    @abstractmethod
    def get(self, tenant_id: str, user_id: str) -> User | None:
        raise NotImplementedError

    @abstractmethod
    def list_by_tenant(self, tenant_id: str) -> list[User]:
        raise NotImplementedError


class BillingRepository(ABC):
    @abstractmethod
    def create_account(self, account: BillingAccount) -> None:
        raise NotImplementedError

    @abstractmethod
    def apply_charge(
        self, tenant_id: str, user_id: str, amount: Decimal
    ) -> BillingAccount:
        raise NotImplementedError

    @abstractmethod
    def get(self, tenant_id: str, user_id: str) -> BillingAccount | None:
        raise NotImplementedError


class SessionStore(ABC):
    @abstractmethod
    def put(self, session: Session) -> None:
        raise NotImplementedError

    @abstractmethod
    def get(self, session_id: str) -> Session | None:
        raise NotImplementedError


class AnalyticsRepository(ABC):
    @abstractmethod
    def build_tenant_report(self, tenant_id: str) -> TenantReport:
        raise NotImplementedError
