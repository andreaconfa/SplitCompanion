import { t, getLocale } from "../i18n";
import { useLanguage } from "../i18n/react";
import { Person } from "../components/Person";
import MonthlyStatistics from "../components/MonthlyStatistics";
import { Link } from "react-router-dom";
import {
  ArrowUpRight,
  ArrowDownLeft,
  ArrowRight,
  CalendarDays,
  House,
  ChevronRight,
} from "lucide-react";
import { useApi } from "../api/client";
import type { Dashboard as DashboardData, Group, Balance, Member, Legacy } from "../api/types";
import { useData, useSession } from "../components/context";
import {
  PageHead,
  Section,
  State,
  Empty,
  ExpenseRow,
  SubscriptionRow,
  Money,
  LegacyRow,
} from "../components/ui";
export default function Dashboard() {
  useLanguage();
  const query = useApi<DashboardData>("/dashboard/summary");
  const legacy = useApi<Legacy[]>("/legacy");
  const { users } = useData();
  const history = [
    ...(query.data?.recent_expenses ?? []).map(record => ({ kind: "expense" as const, record, date: record.expense_date })),
    ...(legacy.data ?? []).map(record => ({ kind: "legacy" as const, record, date: record.date })),
  ].sort((a, b) => b.date.localeCompare(a.date) || b.record.id - a.record.id).slice(0, 5);
  const { session } = useSession();
  const name = (id: number) =>
    users.find((u) => u.id === id)?.display_name ?? t("Utente");
  return (
    <>
      <PageHead
        title={t("Riepilogo")}
        description={t("Ciao, ") + session.user.display_name.split(" ")[0] + t(". Le tue spese, a colpo d’occhio.")}
        action={
          <span className="overview-date"><CalendarDays size={17} />{new Intl.DateTimeFormat(getLocale(), { month: "long", year: "numeric", timeZone: session.timezone }).format(new Date())}</span>
        }
      />
      <State pending={query.isPending} error={query.error}>
        {query.data && (
          <>
            <div className="overview-layout"><div className="overview-summary"><div className="balance-grid">
              {(query.data.balances.length
                ? query.data.balances
                : [
                    {
                      currency: "EUR",
                      balance_cents: 0,
                      to_receive_cents: 0,
                      to_pay_cents: 0,
                    },
                  ]
              ).map((balance) => (
                <div className="balance-card" key={balance.currency}>
                  <div className="balance-top">
                    <span>{t("Il tuo saldo")}</span>
                    <span className="balance-currency">{balance.currency}</span>
                  </div>
                  <div className="balance-amount">
                    <Money
                      value={balance.balance_cents}
                      currency={balance.currency}
                    />
                  </div>
                  <p>
                    {balance.balance_cents === 0
                      ? t("Siete in pari. Bel lavoro!")
                      : balance.balance_cents > 0
                        ? t("Hai anticipato qualcosa per gli altri.")
                        : t("Un piccolo conto da sistemare.")}
                  </p>
                  <div className="balance-breakdown">
                    <div>
                      <span>
                        <ArrowDownLeft size={16} />{" "}{t("Ti devono")}</span>
                      <strong>
                        {new Intl.NumberFormat(getLocale(), {
                          style: "currency",
                          currency: balance.currency,
                        }).format(balance.to_receive_cents / 100)}
                      </strong>
                    </div>
                    <div>
                      <span>
                        <ArrowUpRight size={16} />{" "}{t("Tu devi")}</span>
                      <strong>
                        {new Intl.NumberFormat(getLocale(), {
                          style: "currency",
                          currency: balance.currency,
                        }).format(balance.to_pay_cents / 100)}
                      </strong>
                    </div>
                  </div>
                </div>
              ))}
            </div>
            </div>
            <MonthlyStatistics />
            <div className="overview-groups">{query.data.groups.filter(group => !group.archived).map(group => <OverviewGroup key={group.id} group={group} />)}</div>
            <div className="desktop-columns">
              <Section title={t("Ultime spese")} action={<Link to="/expenses" className="text-link">{t("Vedi tutte")}{" "}<ArrowRight size={14} /></Link>}>
                <div className="card">
                  <State pending={legacy.isPending} error={legacy.error}>
                    {history.length ? history.map(entry => entry.kind === "legacy" ?
                      <LegacyRow key={`legacy-${entry.record.id}`} record={entry.record} groupName={query.data!.groups.find(group => group.id === entry.record.group_id)?.name} /> :
                      <ExpenseRow key={`expense-${entry.record.id}`} expense={entry.record} users={users} groupName={query.data!.groups.find(group => group.id === entry.record.group_id)?.name} />
                    ) : <Empty title={t("Il primo passo è una spesa")} detail={t("Dalla spesa di casa a una cena fra amici.")} action={<Link to="/expenses/new" className="text-link">{t("Aggiungi spesa")}</Link>} />}
                  </State>
                </div>
              </Section>
              <Section title={t("Prossimi abbonamenti")} action={<Link to="/subscriptions" className="text-link">{t("Vedi tutti")}{" "}<ArrowRight size={14} /></Link>}>
                <div className="card">
                  {query.data.upcoming.length ? query.data.upcoming.slice(0, 4).map(sub => <SubscriptionRow key={sub.id} subscription={sub} users={users} />) :
                    <Empty title={t("Nessuna scadenza vicina")} detail={t("Automatizza le spese che si ripetono.")} action={<Link to="/subscriptions/new" className="text-link">{t("Crea un abbonamento")}</Link>} />}
                </div>
              </Section>
            </div>
            <Section
              title={t("Da sistemare")}
              action={
                <Link className="text-link" to="/groups">{t("Vedi saldi")}{" "}<ArrowRight size={14} />
                </Link>
              }
            >
              <div className="card">
                {query.data.debts.length ? (
                  query.data.debts.map((debt, index) => (
                    <Link
                      className="list-row"
                      key={index}
                      to={"/groups/" + debt.group_id + "?tab=balances"}
                    >
                      <span className="row-icon">
                        <ArrowRight size={18} />
                      </span>
                      <div className="row-main">
                        <strong>
                          <Person userId={debt.paid_by_user_id} name={name(debt.paid_by_user_id)} small /> →{" "}
                          <Person userId={debt.paid_to_user_id} name={name(debt.paid_to_user_id)} small />
                        </strong>
                        <span>{debt.group_name}</span>
                      </div>
                      <Money
                        value={debt.amount_cents}
                        currency={debt.currency}
                      />
                    </Link>
                  ))
                ) : (
                  <Empty
                    title={t("Nessun conto in sospeso")}
                    detail={t("Qui vedrai i pagamenti suggeriti per tornare in pari.")}
                  />
                )}
              </div>
            </Section>
            </div>
          </>
        )}
      </State>
    </>
  );
}

function OverviewGroup({ group }: { group: Group }) {
  useLanguage();
  const { session } = useSession();
  const balances = useApi<Balance[]>(`/groups/${group.id}/balances`);
  const members = useApi<Member[]>(`/groups/${group.id}/members`);
  return <Link className="overview-group card" to={`/groups/${group.id}`}>
    <span className="row-icon"><House size={23} /></span>
    <div className="row-main"><strong>{group.name}</strong><span>{members.data ? t("{0} membri", {0: members.data.filter(member => member.active).length}) : t("Caricamento…")}</span></div>
    <div className="overview-group-balances">{balances.data?.filter(balance => balance.user_id === session.user.id).map(balance => <Money key={balance.currency} value={balance.balance_cents} currency={balance.currency} signed />)}{balances.isError && <small>{t("Saldo non disponibile")}</small>}</div>
    <ChevronRight size={18} />
  </Link>;
}
