import { t } from "../i18n";
import { useLanguage } from "../i18n/react";
import { useCallback, useEffect, useRef, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { Server, RefreshCw, CircleCheck, WifiOff, LoaderCircle } from 'lucide-react';
import { probeServer, type ServerStatus as Status } from '../utils/server';
import { Sheet } from './ui';

const labels = { checking: 'Verifica in corso', online: 'Disponibile', offline: 'Non raggiungibile' };
export function ServerStatus() {
  useLanguage();
  const [status, setStatus] = useState<Status>('checking');
  const [open, setOpen] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const current = useRef<AbortController | null>(null);
  const cache = useQueryClient();
  const check = useCallback(async () => {
    current.current?.abort();
    const controller = new AbortController();
    current.current = controller;
    const timeout = window.setTimeout(() => controller.abort(), 5000);
    const next = await probeServer(controller.signal);
    clearTimeout(timeout);
    if (current.current === controller) setStatus(next);
  }, []);
  useEffect(() => {
    void check();
    const tick = () => { if (document.visibilityState === 'visible') void check(); };
    const interval = window.setInterval(tick, 30000);
    document.addEventListener('visibilitychange', tick);
    window.addEventListener('online', tick);
    const offline = () => { current.current?.abort(); setStatus('offline'); };
    window.addEventListener('offline', offline);
    return () => { clearInterval(interval); current.current?.abort(); current.current = null; document.removeEventListener('visibilitychange', tick); window.removeEventListener('online', tick); window.removeEventListener('offline', offline); };
  }, [check]);
  const close = useCallback(() => setOpen(false), []);
  const refresh = async () => {
    setRefreshing(true);
    try { await Promise.all([check(), cache.invalidateQueries()]); }
    finally { setRefreshing(false); }
  };
  return <>
    <button type="button" className={`glass-button server-status ${status}`} aria-label={t("Server: {0}", {0: t(labels[status])})} title={t("Server: {0}", {0: t(labels[status])})} onClick={() => setOpen(true)}><Server size={23} /></button>
    {open && <Sheet title={t("Il tuo server")} onClose={close}>
      <div className="server-panel">
        <span className={`server-status-emblem ${status}`}><Server size={32} /></span>
        <h3>{location.hostname}</h3>
        <p className={`server-state ${status}`} role="status">{status === 'checking' ? <LoaderCircle size={18} className="spin" /> : status === 'online' ? <CircleCheck size={18} /> : <WifiOff size={18} />}{t(labels[status])}</p>
        {status === 'offline' && <p className="muted">{t("Controlla la connessione o riprova tra poco.")}</p>}
        <button type="button" className="btn btn-primary" disabled={refreshing} onClick={refresh}><RefreshCw size={18} className={refreshing ? 'spin' : ''} />{refreshing ? t("Aggiornamento…") : t("Aggiorna")}</button>
      </div>
    </Sheet>}
  </>;
}
