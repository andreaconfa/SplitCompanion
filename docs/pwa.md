# PWA: usare Split Companion come app web

Per le funzionalità PWA complete, usa **HTTPS con un certificato attendibile**.
Questo vale anche quando server e telefono sono sulla stessa LAN o VPN. HTTP
su un IP privato non è un contesto sicuro per i service worker.

Il requisito non è soltanto una limitazione Apple: i browser riservano i service
worker ai contesti sicuri. L’eccezione `http://localhost` serve allo sviluppo sullo
stesso dispositivo, non rende sicuro l’IP di un server remoto.
[Documentazione Service Worker](https://developer.mozilla.org/en-US/docs/Web/API/Service_Worker_API).

## iPhone e iPad

Apri il tuo indirizzo HTTPS in Safari, scegli **Condividi → Aggiungi alla schermata
Home** e avvia l’icona creata. Può essere possibile aggiungere anche un semplice
collegamento HTTP, ma ciò non abilita le funzioni PWA protette.

Le notifiche Web Push su iOS/iPadOS richiedono versione 16.4 o successiva e una
web app aggiunta alla Home; il consenso deve seguire un’azione dell’utente.
[Requisiti WebKit](https://webkit.org/blog/13878/web-push-for-web-apps-on-ios-and-ipados/).
L’operatore deve anche abilitare push, impostare un contatto/origine VAPID valido e
consentire le connessioni HTTPS in uscita verso i provider di notifiche.

## Rete e aggiornamenti

La PWA conserva la shell statica, non mette le API autenticate nella cache e non
accoda spese da inviare in seguito. I dati richiedono il server raggiungibile.
Quando compare una nuova versione, salva i moduli aperti e scegli **Aggiorna**.

Tema e colore sono preferenze del browser. Il layout segue lo spazio disponibile:
navigazione inferiore sotto 768 px, a destra su schermi più ampi, riepilogo a due
colonne da 1024 px. Non richiede rilevamento di cerniere o angoli di piega.

HTTPS e certificati sono interamente gestiti dal tuo [proxy esterno](proxy.md).
