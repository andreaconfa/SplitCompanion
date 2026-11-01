import type { Legacy } from "../api/types";
export function filterLegacy(
  records: Legacy[],
  filters: Record<string, string>,
) {
  if (
    filters.payer_id ||
    filters.subscription_id ||
    filters.source === "NATIVE"
  )
    return [];
  return records.filter(
    (record) =>
      (!filters.group_id || record.group_id === Number(filters.group_id)) &&
      (!filters.date_from || record.date >= filters.date_from) &&
      (!filters.date_to || record.date <= filters.date_to) &&
      (!filters.participant_id ||
        record.entries.some(
          (entry) => entry.user_id === Number(filters.participant_id),
        )),
  );
}
