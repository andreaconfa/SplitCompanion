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
  expect(notifications[0][1].body).toBe('A new expense involves you.');
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
it('uses the payload language, defaults to English and keeps notification content private', async () => {
  const handlers = {}, notifications = [];
  const self = { addEventListener: (type, handler) => {handlers[type] = handler;}, registration: {showNotification: (...args) => {notifications.push(args); return Promise.resolve();}} };
  vm.runInNewContext(code, {self, URL});
  for (const language of [undefined, 'it', 'fr']) {
    let work;
    handlers.push({data: {json: () => ({language, url:'/expenses/1', body:'Secret amount'})}, waitUntil: promise => {work = promise;}});
    await work;
  }
  expect(notifications.map(value => value[1].body)).toEqual(['A new expense involves you.', 'Una nuova spesa ti coinvolge.', 'A new expense involves you.']);
});
