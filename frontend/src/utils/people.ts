import { t } from "../i18n";
export type PeopleDisplay = "both" | "name" | "photo";
export const PEOPLE_DISPLAY_KEY = "split.peopleDisplay";
let fallbackDisplay: PeopleDisplay = "both";
export function peopleDisplay(): PeopleDisplay {
  try {
    const value = localStorage.getItem(PEOPLE_DISPLAY_KEY);
    return value === "name" || value === "photo" ? value : "both";
  } catch { return fallbackDisplay; }
}
export function choosePeopleDisplay(value: PeopleDisplay) {
  fallbackDisplay = value;
  try { localStorage.setItem(PEOPLE_DISPLAY_KEY, value); } catch { /* Storage may be unavailable. */ }
  window.dispatchEvent(new Event("people-display-change"));
}
export function initials(name: string) {
  return name.trim().split(/\s+/).filter(Boolean).slice(0, 2).map(part => Array.from(part)[0]).join("").toLocaleUpperCase() || "?";
}
export function avatarURL(id: number, version?: string | null) {
  return version ? `/api/users/${id}/avatar?v=${encodeURIComponent(version)}` : null;
}
export function avatarFileError(file: { size: number; type: string }) {
  if (!["image/png", "image/jpeg", "image/webp"].includes(file.type)) return t("Scegli una foto PNG, JPEG o WebP.");
  if (file.size > 2 * 1024 * 1024) return t("La foto supera il limite di 2 MB.");
  if (!file.size) return t("La foto è vuota. Scegli un altro file.");
  return "";
}
