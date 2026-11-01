import { Brand } from "../components/Brand";
import { useState, type FormEvent } from "react";
import { api } from "../api/client";
import { Button, ErrorBox } from "../components/ui";

export default function Setup({ onComplete }: { onComplete: () => void }) {
  const [token, setToken] = useState("");
  const [username, setUsername] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (busy) return;
    if (password !== confirmation) { setError("Le password non coincidono."); return; }
    setBusy(true);
    setError("");
    try {
      await api("/setup/complete", {
        method: "POST", headers: { "X-Setup-Token": token.trim() },
        body: JSON.stringify({ username, display_name: displayName, password }),
      });
      setToken(""); setPassword(""); setConfirmation("");
      onComplete();
    } catch (reason) { setError((reason as Error).message); }
    finally { setBusy(false); }
  }
  return <div className="login-form-area setup-screen"><Brand /><div className="login-form">
    <span className="eyebrow">BENVENUTO IN SPLITCOMPANION</span>
    <h1>Configura il tuo spazio.</h1>
    <p className="muted">Crea il primo amministratore della tua istanza privata. Gli altri account saranno aggiunti dall’amministratore.</p>
    <p>Incolla il codice ottenuto dal comando di configurazione sul server. Il codice scade dopo 30 minuti.</p>
    <form onSubmit={submit}>
      <label>Codice di configurazione<input type="password" autoComplete="off" value={token} onChange={e => setToken(e.target.value)} required maxLength={256} /></label>
      <label>Nome visualizzato<input autoComplete="name" value={displayName} onChange={e => setDisplayName(e.target.value)} required maxLength={200} /></label>
      <label>Username<input autoComplete="username" autoCapitalize="none" spellCheck={false} value={username} onChange={e => setUsername(e.target.value)} required pattern="[a-zA-Z0-9_.\-]{3,50}" minLength={3} maxLength={50} /></label>
      <label>Password<input type="password" autoComplete="new-password" value={password} onChange={e => setPassword(e.target.value)} required minLength={10} maxLength={256} /></label>
      <label>Conferma password<input type="password" autoComplete="new-password" value={confirmation} onChange={e => setConfirmation(e.target.value)} required minLength={10} maxLength={256} /></label>
      <ErrorBox error={error} />
      <Button type="submit" disabled={busy}>{busy ? "Configurazione in corso…" : "Crea amministratore"}</Button>
    </form>
  </div></div>;
}
