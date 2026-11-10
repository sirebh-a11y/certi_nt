# DDT da certificare — contatori e filtri chiari, 10/11/2026

## Perimetro approvato

Solo sviluppo locale. Tre contatori: **Aperti, Completati, Esclusi**.
Quattro scelte in Stato: **Tutti, PDF da generare, Incoming da completare,
Anomalie**. Completati/Esclusi/Archivio pre-avvio si scelgono solo da Vista.
Restano tutte le 13 colonne, requisiti cliente, scadenze, permessi e azioni.

Nessun deploy Alpha, commit/push o riavvio del frontend abituale implicito.

## Audit e incoerenze precedenti

- Il vecchio contatore Pronti Incoming sommava `ready + word_ready`, mentre
  Pronti lato Incoming filtrava soltanto `ready`. Inoltre non contava gli OL
  con Incoming completo ma altra anomalia: non era il conteggio di tutti gli
  Incoming completi. Rimosso il contatore, non i controlli che determinano i fatti.
- Da verificare sommava `review + quality_rejected` in alto, ma il filtro
  selezionava soltanto `review`. Da collegare significava OL assente in eSolver,
  non un riaggancio Word richiesto all'utente.
- Word pronto indicava un Word presente per la quota e Incoming pronto, ma
  non garantiva numero/data/conformità/quantità necessari al PDF diretto.
  Simulato lo stesso documento conforme/non conforme: medesimo stato interno
  `word_ready`, ma solo il primo aveva `pdf_action`.
- Vista e Stato ripetevano Completati, Esclusi e Archiviati; gli incroci potevano
  essere vuoti senza aiutare l'utente. I conteggi seguono ricerca/date/presenza
  eSolver, non Vista/Stato/pagina: questa regola resta e viene spiegata.

## Regole di presentazione e selezione

1. **Tutti** non limita ulteriormente la Vista scelta. In Aperti include anche
   prime certificazioni e righe con Word di riferimento non ancora associato
   alla singola spedizione. Non richiede di rifare/collegare manualmente il Word:
   il normale riuso automatico e la sua ereditarietà restano intatti.
2. **PDF da generare** richiede la `pdf_action` effettiva della precisa quota,
   non il solo file Word. Con gli stessi controlli esistenti su Incoming,
   identità/revisione, quantità, conformità, numero/date, esclusioni e archivio.
   Il server ricontrolla comunque tutto alla generazione: nessuna nuova deroga.
   È una disponibilità al momento della lettura, non una garanzia che la
   conversione non possa fallire: errore/riprova restano gestiti come prima.
3. **Incoming da completare** seleziona `waiting_incoming`: può esserci già un
   Word, ma manca una conferma/valutazione o il certificato fornitore. Non è
   sinonimo di Word da preparare. Le ragioni restano visibili.
4. **Anomalie** raccoglie `review`, qualità respinta, OL mancante, data DDT
   mancante e Word della quota presente senza PDF direttamente generabile.
   Per questi Word vengono mostrati motivi concreti (non conformità, conformità
   sconosciuta, quantità diversa, numero/data mancanti, PDF precedente).
   Il fallback chiede di aprire Certificazione per verificare, senza inventare
   elaborazioni in corso o automatismi fermi. Completati/Esclusi/Archivio sono
   esclusi da questa selezione, anche se l'Incoming attuale non è più pronto.
5. In riga: Da certificare per `ready`; Incoming da completare per l'attesa;
   PDF da generare soltanto quando disponibile; Word da verificare con motivo
   quando la quota ha un Word ma non la `pdf_action`. Conservate le etichette
   specifiche Word da aggiornare, Totale DDT da verificare, Qualità respinta ecc.
   Nessun nuovo obbligo di rigenerazione Word o conferma dei documenti riusati.
6. Gli utenti in sola consultazione vedono PDF da generare come testo, non
   ottengono il pulsante/permesso. Requisiti e finestra PDF restano gli esistenti.
7. Lo Stato si azzera cambiando Vista ed è disabilitato per le viste terminali;
   tornando ad Aperti/Tutti non rimangono combinazioni nascoste. Le righe di
   archivio e i ripristini autorizzati restano raggiungibili. Archivio pre-avvio
   non equivale a Presenza eSolver → Solo storico: quest'ultimo può contenere
   lavoro ancora aperto, non si deve archiviarlo o nasconderlo automaticamente.

Il filtro viene applicato sul server **prima di totale, ordinamento e pagina**.
Gli stati interni, `by_state` e `active` non cambiano: sidebar identica per gli
stessi dati. La nuova API accetta `state=pdf_ready` e `state=anomalies`, mantenendo
validi i vecchi filtri di stato per compatibilità; nessuna migrazione/schema DB.

## Fallback e salvaguardie

- Vuoto PDF: messaggio esplicito e indicazione Stato → Tutti per cercare le
  altre righe. Vuoto anomalie riferito ai filtri scelti, non a tutta l'app.
- Errore API: niente vecchie righe sotto il nuovo filtro, niente falsi zeri o
  messaggio Nessun DDT. Risposta incompleta/non valida diventa errore leggibile.
- Backend precedente che rifiuta il nuovo filtro: indicazione Seleziona Tutti e
  riprova; referente interno IT se persiste. Non simulare il filtro nel browser
  sulla sola pagina né passare silenziosamente a Tutti.
- Risposte tardive ignorate dal controllo di cancellazione già esistente.
  Aggiorna vista/Azzera permettono di ritentare. Resta l'avviso eSolver 4 ore.
- Nessuna scrittura dati per questo riordino, nessun recupero, pulizia o
  aggiornamento massivo dei documenti. Non cambiano i percorsi di Word/PDF,
  numerazione, seconde pagine, allegati, eSolver export, match o motore AI.

## Verifiche locali

- Suite ufficiale backend: **953 superati, 177 saltati** per prerequisiti
  opzionali non attivati (PostgreSQL/render dedicati). Nessun errore nella suite.
- 16 nuovi casi backend: alias e retrocompatibilità, PDF abilitati nella
  proiezione, dati mancanti/non conformità, oltre i primi 25, paginazione,
  conteggi/sidebar immutati, Word con Incoming incompleto, data DDT assente,
  PDF già chiuso e validazione delle rotte. Prima esecuzione con due errori
  nelle fixture (reparto simulato e Word fittizi mescolati tra lavorazioni):
  corrette le fixture, non indebolite le protezioni applicative.
- 51 test frontend superati; build production riuscita. Restano gli avvisi
  preesistenti Browserslist/bundle. Primo build bloccato dai permessi del
  processo esbuild: ripetizione autorizzata riuscita, nessuna modifica sicurezza.
- Browser React reale con API tutte simulate: tre contatori/quattro scelte,
  tutte le viste, 11 righe di prova raggiungibili, Word non conforme, OL/data
  mancanti, attesa con Word, archivio/ripristino visibile, 13 colonne e 1920/1440
  senza debordo pagina, requisiti, ruolo consultazione, risposta vuota, errore,
  riprova e risposta tardiva. Nessuna scrittura o errore JS. Script temporaneo
  `tmp_eval/packages_qa/ddt_work_filters_check.mjs`; screenshot ispezionati
  `tmp_eval/ddt-work-filters-1920.png` e `tmp_eval/ddt-work-filters-1440.png`.
  Verificata anche la scelta Incoming da completare a 1440: prima colonna dei
  filtri riservata ad almeno 210 px per non troncare il testo, senza ridurre font
  o aggiungere colonne. Controllo dimensionale aggiunto al collaudo browser.
- Superata anche la regressione browser esistente `ddt_actions_check.mjs`:
  requisiti/PDF stessa pagina, nome personalizzato, errore-riprova-chiusura della
  sola quota e permessi. Solo API simulate, nessun PDF aziendale generato.

Le prove backend usano container senza rete, codice in sola lettura, SQLite e
file temporanei, non i DB dell'app o di Alpha. Nessuna chiamata AI o eSolver.
Il Vite 5174 temporaneo è stato fermato dopo il collaudo; frontend abituale non
riavviato. Deploy Alpha non eseguito; commit/push soltanto su richiesta esplicita.
