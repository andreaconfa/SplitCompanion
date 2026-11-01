import { Person } from "../components/Person";
import { CategoryBadge } from "../components/Categories";
import { useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";
import {
  Pause,
  Play,
  Pencil,
  ArrowUpRight,
  ArrowDownLeft,
  RefreshCw,
  Trash2,
} from "lucide-react";
import { useApi, useAction, send, params } from "../api/client";
import type { Subscription, Credit, Expense, Settlement } from "../api/types";
import { useData, useSession } from "../components/context";
import {
  PageHead,
  State,
  Empty,
  SubscriptionRow,
  AddLink,
  Section,
  Money,
  Button,
  ErrorBox,
  ExpenseRow,
  Sheet,
  Busy,
} from "../components/ui";
import {
  cents,
  decimal,
  dateLabel,
  recurrenceLabel,
  today,
} from "../utils/money";
export default function Subscriptions() {
  const { groups, users } = useData();
  const { session } = useSession();
  const [group, setGroup] = useState("");
  const [showPaused, setShowPaused] = useState(true);
  const subs = useApi<Subscription[]>(
    "/subscriptions" + params({ group_id: group }),
  );
  const run = useAction(async () => send("/subscriptions/run", "POST"));
  return (
    <>
      <PageHead
        eyebrow="LA ROUTINE, SENZA PENSIERI"
        title="Abbonamenti"
        description="Un’unica casa per le spese che si ripetono."
        action={<AddLink to="/subscriptions/new" label="Nuovo" />}
      />
      <div className="card form-card">
        <label>
          Gruppo
          <select value={group} onChange={(e) => setGroup(e.target.value)}>
            <option value="">Tutti i gruppi</option>
            {groups.map((g) => (
              <option key={g.id} value={g.id}>
                {g.name}
              </option>
            ))}
          </select>
        </label>
        <label className="checkbox-line">
          <input
            type="checkbox"
            checked={showPaused}
            onChange={(e) => setShowPaused(e.target.checked)}
          />{" "}
          Includi abbonamenti in pausa / terminati
        </label>
      </div>
      <Section title="Le vostre ricorrenze">
        <State pending={subs.isPending} error={subs.error}>
          <div className="card">
            {subs.data?.filter((s) => showPaused || s.active).length ? (
              subs.data
                .filter((s) => showPaused || s.active)
                .map((sub) => (
                  <SubscriptionRow
                    key={sub.id}
                    subscription={sub}
                    users={users}
                  />
                ))
            ) : (
              <Empty
                title="Una cosa in meno da ricordare"
                detail="Crea il primo abbonamento condiviso."
                action={
                  <AddLink to="/subscriptions/new" label="Crea abbonamento" />
                }
              />
            )}
          </div>
        </State>
      </Section>
      {session.user.is_admin && (
        <div className="card form-card">
          <h3>Controlla le scadenze</h3>
          <p className="muted">
            Le scadenze vengono generate automaticamente. Puoi avviare ora il
            recupero di eventuali rinnovi mancanti.
          </p>
          <Button
            variant="secondary"
            disabled={run.isPending}
            onClick={() => run.mutate(undefined)}
          >
            <RefreshCw size={16} /> Genera scadenze dovute
          </Button>
          {run.isSuccess && (
            <p className="success-text" role="status">
              Scadenze controllate. I conti sono aggiornati.
            </p>
          )}
          <ErrorBox error={run.error} />
        </div>
      )}
    </>
  );
}
export function SubscriptionDetail() {
  const { id } = useParams();
  const { users } = useData();
  const sub = useApi<Subscription>("/subscriptions/" + id);
  const credits = useApi<Credit[]>("/subscriptions/" + id + "/credits");
  const expenses = useApi<Expense[]>("/expenses?subscription_id=" + id);
  const advances = useApi<Settlement[]>("/subscriptions/" + id + "/advances");
  const [transfer, setTransfer] = useState<{
    kind: "advances" | "refunds";
    userId?: number;
  } | null>(null);
  const action = useAction(
    async ({ method, suffix }: { method: string; suffix: string }) =>
      send("/subscriptions/" + id + suffix, method),
  );
  const name = (uid: number) =>
    users.find((u) => u.id === uid)?.display_name ?? "Utente";
  return (
    <State pending={sub.isPending} error={sub.error}>
      {sub.data && (
        <>
          <PageHead
            eyebrow={
              sub.data.deleted
                ? "ABBONAMENTO TERMINATO"
                : sub.data.active
                  ? "ABBONAMENTO ATTIVO"
                  : "ABBONAMENTO IN PAUSA"
            }
            title={sub.data.name}
            back="/subscriptions"
            description={sub.data.description}
          />
          <div className="card detail-hero">
            <CategoryBadge value={sub.data} label />
            <Money value={sub.data.amount_cents} currency={sub.data.currency} />
            <p>{recurrenceLabel(sub.data.recurrence_rule)}</p>
            <span>
              {sub.data.deleted
                ? "Terminato: lo storico e i crediti restano disponibili"
                : sub.data.active
                  ? "Prossimo: " + dateLabel(sub.data.next_occurrence_date)
                  : "La generazione delle scadenze è sospesa"}
            </span>
            <p>
              Pagato da <strong><Person userId={sub.data.paid_by_user_id} name={name(sub.data.paid_by_user_id)} small /></strong>
            </p>
            <small>
              Dal {dateLabel(sub.data.start_date)}
              {sub.data.end_date ? " al " + dateLabel(sub.data.end_date) : ""}
            </small>
          </div>
          {!sub.data.deleted && (
            <div className="form-footer">
              <Link
                className="btn btn-secondary"
                to={"/subscriptions/" + id + "/edit"}
              >
                <Pencil size={16} /> Modifica
              </Link>
              <Button
                variant="secondary"
                disabled={action.isPending}
                onClick={() =>
                  action.mutate({
                    method: "POST",
                    suffix: sub.data!.active ? "/pause" : "/resume",
                  })
                }
              >
                {sub.data.active ? <Pause size={17} /> : <Play size={17} />}{" "}
                {sub.data.active ? "Pausa" : "Riprendi"}
              </Button>
              <Button
                variant="danger"
                disabled={action.isPending}
                onClick={() => {
                  if (
                    confirm(
                      "Terminare questo abbonamento? Lo storico e i crediti rimarranno disponibili.",
                    )
                  )
                    action.mutate({ method: "DELETE", suffix: "" });
                }}
              >
                <Trash2 size={16} /> Termina
              </Button>
            </div>
          )}
          <ErrorBox error={action.error} />
          {!sub.data.active && !sub.data.deleted && (
            <p className="notice">
              Riprendendo un abbonamento in pausa vengono recuperate anche le
              scadenze trascorse. Se la data finale è passata, aggiornala prima
              di riprendere.
            </p>
          )}
          <Section title="Suddivisione a ogni scadenza">
            <div className="card">
              {sub.data.splits.map((split) => (
                <div className="list-row" key={split.user_id}>

                  <div className="row-main">
                    <strong><Person userId={split.user_id} name={name(split.user_id)} small /></strong>
                  </div>
                  <Money
                    value={split.amount_cents}
                    currency={sub.data!.currency}
                  />
                </div>
              ))}
            </div>
          </Section>
          <Section
            title="Anticipi e credito"
            action={
              !sub.data.deleted && (
                <Button onClick={() => setTransfer({ kind: "advances" })}>
                  <ArrowUpRight size={16} /> Anticipo
                </Button>
              )
            }
          >
            <State pending={credits.isPending} error={credits.error}>
              {credits.data?.length ? (
                credits.data.map((credit) => (
                  <div className="card credit-card" key={credit.user_id}>
                    <div className="heading-row">
                      <div className="person-heading">

                        <h3><Person userId={credit.user_id} name={name(credit.user_id)} small /></h3>
                      </div>
                      <span className="pill">Credito</span>
                    </div>
                    <div className="credit-numbers">
                      <div>
                        <span>Anticipato</span>
                        <Money
                          value={credit.advanced_cents}
                          currency={sub.data!.currency}
                        />
                      </div>
                      <div>
                        <span>Utilizzato</span>
                        <Money
                          value={credit.used_cents}
                          currency={sub.data!.currency}
                        />
                      </div>
                      <div>
                        <span>Rimborsato</span>
                        <Money
                          value={credit.refunded_cents}
                          currency={sub.data!.currency}
                        />
                      </div>
                    </div>
                    <div className="credit-remaining">
                      <span>Credito residuo</span>
                      <Money
                        value={credit.remaining_cents}
                        currency={sub.data!.currency}
                      />
                    </div>
                    <div className="form-footer">
                      <Button
                        variant="secondary"
                        disabled={sub.data!.deleted}
                        onClick={() =>
                          setTransfer({
                            kind: "advances",
                            userId: credit.user_id,
                          })
                        }
                      >
                        Aggiungi anticipo
                      </Button>
                      <Button
                        variant="secondary"
                        disabled={credit.remaining_cents <= 0}
                        onClick={() =>
                          setTransfer({
                            kind: "refunds",
                            userId: credit.user_id,
                          })
                        }
                      >
                        <ArrowDownLeft size={16} /> Rimborso
                      </Button>
                    </div>
                    {credit.history.length > 0 && (
                      <details className="history-details">
                        <summary>Storico del credito</summary>
                        {credit.history.map((entry, index) => (
                          <div className="history-row" key={index}>
                            <div>
                              <strong>
                                {entry.kind.includes("REFUND")
                                  ? "Rimborso"
                                  : entry.kind.includes("ADVANCE")
                                    ? "Anticipo"
                                    : "Credito utilizzato"}
                              </strong>
                              <span>{dateLabel(entry.date)}</span>
                              {entry.expense_id && (
                                <Link
                                  className="text-link"
                                  to={"/expenses/" + entry.expense_id}
                                >
                                  Apri spesa
                                </Link>
                              )}
                            </div>
                            <Money
                              value={entry.amount_cents}
                              currency={sub.data!.currency}
                            />
                          </div>
                        ))}
                      </details>
                    )}
                  </div>
                ))
              ) : (
                <div className="card">
                  <Empty
                    title="Nessun anticipo registrato"
                    detail="Un contributo oggi, meno pensieri ai prossimi rinnovi."
                  />
                </div>
              )}
            </State>
          </Section>
          <Section title="Spese generate">
            <State pending={expenses.isPending} error={expenses.error}>
              <div className="card">
                {expenses.data?.length ? (
                  expenses.data.map((expense) => (
                    <ExpenseRow
                      key={expense.id}
                      expense={expense}
                      users={users}
                    />
                  ))
                ) : (
                  <Empty
                    title="Il prossimo rinnovo ti aspetta"
                    detail="Le spese vengono create alla data della scadenza."
                  />
                )}
              </div>
            </State>
          </Section>
          <Section title="Trasferimenti anticipati">
            <State pending={advances.isPending} error={advances.error}>
              <div className="card">
                {advances.data?.length ? (
                  advances.data.map((item) => (
                    <div className="list-row" key={item.id}>
                      <div className="row-main">
                        <strong>
                          <Person userId={item.paid_by_user_id} name={name(item.paid_by_user_id)} small /> →{" "}
                          <Person userId={item.paid_to_user_id} name={name(item.paid_to_user_id)} small />
                        </strong>
                        <span>
                          {dateLabel(item.settlement_date)} ·{" "}
                          {item.kind === "SUBSCRIPTION_REFUND"
                            ? "Rimborso"
                            : "Anticipo"}
                        </span>
                        {item.notes && <small>{item.notes}</small>}
                      </div>
                      <Money
                        value={item.amount_cents}
                        currency={item.currency}
                      />
                    </div>
                  ))
                ) : (
                  <Empty title="Nessun trasferimento" />
                )}
              </div>
            </State>
          </Section>
          {transfer && (
            <TransferForm
              subscription={sub.data}
              credits={credits.data ?? []}
              kind={transfer.kind}
              userId={transfer.userId}
              onClose={() => setTransfer(null)}
            />
          )}
        </>
      )}
    </State>
  );
}
function TransferForm({
  subscription,
  credits,
  kind,
  userId,
  onClose,
}: {
  subscription: Subscription;
  credits: Credit[];
  kind: "advances" | "refunds";
  userId?: number;
  onClose: () => void;
}) {
  const { users } = useData();
  const participantIds =
    kind === "refunds"
      ? Array.from(
          new Set([
            ...subscription.splits.map((s) => s.user_id),
            ...credits
              .filter((c) => c.remaining_cents > 0)
              .map((c) => c.user_id),
          ]),
        )
      : subscription.splits.map((s) => s.user_id);
  const participants = participantIds
    .filter((id) => id !== subscription.paid_by_user_id)
    .map((user_id) => ({ user_id }));
  const [person, setPerson] = useState(userId ?? participants[0]?.user_id ?? 0);
  const [amount, setAmount] = useState("");
  const [date, setDate] = useState(today());
  const [notes, setNotes] = useState("");
  const [error, setError] = useState("");
  const refund = kind === "refunds";
  const remaining =
    credits.find((c) => c.user_id === person)?.remaining_cents ?? 0;
  const action = useAction(async (body: unknown) =>
    send("/subscriptions/" + subscription.id + "/" + kind, "POST", body),
  );
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    try {
      const parsed = cents(amount);
      if (!person || parsed <= 0)
        throw new Error(
          "Scegli un partecipante e un importo maggiore di zero.",
        );
      if (refund && parsed > remaining)
        throw new Error("Il rimborso non può superare il credito residuo.");
      setError("");
      await action.mutateAsync({
        user_id: person,
        amount_cents: parsed,
        settlement_date: date,
        notes,
      });
      onClose();
    } catch (e) {
      setError((e as Error).message);
    }
  };
  return (
    <Sheet
      title={refund ? "Registra un rimborso" : "Aggiungi un anticipo"}
      onClose={onClose}
    >
      <form className="form-card" onSubmit={submit}>
        <p className="notice">
          {refund
            ? "Il pagante restituisce parte del credito non utilizzato."
            : "Registra il denaro già versato al pagante. Il credito verrà utilizzato sulle prossime quote."}
        </p>
        <label>
          {refund ? "Chi riceve il rimborso?" : "Chi ha anticipato?"}
          <select
            value={person}
            onChange={(e) => setPerson(Number(e.target.value))}
            required
          >
            <option value="">Scegli una persona</option>
            {participants.map((p) => (
              <option key={p.user_id} value={p.user_id}>
                {users.find((u) => u.id === p.user_id)?.display_name ?? "Utente"}
              </option>
            ))}
          </select>
        </label>
        {refund && (
          <div className="split-summary">
            <span>Credito disponibile</span>
            <Money value={remaining} currency={subscription.currency} />
            <button
              type="button"
              className="text-link"
              onClick={() => setAmount(decimal(remaining))}
            >
              Tutto
            </button>
          </div>
        )}
        <label>
          Importo ({subscription.currency})
          <input
            inputMode="decimal"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            required
          />
        </label>
        <label>
          Data del trasferimento
          <input
            type="date"
            value={date}
            onChange={(e) => setDate(e.target.value)}
            required
          />
        </label>
        <label>
          Note
          <textarea
            rows={2}
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
          />
        </label>
        <ErrorBox error={error || action.error} />
        <Busy
          busy={action.isPending}
          label={refund ? "Registra rimborso" : "Registra anticipo"}
        />
      </form>
    </Sheet>
  );
}
