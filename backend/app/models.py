from datetime import date, datetime, timezone
from typing import Optional
from sqlalchemy import UniqueConstraint, CheckConstraint, Column, Text
from sqlmodel import SQLModel, Field


def now():
    return datetime.now(timezone.utc)


class Record(SQLModel):
    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=now)


class User(Record, table=True):
    username: str = Field(unique=True, index=True)
    display_name: str
    password_hash: str
    is_admin: bool = False
    is_active: bool = True
    avatar_version: Optional[str] = None
    mfa_secret: Optional[str] = None
    mfa_enabled: bool = False
    mfa_last_counter: int = -1
    updated_at: datetime = Field(default_factory=now)


class UserAvatar(SQLModel, table=True):
    user_id: int = Field(primary_key=True, foreign_key="user.id")
    png: bytes


class AuthSession(SQLModel, table=True):
    token_hash: str = Field(primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    csrf_token: str
    mfa_verified: bool = False
    expires_at: datetime


class Group(Record, table=True):
    name: str
    description: str = ""
    created_by_user_id: int = Field(foreign_key="user.id")
    updated_at: datetime = Field(default_factory=now)
    archived: bool = False


class GroupMember(Record, table=True):
    __table_args__ = (UniqueConstraint("group_id", "user_id"),)
    group_id: int = Field(foreign_key="group.id", index=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    joined_at: datetime = Field(default_factory=now)
    active: bool = True


class ImportBatch(Record, table=True):
    source: str = "SPLITWISE"
    format: str
    original_filename: str
    file_hash: str = Field(index=True)
    uploaded_by_user_id: int = Field(foreign_key="user.id")
    status: str = "ANALYZED"
    completed_at: Optional[datetime] = None
    records_total: int = 0
    records_imported: int = 0
    records_skipped: int = 0
    records_failed: int = 0
    data_json: str = Field(default="{}", sa_column=Column(Text, nullable=False))
    mapping_json: str = "{}"
    previewed: bool = False


class Category(Record, table=True):
    name: str
    slug: Optional[str] = Field(default=None, unique=True)
    icon_key: str = "tag"
    created_by_user_id: Optional[int] = Field(default=None, foreign_key="user.id")


class CustomIcon(Record, table=True):
    name: str
    created_by_user_id: int = Field(foreign_key="user.id")
    png: bytes


class CategoryMetadata(SQLModel):
    category_id: Optional[int] = Field(default=None, foreign_key="category.id")
    icon_key: Optional[str] = None
    category_source: Optional[str] = None


class Subscription(CategoryMetadata, Record, table=True):
    __table_args__ = (CheckConstraint("amount_cents > 0"),)
    group_id: int = Field(foreign_key="group.id", index=True)
    name: str
    description: str = ""
    amount_cents: int
    currency: str = "EUR"
    paid_by_user_id: int = Field(foreign_key="user.id")
    recurrence_rule: str
    start_date: date
    next_occurrence_date: date
    end_date: Optional[date] = None
    active: bool = True
    deleted: bool = False
    created_by_user_id: int = Field(foreign_key="user.id")
    updated_at: datetime = Field(default_factory=now)


class SubscriptionSplit(Record, table=True):
    __table_args__ = (
        UniqueConstraint("subscription_id", "user_id"),
        CheckConstraint("amount_cents >= 0"),
    )
    subscription_id: int = Field(foreign_key="subscription.id", index=True)
    user_id: int = Field(foreign_key="user.id")
    amount_cents: int


class Expense(CategoryMetadata, Record, table=True):
    __table_args__ = (
        UniqueConstraint("subscription_id", "subscription_occurrence_date"),
        CheckConstraint("amount_cents > 0"),
    )
    group_id: int = Field(foreign_key="group.id", index=True)
    description: str
    amount_cents: int
    currency: str = "EUR"
    paid_by_user_id: int = Field(foreign_key="user.id")
    expense_date: date = Field(index=True)
    notes: str = ""
    created_by_user_id: int = Field(foreign_key="user.id")
    subscription_id: Optional[int] = Field(default=None, foreign_key="subscription.id")
    subscription_occurrence_date: Optional[date] = None
    updated_at: datetime = Field(default_factory=now)
    source: str = "NATIVE"
    import_batch_id: Optional[int] = Field(default=None, foreign_key="importbatch.id", index=True)
    external_id: Optional[str] = None


class ExpenseSplit(Record, table=True):
    __table_args__ = (
        UniqueConstraint("expense_id", "user_id"),
        CheckConstraint("amount_cents >= 0"),
    )
    expense_id: int = Field(foreign_key="expense.id", index=True)
    user_id: int = Field(foreign_key="user.id")
    amount_cents: int


class Settlement(Record, table=True):
    __table_args__ = (
        CheckConstraint("amount_cents > 0"),
        CheckConstraint("paid_by_user_id != paid_to_user_id"),
    )
    group_id: int = Field(foreign_key="group.id", index=True)
    paid_by_user_id: int = Field(foreign_key="user.id")
    paid_to_user_id: int = Field(foreign_key="user.id")
    amount_cents: int
    currency: str = "EUR"
    settlement_date: date
    kind: str = "GENERAL"
    subscription_id: Optional[int] = Field(default=None, foreign_key="subscription.id")
    notes: str = ""
    created_by_user_id: int = Field(foreign_key="user.id")
    source: str = "NATIVE"
    import_batch_id: Optional[int] = Field(default=None, foreign_key="importbatch.id", index=True)
    external_id: Optional[str] = None


class SubscriptionAdvanceApplication(Record, table=True):
    __table_args__ = (
        UniqueConstraint("advance_settlement_id", "expense_id", "user_id"),
        CheckConstraint("amount_cents > 0"),
    )
    advance_settlement_id: int = Field(foreign_key="settlement.id", index=True)
    expense_id: int = Field(foreign_key="expense.id", index=True)
    user_id: int = Field(foreign_key="user.id")
    amount_cents: int


class AdvanceRefundAllocation(Record, table=True):
    __table_args__ = (
        UniqueConstraint("advance_settlement_id", "refund_settlement_id"),
        CheckConstraint("amount_cents > 0"),
    )
    advance_settlement_id: int = Field(foreign_key="settlement.id", index=True)
    refund_settlement_id: int = Field(foreign_key="settlement.id", index=True)
    amount_cents: int


class LegacyTransaction(CategoryMetadata, Record, table=True):
    group_id: int = Field(foreign_key="group.id", index=True)
    import_batch_id: int = Field(foreign_key="importbatch.id", index=True)
    external_id: Optional[str] = None
    date: date
    description: str
    cost_cents: Optional[int] = None
    currency: str = "EUR"
    source: str = "SPLITWISE"
    raw_metadata_json: str = "{}"


class LegacyTransactionEntry(Record, table=True):
    __table_args__ = (UniqueConstraint("legacy_transaction_id", "user_id"),)
    legacy_transaction_id: int = Field(foreign_key="legacytransaction.id", index=True)
    user_id: int = Field(foreign_key="user.id")
    balance_delta_cents: int


class ImportedRecord(Record, table=True):
    fingerprint: str = Field(unique=True, index=True)
    import_batch_id: int = Field(foreign_key="importbatch.id", index=True)


class SubscriptionOccurrence(Record, table=True):
    __table_args__ = (UniqueConstraint("subscription_id", "occurrence_date"),)
    subscription_id: int = Field(foreign_key="subscription.id", index=True)
    occurrence_date: date
    expense_id: Optional[int] = Field(default=None, foreign_key="expense.id")


class MFAChallenge(SQLModel, table=True):
    token_hash: str = Field(primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    purpose: str
    expires_at: datetime
    secret: Optional[str] = None


class MFARecovery(SQLModel, table=True):
    code_hash: str = Field(primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)


class AuthThrottle(SQLModel, table=True):
    key: str = Field(primary_key=True)
    attempts: int = 0
    expires_at: datetime


class SetupState(SQLModel, table=True):
    __table_args__ = (CheckConstraint("id = 1"),)
    id: int = Field(default=1, primary_key=True)
    completed: bool = False
    token_hash: Optional[str] = None
    expires_at: Optional[datetime] = None
    attempts: int = 0
    attempt_window_expires_at: Optional[datetime] = None
