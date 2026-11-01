import { t } from "../i18n";
import { useLanguage } from "../i18n/react";
import { useCallback, useState, type FormEvent } from 'react';
import { LockKeyhole } from 'lucide-react';
import { api, useApi } from '../api/client';
import { useSession } from './context';
import { Button, ErrorBox, Loading, Section, Sheet } from './ui';

export function PasswordSettings() {
  useLanguage();
  const [editing, setEditing] = useState(false);
  return <Section title={t("Password")}><div className="card form-card">
    <div className="row-title"><LockKeyhole size={20}/><strong>{t("Password dell’account")}</strong></div>
    <p className="muted">{t("Aggiorna la password che usi per accedere.")}</p>
    <Button variant="secondary" onClick={()=>setEditing(true)}>{t("Cambia password")}</Button>
    {editing && <PasswordForm onClose={()=>setEditing(false)}/>}
  </div></Section>;
}
function PasswordForm({onClose}:{onClose:()=>void}) {
  useLanguage();
  const {invalidate} = useSession();
  const status=useApi<{enabled:boolean}>('/auth/mfa/status');
  const [current,setCurrent]=useState('');
  const [password,setPassword]=useState('');
  const [confirm,setConfirm]=useState('');
  const [code,setCode]=useState('');
  const [recovery,setRecovery]=useState(false);
  const [visible,setVisible]=useState(false);
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState('');
  const close=useCallback(()=>{if(!busy)onClose();},[busy,onClose]);
  const submit=async(event:FormEvent)=>{
    event.preventDefault();setError('');
    if(password!==confirm){setError(t("Le password non coincidono."));return;}
    if(!status.data || busy)return;
    setBusy(true);
    try {
      await api('/auth/password',{method:'POST',body:JSON.stringify({current_password:current,new_password:password,...(status.data.enabled?{code:code.trim()}:{})})});
      invalidate(t("Password aggiornata. Accedi di nuovo con la nuova password. Le altre sessioni sono state chiuse."));
    } catch(e){setError((e as Error).message);setBusy(false);}
  };
  return <Sheet title={t("Cambia password")} onClose={close}>
    <form className="form-card" onSubmit={submit}>
      <p className="muted">{t("Dopo il cambio uscirai da tutti i dispositivi. Accedi con la nuova password e riattiva le notifiche push su ciascun dispositivo. La verifica in due passaggi resta attiva se già configurata.")}</p>
      <label>{t("Password attuale")}<input type={visible?'text':'password'} autoComplete="current-password" value={current} onChange={e=>setCurrent(e.target.value)} required maxLength={256} disabled={busy}/></label>
      <label>{t("Nuova password")}<input type={visible?'text':'password'} autoComplete="new-password" value={password} onChange={e=>setPassword(e.target.value)} required minLength={10} maxLength={256} aria-describedby="password-policy" disabled={busy}/></label>
      <p id="password-policy" className="field-hint">{t("Da 10 a 256 caratteri. Scegli una password lunga e diversa da quella attuale.")}</p>
      <label>{t("Conferma nuova password")}<input type={visible?'text':'password'} autoComplete="new-password" value={confirm} onChange={e=>setConfirm(e.target.value)} required minLength={10} maxLength={256} disabled={busy}/></label>
      <label className="checkbox-line"><input type="checkbox" checked={visible} onChange={e=>setVisible(e.target.checked)}/>{t("Mostra password")}</label>
      {status.isPending?<Loading/>:status.data?.enabled && <>
        <p className="field-hint">{t("Conferma con un nuovo codice della tua app o un codice di recupero. Un codice di recupero usato non sarà più disponibile.")}</p>
        <label>{recovery?t("Codice di recupero"):t("Codice a 6 cifre")}<input value={code} onChange={e=>setCode(e.target.value)} required inputMode={recovery?'text':'numeric'} autoComplete={recovery?'off':'one-time-code'} autoCapitalize="none" spellCheck={false} pattern={recovery?undefined:'[0-9]{6}'} maxLength={recovery?64:6} disabled={busy}/></label>
        <Button type="button" variant="ghost" disabled={busy} onClick={()=>{setRecovery(!recovery);setCode('');setError('');}}>{recovery?t("Usa l’app di autenticazione"):t("Usa un codice di recupero")}</Button>
      </>}
      <ErrorBox error={error || status.error}/>
      {status.isError && <Button type="button" variant="secondary" onClick={()=>void status.refetch()}>{t("Riprova verifica sicurezza")}</Button>}
      <div className="form-actions"><Button type="submit" disabled={busy || !status.data}>{busy?t("Salvataggio…"):t("Salva nuova password")}</Button><Button type="button" variant="ghost" disabled={busy} onClick={onClose}>{t("Annulla")}</Button></div>
    </form>
  </Sheet>;
}
