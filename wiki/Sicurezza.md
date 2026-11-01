# Sicurezza

Split Companion è destinato a istanze private di famiglia o piccoli gruppi, non
è un servizio multi-tenant per utenti pubblici ostili. Non offre registrazione
aperta. La preparazione di questa release comprende revisione del codice e test;
non costituisce una certificazione o un penetration test indipendente.

## Esposizione su Internet

La soluzione con superficie esposta minore è l’accesso tramite VPN. Se scegli
Internet, pubblica soltanto il tuo proxy HTTPS e impedisci l’accesso diretto alla
porta 8000. TLS, certificati, DNS, firewall e protezioni del proxy sono responsabilità
dell’operatore; nessun proxy viene distribuito con l’app.

| Rischio | Controlli presenti | Cosa resta da fare |
| --- | --- | --- |
| Furto credenziali/sessioni | Argon2id, cookie HttpOnly/Secure su HTTPS, MFA TOTP, CSRF, sessioni revocabili | HTTPS, password uniche, conservazione sicura dei recovery code |
| Tentativi di login | Limiti per account e IP, limitazione MFA/setup | Proxy configurato correttamente, protezione contro traffico distribuito |
| Falsificazione proxy | IP/CIDR fidati espliciti, origine HTTPS/host verificati | Sovrascrivere forwarded header e isolare la porta backend |
| Accesso ai dati | Autorizzazioni per gruppo e per amministrazione | Creare solo utenti fidati; utenti e foto sono condivisi nell’istanza |
| Upload malevoli | Limiti dimensione, ricodifica immagini, validazione import | Limiti proxy/timeout, spazio e risorse monitorati |
| DoS e abuso risorse | Un worker, limiti body e auth | Limiti globali di richieste/concorrenza/tempo sul proxy; l’app non è anti-DDoS |
| Compromissione host | Container non root, filesystem read-only, cap_drop, no-new-privileges | Aggiornare host e runtime, non montare Docker socket, isolare reti |
| Furto backup | Permessi restrittivi e archivi con checksum | I backup non sono cifrati: cifrare le copie, conservarle fuori host |
| Ripristino di vecchi accessi | Sessioni/challenge invalidate al restore | Riconciliare password, utenti, recovery code e consensi del backup |

L’amministratore non ottiene automaticamente accesso ai gruppi di cui non è membro.
I membri di un gruppo possono modificarne i movimenti secondo le regole del prodotto:
non è un registro immutabile contro gli stessi membri autorizzati.

Il web push è opzionale e contatta provider esterni. Gli endpoint vengono validati,
con esclusione di indirizzi privati e loopback; l’operatore può inoltre limitare
l’egress. Le notifiche possono mostrare informazioni sul blocco schermo: configura
le preferenze del dispositivo. Disabilita push se non necessario.

Mantieni aggiornati applicazione, immagine base, dipendenze e proxy. Le immagini
vanno riferite con versione esplicita o digest; nessun tag `latest` è necessario.
La validazione CI blocca vulnerabilità high/critical correggibili note allo scanner,
ma una scansione pulita non dimostra assenza di vulnerabilità.

## Segnalare una vulnerabilità

Se disponibile nel repository GitHub, usa **Security → Report a vulnerability**
(Private Vulnerability Reporting). L’operatore della pubblicazione deve abilitarlo
prima della prima release. Non pubblicare dettagli sfruttabili o dati reali in una
issue pubblica. Se il canale non è ancora attivo, chiedine l’attivazione senza
includere dettagli della vulnerabilità.

## Riferimenti

- [OWASP: sicurezza Docker](https://cheatsheetseries.owasp.org/cheatsheets/Docker_Security_Cheat_Sheet.html)
- [Proxy e HTTPS](Proxy-HTTPS.md)
- [Backup e ripristino](Backup-e-aggiornamenti.md)
