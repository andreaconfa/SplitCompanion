export type ThemePreference = 'light' | 'dark' | 'system';
export const THEME_KEY = 'split-companion-theme';
export function readTheme(value: string | null): ThemePreference {
  return value === 'light' || value === 'dark' ? value : 'system';
}
export function resolveTheme(preference: ThemePreference, systemDark: boolean) {
  return preference === 'system' ? (systemDark ? 'dark' : 'light') : preference;
}
export function storedTheme(): ThemePreference {
  try { return readTheme(localStorage.getItem(THEME_KEY)); } catch { return 'system'; }
}
export function applyTheme(preference: ThemePreference) {
  const theme = resolveTheme(preference, matchMedia('(prefers-color-scheme: dark)').matches);
  document.documentElement.dataset.theme = theme;
  document.documentElement.style.colorScheme = theme;
  document.querySelector('meta[name="theme-color"]')?.setAttribute('content', theme === 'dark' ? '#000000' : '#f2f2f7');
}

let activePreference: ThemePreference | undefined;
export function currentTheme() { return activePreference ??= storedTheme(); }
export function chooseTheme(preference: ThemePreference) {
  activePreference = preference;
  try { localStorage.setItem(THEME_KEY, preference); } catch { /* Keep the in-memory choice. */ }
  applyTheme(preference);
  window.dispatchEvent(new Event('appearance-change'));
}
export function syncStoredTheme() {
  activePreference = storedTheme();
  applyTheme(activePreference);
  window.dispatchEvent(new Event('appearance-change'));
}

export const ACCENT_KEY = 'split-companion-accent';
export const ACCENTS = [
  { value: 'indigo', label: 'Indaco', color: 'rgb(31% 30% 90%)' },
  { value: 'ocean', label: 'Oceano', color: 'rgb(2% 42% 74%)' },
  { value: 'forest', label: 'Foresta', color: 'rgb(2% 48% 35%)' },
  { value: 'rose', label: 'Rosa', color: 'rgb(75% 16% 40%)' },
  { value: 'amber', label: 'Ambra', color: 'rgb(66% 35% 2%)' },
] as const;
export type AccentPreference = typeof ACCENTS[number]['value'];
export function readAccent(value: string | null): AccentPreference {
  return ACCENTS.find(accent => accent.value === value)?.value ?? 'indigo';
}
export function storedAccent(): AccentPreference {
  try { return readAccent(localStorage.getItem(ACCENT_KEY)); } catch { return 'indigo'; }
}
let activeAccent: AccentPreference | undefined;
export function currentAccent() { return activeAccent ??= storedAccent(); }
export function applyAccent(preference: AccentPreference) {
  document.documentElement.dataset.accent = preference;
}
export function chooseAccent(preference: AccentPreference) {
  activeAccent = preference;
  try { localStorage.setItem(ACCENT_KEY, preference); } catch { /* Keep the in-memory choice. */ }
  applyAccent(preference);
  window.dispatchEvent(new Event('appearance-change'));
}
export function syncStoredAccent() {
  activeAccent = storedAccent();
  applyAccent(activeAccent);
  window.dispatchEvent(new Event('appearance-change'));
}
