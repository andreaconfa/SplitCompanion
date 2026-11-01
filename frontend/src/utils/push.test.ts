import { describe, expect, it } from 'vitest';
import { pushSupport, applicationKey } from './push';
describe('push capability', () => {
  it('explains HTTPS, unsupported browser, permission blocks and readiness', () => {
    expect(pushSupport(false, true, 'default')).toContain('HTTPS');
    expect(pushSupport(true, false, 'default')).toContain('supporta');
    expect(pushSupport(true, true, 'denied')).toContain('bloccate');
    expect(pushSupport(true, true, 'default')).toBe('');
  });
  it('decodes URL-safe application keys', () => {
    expect([...applicationKey('AQID-_8')]).toEqual([1, 2, 3, 251, 255]);
  });
});
