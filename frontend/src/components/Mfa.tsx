import { t, translateMessage } from "../i18n";
import { useLanguage } from "../i18n/react";
import { useEffect, useRef, useState, type FormEvent } from 'react';
import { ShieldCheck, Copy, Download } from 'lucide-react';
import { api, useApi } from '../api/client';
import type { Session } from '../api/types';
import { Button, ErrorBox, Loading, Section } from './ui';

export interface MfaChallenge {
  status: 'mfa_required' | 'mfa_setup_required';
  challenge_token: string;
}
interface Setup { secret: string; otpauth_uri: string; qr_svg: string }
interface Recovery { session: Session; recovery_codes: string[] }
function post<T>(path: string, body: unknown) {
  return api<T>(path, {method:'POST', body:JSON.stringify(body)});
}
function CodeField({value,onChange,recovery=false}: {value:string;onChange:(value:string)=>void;recovery?:boolean}) {
  useLanguage();
  return <label>{recovery ? t("Codice di recupero") : t("Codice a 6 cifre")}
    <input autoFocus key={String(recovery)} value={value} onChange={e=>onChange(e.target.value)} required
      inputMode={recovery ? 'text' : 'numeric'} autoComplete={recovery ? 'off' : 'one-time-code'}
      autoCapitalize="none" spellCheck={false} pattern={recovery ? undefined : '[0-9]{6}'}
      maxLength={recovery ? 64 : 6} placeholder={recovery ? 'XXXX-XXXX-XXXX' : '000000'} />
  </label>;
}
export function RecoveryCodes({codes,onDone}: {codes:string[];onDone:()=>void}) {
  useLanguage();
  const [saved,setSaved] = useState(false);
  const [message,setMessage] = useState('');
  const [error,setError] = useState('');
  const title = useRef<HTMLHeadingElement>(null);
  useEffect(()=>{ title.current?.focus(); },[]);
  const content = t("Split Companion — codici di recupero\nOgni codice può essere usato una sola volta.\n\n") + codes.join('\n') + '\n';
  const download = () => {
    const url = URL.createObjectURL(new Blob([content],{type:'text/plain;charset=utf-8'}));
    const anchor = document.createElement('a'); anchor.href=url; anchor.download='split-companion-codici-recupero.txt'; anchor.click();
    setTimeout(()=>URL.revokeObjectURL(url),1000);
  };
  return <div className="mfa-panel">
    <h2 ref={title} tabIndex={-1}>{t("Conserva i codici di recupero")}</h2>
    <p className="muted">{t("Ti permettono di accedere se perdi l’app di autenticazione. Ogni codice funziona una sola volta. Salvali in un gestore di password o in un posto sicuro: non saranno più mostrati.")}</p>
    <ul className="mfa-recovery-codes">{codes.map(code=><li key={code}><code>{code}</code></li>)}</ul>
    <div className="form-actions">
      <Button type="button" variant="secondary" onClick={download}><Download size={17}/>{t("Scarica")}</Button>
      <Button type="button" variant="secondary" onClick={async()=>{try {await navigator.clipboard.writeText(content);setMessage(t("Codici copiati."));setError('');} catch {setError(t("Copia non disponibile. Scarica i codici o copiali manualmente."));}}}><Copy size={17}/>{t("Copia")}</Button>
    </div>
    <ErrorBox error={error}/>{message && <p role="status">{translateMessage(message)}</p>}
    <label className="checkbox-line"><input type="checkbox" checked={saved} onChange={e=>setSaved(e.target.checked)}/>{t("Ho salvato i codici in un posto sicuro")}</label>
    <Button type="button" disabled={!saved} onClick={onDone}>{t("Continua")}</Button>
  </div>;
}
export function MfaChallengeForm({challenge,onLogin,onRestart}: {challenge:MfaChallenge;onLogin:(session:Session)=>void;onRestart:()=>void}) {
  useLanguage();
  const enrollment = challenge.status === 'mfa_setup_required';
  const [setup,setSetup] = useState<Setup | null>(null);
  const [recovery,setRecovery] = useState<Recovery | null>(null);
  const [useRecovery,setUseRecovery] = useState(false);
  const [code,setCode] = useState('');
  const [busy,setBusy] = useState(false);
  const [error,setError] = useState('');
  const [expired,setExpired] = useState(false);
  const [setupAttempt,setSetupAttempt] = useState(0);
  const fail = (e:unknown) => {
    const message = (e as Error).message;
    setError(message);
    if (/scadut|expired|invalid.*challenge|challenge.*invalid/i.test(message)) {setExpired(true);setSetup(null);setCode('');}
  };
  useEffect(()=>{
    if (!enrollment) return;
    let active=true;
    setBusy(true);setError('');
    post<Setup>('/auth/mfa/setup',{challenge_token:challenge.challenge_token})
      .then(data=>{if(active)setSetup(data);})
      .catch(e=>{if(active)fail(e);})
      .finally(()=>{if(active)setBusy(false);});
    return ()=>{active=false;};
  },[enrollment,challenge.challenge_token,setupAttempt]);
  const submit = async (e:FormEvent) => {
    e.preventDefault();setBusy(true);setError('');
    try {
      const body={challenge_token:challenge.challenge_token,code:code.trim()};
      if(enrollment) {setRecovery(await post<Recovery>('/auth/mfa/confirm',body));setSetup(null);}
      else onLogin(await post<Session>('/auth/mfa/verify',body));
      setCode('');
    } catch(e) {fail(e);} finally {setBusy(false);}
  };
  if(recovery) return <RecoveryCodes codes={recovery.recovery_codes} onDone={()=>onLogin(recovery.session)}/>;
  return <div className="mfa-panel">
    <span className="eyebrow">{t("PROTEGGI IL TUO ACCESSO")}</span>
    <h1>{enrollment ? t("Attiva la verifica in due passaggi.") : t("Un ultimo passaggio.")}</h1>
    {!expired && <>
      <p className="muted">{enrollment ? t("Aggiungi Split Companion a un’app di autenticazione TOTP, come Google Authenticator o Microsoft Authenticator per Android e iPhone, oppure 2FAS. I codici funzionano anche senza connessione.") : useRecovery ? t("Inserisci uno dei codici salvati durante l’attivazione. Dopo questo accesso non potrai riutilizzarlo.") : t("Apri la tua app di autenticazione e inserisci il codice di Split Companion.")}</p>
      {enrollment && !setup && busy && <Loading/>}
      {setup && <>
        <img className="mfa-qr" src={'data:image/svg+xml;charset=utf-8,'+encodeURIComponent(setup.qr_svg)} alt={t("QR per configurare l’app di autenticazione")}/>
        <p className="field-hint">{t("Scansiona il QR nell’app. Se sei sullo stesso telefono, aggiungi manualmente un account con questa chiave e scegli codici basati sul tempo (TOTP).")}</p>
        <label>{t("Chiave di configurazione")}<input readOnly value={setup.secret} autoComplete="off" onFocus={e=>e.target.select()}/></label>
        <p className="field-hint">{t("Conferma con un codice generato dall’app per completare l’attivazione.")}</p>
      </>}
      {(!enrollment || setup) && <form onSubmit={submit}>
        <CodeField value={code} onChange={setCode} recovery={useRecovery}/>
        <Button type="submit" disabled={busy}>{busy ? t("Verifica in corso…") : enrollment ? t("Conferma e attiva") : t("Verifica e accedi")}</Button>
      </form>}
      {!enrollment && <Button type="button" variant="ghost" disabled={busy} onClick={()=>{setUseRecovery(!useRecovery);setCode('');setError('');}}>{useRecovery ? t("Usa l’app di autenticazione") : t("Usa un codice di recupero")}</Button>}
    </>}
    <ErrorBox error={error}/>
    {expired && <p className="muted">{t("La richiesta di accesso è scaduta. Riparti da username e password.")}</p>}
    {!expired && enrollment && !setup && !busy && <Button type="button" variant="secondary" onClick={()=>setSetupAttempt(value=>value+1)}>{t("Riprova configurazione")}</Button>}
    <Button type="button" variant="ghost" disabled={busy} onClick={onRestart}>{t("Torna all’accesso")}</Button>
  </div>;
}
export function MfaSettings() {
  useLanguage();
  const status = useApi<{enabled:boolean;required:boolean;recovery_codes_remaining:number}>('/auth/mfa/status');
  const [editing,setEditing] = useState(false);
  const [password,setPassword] = useState('');
  const [code,setCode] = useState('');
  const [codes,setCodes] = useState<string[] | null>(null);
  const [busy,setBusy] = useState(false);
  const [error,setError] = useState('');
  const regenerate = async (event:FormEvent) => {
    event.preventDefault();setBusy(true);setError('');
    try {
      const result=await post<{recovery_codes:string[]}>('/auth/mfa/recovery-codes',{password,code});
      setCodes(result.recovery_codes);setEditing(false);setPassword('');setCode('');
      void status.refetch();
    } catch(e) {setError((e as Error).message);} finally {setBusy(false);}
  };
  return <Section title={t("Sicurezza")}><div className="card form-card mfa-panel">
    <div className="row-title"><ShieldCheck size={20}/><strong>{t("Verifica in due passaggi")}</strong></div>
    {status.isPending ? <Loading/> : status.data && <>
      <p className="muted">{status.data.enabled ? t("Attiva: ogni accesso richiede la password e un codice della tua app di autenticazione.") : t("Non attiva per questo account.")} {status.data.required && t("Richiesta da questa installazione.")}</p>
      {status.data.enabled && <p className="field-hint">{status.data.recovery_codes_remaining}{" "}{t("codici di recupero disponibili.")}</p>}
      {codes ? <RecoveryCodes codes={codes} onDone={()=>setCodes(null)}/> : editing ? <form onSubmit={regenerate}>
        <p className="muted">{t("I nuovi codici sostituiranno subito tutti quelli precedenti. Conferma con la password e un codice della tua app.")}</p>
        <label>{t("Password attuale")}<input type="password" autoComplete="current-password" value={password} onChange={e=>setPassword(e.target.value)} required/></label>
        <CodeField value={code} onChange={setCode}/>
        <div className="form-actions"><Button type="submit" disabled={busy}>{busy ? t("Generazione…") : t("Sostituisci i codici")}</Button><Button type="button" variant="ghost" disabled={busy} onClick={()=>{setEditing(false);setPassword('');setCode('');setError('');}}>{t("Annulla")}</Button></div>
      </form> : status.data.enabled && <Button type="button" variant="secondary" onClick={()=>setEditing(true)}>{t("Genera nuovi codici")}</Button>}
    </>}
    <ErrorBox error={error || status.error}/>
  </div></Section>;
}
