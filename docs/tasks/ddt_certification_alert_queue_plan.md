# DDT da certificare - audit Alpha e piano di implementazione

**Stato:** fasi 1, 2A, 2B e 3 e protezioni 4C pubblicate; recupero storico eseguito solo in locale; verifica visiva integrata locale completata; audit e prerequisiti Alpha verificati in sola lettura; attivazione, recupero dati e deploy Alpha ancora da autorizzare

**Data audit:** 29/09/2026

**Ambiente verificato:** Alpha `certi-test.forgialluminio.it`

**Scopo del documento:** consegna operativa per proseguire il lavoro con Codex in VS Code.

## Seguito UI e passaggio beta (29/09/2026)

La verifica funzionale locale aveva lasciato aperte le frecce di ordinamento.
L'utente ha autorizzato **solo** queste per la pagina DDT: sono state aggiunte
in locale alle intestazioni, con ordinamento dell'intera lista filtrata prima
della paginazione. Il selettore Righe esistente (25/50/100/200) e le colonne
fisse restano come concordato.

Autorizzato anche l'avviso dopo quattro ore senza lettura eSolver riuscita:
stesso riquadro già presente, giallo tenue; eventuale errore resta rosso.
Il testo indica di contattare il referente interno IT. La pagina controlla
periodicamente lo stato senza rileggere l'intera coda a ogni minuto.
Al primo successo dopo un avviso, la pagina ricarica la tabella e mostra
«Collegamento eSolver ripristinato» con data e ora; dichiara l'elenco aggiornato
solo dopo che la nuova lettura della coda è riuscita.

Il numero elevato di quote storiche nella pagina e nel badge è accettato per
ora. Riduzione dei campi e data iniziale operativa beta vanno concordate con
il cliente, senza cancellare automaticamente lo storico. Nessuna modifica
applicativa o attivazione Alpha è autorizzata da questa nota.

Decisioni, stato UI, spiegazione dei passaggi mancanti e risposte alla mail
sono mantenuti in [Passaggio alla beta](beta_transition_plan.md).
Le sezioni successive conservano la cronologia delle singole fasi: le note
di lavoro ancora da fare nelle fasi iniziali vanno lette con gli esiti successivi.

### Scadenza calendario (30/09/2026, solo locale)

Autorizzata e implementata la scadenza di 7 giorni dalla **data DDT**, inclusa
come giorno 1: termine data + 6. Unico parametro `DDT_CERTIFICATION_DAYS=7`.
L'API calcola `certification_due_date` senza scrivere dati; la UI mostra il
termine sotto Data DDT. Giallo con due giorni residui contando oggi, arancione
nell'ultimo giorno, rosso da quello successivo. Il timer UI esistente aggiorna
l'avviso secondo il giorno `Europe/Rome`, anche al ritorno sulla scheda.
Data non disponibile: «Data DDT da verificare». PDF finale valido completato:
nessun avviso; stati, conteggi, filtri e collegamenti restano quelli esistenti.
Una scadenza superata non chiude né blocca la quota. Lo storico non viene
ringiovanito dalla data di recupero. Nessuna modifica al calendario KPI.

Walter ha comunicato invio serale eSolver alle 23:00 e raggruppamento delle
righe sorgente identiche sommando le quantità. Questa modifica non attua la
riconciliazione del duplicato locale, né conferma la spedizione esterna del PDF.
Dettagli e decisioni aperte nella sezione 6 del piano beta.

Verifica locale: 68 test backend superati e 2 saltati (prove PostgreSQL opzionali
non configurate in questa esecuzione); 8 test frontend superati, build riuscita.
Collaudo Playwright con API simulate a 1920/1440 px: avvisi, data mancante,
completati, campi lunghi e cambio giorno italiano verificati; nessuna scrittura
DB. Procedura browser recuperata e registrata in
`docs/development/browser_verification_windows.md`, richiamata da `AGENTS.md`.
Usato Vite temporaneo 5174 perché 5173 serviva ancora codice precedente;
frontend abituale non riavviato, nessun deploy né attivazione Alpha.

## Avanzamento locale dopo il procedi

L'utente ha autorizzato lo sviluppo locale. È stata realizzata la fase 1:

- `QuartaTaglioDdtWorkItem` conserva i fatti sorgente anche oltre la finestra eSolver;
- `QuartaTaglioDdtSyncRun` conserva esiti/timestamp e contatori, separando ultimo tentativo e ultimo successo;
- `ddt_snapshot.py` legge la vista completa e applica il batch in transazione;
- nuove tabelle create dal bootstrap `Base.metadata.create_all`, secondo la convenzione esistente, senza ALTER distruttivi;
- lock transazionale PostgreSQL contro esecuzioni concorrenti, più lock locale di processo;
- errori di lettura, righe non valide e conflitti di identità lasciano intatto lo snapshot;
- OL mancante promosso a OL noto solo quando l'abbinamento è unico;
- errori persistiti tramite codici fissi, senza testo del driver o credenziali;
- scheduler predisposto con `DDT_SNAPSHOT_ENABLED=false` di default.

La nuova sincronizzazione **non è stata attivata** sul database applicativo. I test usano dati simulati, SQLite e PostgreSQL temporaneo isolato. Nessun collegamento ad Alpha/eSolver è stato effettuato durante questa implementazione.

Le aggiunte qui descritte sono autorizzate dal procedi per la fase 1. Il vecchio documento `docs/development_rules.md` contiene vincoli del progetto inizialmente limitato al core: l'eccezione riguarda soltanto questa funzionalità approvata, non modifiche generali all'architettura.

La fase 1 è stata pubblicata su `main` con `c16cb7d4`; le fasi 2A/2B con `abcb0ee2`. Il successivo `procedi` ha autorizzato la fase 3 locale, non il deploy. Restano da decidere esclusione manuale, storico iniziale e soglie degli avvisi. La sincronizzazione è ancora disattivata: non considerare la coda operativa finché non saranno completati il collaudo integrato e l'attivazione concordata.

### Fase 2A - stati e API locali in sola lettura (29/09/2026)

Implementati:

- `ddt_queue.py`: proiezione degli stati correnti, senza persistire lo stato calcolato;
- `ddt_schemas.py` e `ddt_router.py`: contratto ed endpoint di lettura;
- `GET /api/quarta-taglio/ddt-work-items` e `/counters`, prima delle rotte dinamiche OL;
- accesso autenticato per IT, Qualità e Laboratorio, coerente con i reparti autorizzati alla pagina Certificazione;
- filtri testuali, date DDT, presenza nella sorgente, stato, storico completati; paginazione e ordinamento stabile per data DDT/id, date mancanti in fondo;
- contatori sulla popolazione filtrata per dati sorgente, indipendenti da stato/vista e paginazione; `total_items` conta invece il risultato effettivo della vista/stato selezionati;
- ultimo tentativo e ultimo successo separati, più flag di sincronizzazione attiva, senza inventare soglie giallo/rosso;
- rivalutazione Incoming con la stessa funzione già usata da Certificazione, estratta in un helper di sola lettura. La funzione preesistente di aggiornamento Quarta mantiene il comportamento di prima;
- nessuna chiamata a `get_quarta_taglio_detail`, conferma rapida, servizi remoti, refresh cache, generazione Word/PDF o scrittura durante i GET.

Stati restituiti: `completed`, `to_link`, `quality_rejected`, `waiting_incoming`, `word_ready`, `ready`, `review`.

`Pronto lato Incoming` significa che chimica/proprietà/note/qualità soddisfano le regole già esistenti. **Non significa che standard, conformità o PDF siano automaticamente autorizzati**: quei controlli restano nel flusso Certificazione.

La chiusura è prudente: richiede unit key esatta, identità strutturata coerente (OL, CodF3, DDT, documento, riga, lotto e ordine), quantità compatibile con il Float del certificato, stato `pdf_final`, versione attiva non annullata relativa allo stesso file e file presente/non vuoto nel percorso storage ammesso. Non viene analizzato il contenuto binario del PDF. Una chiave legacy, un PDF di altra quota o un file mancante non chiudono la segnalazione. Due certificati esatti generano verifica richiesta. Una quantità modificata dopo il PDF viene segnalata, senza modificare il PDF.

La verifica separata dei campi evita anche che una collisione del separatore `|` nella chiave storica CERTI chiuda la quota sbagliata; la chiave sorgente SHA-256 della fase 1 non cambia.

Un Word anticipato viene segnalato come candidato soltanto per lo stesso OL/CodF3, senza DDT né identità eSolver, e quando l'associazione è unica. Non viene assegnato o copiato dal GET. Più Word candidati o più quote possibili richiedono verifica; il risultato non cambia restringendo il filtro della pagina. Le regole di ereditarietà Word delle altre lavorazioni restano invariate.

Le anomalie hanno priorità sullo stato pronto: una riga con collegamento ambiguo non deve sembrare liberamente lavorabile. Il PDF esatto valido ha priorità su Incoming eventualmente modificato dopo la chiusura; la coda non invalida PDF già chiusi.

Correzione circoscritta alla fase 1: se eSolver corregge una data DDT prima illeggibile, viene rimosso il solo avviso `ddt_date_unrecognized`. Un conflitto `source_identity_changed` non viene cancellato automaticamente.

### Limiti espliciti annotati alla fine della fase 2A

- Il GET non modifica cache o certificati: uno snapshot vecchio non diventa automaticamente un'unità selezionabile nel dettaglio OL esistente.
- Raccordo successivamente realizzato nella fase 2B sotto descritta: selezione della quota storica nel dettaglio/creazione Word/chiusura PDF, senza dipendenza dalla finestra DDT eSolver e senza sostituire la cache corrente o PDF già chiusi.
- Nessun endpoint `sync` o `disposition` aggiunto in questa fase. Esclusione manuale, autorizzazioni relative e soglie temporali restano decisioni da confermare. Nessuna etichetta `Nuovo/non letto` con durata arbitraria.
- Nessuna importazione storica, nessuna attivazione di `DDT_SNAPSHOT_ENABLED`, nessuna modifica alle configurazioni Alpha.
- I GET valutano lato server la popolazione candidata prima della paginazione; al client arriva soltanto la pagina oppure i contatori. Le query di contesto sono suddivise in blocchi e Incoming viene valutato una volta per OL, non per ogni DDT. Prima di importazioni storiche estese misurare i tempi con il volume reale: il conteggio degli stati richiede ancora la lettura delle righe candidate, non è un conteggio SQL materializzato.
- Per questa prossima parte restare su Astra; valutare Sol per la successiva interfaccia quando il raccordo storico sarà collaudato.

### Test fase 2A

36 test dedicati alla coda: stati Incoming reali con dati sintetici, accettato/riserva/respinto, conferme mancanti, più materiali, AI in corso, solo DDT, scelta manuale, diametri 285/85 ambigui, cache Quarta obsoleta, storico, Word anticipato/ambiguo, più DDT/OL/righe/lotti, riapertura, versioni annullate, file mancanti e percorsi non ammessi, PDF legacy, duplicati, collisione di chiave, variazione quantità, filtro/paginazione su 510 elementi, autenticazione e autorizzazioni.

Il test di non interferenza controlla che durante la lettura vengano eseguiti solo `SELECT`, senza oggetti ORM modificati, commit, chiamate esterne o modifica della cache. Il test del refresh preesistente verifica che continui invece ad aggiornare normalmente lo stato Quarta.

Comando di regressione dalla radice:

```powershell
$env:PYTHONPATH = 'backend'
$ddtRegressionFiles = (rg --files backend/tests | Where-Object { $_ -match 'test_quarta_taglio_.*\.py$|test_esolver_export\.py$' })
python -m pytest $ddtRegressionFiles -q
```

Esito finale: **157 test superati, 2 saltati** (test PostgreSQL opzionali della fase 1, già collaudati separatamente nella fase precedente e non rieseguiti qui). Rimangono soltanto avvisi di deprecazione SWIG/AnyIO. `git diff --check` superato. UI non ancora realizzata, quindi nessuna verifica visiva o build frontend in questa fase. Nessun commit/push o deploy della fase 2A effettuato.

### Fase 2B - raccordo backend della quota storica

Implementata in locale dopo il successivo `procedi`:

1. `GET /api/quarta-taglio/{OL}?ddt_work_item_id={id}` apre precisamente la quota conservata. L'ID deve appartenere all'OL richiesto. Nessun collegamento inventato se manca OL/Quarta.
2. `POST /api/quarta-taglio/{OL}/word-draft` accetta `ddt_work_item_id` nel corpo JSON. Non combinarlo con `candidate_cod_f3`.
3. Dopo la creazione, gli ID eSolver e la chiave già salvati sul certificato permettono a download Word, rigenerazione e PDF di ritrovare la quota senza un nuovo campo DB. Se non esiste alcuno snapshot corrispondente, resta il percorso precedente.
4. Apertura della quota: valutazione locale di Incoming su oggetti temporanei, nessuna scrittura di cache/registro, nessuna assegnazione automatica del Word anticipato. La vecchia vista `CertiRigheDDT` non viene riletta. **Rimane la lettura di `CertiOL`**, come nel flusso precedente, per descrizioni e relazione raw/finished; non è la vista soggetta alla finestra DDT. Lo storico DDT non è quindi una copia offline di tutti i dati eSolver/Quarta.
5. Creazione: lock della quota e lock registro OL, conservazione della precisa identità, riuso del certificato esatto oppure del solo Word anticipato univoco. Le verifiche standard, conformità, conferma di non conformità e protezione del Word manuale restano attive. Nessuna creazione di record per le altre quote dalla sola selezione storica.
6. Legacy senza identità, doppia associazione, correzione eSolver ambigua o quantità cambiata rispetto a un certificato esistente producono `409` con richiesta di verifica. Non vengono scelti automaticamente altri DDT o altri Word. Il flusso di risoluzione manuale di questi conflitti non è stato aggiunto.
7. Download Word: controlla l'identità anche per file manuali senza content control; quando aggiorna i campi di un Word della quota storica, usa un nuovo file per non riscrivere un percorso condiviso. Rigenerazioni/upload/allegati del nuovo contesto non propagano il file ad altri record con lo stesso numero.
8. Chiusura PDF: controlla nuovamente la quota dopo la conversione e prima di salvare la chiusura. Una modifica intervenuta nel frattempo non può chiudere un PDF su dati superati. Il file prodotto da una conversione poi rifiutata può restare non referenziato nello storage; non diventa PDF valido né viene esportato. Nessuna cancellazione automatica di file introdotta.
9. Registro: se la cache corrente non contiene più quella quota, può usare la quantità dello snapshot con identità esatta; se la quota è ancora nella cache, mantiene quel dato. Non usa il peso Quarta come quantità spedita. Il fallback già usato nel certificato (`cdo_lega = ordine_cliente` quando ODVF3 manca) viene riconosciuto nel confronto quantità.

La risposta dettaglio aggiunge `ddt_work_item_id`, `ddt_source_present`, `ddt_last_seen_at`, `ddt_early_word_id`. La futura UI deve conservare l'ID della quota nella navigazione e nel comando Word. Dopo azioni OL-wide (standard, conferme Incoming, dati articolo) deve ricaricare il dettaglio con lo stesso ID, non sostituirlo con il dettaglio generico restituito dall'azione. La navigazione UI non è ancora stata modificata o collaudata.

Non tutte le eccezioni del mondo reale sono risolte: la riga resta visibile nella coda anche quando la quota non può essere aperta per identità incoerente, assenza Quarta o dati da verificare. Non introdurre un pulsante `Nascondi` per aggirare questi casi.

### Correzioni circoscritte emerse dai test 2B

- Il lettore data preesistente riconosceva erroneamente `77-01/09` dentro `77-01/09/2026` (data vuota) e poteva ottenere il 2009 con numeri DDT brevi. Ora cerca date con separatore coerente, preferendo l'anno a quattro cifre; restano supportate date slash/trattino e anno a due cifre. La correzione vale anche per il flusso precedente, perché l'helper è condiviso, senza modificare date già salvate.
- Un CDQ Quarta vuoto resta una riga bloccata invece di lasciare una lista materiale vuota e provocare errore nel dettaglio storico.
- Nel nuovo percorso, una quantità spedita assente resta assente: niente ripiego sul peso materiale Quarta.

### Collaudo e limiti fase 2B

26 nuovi test backend su database SQLite isolato e file temporanei, più 2 test concorrenti su PostgreSQL isolato, oltre alle regressioni Quarta/export. Testano selezione esatta, quota vecchia, working copy del Word, creazione ripetuta senza duplicati, Word anticipato univoco/ambiguo, manuale protetto, PDF già chiuso, riapertura, cambi sorgente prima/durante conversione, descrizione finished, date, quantità e accessi.

La costruzione del layout Word e il convertitore PDF sono sostituiti nei test del ciclo completo: il collaudo verifica collegamenti, stati e invarianti, **non la resa visiva dei documenti**. Il layout/generatore documenti non è stato cambiato. Nessuna chiamata reale eSolver/Alpha effettuata, nessun file o database applicativo modificato dai test.

Esito finale: **187 test superati, nessuno saltato**; inclusi i 2 test PostgreSQL della fase 1, rieseguiti, e i 2 nuovi test concorrenti. Rimangono soltanto avvisi di deprecazione SWIG/AnyIO. `git diff --check` superato.

Il collaudo PostgreSQL usa connessioni/transazioni distinte concorrenti, con gli stessi lock usati dal codice: due creatori della stessa quota producono un solo record; l'aggiornamento sorgente attende il lock e la modifica successiva della quantità viene rilevata. I test si abilitano con `DDT_TEST_POSTGRES_URL` e rifiutano host non locali o nomi database diversi da `certi_ddt_test*`. Creano e rimuovono un proprio schema temporaneo. Il contenitore PostgreSQL 16 dedicato è stato arrestato e rimosso; nessun volume dell'app è stato usato.

Le fasi 2A/2B sono state poi committate e pubblicate con `abcb0ee2`; nessun deploy effettuato. Sincronizzazione ancora disattivata.

La UI della coda e il collegamento alla quota esatta sono stati aggiunti nella fase 3 seguente. Restano collaudo integrato, dry-run/import storico autorizzato e scelta soglie/esclusioni. Nessuna attivazione o deploy implicito.

### Fase 3 - pagina DDT da certificare (29/09/2026)

- Nuova pagina `/quarta-taglio/ddt-da-certificare`, prima voce del flusso Certificazione, con accesso per gli stessi reparti della pagina Certificazione.
- Badge sidebar delle **righe attive globali** dall'endpoint `/counters`: si aggiorna all'ingresso e ogni due minuti con app visibile. Il conteggio della pagina usa invece i filtri sorgente applicati, come previsto dall'API; il badge non viene sostituito dal conteggio filtrato.
- Tabella paginata con DDT, OL, CodF3, cliente, quantità, ordini, stato Incoming, stato certificazione, motivi, ultima lettura e azioni. Filtri per ricerca generale, DDT, OL, CodF3, cliente, date, presenza nella vista eSolver, stato e vista attivi/completati.
- La riga apre `/quarta-taglio/{OL}?ddtWorkItemId={id}`. Il dettaglio invia `ddt_work_item_id` all'API, lo conserva dopo il Word e ricarica la medesima quota dopo le azioni OL-wide o sugli allegati. Il selettore CodF3 generico è nascosto nel contesto della quota storica per evitare un passaggio silenzioso a un'altra lavorazione.
- Righe senza OL o con identità sorgente incompleta restano visibili con motivo esplicito; il collegamento a Certificazione è disponibile solo quando i campi minimi della quota sono validi. Il link Incoming appare quando ci sono righe collegate.
- Stato sincronizzazione fattuale: ultimo successo e ultimo errore, senza soglie giallo/rosso arbitrarie. `Aggiorna vista` rilegge la coda locale; non forza la sincronizzazione eSolver. L'etichetta `Nuovo` e l'esclusione manuale restano da definire.
- Nessuna variabile di attivazione, migrazione dati, import storico o deploy in questa fase.

Verifica locale: build frontend riuscita. La verifica visiva con dati reali e il collaudo integrato end-to-end restano nella fase 5.

### Fase 4A - dry-run dello storico locale (29/09/2026)

La UI della fase 3 è stata pubblicata con il commit `0bdc2d72`. Dopo il successivo `procedi` è stato aggiunto un **report in sola lettura** in `backend/scripts/audit_ddt_legacy_cache.py`, con classificazione in `ddt_legacy_audit.py` e test isolati. Il comando usa `SET TRANSACTION READ ONLY` su PostgreSQL; non crea la nuova tabella e non importa nessuna riga. `--with-esolver` legge la vista completa attuale, senza scriverla. Se manca una base corrente affidabile, il report usa `source_baseline_required` e non dichiara sicura nessuna quota storica. Sorgente vuota in presenza di cache, chiavi duplicate, identità variate, dati mancanti, certificati ambigui e PDF non verificabili non vengono promossi a recuperabili.

Comando locale (con PostgreSQL del Compose avviato):

```powershell
$env:PYTHONPATH='backend'
python backend/scripts/audit_ddt_legacy_cache.py --local-compose --with-esolver
```

Risultato misurato sul **database locale**, confrontato con la vista eSolver completa il 29/09/2026:

| Misura | Esito |
| --- | ---: |
| Collegamenti OL nella vecchia cache | 15.838 |
| Collegamenti che contengono righe DDT | 244 |
| Righe DDT nella cache | 491 |
| Identità distinte nella cache | 490 |
| Quote storiche recuperabili per identità e campi minimi | 489 |
| Identità duplicata da verificare | 1 (2 righe con dati discordanti) |
| Quote attuali nella vista eSolver | 393 |

I DDT conservati nella cache locale sono datati **17/06–29/07/2026**; quelli della vista corrente **03/08–29/09/2026**. Le 489 quote non sovrapposte non hanno un PDF finale esatto e verificabile nel database locale. `Recuperabile` indica che possono entrare in una successiva importazione controllata; non certifica la correttezza commerciale del dato né autorizza automaticamente Word/PDF. La coppia duplicata resta esclusa dall'importazione automatica e richiede ispezione puntuale prima di scegliere se sono due quote o una correzione.

#### Caso da sottoporre al cliente nella prossima email sulle modifiche

Nella cache **locale** la lettura eSolver del 28/07/2026 (09:14 UTC) contiene due record per
`OL2026000466`, DDT `1934-17/07/2026`, `IdDocumento 5180631`, `IdRigaDoc 2`,
`RifLottoAlfanum 2026000466`, `CodF3 509001161`. Cliente, ordini e tutti gli altri
campi coincidono; solo `QtaUmMag` differisce: **2100** e **1**. I due record sono
nel medesimo snapshot della cache, non derivano da due aggiornamenti successivi.
Il codice legge entrambe le righe dalla vista `CertiRigheDDT` e le conserva senza
aggiungerne una seconda. Non è però possibile stabilire dalla cache se la vista
abbia duplicato la quota o se due registrazioni eSolver distinte richiedano un
ulteriore identificativo: quel DDT non è più nella finestra della vista corrente.

**Trattamento:** escludere entrambe dall'importazione automatica; non scegliere
2100, non scegliere 1 e non sommare a 2101. Nessun Word/PDF deve essere creato
automaticamente sulla base della coppia. Chiedere al cliente/eSolver di
controllare il documento `5180631`, riga `2`, e spiegare cosa rappresentano le
due quantità. Nella futura email al cliente richiamare il caso con la formula
«come volevasi dimostrare, abbiamo trovato un DDT con due righe indistinguibili
per l'app ma quantità diverse», chiedendo il chiarimento; comunicare che questi
casi rimangono in verifica fino a una regola confermata. Non inviare l'email
senza una successiva richiesta dell'utente.

La nuova tabella DDT non esisteva ancora nel database locale consultato, perché l'app aggiornata non era stata avviata lì. Nessuna tabella è stata creata durante il dry-run. Il report non dimostra la completezza di DDT mai transitati nella vecchia cache: per quelli servirebbe un'estrazione storica eSolver separata. I numeri locali non vanno applicati ad Alpha senza un dry-run sul suo database al momento dell'attivazione.

Verifica: 6 nuovi test del report superati; regressioni Quarta/eSolver **189 superate, 4 PostgreSQL opzionali saltate** nella suite offline (già collaudate nella fase 2B su PostgreSQL temporaneo). Prossima decisione: dopo visione del report, autorizzare o meno l'implementazione/esecuzione dell'importazione locale; la riga duplicata rimane comunque in revisione. Nessuna importazione o deploy è stata fatta.

### Fase 4B - recupero storico locale autorizzato (29/09/2026)

Il successivo `procedi` ha autorizzato l'importazione **sul solo PostgreSQL locale**.
`ddt_legacy_import.py` riusa la classificazione del dry-run e la funzione dello
snapshot corrente; lo script `import_ddt_legacy_cache.py` accetta solo
`--local-compose --apply`. Dopo una nuova lettura completa eSolver crea, se
necessarie, solo le due tabelle DDT già previste e registra snapshot corrente
e storico nella stessa transazione PostgreSQL, sotto il lock della sincronizzazione.
Se la sorgente è incompleta/duplicata o l'importazione fallisce, anche la
creazione delle tabelle viene annullata. La vecchia cache e i certificati non
vengono modificati. Le righe storiche importate mantengono come ultima lettura
il timestamp della cache; la data di uscita dalla vista è **data di rilevazione**,
non data eSolver conosciuta. La pagina le mostra come non più presenti nella
finestra eSolver, da verificare operativamente prima della certificazione.

Esito locale: 393 righe della vista corrente + 489 quote storiche univoche =
**882 work item**. La coppia `5180631/2` con quantità 2100/1 è rimasta nella
vecchia cache ma **non** nella nuova tabella; nessuna quantità è stata scelta o
sommata. Seconda esecuzione: zero nuove righe, 489 storiche già presenti, zero
conflitti. La lettura della coda su tutti gli 882 elementi ha restituito 882
attivi (49 da collegare, 807 in attesa Incoming, 14 pronti lato Incoming,
12 in verifica), senza oggetti ORM modificati e in circa 3,7 secondi sul PC
locale. Questi numeri sono una fotografia, non soglie o aspettative fisse.

Test: **192 superati, 4 PostgreSQL opzionali saltati** nella suite Quarta/eSolver;
9 test mirati di audit/import inclusi. Nessuna modifica a frontend, deploy Alpha,
flag `DDT_SNAPSHOT_ENABLED`, Word/PDF o dati del server. PostgreSQL locale era
spento prima della verifica ed è stato fermato nuovamente al termine.

Limite: il recupero riguarda solo le righe ancora presenti nella vecchia cache
locale. Non dimostra che ogni DDT storico eSolver sia stato visto dall'app; per
Alpha serve un proprio dry-run, decisione esplicita sull'importazione e collaudo
prima dell'attivazione periodica. Non usare i conteggi locali come dati Alpha.

### Passaggio futuro su Alpha: dati propri, non copia del locale

**Il commit/push del codice non autorizza un'importazione né un deploy Alpha.**
Lo script `import_ddt_legacy_cache.py` è volutamente limitato al Compose locale:
non copiarne o aggirarne il controllo per eseguirlo sul server. La modalità server
separata `recover_ddt_alpha.py` è ora implementata e testata in locale (sezione
4C sotto), ma non installata né eseguita su Alpha.

Ordine richiesto sul server, solo dopo nuova autorizzazione:

1. verificare che non ci siano run/caricamenti utenti in corso, seguire il
   Markdown di deploy soft e fare backup del **database Alpha** e dei file;
2. leggere in sola lettura la cache `quarta_taglio_esolver_links.rows`, le
   righe Quarta, i certificati/Word/PDF e la vista eSolver **dell'ambiente
   Alpha**, producendo un dry-run con conteggi e identità problematiche;
3. confrontare il report Alpha con lo stato reale della sua nuova tabella DDT:
   distinguere quote correnti, già importate, storiche univoche, completate,
   duplicate, modificate e collegate a certificati non univoci. Non usare i
   numeri locali (393/489/882) come condizione di importazione;
4. presentare report, conflitti e piano di gestione all'utente. I record
   discordanti restano fuori dall'automatismo; nessun DDT locale viene copiato;
5. solo dopo l'OK specifico, importare nella **stessa transazione** snapshot
   corrente e sole righe storiche sicure della cache Alpha, con lock e verifica
   d'idempotenza. Non riscrivere cache, Incoming, Word, PDF o certificati;
6. confrontare prima/dopo contatori, chiavi e qualche OL campione (più DDT,
   Word anticipato, PDF chiuso, dato ambiguo), verificare pagina e registro,
   poi decidere **separatamente** quando abilitare il job periodico.

Se il backup, la sorgente completa, il dry-run o la verifica post-import non
sono affidabili, fermarsi: il deploy del codice può restare con sincronizzazione
disattivata e non deve essere spacciato per recupero storico completato.

### Audit Alpha in sola lettura del 29/09/2026, ore 13:21 italiane

Autorizzato dopo il commit `98f06ff1`. Alpha esegue il commit
`901d491f56e06ab4291ce87d0a1ab96df4ae03d0`; i tre container sono attivi e PostgreSQL
è healthy. Le nuove tabelle DDT non sono ancora presenti. Il controllo ha usato
le configurazioni eSolver, la cache, i certificati e i file di **Alpha**: nessun
dato locale è stato trasferito nel database server. Gli helper di audit sono
stati caricati esclusivamente nella memoria di un processo Python separato via
stdin, senza installare file, lanciare bootstrap, sincronizzazione o migrazioni.
Transazione PostgreSQL `REPEATABLE READ, READ ONLY`, verificata con
`transaction_read_only = on`; a fine lettura zero oggetti ORM nuovi/modificati
e rollback. La simulazione della coda ha usato oggetti temporanei.

| Misura Alpha | Esito |
| --- | ---: |
| Collegamenti OL nella cache | 1.813 |
| Collegamenti con righe DDT | 202 |
| Righe/identità DDT distinte in cache | 415 / 415 |
| Righe correnti della vista eSolver completa | 393 |
| Righe correnti già nella cache Alpha | 233 |
| Righe correnti non ancora nella cache Alpha | 160 |
| Quote storiche recuperabili dalla cache Alpha | 182 |
| OL / DDT distinti dello storico recuperabile | 90 / 62 |
| Duplicati cache o sorgente, quantità discordanti, conflitti certificato identificati | 0 |
| Totale simulato dopo recupero | 575 |
| PDF finali esatti verificati su file/versione Alpha | 8 |
| Segnalazioni attive simulate | 567 |

Le 182 quote storiche sono datate **02/07–30/07/2026**, tutte oltre 60 giorni;
le 393 correnti **03/08–29/09/2026**. Nessuna candidata storica è ancora dentro
60 giorni e nessuna quantità corrente/candidata risulta nulla o negativa.
Le 233 identità comuni tra cache e vista corrente coincidono nei campi
confrontati. Nessuna collisione aggiuntiva è emersa simulando il controllo
documento/riga/lotto dell'importatore sulle 182 candidate Alpha.

Distribuzione simulata: **514 in attesa Incoming** (332 correnti + 182 storiche),
**49 senza OL**, **2 pronti lato Incoming**, **2 Word pronti da completare**,
**8 completati**. Nessuna nuova ambiguità Word rilevata nel campione. I controlli
di standard/conformità restano necessari nel normale flusso; "pronto lato
Incoming" non certifica automaticamente il documento.

La coppia locale `5180631/2`, OL `OL2026000466`, quantità 2100/1 **non è presente
nella cache Alpha disponibile**. Il caso resta documentato per la futura email:
la sua assenza su Alpha non dimostra che eSolver lo abbia corretto.

Questi conteggi sono una fotografia: prima dell'importazione reale occorre
rifare il dry-run. Non garantiscono il recupero di DDT mai memorizzati da Alpha.
Il limite SQL esatto della vista resta da confermare con eSolver, come già
documentato; il campione è coerente con una finestra di circa 60 giorni.

### Due limiti rilevati nell'audit (corretti in locale nella fase 4C)

Il campione Alpha non li presenta, ma le prove su SQLite **solo in memoria**
hanno riprodotto due casi nel codice locale pubblicato:

1. **Candidati storici con stesso documento/riga/lotto e OL differenti.** Il
   dry-run dichiara due candidate recuperabili; `import_legacy_cache` inserisce
   la prima e scarta la seconda tramite `by_base`. Invertendo l'ordine della
   cache cambia l'OL importato. Le cache dei diversi OL potrebbero risalire a
   momenti diversi: senza prova che siano quote simultanee non si può scegliere
   arbitrariamente. Proposta: classificazione preventiva dell'intero gruppo,
   identica per dry-run e import, lasciando entrambe in verifica se non è
   distinguibile una correzione da due quote reali. Distinti lotti/righe e quote
   simultanee della vista corrente devono continuare a essere conservati.
2. **Vista vuota durante una sincronizzazione periodica dopo uno snapshot non
   vuoto.** `_apply_snapshot([], ...)` conserva le righe ma le marca tutte
   assenti e restituisce `success`; l'ultimo successo apparirebbe aggiornato.
   L'importatore iniziale già rifiuta sorgente vuota con cache, il job periodico
   no. Proposta: mantenere il precedente snapshot e ultimo successo, registrare
   un esito esplicito di sorgente vuota da verificare. Una prima lettura vuota
   senza dati precedenti resta un caso distinto; una vista realmente svuotata
   in seguito richiede verifica, non una cancellazione presunta.

Nessuna correzione applicativa implementata durante questo audit. Nessuna
evidenza che questi casi abbiano compromesso le 489 quote importate in locale
o le 182 candidate Alpha; nessuna importazione è stata eseguita su Alpha.

### Intervento proposto nell'audit e poi autorizzato (Astra)

- correggere i due casi limite sopra descritti, con decisioni di gruppo
  indipendenti dall'ordine e report coerente con ciò che verrà davvero inserito;
- predisporre una modalità Alpha esplicita per audit/import, verificando
  ambiente/database di destinazione e richiedendo un report recente approvato;
  nessun bypass del comando locale o collegamento implicito al database server;
- testare su PostgreSQL isolato rollback, ripetizione senza duplicati,
  concorrenza con snapshot, cambi dati tra report e applicazione, errore/zero
  righe sorgente e preservazione di cache/certificati/PDF;
- completare il collaudo UI del flusso coda → quota corretta → certificazione
  e verificare i tempi sui volumi reali prima di dichiarare conclusa la fase 5;
- per l'esecuzione futura su Alpha: backup prima del cambio codice e recupero
  nella finestra concordata, con accessi utenti/job che aggiornano la vecchia
  cache sospesi. Questo evita che un refresh elimini dalla cache i DDT vecchi
  prima del loro recupero. Rileggere i dati Alpha nella transazione protetta,
  poi avviare l'app e verificare i risultati. Deploy, import e attivazione del
  job rimangono autorizzazioni da ottenere secondo il piano concordato.

### Fase 4C - protezioni e procedura Alpha, solo sviluppo locale (29/09/2026)

Dopo il `procedi` sono state implementate e testate le seguenti correzioni:

- **Gruppo storico ambiguo:** stesso documento/riga/lotto con OL diversi nella
  sola cache storica → tutte le nuove candidate del gruppo restano escluse
  dall'importazione automatica. Invertire l'ordine non cambia il risultato.
  Quote simultanee nella vista corrente e lotti/righe distinti restano conservati.
  Nessuna correzione retroattiva delle quote già salvate.
- **Vista improvvisamente vuota:** se esistono DDT conservati, zero righe non
  aggiorna l'ultimo successo né marca tutti i DDT assenti. Registra
  `empty_source_requires_review`; la pagina spiega che sono mantenuti i dati
  dell'ultima lettura valida. Primo avvio vuoto senza dati precedenti distinto.
- **Modalità Alpha dedicata:** `backend/scripts/recover_ddt_alpha.py` usa
  `ddt_recovery.py`. `--preview` legge soltanto; `--apply` richiede un report,
  un backup PostgreSQL leggibile e `--maintenance-confirmed`. Nessun bootstrap,
  avvio del job o importazione implicita al deploy.

Il report vale **un'ora**, identifica il cluster/database Alpha e memorizza
un'impronta della sorgente completa, cache, righe Quarta, certificati/versioni,
nuova coda, file Word/PDF (presenza/dimensione/data modifica) e codice di recupero.
L'applicazione rilegge i dati dopo i lock: se qualcosa è cambiato, il report
è scaduto o riguarda un altro ambiente, si ferma senza importare e richiede
un nuovo report da esaminare. Non basta ricopiare il vecchio `plan_id`.
Il report non è una firma digitale e non deve essere modificato manualmente.

Il recupero usa solo i dati **Alpha**, non i 882 elementi del database locale.
Lock PostgreSQL comuni al job e lock sulle tabelle coinvolte impediscono una
scrittura concorrente durante l'operazione; un writer già attivo provoca
`recovery_inputs_busy`. Cache e certificati preesistenti non vengono riscritti.
Errore a metà operazione → rollback anche delle due nuove tabelle, se appena
create. La ripetizione con un nuovo report non duplica le quote storiche.
Il vecchio report dopo un'applicazione riuscita non è più valido.

Prerequisiti operativi: utenti/job sospesi nella finestra concordata, backup
DB e storage verificati, nuova immagine backend disponibile, sincronizzazione
automatica disabilitata. Il controllo dell'intestazione del dump nello script
**non sostituisce una verifica di ripristinabilità del backup**. Il ruolo di
manutenzione deve poter leggere `pg_control_system()` e creare le sole due
tabelle DDT: se non può, non aggirare il controllo con altre credenziali.
Comandi e ordine nel Markdown di deploy soft, sezione recupero DDT Alpha.

Verifiche locali: **210 test Quarta/eSolver superati, zero saltati**, inclusi
i test PostgreSQL su container temporaneo isolato senza volumi applicativi.
Coperti: ordine invertito, quantità discordanti, nessuna riscrittura cache,
report scaduto/altro ambiente, cambi sorgente/cache/certificati/file dopo
preview, errore/zero righe, concorrenza, idempotenza, rollback dati e DDL.
Build frontend riuscita; restano gli avvisi già presenti su Browserslist
obsoleto e dimensione bundle. Nessun aggiornamento dipendenze.

**Collaudo visivo locale completato:** lo strumento Computer Use continua a non
avviare Chrome/Edge per `windows sandbox failed: helper_unknown_error`, ma è
stato usato il browser di collaudo Playwright già presente nel progetto. Con i
dati locali reali la pagina ha mostrato 882 quote attive e 50 righe nella prima
pagina; la somma degli stati coincide con il totale. Verificati filtro
`In attesa Incoming` (807), combinazione con `Solo storico` (469), intervallo
date non valido, azzeramento filtri e contatori. Il collegamento della quota
DDT `#393` ha aperto esattamente
`/quarta-taglio/OL2026000997?ddtWorkItemId=393`; nel dettaglio sono rimasti
visibili quota, DDT, OL, CDQ e colata corretti.

A 1920 e 1440 px la pagina non deborda orizzontalmente; a 1440 px la tabella
usa correttamente il proprio scorrimento orizzontale. I due rilievi grafici
emersi nel primo controllo sono stati corretti e ricollaudati: la voce sidebar
mostra `DDT da certificare` per intero su due righe; OL e Cod. F3 non vengono
più spezzati, mentre ordine e conferma possono andare a capo soltanto sui
separatori normali. A 1920 px resta visibile anche l'azione `Apri
certificazione`; a 1440 px si usa lo scorrimento interno. L'unico errore console
è il `404` del solo `favicon.ico`; nessuna API della coda o di Certificazione ha
restituito errore e nessun errore JavaScript è stato rilevato. Prestazioni e
campioni reali Alpha restano da ricontrollare nel successivo passaggio
autorizzato; la fase 5 rimane aperta per Alpha, import e attivazione.

In questa fase nessun accesso/mutazione Alpha, nessuna nuova importazione nel
database applicativo locale, nessun commit/push/deploy né attivazione del job.

### Audit integrato finale locale (29/09/2026)

Ricontrollati importatore, classificazione dei gruppi storici, protezione della
sorgente vuota, report Alpha, lock, rollback, configurazione Docker e procedura
di deploy. Trovato e corretto un errore nei comandi del Markdown: dentro il
container `python scripts/recover_ddt_alpha.py` fallisce con
`ModuleNotFoundError: No module named 'app'`. Usare dalla directory `/app`
`python -m scripts.recover_ddt_alpha`; avvio con `--help` verificato nel container
locale. Nessuna modifica alla logica backend necessaria da questo audit.

Rieseguita l'intera suite Quarta/eSolver: **210 test superati, zero saltati**.
Il collaudo ha usato due container temporanei: PostgreSQL 16 senza rete esterna
e senza volumi applicativi, runner con sorgenti in sola lettura e storage
temporaneo. Inclusi i test di recupero ripetuto, report superato, writer
concorrente e rollback anche delle tabelle appena create. Entrambi i container
sono stati rimossi al termine. Nessun accesso Alpha o importazione applicativa.

Il controllo riguarda i casi della suite e il collaudo UI locale già descritto;
non sostituisce la verifica sui dati aggiornati Alpha né la prova operativa di
un nuovo PDF finale. Prossimo passaggio: commit/push del lavoro DDT dopo richiesta
esplicita, poi audit/preview Alpha e recupero/attivazione nelle autorizzazioni
previste dal piano. I report temporanei, gli screenshot e il Markdown separato
sulle dipendenze non fanno parte del commit DDT.

### Pubblicazione e nuova verifica Alpha in sola lettura (29/09/2026)

Il commit `a0c58bd5cc8c962e7da4ee568d391982efd2ee31` è pubblicato su `main`:
contiene le protezioni 4C, la procedura di recupero, i test e le correzioni
visive. L'utente ha autorizzato commit/push e prosecuzione delle verifiche,
ma ha esplicitamente rinviato il deploy Alpha al proprio successivo via.

Audit Alpha ripetuto alle **15:18 italiane**, usando il codice di classificazione
appena pubblicato solo nella memoria di un processo separato. Confermati:
393 quote correnti, 182 storiche recuperabili (62 DDT, 90 OL), zero duplicati,
zero conflitti identificati, zero differenze sui dati comuni cache/sorgente.
Simulazione: 575 quote totali, di cui 567 attive e 8 completate con PDF verificato;
fra le attive, 514 in attesa Incoming, 49 da collegare, 2 pronte e 2 con Word.
Transazione `READ ONLY` verificata, zero oggetti ORM nuovi/modificati, rollback.

Prerequisiti letti sul server: ambiente `production`, database `certi_nt` su
`postgres:5432`, URL pubblico Alpha corretto, directory storage presente,
identità del cluster leggibile e permessi CREATE sul database/schema pubblico
disponibili. Nessuna tabella creata per provarli. Sincronizzazione DDT disattiva;
le due nuove tabelle DDT non esistono ancora. Tre servizi attivi, PostgreSQL
healthy. `SOURCE_COMMIT` resta `901d491f56e06ab4291ce87d0a1ab96df4ae03d0`.

Questa lettura non è il report approvabile di `recover_ddt_alpha --preview`:
quello andrà generato con la nuova immagine nella finestra autorizzata e vale
un'ora. Prima di importare servono backup verificati e nuova approvazione sul
report. Nessun file installato su Alpha, nessun riavvio, deploy, import o avvio
del job. I numeri vanno riletti al momento dell'intervento.

### Precisazione emersa nell'implementazione

Le quattro righe senza OL che condividono documento/riga con quote aventi OL **non sono duplicati dimostrati**. L'audit mostra lotti/quantità distinti: vanno conservate finché un controllo specifico non prova il contrario. La condivisione di `IdDocumento + IdRigaDoc` da sola non autorizza l'esclusione.

### Verifiche fase 1

- suite offline dedicata a identità, persistenza, riconciliazione, errori, rollback e scheduler;
- verifica PostgreSQL locale con lock detenuto da un'altra connessione, rilascio del lock e violazione reale NOT NULL per verificare il rollback;
- regressioni su eSolver, filtri Word, quantità registro, riserva qualità ed export PDF;
- risultati e comando finale annotati a fine documento.

## Istruzioni obbligatorie per Codex

Prima di modificare il codice:

1. leggere completamente questo documento;
2. rileggere `docs/development_rules.md` e i documenti eSolver richiamati più avanti;
3. controllare il codice attuale e verificare che i riferimenti indicati non siano cambiati;
4. presentare al proprietario un audit aggiornato, il piano dei file da modificare, i rischi e i test;
5. attendere un suo esplicito **OK** o **procedi** prima di scrivere codice;
6. lavorare prima e solamente in locale;
7. non fare deploy Alpha finché non viene richiesto esplicitamente;
8. per un eventuale deploy Alpha seguire integralmente `docs/deploy/alpha_soft_update_server.md`;
9. non modificare dati Alpha durante l'audit e non inserire credenziali o password in codice, documentazione, test o log;
10. non alterare le logiche esistenti di Incoming, standard, certificazione, registro o PDF salvo quanto definito qui.

## Obiettivo funzionale

Creare una nuova pagina che avvisi l'utente quando eSolver espone un nuovo DDT collegato a un OL e mostri il lavoro di certificazione ancora da completare.

Nome proposto nella sidebar:

> **DDT da certificare**

Posizione proposta:

- prima voce della sezione `Flusso certificazione`;
- prima di `Carica Documenti`;
- accessibile con lo stesso permesso già usato per `Certificazione`, senza introdurre un nuovo ruolo se non necessario;
- badge con il numero delle unità ancora attive.

Una riga deve lasciare la vista attiva solamente quando il PDF definitivo della sua specifica unità DDT/OL è stato chiuso. L'apertura della pagina o della riga non equivale al completamento.

## Cosa non deve fare

- Non deve sostituire la pagina `Certificazione`.
- Non deve cambiare automaticamente lo stato di Incoming.
- Non deve confermare chimica, proprietà, note, qualità o standard.
- Non deve considerare il solo Word come lavoro concluso.
- Non deve unire righe basandosi soltanto sul numero DDT o soltanto sull'OL.
- Non deve cancellare una segnalazione solo perché la vista eSolver non restituisce più un DDT vecchio.
- Non deve usare `CertificatoPresente` come fonte di verità per il PDF CERTI.
- Non deve inventare un OL quando eSolver non lo fornisce.

## Risultato dell'audit Alpha

### Finestra temporale eSolver

Il 29/09/2026 la vista `dbo.CertiRigheDDT` ha restituito:

- 392 righe;
- 154 DDT distinti;
- 190 valori OL distinti contando anche il valore vuoto;
- 189 OL non vuoti;
- date comprese tra 03/08/2026 e 29/09/2026;
- età massima osservata: 57 giorni;
- nessuna data non interpretabile;
- nessuna riga oltre 60 giorni.

La cache locale Alpha conserva righe del 30/07/2026, oggi vecchie di 61 giorni, che non sono più restituite dalla vista. Le righe del 03/08/2026, vecchie di 57 giorni, sono ancora restituite.

Il comportamento è quindi coerente con un limite di circa 60 giorni. Non è possibile certificare dal solo campione se il limite esatto sia 58, 59 o 60 giorni, perché non risultano DDT dal 31/07 al 02/08. L'utente SQL configurato in CERTI possiede `SELECT`, ma non `VIEW DEFINITION`, sulla vista. Per confermare il valore SQL esatto occorre una delle seguenti informazioni da Matteo/eSolver:

- definizione della vista `dbo.CertiRigheDDT`; oppure
- permesso temporaneo o permanente `VIEW DEFINITION` sulla vista.

Questo dettaglio non cambia l'architettura necessaria: CERTI deve conservare localmente le righe già viste.

### Completezza dei collegamenti correnti

Sulle 392 righe correnti:

- 343 hanno un OL e formano 343 unità eSolver distinguibili;
- tutte le 343 righe con OL appartengono a uno dei 189 OL presenti anche nei dati Quarta correnti;
- non sono stati trovati OL valorizzati in eSolver ma assenti da Quarta;
- 49 righe hanno OL vuoto;
- 4 delle 49 righe vuote condividono documento/riga con quote collegate a uno o più OL, ma non sono duplicati dimostrati;
- 45 righe, relative a 44 righe documento, restano realmente senza OL utilizzabile.

Non emerge una perdita corrente degli OL valorizzati tra eSolver e Quarta. Le righe senza OL, invece, oggi non possono essere aperte correttamente in Certificazione.

### Stato del lavoro corrente

Tra le 343 unità correnti con OL:

- 8 hanno già un PDF finale esattamente collegato e non dovrebbero comparire nella vista attiva;
- 3 sono pronte lato Incoming e non hanno ancora il PDF finale;
- 332 non sono ancora complete lato Incoming;
- non sono state trovate unità correnti classificate come sola qualità respinta nel campione del giorno.

Conservando tutte le quote distinte, l'avvio della nuova funzione produrrebbe indicativamente:

- 335 unità con OL ancora attive;
- 49 righe senza OL da verificare;
- totale iniziale: circa 384 segnalazioni attive.

Questi numeri sono una fotografia dell'audit e non devono diventare valori fissi nei test o nel codice.

### Limite della cache attuale

Il sincronizzatore Quarta viene eseguito ogni 15 minuti, ma `sync_and_list_quarta_taglio()` aggiorna i collegamenti eSolver soltanto per gli OL della pagina restituita, normalmente 25 gruppi.

Al momento dell'audit:

- la cache locale conteneva 413 identità eSolver;
- soltanto 231 delle 392 identità correnti erano già in cache;
- 161 identità correnti non erano ancora state memorizzate dalla navigazione/paginazione;
- la cache conservava 182 unità uniche più vecchie di 60 giorni;
- queste 182 unità appartenevano a 90 OL;
- nessuna delle 182 risultava chiusa con PDF finale secondo la chiave esatta disponibile.

Quando un OL vecchio viene riletto dopo che il DDT è uscito dalla finestra eSolver, il collegamento corrente può essere sovrascritto con `DDT mancante`. Per questo la nuova pagina non deve appoggiarsi soltanto a `quarta_taglio_esolver_links`.

### Campo eSolver `CertificatoPresente`

Nell'audit tutte le 392 righe riportavano `CertificatoPresente = 0`, comprese otto unità per le quali CERTI possiede già il PDF finale.

Conclusione:

- il campo può essere conservato come informazione proveniente da eSolver;
- non deve determinare la scomparsa della riga;
- la fonte di verità deve restare `quarta_taglio_final_certificates` con PDF finale valido.

## Identità corretta di una segnalazione

L'audit ha confrontato più chiavi:

| Chiave | Unicità sulle 392 righe | Esito |
| --- | ---: | --- |
| `IdDocumento + IdRigaDoc` | 359 | insufficiente: una riga documento può appartenere a più OL |
| `IdDocumento + IdRigaDoc + ORP` | 390 | insufficiente per due casi senza OL |
| `IdDocumento + IdRigaDoc + ORP + RifLottoAlfanum` | 392 | univoca nel campione corrente |
| chiave unità CERTI completa | 392 | univoca nel campione corrente |

Chiave sorgente proposta per lo storico:

```text
IdDocumento + IdRigaDoc + ORP normalizzato + RifLottoAlfanum normalizzato
```

La chiave completa già prodotta da `_certifiable_unit_key()` deve restare la chiave di lavoro verso la certificazione e il PDF. Contiene anche CodF3, DDT, ordine cliente e conferma ordine.

Regola per una correzione eSolver:

- se cambiano DDT, CodF3, quantità o ordini ma la chiave sorgente resta uguale, aggiornare la stessa segnalazione mantenendo `first_seen_at`;
- se un ORP inizialmente vuoto viene successivamente valorizzato, riconciliare la riga tramite `IdDocumento + IdRigaDoc + RifLottoAlfanum` e trasformarla da `Da collegare` a riga collegata, senza lasciare un duplicato;
- se anche il lotto cambia e la riconciliazione è ambigua, non unire automaticamente: evidenziare `Dati eSolver modificati - verifica richiesta`.

## Casistiche obbligatorie

### Un DDT e un OL

Esempio:

```text
DDT 2349 -> OL2026001004
```

Mostrare una riga. Se Incoming è pronto, l'azione apre direttamente il dettaglio di Certificazione dell'OL e della specifica unità.

### Stesso DDT con più OL

Nell'audit sono stati trovati 59 DDT associati a più OL.

Esempio:

```text
DDT 2071 -> OL2026000499
DDT 2071 -> OL2026000657
```

Mostrare due lavori separati. Il PDF chiuso per un OL non deve chiudere l'altro.

### Stessa riga documento divisa tra più OL

Sono state trovate 24 righe documento con più collegamenti OL. Distinguere sempre tramite ORP e lotto, non solo tramite `IdDocumento + IdRigaDoc`.

### Stesso OL con più DDT

Sono stati trovati 40 OL associati a più DDT. Ogni unità resta indipendente. Se un PDF è pronto solo per un DDT, gli altri restano visibili.

### DDT senza OL

Le righe realmente senza OL vanno mostrate nella categoria `Da collegare` con:

- DDT e data;
- IdDocumento e IdRigaDoc;
- CodF3;
- cliente;
- quantità;
- motivo `OL non fornito da eSolver`.

Non consentire l'apertura diretta della certificazione finché manca l'OL e non tentare collegamenti automatici non certi.

### Word preparato prima del DDT

Quando esiste già un Word/raw senza DDT e successivamente arriva l'unità eSolver:

- non creare automaticamente un secondo lavoro Word;
- mostrare `Word già preparato - DDT arrivato, completare il PDF`;
- usare le regole già presenti per associare il draft all'unità;
- se l'associazione è ambigua, chiedere scelta manuale senza sovrascrivere dati.

### Incoming non completo

La riga deve essere visibile, con stato `In attesa Incoming` e azione per aprire le righe Incoming collegate. Non deve risultare pronta per la creazione del certificato.

### Qualità respinta

La riga deve restare visibile. Mostrare `Qualità respinta` e lasciare che siano le regole esistenti di Certificazione a bloccare o guidare il seguito. Non nasconderla dal promemoria.

### Accettato con riserva

La riga deve essere trattata secondo la logica esistente: visibile e lavorabile quando gli altri requisiti lo consentono. Non cambiare la valutazione.

### Nuovo DDT dopo un PDF già chiuso

Il nuovo DDT crea una nuova segnalazione anche se lo stesso OL possiede già un altro PDF finale.

### PDF annullato o riaperto

La relativa segnalazione deve tornare nella vista attiva. Un PDF annullato non è un completamento valido.

### Uscita dalla finestra eSolver

Quando una riga non è più restituita dalla vista per anzianità:

- mantenere lo storico locale;
- segnare `non più presente nella finestra eSolver`;
- continuare a mostrarla se non è completata o esclusa manualmente;
- non cancellare dati e non trasformarla automaticamente in completata.

### Errore di collegamento eSolver

Se la lettura fallisce:

- conservare l'ultimo snapshot valido;
- mostrare data e risultato dell'ultimo aggiornamento riuscito;
- non segnare tutte le righe come scomparse;
- registrare l'errore senza password o dati sensibili.

### Avviso di sincronizzazione eSolver ferma

L'app deve controllare quando è terminata con successo l'ultima lettura completa di `CertiRigheDDT`.

Comportamento concordato e implementato in locale:

- ultima lettura riuscita meno di quattro ore fa: mostrare data e ora senza avviso;
- almeno quattro ore dall'ultima lettura riuscita: avviso giallo tenue nel riquadro
  esistente, con istruzione di contattare il referente interno IT;
- ultimo tentativo fallito: mantenere il rosso già presente nello stesso riquadro;
- nessuna lettura riuscita da quando la sincronizzazione è attiva: messaggio esplicito;
- sincronizzazione disattivata: messaggio specifico, senza falso avviso di ritardo;
- dopo una nuova lettura riuscita: l'avviso scompare al successivo controllo
  periodico della pagina, senza modificare i dati già conservati.

L'avviso non deve:

- cancellare o modificare i DDT già memorizzati;
- trasformare righe attive in completate o scomparse;
- mostrare password, stringhe di connessione o dettagli tecnici sensibili;
- dichiarare che i dati sono aggiornati quando l'ultima lettura completa è fallita.

Scopo dell'avviso: rendere evidente un'interruzione prima che duri abbastanza da
creare una possibile lacuna rispetto alla finestra temporale eSolver. La sola
soglia temporale concordata è quattro ore. Eventuali ulteriori livelli di
gravità richiedono una decisione successiva.

## Regole di comparsa e scomparsa

### Una riga compare quando

- viene rilevata per la prima volta in `CertiRigheDDT`; oppure
- esiste nello storico locale ma è ancora incompleta; oppure
- il suo PDF definitivo è stato annullato o riaperto.

### Una riga lascia la vista attiva quando

- esiste un `quarta_taglio_final_certificates` della stessa unità;
- il certificato è realmente `pdf_final`;
- `storage_key_pdf` è presente e valido;
- il PDF non è stato annullato.

La riga deve restare consultabile nello storico `Completati`.

### Condizioni che non chiudono la segnalazione

- Word caricato o generato;
- draft creato;
- utente che apre la pagina;
- spunta di lettura dell'avviso;
- `CertificatoPresente = 1` senza un PDF finale CERTI verificabile;
- PDF di un altro DDT o di un altro OL.

### Esclusione manuale

Non aggiungere un generico `Nascondi`.

Se necessario, prevedere:

> **Non richiede certificazione**

con motivazione obbligatoria, utente, data e possibilità di ripristino. Questa azione deve essere limitata ai ruoli già autorizzati alla certificazione e tracciata nei log.

## UI proposta

### Sidebar

```text
Flusso certificazione
  DDT da certificare        [numero attivi]
  Carica Documenti
  Incoming materiale
  Certificazione
  Registro certificazione
```

Il badge conta le righe attive, non soltanto quelle appena visualizzate. Le righe rilevate di recente possono avere anche l'etichetta `Nuovo`, ma aprire la pagina non le elimina.

### Contatori pagina

- `Attivi`
- `Nuovi`
- `Pronti`
- `In attesa Incoming`
- `Da collegare`
- `Completati`

Vicino ai contatori mostrare sempre:

- data e ora dell'ultima sincronizzazione completa riuscita;
- eventuale avviso giallo o rosso di sincronizzazione ferma;
- pulsante di aggiornamento manuale, senza cancellare lo snapshot in caso di errore.

### Filtri

- stato operativo;
- DDT;
- OL;
- CodF3;
- cliente;
- intervallo data DDT;
- nuovi/non letti;
- solo elementi non più presenti nella finestra eSolver;
- storico completati/esclusi.

### Colonne minime

| Colonna | Origine/nota |
| --- | --- |
| Nuovo | calcolato da `first_seen_at` |
| Data DDT | estratta dal campo DDT, mantenendo anche il valore raw |
| DDT | eSolver |
| OL | eSolver; se vuoto mostra `Da collegare` |
| CodF3 | eSolver |
| Cliente | eSolver `RagSoc` |
| Quantità | eSolver `QtaUmMag` |
| Ordine cliente | eSolver `ODVCli` |
| Conferma F3 | eSolver `ODVF3` |
| Incoming | stato derivato dalle righe Quarta/Incoming |
| Certificazione | nessuna, Word, bozza, PDF finale, PDF annullato |
| Azione | apri Certificazione, apri Incoming, verifica collegamento |

Mostrare sempre anche `Ultimo aggiornamento eSolver` e un pulsante di aggiornamento manuale protetto contro richieste ripetute.

## Architettura proposta

### Nuova tabella persistente

Nome proposto:

```text
quarta_taglio_ddt_work_items
```

Campi da confermare durante l'audit pre-codice:

- `id`;
- `source_key`, univoca;
- `id_documento`;
- `id_riga_doc`;
- `rif_lotto_alfanum`;
- `cod_odp` nullable;
- `cod_f3`;
- `ddt_raw`;
- `ddt_date` nullable;
- `cliente`;
- `ordine_cliente`;
- `conferma_ordine`;
- `quantita`;
- `certificato_presente_esolver` solo informativo;
- `certification_unit_key`;
- `first_seen_at`;
- `last_seen_at`;
- `source_present`;
- `source_disappeared_at` nullable;
- `manual_disposition` nullable;
- `manual_reason` nullable;
- `manual_actor_id` nullable;
- `manual_at` nullable;
- `created_at` e `updated_at`.

Non salvare come verità definitiva lo stato Incoming o lo stato del PDF: devono essere ricalcolati dai dati correnti per non diventare obsoleti.

### Sincronizzazione

Creare una sincronizzazione dedicata che:

1. legge integralmente `CertiRigheDDT`, non per pagina e non per lista OL;
2. lavora in batch/upsert tramite chiave sorgente;
3. aggiorna `last_seen_at` e i campi modificabili;
4. non elimina righe assenti dal nuovo snapshot;
5. imposta `source_present = false` solamente dopo una lettura completa riuscita;
6. non altera lo snapshot in caso di errore di connessione o query parziale;
7. gira ogni 15 minuti insieme al ciclo Quarta, ma come operazione separata;
8. può essere richiamata manualmente dalla nuova pagina;
9. impedisce due esecuzioni contemporanee;
10. registra contatori sintetici nei log, senza credenziali;
11. conserva separatamente l'esito dell'ultimo tentativo e la data dell'ultima lettura completa riuscita;
12. alimenta l'avviso giallo/rosso quando la sincronizzazione resta ferma.

Lettura completa attuale: circa 392 righe. È sufficientemente piccola per un caricamento periodico, ma usare comunque query e transazioni controllate.

### Stato derivato di ogni riga

Ordine proposto:

1. `Completato` se il PDF finale esatto è valido;
2. `Escluso manualmente` se esiste una disposizione valida;
3. `Da collegare` se manca l'OL;
4. `Qualità respinta` se la riga Incoming collegata è respinta;
5. `In attesa Incoming` se Incoming non è completo;
6. `Word pronto - chiudere PDF` se esiste Word/draft associabile;
7. `Pronto da certificare` negli altri casi lavorabili;
8. `Verifica richiesta` in presenza di identità o associazioni ambigue.

Non duplicare le regole: riusare, estraendo dove opportuno, le funzioni già presenti in `backend/app/modules/quarta_taglio/service.py`.

### Endpoint proposti

Confermare nomi e convenzioni durante l'audit:

```text
GET  /quarta-taglio/ddt-work-items
GET  /quarta-taglio/ddt-work-items/counters
POST /quarta-taglio/ddt-work-items/sync
PATCH /quarta-taglio/ddt-work-items/{id}/disposition
```

Il listing deve supportare paginazione, filtri e ordinamento lato server. Il contatore sidebar non deve scaricare l'intera tabella.

### Frontend proposto

- nuova rotta: `/quarta-taglio/ddt-da-certificare`;
- nuova pagina nel modulo `frontend/src/pages/quartaTaglio/`;
- voce e badge in `frontend/src/components/layout/Sidebar.jsx`;
- API in `frontend/src/app/api.js` seguendo le convenzioni esistenti;
- stesso `AccessGuard` della pagina Certificazione;
- navigazione alla specifica unità, non soltanto all'OL, tramite query o stato già supportato dal dettaglio.

## Avvio iniziale e recupero storico

La prima esecuzione non deve limitarsi alla vista corrente, altrimenti si perderebbero le unità più vecchie già note ad Alpha.

Procedura proposta:

1. importare lo snapshot corrente completo di `CertiRigheDDT`;
2. importare da `quarta_taglio_esolver_links.rows` le unità storiche non più presenti nella vista;
3. deduplicare usando la chiave sorgente;
4. marcarle `Storico recuperato - da verificare`, non `Nuovo`;
5. confrontarle con tutti i certificati finali già esistenti;
6. lasciare attive solamente quelle non completate;
7. produrre prima un report dry-run con conteggi e conflitti;
8. richiedere conferma del proprietario prima di eseguire l'importazione reale su Alpha.

Non usare numeri dell'audit come condizione applicativa. I 182 elementi storici e i 90 OL servono solo per controllare il risultato del dry-run.

Il recupero della cache non garantisce lo storico completo: i DDT usciti dalla vista e mai memorizzati da CERTI richiedono un'estrazione storica aggiuntiva da eSolver. Anche dopo l'attivazione, DDT mai esposti dalla vista, rimossi prima della lettura o non letti per un'interruzione superiore alla finestra disponibile non sono recuperabili dal solo snapshot. L'avviso di sincronizzazione riduce il rischio, ma non costituisce una garanzia assoluta di assenza di lacune.

## File e logiche da riesaminare prima dell'implementazione

### Backend

- `backend/app/modules/quarta_taglio/models.py`
- `backend/app/modules/quarta_taglio/schemas.py`
- `backend/app/modules/quarta_taglio/router.py`
- `backend/app/modules/quarta_taglio/service.py`
- `backend/app/modules/quarta_taglio/scheduler.py`
- migrazioni/database bootstrap secondo la convenzione reale del repository
- `backend/tests/test_quarta_taglio_esolver.py`
- test specifici nuovi per la coda DDT

Funzioni esistenti da preservare o riusare:

- `_fetch_esolver_ddt_rows_batch()`;
- `_refresh_esolver_links_for_rows()`;
- `_build_certifiable_units()`;
- `_certifiable_unit_key()`;
- `_certification_progress_for_group()`;
- `_incoming_rows_ready_for_certification()`;
- `_incoming_rows_complete_for_word_queue()`;
- `_certificate_is_pdf_final()` e relative regole di annullamento.

### Frontend

- `frontend/src/components/layout/Sidebar.jsx`
- `frontend/src/app/router.jsx`
- `frontend/src/app/api.js`
- `frontend/src/app/access.js`
- `frontend/src/pages/quartaTaglio/QuartaTaglioPage.jsx`
- `frontend/src/pages/quartaTaglio/QuartaTaglioDetailPage.jsx`
- eventuali helper e test `.mjs` dedicati.

### Documentazione collegata

- `docs/development_rules.md`
- `docs/modules/esolver_sql_view_implementation_plan.md`
- `docs/modules/esolver_sql_view_export_plan.md`
- `docs/modules/quarta_taglio_final_certificate_flow_placeholder.md`
- `docs/modules/quarta_taglio_word_inheritance_rules.md`
- `docs/deploy/alpha_soft_update_server.md`

## Piano di sviluppo per fasi

### Fase 0 - audit aggiornato e approvazione

- verificare lo stato Git e preservare modifiche estranee;
- controllare modelli, migrazioni, API e test attuali;
- confermare la chiave e la semantica del PDF finale;
- presentare file, rischi e test;
- attendere `procedi`.

### Fase 1 - snapshot persistente backend

- modello e migrazione;
- lettura completa eSolver;
- upsert non distruttivo;
- gestione finestra scaduta ed errori;
- test unitari della chiave e della sincronizzazione;
- nessuna UI.

### Fase 2 - stato operativo e API

- correlazione con Quarta, Incoming, Word, draft e PDF;
- contatori e filtri;
- esclusione manuale tracciata;
- test delle casistiche e delle autorizzazioni.

### Fase 3 - UI

- pagina, contatori e filtri;
- voce sidebar e badge;
- navigazioni verso Incoming e Certificazione;
- controllo responsive e testi chiari.

### Fase 4 - recupero storico locale

- dry-run dell'importazione della cache;
- report conteggi, duplicati e ambiguità;
- importazione locale dopo conferma;
- test con righe oltre 60 giorni.

### Fase 5 - verifica complessiva

- test backend mirati e suite Quarta/eSolver;
- test frontend/helper;
- build frontend;
- controllo manuale con dati simulati;
- verifica che filtri, registro e generazione PDF esistenti non cambino.

### Fase 6 - commit/push e Alpha

Solo su richiesta esplicita e in passaggi separati:

1. mostrare diff e risultati dei test;
2. attendere conferma per commit/push;
3. attendere conferma separata per deploy;
4. seguire `docs/deploy/alpha_soft_update_server.md`;
5. eseguire prima il dry-run storico;
6. verificare applicazione e database senza interrompere il lavoro utente.

## Test obbligatori

### Sincronizzazione

- vista vuota per errore: nessuna cancellazione;
- errore connessione: snapshot invariato;
- stessa lettura ripetuta: nessun duplicato;
- modifica quantità/DDT/CodF3 con stessa chiave: stessa riga aggiornata;
- DDT non più restituito oltre finestra: riga conservata;
- OL inizialmente vuoto e poi valorizzato: una sola segnalazione riconciliata;
- due job contemporanei: nessuna doppia importazione.
- ultimo tentativo fallito ma snapshot precedente valido: dati invariati e avviso visibile;
- ripristino eSolver: recupero automatico delle righe ancora disponibili e rimozione dell'avviso;
- stato giallo/rosso calcolato dalla data dell'ultima lettura completa riuscita, non dalla semplice apertura della pagina.

### Identità

- stesso DDT, più OL;
- stesso OL, più DDT;
- stessa riga documento, più OL;
- stesso documento/riga/OL ma lotti differenti;
- DDT senza OL;
- correzione eSolver ambigua: nessuna unione automatica.

### Stato Incoming

- Incoming completo;
- Incoming incompleto;
- accettato con riserva;
- respinto;
- CDQ mancante;
- più righe Incoming collegate allo stesso OL.

### Certificazione

- nessun Word;
- Word preparato prima del DDT;
- draft con DDT;
- PDF finale esatto;
- PDF finale di un altro DDT dello stesso OL;
- PDF finale di un altro OL dello stesso DDT;
- PDF annullato o riaperto;
- nuovo DDT dopo PDF precedente;
- record finale legacy senza identità precisa: non chiudere automaticamente una riga ambigua.

### UI

- badge uguale ai contatori API;
- apertura pagina non chiude le righe;
- filtri combinati e paginazione;
- navigazione alla specifica unità;
- righe senza OL non aprono un OL inventato;
- storico completati ed esclusi;
- layout con dati lunghi e quantità grandi;
- messaggio e timestamp in caso di eSolver non aggiornato.

### Regressioni

- filtri attuali di Certificazione;
- `Nascondi completati`;
- `Solo certificati da fare`;
- `Altri Word da preparare`;
- selezione standard;
- generazione Word;
- chiusura e riapertura PDF;
- Registro certificazione;
- flusso Incoming e valutazione qualità.

## Criteri di accettazione

La funzione è accettabile quando:

1. ogni nuova unità eSolver con OL compare entro il ciclo di sincronizzazione previsto;
2. una riga non scompare attraversando il limite temporale eSolver;
3. stessa DDT con OL differenti produce lavori indipendenti;
4. stesso OL con DDT differenti produce lavori indipendenti;
5. il PDF finale chiude esclusivamente la propria unità;
6. annullare il PDF fa ricomparire la segnalazione;
7. draft e Word non chiudono la segnalazione;
8. le righe senza OL sono visibili e non collegate automaticamente;
9. errori eSolver non cancellano né completano elementi;
10. nessuna logica esistente di Incoming, standard, Word, PDF o registro cambia senza richiesta esplicita.

## Decisioni ancora da confermare con il proprietario

Prima dell'implementazione finale chiedere conferma solamente sui punti che incidono sul comportamento:

1. importare in Alpha anche tutto lo storico recuperabile oltre la finestra eSolver oppure partire solo dai DDT correnti;
2. consentire `Non richiede certificazione` e a quali ruoli;
3. mostrare nel badge tutte le righe attive oppure solamente quelle pronte;
4. periodo visivo dell'etichetta `Nuovo`;
5. conferma da Matteo/eSolver del limite SQL esatto della vista, informazione utile ma non bloccante.

La soglia dell'avviso è stata decisa successivamente: giallo tenue dopo quattro
ore senza lettura riuscita; l'errore effettivo conserva il rosso già esistente.

## Nota finale

Il punto architetturale non negoziabile è lo snapshot persistente e indipendente dalla paginazione. Limitarsi ad aggiungere una nuova pagina sopra `quarta_taglio_esolver_links` manterrebbe il rischio attuale: righe non ancora visitate non memorizzate e DDT incompleti che possono sparire quando escono dalla finestra eSolver.

## Esito test locali della fase 1

Verifica finale: **76 test superati** e **2 test PostgreSQL saltati nella suite offline**, già eseguiti separatamente e superati su PostgreSQL 16 locale temporaneo. Totale: 78 casi distinti verificati. Rimangono solo avvisi di deprecazione delle dipendenze SWIG già utilizzate dal progetto.

Comando offline dalla radice del repository (usare l'interprete locale con le dipendenze backend installate):

```powershell
$env:PYTHONPATH = 'backend'
python -m pytest backend/tests/test_quarta_taglio_ddt_snapshot.py backend/tests/test_quarta_taglio_esolver.py backend/tests/test_quarta_taglio_word_filters.py backend/tests/test_quarta_taglio_register_quantity.py backend/tests/test_quarta_taglio_quality_reservation.py backend/tests/test_esolver_export.py -q
```

I due test di integrazione si abilitano con `DDT_TEST_POSTGRES_URL`. Accettano esclusivamente host `localhost`/`127.0.0.1` e un database dedicato il cui nome inizia con `certi_ddt_test`; creano e rimuovono soltanto uno schema temporaneo proprio. Non usare il database applicativo. Il contenitore usa-e-getta utilizzato per il collaudo è stato arrestato e rimosso, senza volumi dell'app.

`git diff --check` superato. Nessun frontend modificato: build/UI da verificare nelle fasi successive.

### Attivazione ancora da fare

`DDT_SNAPSHOT_ENABLED` è disattivo per impostazione predefinita. Non è stato aggiunto alle configurazioni di deploy né impostato nei file `.env`. Prima dell'attivazione reale completare le fasi successive e predisporre esplicitamente il passaggio della variabile nel Compose dell'ambiente scelto; non basta aggiungerla al `.env` radice se Compose non la inoltra al backend.

La conservazione persistente riguarda i nuovi work item. Le pagine esistenti continuano a usare la cache precedente: il collegamento operativo allo storico, specialmente per certificare un DDT ormai uscito dalla vista eSolver, è ancora da implementare e testare. Salvare il DDT è il primo passo, non rende già disponibile il flusso completo.
