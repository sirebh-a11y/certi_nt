# Cambio standard, Word e conformità — audit 09/10/2026

## Stato del lavoro

Audit esteso autorizzato e implementazione locale del piano richiesta dall'utente.
Alpha: **sole query SELECT in transazione READ ONLY**, nessuna modifica/deploy.
Commit e push non richiesti. **Correzione completata in locale il 09/10**:
tracciabilità, avvisi, blocchi PDF/riuso, rigenerazione e preparazione database.
Alpha NON aggiornato. Lo storico non viene rigenerato: scelta dell'utente
successiva all'audit; il singolo OL1232 resta da correggere esplicitamente.

Parte indipendente già corretta in locale:

1. `Rigenera da zero` propone la conferma esplicita per chimica/proprietà fuori
   norma e conserva l'intento di rigenerazione, il certificato e la quota DDT.
   Per Word manuali resta prima la conferma della perdita delle modifiche.
   Annullare non invia la richiesta; non identificare il certificato non può
   trasformare la richiesta in una creazione di un nuovo Word Raw.
2. Il registro non ricalcola più la conformità dei **PDF chiusi** usando lo
   standard OL attuale. Conserva i valori già registrati, senza affermare che
   quelli storici siano sempre corretti o riscriverli arbitrariamente.

Le sezioni di audit e piano sotto documentano anche lo stato intermedio.
Il loro elenco di attività mancanti è superato dal completamento descritto qui.

### Completamento locale dopo approvazione

- JSON `word_standard_snapshot`: standard/limiti usati dai nuovi Word;
  copiato dalla sorgente in propagazione/ereditarietà/riuso DDT. Cambi di
  selezione e modifiche dei limiti sullo stesso standard sono rilevati.
- Per lo storico, baseline idempotente con origine `legacy_baseline`, distinta
  da `generated`: avvia il monitoraggio futuro senza inventare lo standard
  originale. Non tocca file, date di modifica, numeri, PDF o conformità.
- `Word da aggiornare` nel dettaglio, Registro e DDT da certificare; nessuna
  azione PDF per Word superato, controllo anche server. Il registro distingue
  l'esito dello standard attuale dal Word non aggiornato.
- Download del Word precedente resta disponibile e non rigenera le tabelle;
  restano i controlli d'identità della quota. Ricarica manuale e allegati non
  possono validare implicitamente lo standard nuovo: prima rigenerazione
  esplicita (scaricare il manuale prima di perdere le modifiche).
- Rigenerazione con conferma dei fuori norma, stesso ID/numero e nuova chiave
  file; originali preservati. Snapshot aggiornato solo a generazione riuscita.
- PDF chiusi immutati, anche se cambia lo standard; dopo riapertura si applica
  il controllo. Una fonte chiusa superata non alimenta nuovi Word DDT.
- Concorrenza: fotografia prima del calcolo e verifica prima della pubblicazione,
  lock OL condiviso con selezione e lock standard condiviso con modifica limiti.
  Standard cambiato durante Word/PDF genera 409, senza pubblicare il risultato.
- Preparazione offline `python -m scripts.prepare_word_standard`: nuova colonna
  e baseline atomiche, flag manutenzione/backup, nessun bootstrap/job né file.
  Aggiornato il markdown deploy: preparare PRIMA delle preview Word/archivio,
  ricontrollare OL1232, non attivare il suo riuso finché irrisolto.

La decisione di NON intervenire sui materiali aggiunti agli OL0986/1012 è
rispettata: questo controllo riguarda lo standard, non nuove invalidazioni
per cambi Incoming/materiali. Nessun intervento sui loro dati Alpha.

### Collaudo finale locale

- Suite `python -m pytest -q tests` in container con PostgreSQL temporaneo
  dedicato `certi_ddt_test_word_standard`: **635 superati, nessun salto**.
- 3 prove PostgreSQL dedicate: vecchio schema/ALTER idempotente/baseline senza
  cambi timestamp; lock standard contro editor limiti; lock OL contro selezione.
- Ultima riesecuzione mirata dopo gli aggiustamenti finali: **85 test superati**
  (rigenerazione, riuso DDT e prove PostgreSQL), nessun salto.
- Prove mirate: A→B→A, stesso ID con limiti cambiati, nota amministrativa
  ininfluente, snapshot conservato nei riusi, download vecchio Word, blocchi
  PDF/manuale/allegati, rigenerazione fallita o cambio standard durante build,
  PDF chiuso/riaperto e provenienza legacy esplicita.
- **28 test frontend** superati; build riuscita (avvisi preesistenti bundle e
  Browserslist). Browser Playwright con API simulate: conferme/cancellazione,
  rigenerazione conforme e non conforme/manuale, errore senza perdita file,
  avviso Word superato e upload disabilitato, PDF chiuso non modificabile.
- Computer Use inizializzato secondo skill ma kernel fallito prima dell'avvio
  (`helper_unknown_error`): fallback Playwright documentato, Vite temporaneo
  5174. Nessuna azione browser su dati reali, nessun test su Alpha.
- Verificato anche il Registro con `Word da aggiornare` e senza azione PDF.
  Sul database locale risultano 35 baseline legacy, senza rigenerare i file.
  Frontend abituale 5173 riavviato solo dopo consenso esplicito dell'utente:
  verificato via HTTP che serve il codice aggiornato.

### Secondo ricontrollo richiesto dall'utente — 09/10

Solo test e documentazione, nessuna ulteriore modifica alla logica applicativa
e nessuna operazione Alpha. Aggiunte prove permanenti per:

- selezione standard rimossa e poi ripristinata: blocco e riallineamento corretti;
- modifica di minimo/massimo/intervallo meccanico sullo stesso standard;
- più quote/F3 dello stesso OL, Word aperti e PDF chiusi insieme, altro OL isolato;
- legacy senza standard e successiva selezione, senza sovrascrivere la baseline;
- riordino delle righe limiti e note/codice amministrativo senza falsi allarmi;
- errore nella preparazione PostgreSQL: rollback di colonna e baseline insieme;
- generazione DOCX reale: con Si 0,8 e Rm 350, passaggio da limiti 1,2/300 a
  0,7/400; rigenerazione respinta senza consenso e riuscita dopo consenso.
  Verificati i limiti nelle tabelle OOXML, la conformità non conforme e il file
  precedente immutato. Non è un nuovo collaudo grafico del layout;
- standard cambiato durante conversione PDF: 409, certificato ancora aperto,
  nessuna versione PDF pubblicata, tracciabilità Word precedente conservata.

Corretto anche il test della nota amministrativa perché utilizzi il campo
persistito `notes`, non un attributo Python estraneo al modello.
Markdown deploy ricontrollato: reso esplicito l'ordine cumulativo standard →
archivio → recupero Word; chiarito che OL1232 non ha quarantena automatica e
che un report che lo riusa non va modificato a mano o applicato parzialmente.
La raccolta DDT e il riuso Word sono due automatismi distinti.

Esito: suite generale **644 passati, nessun salto** con PostgreSQL isolato
(332,10 secondi); le due prove DOCX reale/conversione aggiunte dopo l'avvio della
suite sono state eseguite separatamente, **2 passate**. Frontend: **28 passati**,
build riuscita; restano soltanto gli avvisi preesistenti delle dipendenze e
dimensione bundle. `git diff --check` superato. Nessuna nuova regressione emersa.

## Difetto certo e regole da preservare

- Prima generazione: il frontend mostra i fuori norma e l'utente può scegliere
  `Crea comunque Word numerato`. Il backend richiede `force_non_conforming`.
- Rigenerazione precedente: inviava `force_regenerate=true` ma sempre
  `force_non_conforming=false`, anche dopo la conferma di perdita del manuale.
  Il backend rispondeva 409 e conservava il Word precedente.
- Cambiare standard cambia la selezione **per OL**, non il documento già salvato.
  La conformità del registro aperto è ricalcolata sullo standard attuale.
- Conformità rispetto allo standard e allineamento del documento sono concetti
  distinti. La generazione forzata non rende conforme il materiale.
- Il PDF finale è attualmente bloccato se non conforme: regola NON modificata.
- Nessun cambiamento a chimica/accettazione Incoming, match, soglia archivio,
  scadenze o regole di numerazione è richiesto da questo intervento.

## Ricadute trovate nel codice

| Percorso | Rischio / trattamento necessario nella fase restante |
| --- | --- |
| Conferma standard OL | Influenza tutte le lavorazioni/quote dell'OL; non limitare il controllo alla riga aperta |
| Registro certificazione | Separare conformità corrente e Word non aggiornato; PDF chiusi non rivalutati retroattivamente |
| Download Word | Aggiornamenti dei controlli di contenuto non riscrivono le tabelle chimica/meccanica; il download non prova una rigenerazione |
| Word con allegati | Alcuni percorsi ricostruiscono il documento con lo standard corrente; non usarli per aggirare una conferma necessaria |
| Ricarica manuale | Non dedurre automaticamente dal caricamento che standard e limiti siano stati corretti dall'utente |
| Riuso `ddt_word_reuse` | Confronta materiale, file, campi spedizione e conformità, ma non lo standard originario non registrato |
| Ereditarietà/propagazione Word | Copiare la tracciabilità della sorgente, non attribuire lo standard attuale a contenuto precedente |
| DDT da certificare e azione PDF | Stesso controllo del backend, non soltanto disabilitare un pulsante nel registro |
| PDF chiusura/riapertura | Non toccare PDF/versioni chiuse; dopo riapertura applicare i controlli prima di una nuova chiusura |
| Più utenti / errore generazione | Verificare che lo standard non cambi durante la generazione; aggiornare tracciabilità solo con file riuscito, senza sostituire il precedente in caso di errore |
| Recupero Word offline Alpha | Nuova preview dopo il codice completo; nessun riuso di report prodotti con algoritmo precedente |

La selezione e i dati attuali non permettono di provare automaticamente lo
standard usato da un Word storico. `updated_at`, `conformity_status` e il nome
del file non sono prove: possono cambiare senza rigenerare il corpo del Word.
Le tabelle del DOCX contengono limiti statici, non un identificativo completo
e immutabile della selezione standard. Anche due standard differenti possono
avere gli stessi limiti visibili: non ricostruire associazioni per somiglianza.

## Audit dati reale (fotografia 09/10, da ricalcolare)

| Ambiente | Word aperti | Ripartizione | PDF chiusi con Word |
| --- | ---: | --- | ---: |
| Locale | 25 | 17 generati, 4 ereditati, 2 riusati per DDT, 2 manuali | 10 |
| Alpha | 150 | 143 generati, 7 ereditati | 19 |

Questi sono documenti **non tracciati**, non documenti dimostrati errati.
Applicare il blocco prudenziale a tutti avrebbe un impatto operativo ampio.
L'utente ha chiesto il controllo preliminare dei documenti, svolto nella sezione
seguente. **La politica di gestione dei Word legacy resta da approvare:**
il controllo non autorizza migrazioni o rigenerazioni automatiche.

## Controllo dei Word esistenti — 09/10/2026, ore 12:52 CEST

Lettura diretta dei DOCX salvati, senza endpoint applicativi (alcuni aggiornano
lo stato anche in lettura). Database locale e Alpha in transazione
`REPEATABLE READ, READ ONLY`, rollback finale; `transaction_read_only=on`,
sessione senza oggetti modificati. Hash SHA-256 dei file invariati a fine
scansione. Nessuna modifica al codice applicativo in questa fase, né ai dati
o documenti Alpha. Script ed evidenze JSON private in `tmp_eval/`.

Confrontati lega e intestazione norma/trattamento, colonne e minimi/massimi
chimici, minimi meccanici, valori misurati con il contenuto che le funzioni
attualmente installate produrrebbero dai dati Incoming e dallo standard
confermato. Spazi e interruzioni di riga nelle intestazioni normalizzati;
vecchie diciture separate dalle differenze numeriche. Nessuna deduzione
dello standard storico dalla sola conformità registrata.

| Ambiente / documenti | Esito |
| --- | --- |
| Alpha, 150 Word aperti | 147 coincidono nel contenuto tecnico visibile confrontato; 1 disallineato; 2 con contesto Incoming incompleto |
| Alpha, 19 Word di PDF chiusi | 17 coincidono; 1 differisce solo per la variante Sigma nell'etichetta; 1 contiene norma/minimi diversi dalla selezione corrente |
| Locale, 25 Word aperti | 1 coincide; 17 hanno tabelle coincidenti ma diciture del modello precedente; 7 non verificabili integralmente con confronto automatico |
| Locale, 10 Word di PDF chiusi | 9 hanno tabelle coincidenti e vecchie diciture; 1 ha sezioni aggiuntive ambigue |

### Casi Alpha da distinguere

- **OL2026001232, ID 174, 7033_01_00/26, aperto:** selezione corrente
  7075 / EN AW 755-2 / T62, Word 7150 / EN AW 755-2 / T76. Differenze reali:
  Cu stampato 1,9–2,5 contro 1,2–2 dello standard corrente; Rp minimo 525
  contro 500, Rm 580 contro 560, A 8 contro 7, oltre ad altri limiti chimici.
  Valori misurati comuni coincidenti. Il registro memorizza `conforme`, ma
  questo non prova la conformità rispetto ai limiti effettivamente nel Word
  (esempio: Cu misurato 1,479, inferiore al minimo stampato 1,9).
  Documento creato 06:31:18 UTC; selezione corrente 06:31:49 UTC.
  Disallineamento certo da gestire con aggiornamento esplicito del Word.
- **OL2026000986, ID 8, 7006_00_00/26, aperto:** CDQ 24-0985 senza riga
  Incoming nel collegamento ricostruibile oggi. Limiti stampati coincidenti,
  ma valori aggregati attuali diversi (es. Rm 492 nel Word, 452 ricostruito).
  Non rigenerare automaticamente da un contesto incompleto; prima chiarire
  il materiale mancante. Non classificare come semplice cambio standard.
- **OL2026001012, ID 24, 7019_00_00/26, aperto:** contenuto confrontato
  coincidente, ma CDQ 26-0969 senza riga Incoming nel contesto attuale.
  La coincidenza dei dati disponibili non dimostra completezza.
- **OL2026000972, ID 3, 7002_00_00/26, PDF chiuso:** Word con norma 603-2
  e minimi meccanici `-`; selezione corrente EN AW 755-2 con Rp 260,
  Rm 310, A 8. La selezione è del 02/10, successiva all'aggiornamento del
  certificato del 30/09. Non è prova di PDF errato al momento della chiusura:
  conservarlo, non riallinearne automaticamente contenuto o conformità.
- **OL2026000981, ID 6, PDF chiuso:** `EN AW 2024 Sigma` nel Word contro
  `EN AW 2024` oggi, tabelle identiche. Coerente con la precedente rimozione
  della variante dal testo certificato, non con un errore numerico.

### Approfondimento Alpha 0986/1012: provenienza e cronologia

Ulteriore audit READ ONLY: i Word non erano stati creati senza certificati.
La spiegazione iniziale «manca un certificato» descriveva solo il contesto
attuale e non spiegava la situazione alla generazione. Le firme/CDQ salvati
nei due certificati e le date `first_seen_at` di Quarta chiariscono:

- OL2026000986: Word generato il 24/07 alle 06:46 UTC, `cdq_signature`
  contenente solo 26-1820, 1456 kg, lotti 10102085/10102086. Fonte presente:
  Incoming #43, documento #35 `DEFAULT_26-1820_20000.pdf`. Quarta vede poi
  26-1818 alle 10:56 UTC del 24/07 (Incoming #46/documento #33 presenti) e
  24-0985 il 27/07 (oggi non trovato). Quindi il materiale dell'OL è aumentato
  dopo il Word. Il confronto attuale Rm 492 → 452 NON è attribuibile al solo
  certificato mancante: sui due CDQ disponibili l'algoritmo prende il minimo,
  min(492,452). La chimica combina i due contributi con i pesi attuali.
- Su Incoming #43, Proprietà, esiste una modifica utente reale il 21/07
  alle 08:12:56 UTC: Rm da 452 a 492 (utente ID 4; fonte/metodo `utente`).
  Il testo estratto del certificato #35 riporta prove T42 con Rm 509/492
  e prove T62 con Rm 452/452: 492 non è inventato, appartiene a una prova
  del certificato. Non presumere errore utente. Le altre prove multiple e la
  loro selezione per trattamento sono una questione distinta da verificare
  prima di qualsiasi rigenerazione (il #33 riporta T42 477 e T62 452).
- OL2026001012: Word generato il 25/08 alle 15:19 UTC con sola firma 26-1909,
  721 kg, lotto 10102141. Fonte Incoming #75, documento #67
  `DEFAULT_26-1909_20000.pdf`, presente; valori con metodo `chatgpt`, fonte
  `certificato`. Rm 378 è presente sia nel testo estratto sia in Incoming e
  nel Word; nessuna modifica numerica Rm successiva nella cronologia.
  Quarta vede il CDQ aggiuntivo 26-0969 il 26/08 alle 07:22 UTC, dopo il Word.
  I valori attuali coincidono perché resta disponibile solo il 26-1909.
- Entrambi i Word hanno `word_source=generated`, nessun filename di ricarica
  manuale; non risultano Word caricati a mano. La modifica manuale del primo
  riguarda il dato in Incoming, non un Word compilato senza sorgente.
- Ricerca attuale dei due CDQ mancanti in righe Incoming, nomi documenti,
  testi estratti/OCR e storico valori: nessun riscontro per i riferimenti
  esatti. Questo NON dimostra che non siano mai esistiti: eventuali record
  cancellati possono aver perso anche lo storico. Non inventare cancellazioni.

Conclusione: si tratta di ampliamento dei materiali dell'OL dopo la generazione,
non prova di perdita dei dati originari o di errore di standard. Conservare
Word e modifiche manuali; verificare completezza dei materiali e trattamento
delle prove prima di proporre un aggiornamento. Nessuna modifica Alpha.

### Dettaglio casi locali non verificabili integralmente

IDs 19, 20, 21, 22, 23, 24 e 25 aperti; ID 34 chiuso. Ispezione XML mirata:
vecchi documenti di prova con sezioni/allegati che riportano un'altra lega
(2618A contro 6082 della prima sezione), tabelle aggiuntive e, per IDs 19/25,
assenza della tabella meccanica principale. ID 25 contiene anche testo di
codice nelle pagine aggiunte. Non assumere che siano documenti validabili
automaticamente; conservare gli originali e separare questi casi di test
dai risultati Alpha. Nessuna correzione o cancellazione effettuata.

### Limiti e proposta conseguente

- Si tratta di confronto dei contenuti OOXML, non di collaudo grafico/PDF
  né di verifica normativa indipendente dei limiti configurati.
- Corrispondenza visibile NON ricostruisce ID/fotografia dello standard
  originario: massimi meccanici e precisione non stampata non sono provati.
- I 147 Word Alpha corrispondenti non vanno dichiarati errati né rigenerati
  in massa per il solo fatto di non avere la nuova tracciabilità. Proporre
  una gestione esplicita del legacy verificato, distinta dai Word nuovi
  tracciati; non attribuire retroattivamente un'identità standard certa.
- Isolare i 3 aperti da approfondire/correggere. Mantenere intatti i chiusi.
  Al deploy rieseguire controllo e hash: Alpha può cambiare nel frattempo.
- Decisione necessaria prima di implementare la migrazione e i blocchi dei
  legacy. La correzione completa resta ancora da terminare.

## Piano restante, dopo tale scelta

1. Salvare con ogni Word nuovo/rigenerato la selezione e una fotografia dei
   parametri standard rilevanti, distinta dalla conformità corrente. Non
   attribuire retroattivamente la selezione attuale ai file precedenti.
2. Confrontare la fotografia con la selezione corrente per mostrare `Word da
   aggiornare`; disattivare PDF e riuso sul documento superato anche lato server.
3. Verificare tutti i percorsi di copia, download, allegati e manuale della
   tabella sopra. Il successo della rigenerazione aggiorna la fotografia; il
   fallimento conserva documento e tracciabilità precedenti.
4. Gestire espressamente i Word legacy secondo la decisione dell'utente, con
   nuova anteprima specifica Alpha e procedura additiva documentata, senza
   generare o modificare in massa documenti/server durante l'audit.
5. Testare standard A conforme → B non conforme, ritorno ad A, stesso standard,
   più DDT/F3, PDF chiuso/riaperto, manuale, allegati, fallimento e concorrenza.

## Verifiche della parte già corretta

- 4 nuovi test JavaScript sul payload; complessivamente 28 test frontend passati.
- Prove backend della generazione con doppio fuori norma chimica/meccanica,
  richiesta senza conferma respinta, rigenerazione con stesso numero/ID,
  mantenimento del file precedente se la generazione fallisce, registro PDF
  chiuso senza lettura dello standard attuale.
- Browser Chromium/Playwright, API interamente simulate: annullamento senza POST,
  rigenerazione conforme e non conforme, doppia conferma manuale, prima
  generazione invariata, errore visibile con vecchio Word ancora disponibile,
  rigenerazione disabilitata per PDF chiuso. Screenshot verificato.
- Skill Computer Use letta: il runtime fallisce prima dell'avvio con
  `helper_unknown_error`; usato il fallback documentato Playwright sulla porta
  temporanea 5174, senza riavviare il frontend abituale né usare dati reali.
- Build frontend riuscita; avvisi preesistenti Browserslist/bundle invariati.
- Suite backend generale: **614 test raccolti, 558 superati e 56 opzionali
  PostgreSQL saltati** (database PostgreSQL isolato non avviato in questa fase).
  Non presentare questo risultato come collaudo PostgreSQL della correzione
  completa, che rimane subordinata alla scelta sui Word precedenti.

La frase cliente sullo standard 7003 è incompleta: nessuna modifica specifica
ai limiti, alle caratteristiche o alla tabella di tale lega è stata dedotta.
