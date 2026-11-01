from datetime import date, datetime
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator

Money = Annotated[StrictInt, Field(gt=0, le=10**12)]
Currency = Annotated[str, Field(pattern=r"^[A-Z]{3}$")]
Name = Annotated[str, Field(min_length=1, max_length=200)]
Password = Annotated[str, Field(min_length=10, max_length=256)]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Output(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Login(Input):
    username: Annotated[str, Field(min_length=1, max_length=50)]
    password: Annotated[str, Field(min_length=1, max_length=256)]


class PasswordChange(Input):
    current_password: Annotated[str, Field(min_length=1, max_length=256)]
    new_password: Password
    code: Annotated[str, Field(min_length=1, max_length=128)] | None = None


class UserCreate(Input):
    username: Annotated[str, Field(pattern=r"^[a-zA-Z0-9_.-]{3,50}$")]
    display_name: Name
    password: Password
    is_admin: bool = False

    @field_validator("username")
    @classmethod
    def normalize(cls, v):
        return v.lower()


class UserUpdate(Input):
    display_name: Name | None = None
    password: Password | None = None
    is_admin: bool | None = None
    is_active: bool | None = None


class UserResponse(Output):
    avatar_version: str | None = None
    id: int
    username: str
    display_name: str
    is_admin: bool
    is_active: bool


class AuthResponse(Output):
    user: UserResponse
    csrf_token: str
    timezone: str
    default_currency: str = "EUR"
    supported_currencies: list[str] = Field(default_factory=list)
    supported_languages: list[str] = Field(default_factory=lambda: ["en", "it"])


class GroupCreate(Input):
    name: Name
    description: Annotated[str, Field(max_length=2000)] = ""
    member_ids: list[int] = Field(default_factory=list, max_length=100)


class GroupUpdate(Input):
    name: Name | None = None
    description: Annotated[str, Field(max_length=2000)] | None = None
    archived: bool | None = None


class GroupResponse(Output):
    id: int
    name: str
    description: str
    archived: bool
    created_by_user_id: int
    created_at: datetime
    updated_at: datetime


class MemberCreate(Input):
    user_id: int


class SplitInput(Input):
    user_id: StrictInt
    amount_cents: Annotated[StrictInt, Field(ge=0, le=10**12)] | None = None
    percentage: Annotated[str, Field(max_length=20)] | None = None


class SplitResponse(Output):
    user_id: int
    amount_cents: int


class SplitCreate(Input):
    split_mode: Literal["equal", "exact", "percent", "single"] = "equal"
    splits: list[SplitInput] = Field(min_length=1, max_length=100)


class CategoryInput(Input):
    category_id: int | None = None
    # Accepted for older clients; category_id is the only writable display metadata.
    icon_key: Annotated[str, Field(max_length=60)] | None = None


class CategoryOutput(Output):
    category_id: int | None = None
    icon_key: str | None = None


class ExpenseCreate(CategoryInput, SplitCreate):
    group_id: int
    description: Name
    amount_cents: Money
    currency: Currency = "EUR"
    paid_by_user_id: int
    expense_date: date
    notes: Annotated[str, Field(max_length=5000)] = ""


class ExpenseUpdate(CategoryInput):
    group_id: int | None = None
    description: Name | None = None
    amount_cents: Money | None = None
    currency: Currency | None = None
    paid_by_user_id: int | None = None
    expense_date: date | None = None
    notes: Annotated[str, Field(max_length=5000)] | None = None
    split_mode: Literal["equal", "exact", "percent", "single"] | None = None
    splits: list[SplitInput] | None = Field(default=None, min_length=1, max_length=100)


class ExpenseResponse(CategoryOutput):
    id: int
    group_id: int
    description: str
    amount_cents: int
    currency: str
    paid_by_user_id: int
    expense_date: date
    notes: str
    subscription_id: int | None
    subscription_occurrence_date: date | None
    source: str
    created_at: datetime
    updated_at: datetime
    splits: list[SplitResponse] = Field(default_factory=list)


class SettlementCreate(Input):
    group_id: int
    paid_by_user_id: int
    paid_to_user_id: int
    amount_cents: Money
    currency: Currency = "EUR"
    settlement_date: date
    notes: Annotated[str, Field(max_length=5000)] = ""


class SettlementResponse(Output):
    id: int
    group_id: int
    paid_by_user_id: int
    paid_to_user_id: int
    amount_cents: int
    currency: str
    settlement_date: date
    kind: str
    subscription_id: int | None
    notes: str
    source: str
    created_at: datetime


class SubscriptionCreate(CategoryInput, SplitCreate):
    group_id: int
    name: Name
    description: Annotated[str, Field(max_length=2000)] = ""
    amount_cents: Money
    currency: Currency = "EUR"
    paid_by_user_id: int
    recurrence_rule: str
    start_date: date
    end_date: date | None = None


class SubscriptionUpdate(CategoryInput):
    group_id: int | None = None
    name: Name | None = None
    description: Annotated[str, Field(max_length=2000)] | None = None
    amount_cents: Money | None = None
    currency: Currency | None = None
    paid_by_user_id: int | None = None
    recurrence_rule: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    split_mode: Literal["equal", "exact", "percent", "single"] | None = None
    splits: list[SplitInput] | None = Field(default=None, min_length=1, max_length=100)


class SubscriptionResponse(CategoryOutput):
    id: int
    group_id: int
    name: str
    description: str
    amount_cents: int
    currency: str
    paid_by_user_id: int
    recurrence_rule: str
    start_date: date
    next_occurrence_date: date
    end_date: date | None
    active: bool
    deleted: bool
    created_at: datetime
    updated_at: datetime
    splits: list[SplitResponse] = Field(default_factory=list)


class AdvanceCreate(Input):
    user_id: int
    amount_cents: Money
    settlement_date: date
    notes: Annotated[str, Field(max_length=5000)] = ""


class MappingInput(Input):
    users: dict[str, int | dict[str, str] | None]
    groups: dict[str, int | dict[str, str]]
