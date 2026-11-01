import { t, translateMessage } from "../i18n";
import { useLanguage } from "../i18n/react";
import { Person, UserPhoto } from "./Person";
import { CategoryBadge } from "./Categories";
import {
  useEffect,
  useRef,
  type ReactNode,
  type ButtonHTMLAttributes,
} from "react";
import {
  ArrowLeft,
  ChevronRight,
  X,
  Plus,
  Inbox,
  LoaderCircle,
} from "lucide-react";
import { Link } from "react-router-dom";
import type { Expense, Subscription, User, Credit, Legacy } from "../api/types";
import { useApi } from "../api/client";
import { money, dateLabel, recurrenceLabel } from "../utils/money";
export function Button({
  children,
  variant = "primary",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "danger" | "ghost";
}) {
  useLanguage();
  return (
    <button className={"btn btn-" + variant} {...props}>
      {children}
    </button>
  );
}
export function PageHead({
  eyebrow,
  title,
  description,
  action,
  back,
}: {
  eyebrow?: string;
  title: string;
  description?: string;
  action?: ReactNode;
  back?: string;
}) {
  useLanguage();
  return (
    <header className="page-head">
      {back && (
        <Link className="back" to={back}>
          <ArrowLeft size={18} />{" "}{t("Indietro")}</Link>
      )}
      <div className="heading-row">
        <div>
          {eyebrow && <p className="eyebrow">{eyebrow}</p>}
          <h1>{title}</h1>
          {description && <p className="muted">{description}</p>}
        </div>
        {action}
      </div>
    </header>
  );
}
export function Section({
  title,
  action,
  children,
}: {
  title: string;
  action?: ReactNode;
  children: ReactNode;
}) {
  useLanguage();
  return (
    <section className="section">
      <div className="section-head">
        <h2>{title}</h2>
        {action}
      </div>
      {children}
    </section>
  );
}
export function ErrorBox({ error }: { error: unknown }) {
  useLanguage();
  return error ? (
    <div className="notice error" role="alert">
      {translateMessage(error instanceof Error ? error.message : String(error))}
    </div>
  ) : null;
}
export function Loading() {
  useLanguage();
  return (
    <div className="skeletons" aria-label={t("Caricamento")} role="status">
      <div />
      <div />
      <div />
    </div>
  );
}
export function State({
  pending,
  error,
  children,
}: {
  pending: boolean;
  error: unknown;
  children: ReactNode;
}) {
  useLanguage();
  if (pending) return <Loading />;
  if (error) return <ErrorBox error={error} />;
  return <>{children}</>;
}
export function Empty({
  title,
  detail,
  action,
}: {
  title: string;
  detail?: string;
  action?: ReactNode;
}) {
  useLanguage();
  return (
    <div className="empty">
      <div className="empty-icon">
        <Inbox size={26} />
      </div>
      <h3>{title}</h3>
      {detail && <p>{detail}</p>}
      {action}
    </div>
  );
}
export function Avatar({ name, size = "normal" }: { name: string; size?: "normal" | "small" }) {
  useLanguage();
  return <UserPhoto name={name} small={size === "small"} />;
}
export function Money({
  value,
  currency = "EUR",
  signed = false,
}: {
  value: number;
  currency?: string;
  signed?: boolean;
}) {
  useLanguage();
  return (
    <span
      className={
        "money " +
        (signed ? (value > 0 ? "positive" : value < 0 ? "negative" : "") : "")
      }
    >
      {money(value, currency, signed)}
    </span>
  );
}
export function ExpenseRow({
  expense,
  users,
  groupName,
}: {
  expense: Expense;
  users: User[];
  groupName?: string;
}) {
  useLanguage();
  const payer =
    users.find((u) => u.id === expense.paid_by_user_id)?.display_name ??
    t("Utente");
  return (
    <Link to={"/expenses/" + expense.id} className="list-row">
      <span className="row-icon">
        <CategoryBadge value={expense} />
      </span>
      <div className="row-main">
        <strong>{expense.description}</strong>
        <span>
          {groupName ? groupName + " · " : ""}
          {dateLabel(expense.expense_date)}
        </span>
        <small>{t("Pagato da")}{" "}<Person user={users.find(user => user.id === expense.paid_by_user_id)} name={payer} small />
          {expense.source === "SPLITWISE" ? " · Splitwise" : ""}
          {expense.subscription_id ? t(" · Ricorrente") : ""}
        </small>
        <small className="expense-participants"><span>{t("Divisa tra")}</span>{expense.splits.map(split => <Person key={split.user_id} user={users.find(user => user.id === split.user_id)} small />)}</small>
      </div>
      <div className="row-end">
        <Money value={expense.amount_cents} currency={expense.currency} />
        <ChevronRight size={16} />
      </div>
    </Link>
  );
}
export function SubscriptionRow({
  subscription,
  users,
}: {
  subscription: Subscription;
  users: User[];
}) {
  useLanguage();
  const credits = useApi<Credit[]>(
    "/subscriptions/" + subscription.id + "/credits",
  );
  return (
    <Link className="list-row" to={"/subscriptions/" + subscription.id}>
      <span className="service-icon">
        <CategoryBadge value={subscription} />
      </span>
      <div className="row-main">
        <strong>{subscription.name}</strong>
        <span>{recurrenceLabel(subscription.recurrence_rule)}</span>
        <small>
          {subscription.deleted
            ? t("Terminato")
            : subscription.active
              ? t("Prossimo: ") + dateLabel(subscription.next_occurrence_date)
              : t("In pausa")}{" "}
          ·{" "}
          <Person user={users.find(user => user.id === subscription.paid_by_user_id)} small />
        </small>
        {credits.data
          ?.filter((credit) => credit.remaining_cents > 0)
          .map((credit) => (
            <small className="row-credit" key={credit.user_id}>
              <Person user={users.find(user => user.id === credit.user_id)} name={t("Un partecipante")} small />{" "}{t("ha")}{" "}{money(credit.remaining_cents, subscription.currency)}{" "}{t("di credito")}</small>
          ))}
        {credits.error && (
          <small>{t("Credito non disponibile: apri il dettaglio per riprovare.")}</small>
        )}
      </div>
      <div className="row-end">
        <Money
          value={subscription.amount_cents}
          currency={subscription.currency}
        />
        <ChevronRight size={16} />
      </div>
    </Link>
  );
}
export function LegacyRow({
  record,
  groupName,
}: {
  record: Legacy;
  groupName?: string;
}) {
  useLanguage();
  return (
    <Link to={"/legacy/" + record.id} className="list-row">
      <span className="row-icon">
        <CategoryBadge value={record} />
      </span>
      <div className="row-main">
        <strong>{record.description}</strong>
        <span>
          {groupName ? groupName + " · " : ""}
          {dateLabel(record.date)}
        </span>
        <small>{t("Splitwise · Movimento storico")}</small>
      </div>
      <div className="row-end">
        <Money value={record.cost_cents} currency={record.currency} />
        <ChevronRight size={16} />
      </div>
    </Link>
  );
}
export function AddLink({
  to,
  label = t("Aggiungi"),
}: {
  to: string;
  label?: string;
}) {
  useLanguage();
  return (
    <Link className="btn btn-primary" to={to}>
      <Plus size={18} />
      {label}
    </Link>
  );
}
export function Busy({
  busy,
  label = t("Salva"),
}: {
  busy: boolean;
  label?: string;
}) {
  useLanguage();
  return (
    <Button type="submit" disabled={busy}>
      {busy ? (
        <>
          <LoaderCircle size={18} className="spin" />{" "}{t("Salvataggio…")}</>
      ) : (
        label
      )}
    </Button>
  );
}
export function Sheet({
  title,
  children,
  onClose,
}: {
  title: string;
  children: ReactNode;
  onClose: () => void;
}) {
  useLanguage();
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const old = document.activeElement as HTMLElement;
    const focusable = () =>
      ref.current?.querySelectorAll<HTMLElement>(
        'button,a,input,select,textarea,[tabindex="0"]',
      );
    focusable()?.[0]?.focus();
    const handle = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
      if (event.key === "Tab") {
        const elements = focusable();
        if (!elements?.length) return;
        const first = elements[0],
          last = elements[elements.length - 1];
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault();
          last.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first.focus();
        }
      }
    };
    document.addEventListener("keydown", handle);
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", handle);
      document.body.style.overflow = overflow;
      old?.focus();
    };
  }, [onClose]);
  return (
    <div className="sheet-overlay" onClick={onClose}>
      <div
        className="sheet"
        ref={ref}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="sheet-head">
          <h2>{title}</h2>
          <button
            type="button"
            className="icon-button"
            aria-label={t("Chiudi")}
            onClick={onClose}
          >
            <X size={22} />
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}
