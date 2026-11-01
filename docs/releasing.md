# Preparare una release pubblica

Questo ramo contiene soltanto server e web, con una cronologia iniziale nuova.
Non pubblicare con `git push --mirror` o `--all` un repository che contiene anche
rami privati. Per GitHub crea un clone della sola branch di release, senza tag
privati, verifica ref e remoti e pubblica solo la branch prevista.

Prima della pubblicazione:

1. Scegli repository GitHub e namespace del registry. Abilita Private Vulnerability
   Reporting. Verifica disponibilità e permessi del package GHCR.
2. Controlla file, cronologia, identità dei commit, asset, archivio sorgenti e layer
   dell’immagine. Scansiona segreti e riferimenti personali; non aggiungere export,
   `.env`, DB, backup, certificati o file iOS. Le fixture contengono dati inventati.
3. Esegui test Python/TypeScript, build e `scripts/container-smoke.py` su entrambe le
   architetture. La prova crea e distrugge solo cartelle temporanee nuove.
4. Aggiorna `backend/app/version.py`, tag e documentazione coerentemente. La pipeline
   accetta tag `vX.Y.Z` oppure `vX.Y.Z-rc.N`; rifiuta mismatch con la versione server.
5. Crea una release GitHub sul commit verificato. Il workflow `release.yml` esegue
   test e scansioni, avvia le immagini amd64/arm64, poi pubblica i tag per architettura
   e il manifest comune su `ghcr.io/<owner>/<repository>:<version>`.
6. Controlla che il package sia effettivamente pubblico e prova un pull anonimo da
   un host pulito. Metti nome e digest esatti nelle note della release e negli
   esempi. Non sovrascrivere tag di versioni già consegnate.

Il workflow pubblica soltanto in risposta a una release GitHub pubblicata, non a
normali push. Nella preparazione privata non viene pubblicato alcun package.
Non esiste un tag `latest` automatico. Il registry è separato dal repository:
un repository pubblico non garantisce che il package sia già accessibile.

## Allegati e build manuali

```sh
docker build --platform linux/amd64 -t splitcompanion:1.2.0-rc.1 .
docker save -o splitcompanion-amd64.tar splitcompanion:1.2.0-rc.1
python3 scripts/make-source-archive.py --output splitcompanion-source.tar.gz
sha256sum splitcompanion-amd64.tar splitcompanion-source.tar.gz > SHA256SUMS
```

Per arm64 ripeti su un builder compatibile con `--platform linux/arm64`.
Pubblica il sorgente corrispondente insieme ai binari; nelle immagini è presente
anche `/app/source.tar.gz`, scaricabile da `/api/source`. La build produce
`third-party-notices.txt` per le dipendenze web; le dipendenze Python conservano i
propri metadati e avvisi nell’immagine. Non rimuovere gli avvisi di terze parti.

## Wiki

La documentazione della wiki è in `wiki/`, navigabile anche dal repository.
Per preparare file per il repository Git della wiki GitHub:

```sh
python3 scripts/export-wiki.py --output /tmp/splitcompanion-wiki
```

Il comando crea una directory nuova, adatta al successivo commit nella wiki;
non crea repository remoti né pubblica contenuti. Aggiorna la wiki insieme alla
release e verifica i link sul servizio di destinazione.
