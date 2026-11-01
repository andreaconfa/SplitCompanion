export interface User {
  avatar_version?: string | null;
  id: number;
  username: string;
  display_name: string;
  is_admin: boolean;
  is_active: boolean;
}
export interface Session {
  user: User;
  csrf_token: string;
  timezone: string;
}
export interface Group {
  id: number;
  name: string;
  description: string;
  archived: boolean;
  created_by_user_id: number;
  created_at: string;
  updated_at: string;
}
export interface Member {
  id: number;
  user_id: number;
  display_name: string;
  username: string;
  active: boolean;
}
export interface Split {
  user_id: number;
  amount_cents: number;
}
export type SplitMode = "equal" | "exact" | "percent" | "single";
export interface Expense extends CategoryMetadata {
  id: number;
  group_id: number;
  description: string;
  amount_cents: number;
  currency: string;
  paid_by_user_id: number;
  expense_date: string;
  notes: string;
  source: "NATIVE" | "SPLITWISE";
  subscription_id: number | null;
  subscription_occurrence_date: string | null;
  splits: Split[];
  created_at: string;
  updated_at: string;
}
export interface Balance {
  user_id: number;
  currency: string;
  balance_cents: number;
}
export interface Debt {
  paid_by_user_id: number;
  paid_to_user_id: number;
  amount_cents: number;
  currency: string;
  group_id?: number;
  group_name?: string;
}
export interface Settlement extends Debt {
  id: number;
  group_id: number;
  settlement_date: string;
  kind: string;
  subscription_id: number | null;
  notes: string;
  source: string;
  created_at: string;
}
export interface Subscription extends CategoryMetadata {
  id: number;
  group_id: number;
  name: string;
  description: string;
  amount_cents: number;
  currency: string;
  paid_by_user_id: number;
  recurrence_rule: string;
  start_date: string;
  next_occurrence_date: string | null;
  end_date: string | null;
  active: boolean;
  deleted: boolean;
  splits: Split[];
  created_at: string;
  updated_at: string;
}
export interface Credit {
  user_id: number;
  advanced_cents: number;
  used_cents: number;
  refunded_cents: number;
  remaining_cents: number;
  history: {
    date: string;
    kind: string;
    amount_cents: number;
    expense_id?: number;
    settlement_id?: number;
  }[];
}
export interface Legacy extends CategoryMetadata {
  id: number;
  group_id: number;
  date: string;
  description: string;
  cost_cents: number;
  currency: string;
  source: string;
  entries: { user_id: number; balance_delta_cents: number }[];
}
export interface Dashboard {
  user: User;
  balances: {
    currency: string;
    balance_cents: number;
    to_receive_cents: number;
    to_pay_cents: number;
  }[];
  debts: Debt[];
  upcoming: Subscription[];
  recent_expenses: Expense[];
  groups: Group[];
}
export type UserMapping =
  number | { username: string; display_name: string; password?: string } | null;
export type GroupMapping = number | { name: string };
export interface Mapping {
  users: Record<string, UserMapping>;
  groups: Record<string, GroupMapping>;
}
export interface Batch {
  id: number;
  original_filename: string;
  format: string;
  status: string;
  records_total: number;
  records_imported: number;
  records_skipped: number;
  records_failed: number;
  created_at: string;
  people: string[];
  groups: string[];
  errors: string[];
  warnings: string[];
  mapping: Mapping;
}
export interface Preview {
  records_total: number;
  importable: number;
  duplicates: number;
  errors: string[];
  warnings: string[];
  records: {
    description: string;
    date: string;
    currency: string;
    kind: string;
    group: string;
    amount_cents: number;
    deltas: Record<string, number>;
  }[];
  balance_deltas: {
    group: string;
    user: string;
    currency: string;
    amount_cents: number;
  }[];
}

export interface CategoryMetadata { category_id?: number | null; icon_key?: string | null; }
export interface Category { id: number; name: string; slug: string | null; icon_key: string; created_by_user_id: number | null; }
export interface IconCatalog { builtin: string[]; custom: {id: number; name: string; icon_key: string; created_by_user_id: number}[]; }

export interface MonthlyStatisticsData {
  month: string;
  current_month: string;
  available_months: string[];
  currencies: string[];
  currency: string;
  period: { start: string; end: string; days: number; is_current: boolean };
  comparison: { month: string; start: string; end: string; total_cents: number; change_cents: number; change_percent: number | null };
  summary: { total_cents: number; expense_count: number; average_cents: number; daily_average_cents: number; native_total_cents: number; legacy_total_cents: number };
  coverage: { legacy_included_count: number; legacy_excluded_count: number; legacy_transfers_excluded_count: number; legacy_missing_cost_count: number; legacy_nonpositive_count: number };
  categories: { category_id: number | null; name: string; icon_key: string; total_cents: number; count: number }[];
  groups: { group_id: number; name: string; total_cents: number; count: number }[];
  trend: { month: string; total_cents: number; count: number; is_partial: boolean }[];
  daily: { date: string; total_cents: number; cumulative_cents: number }[];
}
