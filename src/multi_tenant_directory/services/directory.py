from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
import logging

from src.multi_tenant_directory.domain.models import BillingAccount, Session, User
from src.multi_tenant_directory.exceptions import ShardNotFoundError
from src.multi_tenant_directory.ports.repositories import (
    BillingRepository,
    SessionStore,
    UserRepository,
)
from src.multi_tenant_directory.services.sharding import ShardStrategy

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TenantShardContext:
    shard_id: int
    users: UserRepository
    billing: BillingRepository


class TenantShardResolver:
    def __init__(
        self, strategy: ShardStrategy, shards: dict[int, TenantShardContext]
    ) -> None:
        self._strategy = strategy
        self._shards = shards

    def resolve(self, tenant_id: str) -> TenantShardContext:
        shard_id = self._strategy.shard_for(tenant_id)
        logger.debug("Resolved tenant to primary shard %s", shard_id)
        try:
            return self._shards[shard_id]
        except KeyError as exc:
            logger.error("Missing primary shard configuration for tenant %s", tenant_id)
            raise ShardNotFoundError(f"missing shard for tenant {tenant_id}") from exc


class UserDirectoryService:
    def __init__(
        self, shard_resolver: TenantShardResolver, session_store: SessionStore
    ) -> None:
        self._shard_resolver = shard_resolver
        self._session_store = session_store

    def register_user(
        self, user: User, starting_balance: Decimal, currency: str
    ) -> None:
        logger.info("Registering user %s for tenant %s", user.user_id, user.tenant_id)
        shard = self._shard_resolver.resolve(user.tenant_id)
        shard.users.add(user)
        shard.billing.create_account(
            BillingAccount(
                tenant_id=user.tenant_id,
                user_id=user.user_id,
                balance=starting_balance,
                currency=currency,
            )
        )
        logger.debug("Registered user %s for tenant %s", user.user_id, user.tenant_id)

    def charge_user(
        self, tenant_id: str, user_id: str, amount: Decimal
    ) -> BillingAccount:
        logger.info("Charging user %s for tenant %s", user_id, tenant_id)
        shard = self._shard_resolver.resolve(tenant_id)
        account = shard.billing.apply_charge(
            tenant_id=tenant_id, user_id=user_id, amount=amount
        )
        logger.debug(
            "Charge applied to user %s for tenant %s; new balance=%s",
            user_id,
            tenant_id,
            account.balance,
        )
        return account

    def create_session(self, session: Session) -> None:
        logger.debug("Creating session %s", session.session_id)
        self._session_store.put(session)

    def get_session(self, session_id: str) -> Session | None:
        logger.debug("Fetching session %s", session_id)
        return self._session_store.get(session_id)

    def get_user(self, tenant_id: str, user_id: str) -> User | None:
        logger.debug("Fetching user %s for tenant %s", user_id, tenant_id)
        shard = self._shard_resolver.resolve(tenant_id)
        return shard.users.get(tenant_id, user_id)
