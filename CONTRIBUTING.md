# Contribuire

Prima di una modifica, descrivi il problema e come riprodurlo con dati sintetici.
Non allegare database, esportazioni reali, password, token, foto o indirizzi privati.
Per vulnerabilità segui SECURITY.md, non una issue pubblica.

Mantieni invarianti contabili (importi interi, valute separate, idempotenza,
autorizzazione ai gruppi e provenienza import). Aggiungi test per le regressioni e
usa la procedura di sviluppo in docs/native.md. Contributi a server/web sono soggetti
ad AGPL-3.0; mantieni gli avvisi delle dipendenze e il sorgente distribuito aggiornato.

Non aggiungere configurazioni personali o servizi proxy al Compose applicativo.
Le installazioni native devono restare possibili senza Docker. Le variazioni API
incompatibili richiedono un aggiornamento esplicito del contratto.
