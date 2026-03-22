from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
import logging
import time

from src.multi_tenant_directory.config import AppConfig
from src.multi_tenant_directory.domain.models import Session, User
from src.multi_tenant_directory.exceptions import DirectoryError
from src.multi_tenant_directory.logging_config import setup_logging
from src.multi_tenant_directory.services.bootstrap import ApplicationContainer


def main() -> None:
    setup_logging()
    logger = logging.getLogger(__name__)
    args = _build_parser().parse_args()
    container = ApplicationContainer(AppConfig())

    try:
        if args.command == "load-test":
            _run_load_test(container, args, logger)
            return

        _run_demo(container, args, logger)
    except DirectoryError as exc:
        logger.error("Application flow failed: %s", exc)
        raise


def _run_demo(
    container: ApplicationContainer,
    args: argparse.Namespace,
    logger: logging.Logger,
) -> None:
    user = User(
        tenant_id=args.tenant_id,
        user_id=args.user_id,
        email=args.email,
        full_name=args.full_name,
        is_active=not args.inactive,
    )
    container.user_directory.register_user(
        user=user,
        starting_balance=args.starting_balance,
        currency=args.currency,
    )
    container.user_directory.charge_user(
        tenant_id=args.tenant_id,
        user_id=args.user_id,
        amount=args.charge_amount,
    )
    container.user_directory.create_session(
        Session(
            session_id=args.session_id,
            tenant_id=args.tenant_id,
            user_id=args.user_id,
            payload=args.session_payload,
        )
    )
    container.replication.replicate_all()
    report = container.reporting.generate_daily_report(args.tenant_id)
    logger.info("Demo flow completed for tenant %s", report.tenant_id)
    print(
        "tenant={tenant} active_users={active} inactive_users={inactive} total_balance={balance}".format(
            tenant=report.tenant_id,
            active=report.active_users,
            inactive=report.inactive_users,
            balance=report.total_balance,
        )
    )


def _run_load_test(
    container: ApplicationContainer,
    args: argparse.Namespace,
    logger: logging.Logger,
) -> None:
    start_time = time.perf_counter()
    total_operations = args.tenant_count * args.users_per_tenant

    def run_user_flow(tenant_index: int, user_index: int) -> None:
        tenant_id = f"{args.tenant_prefix}-{tenant_index:04d}"
        user_id = f"{args.user_prefix}-{tenant_index:04d}-{user_index:04d}"
        session_id = f"{args.session_prefix}-{tenant_index:04d}-{user_index:04d}"
        user = User(
            tenant_id=tenant_id,
            user_id=user_id,
            email=f"{user_id}@example.com",
            full_name=f"Load Test User {tenant_index}-{user_index}",
            is_active=True,
        )
        container.user_directory.register_user(
            user=user,
            starting_balance=args.starting_balance,
            currency=args.currency,
        )
        container.user_directory.charge_user(
            tenant_id=tenant_id,
            user_id=user_id,
            amount=args.charge_amount,
        )
        container.user_directory.create_session(
            Session(
                session_id=session_id,
                tenant_id=tenant_id,
                user_id=user_id,
                payload=args.session_payload,
            )
        )

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = [
            executor.submit(run_user_flow, tenant_index, user_index)
            for tenant_index in range(args.tenant_count)
            for user_index in range(args.users_per_tenant)
        ]
        for future in futures:
            future.result()

    container.replication.replicate_all()
    elapsed = time.perf_counter() - start_time
    throughput = total_operations / elapsed if elapsed > 0 else 0.0

    logger.info(
        "Load test completed: tenants=%s users_per_tenant=%s operations=%s elapsed=%.4fs",
        args.tenant_count,
        args.users_per_tenant,
        total_operations,
        elapsed,
    )
    print(
        "load_test tenants={tenants} users_per_tenant={users_per_tenant} operations={operations} workers={workers} elapsed_seconds={elapsed:.4f} throughput_ops_per_sec={throughput:.2f}".format(
            tenants=args.tenant_count,
            users_per_tenant=args.users_per_tenant,
            operations=total_operations,
            workers=args.workers,
            elapsed=elapsed,
            throughput=throughput,
        )
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Multi-tenant user directory demo and load-test CLI."
    )
    subparsers = parser.add_subparsers(dest="command")

    demo_parser = subparsers.add_parser("demo", help="Run a single demo workflow.")
    _add_demo_arguments(demo_parser)

    load_test_parser = subparsers.add_parser(
        "load-test",
        help="Run a simple workload generator across multiple tenants.",
    )
    _add_load_test_arguments(load_test_parser)

    parser.set_defaults(
        command="demo",
        tenant_id="tenant-acme",
        user_id="user-001",
        email="owner@acme.example",
        full_name="Acme Owner",
        inactive=False,
        starting_balance=Decimal("100.00"),
        currency="USD",
        charge_amount=Decimal("19.99"),
        session_id="session-001",
        session_payload='{"role":"owner"}',
    )
    return parser


def _add_demo_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--tenant-id", default="tenant-acme")
    parser.add_argument("--user-id", default="user-001")
    parser.add_argument("--email", default="owner@acme.example")
    parser.add_argument("--full-name", default="Acme Owner")
    parser.add_argument("--inactive", action="store_true")
    parser.add_argument("--starting-balance", type=Decimal, default=Decimal("100.00"))
    parser.add_argument("--currency", default="USD")
    parser.add_argument("--charge-amount", type=Decimal, default=Decimal("19.99"))
    parser.add_argument("--session-id", default="session-001")
    parser.add_argument("--session-payload", default='{"role":"owner"}')


def _add_load_test_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--tenant-count", type=int, default=5)
    parser.add_argument("--users-per-tenant", type=int, default=10)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--tenant-prefix", default="tenant")
    parser.add_argument("--user-prefix", default="user")
    parser.add_argument("--session-prefix", default="session")
    parser.add_argument("--starting-balance", type=Decimal, default=Decimal("100.00"))
    parser.add_argument("--currency", default="USD")
    parser.add_argument("--charge-amount", type=Decimal, default=Decimal("19.99"))
    parser.add_argument("--session-payload", default='{"role":"load-test"}')


if __name__ == "__main__":
    main()
