import { useRegisterSW } from "virtual:pwa-register/react";
import { useState, useEffect } from "react";
import { Download, RefreshCw } from "lucide-react";
import { Button } from "./ui";
interface InstallEvent extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: string }>;
}
export function Pwa() {
  const [registration, setRegistration] =
    useState<ServiceWorkerRegistration | null>(null);
  const [updateError, setUpdateError] = useState("");
  const {
    needRefresh: [needRefresh, setNeedRefresh],
    updateServiceWorker,
  } = useRegisterSW({
    onRegisteredSW: (_url, value) => {
      if (value) setRegistration(value);
    },
  });
  useEffect(() => {
    if (!registration) return;
    const check = () => {
      if (navigator.onLine && document.visibilityState === "visible")
        registration.update().catch(() => {});
    };
    const interval = window.setInterval(check, 60 * 60 * 1000);
    window.addEventListener("online", check);
    document.addEventListener("visibilitychange", check);
    return () => {
      window.clearInterval(interval);
      window.removeEventListener("online", check);
      document.removeEventListener("visibilitychange", check);
    };
  }, [registration]);
  const [install, setInstall] = useState<InstallEvent | null>(null);
  const [online, setOnline] = useState(navigator.onLine);
  useEffect(() => {
    const capture = (event: Event) => {
      event.preventDefault();
      setInstall(event as InstallEvent);
    };
    const status = () => setOnline(navigator.onLine);
    window.addEventListener("beforeinstallprompt", capture);
    window.addEventListener("online", status);
    window.addEventListener("offline", status);
    return () => {
      window.removeEventListener("beforeinstallprompt", capture);
      window.removeEventListener("online", status);
      window.removeEventListener("offline", status);
    };
  }, []);
  return (
    <>
      {!online && (
        <div className="connection-banner" role="status">
          Split Companion non è raggiungibile. Controlla la connessione alla
          rete.
        </div>
      )}
      {needRefresh && (
        <div className="pwa-banner">
          <p>È disponibile una nuova versione di Split Companion.</p>
          {updateError && <p role="alert">{updateError}</p>}
          <Button
            onClick={async () => {
              try {
                await updateServiceWorker(true);
              } catch {
                setUpdateError(
                  "Aggiornamento non disponibile. Controlla la connessione e riprova.",
                );
              }
            }}
          >
            <RefreshCw size={16} /> Aggiorna
          </Button>
          <Button variant="ghost" onClick={() => setNeedRefresh(false)}>
            Più tardi
          </Button>
        </div>
      )}
      {install && (
        <div className="install-banner">
          <Download size={18} />
          <span>Porta Split nella tua home.</span>
          <button
            onClick={async () => {
              await install.prompt();
              setInstall(null);
            }}
          >
            Installa
          </button>
          <button
            aria-label="Nascondi suggerimento installazione"
            onClick={() => setInstall(null)}
          >
            ×
          </button>
        </div>
      )}
    </>
  );
}
