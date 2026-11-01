import { useUnsavedChanges } from "../components/UnsavedChanges";
import { Person } from "../components/Person";
import { CategoryPicker } from "../components/Categories";
import type { Category, CategoryMetadata } from "../api/types";
import { useState, useEffect, type FormEvent } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { CalendarDays, Check, Users, Coins } from "lucide-react";
import { useApi, useAction, send } from "../api/client";
import type { Expense, Subscription, Member, SplitMode } from "../api/types";
import { useData, useSession } from "../components/context";
import {
  PageHead,
  ErrorBox,
  State,
  Button,
  Busy,
  Money,
} from "../components/ui";
import {
  cents,
  decimal,
  money,
  splitAmounts,
  today,
  validCurrency,
} from "../utils/money";
export function ExpenseForm() {
  const { id } = useParams();
  const query = useApi<Expense>("/expenses/" + id, !!id);
  return id ? (
    <State pending={query.isPending} error={query.error}>
      {query.data && <Composer key={query.data.id} expense={query.data} />}
    </State>
  ) : (
    <Composer />
  );
}
export function SubscriptionForm() {
  const { id } = useParams();
  const query = useApi<Subscription>("/subscriptions/" + id, !!id);
  return id ? (
    <State pending={query.isPending} error={query.error}>
      {query.data && (
        <Composer key={query.data.id} subscription={query.data} recurring />
      )}
    </State>
  ) : (
    <Composer recurring />
  );
}
function Composer({
  expense,
  subscription,
  recurring = false,
}: {
  expense?: Expense;
  subscription?: Subscription;
  recurring?: boolean;
}) {
  const existing = expense ?? subscription;
  const unsaved = useUnsavedChanges();
  const [category, setCategory] = useState<CategoryMetadata>({ category_id: existing?.category_id ?? null });
  const categories = useApi<Category[]>("/categories");
  const transferCategory = categories.data?.find(c => c.id === category.category_id)?.slug === "transfers";
  const navigate = useNavigate();
  const [search] = useSearchParams();
  const { groups } = useData();
  const { session } = useSession();
  const [groupId, setGroup] = useState(
    existing?.group_id ?? Number(search.get("group_id")) ?? 0,
  );
  const [description, setDescription] = useState(
    expense?.description ?? subscription?.name ?? "",
  );
  const [amount, setAmount] = useState(
    existing ? decimal(existing.amount_cents) : "",
  );
  const [currency, setCurrency] = useState(existing?.currency ?? "EUR");
  const [payer, setPayer] = useState(
    existing?.paid_by_user_id ?? session.user.id,
  );
  const [date, setDate] = useState(
    expense?.expense_date ?? subscription?.start_date ?? today(),
  );
  const [notes, setNotes] = useState(
    expense?.notes ?? subscription?.description ?? "",
  );
  const [endDate, setEndDate] = useState(subscription?.end_date ?? "");
  const [frequency, setFrequency] = useState(
    subscription?.recurrence_rule.match(/FREQ=(\w+)/)?.[1] ?? "MONTHLY",
  );
  const [interval, setInterval] = useState(
    subscription?.recurrence_rule.match(/INTERVAL=(\d+)/)?.[1] ?? "1",
  );
  const [mode, setMode] = useState<SplitMode>(existing ? "exact" : "equal");
  const [participants, setParticipants] = useState<number[]>(
    existing?.splits.map((s) => s.user_id) ?? [],
  );
  const [values, setValues] = useState<Record<number, string>>(
    Object.fromEntries(
      existing?.splits.map((s) => [s.user_id, decimal(s.amount_cents)]) ?? [],
    ),
  );
  const [error, setError] = useState("");
  const members = useApi<Member[]>(
    "/groups/" + groupId + "/members",
    !!groupId,
  );
  const active = members.data?.filter((m) => m.active) ?? [];
  useEffect(() => {
    if (!groupId && groups.length)
      setGroup(groups.find((g) => !g.archived)?.id ?? 0);
  }, [groups, groupId]);
  useEffect(() => {
    if (members.data && !existing) {
      setParticipants(
        members.data.filter((m) => m.active).map((m) => m.user_id),
      );
      if (!members.data.some((m) => m.user_id === payer && m.active))
        setPayer(members.data.find((m) => m.active)?.user_id ?? 0);
    }
  }, [members.data, existing]);
  const action = useAction(async (body: unknown) =>
    send(
      "/" +
        (recurring ? "subscriptions" : "expenses") +
        (existing ? "/" + existing.id : ""),
      existing ? "PATCH" : "POST",
      body,
    ),
  );
  let parsed = 0;
  let preview: ReturnType<typeof splitAmounts> = [];
  let validation = "";
  try {
    parsed = cents(amount || "0");
    preview = splitAmounts(parsed, mode, participants, values);
    if (!parsed) validation = "Inserisci un importo maggiore di zero.";
    if (!validCurrency(currency))
      validation = "Inserisci un codice valuta valido, per esempio EUR.";
  } catch (e) {
    validation = (e as Error).message;
  }
  const exactAssigned =
    mode === "exact"
      ? participants.reduce((sum, id) => {
          try {
            return sum + cents(values[id] ?? "0");
          } catch {
            return sum;
          }
        }, 0)
      : preview.reduce((sum, s) => sum + s.amount_cents, 0);
  const toggle = (id: number) =>
    setParticipants(
      mode === "single"
        ? [id]
        : participants.includes(id)
          ? participants.filter((p) => p !== id)
          : [...participants, id],
    );
  const changeMode = (next: SplitMode) => {
    setMode(next);
    if (next === "single")
      setParticipants([participants[0] ?? active[0]?.user_id].filter(Boolean));
    if (next === "percent")
      setValues(
        Object.fromEntries(
          participants.map((id, index) => [
            id,
            decimal(
              Math.trunc(10000 / participants.length) +
                (index === 0 ? 10000 % participants.length : 0),
            ),
          ]),
        ),
      );
    if (next === "exact" && preview.length)
      setValues(
        Object.fromEntries(
          preview.map((s) => [s.user_id, decimal(s.amount_cents)]),
        ),
      );
  };
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    if (validation) {
      setError(validation);
      return;
    }
    if (!groupId || !payer || !description.trim()) {
      setError("Completa gruppo, descrizione e pagante.");
      return;
    }
    if (recurring && (!/^\d+$/.test(interval) || Number(interval) < 1)) {
      setError("La frequenza deve essere un numero intero positivo.");
      return;
    }
    const splits = participants.map((id) =>
      mode === "exact"
        ? { user_id: id, amount_cents: cents(values[id] ?? "0") }
        : mode === "percent"
          ? { user_id: id, percentage: (values[id] ?? "0").replace(",", ".") }
          : { user_id: id },
    );
    const common = {
      ...category,
      group_id: groupId,
      amount_cents: parsed,
      currency,
      paid_by_user_id: payer,
      split_mode: mode,
      splits,
    };
    const body = recurring
      ? {
          ...common,
          name: description.trim(),
          description: notes,
          recurrence_rule: `FREQ=${frequency};INTERVAL=${interval}`,
          start_date: date,
          end_date: endDate || null,
        }
      : {
          ...common,
          description: description.trim(),
          expense_date: date,
          notes,
        };
    try {
      await action.mutateAsync(body);
      unsaved.markSaved();
      navigate(
        existing
          ? "/" + (recurring ? "subscriptions" : "expenses") + "/" + existing.id
          : recurring
            ? "/subscriptions"
            : groupId
              ? "/groups/" + groupId
              : "/",
      );
    } catch {
      /* error rendered */
    }
  };
  if (expense?.source === "SPLITWISE")
    return (
      <div>
        <PageHead title="Spesa importata" back={"/expenses/" + expense.id} />
        <p className="notice">
          Lo storico importato è conservato per garantire l’integrità del
          rollback.
        </p>
      </div>
    );
  return (
    <>
      <PageHead
        eyebrow={
          recurring
            ? "UNA COSA IN MENO A CUI PENSARE"
            : "CONDIVIDI, SENZA PENSIERI"
        }
        title={
          existing
            ? "Modifica " + (recurring ? "abbonamento" : "spesa")
            : recurring
              ? "Nuovo abbonamento"
              : "Nuova spesa"
        }
        back={
          existing
            ? "/" +
              (recurring ? "subscriptions" : "expenses") +
              "/" +
              existing.id
            : "/"
        }
        description={
          recurring
            ? "Le scadenze diventano spese, automaticamente. Una data iniziale passata genera subito i rinnovi trascorsi."
            : "Un piccolo gesto, tutti i conti in ordine."
        }
      />
      {unsaved.dialog}
      <form className="composer" onSubmit={submit} onChangeCapture={unsaved.markDirty} onClickCapture={event => { const target = event.target as HTMLElement; if (target.closest(".split-modes button")) unsaved.markDirty(); }}>
        <div className="card amount-card">
          <label htmlFor="amount">
            {recurring ? "Importo a ogni scadenza" : "Quanto avete speso?"}
          </label>
          <div className="amount-input">
            <input
              id="amount"
              inputMode="decimal"
              placeholder="0,00"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              required
              autoFocus
            />
            <span>{currency === "EUR" ? "€" : currency}</span>
          </div>
          <div className="two-fields">
            <label>
              Gruppo
              <select
                disabled={!!existing}
                value={groupId}
                onChange={(e) => {
                  setGroup(Number(e.target.value));
                  setParticipants([]);
                }}
                required
              >
                <option value="">Scegli un gruppo</option>
                {groups
                  .filter((g) => !g.archived || g.id === groupId)
                  .map((g) => (
                    <option key={g.id} value={g.id}>
                      {g.name}
                    </option>
                  ))}
              </select>
            </label>
            <label>
              Valuta
              <input
                value={currency}
                maxLength={3}
                pattern="[A-Z]{3}"
                onChange={(e) => setCurrency(e.target.value.toUpperCase())}
                required
              />
            </label>
          </div>
        </div>
        <div className="card form-card">
          <CategoryPicker value={category} onChange={setCategory} />
          {!recurring && transferCategory && <div className="notice">
            <p>La categoria non registra un pareggio. Se stai restituendo soldi a una persona, usa un pareggio parziale o totale: una spesa attribuita soltanto a chi paga non cambia il saldo.</p>
            {!!groupId && <Link to={"/groups/" + groupId + "?tab=balances"}>Vai ai pareggi del gruppo</Link>}
            {existing && <p>Questo collegamento non modifica la spesa già salvata.</p>}
          </div>}
          <label>
            {recurring ? "Nome abbonamento" : "Descrizione"}
            <input
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder={
                recurring
                  ? "Netflix, fibra, affitto…"
                  : "Spesa al supermercato, cena…"
              }
              maxLength={200}
              required
            />
          </label>
          <label>
            Chi ha pagato?
            <select
              value={payer}
              onChange={(e) => setPayer(Number(e.target.value))}
              required
            >
              <option value="">Scegli una persona</option>
              {active.map((m) => (
                <option key={m.user_id} value={m.user_id}>
                  {m.display_name}
                  {m.user_id === session.user.id ? " (tu)" : ""}
                </option>
              ))}
            </select>
          </label>
          <ErrorBox error={members.error} />
          {recurring && (
            <>
              <div className="two-fields">
                <label>
                  Ogni
                  <input
                    type="number"
                    min="1"
                    max="1000"
                    value={interval}
                    onChange={(e) => setInterval(e.target.value)}
                    required
                  />
                </label>
                <label>
                  Periodo
                  <select
                    value={frequency}
                    onChange={(e) => setFrequency(e.target.value)}
                  >
                    <option value="WEEKLY">Settimana/e</option>
                    <option value="MONTHLY">Mese/i</option>
                    <option value="YEARLY">Anno/i</option>
                  </select>
                </label>
              </div>
              <div className="two-fields">
                <label>
                  Prima scadenza
                  <input
                    type="date"
                    value={date}
                    onChange={(e) => setDate(e.target.value)}
                    required
                  />
                </label>
                <label>
                  Ultima scadenza (facoltativa)
                  <input
                    type="date"
                    min={date}
                    value={endDate}
                    onChange={(e) => setEndDate(e.target.value)}
                  />
                </label>
              </div>
            </>
          )}
        </div>
        <div className="card form-card">
          <h2>
            <Users size={20} /> Come dividiamo?
          </h2>
          <div className="segmented split-modes">
            {(["equal", "exact", "percent", "single"] as SplitMode[]).map(
              (m, i) => (
                <button
                  key={m}
                  type="button"
                  className={mode === m ? "selected" : ""}
                  onClick={() => changeMode(m)}
                >
                  {["Uguale", "Importi", "%", "Una persona"][i]}
                </button>
              ),
            )}
          </div>
          {active.map((member) => (
            <div className="split-row" key={member.user_id}>
              <label className="person-check">
                <input
                  type={mode === "single" ? "radio" : "checkbox"}
                  name={mode === "single" ? "participant" : undefined}
                  checked={participants.includes(member.user_id)}
                  onChange={() => toggle(member.user_id)}
                />
                <Person userId={member.user_id} name={member.display_name} small forceName />
              </label>
              {participants.includes(member.user_id) &&
              (mode === "exact" || mode === "percent") ? (
                <div className="split-input-block">
                  <div className="split-input">
                    <input
                      aria-label={"Quota di " + member.display_name}
                      inputMode="decimal"
                      placeholder="0"
                      value={values[member.user_id] ?? ""}
                      onChange={(e) =>
                        setValues({
                          ...values,
                          [member.user_id]: e.target.value,
                        })
                      }
                    />
                    <span>
                      {mode === "percent"
                        ? "%"
                        : currency === "EUR"
                          ? "€"
                          : currency}
                    </span>
                  </div>
                  {mode === "percent" && (
                    <small className="split-share-preview">
                      {money(
                        preview.find((s) => s.user_id === member.user_id)
                          ?.amount_cents ?? 0,
                        currency,
                      )}
                    </small>
                  )}
                </div>
              ) : (
                <Money
                  value={
                    preview.find((s) => s.user_id === member.user_id)
                      ?.amount_cents ?? 0
                  }
                  currency={currency}
                />
              )}
            </div>
          ))}
          {!active.length && (
            <p className="muted">Scegli un gruppo per vedere i partecipanti.</p>
          )}
          <div className={"split-summary " + (!validation ? "valid" : "")}>
            <Coins size={18} />
            <div>
              <strong>
                {!validation ? "Tutto torna" : "Controlla la suddivisione"}
              </strong>
              <span>
                Assegnato {money(exactAssigned, currency)} · Rimanente{" "}
                {money(parsed - exactAssigned, currency)}
              </span>
              {mode === "percent" && (
                <small>Le percentuali devono sommare 100%.</small>
              )}
            </div>
            {!validation && <Check size={20} />}
          </div>
          {validation && parsed > 0 && (
            <p className="field-error">{validation}</p>
          )}
        </div>
        <details className="card options">
          <summary>
            <CalendarDays size={18} /> Altre opzioni
          </summary>
          <div className="form-card">
            {!recurring && (
              <label>
                Data della spesa
                <input
                  type="date"
                  value={date}
                  onChange={(e) => setDate(e.target.value)}
                  required
                />
              </label>
            )}
            <label>
              {recurring ? "Descrizione (facoltativa)" : "Note (facoltative)"}
              <textarea
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                rows={3}
              />
            </label>
          </div>
        </details>
        <ErrorBox error={error || action.error} />
        <div className="form-footer">
          <Button
            variant="secondary"
            type="button"
            onClick={() => navigate(-1)}
          >
            Annulla
          </Button>
          <Busy
            busy={action.isPending}
            label={
              existing
                ? "Salva modifiche"
                : recurring
                  ? "Crea abbonamento"
                  : "Aggiungi spesa"
            }
          />
        </div>
      </form>
    </>
  );
}
