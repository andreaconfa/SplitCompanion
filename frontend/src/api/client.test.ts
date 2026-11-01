import { afterEach, expect, it, vi } from 'vitest';
import { api, setCsrf } from './client';
const dispatchEvent = vi.fn();
vi.stubGlobal('navigator', { onLine: true });
vi.stubGlobal('window', { dispatchEvent });
afterEach(() => { vi.restoreAllMocks(); dispatchEvent.mockClear(); setCsrf(''); });
it('keeps the login challenge visible when a second-factor code is rejected', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: 'Invalid code' }), { status: 401 })));
  await expect(api('/auth/mfa/verify', { method: 'POST' })).rejects.toThrow('Invalid code');
  expect(dispatchEvent).not.toHaveBeenCalled();
});
it('retains CSRF after a challenge response and installs it after MFA confirmation', async () => {
  const fetcher = vi.fn()
    .mockResolvedValueOnce(new Response(JSON.stringify({status:'mfa_required', challenge_token:'challenge'})))
    .mockResolvedValueOnce(new Response(JSON.stringify({session:{csrf_token:'verified',timezone:'UTC'},recovery_codes:['code']})))
    .mockResolvedValueOnce(new Response('{}'));
  vi.stubGlobal('fetch', fetcher);
  setCsrf('existing');
  await api('/auth/login', {method:'POST'});
  await api('/auth/mfa/confirm', {method:'POST'});
  await api('/example', {method:'POST'});
  expect(fetcher.mock.calls[1][1].headers.get('X-CSRF-Token')).toBe('existing');
  expect(fetcher.mock.calls[2][1].headers.get('X-CSRF-Token')).toBe('verified');
});
it('keeps password correction in the authenticated form after a rejected current password', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({detail:'Password attuale non corretta'}), {status:401})));
  await expect(api('/auth/password', {method:'POST',body:JSON.stringify({current_password:'wrong',new_password:'new-password'})})).rejects.toThrow('Password attuale non corretta');
  expect(dispatchEvent).not.toHaveBeenCalled();
});
it('sends the selected UI language for every API request', async () => {
  const { setLanguage } = await import('../i18n');
  const fetcher = vi.fn().mockImplementation(() => Promise.resolve(new Response('{}')));
  vi.stubGlobal('fetch', fetcher);
  setLanguage('it');
  await api('/meta');
  expect(fetcher.mock.calls[0][1].headers.get('Accept-Language')).toBe('it');
  setLanguage('en');
  await api('/groups', { method: 'POST', body: '{}' });
  expect(fetcher.mock.calls[1][1].headers.get('Accept-Language')).toBe('en');
});
