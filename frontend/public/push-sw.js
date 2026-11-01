/* Imported by Workbox: push never caches or fetches authenticated API data. */
self.addEventListener('push', event => {
  let payload = {};
  try { payload = event.data ? event.data.json() : {}; } catch (_) { /* generic fallback */ }
  if (!payload || typeof payload !== 'object') payload = {};
  const url = typeof payload.url === 'string' && /^\/expenses\/\d+$/.test(payload.url) ? payload.url : '/profile';
  event.waitUntil(self.registration.showNotification('Split Companion', {
    body: url === '/profile' ? 'Le notifiche su questo dispositivo sono attive.' : 'Una nuova spesa ti coinvolge.',
    icon: '/icon-192.png', badge: '/icon-192.png',
    tag: typeof payload.tag === 'string' ? payload.tag.slice(0, 100) : 'split-update',
    data: {url},
  }));
});
self.addEventListener('notificationclick', event => {
  event.notification.close();
  const candidate = event.notification.data?.url;
  const path = typeof candidate === 'string' && /^\/expenses\/\d+$/.test(candidate) ? candidate : '/profile';
  const url = new URL(path, self.location.origin).href;
  event.waitUntil(self.clients.matchAll({type: 'window', includeUncontrolled: true}).then(async clients => {
    for (const client of clients) {
      if (new URL(client.url).origin === self.location.origin && 'navigate' in client) {
        await client.navigate(url); return client.focus();
      }
    }
    return self.clients.openWindow(url);
  }));
});
