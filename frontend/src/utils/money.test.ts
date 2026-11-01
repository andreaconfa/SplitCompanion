import { describe, expect, it } from "vitest";
import {
  cents,
  decimal,
  splitAmounts,
  money,
  configureTimezone,
  today,
} from "./money";
describe("decimal money without floating point", () => {
  it("accepts Italian and dot decimals with exact cents", () => {
    expect(cents("12,50")).toBe(1250);
    expect(cents("0.29")).toBe(29);
    expect(cents("120")).toBe(12000);
    expect(decimal(1)).toBe("0,01");
  });
  it("rejects precision, negatives, exponent and unsafe integers", () => {
    for (const v of ["1.001", "-2", "1e3", "12,2.3", "9007199254740992", ""])
      expect(() => cents(v)).toThrow();
  });
  it("allocates deterministic equal remainder in user id order", () => {
    expect(splitAmounts(10000, "equal", [3, 1, 2], {})).toEqual([
      { user_id: 1, amount_cents: 3334 },
      { user_id: 2, amount_cents: 3333 },
      { user_id: 3, amount_cents: 3333 },
    ]);
  });
  it("checks exact amounts and supports payer independent single split", () => {
    expect(splitAmounts(1234, "single", [7], {})).toEqual([
      { user_id: 7, amount_cents: 1234 },
    ]);
    expect(() =>
      splitAmounts(1000, "exact", [1, 2], { 1: "5", 2: "4" }),
    ).toThrow();
  });
  it("uses integer percentage rounding and exact 100 percent", () => {
    expect(splitAmounts(101, "percent", [1, 2], { 1: "50", 2: "50" })).toEqual([
      { user_id: 1, amount_cents: 51 },
      { user_id: 2, amount_cents: 50 },
    ]);
    expect(() => splitAmounts(100, "percent", [1], { 1: "99.99" })).toThrow();
  });
});

describe("editable currency drafts", () => {
  it("renders empty and partial currency codes without throwing", () => {
    expect(money(1250, "")).toBe("12,50");
    expect(money(1250, "E")).toBe("12,50 E");
    expect(money(1250, "EU")).toBe("12,50 EU");
    expect(money(1250, "USD")).toContain("12,50");
  });
});
describe("configured installation dates", () => {
  it("honors Honolulu at a UTC midnight before forms initialize", () => {
    try {
      configureTimezone("Pacific/Honolulu");
      expect(today(new Date("2026-10-01T00:00:00Z"))).toBe("2026-09-30");
    } finally {
      configureTimezone("Europe/Rome");
    }
  });
});
