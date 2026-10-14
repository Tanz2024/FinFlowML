import { describe, expect, it } from "vitest";
import { dirtyCorrections } from "./review";
const values = { company: "Acme", receipt_date: "2024-01-01", address: "One Road", total: "10.00", currency: "MYR" };
describe("dirtyCorrections", () => {
  it("sends only changed fields", () => expect(dirtyCorrections(values, { ...values, total: "11.00" })).toEqual({ total: "11.00" }));
  it("does not mark unchanged valid values corrected", () => expect(dirtyCorrections(values, values)).toEqual({}));
});
