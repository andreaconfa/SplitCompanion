import { t } from "../i18n";
import { useLanguage } from "../i18n/react";
import { useCallback, useRef } from 'react';
import { useBeforeUnload, useBlocker } from 'react-router-dom';
import { Button, Sheet } from './ui';

export function useUnsavedChanges() {
  useLanguage();
  const dirty = useRef(false);
  const blocker = useBlocker(({currentLocation, nextLocation}) => dirty.current && (currentLocation.pathname !== nextLocation.pathname || currentLocation.search !== nextLocation.search));
  useBeforeUnload(useCallback(event => { if (dirty.current) { event.preventDefault(); event.returnValue = ''; } }, []));
  const markDirty = () => { dirty.current = true; };
  const markSaved = () => { dirty.current = false; };
  const dialog = blocker.state === 'blocked' ? <Sheet title={t("Modifiche non salvate")} onClose={() => blocker.reset()}>
    <p className="muted">{t("Vuoi uscire senza salvare? Le modifiche a questo modulo andranno perse.")}</p>
    <div className="form-actions"><Button variant="secondary" onClick={() => blocker.reset()}>{t("Continua a modificare")}</Button><Button variant="danger" onClick={() => { dirty.current = false; blocker.proceed(); }}>{t("Esci senza salvare")}</Button></div>
  </Sheet> : null;
  return { markDirty, markSaved, dialog };
}
