# Unione certificato-first e DDT: conservazione note e date

## Stato — 18 settembre 2026

Correzione concordata, implementata e verificata in locale. Commit e push
autorizzati dall'utente dopo i test. Nessun deploy Alpha; nessuna migrazione DB.

## Causa verificata

L'unione copiava nota e date soltanto se la riga certificato aveva gia una
valutazione e la riga DDT non l'aveva. Una nota salvata prima della valutazione
poteva quindi andare persa; una data vuota poteva sovrascriverne una compilata.
La nota valutazione puo essere salvata anche sulla riga solo DDT: non va confusa
con le note tecniche estratte dal certificato.

La normale pagina Valutazione non consente invece di compilare la data su una
semplice riga solo DDT non confermata. Il conflitto fra due date resta protetto
anche per dati preesistenti o casi particolari.

## Regole approvate

- Una sola nota: conservarla. Note uguali: conservarne una sola.
- Note diverse: conservare entrambe nel campo, con le etichette
  `Da certificato:` e `Da riga DDT:`. Nessun limite aggiuntivo o troncamento.
- Una sola data accettazione, oppure date uguali: conservarla.
- Date diverse: mantenere quella della valutazione gia presente; se entrambe
  le righe hanno una valutazione, mantenere quella della riga DDT, coerentemente
  con la valutazione che l'unione gia conservava.
- Date diverse e nessuna valutazione: chiedere quale mantenere prima dell'unione.
  Annullando, le righe rimangono separate. La scelta deve coincidere con una
  delle date correnti: una scelta diventata obsoleta ripresenta la domanda.
- Nel rematch automatico, quest'ultimo conflitto lascia le righe separate e
  registra nello storico la necessita del collegamento manuale.
- Conservare nello storico i valori originali di entrambe le righe e il risultato.
- Anche data ricezione e data richiesta non vengono cancellate da valori vuoti;
  per due valori non vuoti resta la precedenza preesistente.

Nessuna nuova regola di accettazione, obbligatorieta, scoring del match o modifica
delle conferme chimica/proprieta/note. Le regole preesistenti di colli, estrusione,
valutazione e chiusura rimangono invariate.

## Implementazione e protezioni

- Regole condivise in `backend/app/modules/acquisition/quality_merge.py`.
- Controllo conflitto prima di modificare il collegamento, in entrambe le direzioni.
- Lock delle due righe in ordine di ID e rilettura dei campi manuali.
- Collegamento e unione nella stessa transazione; anche indicizzazione/OCR
  richiamati dal collegamento rispettano il salvataggio differito. Gli altri
  chiamanti mantengono il comportamento precedente tramite il default `commit=True`.
- API: risposta 409 strutturata `merge_acceptance_date_choice`; il nuovo campo
  opzionale `merge_acceptance_date` contiene la scelta dell'utente.
- UI collegamento documenti: finestra con le due date e pulsante Annulla.
- I valori originali completi sono salvati nelle colonne Text dello storico
  valori, non nel riepilogo breve di 255 caratteri.

## Test eseguiti

- 11 test mirati: note non valutate, note lunghe/diverse/uguali/vuote, date,
  tutti gli esiti qualita, scelta obbligatoria e scelta non valida, collegamento
  manuale nei due versi, stop del rematch automatico, rollback anche con OCR,
  indicizzazione senza commit intermedio e righe sorelle non modificate.
- Suite backend completa: **317 test superati** (pytest, directory `tests`).
- Suite frontend disponibile: **10 test superati**, inclusi errore strutturato
  e compatibilita dei messaggi di errore precedenti.
- Build frontend riuscita; restano gli avvisi su dimensione bundle e Browserslist.
- `git diff --check` superato.
- Verifica visiva successiva riuscita con Chromium/Playwright gia installato:
  componente React reale, risposte API simulate, nessuna scrittura sul database.
  Controllati desktop 1366x900 e mobile 390x844, annullamento senza richiesta,
  scelta di entrambe le date, percorso certificate-first e ripresentazione di
  una data cambiata. Nessun errore JavaScript. Screenshot ispezionati in
  `tmp_eval/merge_visual_20260918/`; script locale `tmp_eval/merge_visual_20260918.mjs`.
  I 409 del test sono risposte simulate previste, non errori del server reale.

## Disallineamento frontend locale rilevato

Il servizio su localhost:5173 restituisce ancora il componente e api.js senza
dialogo e payload strutturato, mentre gli stessi file dentro il container sono
aggiornati. Questo indica codice servito non aggiornato dal processo Vite;
non e stata accertata la causa del mancato aggiornamento automatico.
La verifica visiva e stata eseguita avviando Vite temporaneamente su
127.0.0.1:5174 dai file locali aggiornati. Istanza temporanea arrestata a fine test.
Il servizio abituale non e stato riavviato. Proposto riavvio del solo frontend
locale, su consenso dell'utente, seguito da verifica del codice HTTP servito.

Successivamente l'utente ha autorizzato il riavvio: eseguito sul solo frontend
locale. Verificati via HTTP dialogo, invio `merge_acceptance_date` ed
`error.payload` sulla porta 5173: tutti presenti dopo il riavvio.

## Prova integrata reale completata

Eseguita l'app frontend completa su 5173 con tutti i router e servizi backend
reali, collegati a PostgreSQL 16 temporaneo separato. Le chiamate API del browser
sono state inoltrate al backend di test senza simulare le risposte. Nessuna
modifica alle righe, ai PDF o al database dell'app locale abituale e di Alpha.
Job periodici, recupero run e integrazioni esterne non avviati nel server di prova.

Quattro coppie di righe inventate, con PDF di test, verificate in Chromium:

- Annullamento dopo conflitto: database invariato, righe separate.
- Scelta data certificato e scelta data DDT: entrambe persistite correttamente.
- Collegamento a partire dal certificato: navigazione verso la riga DDT riuscita.
- Valutazione gia presente: conservata la sua data, senza richiesta di scelta.
- In tutti i casi: entrambe le note conservate, due origini nello storico per
  note e date, valutazione non introdotta dove assente, sorgente eliminata solo
  dopo unione, refresh e ritorno alla griglia/rientro riusciti.
- Nessun errore JavaScript o risposta HTTP inattesa. Screenshot esaminati in
  `tmp_eval/merge_e2e_20260918/`. Script di prova in `tmp_eval/merge_e2e_20260918.mjs`
  e `backend/tmp/merge_e2e_server_20260918.py`, non parte del codice applicativo.

I due container temporanei `certi-merge-e2e-api-20260918` e
`certi-merge-e2e-pg-20260918`, creati con AutoRemove e database senza volume
persistente, vengono rimossi a fine verifica. Script e screenshot restano locali.

## Verifiche ancora da fare prima del deploy

- La prova integrata su PostgreSQL e completata; non e stata eseguita una
  simulazione concorrente multiutente. Verificare in staging autosave durante
  collegamento e aggiornamento delle date mentre il dialogo e aperto.
- Nessuna ricostruzione automatica dei dati eventualmente persi da unioni
  precedenti: richiederebbe un audit separato di storico/backup.
- Futuro deploy solo su autorizzazione, seguendo il MD Alpha soft e aggiornando
  backend e frontend insieme. Nessuna modifica ai documenti PDF originali.
