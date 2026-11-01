# Backup, aggiornamenti e recupero

## Cosa conservare

La cartella `data` contiene database SQLite, segreto applicativo, chiavi VAPID e
stato operativo. Avatar e icone caricate sono nel database. La cartella `backups`
contiene archivi consistenti con database, segreti e manifest con checksum.
I backup sono **in chiaro** e sensibili: limita i permessi, cifra le copie esterne
e conserva una copia su un altro host. Non caricarli su GitHub o nelle issue.

```sh
docker compose exec app python -m app.cli backup-full --output-dir /backups --kind manual
```

Sono pianificati backup giornalieri (ore 03:00 nel fuso configurato), mantenendo
gli ultimi 14. I backup manuali e precedenti alle migrazioni sono separati dalla
rotazione: controlla spazio disponibile e diagnostica amministrativa.

## Aggiornare

Crea un backup e conserva versione e digest attuali. Imposta il nuovo tag/digest,
esegui `docker compose pull` e `docker compose up -d`. Se usi un archivio locale,
caricalo con `docker load` invece di `pull`. Non cancellare né cambiare le cartelle
`data` e `backups`. Una sola istanza può scrivere sul volume.

L’avvio controlla schema, integrità, permessi e asset; prima di una migrazione crea
un backup. Se fallisce, si arresta senza ripristini distruttivi automatici. Controlla:

```sh
docker compose ps
docker compose logs --tail 100 app
curl --fail http://localhost:8000/api/ready
```

La healthcheck Docker segnala `unhealthy`, ma da sola non riavvia il container.
Un downgrade dell’immagine non annulla le migrazioni: usa versione e backup abbinati.
Non sostituire un database aggiornato con uno precedente ignorando nuove scritture.

## Ripristino offline su una cartella nuova

Ferma il servizio; conserva i dati attuali. Crea una cartella vuota e avvia il CLI
con l’immagine compatibile con il backup. Esempio dalla cartella Compose, dopo aver
sostituito nome archivio e versione con quelli effettivi:

```sh
docker compose stop app
sudo install -d -m 0700 -o 10001 -g 10001 data-restored
docker run --rm --network none --read-only --cap-drop ALL \
  --security-opt no-new-privileges --tmpfs /tmp:rw,noexec,nosuid,size=64m \
  --mount "type=bind,src=$PWD/data-restored,dst=/data" \
  --mount "type=bind,src=$PWD/backups,dst=/backups,readonly" \
  splitcompanion:1.2.0-rc.1 python -m app.cli restore /backups/ARCHIVE.tar.gz --confirm
```

Il comando verifica archivio, checksum, integrità e compatibilità. Cambia
`SPLIT_COMPANION_DATA_DIR` a `./data-restored` prima di riavviare. Le sessioni e le
richieste MFA pendenti vengono invalidate durante il ripristino: serve un nuovo
login. Il segreto MFA è conservato, quindi gli autenticatori continuano a funzionare.

Un backup riporta anche password, account, codici di recupero e consensi push allo
stato del salvataggio. Prima di riesporre l’istanza, riconcilia account disabilitati,
password cambiate e codici recupero utilizzati; rigenera questi ultimi se necessario.

## Recuperare un account

```sh
docker compose exec app python -m app.cli reset-password USERNAME
docker compose exec app python -m app.cli reset-mfa USERNAME
```

La password viene richiesta senza eco; non passarla in argomenti shell. Un reset
MFA è un’operazione amministrativa sensibile: verifica l’identità della persona.
Il setup iniziale non si riapre disabilitando gli amministratori.

## Diagnostica

`/api/health` conserva la risposta `{"status":"ok"}`; `/api/ready` verifica la
prontezza del servizio. `/api/admin/status` richiede un amministratore e riporta
scheduler, backup e notifiche. I fallimenti push non rendono indisponibile la
contabilità. Usa log e identificativo richiesta per diagnosticare errori senza
condividere password, cookie, import o database.
