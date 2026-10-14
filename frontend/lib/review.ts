export const REVIEW_FIELDS = ["company", "receipt_date", "address", "total", "currency"] as const;
export type ReviewField = (typeof REVIEW_FIELDS)[number];
export function dirtyCorrections(original: Record<ReviewField, string>, current: Record<ReviewField, string>): Partial<Record<ReviewField, string>> {
  return Object.fromEntries(REVIEW_FIELDS.filter((field) => current[field] !== original[field]).map((field) => [field, current[field]]));
}
