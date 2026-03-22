from __future__ import annotations


class DirectoryError(Exception):
    """Base exception for application-specific failures."""


class ShardNotFoundError(DirectoryError, LookupError):
    """Raised when a tenant cannot be routed to a configured shard."""


class UserAlreadyExistsError(DirectoryError):
    """Raised when a duplicate user is inserted for the same tenant."""


class BillingAccountAlreadyExistsError(DirectoryError):
    """Raised when a duplicate billing account is inserted."""


class BillingAccountNotFoundError(DirectoryError, LookupError):
    """Raised when a billing account cannot be found."""


class DataAccessError(DirectoryError):
    """Raised when the relational store cannot complete an operation."""


class ReplicationError(DirectoryError):
    """Raised when primary-to-replica synchronization fails."""
