import { expect, it } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
it('shows the configured server currency and supported choices in the admin form', async () => {
  const module = await import('./DefaultCurrencySettings').catch(() => null);
  expect(module).not.toBeNull();
  const cache = new QueryClient();
  cache.setQueryData(['/admin/settings'], {default_currency:'USD',supported_currencies:['EUR','USD','CHF']});
  const Settings = module!.DefaultCurrencySettings;
  const html = renderToStaticMarkup(<QueryClientProvider client={cache}><Settings /></QueryClientProvider>);
  expect(html).toContain('Default currency');
  expect(html).toContain('value="USD" selected=""');
  expect(html).toContain('CHF');
  expect(html).toContain('amounts are not converted');
  cache.clear();
});
