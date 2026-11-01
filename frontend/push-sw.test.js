import { it, expect } from 'vitest';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';
const code = readFileSync(new URL('./public/push-sw.js', import.meta.url), 'utf8');
it('shows private push content and opens only local authorized routes', async () => {
  const handlers = {}, notifications = [], opened = [];
  const self = {
    addEventListener: (type, handler) => {handlers[type] = handler;},
    registration: {showNotification: (...args) => {notifications.push(args); return Promise.resolve();}},
    location: {origin: 'https://split.example'},
    clients: {matchAll: async () => [], openWindow: async url => {opened.push(url);}},
  };
  vm.runInNewContext(code, {self, URL});
  let work;
  handlers.push({data: {json: () => ({body: 'Private amount €100', url: '/expenses/42', tag: 'event'})}, waitUntil: promise => {work = promise;}});
  await work;
  expect(notifications[0][1].body).toBe('Una nuova spesa ti coinvolge.');
  expect(notifications[0][1].data.url).toBe('/expenses/42');
  handlers.notificationclick({notification: {data: {url: 'https://evil.example/'}, close() {}}, waitUntil: promise => {work = promise;}});
  await work;
  expect(opened).toEqual(['https://split.example/profile']);
});
it('shows a fallback notification for null and malformed payloads', async () => {
  const handlers = {}, notifications = [];
  const self = {addEventListener: (type, handler) => {handlers[type] = handler;}, registration: {showNotification: (...args) => {notifications.push(args); return Promise.resolve();}}};
  vm.runInNewContext(code, {self, URL});
  for (const data of [{json: () => null}, {json: () => {throw new Error('bad json');}}]) {
    let work;
    handlers.push({data, waitUntil: promise => {work = promise;}});
    await work;
  }
  expect(notifications).toHaveLength(2);
});
