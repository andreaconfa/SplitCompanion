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
