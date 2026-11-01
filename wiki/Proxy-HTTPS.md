# Proxy HTTPS esterno

Split Companion serve HTTP sulla porta 8000. Il container non installa, avvia o
configura proxy, certificati, DNS o rinnovi TLS. Puoi usare Nginx Proxy Manager,
Caddy, Nginx o un’infrastruttura equivalente amministrata da te.

1. Crea un nome DNS e un certificato attendibile dai client.
2. Configura il proxy per inoltrare l’intera origine (web e `/api`) alla porta 8000.
   Non è previsto un prefisso come `/split/`.
3. Conserva l’header `Host` originale. Il proxy deve **sovrascrivere**, non fidarsi
   dei valori forniti dal client, `X-Forwarded-Proto` e `X-Forwarded-For`.
4. Configura `.env`:

   ```dotenv
   SPLIT_COMPANION_PUBLIC_ORIGIN=https://split.example.org
   SPLIT_COMPANION_TRUSTED_PROXY_IPS=192.0.2.10
   SPLIT_COMPANION_ALLOW_HTTP=false
   ```

   Sostituisci dominio e IP di documentazione: l’IP deve essere quello del proxy
   **visto dal container**. Non usare `*`, `0.0.0.0/0`, `::/0` o intere reti LAN
   se non necessarie. Con PUBLIC_ORIGIN i cookie diventano Secure e sono accettati
   soltanto host e schema previsti. `/api/health` e `/api/ready` restano sonde locali.
5. Riavvia con `docker compose up -d` e controlla il login tramite HTTPS.

Il binding `127.0.0.1` funziona con un proxy sullo stesso host. Un proxy in un altro
container non raggiunge il loopback dell’host: collegalo a una rete Docker dedicata
mediante un tuo override, oppure esponi la porta soltanto sull’interfaccia privata
raggiungibile da quel proxy e applica il firewall. Non pubblicare 8000 su Internet.
Le regole Docker possono aggirare alcuni frontend firewall: verifica dall’esterno.

Sul proxy configura limiti per richieste concorrenti, velocità e tempi di lettura,
oltre a un massimo body di 12 MiB (l’app applica limiti più restrittivi per endpoint).
Un limite troppo basso impedisce gli import. Una catena di più proxy richiede una
configurazione verificata degli IP originali; altrimenti il rate limit può trattare
tutti gli utenti come una sola sorgente o fidarsi di dati falsificati.

TLS termina sul proxy: mantieni protetto anche il collegamento proxy→app. Non
cachare risposte `/api`, cookie o pagine autenticate. `PUBLIC_ORIGIN` deve corrispondere
all’indirizzo effettivamente usato dai client, senza slash finale o percorso.
