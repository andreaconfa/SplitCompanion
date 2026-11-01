import { t } from "../i18n";
import { useLanguage } from "../i18n/react";
import { Person } from "../components/Person";
import { CategoryEditor } from "../components/Categories";
import { useState } from "react";
import { Link, useParams, useNavigate } from "react-router-dom";
import {
  SlidersHorizontal,
  Pencil,
  Trash2,
  Receipt,
  Archive,
} from "lucide-react";
import { useApi, useAction, send, params } from "../api/client";
import type { Expense, Subscription, Legacy } from "../api/types";
import { useData } from "../components/context";
import {
  PageHead,
  State,
  Empty,
  ExpenseRow,
  AddLink,
  Sheet,
  Button,
  ErrorBox,
  Money,
  Section,
  LegacyRow,
} from "../components/ui";
import { dateLabel } from "../utils/money";
import { filterLegacy } from "../utils/history";
export default function Expenses() {
  useLanguage();
  const { users, groups } = useData();
  const subscriptions = useApi<Subscription[]>("/subscriptions");
  const [filters, setFilters] = useState<Record<string, string>>({});
  const [open, setOpen] = useState(false);
  const expenses = useApi<Expense[]>("/expenses" + params(filters));
  const includeLegacy =
    filters.source !== "NATIVE" &&
    !filters.payer_id &&
    !filters.subscription_id;
  const legacy = useApi<Legacy[]>(
    "/legacy" + params({ group_id: filters.group_id }),
    includeLegacy,
  );
  const history = [
    ...(expenses.data ?? []).map((record) => ({
      kind: "expense" as const,
      record,
      date: record.expense_date,
    })),
    ...filterLegacy(legacy.data ?? [], filters).map((record) => ({
      kind: "legacy" as const,
      record,
      date: record.date,
    })),
  ].sort((a, b) => b.date.localeCompare(a.date) || b.record.id - a.record.id);
  const count = Object.values(filters).filter(Boolean).length;
  return (
    <>
      <PageHead
        eyebrow={t("SPESE CONDIVISE")}
        title={t("Movimenti")}
        description={t("Importi, pagamenti e storico.")}
        action={<AddLink to="/expenses/new" label={t("Nuova")} />}
      />
      <div className="list-toolbar">
        <span>
          {expenses.isPending || (includeLegacy && legacy.isPending)
            ? "…"
            : history.length}{" "}{t("movimenti")}</span>
        <Button variant="secondary" onClick={() => setOpen(true)}>
          <SlidersHorizontal size={17} />{" "}{t("Filtri")}{" "}
          {count > 0 && <span className="count-badge">{count}</span>}
        </Button>
      </div>
      {(filters.payer_id || filters.subscription_id) && (
        <p className="notice">{t("I movimenti legacy senza un pagante unico sono esclusi dai filtri per pagante e abbonamento.")}</p>
      )}
      <State
        pending={expenses.isPending || (includeLegacy && legacy.isPending)}
        error={expenses.error || (includeLegacy && legacy.error)}
      >
        <div className="card">
          {history.length ? (
            history.map((entry) =>
              entry.kind === "legacy" ? (
                <LegacyRow
                  key={"legacy-" + entry.record.id}
                  record={entry.record}
                  groupName={
                    groups.find((group) => group.id === entry.record.group_id)
                      ?.name
                  }
                />
              ) : (
                <ExpenseRow
                  key={"expense-" + entry.record.id}
                  expense={entry.record}
                  users={users}
                  groupName={
                    groups.find((g) => g.id === entry.record.group_id)?.name
                  }
                />
              ),
            )
          ) : (
            <Empty
              title={
                count
                  ? t("Nessuna spesa con questi filtri")
                  : t("Ancora nessuna spesa")
              }
              detail={
                count
                  ? t("Prova ad ampliare la ricerca.")
                  : t("Aggiungi una spesa per iniziare.")
              }
              action={
                count ? (
                  <Button variant="secondary" onClick={() => setFilters({})}>{t("Azzera filtri")}</Button>
                ) : (
                  <AddLink to="/expenses/new" />
                )
              }
            />
          )}
        </div>
      </State>
      {open && (
        <Sheet title={t("Filtra le spese")} onClose={() => setOpen(false)}>
          <div className="form-card">
            <label>{t("Gruppo")}<select
                value={filters.group_id ?? ""}
                onChange={(e) =>
                  setFilters({ ...filters, group_id: e.target.value })
                }
              >
                <option value="">{t("Tutti i gruppi")}</option>
                {groups.map((g) => (
                  <option key={g.id} value={g.id}>
                    {g.name}
                  </option>
                ))}
              </select>
            </label>
            <div className="two-fields">
              <label>{t("Dal")}<input
                  type="date"
                  value={filters.date_from ?? ""}
                  onChange={(e) =>
                    setFilters({ ...filters, date_from: e.target.value })
                  }
                />
              </label>
              <label>{t("Al")}<input
                  type="date"
                  value={filters.date_to ?? ""}
                  min={filters.date_from}
                  onChange={(e) =>
                    setFilters({ ...filters, date_to: e.target.value })
                  }
                />
              </label>
            </div>
            {[
              ["payer_id", t("Pagato da")],
              ["participant_id", t("Persona coinvolta")],
            ].map(([key, label]) => (
              <label key={key}>
                {label}
                <select
                  value={filters[key] ?? ""}
                  onChange={(e) =>
                    setFilters({ ...filters, [key]: e.target.value })
                  }
                >
                  <option value="">{t("Tutte le persone")}</option>
                  {users.map((u) => (
                    <option key={u.id} value={u.id}>
                      {u.display_name}
                    </option>
                  ))}
                </select>
              </label>
            ))}
            <label>{t("Origine")}<select
                value={filters.source ?? ""}
                onChange={(e) =>
                  setFilters({ ...filters, source: e.target.value })
                }
              >
                <option value="">{t("Tutte")}</option>
                <option value="NATIVE">Split Companion</option>
                <option value="SPLITWISE">Splitwise</option>
              </select>
            </label>
            <label>{t("Abbonamento")}<select
                value={filters.subscription_id ?? ""}
                onChange={(e) =>
                  setFilters({ ...filters, subscription_id: e.target.value })
                }
              >
                <option value="">{t("Tutti")}</option>
                {subscriptions.data?.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name}
                  </option>
                ))}
              </select>
            </label>
            <ErrorBox error={subscriptions.error} />
            <div className="form-footer">
              <Button variant="secondary" onClick={() => setFilters({})}>{t("Azzera")}</Button>
              <Button onClick={() => setOpen(false)}>{t("Mostra risultati")}</Button>
            </div>
          </div>
        </Sheet>
      )}
    </>
  );
}
export function ExpenseDetail() {
  useLanguage();
  const { id } = useParams();
  const navigate = useNavigate();
  const { users, groups } = useData();
  const expense = useApi<Expense>("/expenses/" + id);
  const action = useAction(async () => send("/expenses/" + id, "DELETE"));
  const name = (uid: number) =>
    users.find((u) => u.id === uid)?.display_name ?? t("Utente");
  return (
    <State pending={expense.isPending} error={expense.error}>
      {expense.data && (
        <>
          <PageHead
            title={expense.data.description}
            eyebrow={
              expense.data.source === "SPLITWISE"
                ? t("IMPORTATA DA SPLITWISE")
                : t("SPESA CONDIVISA")
            }
            back={"/groups/" + expense.data.group_id + "?tab=expenses"}
            description={
              groups.find((g) => g.id === expense.data!.group_id)?.name
            }
          />
          <CategoryEditor value={expense.data} path={"/expenses/" + id} />
          <div className="card detail-hero">
            <Receipt size={28} />
            <Money
              value={expense.data.amount_cents}
              currency={expense.data.currency}
            />
            <p>{t("Pagato da")}{" "}<strong><Person userId={expense.data.paid_by_user_id} name={name(expense.data.paid_by_user_id)} small /></strong>
            </p>
            <span>{dateLabel(expense.data.expense_date)}</span>
          </div>
          {expense.data.subscription_id && (
            <Link
              className="notice"
              to={"/subscriptions/" + expense.data.subscription_id}
            >{t("Spesa generata da un abbonamento. Apri il dettaglio →")}</Link>
          )}
          <Section title={t("Come è stata divisa")}>
            <div className="card">
              {expense.data.splits.map((split) => (
                <div key={split.user_id} className="list-row">

                  <div className="row-main">
                    <strong><Person userId={split.user_id} name={name(split.user_id)} small /></strong>
                    <span>{t("Quota della spesa")}</span>
                  </div>
                  <Money
                    value={split.amount_cents}
                    currency={expense.data!.currency}
                  />
                </div>
              ))}
            </div>
          </Section>
          {expense.data.notes && (
            <Section title={t("Note")}>
              <div className="card form-card">
                <p className="pre-line">{expense.data.notes}</p>
              </div>
            </Section>
          )}
          <ErrorBox error={action.error} />
          {expense.data.source !== "SPLITWISE" ? (
            <div className="form-footer">
              <Link
                className="btn btn-secondary"
                to={"/expenses/" + id + "/edit"}
              >
                <Pencil size={16} />{" "}{t("Modifica")}</Link>
              <Button
                variant="danger"
                disabled={action.isPending}
                onClick={async () => {
                  if (
                    confirm(
                      t("Eliminare questa spesa? I saldi saranno ricalcolati."),
                    )
                  ) {
                    try {
                      await action.mutateAsync(undefined);
                      navigate(
                        "/groups/" + expense.data!.group_id + "?tab=expenses",
                      );
                    } catch {
                      /* rendered */
                    }
                  }
                }}
              >
                <Trash2 size={17} />{" "}{t("Elimina")}</Button>
            </div>
          ) : (
            <div className="notice">
              <Archive size={18} />{" "}{t("Lo storico importato è protetto. Puoi annullare l’intero import dalla gestione importazioni.")}</div>
          )}
        </>
      )}
    </State>
  );
}
export function LegacyDetail() {
  useLanguage();
  const { id } = useParams();
  const query = useApi<Legacy>("/legacy/" + id);
  const { users } = useData();
  return (
    <State pending={query.isPending} error={query.error}>
      {query.data && (
        <>
          <PageHead
            eyebrow={t("STORICO SPLITWISE")}
            title={query.data.description}
            back={"/groups/" + query.data.group_id + "?tab=expenses"}
            description={dateLabel(query.data.date)}
          />
          <CategoryEditor value={query.data} path={"/legacy/" + id} />
          <div className="card detail-hero">
            <Archive size={28} />
            <Money
              value={query.data.cost_cents}
              currency={query.data.currency}
            />
            <p>{t("Movimento legacy importato")}</p>
          </div>
          <p className="notice">{t("Questa transazione conserva i saldi originali di Splitwise, anche quando non è possibile identificare un singolo pagante.")}</p>
          <Section title={t("Effetto sui saldi")}>
            <div className="card">
              {query.data.entries.map((entry) => (
                <div key={entry.user_id} className="list-row">
                  <div className="row-main">
                    <strong>
                      <Person userId={entry.user_id} />
                    </strong>
                    <span>
                      {entry.balance_delta_cents > 0
                        ? t("Credito")
                        : entry.balance_delta_cents < 0
                          ? t("Debito")
                          : t("In pari")}
                    </span>
                  </div>
                  <Money
                    value={entry.balance_delta_cents}
                    currency={query.data!.currency}
                    signed
                  />
                </div>
              ))}
            </div>
          </Section>
        </>
      )}
    </State>
  );
}
