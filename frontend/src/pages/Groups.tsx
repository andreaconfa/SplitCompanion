import { Person } from "../components/Person";
import { useState, type FormEvent } from "react";
import {
  Link,
  useNavigate,
  useParams,
  useSearchParams,
} from "react-router-dom";
import {
  House,
  ChevronRight,
  Archive,
  Plus,
  Users,
  Check,
  ArrowRight,
  Pencil,
  Trash2,
} from "lucide-react";
import { useApi, useAction, send } from "../api/client";
import type {
  Group,
  Member,
  Expense,
  Subscription,
  Balance,
  Debt,
  Settlement,
  Legacy,
} from "../api/types";
import { useData, useSession } from "../components/context";
import {
  PageHead,
  Section,
  State,
  Empty,
  ErrorBox,
  Money,
  AddLink,
  Sheet,
  Button,
  Busy,
  ExpenseRow,
  LegacyRow,
  SubscriptionRow,
} from "../components/ui";
import { cents, dateLabel, decimal, today, money } from "../utils/money";
export default function Groups() {
  const { groups } = useData();
  const [search, setSearch] = useSearchParams();
  const show = search.get("new") === "1";
  const setShow = (visible: boolean) => setSearch(current => { const next = new URLSearchParams(current); if (visible) next.set("new", "1"); else next.delete("new"); return next; });
  const [archived, setArchived] = useState(false);
  return (
    <>
      <PageHead
                title="Gruppi"
        description="Casa, viaggi e piccoli progetti insieme."
        action={
          <Button onClick={() => setShow(true)}>
            <Plus size={18} /> Nuovo gruppo
          </Button>
        }
      />
      <label className="checkbox-line">
        <input
          type="checkbox"
          checked={archived}
          onChange={(e) => setArchived(e.target.checked)}
        />{" "}
        Mostra anche i gruppi archiviati
      </label>
      <div className="group-grid">
        {groups
          .filter((g) => archived || !g.archived)
          .map((group, index) => (
            <GroupCard group={group} key={group.id} color={index % 3} />
          ))}
        {!groups.length && (
          <Empty
            title="Ogni gruppo è un piccolo mondo"
            detail="Crea il primo per iniziare a condividere le spese."
            action={
              <Button onClick={() => setShow(true)}>Crea un gruppo</Button>
            }
          />
        )}
      </div>
      {show && <GroupForm onClose={() => setShow(false)} />}
    </>
  );
}
function GroupCard({ group, color }: { group: Group; color: number }) {
  const balances = useApi<Balance[]>("/groups/" + group.id + "/balances");
  const members = useApi<Member[]>("/groups/" + group.id + "/members");
  const { session } = useSession();
  return (
    <Link className={"group-card tone-" + color} to={"/groups/" + group.id}>
      <div className="group-cover">
        <House size={30} />
        <span>{group.archived ? "Archiviato" : "Il nostro spazio"}</span>
      </div>
      <div className="group-card-body">
        <div className="heading-row">
          <h2>{group.name}</h2>
          <ChevronRight size={20} />
        </div>
        <p>{members.data?.filter((m) => m.active).length ?? "…"} membri</p>
        <ErrorBox error={balances.error || members.error} />
        <div className="group-bottom">
          <span>Il tuo saldo</span>
          <div>
            {balances.data
              ?.filter((b) => b.user_id === session.user.id)
              .map((balance) => (
                <Money
                  key={balance.currency}
                  value={balance.balance_cents}
                  currency={balance.currency}
                  signed
                />
              ))}
          </div>
        </div>
      </div>
    </Link>
  );
}
function GroupForm({ group, onClose }: { group?: Group; onClose: () => void }) {
  const { users } = useData();
  const { session } = useSession();
  const navigate = useNavigate();
  const [name, setName] = useState(group?.name ?? "");
  const [description, setDescription] = useState(group?.description ?? "");
  const [memberIds, setMembers] = useState([session.user.id]);
  const action = useAction(async (body: unknown) =>
    send(
      "/groups" + (group ? "/" + group.id : ""),
      group ? "PATCH" : "POST",
      body,
    ),
  );
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    const result = (await action.mutateAsync(
      group
        ? { name: name.trim(), description }
        : { name: name.trim(), description, member_ids: memberIds },
    )) as Group;
    onClose();
    if (!group) navigate("/groups/" + result.id);
  };
  return (
    <Sheet
      title={group ? "Modifica gruppo" : "Un nuovo gruppo"}
      onClose={onClose}
    >
      <form
        onSubmit={(e) => {
          submit(e).catch(() => {});
        }}
        className="form-card"
      >
        <label>
          Nome
          <input
            value={name}
            required
            maxLength={100}
            placeholder="Casa, vacanza, weekend…"
            onChange={(e) => setName(e.target.value)}
          />
        </label>
        <label>
          Descrizione (facoltativa)
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={2}
          />
        </label>
        {!group && (
          <fieldset>
            <legend>Chi c’è nel gruppo?</legend>
            {users
              .filter((u) => u.is_active)
              .map((u) => (
                <label className="checkbox-line" key={u.id}>
                  <input
                    type="checkbox"
                    aria-label={u.display_name}
                    checked={memberIds.includes(u.id)}
                    disabled={u.id === session.user.id}
                    onChange={() =>
                      setMembers(
                        memberIds.includes(u.id)
                          ? memberIds.filter((id) => id !== u.id)
                          : [...memberIds, u.id],
                      )
                    }
                  />
                  <Person user={u} small forceName />
                </label>
              ))}
          </fieldset>
        )}
        <ErrorBox error={action.error} />
        <Busy
          busy={action.isPending}
          label={group ? "Salva gruppo" : "Crea gruppo"}
        />
      </form>
    </Sheet>
  );
}
export function GroupDetail() {
  const { id } = useParams();
  const gid = Number(id);
  const [search, setSearch] = useSearchParams();
  const tab = search.get("tab") ?? "overview";
  const group = useApi<Group>("/groups/" + id);
  const members = useApi<Member[]>("/groups/" + id + "/members");
  const expenses = useApi<Expense[]>("/expenses?group_id=" + id);
  const subscriptions = useApi<Subscription[]>("/subscriptions?group_id=" + id);
  const balances = useApi<Balance[]>("/groups/" + id + "/balances");
  const debts = useApi<Debt[]>("/groups/" + id + "/debts");
  const settlements = useApi<Settlement[]>("/settlements?group_id=" + id);
  const legacy = useApi<Legacy[]>("/legacy?group_id=" + id);
  const history = [
    ...(expenses.data ?? []).map(record => ({ kind: "expense" as const, record, date: record.expense_date })),
    ...(legacy.data ?? []).map(record => ({ kind: "legacy" as const, record, date: record.date })),
  ].sort((a, b) => b.date.localeCompare(a.date) || b.record.id - a.record.id);

  const { users } = useData();
  const { session } = useSession();
  const [edit, setEdit] = useState(false);
  const [payment, setPayment] = useState<Debt | null | false>(false);
  const [newMember, setNewMember] = useState("");
  const action = useAction(
    async ({
      path,
      method,
      body,
    }: {
      path: string;
      method: string;
      body?: unknown;
    }) => send(path, method, body),
  );
  const names = (userId: number) =>
    users.find((u) => u.id === userId)?.display_name ??
    members.data?.find((m) => m.user_id === userId)?.display_name ??
    "Utente";
  const active = members.data?.filter((m) => m.active) ?? [];
  const payments = (
    <div className="card">
      {settlements.data?.length ? (
        settlements.data.map((p) => (
          <div className="list-row" key={p.id}>
            <span className="row-icon">
              <ArrowRight size={18} />
            </span>
            <div className="row-main">
              <strong>
                <Person userId={p.paid_by_user_id} name={names(p.paid_by_user_id)} small /> → <Person userId={p.paid_to_user_id} name={names(p.paid_to_user_id)} small />
              </strong>
              <span>
                {dateLabel(p.settlement_date)} ·{" "}
                {p.kind === "GENERAL"
                  ? "Pagamento"
                  : p.kind === "SUBSCRIPTION_ADVANCE"
                    ? "Anticipo"
                    : "Rimborso"}
              </span>
              {p.notes && <small>{p.notes}</small>}
              {p.source === "SPLITWISE" && (
                <small>Importato da Splitwise</small>
              )}
            </div>
            <Money value={p.amount_cents} currency={p.currency} />
            {p.source !== "SPLITWISE" && (
              <button
                className="icon-button"
                title="Elimina pagamento"
                aria-label="Elimina pagamento"
                disabled={action.isPending}
                onClick={() => {
                  if (
                    confirm(
                      "Eliminare questo pagamento? Il saldo sarà ricalcolato.",
                    )
                  )
                    action.mutate({
                      path: "/settlements/" + p.id,
                      method: "DELETE",
                    });
                }}
              >
                <Trash2 size={17} />
              </button>
            )}
          </div>
        ))
      ) : (
        <Empty title="Nessun pagamento registrato" />
      )}
      <ErrorBox error={settlements.error} />
    </div>
  );
  return (
    <State pending={group.isPending} error={group.error}>
      {group.data && (
        <>
          <PageHead
            eyebrow={
              group.data.archived ? "GRUPPO ARCHIVIATO" : "IL VOSTRO SPAZIO"
            }
            title={group.data.name}
            description={
              group.data.description ||
              `${active.length} persone, una cosa in comune.`
            }
            back="/groups"
            action={
              <Button
                variant="secondary"
                onClick={() => setEdit(true)}
                aria-label="Modifica gruppo"
              >
                <Pencil size={18} />
              </Button>
            }
          />
          <div className="tabs">
            {[
              ["overview", "Panoramica"],
              ["expenses", "Spese"],
              ["subscriptions", "Abbonamenti"],
              ["balances", "Saldi"],
              ["members", "Membri"],
            ].map(([value, label]) => (
              <button
                key={value}
                className={tab === value ? "selected" : ""}
                onClick={() => setSearch({ tab: value })}
              >
                {label}
              </button>
            ))}
          </div>
          <ErrorBox error={action.error} />
          {(tab === "overview" || tab === "balances") && (
            <>
              <div className="card group-balance">
                <span>Il tuo saldo nel gruppo</span>
                <div>
                  {balances.data
                    ?.filter((b) => b.user_id === session.user.id)
                    .map((b) => (
                      <Money
                        key={b.currency}
                        value={b.balance_cents}
                        currency={b.currency}
                        signed
                      />
                    ))}
                </div>
                <ErrorBox error={balances.error} />
              </div>
              <Section
                title="Pareggi"
                action={
                  <Button variant="secondary" onClick={() => setPayment(debts.data?.find(d => d.paid_by_user_id === session.user.id || d.paid_to_user_id === session.user.id) ?? null)}>
                    <Plus size={16} /> Registra un pareggio
                  </Button>
                }
              >
                <State pending={debts.isPending} error={debts.error}>
                  <div className="card">
                    {debts.data?.length ? (
                      debts.data.map((debt, index) => (
                        <div className="list-row" key={index}>
                          <div className="row-main">
                            <strong>
                              <Person userId={debt.paid_by_user_id} name={names(debt.paid_by_user_id)} small /> →{" "}
                              <Person userId={debt.paid_to_user_id} name={names(debt.paid_to_user_id)} small />
                            </strong>
                            <span>Per tornare in pari</span>
                          </div>
                          <div className="row-end">
                            <Money
                              value={debt.amount_cents}
                              currency={debt.currency}
                            />
                            <button
                              className="text-link"
                              onClick={() => setPayment(debt)}
                            >
                              Pareggia <Check size={14} />
                            </button>
                          </div>
                        </div>
                      ))
                    ) : (
                      <Empty
                        title="Tutti in pari"
                        detail="Nessun pagamento da suggerire."
                      />
                    )}
                  </div>
                </State>
              </Section>
            </>
          )}
          {tab === "balances" && (
            <>
              <Section title="Saldi delle persone">
                <div className="card">
                  {balances.data?.map((b) => (
                    <div className="list-row" key={b.user_id + b.currency}>

                      <div className="row-main">
                        <strong><Person userId={b.user_id} name={names(b.user_id)} small /></strong>
                        <span>
                          {b.balance_cents > 0
                            ? "Deve ricevere"
                            : b.balance_cents < 0
                              ? "Deve pagare"
                              : "In pari"}
                        </span>
                      </div>
                      <Money
                        value={b.balance_cents}
                        currency={b.currency}
                        signed
                      />
                    </div>
                  ))}
                </div>
              </Section>
              <Section title="Pagamenti e trasferimenti">{payments}</Section>
            </>
          )}
          {(tab === "overview" || tab === "expenses") && (
            <>
              <Section
                title={tab === "overview" ? "Ultime spese" : "Spese del gruppo"}
                action={
                  <AddLink to={"/expenses/new?group_id=" + id} label="Spesa" />
                }
              >
                <State pending={expenses.isPending || legacy.isPending} error={expenses.error || legacy.error}>
                  <div className="card">
                    {history.length ? (
                      (tab === "overview" ? history.slice(0, 5) : history).map(entry =>
                        entry.kind === "legacy" ? (
                          <LegacyRow key={"legacy-" + entry.record.id} record={entry.record} />
                        ) : (
                          <ExpenseRow key={"expense-" + entry.record.id} expense={entry.record} users={users} />
                        )
                      )
                    ) : (
                      <Empty title="Nessuna spesa, per ora" detail="Aggiungi la prima spesa condivisa." />
                    )}
                  </div>
                </State>
                {tab === "overview" && history.length > 5 && (
                  <Link className="text-link" to={"/groups/" + id + "?tab=expenses"}>
                    Vedi tutte le {history.length} spese <ChevronRight size={16} />
                  </Link>
                )}
              </Section>
            </>
          )}
          {(tab === "overview" || tab === "subscriptions") && (
            <Section
              title="Abbonamenti"
              action={
                <AddLink
                  to={"/subscriptions/new?group_id=" + id}
                  label="Nuovo"
                />
              }
            >
              <State
                pending={subscriptions.isPending}
                error={subscriptions.error}
              >
                <div className="card">
                  {subscriptions.data?.length ? (
                    subscriptions.data.map((sub) => (
                      <SubscriptionRow
                        key={sub.id}
                        subscription={sub}
                        users={users}
                      />
                    ))
                  ) : (
                    <Empty
                      title="La routine, senza pensieri"
                      detail="Aggiungi affitto, servizi o abbonamenti condivisi."
                    />
                  )}
                </div>
              </State>
            </Section>
          )}
          {tab === "members" && (
            <>
              <Section title="Le persone">
                <State pending={members.isPending} error={members.error}>
                  <div className="card">
                    {members.data?.map((member) => (
                      <div className="list-row" key={member.user_id}>

                        <div className="row-main">
                          <strong><Person userId={member.user_id} name={member.display_name} /></strong>
                          <span>
                            @{member.username}
                            {!member.active ? " · Membro rimosso" : ""}
                          </span>
                        </div>
                        {member.active && (
                          <button
                            aria-label={"Rimuovi " + member.display_name}
                            className="icon-button"
                            disabled={action.isPending}
                            onClick={() => {
                              if (
                                confirm(
                                  "Rimuovere " +
                                    member.display_name +
                                    " dal gruppo? Lo storico resterà disponibile.",
                                )
                              )
                                action.mutate({
                                  path:
                                    "/groups/" +
                                    id +
                                    "/members/" +
                                    member.user_id,
                                  method: "DELETE",
                                });
                            }}
                          >
                            <Trash2 size={18} />
                          </button>
                        )}
                      </div>
                    ))}
                  </div>
                </State>
              </Section>
              <form
                className="card form-card"
                onSubmit={(e) => {
                  e.preventDefault();
                  if (newMember)
                    action.mutate(
                      {
                        path: "/groups/" + id + "/members",
                        method: "POST",
                        body: { user_id: Number(newMember) },
                      },
                      { onSuccess: () => setNewMember("") },
                    );
                }}
              >
                <label>
                  Aggiungi una persona
                  <select
                    value={newMember}
                    onChange={(e) => setNewMember(e.target.value)}
                    required
                  >
                    <option value="">Scegli utente</option>
                    {users
                      .filter(
                        (u) =>
                          u.is_active &&
                          !active.some((m) => m.user_id === u.id),
                      )
                      .map((u) => (
                        <option key={u.id} value={u.id}>
                          {u.display_name}
                        </option>
                      ))}
                  </select>
                </label>
                <Busy busy={action.isPending} label="Aggiungi al gruppo" />
              </form>
              <div className="card form-card">
                <h3>
                  {group.data.archived
                    ? "Ripristina il gruppo"
                    : "Archivia questo gruppo"}
                </h3>
                <p className="muted">
                  Lo storico e i saldi rimangono consultabili.
                </p>
                <Button
                  variant="secondary"
                  disabled={action.isPending}
                  onClick={() =>
                    action.mutate({
                      path: "/groups/" + id,
                      method: "PATCH",
                      body: { archived: !group.data!.archived },
                    })
                  }
                >
                  <Archive size={18} />
                  {group.data.archived ? "Ripristina" : "Archivia gruppo"}
                </Button>
              </div>
            </>
          )}
          {edit && (
            <GroupForm group={group.data} onClose={() => setEdit(false)} />
          )}{" "}
          {payment !== false && (
            <PaymentForm
              groupId={gid}
              debt={payment}
              members={members.data ?? []}
              onClose={() => setPayment(false)}
            />
          )}
        </>
      )}
    </State>
  );
}
export function PaymentForm({
  groupId,
  debt,
  members,
  onClose,
}: {
  groupId: number;
  debt: Debt | null;
  members: Member[];
  onClose: () => void;
}) {
  const { session } = useSession();
  const suggestions = useApi<Debt[]>("/groups/" + groupId + "/debts");
  const [payer, setPayer] = useState(
    debt?.paid_by_user_id ?? members.find((m) => m.active && m.user_id === session.user.id)?.user_id ?? members.find((m) => m.active)?.user_id ?? 0,
  );
  const [receiver, setReceiver] = useState(
    debt?.paid_to_user_id ??
      members.find((m) => m.active && m.user_id !== payer)?.user_id ??
      0,
  );
  const [amount, setAmount] = useState(debt ? decimal(debt.amount_cents) : "");
  const [currency, setCurrency] = useState(debt?.currency ?? "EUR");
  const [date, setDate] = useState(today());
  const [notes, setNotes] = useState("");
  const [error, setError] = useState("");
  const action = useAction(async (body: unknown) =>
    send("/settlements", "POST", body),
  );
  const suggested = suggestions.data?.find(d => d.paid_by_user_id === payer && d.paid_to_user_id === receiver && d.currency === currency);
  let entered = 0;
  try { entered = cents(amount || "0"); } catch { /* validation on submit */ }
  const person = (id: number) => members.find(m => m.user_id === id)?.display_name ?? "Persona";
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    try {
      const value = cents(amount);
      if (!value || !payer || !receiver || payer === receiver)
        throw new Error(
          "Scegli due persone diverse e un importo maggiore di zero.",
        );
      setError("");
      await action.mutateAsync({
        group_id: groupId,
        paid_by_user_id: payer,
        paid_to_user_id: receiver,
        amount_cents: value,
        currency,
        settlement_date: date,
        notes,
      });
      onClose();
    } catch (e) {
      setError((e as Error).message);
    }
  };
  return (
    <Sheet title="Registra un pareggio" onClose={onClose}>
      <form className="form-card" onSubmit={submit}>
        <p className="muted">
          Registra i soldi già consegnati: il pareggio riduce il debito nel gruppo e aggiorna il saldo complessivo. Non crea una spesa.
        </p>
        <label>
          Chi ha pagato?
          <select
            required
            value={payer}
            onChange={(e) => {
              const next = Number(e.target.value);
              setPayer(next); setAmount("");
              if (next === receiver) setReceiver(members.find(m => m.active && m.user_id !== next)?.user_id ?? 0);
            }}
          >
            {members.map((m) => (
              <option key={m.user_id} value={m.user_id}>
                {m.display_name}
              </option>
            ))}
          </select>
        </label>
        <label>
          A chi?
          <select
            required
            value={receiver}
            onChange={(e) => { setReceiver(Number(e.target.value)); setAmount(""); }}
          >
            <option value="">Scegli destinatario</option>
            {members
              .filter((m) => m.user_id !== payer)
              .map((m) => (
                <option key={m.user_id} value={m.user_id}>
                  {m.display_name}
                </option>
              ))}
          </select>
        </label>
        <div className="category-actions">
          <Button type="button" variant="secondary" onClick={() => setAmount("")}>Pareggio parziale</Button>
          <Button type="button" variant="secondary" disabled={!suggested || suggestions.isFetching}
            onClick={() => { if (suggested) setAmount(decimal(suggested.amount_cents)); }}>Pareggio totale</Button>
        </div>
        <p className="muted">Parziale: inserisci quanto hai versato. Totale: usa l’importo suggerito tra queste persone, nella valuta scelta.</p>
        <ErrorBox error={suggestions.error} />
        <div className="two-fields">
          <label>
            Importo
            <input
              inputMode="decimal"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              required
            />
          </label>
          <label>
            Valuta
            <input
              pattern="[A-Z]{3}"
              maxLength={3}
              value={currency}
              onChange={(e) => { setCurrency(e.target.value.toUpperCase()); setAmount(""); }}
              required
            />
          </label>
        </div>
        <label>
          Data
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
        {entered > 0 && /^[A-Z]{3}$/.test(currency) && payer !== receiver && (
          <div className="notice" role="status">
            <strong>{person(payer)} → {person(receiver)}: <Money value={entered} currency={currency} /></strong>
            {suggested ? <p>Resta da saldare per questo pagamento suggerito: <Money value={Math.max(0, suggested.amount_cents - entered)} currency={currency} />.
              {entered > suggested.amount_cents && <> Stai versando <Money value={entered - suggested.amount_cents} currency={currency} /> in più rispetto al debito suggerito.</>}
            </p> : <p>Non c’è un debito suggerito in questa direzione e valuta. Verifica le persone: il pagamento modifica comunque i saldi.</p>}
          </div>
        )}
        <ErrorBox error={error || action.error} />
        <Busy busy={action.isPending} label="Conferma pareggio" />
      </form>
    </Sheet>
  );
}
