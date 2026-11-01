import { afterEach, expect, it } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import { createMemoryRouter, RouterProvider } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ExpenseForm, SubscriptionForm } from '../pages/ExpenseForm';
import { DataContext, SessionContext } from '../components/context';
import { setLanguage } from './index';
import { money, today, configureTimezone } from '../utils/money';
import type { Session } from '../api/types';

afterEach(() => setLanguage('en'));
function renderForm(recurring: boolean, defaultCurrency?: string, existingCurrency?: string) {
  const session = { user: { id: 1, username: 'alex', display_name: 'Casa', is_admin: true, is_active: true }, csrf_token: 'token', timezone: 'UTC', default_currency: defaultCurrency } as Session;
  const cache = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  cache.setQueryData(['/categories'], []);
  cache.setQueryData(['/groups/1/members'], [{ user_id: 1, display_name: 'Casa', active: true }]);
  const resource = recurring ? 'subscriptions' : 'expenses';
  if (existingCurrency) cache.setQueryData(['/' + resource + '/42'], {id: 42, group_id: 1, currency: existingCurrency, description: 'Spesa originale', name: 'Nome originale', amount_cents: 1234, splits: [{ user_id: 1, amount_cents: 1234 }], paid_by_user_id: 1, expense_date: '2026-01-02', start_date: '2026-01-02', recurrence_rule: 'FREQ=MONTHLY;INTERVAL=1', source: 'NATIVE'});
  const router = createMemoryRouter([{ path: '/' + resource + '/:id?', element: recurring ? <SubscriptionForm /> : <ExpenseForm /> }], { initialEntries: ['/' + resource + (existingCurrency ? '/42' : '')] });
  const html = renderToStaticMarkup(<QueryClientProvider client={cache}><SessionContext.Provider value={{session, logout: async () => {}, invalidate: () => {}}}><DataContext.Provider value={{users:[session.user], groups:[{id:1,name:'Casa',archived:false} as never]}}><RouterProvider router={router} /></DataContext.Provider></SessionContext.Provider></QueryClientProvider>);
  router.dispose(); cache.clear(); return html;
}
it('initializes both creation forms from the server default currency and falls back for older servers', () => {
  for (const recurring of [false,true]) {
    expect(renderForm(recurring, 'USD')).toContain('value="USD"');
    expect(renderForm(recurring)).toContain('value="EUR"');
  }
});
it('preserves saved currency and user descriptions in both UI languages', () => {
  for (const language of ['en','it'] as const) {
    setLanguage(language);
    for (const recurring of [false,true]) {
      const html = renderForm(recurring, 'USD', 'CHF');
      expect(html).toContain('value="CHF"');
      expect(html).toContain(recurring ? 'Nome originale' : 'Spesa originale');
      expect(html).toContain('Casa');
    }
  }
});
it('renders translated form headings and accessibility labels', () => {
  setLanguage('en');
  expect(renderForm(false)).toContain('New expense');
  expect(renderForm(true)).toContain('Create subscription');
  setLanguage('it');
  expect(renderForm(false)).toContain('Nuova spesa');
  expect(renderForm(true)).toContain('Crea abbonamento');
});
it('changes formatting without changing currency, integer amounts or the installation date', () => {
  configureTimezone('Pacific/Honolulu');
  const instant = new Date('2026-10-01T00:00:00Z');
  setLanguage('en');
  expect(money(123456, 'USD')).toBe('$1,234.56');
  expect(today(instant)).toBe('2026-09-30');
  setLanguage('it');
  expect(money(123456, 'USD')).toContain('1234,56');
  expect(today(instant)).toBe('2026-09-30');
  configureTimezone('Europe/Rome');
});
it('uses server defaults for manual settlements and the debt currency for suggested settlements', async () => {
  const {PaymentForm} = await import('../pages/Groups');
  const cache = new QueryClient();
  cache.setQueryData(['/groups/1/members'], [{user_id:1,display_name:'Alex',active:true},{user_id:2,display_name:'Bea',active:true}]);
  const session = {user:{id:1,display_name:'Alex'},default_currency:'USD'} as Session;
  const renderPayment = (currency?: string) => renderToStaticMarkup(<QueryClientProvider client={cache}><SessionContext.Provider value={{session,logout:async()=>{},invalidate:()=>{}}}><DataContext.Provider value={{users:[],groups:[]}}><PaymentForm members={[{id:1,user_id:1,display_name:"Alex",username:"alex",active:true},{id:2,user_id:2,display_name:"Bea",username:"bea",active:true}]} groupId={1} debt={currency ? {paid_by_user_id:1,paid_to_user_id:2,amount_cents:1000,currency} : null} onClose={()=>{}} /></DataContext.Provider></SessionContext.Provider></QueryClientProvider>);
  expect(renderPayment()).toContain('value="USD"');
  expect(renderPayment('CHF')).toContain('value="CHF"');
  cache.clear();
});
