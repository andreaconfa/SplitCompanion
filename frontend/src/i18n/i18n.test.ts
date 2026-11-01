import { describe, it, expect, afterEach, vi } from 'vitest';

const load = () => import('./index').catch(() => null);
afterEach(() => { vi.unstubAllGlobals(); vi.resetModules(); });
describe('language preference and translation', () => {
  it('defaults to English even on an Italian browser and ignores invalid stored preferences', async () => {
    vi.stubGlobal('navigator', { language: 'it-IT' });
    vi.stubGlobal('localStorage', { getItem: () => 'fr' });
    const i18n = await load();
    expect(i18n?.getLanguage()).toBe('en');
  });
  it('persists Italian and restores it after a reload', async () => {
    const stored = new Map<string, string>();
    vi.stubGlobal('localStorage', { getItem: (key: string) => stored.get(key), setItem: (key: string, value: string) => stored.set(key, value) });
    const i18n = await load();
    expect(i18n).not.toBeNull();
    i18n!.setLanguage('it');
    expect(i18n!.t('Impostazioni')).toBe('Impostazioni');
    vi.resetModules();
    const restored = await load();
    expect(restored!.getLanguage()).toBe('it');
    restored!.setLanguage('en');
    expect(restored!.t('Impostazioni')).toBe('Settings');
  });
  it('interpolates literal user data without translating or interpreting it', async () => {
    const i18n = await load();
    expect(i18n?.translate('Scegli la foto di {0}', 'en', {0: 'Casa <b>{1}</b>'})).toBe('Choose a photo for Casa <b>{1}</b>');
  });
  it('uses English for unsupported languages and preserves unknown messages', async () => {
    const i18n = await load();
    expect(i18n?.translate('Impostazioni', 'xx')).toBe('Settings');
    expect(i18n?.translate('custom server message', 'it')).toBe('custom server message');
  });
  it('notifies subscribers without a reload, and keeps the preference when storage is blocked', async () => {
    vi.stubGlobal('localStorage', { getItem() { throw new Error('blocked'); }, setItem() { throw new Error('blocked'); } });
    const i18n = await load();
    expect(i18n).not.toBeNull();
    let observed = '';
    const unsubscribe = i18n!.subscribeLanguage(() => { observed = i18n!.getLanguage(); });
    i18n!.setLanguage('it');
    expect(observed).toBe('it');
    expect(i18n!.getLocale()).toBe('it-IT');
    unsubscribe();
    i18n!.setLanguage('en');
    expect(observed).toBe('it');
  });
  it('has complete nonempty dictionaries with matching interpolation parameters', async () => {
    const i18n = await load();
    expect(i18n).not.toBeNull();
    expect(Object.keys(i18n!.messages.en).length).toBeGreaterThan(500);
    expect(Object.keys(i18n!.messages.en).sort()).toEqual(Object.keys(i18n!.messages.it).sort());
    const parameters = (value: string) => [...value.matchAll(/\{(\w+)\}/g)].map(match => match[1]).sort();
    for (const key of Object.keys(i18n!.messages.en)) {
      expect(i18n!.messages.en[key].trim(), key).not.toBe('');
      expect(parameters(i18n!.messages.en[key]), key).toEqual(parameters(i18n!.messages.it[key]));
    }
  });
});
it('retranslates stored application notices after a language change without altering unknown text', async () => {
  const i18n = await load();
  expect(i18n?.translateMessage?.('Photo updated.')).toBe('Photo updated.');
  i18n!.setLanguage('it');
  expect(i18n?.translateMessage?.('Photo updated.')).toBe('Foto aggiornata.');
  expect(i18n?.translateMessage?.('Personal message: Casa')).toBe('Personal message: Casa');
});
