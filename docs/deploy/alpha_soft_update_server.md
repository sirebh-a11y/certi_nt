# Aggiornamento soft alpha su server

Questo documento descrive come aggiornare la alpha sul server `certi-test.forgialluminio.it` partendo dall'app locale gia modificata e da GitHub aggiornato, senza cancellare database, storage documentale o configurazioni server.

## Obiettivo

Aggiornare il codice applicativo Alpha e le sole integrazioni database approvate,
senza sostituire il database con quello locale.

Devono restare intatti:

- dati PostgreSQL esistenti (sono ammesse soltanto le migrazioni additive e il recupero approvati);
- file caricati e generati dall'app;
- file `.env` del server;
- configurazioni Nginx/server fatte da IT.

### Coda DDT: deploy del codice distinto dal recupero dati

La funzione `DDT da certificare` conserva uno snapshot locale e richiede un
recupero storico iniziale. **Non copiare sul server le righe importate nel
database di sviluppo.** Il recupero Alpha deve usare esclusivamente la cache,
i certificati e il database Alpha, confrontati con la vista eSolver corrente.
Prima occorrono backup e dry-run Alpha in sola lettura; conflitti/duplicati
restano in verifica. L'importazione reale e l'attivazione di
`DDT_SNAPSHOT_ENABLED` sono due decisioni distinte, ciascuna con OK esplicito.
Lo script `backend/scripts/import_ddt_legacy_cache.py` è solo per il Compose
locale e non va lanciato su Alpha. Dettagli e controlli nel piano
`docs/tasks/ddt_certification_alert_queue_plan.md`, sezione «Passaggio futuro
su Alpha: dati propri, non copia del locale».

La scadenza visiva DDT usa `DDT_CERTIFICATION_DAYS` (default 7; giorni di
calendario, data DDT inclusa come giorno 1). Il parametro è passato dal Compose
Alpha; non occorre migrare dati per la scadenza. Preservare il valore server se
configurato e mantenerlo concordato con il termine eSolver. Il deploy non deve
attivare il job DDT, importare lo storico o cambiare la configurazione eSolver
implicitamente. Gli avvisi sono informativi, non confermano l'invio al cliente.

Aggiornamento 30/09 — **esclusioni manuali DDT**: il bootstrap aggiunge la tabella
`quarta_taglio_ddt_decisions`, senza ALTER sulle tabelle esistenti. Contiene
motivi/autori/date e storico di esclusioni, ripristini e riaperture per dati
modificati. Includerla nei normali backup PostgreSQL e conservarla nei rollback.
Verificare dopo deploy permessi admin Qualità e admin IT (estesi su richiesta
dell'utente il 30/09), vista Esclusi e conteggio sidebar.
Il report recupero passa a **versione 2** e controlla anche le decisioni:
rifare sempre preview; un vecchio report non è riutilizzabile. Nessuna
esclusione va importata dal database di sviluppo. Dettagli nel documento
`docs/tasks/ddt_manual_exclusions.md`.

#### Recupero DDT Alpha protetto

Prima esecuzione completata il 01/10/2026 su Alpha.10, con autorizzazione
esplicita al recupero e all'attivazione. Risultati e backup nel verbale
`docs/deploy/alpha10_deploy_20261001.md`. La procedura sotto resta il riferimento
operativo: non ripetere il recupero iniziale nei normali deploy successivi.

Comando dedicato: `backend/scripts/recover_ddt_alpha.py`; non usare quello locale.
Serve autorizzazione specifica al recupero, oltre a quella al deploy. Per ogni
esecuzione occorre un nuovo collaudo sui dati Alpha: non attivare il job come
conseguenza automatica di questa procedura.

Ordine, nella finestra di manutenzione concordata:

1. Verificare run/caricamenti conclusi; sospendere accessi e writer applicativi.
   Fermare backend/frontend, non PostgreSQL. Non aprire la pagina Certificazione:
   un refresh della vecchia cache potrebbe rimuovere storico ancora da recuperare.
2. Fare/verificare backup DB **Alpha**, storage e app secondo questo documento,
   prima del cambio codice. Il backup deve appartenere a questa manutenzione.
3. Installare il pacchetto verificato come nel deploy soft ma **non eseguire ancora
   `up -d --build`**. Costruire la nuova immagine backend con `compose build backend`.
4. Eseguire prima `--prepare-schema`, con backup e manutenzione confermati:
   aggiunge soltanto `pdf_file_name` alle due tabelle dei certificati/versioni PDF.
   Non avvia bootstrap/job, non legge eSolver, non aggiorna la vecchia cache,
   non crea la coda e non modifica nomi/file o certificati esistenti.
5. Eseguire `--preview` nel container one-off con configurazione/storage Alpha,
   senza avviare l'app. Presentare il report all'utente; solo dopo OK, `--apply`.
6. Confrontare il risultato con il report: quantità/chiavi, storico, PDF completati,
   duplicati esclusi. Poi riprendere l'avvio e le verifiche del normale deploy soft.
   Se non si prosegue con il recupero, lasciare il job disattivato e annotare che
   riaprire la vecchia app può aggiornare la cache. Non dichiarare recupero concluso.

Esempio di comandi, dal server `/srv/certi_nt/app`, dopo backup e
sostituzione codice. Sostituire i nomi segnaposto con i file di questa esecuzione:

```bash
docker compose --env-file .env -f docker-compose.alpha.yml build backend

# Prerequisito esplicito: due colonne additive, in un'unica transazione.
# Necessario anche se il job DDT rimane disattivato.
docker compose --env-file .env -f docker-compose.alpha.yml run --rm --no-deps \
  -e DDT_SNAPSHOT_ENABLED=false \
  -v /srv/certi_nt/backup:/audit:ro \
  backend python -m scripts.recover_ddt_alpha \
  --prepare-schema --maintenance-confirmed --backup /audit/db_before_alpha_TIMESTAMP.sql

# Report nuovo: il comando non sovrascrive un file esistente.
docker compose --env-file .env -f docker-compose.alpha.yml run --rm --no-deps \
  -e DDT_SNAPSHOT_ENABLED=false \
  -v /srv/certi_nt/backup:/audit \
  backend python -m scripts.recover_ddt_alpha \
  --preview --report /audit/ddt_preview_TIMESTAMP.json

# Solo dopo esame/OK sul report, con accessi e writer ancora sospesi.
docker compose --env-file .env -f docker-compose.alpha.yml run --rm --no-deps \
  -e DDT_SNAPSHOT_ENABLED=false \
  -v /srv/certi_nt/backup:/audit:ro \
  backend python -m scripts.recover_ddt_alpha \
  --apply --report /audit/ddt_preview_TIMESTAMP.json \
  --maintenance-confirmed --backup /audit/db_before_alpha_TIMESTAMP.sql
```

Usare la forma `python -m scripts.recover_ddt_alpha` dalla directory `/app`
del container: l'esecuzione diretta del file non trova il package `app`.
L'avvio con `--help` è stato verificato nel container locale.

Non saltare `--prepare-schema` sulle versioni precedenti: il codice del report
legge anche il nome PDF, assente su Alpha. La preview **non migra automaticamente**
e restituisce `prepare_pdf_filename_schema_before_recovery` se mancano i campi.
La preparazione è ripetibile: i campi e i nomi già presenti restano intatti;
un errore annulla entrambe le aggiunte. Richiede gli stessi lock del recupero
e rifiuta writer concorrenti. Non usare l'avvio normale dell'app per ottenere
questi campi prima del recupero: potrebbe aggiornare la cache storica.

Lo script verifica ambiente Alpha, database `certi_nt`, host Compose `postgres`,
host pubblico e identità del cluster, e richiede il job disabilitato. Il report
scade dopo un'ora. Prima di scrivere rilegge vista eSolver e dati Alpha sotto lock:
se sono cambiati sorgente/cache/certificati/coda/file/codice, richiede nuova
preview e nuova verifica. Non riutilizzare il vecchio report dopo un'applicazione.
Un writer concorrente, sorgente non affidabile o errore annulla l'importazione;
anche la creazione delle tre tabelle DDT (quote, sincronizzazioni, decisioni) è
transazionale. I record ambigui restano
nella vecchia cache, esclusi dall'importazione automatica: non vengono eliminati
né sommati. Le righe correnti vengono aggiornate dalla sorgente corrente, lo
storico già conservato non viene sovrascritto dalla vecchia cache.

Il dump deve essere verificato realmente: il controllo automatico accerta solo
leggibilità/intestazione, non completezza/ripristinabilità. Il ruolo di manutenzione
deve poter leggere `pg_control_system()`; un errore va diagnosticato, non aggirato.
Non esporre report/backup sul web e non inserirli in Git.

#### Attivazione esplicita della raccolta DDT

Dal 01/10 il Compose Alpha passa `DDT_SNAPSHOT_ENABLED` al backend, con default
**false**. L'esempio `.env.alpha.example` resta false. Questa preparazione locale
non autorizza né modifica il `.env` Alpha: verificare il valore effettivo prima
di avviare l'app; non sovrascrivere l'intero `.env` con quello di esempio.

Soltanto dopo recupero verificato e OK specifico all'attivazione:

1. Impostare `DDT_SNAPSHOT_ENABLED=true` nel solo `.env` Alpha.
2. Ricreare il backend con `docker compose --env-file .env -f docker-compose.alpha.yml up -d --no-deps backend`.
   Un semplice `restart` non rilegge le variabili del container.
3. Verificare che il parametro del container sia true e attendere il primo ciclo
   automatico (ogni 15 minuti). Controllare l'ultima esecuzione riuscita, i dati
   conservati e l'avviso di collegamento della pagina. L'avvio del container da
   solo non dimostra che la lettura eSolver sia riuscita.
4. Se il ciclo fallisce, mantenere gli utenti informati e diagnosticare: non
   ripetere l'importazione alla cieca e non dichiarare la sincronizzazione pronta.

Il job conserva anche le quote che escono dalla finestra eSolver. Il recupero
iniziale può però recuperare solo ciò che è effettivamente presente nelle fonti
Alpha controllate: non garantisce dati storici mai acquisiti.

#### Esito audit preparatorio 01/10/2026 (sola lettura, non è un deploy)

- Alpha: `901d491f`, versione `0.1.0.alpha.9.8`; nuove tabelle DDT, campi nome
  PDF e `incoming_loaded_at` ancora assenti. Nessun run AI attivo al controllo.
- Simulazione: 455 quote correnti e 162 storiche recuperabili (55 DDT, 82 OL;
  storico 02/07–30/07). Totale 617, 9 completate e 608 attive; nessun duplicato
  d'identità rilevato. Quattro quote hanno un Word non assegnabile univocamente:
  devono restare in verifica. Sono numeri indicativi da ricalcolare in manutenzione.
- Preservare mapping PostgreSQL `10.10.1.10:5432` e SELECT del ruolo
  `certi_esolver_reader` sulla vista, senza ricreare utenti o password.
- Spazio: circa 3,6 GB liberi; storage 1,2 GB, backup 2,8 GB, database 97 MB,
  cache build Docker circa 3,6 GB. Misurare di nuovo prima dei backup/build.
  Se insufficiente, fermarsi e concordare spazio aggiuntivo o pulizia mirata della
  sola cache build; non eliminare automaticamente backup, immagini di rollback,
  volumi, container di altri servizi o documenti. Non usare `docker system prune`.

Al normale avvio successivo al recupero, il bootstrap completa la colonna/data
Gemba e aggiorna la vista `esolver_export.certi_certificati_pdf` aggiungendo in
coda `NomeFilePdf`. Verificare le colonne precedenti, i permessi read-only,
download PDF e nomi personalizzati, senza rinominare retroattivamente i file.
Le due colonne PDF sono additive e vanno conservate nel rollback del solo codice.

Collaudo locale della preparazione (01/10): **508 test backend superati, nessuno
saltato**, inclusi i test PostgreSQL su un contenitore dedicato senza volumi
applicativi. Provati schema precedente senza colonne PDF/tabelle DDT,
preparazione ripetibile, conservazione di certificati/versioni/cache, recupero
successivo, rollback delle colonne e rifiuto dei writer concorrenti. Verificati
anche `--help`, protezioni manutenzione/backup e Compose con flag assente/false
e true esplicito. Nessuna chiamata AI o modifica ai dati Alpha; frontend invariato.
Il collaudo non sostituisce preview, backup e verifiche nella futura manutenzione.

### Correzione Word per DDT successivi e recupero Alpha (piano 08/10/2026)

**Stato 08/10: implementata e collaudata in locale; NON installata/applicata su Alpha.**
Questa sezione non autorizza deploy o recupero. Restano necessari commit/push
richiesti dall'utente, pacchetto verificato e nuova preview/OK sui dati Alpha.
Comando dedicato: `backend/scripts/recover_ddt_words_alpha.py`, report versione 1.
Verificati `--help`, pianificazione/applicazione ripetibile e lock su PostgreSQL
locale isolato. I comandi operativi sotto andranno eseguiti solo in manutenzione.
Verifica finale locale: 535 test backend superati senza salti, build frontend e
controllo visivo con API simulate superati; dettagli nel documento di audit.
`recover_ddt_alpha.py` recupera gli snapshot DDT, NON ripara questo problema:
non ripetere l'importazione iniziale del 01/10 per correggere i Word.

#### Regola concordata e limiti

- Il Word gia preparato per OL/lavorazione resta la base utilizzabile quando
  arrivano altre spedizioni, anche mesi dopo. Non si conosce a priori il numero
  di DDT di un OL; nessun limite di 60 giorni nella ricerca della base Word o
  nel recupero delle quote gia conservate. Questo non recupera dati mai acquisiti.
- Ogni quota DDT ricevuta mantiene la propria identita completa (documento,
  riga, OL, CodF3 e riferimenti previsti dal modello), non il solo numero DDT.
  Si predispone automaticamente il suo Word con dati della sua spedizione,
  riutilizzando la base compatibile senza chiedere un nuovo "Genera Word Raw".
  Il riuso della base non significa associare una stessa istanza certificato
  a piu quote, ne modificare un file condiviso in-place.
- L'utente completa il PDF della singola quota. Un PDF pronto chiude quella
  quota, non definitivamente l'OL. Un DDT successivo apre solo il nuovo lavoro.
- Messaggi concordati: "Word pronto - in attesa di DDT", "PDF da preparare",
  "PDF pronto". Riepilogo OL: "PDF pronti per tutti i DDT ricevuti" oppure
  "PDF da completare per DDT ricevuti". Mancanza Word, dati incompleti o
  ambiguita devono avere una spiegazione specifica; non dichiarare la quota
  pronta se altri blocchi esistenti impediscono la certificazione.
- Non modificare Incoming, match, standard confermati, conformita, esclusioni
  manuali, scadenze, numerazione, PDF chiusi o modalita di invio eSolver.
  Non introdurre la diversa ereditarieta tra lavorazioni proposta (ma non
  approvata qui) in `docs/modules/quarta_taglio_word_inheritance_rules.md`.

#### Evidenze e requisiti prima del deploy

Aggiornamento audit messaggi 08/10: OL2026000998 ha il PDF chiuso per il DDT
2229 (380 pezzi), non per il successivo 2386 (1701 pezzi, quota 635 senza
record). L'audit esteso ha trovato 18 quote riutilizzabili, incluse le 8 gia
note: rifare sempre la preview, non usare questo numero come vincolo.
La correzione messaggi locale non cambia l'automatismo: nessuna nuova azione
manuale di collegamento Word. Al controllo dopo recupero verificare che la
quota 635 mostri il Word associato/PDF da preparare e che il certificato 17
rimanga PDF chiuso. Non mostrare "in corso" o "restano i controlli" per una
semplice disponibilita della base Word. Riserva qualita separata dallo stato
documento. Nessuna nuova migrazione per gli indicatori di presentazione.

Audit Alpha del 08/10 sul codice installato
`3951822fa3790bd7e1b1b6ced33d384a2fb5edd1`, confrontato con il codice locale:

- OL2026000997: certificato 16, DDT 2354-29/09/2026, 3000 pezzi, Word e PDF
  chiuso; certificato 148, DDT 2397-05/10/2026, 1398 pezzi, stessa lavorazione
  ma Word assente. Il backup Alpha del 01/10 prova che il Word era gia stato
  preparato il 28/07 senza DDT. Non occorre un secondo lavoro manuale Raw.
- Rilevate 8 righe candidate su 7 OL. Successiva verifica della nuova funzione
  di pianificazione sui dati/file Alpha, in processo temporaneo con transazione
  read-only e senza installazioni: tutte e 8 risultano riutilizzabili. Non e la
  preview ufficiale del deploy: ricalcolare ciascuna riga al prossimo deploy,
  incluse quote senza record certificato. Dettagli in
  `docs/tasks/ddt_word_reuse_20261008.md`.
- In `backend/app/modules/quarta_taglio/service.py`, la ricerca della fonte
  (`_previous_word_certificate_for_inheritance`) esclude lo stesso numero di
  certificato, anche quando appartiene alla stessa lavorazione su un altro DDT.
  La selezione del record recente/aperto puo nascondere il Word gia esistente.
- Il Registro filtra i record senza Word e il suo refresh non riprende gli OL
  con sole righe visibili gia chiuse. La propagazione del Word e esclusa nel
  contesto DDT puntuale. Non rimuovere per questo le protezioni sull'identita
  della quota o sulla scrittura separata dei file.
- Il job in `backend/app/modules/quarta_taglio/scheduler.py` raccoglie DDT e
  aggiorna Quarta, ma non garantisce la preparazione automatica dei Word per
  tutte le nuove quote nella versione Alpha installata. La correzione copre anche l'arrivo senza pagine
  aperte e il successivo completamento dei dati mancanti, non solo il pulsante.

La versione locale aggiunge `DDT_WORD_REUSE_ENABLED` (default **false** anche nel
Compose Alpha). Non modifica lo schema DB; usa record/campi esistenti e distingue
il Word riutilizzato con `word_source=ddt_reused`. Il worker opera ogni 15 minuti
sulle quote conservate, senza limite temporale, ed e attivabile separatamente dal
job snapshot. Non aggiungere `true` implicitamente al `.env` server. Con flag false
le aperture generiche non recuperano indirettamente le quote persistenti.

Prerequisiti bloccanti da dimostrare in locale:

1. Nuovo DDT dopo Word, dopo PDF chiuso e dopo mesi; piu DDT contemporanei;
   Word iniziale senza DDT; storico non piu presente nella vista eSolver.
2. Ripetizione e concorrenza tra job/pagina: nessuna duplicazione, stesso risultato
   a parita di dati; nessun recupero massivo al bootstrap prima dell'OK sul report.
3. Distinzione tra riuso della stessa lavorazione e regole preesistenti per altre
   lavorazioni. Stesso OL/numero non basta: verificare CodF3, CDQ/colate e
   compatibilita tecnica. Fonti multiple discordanti richiedono verifica.
4. Word manuali, controlli dinamici mancanti, seconde pagine e allegati PDF:
   conservare i contenuti; non dichiarare automaticamente aggiornato un Word
   che non permette di sostituire tutti i dati della spedizione necessari.
5. File mancanti/corrotti, errore di scrittura/commit e riavvio: nessun record che
   dichiari un file pronto inesistente; nessuna alterazione della fonte o dei
   certificati chiusi. Il rollback SQL da solo NON annulla le scritture su disco.
6. Test PostgreSQL di lock/transazioni, Registro/coda/sidebar, filtri, pulsanti,
   dati nel Word, PDF ed export. PDF chiusi, nomi, token e versioni preesistenti
   devono restare invariati. Verificare anche la UI con il percorso browser locale.

#### Sequenza del prossimo deploy con recupero Word

1. **Prima del fermo:** audit Alpha in sola lettura, stato spazio e stima di
   backup/build/nuovi Word; riferire all'utente. Inventariare tutte le quote
   conservate e le fonti Word, senza una finestra temporale arbitraria. Non usare
   apertura del dettaglio OL/download Word come audit read-only: alcuni percorsi
   attuali scrivono dati o file anche su GET. Nessuna pulizia implicita.
2. **Manutenzione concordata:** verificare run AI e generazioni Word/PDF conclusi;
   sospendere accessi e writer, inclusi job, fermando backend/frontend. Lasciare
   PostgreSQL e gli altri stack attivi. Salvare e verificare backup coerenti DB,
   storage e app/configurazione della stessa manutenzione; conservare le immagini
   di rollback. Registrare impronte di record/versioni e file dei PDF chiusi,
   Word sorgenti, allegati e risultato export prima di intervenire.
3. **Installazione senza avvio automatico:** seguire pacchetto/SOURCE_COMMIT/hash
   del normale deploy, preservare `.env`, mapping, ruoli e dati. Costruire le
   immagini ma sospendere il normale `up -d --build`. Il nuovo codice non deve
   recuperare lo storico in bootstrap. Se emergono migrazioni, documentarle e
   collaudarle separatamente prima: non assumere che siano gia disponibili.
4. **Preview dedicata:** container one-off con DB/storage Alpha e scheduler non
   avviato; transazione PostgreSQL read-only e storage montato in sola lettura,
   senza importare il bootstrap applicativo. Scrivere soltanto il report privato
   in backup. Mostrare per quota: identita, record di destinazione esistente o da
   creare, fonte Word, motivo di compatibilita, dati DDT da inserire, azione ed
   eventuale esclusione dal recupero. Includere fingerprint di codice/dati/fonti
   e confronti di conteggio; distinguere sicure, gia corrette e da verificare.
   Nessun dato, documento o collegamento viene copiato dallo sviluppo locale.
5. **OK esplicito sul report:** il deploy non autorizza il recupero. Se rinviato,
   la riapertura richiede un percorso collaudato che non applichi lo storico
   indirettamente tramite job o pagine. Se tale separazione non e disponibile,
   fermarsi e concordare rinvio/rollback: non riaprire contando sulla sola preview.
6. **Applicazione controllata:** writer ancora fermi, sole quote approvate;
   rivalidare sotto lock sorgenti, destinazioni e codice. Report superato o dati
   cambiati richiedono nuova preview/OK. Riutilizzare la riga corretta se esiste;
   creare solo quella mancante con identita certa. Scrivere nuovi file per le
   destinazioni, mai sovrascrivere la fonte. Proteggere insieme transazione e file
   con gestione degli errori e registro preciso delle modifiche. Non chiudere
   PDF, rinumerare, riaprire certificati o sostituire Word gia presenti.
7. **Verifica prima della riapertura:** confrontare esito e report, impronte dei
   documenti protetti e risultato export (non deve crescere per il solo recupero
   Word). Seconda preview senza ulteriori modifiche sulle quote recuperate.
   Per OL997: riga 2354 e PDF intatti; riga 2397 con Word aggiornato e PDF ancora
   da preparare. Non usare generazione PDF reale su Alpha come test.
8. **Riapertura e sorveglianza:** riprendere avvio/controlli generali sotto,
   conservando configurazione e cadenza DDT gia autorizzate (15 minuti).
   Verificare primo ciclo riuscito, nessuna duplicazione o riscrittura, Registro,
   coda e messaggi. Il caso di nuovo DDT a distanza di mesi si prova in locale:
   non inserire spedizioni fittizie su Alpha. Alla prossima spedizione reale
   controllare la preparazione automatica. Annotare separatamente deploy, quote
   recuperate, escluse con motivo e controlli ancora da osservare.

Comandi da `/srv/certi_nt/app` dopo fermo writer, backup verificati e installazione
del pacchetto. Sostituire `TIMESTAMP` con i nomi di questa manutenzione. Non
modificano le impostazioni persistenti del `.env`: i due flag false valgono solo
nel container one-off, che non avvia job o bootstrap.

```bash
docker compose --env-file .env -f docker-compose.alpha.yml build backend frontend

docker compose --env-file .env -f docker-compose.alpha.yml run --rm --no-deps \
  -e DDT_SNAPSHOT_ENABLED=false -e DDT_WORD_REUSE_ENABLED=false \
  -v /srv/certi_nt/data/storage:/app/storage:ro \
  -v /srv/certi_nt/backup:/audit \
  backend python -m scripts.recover_ddt_words_alpha \
  --preview --report /audit/word_ddt_preview_TIMESTAMP.json

# Solo dopo esame e OK esplicito sul report, writer ancora fermi.
docker compose --env-file .env -f docker-compose.alpha.yml run --rm --no-deps \
  -e DDT_SNAPSHOT_ENABLED=false -e DDT_WORD_REUSE_ENABLED=false \
  -v /srv/certi_nt/backup:/audit \
  backend python -m scripts.recover_ddt_words_alpha \
  --apply --report /audit/word_ddt_preview_TIMESTAMP.json \
  --maintenance-confirmed --backup /audit/db_before_alpha_TIMESTAMP.sql \
  --storage-backup /audit/storage_before_alpha_TIMESTAMP.tgz
```

La preview e PostgreSQL read-only e non interroga eSolver: usa esclusivamente i
dati Alpha gia conservati e i file Alpha. Il report scade dopo un'ora, identifica
cluster/configurazione/codice e impronte DB/file, e non si puo riutilizzare se i
dati sono cambiati. Nessuna password e inclusa nel report. Il recupero rifiuta
writer attivi tramite lock NOWAIT; non li interrompe.

Il file `word_ddt_preview_TIMESTAMP.applied.json` registra destinazioni/fonti e
nuovi file con stato `pending_commit` prima del commit. Per confermare l'esito
servono output `committed`, controlli DB/file e nuova preview: il solo journal
non prova il commit. In caso di esito incerto conservare i file creati e verificare
prima di rimuoverli; un rollback DB non annulla il filesystem. I backup devono
essere verificati/ripristinabili: il comando controlla soltanto leggibilita e
intestazione del dump e presenza dell'archivio storage.

Solo dopo recupero verificato e OK all'automatismo impostare nel `.env` server
`DDT_WORD_REUSE_ENABLED=true`; conservare il valore preesistente di
`DDT_SNAPSHOT_ENABLED`. Ricreare il backend, non limitarsi a `restart`, e
verificare il primo ciclo e il log `ddt_word_reuse`. Se si rinvia il recupero,
lasciare false e dichiarare che i Word mancanti non sono stati recuperati.
Non esporre report/journal/backup via web o Git. Nessun PDF viene chiuso o inviato
dal recupero: l'utente completa i PDF delle nuove quote.

#### Fallimento e rollback specifici

Prima dell'applicazione e possibile il rollback del solo codice se schema e dati
sono compatibili. Dopo il recupero Word, il rollback codice NON annulla le nuove
associazioni o i nuovi file: usare il registro modifiche e un piano verificato
DB + storage. Conservare anche lo stato del fallimento. Ripristino dati e rimozione
file richiedono decisione esplicita; non cancellare file condivisi o sorgenti.
Se gli utenti hanno ripreso a lavorare, non ripristinare integralmente il vecchio
dump: perderebbe i lavori successivi. Fermarsi, fare un nuovo backup e pianificare
una correzione mirata. Non dichiarare recupero riuscito se rimangono errori non
spiegati; i casi ambigui restano visibili senza associazioni forzate.

### Separazione obbligatoria della futura linea nuovi fornitori

Il futuro laboratorio per configurare nuovi fornitori non esiste ancora e non deve essere presente su Alpha durante il suo sviluppo.

Regola corrente:

```text
main                         → unica fonte autorizzata per i deploy Alpha
feature/supplier-lab         → futuro branch di sviluppo esclusivamente locale
```

Il nome `feature/supplier-lab` è riservato al futuro ramo: il branch non è ancora stato creato.

Durante lo sviluppo della linea generale:

- il codice Lab resta nel branch dedicato;
- il branch Lab non viene unito in `main`;
- il pacchetto `alpha-produzione` continua a essere generato esclusivamente da `origin/main`;
- route, API, tabelle, flag e storage Lab non devono essere installati su Alpha;
- i Markdown di analisi possono essere presenti in `main`: documentano il lavoro futuro ma non abilitano alcuna funzione;
- nessun controllo deve essere rimosso con la motivazione che la pagina sarebbe comunque nascosta agli utenti.

Quando il laboratorio sarà completo in locale serviranno, nell'ordine:

1. audit conclusivo e test di isolamento;
2. nuovo `procedi` esplicito dell'utente;
3. merge intenzionale del branch in `main`;
4. modifica intenzionale dei controlli di esclusione riportati in questo documento;
5. nuovo pacchetto e deploy Alpha;
6. laboratorio visibile solamente ad Admin IT e motore produttivo ancora disabilitato.

L'installazione futura del Lab su Alpha non autorizzerà automaticamente il suo utilizzo in Incoming. L'attivazione produttiva richiederà un'altra decisione separata.

## Percorsi

Sviluppo locale:

- repo app: `C:\Users\sireb\VScodeProjects\certi_nt`
- repo deploy: `C:\Users\sireb\VScodeProjects\certi_nt\deploy_repo\certi_nt_deploy`
- cartella alpha deploy: `deploy_repo\certi_nt_deploy\alpha-produzione`

Server:

- app: `/srv/certi_nt/app`
- dati persistenti: `/srv/certi_nt/data`
- database: `/srv/certi_nt/data/postgres`
- storage documenti: `/srv/certi_nt/data/storage`
- backup: `/srv/certi_nt/backup`

## Parametri infrastrutturali Alpha verificati

Informazioni confermate da IT:

- DNS: `certi-test.forgialluminio.it` → `10.10.1.10`;
- frontend Alpha pubblicato localmente sulla porta host `8080`;
- backend Alpha pubblicato localmente sulla porta host `8001`;
- il 28 luglio 2026 PostgreSQL risultava disponibile soltanto nella rete Docker interna;
- il compose Alpha ora prevede un mapping host persistente e configurabile tramite `.env`;
- Nginx esistente instrada l'host `certi-test.forgialluminio.it` al frontend;
- Nginx instrada `certi-test.forgialluminio.it/api` al backend;
- pubblicazione applicativa attuale in HTTP, senza HTTPS;
- backup della VM ogni quattro ore, dalle 07:00 alle 19:00.

Parametri Nginx confermati da IT:

```nginx
client_max_body_size 200m;
proxy_connect_timeout 300s;
proxy_send_timeout 300s;
proxy_read_timeout 300s;
```

Queste impostazioni appartengono alla configurazione server gestita da IT e devono restare
intatte durante un deploy soft.

### Mapping PostgreSQL persistente

Il mapping della porta PostgreSQL fa parte di `docker-compose.alpha.yml` e usa:

```dotenv
POSTGRES_BIND_HOST=127.0.0.1
POSTGRES_HOST_PORT=5432
```

Con `127.0.0.1` PostgreSQL è raggiungibile soltanto dal server Alpha. È l'impostazione sicura
da usare finché IT non ha verificato firewall, IP sorgente e utenti read-only.

Per rendere disponibile la vista a eSolver/Nemesi, dopo la conferma di Matteo:

```dotenv
POSTGRES_BIND_HOST=10.10.1.10
POSTGRES_HOST_PORT=5432
```

Il collegamento diventa:

```text
10.10.1.10:5432 -> container postgres:5432
```

Questi valori stanno nel `.env` del server, che il deploy soft preserva. Non aggiungere il
mapping manualmente al compose presente soltanto sul server: il file viene sostituito dal
pacchetto e la modifica andrebbe persa al deploy successivo.

Non impostare `POSTGRES_BIND_HOST=0.0.0.0`. Prima di usare `10.10.1.10` devono essere
confermati:

- firewall TCP `5432` limitato agli IP di Nemesi/eSolver e Quarta;
- ruoli PostgreSQL dedicati in sola lettura;
- assenza di accesso alle tabelle applicative;
- modalità SSL concordata con IT.

SSH dal PC locale, usando PowerShell:

```powershell
ssh -i "$env:USERPROFILE\.ssh\certi_nt_admcerti01_ed25519" admcerti01@certi-test.forgialluminio.it
```

La chiave da usare qui e la chiave privata locale `certi_nt_admcerti01_ed25519`, non il file `.pub`.

Non inserire password SSH in questo documento, nel repository o nei pacchetti di deploy.
L'accesso deve usare la chiave locale oppure un secret gestito fuori dal repository.

Se PowerShell crea problemi di quoting con comandi lunghi, usare anche la forma con path esplicito:

```powershell
ssh -i C:\Users\sireb\.ssh\certi_nt_admcerti01_ed25519 admcerti01@certi-test.forgialluminio.it
```

## Flusso corretto

1. Sviluppo e test in locale sul ramo corretto.
2. Verifica che il deploy corrente provenga da `main` e non dal futuro branch Lab.
3. Verifica che il commit `main` non contenga il modulo Lab non ancora autorizzato.
4. Commit e push del repo app.
5. Registrazione del commit app esatto in `alpha-produzione/SOURCE_COMMIT`.
6. Rigenerazione completa di `alpha-produzione` dal commit app, senza copie parziali e senza file non tracciati.
7. Confronto integrale tra commit app e pacchetto deploy.
8. Verifica che backend, footer e bundle frontend riportino la stessa versione.
9. Test del contenuto del pacchetto deploy.
10. Commit, push e tag del repo deploy.
11. Creazione archivio `.tar` pulito dalla cartella `alpha-produzione`.
12. Copia archivio sul server in `/srv/certi_nt/backup`.
13. Backup dell'app server attuale.
14. Sostituzione soft del codice, preservando `.env`, database e storage.
15. Verifica dei parametri PostgreSQL preservati nel `.env`.
16. Avvio Docker.
17. Verifica del contenuto, delle versioni, dell'assenza del Lab non autorizzato e del mapping PostgreSQL realmente installati.

## Prima di aggiornare

Controllare che il server sia sano:

```bash
cd /srv/certi_nt/app
docker compose --env-file .env -f docker-compose.alpha.yml ps
test -f .env
test -d /srv/certi_nt/data/postgres
test -d /srv/certi_nt/data/storage
grep -E '^POSTGRES_(BIND_HOST|HOST_PORT)=' .env || true
```

Non procedere se:

- manca `.env`;
- PostgreSQL non e attivo o non e healthy;
- mancano le cartelle `data/postgres` o `data/storage`;
- l'app e in mezzo a un caricamento importante.

### Spazio server: controllo obbligatorio a ogni deploy

Prima di **ogni** deploy Alpha, misurare e riferire all'utente spazio totale,
occupato e libero, insieme alle dimensioni di backup, storage, database e Docker.
Stimare anche lo spazio richiesto dai nuovi backup e dalle build. Comunicare il
risultato **prima** di iniziare la parte che consuma spazio; decidere con l'utente
se fare una pulizia e quali elementi specifici includere. Una pulizia non e una
conseguenza automatica del deploy. Se lo spazio non basta, fermarsi e concordare
come procedere.

Controlli in sola lettura sul server:

```bash
df -h /srv/certi_nt
du -sh /srv/certi_nt/backup /srv/certi_nt/data/storage /srv/certi_nt/app
du -sh /srv/certi_nt/data/storage_before_hard_reset_* 2>/dev/null || true
docker system df
docker exec app-postgres-1 du -sh /var/lib/postgresql/data
find /srv/certi_nt/backup -maxdepth 1 -type f -printf '%s %TY-%Tm-%Td %f\n' \
  | sort -nr | head -20
```

Misurare PostgreSQL **dentro il container**: l'utente SSH non puo leggere tutta
la directory dati e un `du` sul percorso host potrebbe indicare erroneamente
pochi kilobyte. Le dimensioni Docker sono stime con layer condivisi: non
sommare ingenuamente ogni riga al totale del filesystem.

Riferimento del **01/10/2026**, da ricontrollare a ogni deploy: filesystem 23 GB,
20 GB occupati (91%), 2,2 GB liberi. Backup 3,9 GB; documenti correnti 1,2 GB;
vecchio storage conservato dopo il reset di luglio 637 MB; PostgreSQL 297 MB su
disco (database `certi_nt` circa 98 MB); immagini Docker 3,8 GB; cache build
Docker 3,0 GB, di cui circa 2,9 GB segnalati come recuperabili. Il server ospita
anche un'altra applicazione Docker: non trattare tutte le sue immagini come
materiale CERTI eliminabile.

Possibili pulizie da **valutare con l'utente**, dopo nuovo inventario:

- Cache build Docker: materiale intermedio ricreabile (installazioni OCR,
  LibreOffice, librerie Python e JavaScript, compilazione frontend). La pulizia
  non cancella database, PDF o immagini dei container attivi, ma puo allungare
  i prossimi deploy e richiedere nuovi download. Verificare prima che non sia in
  corso una build e quali cache appartengano anche all'altra applicazione.
- Sei grandi archivi di luglio relativi ad Alpha.9.4/9.5/9.5.1: circa 1,4 GB
  complessivi. Contengono anche immagini temporanee di test. Prima di rimuoverli
  dal server, verificare contenuto, esigenza di rollback e presenza di una copia
  esterna affidabile. Non sono necessari per il rollback immediato di Alpha.10.
- Vecchia cartella `storage_before_hard_reset_20260715_080925`: 637 MB.
  Esiste anche un archivio storico `.tgz` di circa 620 MB, risultato leggibile;
  non e ancora stata verificata la corrispondenza completa dei contenuti. Non
  eliminare la cartella finche questo confronto e la necessita storica non sono
  chiariti.

**ATTENZIONE:** prima di qualsiasi cancellazione ricontrollare attentamente i
percorsi esatti, il contenuto, le dipendenze, i backup e la possibilita reale di
ripristino. Conservare i documenti e il database attuali, i backup del deploy
Alpha.10 e le immagini di rollback `before-alpha10-20261001` finche servono.
Non usare una pulizia generale Docker o cancellazioni per nome generico. Nessuna
delle possibili pulizie sopra e autorizzata da questa sezione: mostrare ogni
volta i dati aggiornati all'utente e scegliere insieme cosa fare.

Se i due parametri PostgreSQL non sono ancora presenti, aggiungerli al `.env` prima di
installare la versione del compose che contiene il mapping. Usare `127.0.0.1` finché Matteo
non ha confermato l'apertura controllata verso Nemesi:

```dotenv
POSTGRES_BIND_HOST=127.0.0.1
POSTGRES_HOST_PORT=5432
```

Se è già prevista la pubblicazione esterna, verificare prima che la porta host scelta non sia
occupata:

```bash
ss -ltn | grep ':5432 ' || true
```

### Controllare run AI attivi

Prima di fermare backend/frontend controllare che non ci siano elaborazioni AI in corso.

Il nome tabella corretto e `acquisition_processing_runs`.

```bash
cd /srv/certi_nt/app
docker compose --env-file .env -f docker-compose.alpha.yml exec -T backend \
  python -c "from app.core.database import SessionLocal; from sqlalchemy import text; db=SessionLocal(); rows=db.execute(text(\"select id, stato, fase_corrente from acquisition_processing_runs where stato in ('in_coda', 'in_esecuzione') order by id desc limit 10\")).mappings().all(); print([dict(r) for r in rows]); db.close()"
```

Se torna `[]`, non ci sono run attivi.

Se ci sono run `in_coda` o `in_esecuzione`, non aggiornare subito: si rischia di interrompere un caricamento documenti o una lettura AI lunga.

Alternativa piu semplice via PostgreSQL, utile quando il quoting Python da PowerShell diventa fragile:

```bash
cd /srv/certi_nt/app
docker compose --env-file .env -f docker-compose.alpha.yml exec -T postgres \
  psql -U certi_nt -d certi_nt \
  -c "select id, stato, fase_corrente from acquisition_processing_runs where stato in ('in_coda', 'in_esecuzione') order by id desc limit 10;"
```

Se torna `(0 rows)`, non ci sono run attivi.

## Allineamento obbligatorio tra app e pacchetto deploy

Il pacchetto non deve essere aggiornato copiando soltanto i file dell'ultima modifica e non deve essere creato copiando la cartella di lavoro locale. Entrambi i metodi hanno gia prodotto pacchetti incompleti o contenenti file temporanei.

La fonte del pacchetto deve essere un commit preciso e gia pubblicato del repo app. Quel commit deve essere scritto in:

```text
alpha-produzione/SOURCE_COMMIT
```

Sono ammessi nel pacchetto soltanto:

- tutti i file tracciati dal commit app indicato in `SOURCE_COMMIT`, con contenuto identico;
- `README_ALPHA.md`, specifico del repository deploy;
- `SOURCE_COMMIT`, contenente l'hash completo del commit app.

Qualsiasi altro file deve bloccare la creazione del tag.

### Perche questo controllo e obbligatorio

Audit del 21 luglio 2026:

- il backend del pacchetto `alpha.9.5` riportava `0.1.0.alpha.9.5`, ma il footer riportava ancora `0.1.0.alpha.9.4`;
- il pacchetto conteneva 518 file di lavoro sotto `backend/tmp` e `backend/tmp_eval`, per circa 244 MiB;
- due file di documentazione non tracciati dal repo app erano entrati nel deploy;
- nei pacchetti `alpha.9.1` e `alpha.9.2` erano rimasti temporaneamente file backend diversi dal commit app disponibile al momento del tag.

Le cause individuate sono:

- sincronizzazione manuale per elenco parziale di file;
- copia dalla working tree invece che da un commit Git;
- assenza dell'hash del commit sorgente nel pacchetto;
- assenza di un confronto completo tra i due alberi Git;
- verifica della sola versione backend, senza controllare footer e bundle frontend.

### Generare il pacchetto da un commit pulito

Da PowerShell usare una directory temporanea generata esclusivamente da `git archive`. Il comando include solo file tracciati dal commit scelto e non puo quindi includere PDF, immagini, cache o script temporanei presenti nella working tree.

```powershell
$appRepo = 'C:\Users\sireb\VScodeProjects\certi_nt'
$deployRepo = 'C:\Users\sireb\VScodeProjects\certi_nt\deploy_repo\certi_nt_deploy'
$alphaDir = Join-Path $deployRepo 'alpha-produzione'
$expectedAlphaDir = 'C:\Users\sireb\VScodeProjects\certi_nt\deploy_repo\certi_nt_deploy\alpha-produzione'

$sourceCommit = (git -C $appRepo rev-parse HEAD).Trim()
$remoteCommit = (git -C $appRepo rev-parse origin/main).Trim()
$currentBranch = (git -C $appRepo branch --show-current).Trim()
if ($currentBranch -ne 'main') {
    throw "Deploy Alpha vietato dal branch '$currentBranch': usare esclusivamente main."
}
if ($sourceCommit -ne $remoteCommit) {
    throw 'Il commit app locale non coincide con origin/main: fare push prima del deploy.'
}
git -C $appRepo diff --quiet
if ($LASTEXITCODE -ne 0) {
    throw 'Il repo app contiene modifiche tracciate non committate.'
}
git -C $appRepo diff --cached --quiet
if ($LASTEXITCODE -ne 0) {
    throw 'Il repo app contiene modifiche in staging non committate.'
}

# Protezione temporanea: resta obbligatoria finche il laboratorio nuovi fornitori
# non e completo, approvato e autorizzato per la prima installazione Alpha.
$forbiddenLabPaths = @(
    'backend/app/modules/supplier_lab',
    'frontend/src/pages/supplierLab'
)
foreach ($relativePath in $forbiddenLabPaths) {
    if (Test-Path -LiteralPath (Join-Path $appRepo $relativePath)) {
        throw "Modulo Lab non ancora autorizzato presente in main: $relativePath"
    }
}

$labMarkers = @(
    git -C $appRepo grep -n -E `
      'app/modules/supplier_lab|app\.modules\.supplier_lab|/supplier-lab|SUPPLIER_LAB_ENABLED|GENERAL_SUPPLIER_RUNTIME_ENABLED' `
      $sourceCommit -- backend/app frontend/src docker-compose.alpha.yml 2>$null
)
if ($LASTEXITCODE -eq 0 -and $labMarkers.Count) {
    $labMarkers | ForEach-Object { Write-Host "Riferimento Lab non autorizzato: $_" }
    throw 'Il commit main contiene codice o configurazione Lab non ancora autorizzati per Alpha.'
}
if ($LASTEXITCODE -notin @(0, 1)) {
    throw 'Controllo riferimenti Lab fallito.'
}

$shortCommit = $sourceCommit.Substring(0, 12)
$stageDir = Join-Path $deployRepo ".alpha-stage-$shortCommit"
$sourceArchive = Join-Path $deployRepo ".alpha-source-$shortCommit.tar"
if (Test-Path -LiteralPath $stageDir) {
    throw "Directory temporanea gia presente: $stageDir"
}
if (Test-Path -LiteralPath $sourceArchive) {
    throw "Archivio temporaneo gia presente: $sourceArchive"
}

New-Item -ItemType Directory -Path $stageDir | Out-Null
git -C $appRepo archive --format=tar --output=$sourceArchive $sourceCommit
if ($LASTEXITCODE -ne 0) { throw 'git archive del repo app fallito.' }
tar -xf $sourceArchive -C $stageDir
if ($LASTEXITCODE -ne 0) { throw 'Estrazione del commit app fallita.' }

Copy-Item -LiteralPath (Join-Path $alphaDir 'README_ALPHA.md') -Destination $stageDir
Set-Content -LiteralPath (Join-Path $stageDir 'SOURCE_COMMIT') -Value $sourceCommit -NoNewline

$forbiddenPaths = @(
    '.env',
    'backend/tmp',
    'backend/tmp_eval',
    'backend/storage',
    'frontend/node_modules',
    'frontend/dist'
)
foreach ($relativePath in $forbiddenPaths) {
    if (Test-Path -LiteralPath (Join-Path $stageDir $relativePath)) {
        throw "Contenuto vietato nel pacchetto: $relativePath"
    }
}

if ([IO.Path]::GetFullPath($alphaDir) -ne [IO.Path]::GetFullPath($expectedAlphaDir)) {
    throw "Target alpha non valido: $alphaDir"
}

robocopy $stageDir $alphaDir /MIR /R:1 /W:1 /NFL /NDL /NJH /NJS /NP
$copyExitCode = $LASTEXITCODE
if ($copyExitCode -gt 7) {
    throw "Sincronizzazione alpha fallita con codice robocopy $copyExitCode"
}

Remove-Item -LiteralPath $stageDir -Recurse -Force
Remove-Item -LiteralPath $sourceArchive -Force
git -C $deployRepo status --short
```

`robocopy /MIR` elimina dal solo percorso validato `alpha-produzione` i file che non appartengono al nuovo pacchetto. Non riutilizzare il comando cambiando il target senza ripetere il controllo del percorso assoluto.

Prima di continuare, controllare che lo stato del repo deploy mostri soltanto l'allineamento previsto. In particolare non devono comparire file sotto `backend/tmp`, `backend/tmp_eval`, storage, cache o build locali.

### Verificare integralmente i due alberi Git

Dopo il commit locale del repo deploy, ma prima di tag e push, eseguire questo controllo. Non basta verificare soltanto i file modificati nell'ultimo commit.

```powershell
$appRepo = 'C:\Users\sireb\VScodeProjects\certi_nt'
$deployRepo = 'C:\Users\sireb\VScodeProjects\certi_nt\deploy_repo\certi_nt_deploy'
$sourceCommit = (git -C $appRepo rev-parse HEAD).Trim()
$deployCommit = (git -C $deployRepo rev-parse HEAD).Trim()

function Read-GitTree([string]$repo, [string]$tree) {
    $result = @{}
    foreach ($line in (git -C $repo ls-tree -r $tree)) {
        if ($line -match '^\d+ blob ([0-9a-f]+)\t(.+)$') {
            $result[$Matches[2]] = $Matches[1]
        }
    }
    return $result
}

$sourceTree = Read-GitTree $appRepo $sourceCommit
$deployTree = Read-GitTree $deployRepo "${deployCommit}:alpha-produzione"
$allowedDeployOnly = @('README_ALPHA.md', 'SOURCE_COMMIT')

$missingFromDeploy = @(
    $sourceTree.Keys |
        Where-Object { -not $deployTree.ContainsKey($_) } |
        Sort-Object
)
$differentContent = @(
    $sourceTree.Keys |
        Where-Object { $deployTree.ContainsKey($_) -and $sourceTree[$_] -ne $deployTree[$_] } |
        Sort-Object
)
$unexpectedInDeploy = @(
    $deployTree.Keys |
        Where-Object { -not $sourceTree.ContainsKey($_) -and $allowedDeployOnly -notcontains $_ } |
        Sort-Object
)

$recordedSource = (git -C $deployRepo show "${deployCommit}:alpha-produzione/SOURCE_COMMIT").Trim()
if ($recordedSource -ne $sourceCommit) {
    throw "SOURCE_COMMIT non valido: atteso $sourceCommit, trovato $recordedSource"
}

if ($missingFromDeploy.Count -or $differentContent.Count -or $unexpectedInDeploy.Count) {
    $missingFromDeploy | ForEach-Object { Write-Host "Manca nel deploy: $_" }
    $differentContent | ForEach-Object { Write-Host "Contenuto diverso: $_" }
    $unexpectedInDeploy | ForEach-Object { Write-Host "File inatteso nel deploy: $_" }
    throw 'Pacchetto deploy non allineato: non creare tag e non fare push.'
}

Write-Host "Pacchetto allineato al commit app $sourceCommit"
```

Il confronto usa gli hash Git dei blob, quindi rileva anche differenze non visibili con un semplice elenco di nomi.

### Verificare versione backend, footer e bundle

La stessa versione deve essere presente nel backend e nel footer prima della build:

```powershell
$backendFile = Join-Path $appRepo 'backend/app/main.py'
$footerFile = Join-Path $appRepo 'frontend/src/components/layout/Footer.jsx'
$backendMatch = Select-String -LiteralPath $backendFile -Pattern 'version="([^"]+)"'
$footerMatch = Select-String -LiteralPath $footerFile -Pattern 'Versione sistema ([0-9A-Za-z._-]+)'

if (-not $backendMatch -or -not $footerMatch) {
    throw 'Versione backend o footer non trovata.'
}

$backendVersion = $backendMatch.Matches[0].Groups[1].Value
$footerVersion = $footerMatch.Matches[0].Groups[1].Value
if ($backendVersion -ne $footerVersion) {
    throw "Versioni disallineate: backend=$backendVersion footer=$footerVersion"
}
```

Costruire poi il frontend dal pacchetto, non dalla sola cartella app:

```powershell
Push-Location (Join-Path $deployRepo 'alpha-produzione/frontend')
try {
    npm ci
    if ($LASTEXITCODE -ne 0) { throw 'Installazione dipendenze frontend del pacchetto fallita.' }
    npm run build
    if ($LASTEXITCODE -ne 0) { throw 'Build frontend del pacchetto fallita.' }
    $expectedText = "Versione sistema $footerVersion"
    $bundleMatch = Get-ChildItem -LiteralPath 'dist' -Recurse -File |
        Select-String -SimpleMatch $expectedText |
        Select-Object -First 1
    if (-not $bundleMatch) {
        throw "Il bundle frontend non contiene: $expectedText"
    }
}
finally {
    Pop-Location
}
```

Se uno qualsiasi di questi controlli fallisce, non creare il tag e non trasferire l'archivio.

## Creare archivio dal deploy repo

Dal PC locale, nel repo deploy:

```powershell
cd C:\Users\sireb\VScodeProjects\certi_nt\deploy_repo\certi_nt_deploy
git status
git add alpha-produzione
git diff --cached --check
git commit -m "Update alpha deploy package 0.1.0.alpha.X"
```

Eseguire ora il confronto integrale e i controlli versione descritti nella sezione precedente. Solo se terminano senza errori creare tag e archivio:

```powershell
git tag v0.1.0-alpha.X-deploy
git archive --format=tar --output alpha-produzione-v0.1.0-alpha.X-deploy.tar v0.1.0-alpha.X-deploy:alpha-produzione

$archive = 'alpha-produzione-v0.1.0-alpha.X-deploy.tar'
$archiveEntries = @(tar -tf $archive)
$forbiddenEntries = @(
    $archiveEntries | Where-Object {
        $_ -match '(^|/)(tmp|tmp_eval|storage|node_modules|dist|__pycache__)(/|$)' -or
        $_ -eq '.env'
    }
)
if ($forbiddenEntries.Count) {
    $forbiddenEntries | ForEach-Object { Write-Host "Contenuto vietato nell'archivio: $_" }
    throw 'Archivio deploy non pulito.'
}
if ($archiveEntries -notcontains 'SOURCE_COMMIT') {
    throw "SOURCE_COMMIT manca dall'archivio deploy."
}

$archiveSize = (Get-Item -LiteralPath $archive).Length
if ($archiveSize -gt 50MB) {
    throw "Archivio insolitamente grande: $archiveSize byte. Verificare prima del trasferimento."
}

Get-FileHash -Algorithm SHA256 -LiteralPath $archive
git push origin main
git push origin v0.1.0-alpha.X-deploy
```

`X` va sostituito con il numero reale della versione.

Se il tag esiste gia e si scopre che non rappresenta il pacchetto corretto, non spostare il tag con force push.
Creare invece un tag progressivo, per esempio `v0.1.0-alpha.6.1-deploy`.
In quel caso la versione applicativa resta `0.1.0.alpha.6`, mentre il suffisso `.1` indica solo il pacchetto deploy aggiornato.

Gli archivi `.tar` creati localmente servono solo per il trasferimento sul server. Possono rimanere non tracciati nel repo deploy e non vanno aggiunti al commit.

La soglia di 50 MiB e intenzionalmente superiore alla dimensione normale osservata del codice. Non aumentarla per far passare il controllo: prima identificare e documentare quali file hanno aumentato il pacchetto.

## Copiare archivio sul server

Da PowerShell locale:

```powershell
scp -i "$env:USERPROFILE\.ssh\certi_nt_admcerti01_ed25519" `
  C:\Users\sireb\VScodeProjects\certi_nt\deploy_repo\certi_nt_deploy\alpha-produzione-v0.1.0-alpha.X-deploy.tar `
  admcerti01@certi-test.forgialluminio.it:/srv/certi_nt/backup/
```

Confrontare sempre SHA-256 locale e server prima di estrarre:

```powershell
(Get-FileHash -Algorithm SHA256 `
  C:\Users\sireb\VScodeProjects\certi_nt\deploy_repo\certi_nt_deploy\alpha-produzione-v0.1.0-alpha.X-deploy.tar).Hash

ssh -i "$env:USERPROFILE\.ssh\certi_nt_admcerti01_ed25519" `
  admcerti01@certi-test.forgialluminio.it `
  'sha256sum /srv/certi_nt/backup/alpha-produzione-v0.1.0-alpha.X-deploy.tar'
```

I due hash devono essere identici, ignorando maiuscole e minuscole. Se non coincidono, non proseguire.

Il contenuto di `SOURCE_COMMIT` può terminare con LF o CRLF. Nei confronti shell
normalizzare soltanto questi fine-riga con `tr -d '\r\n'`, senza cambiare il
file dell'archivio/installato. Il confronto dell'archivio resta sullo SHA-256 completo.

## Backup prima dell'aggiornamento

Sul server:

```bash
set -e
TAG=v0.1.0-alpha.X-deploy
TS=$(date +%Y%m%d_%H%M%S)
cd /srv/certi_nt

tar -czf "backup/app_before_${TAG}_${TS}.tgz" app
```

Questo backup salva il codice applicativo corrente e il `.env`, ma non duplica tutto il database.

### Backup database

Fare sempre un dump DB prima di aggiornamenti che cambiano tabelle, colonne o logiche dati.

Sul server alpha attuale usare esplicitamente utente e database:

```bash
cd /srv/certi_nt/app
TS=$(date +%Y%m%d_%H%M%S)
docker compose --env-file .env -f docker-compose.alpha.yml exec -T postgres \
  pg_dump -U certi_nt certi_nt \
  > "/srv/certi_nt/backup/db_before_alpha_${TS}.sql"
```

Nota: il comando con `"$POSTGRES_USER"` e `"$POSTGRES_DB"` dentro `sh -lc` puo fallire se quelle variabili non sono disponibili nel processo shell del container. In quel caso `pg_dump` prova l'utente `root` e fallisce. Per questo, nella procedura alpha, usare `pg_dump -U certi_nt certi_nt`.

Per aggiornamenti solo frontend/backend senza modifiche DB, il dump e consigliato ma non sempre obbligatorio. In alpha conviene farlo spesso.

## Aggiornamento soft

**Se il deploy include la correzione Word per DDT successivi**, seguire anche la
sezione dedicata del 08/10/2026: stop dei writer, backup DB/storage, build senza
avvio, preview e OK separato al recupero prima della riapertura. Non eseguire
alla cieca l'ultimo `up -d --build` del blocco sotto. La procedura dedicata deve
essere stata implementata e collaudata: questo Markdown non la sostituisce.

**Se è autorizzato anche il primo recupero DDT**, applicare la variante sopra:
backup con writer fermi e pausa prima del comando finale `up -d --build`, per
preview/import con la nuova immagine. Non avviare prima l'app, che aggiorna la
cache utilizzata per recuperare lo storico.

Sul server:

```bash
set -e
TAG=v0.1.0-alpha.X-deploy
ARCHIVE=alpha-produzione-${TAG}.tar
EXPECTED_SOURCE_COMMIT=HASH_COMPLETO_COMMIT_APP
TS=$(date +%Y%m%d_%H%M%S)

cd /srv/certi_nt
test -f "backup/$ARCHIVE"
test -f app/.env
test -d data/postgres
test -d data/storage
test "$(tar -xOf "backup/$ARCHIVE" SOURCE_COMMIT | tr -d '\r\n')" = "$EXPECTED_SOURCE_COMMIT"

tar -czf "backup/app_before_${TAG}_${TS}.tgz" app

cd app
test "$(pwd -P)" = "/srv/certi_nt/app"
docker compose --env-file .env -f docker-compose.alpha.yml stop backend frontend

find . -mindepth 1 -maxdepth 1 ! -name .env -exec rm -rf {} +
tar -xf "../backup/$ARCHIVE" -C .
test "$(tr -d '\r\n' < SOURCE_COMMIT)" = "$EXPECTED_SOURCE_COMMIT"

docker compose --env-file .env -f docker-compose.alpha.yml up -d --build
docker compose --env-file .env -f docker-compose.alpha.yml ps
```

Nota importante: non usare `docker compose down -v`, perche puo cancellare volumi se la configurazione cambia.

## Controlli dopo aggiornamento

Sul server:

```bash
cd /srv/certi_nt/app
docker compose --env-file .env -f docker-compose.alpha.yml ps
docker compose --env-file .env -f docker-compose.alpha.yml logs --tail=120 backend
docker port app-postgres-1 5432/tcp
ss -ltn | grep ':5432 '
curl -I http://127.0.0.1:8080/
curl -I http://127.0.0.1:8001/docs
```

Il controllo PostgreSQL deve corrispondere al valore conservato nel `.env`:

- con `POSTGRES_BIND_HOST=127.0.0.1` deve comparire `127.0.0.1:5432`;
- con `POSTGRES_BIND_HOST=10.10.1.10` deve comparire `10.10.1.10:5432`;
- se `docker port` non restituisce il mapping previsto, il deploy non è concluso;
- non correggere il compose direttamente sul server: correggere configurazione tracciata o
  `.env`, poi ricreare il servizio.

Quando la vista eSolver è attiva, controllare inoltre che il ruolo read-only esista ancora e
che la vista sia presente:

```bash
docker compose --env-file .env -f docker-compose.alpha.yml exec -T postgres \
  psql -U certi_nt -d certi_nt -P pager=off \
  -c "select to_regclass('esolver_export.certi_certificati_pdf') as export_view;" \
  -c "select rolname from pg_roles where rolname in ('certi_esolver_reader', 'certi_quarta_reader');"
```

La query non mostra password. I nomi effettivi dei ruoli devono essere aggiornati nel comando
se Matteo sceglie nomi diversi.

Controllare che i file installati corrispondano all'archivio. Le differenze di UID e GID sono normali nel passaggio da archivio Windows a server Linux; qualsiasi altra differenza deve bloccare la chiusura del deploy:

```bash
set -e
TAG=v0.1.0-alpha.X-deploy
ARCHIVE=alpha-produzione-${TAG}.tar
EXPECTED_SOURCE_COMMIT=HASH_COMPLETO_COMMIT_APP

cd /srv/certi_nt/app
test "$(tr -d '\r\n' < SOURCE_COMMIT)" = "$EXPECTED_SOURCE_COMMIT"
test ! -e backend/tmp
test ! -e backend/tmp_eval
test ! -e backend/app/modules/supplier_lab
test ! -e frontend/src/pages/supplierLab
! grep -R -E 'SUPPLIER_LAB_ENABLED|GENERAL_SUPPLIER_RUNTIME_ENABLED' \
  backend/app frontend/src docker-compose.alpha.yml

content_differences=$(
  tar --compare \
    --file="/srv/certi_nt/backup/$ARCHIVE" \
    --directory=/srv/certi_nt/app 2>&1 |
  grep -Ev ': (Uid|Gid) differs$' || true
)
if [ -n "$content_differences" ]; then
  printf '%s\n' "$content_differences"
  exit 1
fi
```

Controllare insieme versione backend e versione realmente incorporata nel bundle frontend servito da Nginx:

```bash
cd /srv/certi_nt/app
BACKEND_VERSION=$(
  docker compose --env-file .env -f docker-compose.alpha.yml exec -T backend \
    python -c "from app.main import app; print(app.version)"
)
FRONTEND_VERSION=$(
  docker compose --env-file .env -f docker-compose.alpha.yml exec -T frontend \
    grep -Roh 'Versione sistema 0.1.0.alpha.[0-9.]*' /usr/share/nginx/html |
    sed 's/^Versione sistema //' |
    sort -u
)

printf 'Backend: %s\nFrontend: %s\n' "$BACKEND_VERSION" "$FRONTEND_VERSION"
test "$BACKEND_VERSION" = "$FRONTEND_VERSION"
```

Entrambi devono riportare la versione appena installata, per esempio:

```text
Backend: 0.1.0.alpha.9.5
Frontend: 0.1.0.alpha.9.5
```

### Controlli HTTP pubblici

Dal PC locale, se la rete/VPN lo consente:

```powershell
C:\Windows\System32\curl.exe -I -s http://certi-test.forgialluminio.it/
C:\Windows\System32\curl.exe -I -s http://certi-test.forgialluminio.it/api/auth/me
```

Interpretazione:

- `/` deve rispondere `200 OK`: frontend pubblico raggiungibile;
- `/api/auth/me` con `HEAD` puo rispondere `405 Method Not Allowed` con `allow: GET`: e comunque utile, perche dimostra che la richiesta arriva al backend attraverso Nginx;
- non usare `/api/docs` come controllo: puo rispondere `404` perche la documentazione FastAPI non e esposta sotto `/api/docs`;
- non usare `/docs` come prova backend pubblica: puo essere servito dal frontend, quindi non dimostra che il proxy API funzioni.

Da browser:

- login;
- pagina `Carica documenti`;
- pagina `Incoming materiale`;
- pagina `Certificazione`;
- pagina `Registro certificazione`;
- pagina `Connettori eSolver/Quarta`, se serve verificare i collegamenti.

## Rollback codice

Usare se il nuovo codice non parte o rompe l'app, ma il database non e stato modificato.

Sul server:

```bash
set -e
BACKUP=app_before_v0.1.0-alpha.X-deploy_YYYYMMDD_HHMMSS.tgz
TS=$(date +%Y%m%d_%H%M%S)

cd /srv/certi_nt
docker compose --env-file app/.env -f app/docker-compose.alpha.yml stop backend frontend

mv app "app_failed_${TS}"
tar -xzf "backup/$BACKUP" -C .

cd app
docker compose --env-file .env -f docker-compose.alpha.yml up -d --build
docker compose --env-file .env -f docker-compose.alpha.yml ps
```

Il rollback codice non tocca `/srv/certi_nt/data`.

## Rollback database

Da usare solo se abbiamo cambiato struttura dati o se il database e stato alterato in modo sbagliato.

Regola pratica:

- prima si ferma l'app;
- si conserva una copia dello stato rotto;
- si ripristina il dump SQL fatto prima dell'aggiornamento;
- si riavvia l'app con il codice coerente con quel database.

Esempio operativo da adattare con attenzione:

```bash
cd /srv/certi_nt/app
docker compose --env-file .env -f docker-compose.alpha.yml stop backend frontend

docker compose --env-file .env -f docker-compose.alpha.yml exec -T postgres \
  sh -lc 'dropdb -U "$POSTGRES_USER" "$POSTGRES_DB" && createdb -U "$POSTGRES_USER" "$POSTGRES_DB"'

docker compose --env-file .env -f docker-compose.alpha.yml exec -T postgres \
  sh -lc 'psql -U "$POSTGRES_USER" "$POSTGRES_DB"' \
  < /srv/certi_nt/backup/db_before_alpha_YYYYMMDD_HHMMSS.sql

docker compose --env-file .env -f docker-compose.alpha.yml up -d backend frontend
```

Questo punto va fatto solo quando necessario e con backup verificato.

## Caso colonne nuove nel DB

### Gemba: riferimento caricamento (30/09/2026, sviluppato in locale)

Il bootstrap aggiunge `datimaterialeincoming.incoming_loaded_at` e il relativo
indice. Valorizza soltanto i riferimenti mancanti: upload DDT, altrimenti upload
certificato, altrimenti creazione riga. Non copiare valori dal DB locale.
Fare il backup DB Alpha prima di avviare questa versione. Dopo l'avvio verificare
presenza colonna, nessun riferimento mancante e filtro Gemba con ore italiane.
Controllare una riga solo certificato e una abbinata: una sola data `Caricato`
nello spazio esistente. Non richiede riletture AI o ricalcoli dei match.
Preservare colonna e dati nel rollback del solo codice. Piano e test:
`docs/tasks/gemba_upload_time_filter.md`. Questo aggiornamento del Markdown
non autorizza il deploy, che resta da eseguire soltanto su richiesta.

Oggi l'alpha non ha ancora una gestione migrazioni completa tipo Alembic.

Quindi, se una nuova versione introduce colonne o tabelle:

1. va capito prima quali modifiche DB servono;
2. va fatto dump DB;
3. va preparata una piccola migrazione SQL o una procedura controllata;
4. va testato che il backend parta con il DB esistente;
5. solo dopo si fa aggiornamento server.

Il rischio e questo: il codice nuovo parte aspettandosi una colonna che nel DB server non esiste ancora.

## Cose da non fare

Non fare:

- preparare `alpha-produzione` copiando soltanto i file dell'ultimo commit;
- copiare nel deploy la working tree locale invece del contenuto di un commit Git;
- creare o pubblicare il tag prima del confronto integrale tra app e deploy;
- accettare file deploy aggiuntivi diversi da `README_ALPHA.md` e `SOURCE_COMMIT`;
- creare un pacchetto Alpha dal futuro branch `feature/supplier-lab` o da qualsiasi branch diverso da `main`;
- unire o installare il modulo Lab prima dell'audit conclusivo e del nuovo `procedi` esplicito;
- rimuovere i controlli temporanei di esclusione Lab senza autorizzazione;
- includere `backend/tmp`, `backend/tmp_eval`, `.env`, storage, cache, `node_modules` o `dist` nell'archivio;
- verificare soltanto `app.version` senza controllare anche il bundle frontend servito;
- cancellare `/srv/certi_nt/data`;
- cancellare `/srv/certi_nt/data/postgres`;
- cancellare `/srv/certi_nt/data/storage`;
- sovrascrivere `.env`;
- aggiungere il mapping PostgreSQL soltanto al compose presente sul server;
- esporre PostgreSQL su `0.0.0.0`;
- concludere il deploy senza verificare `docker port app-postgres-1 5432/tcp`;
- usare `docker compose down -v`;
- pulire database o documenti senza decisione esplicita;
- aggiornare mentre un caricamento AI lungo e in corso.

## Aggiornamento pulito completo

Da usare solo quando deciso esplicitamente.

In quel caso si puo:

- salvare dump DB;
- salvare storage;
- pulire dati applicativi caricati;
- mantenere hardcoded, standard, fornitori base e configurazioni necessarie;
- riavviare una alpha pulita per test.

Questo non e l'aggiornamento soft.
