import { describe, expect, it } from 'vitest';
import { resolveTheme, readTheme } from './theme';
describe('appearance preference', () => {
  it('uses the system when no valid preference is stored', () => {
    expect(readTheme(null)).toBe('system');
    expect(readTheme('invalid')).toBe('system');
    expect(resolveTheme('system', true)).toBe('dark');
    expect(resolveTheme('system', false)).toBe('light');
  });
  it('honors an explicit selection regardless of the system', () => {
    expect(resolveTheme(readTheme('light'), true)).toBe('light');
    expect(resolveTheme(readTheme('dark'), false)).toBe('dark');
  });
});

import { vi, afterEach } from 'vitest';
afterEach(() => { vi.unstubAllGlobals(); vi.resetModules(); });
describe('theme persistence and live preference', () => {
  function environment(storageFails = false) {
    const saved = new Map<string, string>();
    const root = { dataset: {} as Record<string,string>, style: {} as Record<string,string> };
    const events = new EventTarget();
    let dark = false;
    vi.stubGlobal('document', {documentElement: root, querySelector: () => null});
    vi.stubGlobal('window', events);
    vi.stubGlobal('matchMedia', () => ({matches: dark}));
    vi.stubGlobal('localStorage', {getItem: (key:string) => saved.get(key) ?? null, setItem: (key:string, value:string) => { if(storageFails) throw new Error('Storage blocked'); saved.set(key,value); }});
    return {saved, root, events, system: (value:boolean) => {dark=value;}};
  }
  it('persists and notifies every selector when the preference changes', async () => {
    const env = environment();
    const {chooseTheme,currentTheme,THEME_KEY} = await import('./theme');
    const changed = vi.fn(); env.events.addEventListener('appearance-change',changed);
    chooseTheme('dark');
    expect(env.saved.get(THEME_KEY)).toBe('dark');
    expect(env.root.dataset.theme).toBe('dark');
    expect(currentTheme()).toBe('dark');
    expect(changed).toHaveBeenCalledOnce();
  });
  it('keeps the explicit choice when storage is blocked and the system changes', async () => {
    const env = environment(true);
    const {chooseTheme,currentTheme,applyTheme} = await import('./theme');
    chooseTheme('light'); env.system(true); applyTheme(currentTheme());
    expect(env.root.dataset.theme).toBe('light');
    chooseTheme('system'); expect(env.root.dataset.theme).toBe('dark');
    env.system(false); applyTheme(currentTheme()); expect(env.root.dataset.theme).toBe('light');
  });
  it('synchronizes changes from another tab and defaults removed preferences to system', async () => {
    const env = environment();
    const {THEME_KEY,syncStoredTheme,currentTheme} = await import('./theme');
    env.saved.set(THEME_KEY,'dark'); syncStoredTheme();
    expect(currentTheme()).toBe('dark'); expect(env.root.dataset.theme).toBe('dark');
    env.saved.delete(THEME_KEY); syncStoredTheme(); expect(currentTheme()).toBe('system');
    expect(env.root.dataset.theme).toBe('light');
  });
});

describe('accent preference', () => {
  function environment(storageFails = false) {
    const saved = new Map<string, string>();
    const root = { dataset: {} as Record<string, string> };
    const events = new EventTarget();
    vi.stubGlobal('document', { documentElement: root });
    vi.stubGlobal('window', events);
    vi.stubGlobal('localStorage', {
      getItem: (key: string) => { if (storageFails) throw new Error('Storage blocked'); return saved.get(key) ?? null; },
      setItem: (key: string, value: string) => { if (storageFails) throw new Error('Storage blocked'); saved.set(key, value); },
    });
    return { saved, root, events };
  }
  it('accepts the five iOS accents and falls back for missing or invalid storage', async () => {
    environment();
    const { ACCENTS, readAccent } = await import('./theme');
    expect(ACCENTS.map(item => readAccent(item.value))).toEqual(['indigo', 'ocean', 'forest', 'rose', 'amber']);
    expect(readAccent(null)).toBe('indigo');
    expect(readAccent('blue')).toBe('indigo');
  });
  it('persists the accent without overwriting the existing theme and broadcasts updates', async () => {
    const env = environment();
    const { THEME_KEY, ACCENT_KEY, chooseAccent, currentAccent } = await import('./theme');
    env.saved.set(THEME_KEY, 'dark');
    const changed = vi.fn(); env.events.addEventListener('appearance-change', changed);
    chooseAccent('forest');
    expect(env.saved.get(ACCENT_KEY)).toBe('forest');
    expect(env.saved.get(THEME_KEY)).toBe('dark');
    expect(currentAccent()).toBe('forest');
    expect(env.root.dataset.accent).toBe('forest');
    expect(changed).toHaveBeenCalledOnce();
  });
  it('keeps a usable in-memory accent when storage is unavailable', async () => {
    const env = environment(true);
    const { currentAccent, chooseAccent } = await import('./theme');
    expect(currentAccent()).toBe('indigo');
    chooseAccent('rose');
    expect(currentAccent()).toBe('rose');
    expect(env.root.dataset.accent).toBe('rose');
  });
  it('synchronizes another tab and resets removed or invalid preferences', async () => {
    const env = environment();
    const { ACCENT_KEY, syncStoredAccent, currentAccent } = await import('./theme');
    env.saved.set(ACCENT_KEY, 'amber'); syncStoredAccent();
    expect(currentAccent()).toBe('amber');
    env.saved.set(ACCENT_KEY, 'obsolete'); syncStoredAccent();
    expect(currentAccent()).toBe('indigo');
    env.saved.delete(ACCENT_KEY); syncStoredAccent();
    expect(env.root.dataset.accent).toBe('indigo');
  });
});
