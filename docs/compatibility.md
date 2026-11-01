# Compatibilità dei client

`GET /api/meta` è pubblico e non contiene segreti. Espone `server_version`,
`api_version`, `capabilities`, `setup_required`, `source_available` e il range
`compatibility.min_api_version` / `max_api_version`. In questa release il contratto
supportato è API 1.

La versione del prodotto è informativa: un server 1.3 non è automaticamente
incompatibile con un client 1.2. I client devono verificare il contratto API e le
funzionalità richieste. Le aggiunte compatibili mantengono API 1; cambiamenti
incompatibili richiedono una nuova versione del contratto.

Un client con API troppo nuova deve chiedere l’aggiornamento del server. Un server
che supporta solo API più nuove richiede l’aggiornamento del client. Metadata assenti,
malformati o irraggiungibili non provano compatibilità: mostrare istruzioni per
aggiornare il server o riprovare, evitando operazioni contabili non verificabili.

La web app distribuita nello stesso container è costruita insieme al backend.
Per client separati, verificare all’accesso, dopo una riconnessione e prima delle
scritture. Questo controllo non sostituisce autenticazione, autorizzazioni e
validazione lato server. Il codice dell’app iOS resta fuori da questa distribuzione.
