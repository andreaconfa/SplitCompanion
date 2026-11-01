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
  return (
    <header className="page-head">
      {back && (
        <Link className="back" to={back}>
          <ArrowLeft size={18} /> Indietro
        </Link>
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
  return error ? (
    <div className="notice error" role="alert">
      {error instanceof Error ? error.message : String(error)}
    </div>
  ) : null;
}
export function Loading() {
  return (
    <div className="skeletons" aria-label="Caricamento" role="status">
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
  const payer =
    users.find((u) => u.id === expense.paid_by_user_id)?.display_name ??
    "Utente";
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
        <small>
          Pagato da <Person user={users.find(user => user.id === expense.paid_by_user_id)} name={payer} small />
          {expense.source === "SPLITWISE" ? " · Splitwise" : ""}
          {expense.subscription_id ? " · Ricorrente" : ""}
        </small>
        <small className="expense-participants"><span>Divisa tra</span>{expense.splits.map(split => <Person key={split.user_id} user={users.find(user => user.id === split.user_id)} small />)}</small>
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
            ? "Terminato"
            : subscription.active
              ? "Prossimo: " + dateLabel(subscription.next_occurrence_date)
              : "In pausa"}{" "}
          ·{" "}
          <Person user={users.find(user => user.id === subscription.paid_by_user_id)} small />
        </small>
        {credits.data
          ?.filter((credit) => credit.remaining_cents > 0)
          .map((credit) => (
            <small className="row-credit" key={credit.user_id}>
              <Person user={users.find(user => user.id === credit.user_id)} name="Un partecipante" small />{" "}
              ha {money(credit.remaining_cents, subscription.currency)} di
              credito
            </small>
          ))}
        {credits.error && (
          <small>
            Credito non disponibile: apri il dettaglio per riprovare.
          </small>
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
        <small>Splitwise · Movimento storico</small>
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
  label = "Aggiungi",
}: {
  to: string;
  label?: string;
}) {
  return (
    <Link className="btn btn-primary" to={to}>
      <Plus size={18} />
      {label}
    </Link>
  );
}
export function Busy({
  busy,
  label = "Salva",
}: {
  busy: boolean;
  label?: string;
}) {
  return (
    <Button type="submit" disabled={busy}>
      {busy ? (
        <>
          <LoaderCircle size={18} className="spin" /> Salvataggio…
        </>
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
            aria-label="Chiudi"
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
