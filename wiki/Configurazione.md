# Configurazione

Docker Compose legge `.env` accanto a `compose.yaml`. Non pubblicare quel file.
I valori d’esempio non contengono credenziali: il segreto viene generato alla prima
inizializzazione e conservato in `data/secret.key`.

| Variabile Compose | Default | Uso |
| --- | --- | --- |
| `SPLIT_COMPANION_IMAGE` | `splitcompanion:1.2.0-rc.1` | Tag locale; sostituire con immagine/digest della release pubblicata |
| `SPLIT_COMPANION_DATA_DIR` | `./data` | Cartella host persistente, esistente, UID/GID 10001 |
| `SPLIT_COMPANION_BACKUP_DIR` | `./backups` | Cartella host per backup, esistente, UID/GID 10001 |
| `SPLIT_COMPANION_BIND` | `127.0.0.1` | Interfaccia host sulla quale pubblicare la porta |
| `SPLIT_COMPANION_PORT` | `8000` | Porta host; il container ascolta sempre su 8000 |
| `SPLIT_COMPANION_TIMEZONE` | `UTC` | Fuso IANA per scadenze e backup, ad esempio `Europe/Rome` |
| `SPLIT_COMPANION_MFA_REQUIRED` | `true` | Obbligo verifica in due passaggi |
| `SPLIT_COMPANION_ALLOW_HTTP` | `true` | HTTP locale esplicitamente consentito; disattivare per accesso HTTPS esterno |
| `SPLIT_COMPANION_PUBLIC_ORIGIN` | vuoto | Origine HTTPS esatta del proxy esterno |
| `SPLIT_COMPANION_TRUSTED_PROXY_IPS` | vuoto | Soltanto IP/CIDR dei proxy fidati |
| `SPLIT_COMPANION_PUSH_ENABLED` | `false` | Invio notifiche web opzionale |
| `SPLIT_COMPANION_PUSH_VAPID_SUBJECT` | vuoto | Contatto `mailto:` o URL HTTPS controllato dall’operatore |
| `SPLIT_COMPANION_BACKUP_HOUR` | `3` | Ora locale, da 0 a 23 |
| `SPLIT_COMPANION_BACKUP_RETENTION` | `14` | Numero di backup giornalieri conservati |

Il Compose mantiene scheduler e backup attivi. Per un’istanza di prova usa un
override con scheduler e push disattivati e cartelle diverse. Non usare mai i
volumi reali nei test.

## Segreti montati e impostazioni avanzate

Il backend supporta `SPLIT_COMPANION_SECRET_KEY` oppure
`SPLIT_COMPANION_SECRET_KEY_FILE`, mai entrambi. Per un secret esterno crea un tuo
override Compose, monta il file in sola lettura e rendilo leggibile dall’UID 10001.
Non impostare queste variabili senza necessità: il segreto generato persistente
è sufficiente. Con un database esistente, l’assenza del segreto originale causa
un errore di avvio, non una rigenerazione silenziosa.

Per avvio nativo, le variabili `DB`, `BACKUP_DIR`, `SOURCE_ARCHIVE` e `FRONTEND_DIR`
(con prefisso `SPLIT_COMPANION_`) sono percorsi del sistema operativo, non quelli
del container. `SESSION_HOURS` regola la durata sessione (default 168, intervallo 1–8760).
La configurazione completa è definita in `backend/app/config.py`.

## Problemi frequenti

- **Permission denied:** cartelle dati/backup non possedute o scrivibili dall’UID 10001.
  Correggi il proprietario dei soli percorsi dedicati, senza allargare permessi globali.
- **Host non consentito / richiede HTTPS:** `Host`, origine o header del proxy non
  corrispondono; controlla anche l’IP sorgente visto dal container.
- **Codice setup non valido:** usa un codice nuovo entro 30 minuti, dalla CLI della
  stessa istanza. Il setup si chiude definitivamente alla creazione iniziale.
- **PWA o notifiche assenti:** verifica HTTPS attendibile, installazione Home e
  permessi del dispositivo. Un IP privato HTTP non basta.
- **Database occupato:** controlla che non esistano due istanze o worker sullo stesso
  volume. Non ripetere alla cieca operazioni finanziarie: ricarica e verifica lo storico.
- **Schema più nuovo:** usa l’immagine corrispondente o un ripristino verificato;
  non cancellare il database per aggirare il controllo.



## Host supportato per il database

La distribuzione con cartelle host è destinata a Docker Engine su **Linux**, con
disco locale. Non usare directory condivise macOS di Docker Desktop/virtiofs per
SQLite WAL: nel collaudo possono non condividere correttamente i lock tra processo
web e CLI, con backup incompleti o perdita di dati dopo arresto forzato. I volumi
interni della VM Linux hanno comportamento diverso, ma non rendono affidabile una
cartella macOS condivisa. Per il server reale usa Linux e verifica il ripristino.
