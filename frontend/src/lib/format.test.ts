import { describe, expect, it } from "vitest";
import { compact, money, pct, pValue, signedPct } from "./format";

describe("format", () => {
  it("formats rupiah with Indonesian separators", () => {
    expect(money(150000)).toBe("Rp 150.000");
    expect(money(-2500000)).toBe("-Rp 2.500.000");
    expect(money(116000000, "IDR", { compact: true })).toBe("Rp 116.0M");
  });

  it("formats other currencies with Intl", () => {
    expect(money(25, "USD")).toBe("$25");
  });

  it("formats percentages and p-values", () => {
    expect(pct(0.614)).toBe("61%");
    expect(pct(0.614, 1)).toBe("61.4%");
    expect(signedPct(0.05)).toBe("+5%");
    expect(pValue(0.0004)).toBe("p < .001");
    expect(pValue(0.0213)).toBe("p = .021");
    expect(pct(undefined)).toBe("n/a");
  });

  it("compacts large numbers", () => {
    expect(compact(1234)).toBe("1,234");
    expect(compact(15400)).toBe("15.4K");
    expect(compact(2_300_000)).toBe("2.3M");
  });
});
