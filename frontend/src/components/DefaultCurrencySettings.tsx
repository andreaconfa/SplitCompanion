import { useState, type FormEvent } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { ApiError, api, useAction, useApi } from '../api/client';
import type { Session } from '../api/types';
import { t } from '../i18n';
import { useLanguage } from '../i18n/react';
import { Busy, ErrorBox, Loading } from './ui';
interface CurrencySettings { default_currency: string; supported_currencies?: string[]; }
const supportedFallback = ['AED', 'AUD', 'BRL', 'CAD', 'CHF', 'CNY', 'CZK', 'DKK', 'EUR', 'GBP', 'HKD', 'HUF', 'ILS', 'INR', 'MXN', 'NOK', 'NZD', 'PLN', 'RON', 'SEK', 'SGD', 'TRY', 'USD', 'ZAR'];
export function DefaultCurrencySettings() {
  useLanguage();
  const query = useApi<CurrencySettings>('/admin/settings');
  if (query.isPending) return <Loading />;
  if (query.error instanceof ApiError && query.error.status === 404)
    return <p className="settings-footnote">{t('Questa versione del server non supporta la valuta predefinita configurabile.')}</p>;
  if (!query.data) return <ErrorBox error={query.error} />;
  return <CurrencyForm settings={query.data} />;
}
function CurrencyForm({ settings }: {settings: CurrencySettings}) {
  useLanguage();
  const cache = useQueryClient();
  const meta = useApi<{supported_currencies?: string[]}>('/meta');
  const [currency, setCurrency] = useState(settings.default_currency);
  const [saved, setSaved] = useState(false);
  const choices = settings.supported_currencies ?? meta.data?.supported_currencies ?? supportedFallback;
  const action = useAction<string>(value => api<CurrencySettings>('/admin/settings', {method:'PATCH', body:JSON.stringify({default_currency:value})}));
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setSaved(false);
    try {
      const result = await action.mutateAsync(currency) as CurrencySettings;
      cache.setQueryData(['/admin/settings'], result);
      cache.setQueryData<Session>(['/auth/me'], previous => previous ? {...previous, default_currency:result.default_currency} : previous);
      await cache.invalidateQueries({queryKey:['/auth/me']});
      setSaved(true);
    } catch { /* Error is displayed below. */ }
  };
  return <form className="card form-card" onSubmit={submit}>
    <label>{t('Valuta predefinita')}<select aria-label={t('Valuta predefinita')} value={currency} onChange={event => {setCurrency(event.target.value); setSaved(false);}} disabled={action.isPending}>
      {choices.map(value => <option key={value} value={value}>{value}</option>)}
    </select></label>
    <p className="field-hint">{t('Valuta iniziale per le nuove spese e i nuovi abbonamenti. Le valute già salvate non cambiano e gli importi non vengono convertiti.')}</p>
    <ErrorBox error={action.error} />
    {saved && <p role="status">{t('Valuta predefinita aggiornata.')}</p>}
    <Busy busy={action.isPending} label={t('Salva')} />
  </form>;
}
