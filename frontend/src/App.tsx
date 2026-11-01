import { appURL } from "./utils/basePath";
import { t, translateMessage } from "./i18n";
import { LanguageObserver, LanguageSelector, useLanguage } from "./i18n/react";
import { lazy, Suspense, useState, useEffect, type FormEvent } from "react";
import {
  Routes,
  Navigate,
  Route,
  NavLink,
  Link,
  useNavigate,
  useLocation,
} from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import {
  LayoutGrid,
  ArrowLeftRight,
  Users,
  Plus,
  Repeat2,
  ArrowRight,
  ShieldCheck,
  Settings,
} from "lucide-react";
import { useApi, api, setCsrf, ApiError } from "./api/client";
import Setup from "./pages/Setup";
import { MfaChallengeForm } from "./components/Mfa";
import type { MfaChallenge } from "./components/Mfa";
import type { Session, User, Group } from "./api/types";
import { SessionContext, DataContext } from "./components/context";
import { ThemeObserver, ThemeSelector } from "./components/ThemeSelector";
import { Pwa } from "./components/Pwa";
import { Brand } from "./components/Brand";
import { ServerStatus } from "./components/ServerStatus";
import { Button, ErrorBox, Loading, Sheet } from "./components/ui";
const Dashboard = lazy(() => import("./pages/Dashboard"));
const Groups = lazy(() => import("./pages/Groups"));
const Expenses = lazy(() => import("./pages/Expenses"));
const Subscriptions = lazy(() => import("./pages/Subscriptions"));
const Categories = lazy(() => import("./pages/Categories"));
const Profile = lazy(() => import("./pages/Profile"));
const Imports = lazy(() => import("./pages/Imports"));
const ExpenseForm = lazy(() =>
  import("./pages/ExpenseForm").then((module) => ({
    default: module.ExpenseForm,
  })),
);
const SubscriptionForm = lazy(() =>
  import("./pages/ExpenseForm").then((module) => ({
    default: module.SubscriptionForm,
  })),
);
const GroupDetail = lazy(() =>
  import("./pages/Groups").then((module) => ({ default: module.GroupDetail })),
);
const ExpenseDetail = lazy(() =>
  import("./pages/Expenses").then((module) => ({
    default: module.ExpenseDetail,
  })),
);
const LegacyDetail = lazy(() =>
  import("./pages/Expenses").then((module) => ({
    default: module.LegacyDetail,
  })),
);
const SubscriptionDetail = lazy(() =>
  import("./pages/Subscriptions").then((module) => ({
    default: module.SubscriptionDetail,
  })),
);
const AdminUsers = lazy(() =>
  import("./pages/Profile").then((module) => ({ default: module.AdminUsers })),
);
export default function App() {
  useLanguage();
  const [loginInProgress, setLoginInProgress] = useState(false);
  const [loginMessage, setLoginMessage] = useState("");
  const setup = useApi<{ setup_required: boolean }>("/setup/status");
  const legacyBackend = setup.error instanceof ApiError && setup.error.status === 404;
  const setupReady = setup.data?.setup_required === false || legacyBackend;
  const auth = useApi<Session>("/auth/me", setupReady && !loginInProgress);
  const cache = useQueryClient();
  const navigate = useNavigate();
  useEffect(() => {
    if (auth.data) setCsrf(auth.data.csrf_token);
  }, [auth.data]);
  useEffect(() => {
    const expire = () => {
      setCsrf("");
      cache.clear();
      navigate("/");
    };
    window.addEventListener("session-expired", expire);
    return () => window.removeEventListener("session-expired", expire);
  }, [cache, navigate]);
  const invalidate = (message: string) => {
    setLoginMessage(message);
    setLoginInProgress(true);
    setCsrf("");
    cache.clear();
    navigate("/");
  };
  const logout = async () => {
    await api("/auth/logout", { method: "POST" });
    setCsrf("");
    cache.clear();
    navigate("/");
  };
  return (
    <>
      <ThemeObserver />
      <LanguageObserver />
      <Pwa />
      {setup.isPending ? <div className="app-loading"><Brand /><Loading /></div>
      : setup.error && !legacyBackend ? <div className="app-loading"><Brand /><ErrorBox error={setup.error} /><Button onClick={() => setup.refetch()}>{t("Riprova")}</Button></div>
      : setup.data?.setup_required ? <Setup onComplete={() => {
        cache.setQueryData(["/setup/status"], { setup_required: false });
        setLoginMessage(t("Amministratore creato. Accedi per continuare."));
      }} />
      : auth.isPending && !loginInProgress ? (
        <div className="app-loading">
          <Brand />
          <Loading />
        </div>
      ) : auth.data && !loginInProgress ? (
        <SessionContext.Provider value={{ session: auth.data, logout, invalidate }}>
          <Layout session={auth.data} />
        </SessionContext.Provider>
      ) : (
        <Login
          error={auth.error}
          message={loginMessage}
          onChallenge={setLoginInProgress}
          onLogin={(session) => {
            setLoginMessage("");
            setLoginInProgress(false);
            setCsrf(session.csrf_token);
            cache.setQueryData(["/auth/me"], session);
            navigate("/");
          }}
        />
      )}
    </>
  );
}
function Layout({ session }: { session: Session }) {
  useLanguage();
  const users = useApi<User[]>("/users");
  const groups = useApi<Group[]>("/groups");
  const location = useLocation();
  const [adding, setAdding] = useState(false);
  const nav = [
    { to: "/", label: t("Riepilogo"), mobileLabel: t("Riepilogo"), icon: LayoutGrid },
    { to: "/groups", label: t("Gruppi"), mobileLabel: t("Gruppi"), icon: Users },
    { to: "/expenses", label: t("Movimenti"), mobileLabel: t("Movimenti"), icon: ArrowLeftRight },
    { to: "/subscriptions", label: t("Abbonamenti"), mobileLabel: t("Abbonamenti"), icon: Repeat2 },
    { to: "/profile", label: t("Impostazioni"), mobileLabel: t("Impostazioni"), icon: Settings },
  ];
  useEffect(() => {
    window.scrollTo(0, 0);
  }, [location.pathname]);
  return (
    <DataContext.Provider
      value={{ users: users.data ?? [], groups: groups.data ?? [] }}
    >
      <a className="skip-link" href={appURL(location.pathname + location.search + "#main-content")}>{t("Vai al contenuto")}</a>
      <div className="app-main">
        <header className="app-topbar">
          <Brand />
          <div className="app-tools">
            <button type="button" className="glass-button add-button" aria-label={t("Aggiungi")} title={t("Aggiungi")} onClick={() => setAdding(true)}><Plus size={25} /></button>
            <ServerStatus />
          </div>
        </header>
        <main id="main-content" tabIndex={-1}>

          <ErrorBox error={users.error || groups.error} />
          <Suspense fallback={<Loading />}>
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/groups" element={<Groups />} />
              <Route path="/groups/:id" element={<GroupDetail />} />
              <Route path="/expenses" element={<Expenses />} />
              <Route path="/categories" element={session.user.is_admin ? <Navigate to="/admin/categories" replace /> : <CategoryAccessDenied />} />
              <Route path="/admin/categories" element={session.user.is_admin ? <Categories /> : <CategoryAccessDenied />} />
              <Route path="/expenses/new" element={<ExpenseForm />} />
              <Route path="/expenses/:id" element={<ExpenseDetail />} />
              <Route path="/expenses/:id/edit" element={<ExpenseForm />} />
              <Route path="/legacy/:id" element={<LegacyDetail />} />
              <Route path="/subscriptions" element={<Subscriptions />} />
              <Route path="/subscriptions/new" element={<SubscriptionForm />} />
              <Route
                path="/subscriptions/:id"
                element={<SubscriptionDetail />}
              />
              <Route
                path="/subscriptions/:id/edit"
                element={<SubscriptionForm />}
              />
              <Route path="/profile" element={<Profile />} />
              <Route path="/admin/users" element={<AdminUsers />} />
              <Route path="/admin/imports" element={<Imports />} />
              <Route
                path="*"
                element={
                  <div className="card form-card">
                    <h1>{t("Questa pagina non c’è.")}</h1>
                    <Link to="/" className="btn btn-primary">{t("Torna a casa")}</Link>
                  </div>
                }
              />
            </Routes>
          </Suspense>
        </main>
      </div>
      <nav className="app-navigation" aria-label={t("Navigazione principale")}>
        {nav.map((item) => (
          <NavLink to={item.to} key={item.to} end={item.to === "/"}
            aria-label={item.label} title={item.label}
            className={({ isActive }) => isActive || (item.to === "/profile" && location.pathname.startsWith("/admin")) ? "active" : ""}>
            <span className="nav-icon"><item.icon size={24} /></span>
            <small>{item.mobileLabel}</small>
          </NavLink>
        ))}
      </nav>
      {adding && <Sheet title={t("Aggiungi")} onClose={() => setAdding(false)}>
        <div className="quick-actions">
          {groups.data?.some(group => !group.archived) ? <>
            <Link to="/expenses/new" onClick={() => setAdding(false)}><span className="row-icon"><Plus size={22} /></span><span>{t("Nuova spesa")}<small>{t("Dividi una spesa con il tuo gruppo")}</small></span><ArrowRight size={18} /></Link>
            <Link to="/subscriptions/new" onClick={() => setAdding(false)}><span className="row-icon"><Repeat2 size={22} /></span><span>{t("Nuovo abbonamento")}<small>{t("Organizza una spesa ricorrente")}</small></span><ArrowRight size={18} /></Link>
          </> : <p className="muted">{t("Crea un gruppo per iniziare a condividere le spese.")}</p>}
          <Link to="/groups?new=1" onClick={() => setAdding(false)}><span className="row-icon"><Users size={22} /></span><span>{t("Nuovo gruppo")}<small>{t("Casa, amici o un nuovo viaggio")}</small></span><ArrowRight size={18} /></Link>
        </div>
      </Sheet>}
    </DataContext.Provider>
  );
}
function Login({
  onLogin,
  error: initialError,
  onChallenge,
  message,
}: {
  onLogin: (session: Session) => void;
  error: unknown;
  onChallenge: (active: boolean) => void;
  message: string;
}) {
  useLanguage();
  const [challenge, setChallenge] = useState<MfaChallenge | null>(null);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const session = await api<Session | MfaChallenge>("/auth/login", {
        method: "POST",
        body: JSON.stringify({ username, password }),
      });
      setPassword("");
      if ("challenge_token" in session) {
        onChallenge(true);
        setChallenge(session);
      } else onLogin(session);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="login">
      <div className="login-story">
        <Brand />
        <div className="login-story-content">
          <span className="pill">{t("IL BELLO DI CONDIVIDERE")}</span>
          <h1>{t("La vita insieme.")}<br />{t("I conti, semplici.")}</h1>
          <p>{t("La spesa di casa, il prossimo viaggio, gli abbonamenti. Tutto in equilibrio, in un unico posto.")}</p>
          <div className="login-art">
            <div className="art-orbit" />
            <div className="art-card">
              <Users size={32} />
              <strong>{t("Insieme,")}<br />{t("si sta meglio.")}</strong>
              <span>split companion</span>
            </div>
            <span className="art-bubble one">{t("+ una cena insieme")}</span>
            <span className="art-bubble two">{t("✓ tutti in pari")}</span>
          </div>
        </div>
        <p className="login-local">{t("I vostri dati. La vostra casa. Nessun cloud obbligatorio.")}</p>
      </div>
      <div className="login-form-area">
        <div className="login-mobile-brand">
          <Brand />
        </div>
        <div className="login-form">
          {message && <p className="notice success-text" role="status">{translateMessage(message)}</p>}
          {challenge ? <MfaChallengeForm challenge={challenge} onLogin={onLogin} onRestart={() => { setChallenge(null); setError(""); onChallenge(false); }} /> : <>
          <span className="eyebrow">{t("IL TUO SPAZIO CONDIVISO")}</span>
          <h1>{t("Ciao, di nuovo.")}</h1>
          <p className="muted">{t("Accedi per ritrovare tutto al suo posto.")}</p>
          <form onSubmit={submit}>
            <label>{t("Username")}<input
                autoComplete="username"
                value={username}
                autoCapitalize="none"
                spellCheck={false}
                required
                onChange={(e) => setUsername(e.target.value)}
                placeholder={t("Il tuo username")}
              />
            </label>
            <label>{t("Password")}<input
                type="password"
                autoComplete="current-password"
                value={password}
                required
                onChange={(e) => setPassword(e.target.value)}
                placeholder={t("La tua password")}
              />
            </label>
            <ErrorBox
              error={
                error ||
                ((initialError as { status?: number })?.status === 401
                  ? null
                  : initialError)
              }
            />
            <Button type="submit" disabled={busy}>
              {busy ? t("Accesso in corso…") : t("Entra in Split")}
              <ArrowRight size={19} />
            </Button>
          </form>
          <div className="login-help">
            <ShieldCheck size={21} />
            <div>
              <strong>{t("La prima volta qui?")}</strong>
              <p>{t("Chiedi all’amministratore le credenziali per accedere al tuo account.")}</p>
            </div>
          </div>
          </>}
        </div>
        <LanguageSelector />
        <ThemeSelector />
        <p className="login-caption">{t("Spese condivise, conti sereni.")}</p>
      </div>
    </div>
  );
}

function CategoryAccessDenied() {
  useLanguage();
  return <div className="card form-card"><h1>{t("Accesso riservato")}</h1><p>{t("Solo gli amministratori possono gestire le categorie.")}</p><Link to="/profile" className="btn btn-secondary">{t("Torna al profilo")}</Link></div>;
}
