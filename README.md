# Split Companion

**Spese condivise, sul tuo server.** Gestisci gruppi, spese, abbonamenti e crediti
con un’interfaccia web adattata a telefono, tablet e desktop, installabile come PWA.

Un solo container contiene backend e web. SQLite, chiavi e configurazione
operativa rimangono nelle cartelle del tuo host. Nessun account cloud obbligatorio,
nessuna registrazione pubblica: l’amministratore crea gli utenti dell’istanza.

> **Versione candidata 1.2.0-rc.1.** Questo ramo prepara la prima distribuzione
> pubblica. Non implica che esista già un’immagine su un registry pubblico.
> Le release pubblicate indicheranno il nome esatto dell’immagine e il digest.

## Cosa puoi fare

- Dividere spese in parti uguali, importi, percentuali o assegnarle a una persona.
- Gestire saldi e regolamenti separati per valuta, senza conversioni automatiche.
- Programmare abbonamenti, registrare anticipi, utilizzare crediti e rimborsi.
- Consultare statistiche mensili, categorie, avatar e storico dei movimenti.
- Importare esportazioni CSV/JSON di Splitwise con anteprima e annullamento.
- Usare account locali, verifica in due passaggi e backup completi.

## Avvio rapido con Docker

Servono Docker Engine con Compose e disco locale: **una replica, un worker**.
Non mettere SQLite su NFS/SMB o cartelle macOS condivise da Docker Desktop. Architetture previste: Linux amd64 e arm64.

1. Scarica `compose.yaml` e `.env.example` dalla stessa release.
2. Prepara le cartelle sul server Linux:

   ```sh
   cp .env.example .env
   sudo install -d -m 0700 -o 10001 -g 10001 data backups
   ```

3. In `.env`, imposta `SPLIT_COMPANION_IMAGE` al nome e tag/digest pubblicati nella
   release. Con gli archivi Docker allegati a una release, esegui prima
   `docker load -i splitcompanion-<arch>.tar` e usa il tag indicato nell’archivio.
   Per questa candidata puoi [costruire l’immagine dai sorgenti](docs/native.md).
4. Avvia e genera il codice di configurazione:

   ```sh
   docker compose up -d
   docker compose exec app python -m app.cli setup-token
   ```

5. Apri `http://localhost:8000` dal server e crea l’amministratore con quel codice.
   Scade dopo 30 minuti e funziona una sola volta. Completa la verifica in due
   passaggi e conserva i codici di recupero.

La porta è inizialmente disponibile **solo sul server**, su `127.0.0.1`.
Per una LAN fidata, imposta `SPLIT_COMPANION_BIND` all’IP LAN del server; HTTP
trasmette credenziali e dati senza cifratura. Per accesso da Internet o PWA su
telefono configura il tuo [reverse proxy HTTPS esterno](docs/proxy.md).

## I dati sopravvivono agli aggiornamenti

| Cartella host | Nel container | Contenuto |
| --- | --- | --- |
| `./data` | `/data` | Database, segreto dell’istanza, chiavi push, stato operativo |
| `./backups` | `/backups` | Archivi completi di backup |

Puoi scegliere cartelle assolute in `.env`. Devono esistere ed essere scrivibili
all’UID/GID `10001:10001`. Non usare `chmod 777`. Ricreare il container mantiene
queste cartelle; eliminarle o cambiarle perde o nasconde i dati. Conserva tutto
`data`, non soltanto il file `.db`: perdere il segreto impedisce il recupero MFA.

Prima di aggiornare:

```sh
docker compose exec app python -m app.cli backup-full --output-dir /backups --kind manual
# Imposta in .env il nuovo tag o digest, poi:
docker compose pull
docker compose up -d
docker compose ps
```

Per immagini caricate da archivio, usa `docker load` al posto di `pull`.
Leggi la [guida backup e ripristino](docs/operations.md) prima di un downgrade.

## PWA su iPhone e altri dispositivi

Per l’esperienza PWA completa su iPhone serve **HTTPS con un certificato
considerato attendibile dal dispositivo**, anche sulla LAN o tramite VPN.
Safari → Condividi → Aggiungi alla schermata Home. Un collegamento Home su HTTP
non equivale alla disponibilità di service worker e notifiche.
[Requisiti e limiti PWA](docs/pwa.md).

Il container espone soltanto HTTP sulla porta 8000. **Non include Caddy, Nginx,
certificati o gestione HTTPS**. Il proxy è scelto, configurato e aggiornato da te.

## Documentazione

**[Apri la wiki di installazione e configurazione](wiki/Home.md)**

- [Docker, build e avvio nativo dai sorgenti](docs/native.md)
- [Proxy esterno, HTTPS e porte](docs/proxy.md)
- [Backup, aggiornamenti e recupero accesso](docs/operations.md)
- [PWA e notifiche](docs/pwa.md)
- [Sicurezza e rischi di esposizione su Internet](SECURITY.md)
- [Compatibilità API](docs/compatibility.md)
- [Preparazione e pubblicazione delle release](docs/releasing.md)

## Licenza

Server e web/PWA sono distribuiti sotto [GNU AGPL-3.0](LICENSE). L’app iOS nativa
non è inclusa in questo repository né in questi container. Il codice della
versione installata è scaricabile da **Impostazioni → Codice sorgente** nelle
immagini ufficiali. Vedi anche [NOTICE](NOTICE).
