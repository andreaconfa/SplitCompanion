import { t, getLocale } from "../i18n";
import { useLanguage } from "../i18n/react";
import { useState } from "react";
import { ChevronLeft, ChevronRight, ChartNoAxesCombined } from "lucide-react";
import { params, useApi } from "../api/client";
import type { MonthlyStatisticsData } from "../api/types";
import { dateLabel, today } from "../utils/money";
import { useData } from "./context";
import "./MonthlyStatistics.css";

function monthLabel(month: string, short = false) {
  return new Intl.DateTimeFormat(getLocale(), { month: short ? "short" : "long", year: "numeric", timeZone: "UTC" }).format(new Date(`${month}-01T12:00:00Z`));
}
function adjacentMonth(month: string, offset: number) {
  const [year, index] = month.split("-").map(Number);
  const value = year * 12 + index - 1 + offset;
  return `${String(Math.floor(value / 12)).padStart(4, "0")}-${String(value % 12 + 1).padStart(2, "0")}`;
}

export default function MonthlyStatistics() {
  useLanguage();
  const { groups } = useData();
  const [month, setMonth] = useState(() => today().slice(0, 7));
  const [group, setGroup] = useState("");
  const [currency, setCurrency] = useState("");
  const query = useApi<MonthlyStatisticsData>("/dashboard/statistics" + params({ month, group_id: group, currency }));
  const data = query.data;
  const current = data?.current_month ?? today().slice(0, 7);
  const currencies = data?.currencies ?? (currency ? [currency] : []);
  return <section className="monthly-stats" aria-labelledby="monthly-stats-title">
    <div className="stats-heading"><div><h2 id="monthly-stats-title"><ChartNoAxesCombined size={20} aria-hidden="true" />{t("Statistiche mensili")}</h2><p>{t("Le spese dei tuoi gruppi, mese per mese.")}</p></div></div>
    <div className="stats-filters">
      <div className="stats-month-control"><button type="button" aria-label={t("Mese precedente")} disabled={month <= "1900-01"} onClick={() => setMonth(adjacentMonth(month, -1))}><ChevronLeft size={18} /></button><label><span>{t("Mese")}</span><input aria-label={t("Mese")} type="month" min="1900-01" max={current} value={month} onChange={event => { const value = event.target.value; if (/^\d{4}-(0[1-9]|1[0-2])$/.test(value) && value >= "1900-01" && value <= current) setMonth(value); }} /></label><button type="button" aria-label={t("Mese successivo")} disabled={month >= current} onClick={() => setMonth(adjacentMonth(month, 1))}><ChevronRight size={18} /></button></div>
      <label className="stats-group-filter"><span>{t("Gruppo")}</span><select aria-label={t("Gruppo")} value={group} onChange={event => { setGroup(event.target.value); setCurrency(""); }}><option value="">{t("Tutti i gruppi")}</option>{groups.map(item => <option key={item.id} value={item.id}>{item.name}{item.archived ? t(" · archiviato") : ""}</option>)}</select></label>
      <label className="stats-currency-filter"><span>{t("Valuta")}</span><select aria-label={t("Valuta")} value={currency || data?.currency || ""} disabled={!data} onChange={event => setCurrency(event.target.value)}>{!data && <option value={currency}>{currency || "…"}</option>}{currencies.map(value => <option key={value}>{value}</option>)}</select></label>
    </div>
    {query.isPending ? <p className="stats-state" role="status">{t("Caricamento delle statistiche…")}</p> : query.isError ? <div className="stats-state" role="alert"><p>{t("Non è stato possibile caricare le statistiche.")}</p><button className="btn btn-secondary" onClick={() => void query.refetch()}>{t("Riprova")}</button></div> : data && <StatisticsContent data={data} />}
  </section>;
}

function StatisticsContent({ data }: { data: MonthlyStatisticsData }) {
  useLanguage();
  const format = (cents: number) => new Intl.NumberFormat(getLocale(), { style: "currency", currency: data.currency, minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(cents / 100);
  const { summary, comparison, coverage } = data;
  const maxCategory = Math.max(1, ...data.categories.map(item => item.total_cents));
  const maxTrend = Math.max(1, ...data.trend.map(item => item.total_cents));
  const maxDaily = Math.max(1, ...data.daily.map(item => item.cumulative_cents));
  const points = data.daily.map((item, index) => `${12 + index / Math.max(1, data.daily.length - 1) * 576},${130 - item.cumulative_cents / maxDaily * 115}`).join(" ");
  return <div className="stats-content">
    <div className="stats-summary">
      <div className="stats-total"><div className="stats-eyebrow">{t("Spese dei gruppi ·")}{" "}{monthLabel(data.month)}</div><strong>{format(summary.total_cents)}</strong><p>{t("Totale dei gruppi, non le tue quote personali.")}</p><div className="stats-comparison"><b>{format(comparison.change_cents)}{comparison.change_percent !== null && ` (${new Intl.NumberFormat(getLocale(), { maximumFractionDigits: 1, signDisplay: "exceptZero" }).format(comparison.change_percent)}%)`}</b><span>{" "}{t("rispetto a")}{" "}{dateLabel(comparison.start)} – {dateLabel(comparison.end)}: {format(comparison.total_cents)}.{comparison.change_percent === null && t(" Nessuna spesa nel periodo di confronto: percentuale non disponibile.")}</span></div>{data.period.is_current && <small>{t("Mese in corso: dal")}{" "}{dateLabel(data.period.start)}{" "}{t("al")}{" "}{dateLabel(data.period.end)}{t(". Confronto fino allo stesso giorno, o alla fine del mese precedente.")}</small>}</div>
      <dl className="stats-metrics"><div><dt>{t("Spese registrate")}</dt><dd>{summary.expense_count}</dd></div><div><dt>{t("Importo medio")}</dt><dd>{format(summary.average_cents)}</dd></div><div><dt>{t("Media giornaliera")}{" "}<span>· {data.period.days}{" "}{t("giorni")}</span></dt><dd>{format(summary.daily_average_cents)}</dd></div></dl>
    </div>
    {summary.expense_count === 0 && <div className="stats-empty"><strong>{t("Nessuna spesa in questo periodo.")}</strong><p>{t("Prova un altro mese o gruppo. Sono conteggiate solo le spese con un importo valido.")}</p></div>}
    <div className="stats-charts">
      <div className="stats-chart stats-categories"><h3>{t("Per categoria")}</h3><p>{t("Dove si concentrano le spese")}</p>{data.categories.length ? <ol>{data.categories.map((item, index) => <li key={item.category_id ?? "none"}><div className="stats-category-label"><span><i>{String(index + 1).padStart(2, "0")}</i>{item.name}</span><strong>{format(item.total_cents)}</strong></div><div className="stats-track" aria-hidden="true"><div style={{ width: `${Math.max(0, item.total_cents / maxCategory * 100)}%` }} /></div><small>{item.count} {item.count === 1 ? t("spesa") : t("spese")}</small></li>)}</ol> : <p className="stats-chart-empty">{t("Nessuna categoria da mostrare.")}</p>}</div>
      <div className="stats-chart"><h3>{t("Ultimi sei mesi")}</h3><p>{t("Totali mensili ·")}{" "}{data.currency}</p><ol className="stats-month-bars">{data.trend.map(item => <li key={item.month}><strong>{format(item.total_cents)}</strong><div className="stats-bar-space" aria-hidden="true"><div className={item.month === data.month ? "selected" : ""} style={{ height: `${item.total_cents / maxTrend * 100}%` }} /></div><span>{monthLabel(item.month, true)}</span>{item.is_partial && <small>{t("parziale")}</small>}</li>)}</ol></div>
    </div>
    <div className="stats-chart stats-daily"><div className="stats-daily-heading"><div><h3>{t("Spesa cumulata")}</h3><p>{t("Il totale progressivo giorno per giorno")}</p></div><strong>{format(summary.total_cents)}</strong></div><svg viewBox="0 0 600 145" preserveAspectRatio="none" role="img" aria-label={t("Spesa cumulata dal {0} al {1}: {2}. Valori giornalieri nella tabella sottostante.", {0: dateLabel(data.period.start), 1: dateLabel(data.period.end), 2: format(summary.total_cents)})}><line x1="12" y1="130" x2="588" y2="130" stroke="var(--line)" /><line x1="12" y1="72" x2="588" y2="72" stroke="var(--line)" strokeDasharray="4 5" /><polyline points={points} fill="none" stroke="var(--accent-text)" strokeWidth="3" vectorEffect="non-scaling-stroke" strokeLinejoin="round" />{data.daily.length === 1 && <circle cx="12" cy={130 - data.daily[0].cumulative_cents / maxDaily * 115} r="4" fill="var(--accent-text)" />}</svg><div className="stats-daily-axis"><span>{dateLabel(data.period.start)}</span><span>{dateLabel(data.period.end)}</span></div><details><summary>{t("Vedi gli importi giornalieri")}</summary><table><caption>{t("Spese giornaliere e totale progressivo in")}{" "}{data.currency}</caption><thead><tr><th scope="col">{t("Giorno")}</th><th scope="col">{t("Spese")}</th><th scope="col">{t("Cumulato")}</th></tr></thead><tbody>{data.daily.map(item => <tr key={item.date}><th scope="row">{dateLabel(item.date)}</th><td>{format(item.total_cents)}</td><td>{format(item.cumulative_cents)}</td></tr>)}</tbody></table></details></div>
    <details className="stats-coverage"><summary>{t("Come sono calcolate ·")}{" "}{coverage.legacy_included_count}{" "}{t("spese storiche incluse")}{coverage.legacy_excluded_count > 0 ? t(" · {0} escluse", {0: coverage.legacy_excluded_count}) : ""}</summary><p>{t("Spese registrate e occorrenze degli abbonamenti, conteggiate una sola volta. Pareggi, anticipi e rimborsi degli abbonamenti sono esclusi. Le definizioni degli abbonamenti non sono spese.")}</p><p>{t("Lo storico importato include solo importi positivi noti, esclusa la categoria trasferimenti. Nel periodo e nella valuta selezionati:")}{" "}{coverage.legacy_transfers_excluded_count}{" "}{t("trasferimenti esclusi,")}{" "}{coverage.legacy_missing_cost_count}{" "}{t("importi sconosciuti o mancanti e")}{" "}{coverage.legacy_nonpositive_count}{" "}{t("importi pari a zero o negativi esclusi. Le categorie delle spese native non ne cambiano il conteggio.")}</p><p>{t("Spese native:")}{" "}{format(summary.native_total_cents)}{" "}{t("· Storico incluso:")}{" "}{format(summary.legacy_total_cents)}{t(". Le valute restano separate; i saldi non vengono usati per ricostruire quote personali.")}</p></details>
  </div>;
}
