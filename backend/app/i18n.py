"""Localize application messages only; names, descriptions and imported data stay intact.

Italian source messages remain stable identifiers for existing persisted import reports.
Translation occurs at the HTTP boundary (and per device at push dispatch).
"""

from contextvars import ContextVar
import re

language = ContextVar("response_language", default="en")


def language_from_header(header):
    choices = []
    for index, item in enumerate(header.split(",")):
        parts = item.strip().lower().split(";")
        code = parts[0].split("-")[0]
        quality = 1.0
        for parameter in parts[1:]:
            if parameter.strip().startswith("q="):
                try:
                    quality = float(parameter.strip()[2:])
                except ValueError:
                    quality = 0
        if code in ("en", "it") and 0 < quality <= 1:
            choices.append((quality, -index, code))
    return max(choices)[2] if choices else "en"


# Exact application-owned messages, never arbitrary replacements in user text.
EN = {
    "Senza categoria": "Uncategorized",
    "Accedi per continuare.": "Sign in to continue.",
    "Account non attivo.": "Account inactive.",
    "Completa la verifica a due fattori.": "Complete two-factor verification.",
    "Sessione non valida. Ricarica la pagina.": "Invalid session. Reload the page.",
    "Questa funzione è riservata agli amministratori.": "This feature is available to administrators only.",
    "Endpoint non trovato.": "Endpoint not found.",
    "File non trovato.": "File not found.",
    "Elemento non trovato.": "Item not found.",
    "Interfaccia non compilata. Esegui npm run build nella directory frontend.": "Interface not built. Run npm run build in the frontend directory.",
    "Accedi tramite il dominio HTTPS configurato sul reverse proxy.": "Use the HTTPS domain configured on the reverse proxy.",
    "Host non consentito.": "Host not allowed.",
    "Il file supera il limite di 10 MB.": "The file exceeds the 10 MB limit.",
    "Il file supera il limite consentito.": "The file exceeds the allowed size.",
    "Richiesta non valida.": "Invalid request.",
    "Origine della richiesta non consentita.": "Request origin not allowed.",
    "Richiesta cross-site non consentita.": "Cross-site request not allowed.",
    "Dati non validi. Controlla importi, quote e campi richiesti.": "Invalid data. Check amounts, shares and required fields.",
    "Dati non validi. Controlla i campi richiesti e usa centesimi interi.": "Invalid data. Check required fields and use whole cents.",
    "Operazione in conflitto con dati esistenti. Ricarica e riprova.": "Operation conflicts with existing data. Reload and try again.",
    "Database occupato. Ricarica prima di riprovare.": "Database busy. Reload before trying again.",
    "Database non disponibile. Contatta l’amministratore.": "Database unavailable. Contact the administrator.",
    "Sorgente non disponibile su questa istanza.": "Source code is unavailable on this instance.",
    "Nome partecipante mancante.": "Participant name missing.",
    "Struttura JSON non supportata.": "Unsupported JSON structure.",
    "Il JSON deve contenere una lista expenses.": "JSON must contain an expenses list.",
    "Il file supera il limite di 10000 record.": "The file exceeds the limit of 10000 records.",
    "Transazione non valida.": "Invalid transaction.",
    "Partecipanti assenti.": "No participants.",
    "Costi, quote e delta non coerenti.": "Costs, shares and balance changes do not match.",
    "Descrizione mancante.": "Description missing.",
    "Data non valida (usa AAAA-MM-GG oppure GG/MM/AAAA).": "Invalid date (use YYYY-MM-DD or DD/MM/YYYY).",
    "Importo non valido.": "Invalid amount.",
    "Separatore monetario ambiguo.": "Ambiguous decimal separator.",
    "Valuta mancante o non valida.": "Currency missing or invalid.",
    "Importo non valido o più di due decimali.": "Invalid amount or more than two decimal places.",
    "Importo non leggibile.": "Cannot read the amount.",
    "Il file è vuoto.": "The file is empty.",
    "Colonne duplicate o nomi ambigui nel CSV.": "Duplicate columns or ambiguous names in the CSV.",
    "Header inatteso: servono Date, Description, Cost e Currency.": "Unexpected header: Date, Description, Cost and Currency are required.",
    "Mancano le colonne dei partecipanti.": "Participant columns are missing.",
    "Separatore CSV non riconosciuto.": "Unrecognized CSV delimiter.",
    "Numero di colonne non valido.": "Invalid number of columns.",
    "I delta dei partecipanti non sommano a zero.": "Participant balance changes do not sum to zero.",
    "Gruppo mancante.": "Group missing.",
    "Pagante non presente nelle colonne partecipanti.": "Payer not found in participant columns.",
    "Scegli due persone diverse.": "Choose two different people.",
    "Annulla il batch per eliminare un pagamento importato.": "Undo the import batch to delete an imported payment.",
    "L’anticipo è già stato utilizzato o rimborsato e non può essere eliminato.": "The advance has already been used or refunded and cannot be deleted.",
    "I movimenti importati si gestiscono tramite annullamento del batch.": "Manage imported transactions by undoing the import batch.",
    "Campo spesa non valido.": "Invalid expense field.",
    "Non è possibile spostare una spesa tra gruppi.": "An expense cannot be moved between groups.",
    "Annulla il batch per eliminare una spesa importata.": "Undo the import batch to delete an imported expense.",
    "Specifica le quote per cambiare divisione.": "Specify the shares to change the split.",
    "Per una scadenza modifica solo descrizione, importo, note e quote.": "For a recurring expense, only change its description, amount, notes and shares.",
    "Le categorie predefinite non possono essere eliminate.": "Built-in categories cannot be deleted.",
    "Categoria in uso: riassegna prima i movimenti.": "Category in use: reassign its transactions first.",
    "L’icona supera 1 MB.": "The icon exceeds 1 MB.",
    "Icona in uso: rimuovila prima dalle categorie.": "Icon in use: remove it from categories first.",
    "Immagine non valida. Usa PNG, JPEG o WebP.": "Invalid image. Use PNG, JPEG or WebP.",
    "Usa PNG, JPEG o WebP fino a 2048 × 2048 pixel.": "Use PNG, JPEG or WebP up to 2048 × 2048 pixels.",
    "Codice non valido.": "Invalid code.",
    "Codice non valido o già utilizzato.": "Invalid or already used code.",
    "Password o codice non valido.": "Invalid password or code.",
    "La fine deve essere successiva all’inizio.": "The end date must be on or after the start date.",
    "Abbonamento terminato.": "Subscription ended.",
    "Campo abbonamento non valido.": "Invalid subscription field.",
    "Non puoi spostare un abbonamento tra gruppi.": "A subscription cannot be moved between groups.",
    "Non puoi cambiare il pagante finché esiste credito anticipato.": "You cannot change the payer while advance credit remains.",
    "Data finale non valida.": "Invalid end date.",
    "Abbonamento terminato: crea un nuovo abbonamento.": "Subscription ended: create a new subscription.",
    "Aggiorna la data finale prima di riprendere.": "Update the end date before resuming.",
    "Il pagante non può anticipare denaro a se stesso.": "The payer cannot advance money to themselves.",
    "Registra solo trasferimenti già avvenuti.": "Only record transfers that have already taken place.",
    "Abbonamento terminato: puoi solo rimborsare il credito.": "Subscription ended: you can only refund the credit.",
    "La persona deve partecipare all’abbonamento.": "The person must participate in the subscription.",
    "Valuta e data iniziale non si modificano dopo il primo movimento.": "Currency and start date cannot change after the first transaction.",
    "Utente non attivo.": "User inactive.",
    "Solo il creatore o un amministratore può rimuovere membri.": "Only the creator or an administrator can remove members.",
    "Non puoi rimuovere il creatore del gruppo.": "You cannot remove the group creator.",
    "Sistema prima i saldi del membro.": "Settle the member’s balances first.",
    "Membro non trovato.": "Member not found.",
    "Campo gruppo non valido.": "Invalid group field.",
    "Rimuovi prima il membro dagli abbonamenti.": "Remove the member from subscriptions first.",
    "Questo import appartiene a un altro amministratore.": "This import belongs to another administrator.",
    "Questo file Splitwise risulta già importato.": "This Splitwise file has already been imported.",
    "Conferma esplicitamente l’annullamento dell’import.": "Explicitly confirm undoing the import.",
    "Configurazione già completata. Accedi con il tuo account.": "Setup already completed. Sign in with your account.",
    "Configurazione già completata: usa un amministratore esistente.": "Setup already completed: use an existing administrator.",
    "Troppi tentativi. Riprova tra 15 minuti.": "Too many attempts. Try again in 15 minutes.",
    "Codice di configurazione non valido o scaduto.": "Invalid or expired setup code.",
    "Username o password non corretti.": "Incorrect username or password.",
    "Password attuale o codice di verifica non valido.": "Invalid current password or verification code.",
    "Scegli una password diversa da quella attuale.": "Choose a password different from your current one.",
    "Password attuale o codice di verifica non valido. Usa un codice nuovo.": "Invalid current password or verification code. Use a new code.",
    "Username già utilizzato.": "Username already in use.",
    "I campi utente non possono essere vuoti.": "User fields cannot be empty.",
    "Non puoi disabilitare o rimuovere i tuoi privilegi amministrativi.": "You cannot disable yourself or remove your own administrator privileges.",
    "La foto supera 2 MB.": "The photo exceeds 2 MB.",
    "Puoi modificare solo la tua foto.": "You can only change your own photo.",
    "Foto non valida. Usa PNG, JPEG o WebP.": "Invalid photo. Use PNG, JPEG or WebP.",
    "Usa una foto PNG, JPEG o WebP.": "Use a PNG, JPEG or WebP photo.",
    "La foto supera 2048 × 2048 pixel.": "The photo exceeds 2048 × 2048 pixels.",
    "Le notifiche richiedono una connessione HTTPS.": "Notifications require an HTTPS connection.",
    "Questo dispositivo è associato a un altro account. Disattiva le notifiche nel browser e riprova.": "This device is linked to another account. Disable browser notifications and try again.",
    "Attiva prima le notifiche su questo dispositivo.": "Enable notifications on this device first.",
    "Attendi un minuto prima di inviare un altro test.": "Wait one minute before sending another test.",
    "Limite di dispositivi raggiunto.": "Device limit reached.",
    "Chiavi push non valide.": "Invalid push keys.",
    "Modalità di divisione non valida.": "Invalid split mode.",
    "Scegli partecipanti distinti.": "Choose distinct participants.",
    "Scegli una sola persona.": "Choose just one person.",
    "Le quote devono totalizzare esattamente l’importo della spesa.": "Shares must add up to exactly the expense amount.",
    "Le percentuali devono totalizzare 100%.": "Percentages must add up to 100%.",
    "Percentuale non valida.": "Invalid percentage.",
    "Icona non valida.": "Invalid icon.",
    "Categoria non trovata.": "Category not found.",
    "Ricorrenza non valida: intervallo da 1 a 99.": "Invalid recurrence: interval must be between 1 and 99.",
    "Ricorrenza senza prossima data.": "Recurrence has no next date.",
    "Quote abbonamento incoerenti.": "Subscription shares do not match.",
    "Non hai accesso a questo gruppo.": "You do not have access to this group.",
    "Il gruppo è archiviato. Riattivalo prima di modificarlo.": "This group is archived. Reactivate it before editing.",
    "Tutti i partecipanti devono essere membri attivi del gruppo.": "All participants must be active members of the group.",
    "Troppi tentativi. Riprova tra cinque minuti.": "Too many attempts. Try again in five minutes.",
    "Verifica scaduta o non valida. Accedi di nuovo.": "Verification expired or invalid. Sign in again.",
    "Verifica non valida.": "Invalid verification.",
    "Il mese deve essere compreso tra gennaio 1900 e il mese corrente.": "The month must be between January 1900 and the current month.",
    "Mese non valido.": "Invalid month.",
    "La modifica riaprirebbe credito verso un precedente pagante. Lo storico resta invariato.": "This change would reopen credit with a previous payer. History remains unchanged.",
    "Il rimborso supera il credito disponibile alla data indicata.": "The refund exceeds the credit available on the selected date.",
    "Questo import non è più modificabile.": "This import can no longer be edited.",
    "Completa il mapping di tutte le persone e i gruppi.": "Complete the mapping for all people and groups.",
    "Visualizza e conferma l’anteprima prima di importare.": "View and confirm the preview before importing.",
    "L’anteprima contiene errori: correggi il file o il mapping.": "The preview contains errors: correct the file or mapping.",
    "Solo un import completato può essere annullato.": "Only a completed import can be undone.",
    "Utente mappato inesistente o disabilitato.": "Mapped user does not exist or is disabled.",
    "Mapping utente non valido.": "Invalid user mapping.",
    "Mapping gruppo non valido.": "Invalid group mapping.",
    "Membro disabilitato durante l’import.": "Member disabled during import.",
    "Quote importate incoerenti.": "Imported shares do not match.",
    "Username già presente: associalo all’utente esistente.": "Username already exists: map it to the existing user.",
    "Esiste già un utente con questo nome: usa il mapping esistente.": "A user with this name already exists: use the existing mapping.",
    "Username duplicato nel mapping.": "Duplicate username in mapping.",
    "Utente non più disponibile.": "User no longer available.",
    "I delta importati non sommano a zero.": "Imported balance changes do not sum to zero.",
    "Servizio push non supportato o indirizzo non valido.": "Unsupported push service or invalid address.",
    "Il servizio push non risolve a un indirizzo pubblico.": "The push service does not resolve to a public address.",
    "Una nuova spesa ti coinvolge.": "A new expense involves you.",
    "Le notifiche su questo dispositivo sono attive.": "Notifications are enabled on this device.",
    "Il file non contiene transazioni.": "The file contains no transactions.",
    "Completa il mapping prima di importare.": "Complete the mapping before importing.",
    "riepilogo escluso.": "summary excluded.",
    " transazione eliminata esclusa.": " deleted transaction excluded.",
}
IT = {"Not Found": "Non trovato.", "Method Not Allowed": "Metodo non consentito."}


def translate(message, locale=None):
    locale = locale or language.get()
    if locale == "it":
        return IT.get(message, message)
    return EN.get(message, message)


def import_message(message):
    """Translate report framing without replacing strings within names or descriptions."""
    if language.get() == "it":
        return message
    if message in EN:
        return EN[message]
    match = re.fullmatch(r"(Riga|Record) (\d+): (.*)", message, re.DOTALL)
    if match:
        body = match[3]
        if body == "transazione eliminata esclusa.":
            body = "deleted transaction excluded."
        else:
            body = translate(body)
        return f"{'Row' if match[1] == 'Riga' else 'Record'} {match[2]}: {body}"
    for source, target in (
        (
            "Valute conservate separatamente, senza conversione: ",
            "Currencies kept separate, without conversion: ",
        ),
        ("JSON non valido: ", "Invalid JSON: "),
    ):
        if message.startswith(source):
            return target + translate(message[len(source) :])
    for source, target in (
        (" non può essere ignorato.", " cannot be ignored."),
        (
            ": membro disattivato nel gruppo; riattivalo prima dell’import.",
            ": member disabled in the group; reactivate them before importing.",
        ),
        (
            ": mittente e destinatario devono essere diversi.",
            ": sender and recipient must be different.",
        ),
    ):
        if message.endswith(source):
            return message[: -len(source)] + target
    return message
