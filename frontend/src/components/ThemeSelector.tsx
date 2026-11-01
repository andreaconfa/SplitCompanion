import { useEffect, useId, useState } from 'react';
import { Sun, Moon, Monitor, Check } from 'lucide-react';
import { ACCENTS, ACCENT_KEY, currentAccent, chooseAccent, applyAccent, syncStoredAccent, THEME_KEY, applyTheme, currentTheme, chooseTheme, syncStoredTheme } from '../utils/theme';
export function ThemeSelector() {
  const [preference, setPreference] = useState(currentTheme);
  const groupId = useId();
  useEffect(() => {
    const sync = () => setPreference(currentTheme());
    window.addEventListener('appearance-change', sync);
    return () => window.removeEventListener('appearance-change', sync);
  }, []);
  const options = [{ value: 'light', label: 'Chiaro', Icon: Sun }, { value: 'dark', label: 'Scuro', Icon: Moon }, { value: 'system', label: 'Sistema', Icon: Monitor }] as const;
  return <fieldset className="theme-selector"><legend>Aspetto</legend><div>{options.map(({ value, label, Icon }) => <label key={value} className={preference === value ? 'selected' : ''}><input type="radio" name={`appearance-${groupId}`} value={value} checked={preference === value} onChange={() => chooseTheme(value)} /><Icon size={17} /><span>{label}</span></label>)}</div></fieldset>;
}
export function ThemeObserver() {
  useEffect(() => {
    const media = matchMedia('(prefers-color-scheme: dark)');
    const update = () => applyTheme(currentTheme());
    const sync = (event: StorageEvent) => { if (event.key === THEME_KEY || event.key === null) syncStoredTheme(); if (event.key === ACCENT_KEY || event.key === null) syncStoredAccent(); };
    media.addEventListener('change', update);
    window.addEventListener('storage', sync);
    update();
    applyAccent(currentAccent());
    return () => { media.removeEventListener('change', update); window.removeEventListener('storage', sync); };
  }, []);
  return null;
}

export function AccentSelector() {
  const [preference, setPreference] = useState(currentAccent);
  const groupId = useId();
  useEffect(() => {
    const sync = () => setPreference(currentAccent());
    window.addEventListener('appearance-change', sync);
    return () => window.removeEventListener('appearance-change', sync);
  }, []);
  return <fieldset className="accent-selector"><legend>Colore principale</legend><div>{ACCENTS.map(({ value, label, color }) => <label key={value} className={preference === value ? 'selected' : ''}>
    <input type="radio" name={`accent-${groupId}`} value={value} checked={preference === value} onChange={() => chooseAccent(value)} />
    <span className="accent-swatch" style={{ backgroundColor: color }}>{preference === value && <Check size={19} strokeWidth={3} aria-hidden="true" />}</span><span>{label}</span>
  </label>)}</div></fieldset>;
}
