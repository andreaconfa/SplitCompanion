import { afterEach, expect, it, vi } from 'vitest';
import { probeServer } from './server';
afterEach(() => vi.unstubAllGlobals());
it('reports available only for a successful ready response', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => ({status:'ready'}) }));
  expect(await probeServer(new AbortController().signal)).toBe('online');
});
it('rejects a captive portal or unavailable backend', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => ({status:'ok'}) }));
  expect(await probeServer(new AbortController().signal)).toBe('offline');
  vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('network')));
  expect(await probeServer(new AbortController().signal)).toBe('offline');
});
it('sends the current UI language to readiness probes too', async () => {
  const {setLanguage} = await import('../i18n');
  const fetcher = vi.fn().mockResolvedValue({ok:true,json:async()=>({status:'ready'})});
  vi.stubGlobal('fetch',fetcher);
  setLanguage('it');
  await probeServer(new AbortController().signal);
  expect(new Headers(fetcher.mock.calls[0][1].headers).get('Accept-Language')).toBe('it');
  setLanguage('en');
});
