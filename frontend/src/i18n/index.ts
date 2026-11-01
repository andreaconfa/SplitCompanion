import { english, italian } from './messages';
export type Language = 'en' | 'it';
export const LANGUAGE_KEY = 'split-companion-language';
export const messages = { en: english, it: italian };
export const normalizeLanguage = (value: unknown): Language => value === 'it' ? 'it' : 'en';
function storedLanguage(): Language {
  try { return normalizeLanguage(localStorage.getItem(LANGUAGE_KEY)); } catch { return 'en'; }
}
let language: Language = storedLanguage();
const listeners = new Set<() => void>();
export const getLanguage = () => language;
export const getLocale = () => language === 'it' ? 'it-IT' : 'en-US';
function notify() {
  if (typeof document !== 'undefined') document.documentElement.lang = language;
  listeners.forEach(listener => listener());
}
export function setLanguage(value: Language) {
  language = normalizeLanguage(value);
  try { localStorage.setItem(LANGUAGE_KEY, language); } catch { /* Retain the in-memory choice. */ }
  notify();
}
export function subscribeLanguage(listener: () => void) {
  listeners.add(listener);
  return () => { listeners.delete(listener); };
}
if (typeof window !== 'undefined') {
  window.addEventListener('storage', event => {
    if (event.key === LANGUAGE_KEY || event.key === null) {
      language = storedLanguage();
      notify();
    }
  });
}
export function translate(key: string, locale: string, values: Record<string, string | number> = {}) {
  const template = messages[normalizeLanguage(locale)][key] ?? english[key] ?? key;
  return template.replace(/\{(\w+)\}/g, (placeholder, name: string) => Object.prototype.hasOwnProperty.call(values, name) ? String(values[name]) : placeholder);
}
export const t = (key: string, values?: Record<string, string | number>) => translate(key, language, values);
// Only application notices use this bridge. User names/descriptions never pass through it.
const englishMessageKeys = new Map(Object.entries(english).map(([key, value]) => [value, key]));
export function translateMessage(message: string) {
  return t(englishMessageKeys.get(message) ?? message);
}
