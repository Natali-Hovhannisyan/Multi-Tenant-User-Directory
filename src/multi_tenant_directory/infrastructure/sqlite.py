from __future__ import annotations

import logging
import shutil
import sqlite3
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import cast

from src.multi_tenant_directory.domain.models import BillingAccount, TenantReport, User
from src.multi_tenant_directory.exceptions import (
    BillingAccountAlreadyExistsError,
    BillingAccountNotFoundError,
    DataAccessError,
    ReplicationError,
    UserAlreadyExistsError,
)
from src.multi_tenant_directory.ports.repositories import (
    AnalyticsRepository,
    BillingRepository,
    UserRepository,
)

logger = logging.getLogger(__name__)


def _decimal_to_str(value: Decimal) -> str:
    return format(value, "f")


@dataclass(frozen=True)
class ShardDatabasePaths:
    primary: Path
    replica: Path


class SqliteConnectionFactory:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._bootstrap()

    @property
    def db_path(self) -> Path:
        return self._db_path

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON;")
        return connection

    def _bootstrap(self) -> None:
        try:
            with self.connect() as connection:
                connection.executescript(
                    """
                    PRAGMA foreign_keys = ON;

                    CREATE TABLE IF NOT EXISTS users (
                        tenant_id TEXT NOT NULL,
                        user_id TEXT NOT NULL,
                        email TEXT NOT NULL,
                        full_name TEXT NOT NULL,
                        is_active INTEGER NOT NULL,
                        PRIMARY KEY (tenant_id, user_id)
                    );

                    CREATE TABLE IF NOT EXISTS billing_accounts (
                        tenant_id TEXT NOT NULL,
                        user_id TEXT NOT NULL,
                        balance TEXT NOT NULL,
                        currency TEXT NOT NULL,
                        PRIMARY KEY (tenant_id, user_id),
                        FOREIGN KEY (tenant_id, user_id)
                            REFERENCES users (tenant_id, user_id)
                            ON DELETE CASCADE
                    );
                    """
                )
        except sqlite3.DatabaseError as exc:
            logger.error("Failed to bootstrap database %s", self._db_path)
            raise DataAccessError(
                f"failed to bootstrap database at {self._db_path}"
            ) from exc


class SqliteUserRepository(UserRepository):
    def __init__(self, connection_factory: SqliteConnectionFactory) -> None:
        self._connection_factory = connection_factory

    def add(self, user: User) -> None:
        try:
            with self._connection_factory.connect() as connection:
                connection.execute(
                    """
                    INSERT INTO users (tenant_id, user_id, email, full_name, is_active)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        user.tenant_id,
                        user.user_id,
                        user.email,
                        user.full_name,
                        int(user.is_active),
                    ),
                )
        except sqlite3.IntegrityError as exc:
            logger.error(
                "Duplicate user insert attempted for tenant %s user %s",
                user.tenant_id,
                user.user_id,
            )
            raise UserAlreadyExistsError(
                f"user {user.user_id} already exists for tenant {user.tenant_id}"
            ) from exc
        except sqlite3.DatabaseError as exc:
            logger.error(
                "Failed to insert user %s for tenant %s", user.user_id, user.tenant_id
            )
            raise DataAccessError("failed to insert user") from exc

    def get(self, tenant_id: str, user_id: str) -> User | None:
        try:
            with self._connection_factory.connect() as connection:
                row = cast(
                    sqlite3.Row | None,
                    connection.execute(
                        "SELECT tenant_id, user_id, email, full_name, is_active FROM users WHERE tenant_id = ? AND user_id = ?",
                        (tenant_id, user_id),
                    ).fetchone(),
                )
        except sqlite3.DatabaseError as exc:
            logger.error("Failed to fetch user %s for tenant %s", user_id, tenant_id)
            raise DataAccessError("failed to fetch user") from exc
        return _row_to_user(row) if row else None

    def list_by_tenant(self, tenant_id: str) -> list[User]:
        try:
            with self._connection_factory.connect() as connection:
                rows = cast(
                    list[sqlite3.Row],
                    connection.execute(
                        "SELECT tenant_id, user_id, email, full_name, is_active FROM users WHERE tenant_id = ? ORDER BY user_id",
                        (tenant_id,),
                    ).fetchall(),
                )
        except sqlite3.DatabaseError as exc:
            logger.error("Failed to list users for tenant %s", tenant_id)
            raise DataAccessError("failed to list users") from exc
        return [_row_to_user(row) for row in rows]


class SqliteBillingRepository(BillingRepository):
    def __init__(self, connection_factory: SqliteConnectionFactory) -> None:
        self._connection_factory = connection_factory

    def create_account(self, account: BillingAccount) -> None:
        try:
            with self._connection_factory.connect() as connection:
                connection.execute(
                    """
                    INSERT INTO billing_accounts (tenant_id, user_id, balance, currency)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        account.tenant_id,
                        account.user_id,
                        _decimal_to_str(account.balance),
                        account.currency,
                    ),
                )
        except sqlite3.IntegrityError as exc:
            logger.error(
                "Duplicate billing account insert attempted for tenant %s user %s",
                account.tenant_id,
                account.user_id,
            )
            raise BillingAccountAlreadyExistsError(
                f"billing account already exists for user {account.user_id}"
            ) from exc
        except sqlite3.DatabaseError as exc:
            logger.error(
                "Failed to create billing account for tenant %s user %s",
                account.tenant_id,
                account.user_id,
            )
            raise DataAccessError("failed to create billing account") from exc

    def apply_charge(
        self, tenant_id: str, user_id: str, amount: Decimal
    ) -> BillingAccount:
        try:
            with self._connection_factory.connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                row = cast(
                    sqlite3.Row | None,
                    connection.execute(
                        """
                        SELECT tenant_id, user_id, balance, currency
                        FROM billing_accounts
                        WHERE tenant_id = ? AND user_id = ?
                        """,
                        (tenant_id, user_id),
                    ).fetchone(),
                )
                if row is None:
                    logger.error(
                        "Billing account not found for tenant %s user %s",
                        tenant_id,
                        user_id,
                    )
                    raise BillingAccountNotFoundError(
                        f"billing account not found for user {user_id}"
                    )

                new_balance = Decimal(cast(str, row["balance"])) + amount
                connection.execute(
                    """
                    UPDATE billing_accounts
                    SET balance = ?
                    WHERE tenant_id = ? AND user_id = ?
                    """,
                    (_decimal_to_str(new_balance), tenant_id, user_id),
                )
                return BillingAccount(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    balance=new_balance,
                    currency=cast(str, row["currency"]),
                )
        except BillingAccountNotFoundError:
            raise
        except sqlite3.DatabaseError as exc:
            logger.error(
                "Failed to apply charge for tenant %s user %s",
                tenant_id,
                user_id,
            )
            raise DataAccessError("failed to apply billing charge") from exc

    def get(self, tenant_id: str, user_id: str) -> BillingAccount | None:
        try:
            with self._connection_factory.connect() as connection:
                row = cast(
                    sqlite3.Row | None,
                    connection.execute(
                        """
                        SELECT tenant_id, user_id, balance, currency
                        FROM billing_accounts
                        WHERE tenant_id = ? AND user_id = ?
                        """,
                        (tenant_id, user_id),
                    ).fetchone(),
                )
        except sqlite3.DatabaseError as exc:
            logger.error(
                "Failed to fetch billing account for tenant %s user %s",
                tenant_id,
                user_id,
            )
            raise DataAccessError("failed to fetch billing account") from exc
        return _row_to_billing(row) if row else None


class SqliteAnalyticsRepository(AnalyticsRepository):
    def __init__(self, connection_factory: SqliteConnectionFactory) -> None:
        self._connection_factory = connection_factory

    def build_tenant_report(self, tenant_id: str) -> TenantReport:
        try:
            with self._connection_factory.connect() as connection:
                user_row = cast(
                    sqlite3.Row,
                    connection.execute(
                        """
                        SELECT
                            SUM(CASE WHEN is_active = 1 THEN 1 ELSE 0 END) AS active_users,
                            SUM(CASE WHEN is_active = 0 THEN 1 ELSE 0 END) AS inactive_users
                        FROM users
                        WHERE tenant_id = ?
                        """,
                        (tenant_id,),
                    ).fetchone(),
                )
                billing_rows = cast(
                    list[sqlite3.Row],
                    connection.execute(
                        "SELECT balance FROM billing_accounts WHERE tenant_id = ?",
                        (tenant_id,),
                    ).fetchall(),
                )
        except sqlite3.DatabaseError as exc:
            logger.error("Failed to build report for tenant %s", tenant_id)
            raise DataAccessError("failed to build tenant report") from exc
        total_balance = sum(
            (Decimal(cast(str, row["balance"])) for row in billing_rows),
            Decimal("0"),
        )
        return TenantReport(
            tenant_id=tenant_id,
            active_users=cast(int | None, user_row["active_users"]) or 0,
            inactive_users=cast(int | None, user_row["inactive_users"]) or 0,
            total_balance=total_balance,
        )


class ReplicaSynchronizer:
    def synchronize(self, paths: ShardDatabasePaths) -> None:
        try:
            paths.replica.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(paths.primary, paths.replica)
        except FileNotFoundError as exc:
            logger.error(
                "Primary database missing during replication: %s", paths.primary
            )
            raise ReplicationError(
                f"primary database not found: {paths.primary}"
            ) from exc
        except OSError as exc:
            logger.error(
                "Filesystem error during replication from %s to %s",
                paths.primary,
                paths.replica,
            )
            raise ReplicationError("failed to synchronize replica") from exc


def _row_to_user(row: sqlite3.Row) -> User:
    return User(
        tenant_id=cast(str, row["tenant_id"]),
        user_id=cast(str, row["user_id"]),
        email=cast(str, row["email"]),
        full_name=cast(str, row["full_name"]),
        is_active=bool(cast(int, row["is_active"])),
    )


def _row_to_billing(row: sqlite3.Row) -> BillingAccount:
    return BillingAccount(
        tenant_id=cast(str, row["tenant_id"]),
        user_id=cast(str, row["user_id"]),
        balance=Decimal(cast(str, row["balance"])),
        currency=cast(str, row["currency"]),
    )
