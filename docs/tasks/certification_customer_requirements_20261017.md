# Requisiti cliente nella lista Certificazione — 17/10/2026

## Perimetro approvato

Un solo tag rosso sotto Cliente nella lista OL, come in DDT da certificare.
Clic: finestra nella stessa pagina con i requisiti, separati per articolo F3.
Nessuna nuova colonna o modifica di filtri, stato certificazione, Word/PDF,
seconda pagina, permessi o dati. Solo sviluppo locale; deploy e commit/push
richiedono indicazione separata.

## Audit e scelta

- Il tag DDT usa le schede attive in `/customer-requirements`: priorità al
  codice esatto, poi famiglia senza le ultime due cifre. Più schede di famiglia
  sono alternative da verificare, mai una selezione automatica.
- Non esiste un flag "seconda pagina richiesta" distinto: il tag indica la
  presenza dei requisiti per l'articolo, NON una pagina aggiuntiva già caricata.
- Riscontro Alpha read-only precedente all'intervento: OL2026000962,
  DDT 2367-01/10/2026, F3 1142000100, scheda attiva OMF ID172; note con richiesta
  del grafico e tabella trazione. Nessun certificato/seconda pagina ancora
  presente: il tag deve essere disponibile anche prima della loro creazione.
- Nella lista OL i vecchi F3 sono stringhe aggregate: non passarle al resolver
  numerico, che concatenerebbe due codici. Nuovo campo di sola risposta
  `customer_requirement_articles`: articoli Quarta, righe DDT già caricate,
  candidati CertiOL già utilizzati dalla lista (raw/ddt/ready/medium).
- Nessuna interrogazione remota aggiuntiva per OL. I candidati `review` non
  assegnati sono esclusi; i `medium` mantengono un avviso nella finestra.
  Una fonte certa dello stesso F3 prevale sul solo candidato. Le righe DDT
  esplicitamente di altro OL non vengono usate per il tag. Mai associazioni
  per solo nome cliente, codice materiale fornitore o stringhe F3 concatenate.
- Deduplicazione per codice mantenendo gli zeri iniziali; nessuna riscrittura
  delle fonti. Schede attive senza checkbox ma con note restano consultabili.
- Clic sul tag non propaga il clic alla riga OL. Errori di caricamento requisiti
  mostrano un avviso e Riprova; non sono scambiati per assenza di requisiti.

## Verifiche locali eseguite

- Backend: 23 test `test_quarta_taglio_esolver.py`, 15
  `test_quarta_taglio_word_filters.py`, 46 `test_quarta_taglio_ddt_queue.py`:
  **84 superati**, con mock/SQLite e file temporanei, senza scritture Alpha.
- Frontend: tutti i 31 test Node superati (resolver, filtri, generazione,
  permessi, scadenze e avvisi DDT, payload valutazione e provenienza dati).
- Build production riuscita. Restano gli avvisi non bloccanti su Browserslist
  datato e dimensione bundle; nessun aggiornamento dipendenze in questo lavoro.
- Playwright sulla pagina React locale, API tutte simulate: singolo F3,
  più F3 e DDT ripetuti, assenza DDT, OL completato, scheda inattiva,
  nessun requisito/nessun F3, alternative di famiglia e candidato da verificare.
  Apertura senza navigazione, Chiudi/Escape, ordinamento, errore API e Riprova,
  testi cliente lunghi, schermate 1920/1440, nessun errore JavaScript o scrittura.
- Regressione browser pagina DDT: requisiti, ambiguità, finestra generazione
  PDF simulata, fallimento/riprova/completamento e permessi superati.
- Screenshot ispezionati: `tmp_eval/certification-requirements-1920.png`,
  `tmp_eval/certification-requirements-1440.png`,
  `tmp_eval/certification-requirements-multi.png`.
  Script temporaneo `tmp_eval/packages_qa/certification_requirements_check.mjs`;
  regressione `ddt_actions_check.mjs`. Artefatti temporanei, non necessari al deploy.
- Backend locale aggiornato verificato tramite OpenAPI (nuovo campo presente).
  Il frontend abituale 5173 serve ancora il codice precedente: l'utente ha
  rinviato il riavvio ("No, lo facciamo dopo"). Vite temporaneo 5174 usato per
  le prove e poi fermato. Questo non è un errore della nuova funzionalità.

## Passaggio Alpha

Pubblicare insieme backend/frontend; nessuna integrazione DB, recupero storico,
pulizia o rigenerazione. Checklist nel runbook
[`alpha_soft_update_server.md`](../deploy/alpha_soft_update_server.md).
Le prove browser con API simulate non sostituiscono il controllo post-deploy
dei dati Alpha; non è stata eseguita alcuna operazione su Alpha in questo intervento.
