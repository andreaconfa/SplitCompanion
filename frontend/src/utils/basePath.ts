/** Only backend-rendered Ingress documents may select a mount. Never infer it from the URL. */
export function isIngress(): boolean {
  return typeof document !== 'undefined' && document.querySelector('meta[name="split-ingress"]')?.getAttribute('content') === 'true';
}
export function appBasePath(): string {
  const base = typeof document !== 'undefined' ? document.querySelector('base[href]')?.getAttribute('href') : null;
  return isIngress() && base && /^\/api\/hassio_ingress\/[A-Za-z0-9_-]+\/$/.test(base) ? base : '/';
}
/** Application-owned URL, relative to the explicit server mount, including on deep routes. */
export function appURL(path: string): string {
  return appBasePath() + path.replace(/^\/+/, '');
}
