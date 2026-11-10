# Filtro Requisiti cliente in Certificazione — 10/11/2026

## Perimetro approvato e significato

Nella lista OL di **Certificazione**, menu Requisiti cliente accanto ai filtri
Word: Tutte (predefinita), Con requisiti cliente, Senza requisiti cliente.
Nessuna nuova colonna o modifica delle righe. Non riguarda il Registro
certificazione o la pagina DDT da certificare.

La presenza segue il tag rosso già esistente: basta un F3 dell'OL con scheda
attiva, anche solo note, con codice esatto oppure famiglia senza le ultime due
cifre. Zeri iniziali conservati; non si confronta il nome cliente e non si
concatenano F3 diversi. Schede alternative di famiglia restano consultabili con
il loro avviso: il filtro non sceglie un'alternativa. Non indica una seconda
pagina già caricata, un PDF chiuso o requisiti già soddisfatti.

Esempio: un OL con articoli 1142000100 e 096007830 resta "Con" se almeno uno
ha requisiti. Una scheda disattivata non basta; un OL senza articoli risolti
non ha un'associazione da mostrare. Il filtro non inventa associazioni.

## Audit, implementazione e mitigazioni

- La pagina prima arricchiva i candidati CertiOL solo dopo la paginazione.
  Filtrare quei 25 elementi nel browser avrebbe nascosto risultati validi.
  Il nuovo filtro viene applicato sul server dopo i filtri già esistenti e
  **prima di ordinamento, conteggio e paginazione**; si combina in AND con loro.
- Fonti: articoli Quarta, DDT locali/storici operativi già disponibili e
  candidati CertiOL secondo le regole già utilizzate dal tag
  (`raw/ddt/ready/medium`, non `review`). Le righe DDT di altro OL sono escluse.
- Quando attivo, legge le famiglie attive dal DB e i soli OL potenzialmente
  pertinenti dalla vista CertiOL esistente, con SELECT parametrizzata in blocco
  per famiglia; non esegue una query per ciascun OL. Restituisce l'intero
  contesto candidato dell'OL: non cambia conteggi candidati, anomalie raw o
  soglie di confidenza. Blocchi massimi 500 famiglie/1000 parametri.
- Anche gli OL già positivi da Quarta/DDT mantengono gli altri F3 nei dettagli.
  Con Tutte resta il percorso precedente, senza la nuova lettura globale.
- Un errore del DB o della connessione eSolver configurata non diventa una
  falsa assenza di requisiti: il filtro restituisce errore, senza vecchie righe
  visualizzate come nuovo risultato. Si può scegliere Tutte e riprovare.
  In un ambiente senza integrazione configurata/attiva usa le fonti disponibili,
  come già avveniva per i tag. Non garantisce F3 non ancora acquisiti.
- Conteggi, appartenenza e tag di una risposta usano la stessa istantanea.
  Il normale aggiornamento dei DDT delle righe caricate può acquisire dati
  successivi a quell'istantanea: entrano nella classificazione alla richiesta
  seguente, su tutto l'insieme, non riclassificando solo la pagina dopo il totale.
- Campi API additivi: `requirements_filter` e `has_customer_requirements`
  nullable per compatibilità. Un risultato filtrato conserva il tag noto anche
  se fallisce la distinta API dei dettagli: tag disabilitato e avviso con Riprova,
  non assenza silenziosa. All'avvio senza dettagli le nuove scelte attendono
  il caricamento; Tutte resta accessibile.
- Selezione salvata nello stato di sessione esistente, anche tornando dal
  dettaglio. Vecchie sessioni -> Tutte. Risposte tardive/append precedenti
  ignorate dal controllo di richiesta già presente.
- Nessuna nuova migrazione, modifica di permessi, stato qualità, Incoming,
  Word/PDF, ereditarietà o sorgenti AI. Il filtro aggiunge sole letture;
  la pagina conserva le sincronizzazioni/scritture preesistenti del suo GET.
  **Non usare una GET operativa Alpha come audit privo di effetti.**

## Verifiche locali

- Contratto condiviso Python/JavaScript: esatto, famiglia, zeri iniziali,
  disattivato, sole note, più articoli, alternative ambigue, stringa aggregata
  rifiutata, dati mancanti, sconosciuto, codice scheda formattato, nessuna scheda.
- Test lista: positivi oltre i primi 25 OL, totale/offset/limite, ricerca e Word,
  contesto legacy, troppi candidati review, DDT stesso/altro OL, più F3,
  istantanea stabile e richiesta successiva aggiornata, default invariato.
- Provider e API: query unica simulata con 16.000 OL, dati fuori perimetro
  esclusi, due blocchi di famiglie senza duplicati, errori configurazione/query,
  valori non validi respinti prima del servizio, default API Tutte.
- Browser Playwright sulla pagina React reale a 1920/1440, tutte le API
  intercettate, 61 OL simulati: 31 positivi oltre la prima pagina, carica altri,
  testo/Word, ordinamento, persistenza, finestra/Escape, 11 colonne, nessun
  debordo della pagina, risposta append tardiva, errore/riprova e tag noto
  con dettagli temporaneamente mancanti. Nessun errore JS o richiesta mutante.
  Screenshot ispezionati in `tmp_eval/certification-requirements-filter-*.png`;
  script `tmp_eval/packages_qa/certification_requirement_filter_check.mjs`.
- Build production e 48 test frontend superati. Avvisi preesistenti non
  bloccanti: Browserslist datato e bundle grande; dipendenze non aggiornate.
- Suite ufficiale backend `pytest tests`: **936 superati, 177 saltati** per
  prerequisiti opzionali non attivati (fra cui PostgreSQL/render dedicati).
  Successivamente aggiunto il test della rotta API e rieseguito il file mirato:
  **28 superati**, compreso il nuovo test. I test dei filtri Word e dell'eSolver
  restano verdi: ultimo controllo combinato **66 superati** dopo revisione finale.
  Superato anche lo script browser precedente del tag/dettagli
  per singolo F3, più F3, schede ambigue/inattive, errore e Riprova.
- Il primo tentativo senza specificare `tests` ha raccolto anche due script AI
  temporanei omonimi e si è fermato in raccolta: nessuna chiamata AI eseguita.
  Risolto limitando la raccolta alla cartella ufficiale, senza cancellare cache
  o file dell'utente. I fallimenti iniziali del nuovo collaudo browser erano
  attese non sincronizzate/clic sul contenitore dell'intestazione: corretto lo
  script, non modificata la logica di ordinamento dell'app per farlo passare.
- Prove su container isolato senza rete, codice montato in sola lettura e
  database temporanei. Nessun documento inviato all'AI, nessun dato Alpha letto
  o modificato. Le prove SQL del provider sono simulate: tempi e piano reale
  della SELECT SQL Server vanno verificati nel preflight del deploy autorizzato.

Il frontend abituale non viene riavviato senza accordo: per il browser è stato
usato Vite temporaneo 5174, fermato al termine. Commit/push e deploy richiedono
indicazione separata.
