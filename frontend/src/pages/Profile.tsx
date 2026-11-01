import { AvatarEditor } from "../components/AvatarEditor";
import { Person, PeopleDisplaySelector } from "../components/Person";
import { PasswordSettings } from "../components/PasswordSettings";
import { MfaSettings } from "../components/Mfa";
import { PushSettings } from "../components/PushSettings";
import { AccentSelector, ThemeSelector } from "../components/ThemeSelector";
import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import {
  ShieldCheck,
  Tags,
  Upload,
  Users,
  LogOut,
  ChevronRight,
  Plus,
  Pencil,
  LockKeyhole,
  CircleUserRound,
  CalendarClock,
} from "lucide-react";
import { useData, useSession } from "../components/context";
import { useApi, useAction, send } from "../api/client";
import type { User } from "../api/types";
import {
  PageHead,
  Button,
  ErrorBox,
  Sheet,
  Busy,
  Section,
} from "../components/ui";
import "./Profile.css";

export default function Profile() {
  const { session, logout } = useSession();
  const meta = useApi<{server_version: string; source_available?: boolean}>("/meta");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  return (
    <div className="profile-settings">
      <PageHead
        eyebrow="IL TUO SPAZIO"
        title="Impostazioni"
        description="Account, sicurezza e preferenze."
      />
      <Section title="Account">
        <div className="settings-group">
          <div className="settings-identity">
            <h2><Person user={session.user} forceName /></h2>
            <div className="settings-identity-meta">
              <span>@{session.user.username}</span>
              <span>{session.user.is_admin ? "Amministratore" : "Membro"}</span>
            </div>
          </div>
          <details className="settings-disclosure">
            <summary className="settings-row">
              <span className="settings-icon"><CircleUserRound size={20} /></span>
              <span className="settings-row-main"><strong>Foto profilo</strong><span>La tua foto, su tutti i dispositivi</span></span>
              <ChevronRight className="settings-chevron" size={18} />
            </summary>
            <div className="settings-detail"><AvatarEditor user={session.user} /></div>
          </details>
          <details className="settings-disclosure">
            <summary className="settings-row">
              <span className="settings-icon"><LockKeyhole size={20} /></span>
              <span className="settings-row-main"><strong>Password e sicurezza</strong><span>Password e verifica in due passaggi</span></span>
              <ChevronRight className="settings-chevron" size={18} />
            </summary>
            <div className="settings-detail settings-security"><PasswordSettings /><MfaSettings /></div>
          </details>
          <Link className="settings-row" to="/subscriptions">
            <span className="settings-icon"><CalendarClock size={20} /></span>
            <span className="settings-row-main"><strong>Gestisci abbonamenti</strong><span>Scadenze e spese ricorrenti</span></span>
            <ChevronRight className="settings-chevron" size={18} />
          </Link>
        </div>
      </Section>
      <Section title="Aspetto">
        <div className="settings-group settings-appearance">
          <div className="settings-preference"><PeopleDisplaySelector /></div>
          <div className="settings-preference"><ThemeSelector /></div>
          <div className="settings-preference"><AccentSelector /></div>
        </div>
        <p className="settings-footnote">Personalizza l’aspetto su questo dispositivo.</p>
      </Section>
      <div className="settings-notifications"><PushSettings /></div>
      {session.user.is_admin && (
        <Section title="Amministrazione">
          <div className="settings-group">
            <Link className="settings-row" to="/admin/categories">
              <span className="settings-icon"><Tags size={20} /></span>
              <span className="settings-row-main"><strong>Categorie</strong><span>Nomi e icone per tutte le spese</span></span>
              <ChevronRight className="settings-chevron" size={18} />
            </Link>
            <Link className="settings-row" to="/admin/users">
              <span className="settings-icon"><Users size={20} /></span>
              <span className="settings-row-main"><strong>Gestione utenti</strong><span>Persone, accessi e password</span></span>
              <ChevronRight className="settings-chevron" size={18} />
            </Link>
            <Link className="settings-row" to="/admin/imports">
              <span className="settings-icon"><Upload size={20} /></span>
              <span className="settings-row-main"><strong>Importa da Splitwise</strong><span>Porta con te il vostro storico</span></span>
              <ChevronRight className="settings-chevron" size={18} />
            </Link>
          </div>
        </Section>
      )}
      <Section title="Informazioni">
        <div className="settings-group">
          <div className="settings-row settings-version"><strong>Versione</strong><span>{meta.data?.server_version ?? "—"}</span></div>
          {meta.data?.source_available && <a className="settings-row" href="/api/source"><strong>Codice sorgente · AGPL-3.0</strong><ChevronRight size={18} /></a>}
          <div className="settings-about"><strong>Split Companion</strong><p>Il tuo server, le tue spese.</p><p>Accesso protetto. I tuoi dati restano sulla vostra installazione.</p></div>
        </div>
      </Section>
      <div className="settings-session">
        <ErrorBox error={error} />
        <Button
          variant="secondary"
          disabled={busy}
          onClick={async () => {
            setBusy(true);
            try {
              await logout();
            } catch (e) {
              setError((e as Error).message);
              setBusy(false);
            }
          }}
        >
          <LogOut size={18} /> Esci
        </Button>
      </div>
    </div>
  );
}

export function AdminUsers() {
  const { users } = useData();
  const { session } = useSession();
  const [edit, setEdit] = useState<User | null | false>(false);
  if (!session.user.is_admin)
    return <ErrorBox error="Questa pagina è riservata agli amministratori." />;
  return (
    <>
      <PageHead
        eyebrow="AMMINISTRAZIONE"
        title="Le persone"
        description="Gestisci chi può accedere a Split Companion."
        back="/profile"
        action={
          <Button onClick={() => setEdit(null)}>
            <Plus size={18} /> Utente
          </Button>
        }
      />
      <div className="card">
        {users.map((user) => (
          <div className="list-row" key={user.id}>
            <div className="row-main">
              <strong><Person user={user} /></strong>
              <span>
                @{user.username}
                {!user.is_active ? " · Disabilitato" : ""}
                {user.is_admin ? " · Amministratore" : ""}
              </span>
            </div>
            <button
              className="icon-button"
              aria-label={"Modifica " + user.display_name}
              onClick={() => setEdit(user)}
            >
              <Pencil size={18} />
            </button>
          </div>
        ))}
      </div>
      {edit !== false && (
        <UserForm user={edit} onClose={() => setEdit(false)} />
      )}
    </>
  );
}
function UserForm({
  user,
  onClose,
}: {
  user: User | null;
  onClose: () => void;
}) {
  const [username, setUsername] = useState(user?.username ?? "");
  const [name, setName] = useState(user?.display_name ?? "");
  const [password, setPassword] = useState("");
  const [admin, setAdmin] = useState(user?.is_admin ?? false);
  const [active, setActive] = useState(user?.is_active ?? true);
  const action = useAction(async (body: unknown) =>
    send("/users" + (user ? "/" + user.id : ""), user ? "PATCH" : "POST", body),
  );
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    const body = user
      ? {
          display_name: name.trim(),
          is_admin: admin,
          is_active: active,
          ...(password ? { password } : {}),
        }
      : {
          username: username.trim(),
          display_name: name.trim(),
          password,
          is_admin: admin,
        };
    try {
      await action.mutateAsync(body);
      onClose();
    } catch {
      /* rendered */
    }
  };
  return (
    <Sheet
      title={user ? "Modifica utente" : "Aggiungi una persona"}
      onClose={onClose}
    >
      {user && <div className="form-card"><AvatarEditor user={user} /></div>}
      <form className="form-card" onSubmit={submit}>
        <label>
          Username
          <input
            value={username}
            autoComplete="off"
            required
            disabled={!!user}
            minLength={3}
            maxLength={50}
            pattern="[a-zA-Z0-9_.-]+"
            onChange={(e) => setUsername(e.target.value)}
          />
        </label>
        <label>
          Nome visualizzato
          <input
            value={name}
            required
            maxLength={100}
            onChange={(e) => setName(e.target.value)}
          />
        </label>
        <label>
          {user
            ? "Nuova password (lascia vuoto per conservarla)"
            : "Password iniziale"}
          <input
            type="password"
            value={password}
            autoComplete="new-password"
            minLength={10}
            required={!user}
            onChange={(e) => setPassword(e.target.value)}
          />
        </label>
        <p className="field-hint">
          Almeno 10 caratteri. Condividi la password in modo sicuro.
        </p>
        <label className="checkbox-line">
          <input
            type="checkbox"
            checked={admin}
            onChange={(e) => setAdmin(e.target.checked)}
          />
          <ShieldCheck size={18} /> Amministratore
        </label>
        {user && (
          <label className="checkbox-line">
            <input
              type="checkbox"
              checked={active}
              onChange={(e) => setActive(e.target.checked)}
            />{" "}
            Utente attivo
          </label>
        )}
        <ErrorBox error={action.error} />
        <Busy
          busy={action.isPending}
          label={user ? "Salva modifiche" : "Crea utente"}
        />
      </form>
    </Sheet>
  );
}
