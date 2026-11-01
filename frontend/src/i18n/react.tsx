import { useEffect, useRef, useSyncExternalStore } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { getLanguage, setLanguage, subscribeLanguage, t } from './index';
export function useLanguage() {
  return useSyncExternalStore(subscribeLanguage, getLanguage, getLanguage);
}
export function LanguageObserver() {
  const language = useLanguage();
  const cache = useQueryClient();
  const previousLanguage = useRef(language);
  useEffect(() => {
    document.documentElement.lang = language;
    document.querySelector('meta[name="description"]')?.setAttribute('content', t('Spese condivise, conti sereni.'));
    document.querySelector('link[rel="manifest"]')?.setAttribute("href", language === "it" ? "/manifest-it.webmanifest" : "/manifest.webmanifest");
    if (previousLanguage.current !== language) {
      previousLanguage.current = language;
      // A pending response in the old language must not overwrite the new labels.
      void cache.cancelQueries().then(() => cache.invalidateQueries());
    }
  }, [language, cache]);
  return null;
}
export function LanguageSelector() {
  const language = useLanguage();
  return <label>{t('Lingua')}<select aria-label={t('Lingua')} value={language} onChange={event => setLanguage(event.target.value === 'it' ? 'it' : 'en')}><option value="en" lang="en">English</option><option value="it" lang="it">Italiano</option></select><small className="muted">{t('La lingua viene salvata su questo dispositivo.')}</small></label>;
}
