# Pulizia e conservazione dati prima della produzione

Placeholder operativo da completare prima del passaggio in produzione.

## Obiettivo

Evitare che log, storici tecnici, run AI, sincronizzazioni e file di test crescano senza controllo nel tempo.

## Cosa esiste oggi

### Log runtime

- Pagina: `Log`
- Persistenza: non persistente, solo memoria backend
- Limite attuale: ultimi 200 eventi
- Rischio DB: nessuno
- Nota: si perde al riavvio backend

### Storico Incoming

- Tabelle:
  - `storico_eventi_acquisition`
  - `storico_valori_acquisition`
- Persistenza: DB
- Contenuto: eventi e modifiche valori sulle righe Incoming
- Rischio: crescita progressiva con uso reale, modifiche manuali, conferme, correzioni AI

### Run Assistente AI

- Tabella: `acquisition_processing_runs`
- Persistenza: DB
- Contenuto: stato job, fase, contatori, errori, documenti coinvolti, email
- Rischio: crescita moderata, soprattutto con test e run falliti

### Sync Quarta

- Tabella: `quarta_taglio_sync_runs`
- Persistenza: DB
- Contenuto: esiti aggiornamenti Quarta
- Rischio: crescita costante se il sync resta frequente

### Documenti e file derivati

- Contenuto: PDF, immagini, Word, pagine derivate, file caricati
- Rischio: maggiore impatto su disco rispetto agli storici testuali

## Decisioni da prendere prima della produzione

- Durata conservazione storico Incoming.
- Durata conservazione run AI.
- Durata conservazione sync Quarta.
- Regola per file caricati ma non collegati a righe valide.
- Regola per file di test o batch falliti.
- Chi puo eseguire la pulizia.
- Se serve esportazione prima della cancellazione.

## Proposta iniziale

- Storico Incoming: conservare 2-3 anni.
- Run Assistente AI: conservare 6-12 mesi.
- Sync Quarta: conservare 3-6 mesi, mantenendo lo stato corrente delle righe.
- Documenti non collegati o test: cancellazione controllata dopo validazione admin.
- Certificati finali Word/PDF: non cancellare senza regola qualita esplicita.

## Implementazione futura

- Creare comando admin di manutenzione.
- Aggiungere simulazione prima della cancellazione.
- Mostrare conteggi: righe, file, spazio stimato.
- Scrivere esito pulizia in uno storico persistente dedicato.
- Bloccare cancellazioni su certificati finali chiusi.

## Stato

Da completare prima della produzione.
