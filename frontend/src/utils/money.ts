import type { SplitMode, Split } from "../api/types";
export function cents(value: string): number {
  const normalized = value.trim().replace(",", ".");
  if (!/^\d+(\.\d{1,2})?$/.test(normalized))
    throw new Error("Inserisci un importo valido, con massimo due decimali.");
  const [whole, fraction = ""] = normalized.split(".");
  const amount = BigInt(whole) * 100n + BigInt(fraction.padEnd(2, "0"));
  if (amount > BigInt(Number.MAX_SAFE_INTEGER))
    throw new Error("Importo troppo grande.");
  return Number(amount);
}
export function decimal(value: number) {
  return `${Math.trunc(value / 100)},${String(Math.abs(value % 100)).padStart(2, "0")}`;
}
export function money(value: number, currency = "EUR", sign = false) {
  if (!validCurrency(currency)) {
    const amount = new Intl.NumberFormat("it-IT", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
      signDisplay: sign ? "exceptZero" : "auto",
    }).format(value / 100);
    return amount + (currency ? " " + currency : "");
  }
  return new Intl.NumberFormat("it-IT", {
    style: "currency",
    currency,
    signDisplay: sign ? "exceptZero" : "auto",
  }).format(value / 100);
}
export const validCurrency = (currency: string) => /^[A-Z]{3}$/.test(currency);
export function splitAmounts(
  amount: number,
  mode: SplitMode,
  participants: number[],
  values: Record<number, string>,
): Split[] {
  const ids = [...participants].sort((a, b) => a - b);
  if (!ids.length) throw new Error("Seleziona almeno una persona.");
  if (mode === "single") {
    if (ids.length !== 1) throw new Error("Scegli una sola persona.");
    return [{ user_id: ids[0], amount_cents: amount }];
  }
  if (mode === "equal") {
    const base = Math.trunc(amount / ids.length);
    const rest = amount % ids.length;
    return ids.map((id, index) => ({
      user_id: id,
      amount_cents: base + (index < rest ? 1 : 0),
    }));
  }
  if (mode === "exact") {
    const splits = ids.map((id) => ({
      user_id: id,
      amount_cents: cents(values[id] ?? "0"),
    }));
    if (splits.reduce((sum, s) => sum + s.amount_cents, 0) !== amount)
      throw new Error(`Le quote devono totalizzare ${money(amount)}.`);
    return splits;
  }
  const parts = ids.map((id) => ({ id, percent: cents(values[id] ?? "0") }));
  if (parts.reduce((sum, p) => sum + p.percent, 0) !== 10000)
    throw new Error("Le percentuali devono totalizzare 100%.");
  const shares = parts.map((p) => ({
    user_id: p.id,
    amount_cents: Number((BigInt(amount) * BigInt(p.percent)) / 10000n),
    remainder: (BigInt(amount) * BigInt(p.percent)) % 10000n,
  }));
  let rest = amount - shares.reduce((sum, s) => sum + s.amount_cents, 0);
  for (const share of [...shares].sort((a, b) =>
    a.remainder === b.remainder
      ? a.user_id - b.user_id
      : a.remainder > b.remainder
        ? -1
        : 1,
  )) {
    if (rest-- > 0) share.amount_cents++;
  }
  return shares.map(({ user_id, amount_cents }) => ({ user_id, amount_cents }));
}
let installationTimezone = "Europe/Rome";
export function configureTimezone(timezone: string) {
  new Intl.DateTimeFormat("en", { timeZone: timezone }).format();
  installationTimezone = timezone;
}
export function today(instant = new Date()) {
  const parts = new Intl.DateTimeFormat("en", {
    timeZone: installationTimezone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(instant);
  const value = (type: string) =>
    parts.find((part) => part.type === type)!.value;
  return `${value("year")}-${value("month")}-${value("day")}`;
}
export const dateLabel = (date: string | null) =>
  date
    ? new Intl.DateTimeFormat("it-IT", {
        day: "numeric",
        month: "short",
        year: "numeric",
      }).format(new Date(date + "T12:00:00"))
    : "—";
export function recurrenceLabel(rule: string) {
  const freq = rule.match(/FREQ=(\w+)/)?.[1] ?? "MONTHLY";
  const count = Number(rule.match(/INTERVAL=(\d+)/)?.[1] ?? 1);
  const units: Record<string, string[]> = {
    WEEKLY: ["settimana", "settimane"],
    MONTHLY: ["mese", "mesi"],
    YEARLY: ["anno", "anni"],
  };
  return count === 1
    ? "Ogni " + (units[freq]?.[0] ?? "mese")
    : `Ogni ${count} ${units[freq]?.[1] ?? "mesi"}`;
}
