import { afterEach, expect, it, vi } from 'vitest';
import { api, setCsrf } from '../api/client';
import { probeServer } from './server';
import { avatarURL } from './people';

function documentBase(base: string, ingress = true) {
  vi.stubGlobal('document', { querySelector: (selector: string) => ({
    getAttribute: (attribute: string) => selector === 'base[href]' && attribute === 'href' ? base : selector === 'meta[name="split-ingress"]' && attribute === 'content' && ingress ? 'true' : null,
  }) });
  vi.stubGlobal('location', { pathname: '/api/hassio_ingress/untrusted/expenses/new' });
  vi.stubGlobal('navigator', { onLine: true });
}
afterEach(() => { vi.unstubAllGlobals(); setCsrf(''); });
it('keeps API mutations, readiness and avatars inside the server-provided ingress mount', async () => {
  documentBase('/api/hassio_ingress/token_123-/');
  const fetcher = vi.fn().mockImplementation(() => Promise.resolve(new Response('{"status":"ready"}')));
  vi.stubGlobal('fetch', fetcher);
  setCsrf('csrf');
  await api('/auth/logout', { method: 'POST' });
  expect(fetcher.mock.calls[0][0]).toBe('/api/hassio_ingress/token_123-/api/auth/logout');
  expect(fetcher.mock.calls[0][1].headers.get('X-CSRF-Token')).toBe('csrf');
  expect(fetcher.mock.calls[0][1].credentials).toBe('same-origin');
  expect(await probeServer(new AbortController().signal)).toBe('online');
  expect(fetcher.mock.calls[1][0]).toBe('/api/hassio_ingress/token_123-/api/ready');
  expect(avatarURL(2, 'v1')).toBe('/api/hassio_ingress/token_123-/api/users/2/avatar?v=v1');
});
it('does not infer an ingress mount from the route, an unmarked base, or malformed base', async () => {
  const fetcher = vi.fn().mockImplementation(() => Promise.resolve(new Response('{}')));
  vi.stubGlobal('fetch', fetcher);
  for (const [base, ingress] of [['/api/hassio_ingress/token/', false], ['/anything/', true], ['//host/api/hassio_ingress/token/', true], ['/api/hassio_ingress/../', true], ['/api/hassio_ingress/%2f/', true], ['/', true]] as const) {
    documentBase(base, ingress);
    await api('/auth/me');
    expect(fetcher.mock.lastCall?.[0]).toBe('/api/auth/me');
    expect(avatarURL(2, 'v1')).toBe('/api/users/2/avatar?v=v1');
  }
});
