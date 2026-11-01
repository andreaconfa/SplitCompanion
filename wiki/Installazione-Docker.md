# Installazione Docker

Un solo container contiene server e web/PWA. Il database e le chiavi rimangono
nelle cartelle del server, anche quando ricrei o aggiorni il container.

> Candidata **1.2.0-rc.1**: non è ancora disponibile un registry pubblico.
> Usa gli archivi preparati per la candidata oppure la [build dai sorgenti](Sorgenti-e-avvio-nativo.md).

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
   Per questa candidata puoi [costruire l’immagine dai sorgenti](Sorgenti-e-avvio-nativo.md).
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
telefono configura il tuo [reverse proxy HTTPS esterno](Proxy-HTTPS.md).

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
Leggi la [guida backup e ripristino](Backup-e-aggiornamenti.md) prima di un downgrade.

## Collegare i dispositivi

Per accedere da un altro computer della LAN, imposta in `.env`
`SPLIT_COMPANION_BIND` all’IP LAN del server e ricrea il container con
`docker compose up -d`. Apri `http://IP-DEL-SERVER:8000`. HTTP è adatto solo
a una rete fidata: password e dati non sono cifrati.

Per Internet e per la PWA su telefono configura un [proxy HTTPS esterno](Proxy-HTTPS.md),
poi segui la [guida PWA](PWA.md). Il container non gestisce certificati o proxy.

## Passi successivi

- [Configurazione e risoluzione dei problemi](Configurazione.md)
- [Backup, aggiornamenti e recupero accesso](Backup-e-aggiornamenti.md)
- [Sicurezza](Sicurezza.md)
