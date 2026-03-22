from __future__ import annotations

from decimal import Decimal
import logging

from src.multi_tenant_directory.config import AppConfig
from src.multi_tenant_directory.domain.models import Session, User
from src.multi_tenant_directory.exceptions import DirectoryError
from src.multi_tenant_directory.logging_config import setup_logging
from src.multi_tenant_directory.services.bootstrap import ApplicationContainer


def main() -> None:
    setup_logging()
    logger = logging.getLogger(__name__)
    container = ApplicationContainer(AppConfig())

    tenant_id = "tenant-acme"
    user = User(
        tenant_id=tenant_id,
        user_id="user-001",
        email="owner@acme.example",
        full_name="Acme Owner",
        is_active=True,
    )
    try:
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
        logger.info("Demo flow completed for tenant %s", report.tenant_id)
        print(
            "tenant={tenant} active_users={active} inactive_users={inactive} total_balance={balance}".format(
                tenant=report.tenant_id,
                active=report.active_users,
                inactive=report.inactive_users,
                balance=report.total_balance,
            )
        )
    except DirectoryError as exc:
        logger.error("Application flow failed: %s", exc)
        raise


if __name__ == "__main__":
    main()
