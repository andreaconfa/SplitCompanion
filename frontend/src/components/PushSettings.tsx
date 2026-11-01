import { useEffect, useState } from 'react';
import { Bell, BellOff, Send } from 'lucide-react';
import { api } from '../api/client';
import { Button, ErrorBox, Section } from './ui';
import { applicationKey, pushSupport } from '../utils/push';

export function PushSettings() {
  const available = 'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window;
  const [permission, setPermission] = useState<NotificationPermission>(available ? Notification.permission : 'default');
  const [enabled, setEnabled] = useState(false);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(available && window.isSecureContext);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const reason = pushSupport(window.isSecureContext, available, permission);
  const request = <T,>(path: string, method: string, body: unknown) => api<T>('/push/' + path, {method, body: JSON.stringify(body)});
  useEffect(() => {
    if (!available || !window.isSecureContext) return;
    let alive = true;
    navigator.serviceWorker.getRegistration().then(async reg => {
      const sub = await reg?.pushManager.getSubscription();
      if (sub) {
        const result = await request<{enabled: boolean}>('status', 'POST', {endpoint: sub.endpoint});
        if (alive) setEnabled(result.enabled);
      }
    }).catch(e => {if (alive) setError(e.message);}).finally(() => {if (alive) setLoading(false);});
    return () => {alive = false;};
  }, [available]);
  async function act(action: 'enable' | 'disable' | 'test') {
    setBusy(true); setError(''); setMessage('');
    try {
      // Request permission directly from the user's click (required on iOS).
      if (action === 'enable') {
        const result = await Notification.requestPermission();
        setPermission(result);
        if (result !== 'granted') throw new Error('Permesso non concesso. Puoi riprovare dalle impostazioni del dispositivo.');
      }
      const reg = await navigator.serviceWorker.getRegistration();
      if (!reg?.active) throw new Error('L’app sta preparando le notifiche. Ricarica la pagina e riprova.');
      let sub = await reg.pushManager.getSubscription();
      if (action === 'enable') {
        const cfg = await api<{public_key: string}>('/push/config');
        // A new opt-in replaces any obsolete subscription from a previous account.
        if (sub) {await sub.unsubscribe(); sub = null;}
        sub = await reg.pushManager.subscribe({userVisibleOnly: true, applicationServerKey: applicationKey(cfg.public_key)});
        try {await request('subscriptions', 'POST', sub.toJSON());}
        catch(e) {await sub.unsubscribe(); throw e;}
        setEnabled(true); setMessage('Notifiche attive su questo dispositivo.');
      } else if (action === 'disable') {
        if (sub) {await request('subscriptions', 'DELETE', {endpoint: sub.endpoint}); await sub.unsubscribe();}
        setEnabled(false); setMessage('Notifiche disattivate su questo dispositivo.');
      } else {
        if (!sub) throw new Error('Attiva prima le notifiche.');
        await request('test', 'POST', {endpoint: sub.endpoint});
        setMessage('Test in coda: la notifica dovrebbe arrivare tra pochi secondi.');
      }
    } catch(e) {setError((e as Error).message);}
    finally {setBusy(false);}
  }
  return <Section title="Notifiche"><div className="card form-card">
    <div className="row-title"><Bell size={20}/><strong>{enabled ? 'Attive su questo dispositivo' : 'Le spese che ti coinvolgono'}</strong></div>
    <p className="muted">Ricevi un avviso per nuove spese e scadenze condivise, anche quando l’app è chiusa. Sulla schermata di blocco non mostriamo importi o nomi.</p>
    {reason && <p className="field-hint">{reason}</p>}
    <ErrorBox error={error}/>
    {message && <p role="status">{message}</p>}
    <div className="form-actions">
      <Button disabled={busy || loading || (!enabled && !!reason)} variant={enabled ? 'secondary' : 'primary'} onClick={() => act(enabled ? 'disable' : 'enable')}>
        {enabled ? <BellOff size={18}/> : <Bell size={18}/>} {busy ? 'Attendi…' : loading ? 'Verifica…' : enabled ? 'Disattiva' : 'Attiva su questo dispositivo'}
      </Button>
      {enabled && <Button variant="secondary" disabled={busy} onClick={() => act('test')}><Send size={18}/>Invia un test</Button>}
    </div>
    <p className="field-hint">La consegna dipende da browser, connessione e risparmio energetico e non è garantita. Su iPhone/iPad serve iOS 16.4+ e l’app installata nella Home. Per aprire la spesa, il tuo indirizzo di Split Companion deve essere raggiungibile. Dopo l’uscita, riattiva le notifiche dal profilo.</p>
  </div></Section>;
}
