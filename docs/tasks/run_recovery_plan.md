# Piano Recupero Run Interrotti

## Obiettivo

Evitare che un crash, un riavvio backend/PC, una perdita di corrente o una chiusura accidentale lasci la UI bloccata o i documenti non riutilizzabili.

Questo documento e' solo piano di lavoro. Non e' implementazione.

## Stato attuale rilevato

- I run automatici sono salvati in `acquisition_processing_runs`.
- Gli stati principali sono `in_coda`, `in_esecuzione`, `completato`, `errore`.
- I documenti caricati nel flusso batch sono `temporaneo` finche' il run non finisce bene.
- All'avvio del run i documenti vengono messi in `in_lavorazione`.
- A fine run riuscito i documenti diventano `persistente` e `indicizzato`.
- Se il run fallisce nel codice, i documenti vengono messi in `errore`.
- Se il backend/PC si interrompe di colpo, il run puo' restare `in_esecuzione` e i documenti possono restare `in_lavorazione`.
- Oggi il run non salva in modo strutturato gli ID dei documenti usati. Questo e' il punto debole per recupero e rilancio.

## Problemi da evitare

- UI bloccata perche' vede un run ancora `in_esecuzione`.
- File gia' caricati ma non rilanciabili.
- Utente costretto a ricaricare PDF gia' presenti.
- Duplicazione righe se il run viene rilanciato.
- Cancellazione accidentale di documenti o righe gia' create.
- Run chiuso troppo presto mentre AI o parsing stanno ancora lavorando.

## Strategia proposta

### 1. Salvare il legame run-documenti

Aggiungere una tabella dedicata, per esempio:

`acquisition_processing_run_documents`

Campi minimi:

- `id`
- `run_id`
- `document_id`
- `tipo_documento`
- `created_at`

Questo permette di sapere sempre quali documenti appartenevano a un run, anche dopo crash.

### 2. Controllo OpenAI prima di creare run

Oggi il run viene creato prima del controllo completo della chiave OpenAI.

Regola nuova:

- se `usa_intervento_ai = true` e manca la key, non creare il run
- mostrare errore subito
- non mettere documenti in `in_lavorazione`

### 3. Recupero all'avvio backend

All'avvio:

- cercare run `in_coda` o `in_esecuzione`
- chiuderli come `errore`
- `fase_corrente = errore`
- `ultimo_errore = Run interrotto da riavvio server`
- `finished_at = now`
- sbloccare i documenti collegati al run

Documenti:

- se erano `in_lavorazione`, riportarli a uno stato rilanciabile
- preferenza: `caricato` se temporanei, `indicizzato` se persistenti
- non cancellare nulla

### 4. Timeout run morto

Prima di:

- leggere run attivo
- creare nuovo run
- rilanciare run

fare pulizia dei run vecchi fermi.

Timeout proposti su `updated_at`:

- `in_attesa`, `preparazione`: 2 minuti
- `riga_ddt`, `match_certificato`, `rematch_cross_run`: 3 minuti
- `intervento_ai`, `vision_ddt`, `chimica`, `proprieta`, `note`: 6 minuti

Se `updated_at` e' piu' vecchio del timeout:

- run -> `errore`
- messaggio -> `Run interrotto o senza aggiornamenti`
- documenti collegati -> sbloccati

### 5. Rilancia

La UI deve mostrare sui run tecnici in errore:

`Rilancia sugli stessi documenti`

Il rilancio:

- non richiede nuovo upload
- usa gli ID documenti salvati nella tabella run-documenti
- richiama il flusso esistente
- non duplica righe perche' le funzioni attuali gia' cercano righe esistenti per documento o firma

### 6. Comportamento utente

Se l'utente chiude browser:

- il backend continua
- la UI si riaggancia al run attivo

Se perde internet:

- il backend continua
- al ritorno la UI legge run attivo

Se si spegne PC/server:

- al riavvio il run vecchio viene chiuso
- i documenti vengono sbloccati
- l'utente usa `Rilancia`

Se ricarica lo stesso PDF:

- il sistema puo' dire duplicato
- il flusso corretto non deve essere ricaricare, ma rilanciare dai documenti gia' presenti

## Implementazione proposta, in ordine

1. Aggiungere modello/tabella `run_documents`.
2. Quando parte un run, salvare i documenti collegati.
3. Spostare il controllo OpenAI key prima della creazione run.
4. Creare helper backend:
   - `recover_interrupted_runs_on_startup`
   - `expire_stale_autonomous_runs`
   - `unlock_run_documents`
5. Chiamare recovery in bootstrap backend.
6. Chiamare timeout cleanup in `get_active_autonomous_run` e `start_autonomous_run`.
7. Aggiungere endpoint `POST /automation/runs/{run_id}/retry`.
8. Aggiungere pulsante UI `Rilancia` solo per run in errore tecnico.

## Test minimi

- Run in esecuzione + riavvio simulato -> diventa errore.
- Run scaduto per `updated_at` vecchio -> diventa errore.
- Documenti del run morto -> non restano `in_lavorazione`.
- Rilancia usa stessi documenti.
- Rilancia non duplica righe DDT gia' create.
- Se manca OpenAI key, non crea run e non blocca documenti.

## Decisioni ancora da confermare

- Stato esatto dei documenti sbloccati: `caricato` o `indicizzato`.
- Testo definitivo in UI per run interrotto.
- Se mostrare anche una lista dei documenti coinvolti nel run errore.
- Se tenere timeout configurabile da env o fisso nel codice.
