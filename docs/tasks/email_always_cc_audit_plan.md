# Email: destinatario CC permanente

## Stato

Audit completato il 21 luglio 2026. Indirizzo CC Alpha confermato e implementazione locale completata dopo approvazione dell'utente.

Il codice non è ancora stato committato, pubblicato o installato su Alpha.

## Richiesta

Aggiungere un indirizzo email in copia conoscenza (`Cc`) a tutte le email inviate dall'applicazione, comprese le notifiche inviate al termine dei run di caricamento e analisi AI dei documenti.

L'indirizzo CC non deve essere scritto direttamente nel codice: deve essere configurabile insieme alle altre impostazioni email.

## Audit del comportamento attuale

### Quando viene inviata la notifica del run

Il flusso è in `backend/app/modules/acquisition/service.py`.

La notifica viene inviata in entrambi i casi terminali:

- dopo che il run è stato salvato con stato `completato`, i documenti sono stati marcati `indicizzato` e l'eventuale batch è stato marcato `completato`;
- dopo che il run è stato salvato con stato `errore`, i documenti sono stati marcati `errore` e l'eventuale batch è stato marcato `errore`.

Il fallimento dell'invio email non cambia l'esito del run: l'eccezione SMTP viene intercettata e registrata nei log.

### A chi viene inviata oggi

La funzione `_send_autonomous_run_notification` costruisce un elenco di destinatari usando:

1. `run.notification_email`, cioè l'email dell'utente che ha avviato il run, memorizzata quando il run viene creato;
2. `actor_email`, normalmente la stessa email dell'utente, eliminata se duplicata;
3. `run.admin_notification_email`, fotografia del valore configurato come **Email admin per report Assistente AI** al momento dell'avvio.

Per ogni destinatario viene inviata un'email distinta con intestazione `To`. Non viene attualmente impostata alcuna intestazione `Cc`.

### Destinatari riscontrati su Alpha

La configurazione `ACQUISITION_NOTIFICATION_ADMIN_EMAIL` è attualmente vuota e nella tabella `email_settings` non è presente alcuna configurazione alternativa. Di conseguenza, gli ultimi run completati hanno inviato solo all'utente che li aveva avviati:

- run `#5`: `marco.bee@forgialluminio.it`;
- run `#1`-`#4`: `marco.gorza@forgialluminio.it`.

Il campo esistente **Email admin per report Assistente AI** non è un vero CC:

- vale soltanto per le notifiche dei run AI;
- produce un secondo messaggio separato con destinatario `To`;
- non viene applicato automaticamente alle altre email, per esempio all'email di test della configurazione.

### Punto comune di invio

Tutte le email attualmente individuate passano da `EmailService._send_with_config` in `backend/app/core/email/service.py`.

I chiamanti attuali sono:

- notifica finale del run AI, sia completato sia in errore;
- email di test dalla pagina amministrativa **Email**.

Questo è il punto corretto in cui applicare un CC globale: eventuali future email che useranno lo stesso servizio erediteranno automaticamente la regola.

## Configurazione SMTP riscontrata su Alpha

- Server: `mail.forgialluminio.it`
- Porta: `587`
- Sicurezza: STARTTLS attivo
- Login: `certi@forgialluminio.it`
- Mittente: `CERTI_nt <certi@forgialluminio.it>`
- Fonte attuale: variabili del file `.env`, perché la tabella `email_settings` è vuota

## Indirizzo CC confermato per Alpha

L'indirizzo da inserire sempre in CC su Alpha è:

```text
certi@forgialluminio.it
```

La scelta è intenzionale anche se lo stesso indirizzo è già utilizzato come login e mittente SMTP. L'implementazione dovrà quindi mantenere:

- `From`: `CERTI_nt <certi@forgialluminio.it>`;
- `To`: destinatario principale dell'email;
- `Cc`: `certi@forgialluminio.it`.

Per Alpha la variabile server proposta sarà:

```text
MAIL_ALWAYS_CC_EMAIL=certi@forgialluminio.it
```

La password SMTP è un segreto e non viene riportata in questo documento né deve essere salvata nel repository Git. Deve restare esclusivamente:

- nella variabile protetta `SMTP_PASSWORD` del file `.env`; oppure
- nel campo cifrato `smtp_password_encrypted` quando la configurazione viene salvata dalla pagina amministrativa.

## Implementazione

### 1. Un solo campo configurabile per il CC globale

Aggiungere il campo opzionale `mail_always_cc_email` alle impostazioni email già esistenti, senza creare una configurazione parallela.

Fonti previste:

- variabile server `MAIL_ALWAYS_CC_EMAIL` come configurazione di base;
- colonna `mail_always_cc_email` nella tabella `email_settings` quando un amministratore salva la configurazione dalla pagina.

Come già avviene oggi, la configurazione salvata nel database prevale sul file `.env`; il comando **Ripristina configurazione server** torna ai valori del file `.env`.

Il campo accetta un solo indirizzo, perché la richiesta parla di un indirizzo CC permanente.

### 2. Campo nella pagina Email

Nella sezione **Mittente e report** aggiungere:

```text
Email CC sempre
[ indirizzo@forgialluminio.it ]
```

Testo di aiuto proposto:

```text
Riceve in copia tutte le email inviate dall'applicazione.
```

Il campo **Email admin per report Assistente AI** rimane separato, perché rappresenta una funzione diversa e limitata ai report dei run.

### 3. Applicazione centralizzata del CC

In `EmailService._send_with_config`:

- mantenere il destinatario principale nell'intestazione `To`;
- aggiungere `Cc` quando `mail_always_cc_email` è valorizzato;
- non aggiungere il CC se coincide con il destinatario `To`, confrontando gli indirizzi senza distinzione tra maiuscole e minuscole;
- continuare a usare `smtp.send_message`, che include automaticamente `To` e `Cc` nei destinatari SMTP;
- non cambiare oggetto, corpo, mittente o configurazione TLS.

In questo modo la regola vale per tutte le email correnti e future inviate dal servizio comune.

### 4. Evitare email duplicate nei report AI

Esiste un caso da gestire esplicitamente: se **Email admin per report Assistente AI** e **Email CC sempre** contengono lo stesso indirizzo, oggi il ciclo dei destinatari AI produrrebbe:

- una copia CC dell'email inviata all'utente;
- una seconda email separata inviata direttamente all'admin.

La proposta è escludere dal ciclo dei destinatari diretti del run l'admin che coincide con il CC globale. L'indirizzo riceverà così una sola copia del messaggio.

### 5. Database e compatibilità

Il bootstrap deve aggiungere in modo idempotente la colonna nullable `mail_always_cc_email VARCHAR(255)` alla tabella `email_settings`.

Compatibilità prevista:

- valore assente o vuoto: comportamento identico a oggi;
- installazioni esistenti: nessuna modifica alle configurazioni SMTP già salvate;
- nessuna modifica ai dati dei run o ai loro stati;
- nessuna modifica a caricamento, analisi AI, match o Incoming;
- nessun blocco del run se l'invio email fallisce.

## File modificati

- `backend/app/core/config.py`
- `backend/app/core/email/models.py`
- `backend/app/core/email/settings_schemas.py`
- `backend/app/core/email/settings_service.py`
- `backend/app/core/email/service.py`
- `backend/app/modules/acquisition/service.py`, soltanto per evitare il doppio invio quando admin e CC coincidono
- `backend/app/startup/bootstrap.py`
- `frontend/src/pages/email/EmailSettingsPage.jsx`
- `.env.example`
- nuovi test backend dedicati alle impostazioni e all'invio email

## Test da eseguire

Esito locale dell'implementazione:

- suite backend completa: `182 passed`;
- build frontend: completata correttamente;
- nessuna email SMTP reale inviata durante i test automatici.

### Test automatici backend

1. Con CC configurato, il messaggio contiene `To` e `Cc` corretti.
2. Il destinatario SMTP effettivo comprende sia `To` sia `Cc`.
3. Con CC vuoto, il comportamento rimane identico a oggi.
4. Se `To` e CC coincidono, viene inviata una sola copia.
5. Se admin report AI e CC coincidono, l'indirizzo riceve una sola email.
6. Il CC viene applicato sia al report di run completato sia al report di run in errore.
7. L'email di test include il CC globale.
8. Un indirizzo CC non valido viene rifiutato dall'API.
9. La configurazione DB prevale sulla variabile `.env`.
10. Il ripristino della configurazione server torna al valore `MAIL_ALWAYS_CC_EMAIL` del file `.env`.
11. Il bootstrap aggiunge la nuova colonna ed è ripetibile senza errore.
12. La password SMTP rimane cifrata e non viene mai restituita dall'API.

### Test frontend

1. Il campo **Email CC sempre** viene caricato e mostrato nella pagina Email.
2. Il valore può essere salvato e ritrovato dopo aggiornamento pagina.
3. Il campo vuoto disattiva il CC globale.
4. Un valore non valido mostra l'errore senza alterare le altre impostazioni.
5. Il ripristino al server mostra il valore proveniente da `.env`.
6. La build frontend termina correttamente.

### Prova SMTP reale, solo dopo autorizzazione esplicita

1. Impostare l'indirizzo CC confermato.
2. Inviare una email di test a un destinatario controllato.
3. Verificare che il destinatario principale la riceva in `To`.
4. Verificare che l'indirizzo permanente la riceva in `Cc` una sola volta.
5. Avviare un run controllato e verificare lo stesso comportamento sulla notifica finale.
6. Controllare i log senza esporre credenziali.

## Decisioni confermate

- CC permanente Alpha: `certi@forgialluminio.it`.
- Il valore deve essere configurabile, non scritto direttamente nel codice.
- La regola deve applicarsi a tutte le email inviate dal servizio comune.
- L'indirizzo non deve ricevere copie duplicate quando coincide con un destinatario già presente.
