# Beta 1 — audit cumulativo per il prossimo deploy

11/11/2026. Solo preparazione e letture: nessun deploy, fermo, bootstrap,
backup, pulizia, chiamata AI o scrittura sui dati Alpha/eSolver.
La modifica locale della versione è autorizzata; il deploy resta da autorizzare.

## Esito, correzione locale e attese esterne

L'audit ha rilevato un timeout della nuova SELECT del filtro Con/Senza
requisiti cliente. Dopo approvazione è stata corretta **in locale**: un solo
riferimento alla vista e aggregazione per OL, senza la rilettura correlata.
Il criterio non è obbligare eSolver a rispondere entro 30 secondi: i tempi
esterni validi vanno accettati, mentre il lavoro superfluo di CERTI va corretto.
Configurazioni/server restano invariati; commit/push e deploy ancora separati.

- Connessione SQL di controllo: riuscita, circa 0,000 s.
- SELECT CertiOL esistente per OL2026001387: una riga, **0,151 s**.
- Nuova SELECT parametrizzata per le **181 famiglie attive**: timeout a
  **30,042 s**, con il limite reale configurato di 30 s. Anche il primo
  tentativo prudenziale a 20 s non è terminato entro il limite.
- La query precedente rileggeva la vista in un `EXISTS` correlato per ottenere il
  contesto completo degli OL pertinenti. La misura conferma che questa forma
  non regge il carico reale entro il vecchio limite; non dimostra un guasto della connessione.
  Non è stato acquisito un piano SQL Server per attribuire il costo a un
  singolo operatore o proporre modifiche di indici/vista al buio.
- Riguarda le due scelte filtrate in Certificazione. **Tutte** conserva il
  percorso precedente; non vengono modificati o persi documenti. Il codice
  gestisce l'errore senza trasformarlo in falsa assenza di requisiti.
- I test precedenti del provider erano simulati: superavano la semantica,
  non misuravano questi tempi. Non aumentare semplicemente il timeout e non
  limitare il filtro alle sole righe già paginate.

### Riscontro successivo e correzione autorizzata 11/11

- Una normale proiezione completa della stessa vista impiega **24,391 s**:
  il confronto iniziale con un solo OL da 0,151 s non bastava ad attribuire
  tutta l'attesa a CERTI. Parte importante del tempo è nella lettura esterna.
- Query corretta: **26,749 s**, 181 famiglie, 10.063 righe esaminate nel
  controllo indipendente, **569 OL / 815 righe** restituite. Appartenenza,
  intero contesto e molteplicità delle righe coincidono esattamente con
  un riferimento calcolato dalla proiezione completa. Non è una garanzia di
  risposta entro 30 s al crescere del carico esterno.
- La forma finale usa `MAX(CASE ...) OVER (PARTITION BY OL)`: non taglia
  gli F3 non direttamente associati ai requisiti di un OL pertinente, non
  cambia candidati/ambiguità e non filtra solo la pagina. Parametri, blocchi
  famiglie, errori/Riprova e percorso Tutte restano invariati.
- Anche una fixture T-SQL `VALUES`/SELECT ha verificato famiglia raw/finito,
  zeri iniziali, valori nulli, duplicati e contesto completo. Nessuna tabella
  temporanea, DDL o modifica ai dati. Hash della query esatta portata nell'app:
  `df928887ad8b54f7fbcac9b66d30fec3da766c5673edcf7fc60604dd115ad6d1`.
- Variante a due passaggi scartata, non applicata: ID + contesto a blocchi
  impiegava 65,060 s; blocchi da 500 OL avevano un piano ancora più lento.
  Non sostituire la query finale con questa variante nei pacchetti.
- Suite mirata iniziale dopo il fix: 78 superati, una prova PostgreSQL della
  migrazione nome PDF saltata (già eseguita nel collaudo cumulativo precedente).
  Sei nuovi casi verificano che l'attesa configurata 30/120/600 s sia rispettata
  sia con filtro sia senza. Non esiste un nuovo tetto di 30 s nel motore.
  Regressione generale finale: **1.053 superati, 212 opt-in saltati, zero
  fallimenti**, 208,31 s. Non erano attivati in questa ripetizione i database
  PostgreSQL/render opzionali: il precedente cumulativo su PostgreSQL e i sei
  render reali restano documentati sotto, non vanno conteggiati due volte.
  Modifica applicativa limitata al testo della SELECT; nessun cambio DDL,
  driver, configurazione o logica di classificazione.

### Decisione sulle lentezze esterne, distinta dalla correzione query

Confermato dall'utente: una lettura valida ma lenta di eSolver/Quarta deve
poter terminare; non considerarla un errore CERTI solo perché dura oltre 30 s.
Un collegamento indisponibile deve invece continuare a dare un esito chiaro,
senza inventare dati assenti o lasciare l'utente bloccato indefinitamente.

La cronologia conferma che il valore predefinito di 30 s risale alla gestione
integrazioni del 10/05, non al nuovo filtro o alla numerazione Beta. Entrambi
i collegamenti Alpha hanno attualmente **connessione 10 s / lettura 30 s**.
L'API di configurazione permette una lettura fino a 600 s e il codice ne
rispetta il valore; la UI mostra attualmente soltanto il timeout connessione.
Non confondere i due parametri o modificarli implicitamente durante un deploy.

**Decisione utente 11/11: nessuna scadenza delle letture eSolver/Quarta per il
solo trascorrere del tempo. Proposta 120 s rifiutata, non più da approvare.**
La regola richiesta è attendere il risultato esterno, non mascherare errori
reali di rete/SQL né introdurre un nuovo limite più alto. Piano successivamente
autorizzato e implementato **in locale**; Alpha resta invariata. Non è la sola
sostituzione 30 -> 0.

### Audit alla base della modifica autorizzata: attesa senza scadenza

Audit concreto, oltre al testo della SELECT già corretto:

La lista seguente descrive i vincoli rilevati **prima** dell'implementazione;
la gestione locale attuale è riepilogata subito dopo e nel documento dedicato.

- Driver: `pymssql` supporta `timeout=0` come assenza di scadenza della query;
  segnala però che le impostazioni timeout possono avere effetto sull'intero
  processo, non soltanto sulla singola connessione. Verificare quindi tutte le
  letture eSolver/Quarta, incluse anagrafiche, fornitori, DDT e timer, non solo
  il filtro. [Documentazione ufficiale driver](https://pymssql.readthedocs.io/en/v2.3.11/ref/pymssql.html).
- Configurazione: lo schema API oggi richiede `query_timeout >= 1`; modello e
  seed nuovi collegamenti partono da 30. La UI usa `item.query_timeout || 30`,
  che trasformerebbe nuovamente uno zero in 30 al salvataggio. Consentire e
  conservare esplicitamente il valore senza scadenza, senza cambiare credenziali
  o gli altri parametri. Non confondere con l'apertura della connessione.
- Scheduler: `quarta_taglio_periodic_sync_loop` chiama ancora direttamente
  `sync_and_list_quarta_taglio` nel ciclo asincrono. Una lettura senza scadenza
  non può rimanere in quel punto: isolare l'attesa dal ciclo principale, con
  sessione DB propria e senza riutilizzare sessioni fra thread.
- Richieste interattive: i percorsi Certificazione attendono attualmente la
  lettura prima di restituire la risposta. Il client generale non introduce
  un proprio timeout, ma il proxy pubblico ha 300 s documentati nel runbook,
  da riconfermare prima del deploy. Togliere il limite SQL non toglie quello
  HTTP; non impostare `proxy_read_timeout 0` alla cieca e non modificare Nginx IT.

Piano successivamente approvato e implementato in locale: eseguire le letture lente come lavoro
in background, con stato consultabile tramite richieste brevi. L'utente può
continuare a usare CERTI; la lettura non viene interrotta per età. Un nuovo clic
si aggancia al lavoro già avviato, senza duplicare interrogazioni o applicazioni
dei risultati. Non pubblicare dati incompleti come nuovi risultati definitivi;
conservare l'ultimo aggiornamento valido e le protezioni su DDT/Word/PDF.
L'avviso esistente di aggiornamento fermo resta informativo, non interrompe
automaticamente la lettura. Errori reali di collegamento/SQL vengono distinti
dall'attesa; prevedere recupero controllato di un lavoro fermo senza fermare l'app.

Esito locale e limiti delle prove in [Attesa esterna](../tasks/external_read_wait_20261111.md).
Persistenza: **due nuove tabelle additive** per lavori e ricevute; proprietà
del lavoro protetta da lock PostgreSQL sulla stessa connessione delle scritture,
con blocco del proseguimento se SQLAlchemy tenta di riconnetterla senza lock.
Richieste ripetute si agganciano al lavoro, senza replay dopo un'interruzione
reale. Per i lavori interrotti serve controllo dello stato prima del nuovo clic.
Il timer si limita ad accodare; l'aggiornamento Quarta completo è serializzato
e condiviso, non applicato due volte contemporaneamente.

Le prove oltre 30/120/300 s usano un orologio simulato e il vero client; una
prova TCP separata usa un proxy locale con scadenza HTTP di 0,5 s e un lavoro
più lungo. Non sono attese forzate sui sistemi aziendali. Il browser reale
verifica Vite/StrictMode e production con tutte le API simulate. Nessuna
chiamata AI o modifica ad Alpha. Timeout AI/PDF/lock non rimossi.

Commit/push e deploy restano da autorizzare. Il runbook include ora schema,
spool privato persistente, attività in corso, backup, rollback e ricarica del
frontend; nessun aggiornamento Nginx o dato/configurazione Alpha applicato.

## Stato Alpha verificato circa alle 09:25 italiane

- Sorgente installata `7485ff6e2480cfb21a0d7cdf5e1388a79d51eac1`, pacchetto
  Alpha 10.9; versione backend/footer ancora `0.1.0.alpha.10`.
- **268 file** applicativi/configurazioni confrontati col commit installato:
  nessuna differenza. Backend/frontend attivi, PostgreSQL healthy.
- In quel momento: nessun run AI, caricamento o conversione Word/PDF attivi;
  nessuna richiesta utente rilevata nei tre minuti precedenti. Sono dati
  dell'audit mattutino: ricontrollare immediatamente prima del fermo serale.
- `DDT_SNAPSHOT_ENABLED=true` e `DDT_WORD_REUSE_ENABLED=true`: conservarli.
- Nessuna dipendenza, Dockerfile, lockfile o configurazione runtime cambiata
  dal commit installato. Non autorizza pull/apt/pip/npm update impliciti.
- Conteggi indicativi: 183 requisiti, 248 righe Incoming, 438 documenti,
  412 certificati (141 PDF finali), 145 versioni PDF, 1.057 quote DDT,
  243 letture AI salvate e 45 registrazioni consumo. Non imporre questi numeri
  stasera: gli utenti e i job possono legittimamente lavorare nel frattempo.

## Perimetro da altezza righe certificato in poi

| Intervento | Preparazione DB | Cautele per il deploy |
| --- | --- | --- |
| Altezza DDT/Quantity e pagina vuota fra allegati | Nessuna nuova migrazione | Tutti i moduli Word/riuso insieme. Adeguamento tracciato al normale uso dei Word aperti; nessuna riscrittura dei chiusi. Provare fonte vecchia, nuovo DDT, seconda pagina e allegati. |
| Filtro requisiti in Certificazione | Nessuna propria | Distribuire la query corretta, con contesto OL completo e conteggi prima della paginazione. Attesa senza scadenza tramite la nuova gestione in background. |
| Attesa esterna e background | **Due tabelle additive** | Lavori/ricevute, payload cifrati, spool privato persistente. Nessun backfill documenti; preservare APP_SECRET_KEY, controllare lavori attivi prima del fermo e non riavviare per età. |
| Etichette e filtri DDT da certificare | Nessuna | Backend/frontend/helper insieme; non cambiare stati interni, storico, sidebar o regole PDF. |
| Numeri nuovi con F3 a sette cifre | Nessuna | Distribuire anche `certificate_numbering.py` e tutti i consumatori. Vecchi numeri/file intatti; altre lavorazioni e progressivi non azzerati. |
| Nome PDF particolare nei requisiti | **Una colonna additiva** | `customer_requirements.requires_custom_pdf_name BOOLEAN NOT NULL DEFAULT FALSE`, prima del nuovo frontend; preservare vecchie spunte/note e nomi già scelti. |
| Certificato Leichtmetall comune a più lotti | Nessuna nuova tabella/colonna | Includere `leichtmetall_groups.py`, parser, bridge e Quarta; conservare evidenze e sganci. Nessuna divisione automatica dei cinque casi storici protetti. |
| Versione sistema Beta 1 | Nessuna | Backend/footer/bundle `0.1.0.beta.1`. Non rinominare infrastruttura Alpha né effettuare un taglio DDT implicito. |

La colonna del nome PDF è **assente su Alpha** al controllo: va aggiunta
durante il deploy, dopo backup e con writer fermi. Gli altri campi preesistenti
dei requisiti sono presenti; nessuna delle note attuali attiverebbe la vecchia
regola bootstrap sulla conducibilità cambiando una spunta. Rilevare nuovamente
la situazione prima/dopo, senza reseed o copia delle schede locali.
Digest indicativo dei requisiti senza la nuova colonna:
`5408acc2e110903300330e473d9ac793` (non baseline serale da imporre).

## Spazio e build

Valori decimali GB, 11/11 mattina; disponibilità per l'utente SSH, distinta
dalla riserva ext4. Non sommare immagini/layer Docker a `df`.

| Filesystem | Totale | Occupato | Disponibile | Riservato non disponibile |
| --- | ---: | ---: | ---: | ---: |
| Root: app e Docker | 24,63 | 15,97 | **7,38** | 1,28 |
| Dati e backup, stesso disco | 105,09 | 21,56 | **78,14** | 5,39 |

Backup esistenti circa 18,08 GB; storage corrente 2,38 GB; PostgreSQL fisico
0,35 GB, DB logico 0,12 GB. I mount dati/backup sono sul disco aggiunto, mentre
app, immagini e build Docker restano sulla root.

Budget prudenziale da ricontrollare prima del via: **4 GB dati** per i nuovi
backup/temporanei e **2 GB root** per build/candidate. Con i valori attuali
resterebbero circa 74,14 GB dati e 5,38 GB root: **nessuna pulizia proposta**.
Non è la misura finale degli archivi compressi o delle immagini ancora da
costruire. Se cambiano stime o spazio, fermarsi; nessuna cancellazione implicita.

Backend: preferire il runtime operativo immutabile verificato secondo il
runbook, senza aggiornare apt/pip. Frontend cambiato: costruire davvero il
nuovo bundle dal pacchetto finale, con lockfile verificato e toolchain fissata;
non riusare il vecchio frontend solo perché il contenitore è sano. Verificare
anche il digest Nginx, senza introdurre un nuovo runtime da un tag mutabile.

## Collaudo e passaggi ancora necessari

### Riscontro in sola lettura prima del commit/push 11/11

Alpha raggiungibile via SSH. Nessun deploy, fermo o scrittura sul server:
spazio disponibile effettivo **7,378 GB root / 78,105 GB dati**, compatibile
con i budget prudenziali sopra. Non è proposta alcuna pulizia.
Con il ruolo applicativo `certi_nt`, PostgreSQL riporta `statement_timeout=0`,
`idle_in_transaction_session_timeout=0`, `idle_session_timeout=0` e isolamento
`read committed`: non emerge un limite PostgreSQL incompatibile con l'attesa.
Le due tabelle background e la colonna Nome PDF particolare sono ancora
assenti, come previsto: vanno aggiunte dal pacchetto cumulativo sul contesto
Alpha, non copiate da locale. Nessuna modifica a queste impostazioni.

Questo riscontro non sostituisce quello immediatamente precedente al deploy:
ricontrollare spazio, attività utenti/job, backup e restore, poi provare la
candidata sul clone aggiornato e verificare il percorso pubblico dopo il rilascio.
Il pacchetto locale è collaudato; non è una conferma di installazione serale.

### Prove completate

- Chiusura locale dell'attesa senza scadenza: **1.105 test backend superati,
  214 opt-in/non applicabili saltati, zero fallimenti**, PostgreSQL dedicato
  alla nuova gestione attivato. 66 test frontend, build finale e browser reale
  Vite/production superati. Ripetuti e superati i sei rendering LibreOffice e
  il collaudo visivo precedente del filtro requisiti (1920/1440, pagina successiva,
  errori/Riprova e risposta obsoleta). Le prove cumulative storiche sotto
  rimangono distinte: non sommare conteggi sovrapposti.
  I dettagli e i limiti del collaudo sono nel documento Attesa esterna.

- API locale e footer allineati a Beta 1; build production riuscita e bundle
  controllato. 28 test frontend dei requisiti/filtri/etichette superati.
- Sei conversioni reali degli allegati ripetute: tutte superate. Ripetuta
  anche la chiusura tramite il vero servizio PDF con header vecchio, Word
  manuale e allegati: quattro pagine, integrità valida, nomi Word/PDF corretti,
  originale e successivo download del PDF chiuso invariati. Ispezionate le
  quattro PNG finali: nessuna pagina bianca aggiunta o sovrapposizione.
- Suite cumulativa finale SQLite/PostgreSQL locale: **289 superati, 6 saltati,
  zero fallimenti**, 337,97 secondi. I sei saltati sono gli stessi rendering
  LibreOffice eseguiti separatamente sopra, tutti superati. Include migrazione
  ripetibile del nome PDF, altezze/legacy, numeri nuovi/storici, riuso,
  ereditarietà, concorrenza PDF e recupero offline. Gli avvisi sono deprecazioni
  già presenti; nessun aggiornamento delle dipendenze eseguito.
- La suite generale precedente sul codice Leichtmetall fermo resta una prova
  distinta: 1.112 superati, 147 opt-in esclusi, nessun fallimento. Non sommare
  conteggi sovrapposti e non confonderla col controllo SQL reale fallito sopra.
- Rimossi a prove concluse soltanto il PostgreSQL sintetico temporaneo di
  questo audit (ID verificato `97f0c116ebbd`, dati in tmpfs e nessun volume
  dell'app) e i container render usa-e-getta terminati. Il DB QA è ricreabile;
  risultati/XML, PDF/PNG di fixture e verbale sono conservati. Nessuna pulizia
  di backup, immagini o servizi dell'utente e nessun intervento server.

Prima del deploy: concludere il collaudo e il piano approvato di attesa senza scadenza,
commit/push separato delle modifiche
locali finali, rigenerare **interamente** il pacchetto da quel commit e confrontare
gli alberi. Nuovo tag libero `v0.1.0-beta.1-deploy`; nessuna creazione/force/tag
già effettuati. Le vecchie directory/archivi temporanei del repo deploy non
sono sorgenti da copiare e non sono stati eliminati durante questo audit.

Al via esplicito serale: nuovo controllo spazio/attività, manutenzione solo
servizi applicativi, backup app/configurazione/DB/storage con un solo timestamp,
restore isolato, collaudo della candidata effettiva, delle due tabelle e della colonna sui dati
Alpha del nuovo backup. Proteggere hash di PDF chiusi e sorgenti Word, numeri,
firme, export eSolver e valori requisiti. Nessun vecchio recupero Word/DDT/AI,
archiviazione o reset cache da ripetere. Riapertura separata dopo i controlli;
rollback secondo le cautele per numerazione e nuovi gruppi Leichtmetall.

Artefatti privati locali: `tmp_eval/beta1_readonly_preflight_20261111.json`,
`beta1_requirements_query_20261111_configured.json`,
`beta1_certiol_control_20261111.json` e `tmp_eval/beta_preflight_20261111/`.
Correzione SQL: `tmp_eval/requirements_window_candidate_20261111.json`,
`requirements_two_stage_candidate_20261111_batch25.json` (variante scartata)
e `tmp_eval/requirements_query_20261111/{target,full}.xml`.
Nessuna credenziale nei verbali, nessun dato QA da copiare sul server.
