from __future__ import annotations

from decimal import Decimal

from src.multi_tenant_directory.config import AppConfig
from src.multi_tenant_directory.domain.models import Session, User
from src.multi_tenant_directory.services.bootstrap import ApplicationContainer


def main() -> None:
    container = ApplicationContainer(AppConfig())

    tenant_id = "tenant-acme"
    user = User(
        tenant_id=tenant_id,
        user_id="user-001",
        email="owner@acme.example",
        full_name="Acme Owner",
        is_active=True,
    )
    container.user_directory.register_user(
        user=user, starting_balance=Decimal("100.00"), currency="USD"
    )
    container.user_directory.charge_user(
        tenant_id=tenant_id, user_id=user.user_id, amount=Decimal("19.99")
    )
    container.user_directory.create_session(
        Session(
            session_id="session-001",
            tenant_id=tenant_id,
            user_id=user.user_id,
            payload='{"role":"owner"}',
        )
    )
    container.replication.replicate_all()
    report = container.reporting.generate_daily_report(tenant_id)
    print(
        "tenant={tenant} active_users={active} inactive_users={inactive} total_balance={balance}".format(
            tenant=report.tenant_id,
            active=report.active_users,
            inactive=report.inactive_users,
            balance=report.total_balance,
        )
    )


if __name__ == "__main__":
    main()
