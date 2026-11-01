import { describe, it, expect } from "vitest";
import { filterLegacy } from "./history";
import type { Legacy } from "../api/types";
const records: Legacy[] = [
  {
    id: 1,
    group_id: 7,
    date: "2026-09-30",
    description: "Cena",
    cost_cents: 3000,
    currency: "EUR",
    source: "SPLITWISE",
    entries: [
      { user_id: 2, balance_delta_cents: -1500 },
      { user_id: 1, balance_delta_cents: 1500 },
    ],
  },
  {
    id: 2,
    group_id: 8,
    date: "2026-10-01",
    description: "Viaggio",
    cost_cents: 4000,
    currency: "USD",
    source: "SPLITWISE",
    entries: [{ user_id: 3, balance_delta_cents: 2000 }],
  },
];
describe("unified legacy history filters", () => {
  it("filters actual legacy group, dates and participant without inventing payer", () => {
    expect(
      filterLegacy(records, {
        group_id: "7",
        date_from: "2026-09-01",
        date_to: "2026-09-30",
        participant_id: "2",
        source: "SPLITWISE",
      }).map((row) => row.id),
    ).toEqual([1]);
    expect(
      filterLegacy(records, { date_from: "2026-10-01", participant_id: "2" }),
    ).toEqual([]);
    expect(filterLegacy(records, { source: "NATIVE" })).toEqual([]);
    expect(filterLegacy(records, { payer_id: "1" })).toEqual([]);
    expect(filterLegacy(records, { subscription_id: "1" })).toEqual([]);
  });
});
