# Preflight Alpha 10.1 — 09/10/2026

Deploy richiesto dall'utente; autorizzata la pulizia dei soli 17 ID della
sezione spazio del piano, previo controllo delle attività. Questo verbale
registra attività effettive, non dichiara il deploy completato.

## Stato prima del fermo

- Sorgente prevista: `b91c0b0973bbae3d4095c947bb91b822dbc434e0`.
- Alpha ancora `3951822fa3790bd7e1b1b6ced33d384a2fb5edd1`.
- Nessun run AI in coda/esecuzione, nessuna transazione attiva al secondo
  controllo, nessuna build attiva. Nel backend il solo processo uvicorn;
  nessun processo di conversione rilevato. I log recenti mostravano soltanto
  il controllo `/docs` dell'audit. Ripetere i controlli prima del fermo:
  non dimostrano assenza futura di attività o di browser aperti.
- 179 record certificato, 170 riferimenti Word, 19 PDF e 19 righe export.
  697 quote DDT, 464 presenti nella sorgente. OL1232 ancora senza quote DDT;
  record 174 invariato rispetto all'audit precedente, non corretto.
- Spazio disponibile prima della pulizia: 1.973.899.264 byte.
- Stima in streaming senza file sul server: backup storage 1.327.366.023
  byte; dump SQL 14.717.100 byte. Prima delle scritture serviranno backup
  nuovi e coerenti a writer fermi, non queste misure.

## Tentativo di pulizia limitata autorizzata

Verificati tutti i 17 ID: immutabili, recuperabili, non condivisi, con
descrizione e ultimo uso di mesi prima. La selezione ancorata degli ID
restituiva esattamente i 17 elementi autorizzati. Eseguito soltanto
`docker buildx prune --force --verbose --filter 'id~=^(ID1|...|ID17)$'`,
con la lista esplicita già presente nel piano principale.

Esito: **0 byte recuperati, nessun record rimosso**. Immagini e container
confrontati prima/dopo e invariati. Nessun fermo, modifica di codice,
schema/dati, documenti o configurazione Alpha.

L'inventario delle relazioni mostra quattro discendenti fuori dall'elenco
autorizzato che mantengono riferimenti alle vecchie catene:

| ID aggiuntivo | Contenuto descritto da Docker | Dimensione |
| --- | --- | --- |
| `co7moylyqlco93gohnxstvyx2` | vecchia base Python | 16,63 kB |
| `p607evkxr0pulksxs5iirdrtq` | vecchia base Python | 16,63 kB |
| `jc4oyyg6vh3c7ssni12sz9uvy` | COPY package.json e package-lock.json | 106,5 kB |
| `szznlasfz13694uj9ha3dwz4q` | COPY requirements.txt | 12,68 kB |

Creati a giugno/luglio, ultimo uso riportato sette giorni prima; tutti
immutabili, recuperabili e non condivisi. Chiusura completa delle dipendenze:
21 ID, nessun ulteriore discendente nell'inventario. La relazione spiega
perché la lista iniziale non basta; non garantisce quanti byte una nuova
pulizia libererebbe. Nessun nuovo tentativo prima di OK sui quattro ID.

## Estensione autorizzata e pulizia completata

Dopo spiegazioni e ulteriori verifiche, l'utente ha autorizzato tutti i 21
elementi. Nuovo controllo: zero run AI/transazioni attive, nessuna conversione
o build in corso; tutti i record ancora privati, immutabili e recuperabili.
Nessuna dipendenza esterna al gruppo. La pulizia con filtro sui 21 ID esatti
ha rimosso solo quei record: 1,428 GB dichiarati da Docker; spazio disponibile
passato da 1.973.858.304 a 3.401.818.112 byte. Immagini e container invariati.
HTTP frontend/backend 200; LibreOffice, OCR e Python presenti nel backend.
Cache ricreabile; non sono stati disinstallati programmi dell'app.

## Pacchetto e backup eseguiti

- Repo deploy commit `b6b9e44`, tag `v0.1.0-alpha.10.1-deploy`, entrambi pubblicati.
- Confronto integrale: 422 file identici al commit app, solo README_ALPHA.md e
  SOURCE_COMMIT aggiuntivi. Frontend del pacchetto compilato; bundle alpha.10.
- Archivio trasferito: SHA256
  `dbd0f8b92a77b15282ce9fae4167f27dc5d403a04bfdc127ec264cfc515f55bf`.
- Riferimento unico manutenzione: **20261009_173254**, orario server UTC.
- Prima del fermo rilevato un ciclo Quarta, poi concluso; nuovo controllo
  senza attività. Fermati soltanto frontend/backend Alpha. PostgreSQL e altro
  stack rimangono attivi. Immagini correnti conservate anche con tag
  `before-alpha10_1-20261009`, oltre ai tag storici.
- Creati sotto `/srv/certi_nt/backup`: app/configurazione, dump DB, storage,
  manifest SHA256 e impronte di tutti i file storage. Archivi gzip/tar leggibili,
  dump completo e controlli SHA256 tutti OK. Nessuna modifica codice/schema/dati.
- Copia del dump nella cartella locale `tmp_eval` esclusa da Git; SHA256 identico
  al server: `fa78778d1bd363c048ffe10119ee2cdf8dcec09028c35f032ef7019d51274e6e`.
  Non è una copia nel database applicativo locale, né è stata pubblicata.

## Punto di ripresa: consenso per prova di ripristino

Il controllo di sicurezza ha bloccato copia/import del dump nel container
temporaneo locale, chiedendo consenso specifico per l'uso della copia completa
dei dati Alpha. Non aggirare il blocco: la prova NON è stata eseguita.
Container `certi-alpha-restore-20261009`, senza rete e senza volumi applicativi,
database `certi_restore_test`: verificato vuoto (zero tabelle public).

**Alpha è in manutenzione, frontend/backend fermi.** Codice ancora `3951822f`,
database operativo non modificato, mapping `10.10.1.10:5432` invariato.
Prima di scritture critiche serve consenso esplicito alla prova locale di
ripristino prevista dal piano, oppure nuova decisione concordata. Dopo prova
riuscita: sostituzione/build, preparazioni additive, preview archivio e nuovo
OK, poi nuova preview Word e OK separato. Non riutilizzare vecchi report.
OL1232 non corretto; riuso automatico Word da lasciare disattivato.

## Ripristino autorizzato e nuovo arresto per spazio

L'utente ha autorizzato esplicitamente la prova locale. Dump ripristinato
con `ON_ERROR_STOP=1` nel solo container isolato: confronto esatto di conteggi
e impronte delle 43 tabelle public e della vista export con Alpha riuscito.
Nessun record del database applicativo locale è stato sostituito.

Installato il pacchetto verificato, preservando l'impronta `.env`; backup
ricontrollati prima della sostituzione del solo codice. App ancora ferma.
Build frontend/backend terminata con successo, ma il riferimento mobile
`python:3.11-slim` ha risolto una base nuova e ricostruito tutte le dipendenze:
Python base digest `e88e9763f943ec1834f992a4b51e0f24500486803e8bc534e5767af9ea65f6ce`.
Nuove immagini: backend `687d485dab83`, frontend `7ff16038f118`.
Le immagini precedenti e di rollback restano presenti.

Spazio libero sceso a **80.236.544 byte** (circa 77 MiB): fermarsi, niente
migrazioni, test pesanti o riapertura con questo margine. Schema e dati Alpha
ancora invariati. Prima di usarla occorre anche collaudare la nuova immagine:
alcune dipendenze transitive non sono bloccate dal requirements e sono state
risolte nuovamente; i test della vecchia immagine locale non bastano.

Nuova proposta, NON ancora autorizzata/eseguita: sola vecchia catena cache
backend del 01/10, circa 1,044 GB, 10 record privati/immutabili/recuperabili,
senza discendenti esterni nell'inventario. Non sono le immagini di rollback.

```text
uciduwuvjd9382mn6plkvett9
kuv5tmwo3b4i0di3libliusf8
qfbn0rppk76akbjmwi1c72ije
ga77bez1jbb78bj04blsajrhy
ll3qk40ehsjvsvlxbdy7nas4q
4uerk2j8mn51cvy09jdxpafpp
i1f281z4d1rm92khqzhgqjfo7
v61p2njsvhxutv8s1hv5uy2vf
tmltv47wd14kzpb79fcrb7n4v
i17qvdkfq1qsqsmbas5oly4yj
```

Richiedere nuovo OK; non estendere automaticamente la pulizia precedente.
Al prossimo passo ricontrollare spazio, attività e dipendenze. Database,
documenti, backup e immagini non rientrano nella proposta. Sorgente installata
`b91c0b09`; non riaprire il backend senza le preparazioni schema obbligatorie.

## Seconda pulizia autorizzata e collaudo nuova immagine

L'utente ha autorizzato i dieci ID sopra. Ripetuti inventario, verifica delle
dipendenze e confronto immagini/container: rimossi esattamente i dieci record,
senza toccare immagini, documenti, DB o backup. Docker dichiara 1,044 GB;
lo spazio effettivamente disponibile è 813.592.576 byte (circa 776 MiB).
Il guadagno fisico è inferiore perché alcuni contenuti restano referenziati
dalle immagini conservate. Margine limitato: ricontrollare prima delle
scritture e della riapertura; nessuna ulteriore pulizia autorizzata.

Conversione reale di un DOCX fittizio in PDF con LibreOffice della NUOVA
immagine riuscita; verificati testo e pagina con PyMuPDF. Prova password
hash/verifica riuscita. Contenitore isolato senza rete o dati Alpha.

Prima suite: un test con eseguibile fittizio temporaneo bloccato dal mount
`/tmp` non eseguibile del contenitore di collaudo. Ripetuta con `exec` nel
SOLO contenitore di test: 618 superati, 61 PostgreSQL saltati, 8 warning.
Nessuna modifica al codice per risolvere il problema del collaudo.
Avviata successivamente la suite completa con PostgreSQL temporaneo vuoto,
senza rete esterna e con dati soltanto in tmpfs; esito da registrare sotto.

Prima delle preparazioni, ricontrollati conteggi e impronte di tutte le 43
tabelle e della vista export: ancora identici al backup ripristinato.

## Collaudo completo e preparazioni database riuscite

- Nuova immagine sul server, con PostgreSQL temporaneo isolato: **679 test
  superati, zero saltati**, 8 warning di deprecazione, 118,60 secondi.
  Container di prova server terminati; nessun dato reale usato nei test.
- Ultimo controllo prima delle scritture: zero run AI e zero altre transazioni
  attive; unico standard 7003 ID19 T62 BARRE, 179 certificati, 170 riferimenti
  Word, 19 PDF finali, 19 righe export.
- `prepare_word_standard`: esito committed, colonna aggiunta, 170 baseline
  legacy. Aggiunta anche `elongation_basis`; vecchi standard con valore NULL.
  Confronto di tutti i campi preesistenti delle 43 tabelle e dell'export con
  backup ripristinato: identici, comprese date di modifica e selezioni.
- Preview 7003 coerente con quanto approvato; applicazione committed:
  **ID39 A minimo 10%, ID40 A50mm minimo 8%**, entrambi T6 BARRE attivi.
  Verificati i sei limiti meccanici per standard e i 15 elementi chimici
  identici a ID19. Nuova preview: entrambi `existing_unchanged`.
- Tabella `quarta_taglio_ddt_archive_events` creata, ancora **zero eventi**.
  Nessuna quota archiviata, nessun Word recuperato/generato.
- Dopo tutte queste aggiunte: confronto completo dei dati preesistenti con
  backup ancora identico, escludendo solo colonne nuove e righe dei due nuovi
  standard. Tutte le impronte dei file storage originali e `.env` invariate.
  Spazio residuo 812.679.168 byte, circa 775 MiB; margine ancora limitato.

## Punto di arresto: OK sul nuovo report archiviazione Alpha

Report privato server: `/srv/certi_nt/backup/ddt_archive_20261009_173254.json`,
generato **09/10/2026 17:49:51 UTC**, cutoff **01/10/2026**.
Piano: `17e30bd89554bc9aa18ec5f6b32769809c914b9981abc1ca392e8009e244a201`.
File creato da root nel contenitore; protetto con modo 600 nel medesimo
contenitore. Il tentativo di chmod dall'utente SSH non aveva permessi:
errore solo del passo protezione file, non della preview già riuscita.
Leggere il report con mount read-only nel contenitore, non allargare permessi.

- Totale **697 quote / 258 DDT**.
- Archiviabili **534 quote / 199 DDT**, tutte anteriori al 01/10 e senza
  protezioni di lavoro avviato. Nessun documento suddiviso tra archivio e keep.
  Stato attuale: 492 in attesa Incoming, 42 da collegare.
- Mantenute **163 quote / 59 DDT**: previsione pagina **144 attive, 18
  completate, 1 esclusa**. Le attive: 97 in attesa Incoming, 20 da collegare,
  24 pronte Incoming, 2 Word pronti, 1 da verificare.
- Conservate tutte le righe con certificati, lavoro parziale, candidati
  Incoming, selezioni o decisioni e i documenti recenti. Verificate le quattro
  quote dei casi OL997/998, tutte mantenute; OL1232 senza quote, non modificato.
- Questi conteggi della coda non coincidono necessariamente con le 19 righe
  export/19 PDF chiusi: sono conteggi di quote collegate, non di certificati.

**Richiedere OK esplicito sui 534 elementi prima di `archive_ddt --apply`.**
Non si cancella nulla: archiviazione reversibile tramite eventi, dati e
documenti conservati. Il report scade dopo un'ora: se trascorsa, nuova preview
con nuovo nome e nuova verifica, senza modificare il report precedente.

Poi verificare zero nuove archiviazioni proposte, eseguire NUOVA preview Word
e chiedere OK separato prima del recupero. App frontend/backend ancora fermi;
PostgreSQL e altro stack attivi. Deploy NON concluso. Riuso automatico Word
resta disattivato per OL1232; raccolta snapshot da preservare come autorizzata.

## Archiviazione approvata, applicata e verificata

L'utente ha risposto «sì» alla proposta delle **534 quote / 199 DDT**.
Ricontrollati manutenzione, zero run/altre transazioni attive, spazio e hash
backup/configurazione. Report ancora valido; applicazione con lock e
rivalidazione completa: **committed, archived 534**.

Nuovo report `ddt_archive_after_20261009_173254.json`: 534 già archiviate,
163 mantenute, **zero nuove archiviazioni**. Verificati nel DB tutti i 534
ID esatti e relativo batch; nella proiezione reale della pagina: 144 attive,
18 completate, 1 esclusa, 534 archiviate. Nessun DELETE.

Confronto di tutte le righe/campi preesistenti con backup ripristinato ancora
identico (escluse soltanto le aggiunte approvate); tutti i file originali,
configurazione e 19 righe export invariati. Spazio libero 811.528.192 byte.

## Nuovo punto di arresto: approvazione recupero Word

Preview prodotta DOPO l'archiviazione, in sola lettura DB/storage, senza
eSolver o bootstrap. Report privato root 600:
`/srv/certi_nt/backup/word_ddt_preview_20261009_173254.json`.
Generato **09/10/2026 17:54:54 UTC**, piano
`c2f7feae8735462afea2f31e1041ac4eccdcac6d1468f501b3b8b1ccc2829c3f`.

- **23 quote su 14 DDT / 18 OL** recuperabili: 9 record destinazione esistenti
  privi di Word/PDF e 14 nuovi record. Le fonti Word restano intatte; si copiano
  con i dati della singola quota, senza rigenerare contenuti tecnici o PDF.
- Esaminati tutti i 23 casi: stessa identità OL/F3, numero della fonte coerente,
  hash Word invariato, ramo RAW/FINISHED univoco e dati DDT/data corretti.
  Nessuna destinazione ha Word/PDF e nessuna quota archiviata è coinvolta.
- OL997 quota652 / DDT2397: riuso fonte16 (DDT2354, PDF chiuso) nella riga148.
  OL998 quota635 / DDT2386: nuovo record dalla fonte17 (DDT2229, PDF chiuso).
  Nessuna modifica alle fonti o ai PDF già chiusi.
- 20 quote con documenti esistenti preservate; 534 archiviate saltate;
  97 senza Word preparato, 20 senza OL e 1 con decisione manuale non recuperate.
- Altre due quote restano fuori dal recupero: quota660, OL1012/DDT2410
  (`incoming_not_ready`); quota684, OL977/DDT2436 (`no_compatible_word`).
  Non forzare associazioni né modificare il report per includerle.
- OL1232 non compare nel report; fonte174 non coinvolta. Il problema noto
  rimane non risolto, riuso automatico globale ancora da lasciare false.

**Recupero Word NON applicato: chiedere OK esplicito sui 23 casi.**
Il report scade dopo un'ora; se scaduto o dati cambiati, rifare preview e
verifica. Dopo eventuale apply: verificare file/DB/export, nuova preview
senza ulteriori recuperi, poi riaprire e verificare app/job secondo piano.
Frontend/backend Alpha ancora fermi; deploy NON concluso.

## Recupero Word approvato, completato e riapertura

L'utente ha approvato i 23 recuperi dopo chiarimento sul significato. Applicato
il report ancora valido sotto lock: **committed, 23 modifiche**, 9 righe
esistenti aggiornate e 14 nuove (ID180-193). Conteggi: 193 certificati con Word,
19 PDF finali. Nessun PDF generato/riaperto e nessun originale sovrascritto.

Verificati tutti i 23 nuovi file: controlli DDT/data/quantità coincidenti con
il report; contenuto tecnico DOCX (esclusi i soli campi spedizione) identico
alla fonte, numero e provenienza conservati. Nuova preview propone zero riusi,
43 quote con documento esistente preservato. Tutti i file originali e i dati
protetti/export confrontati con il backup sono invariati.
OL997 quota652 → certificato148 e OL998 quota635 → certificato185 ora sono
`word_ready` con `pdf_action`; vecchie quote393/213 ancora completate.

Riaperti backend/frontend dalle immagini collaudate senza build, PostgreSQL
non ricreato. Health locale e pubblico OK, versione backend/bundle alpha.10,
mapping DB 10.10.1.10:5432, coda non autenticata risponde401. All'avvio flag
snapshot=true, reuse=false secondo il piano allora vigente.
Ciclo raccolta eSolver controllato riuscito: 464 righe lette/aggiornate,
zero inserimenti, riconciliazioni e scomparse. È una chiamata esplicita della
stessa funzione del job, non prova dell'attesa del timer di15 minuti.

Browser integrato fallito all'avvio due volte; fallback Playwright documentato:
coda reale caricata, pulsanti PDF/requisiti presenti, dialog OL997 mostra
DDT2397 e nome7013_00_00_26.pdf, annullato senza generazione. Prova successiva
fermata da selettore test `Vista` troppo restrittivo; non prova di errore app.
Controlli visivi archivio/altre pagine ancora da completare.

## Decisione successiva: rimuovere il fermo globale del riuso

Dopo chiarimento, l'utente ha esplicitamente richiesto di attivare il riuso
anche per OL1232: avviserà il cliente che correggerà manualmente. Nessun
blocco speciale da introdurre per quell'OL e nessuna correzione automatica
del documento. Questa decisione revoca le precedenti prescrizioni `false`
di questo verbale; aggiornato anche il piano principale.

Audit sorgente effettuato in sola lettura e verificato visivamente sul PDF
Metalba26-1974 del28/07/2026, colata26120B, Incoming93, documento102:
**lega7075, fornituraF, prove meccanicheT62**, diametro26mm.
Rm641MPa, Rp598MPa, A8,5%, HB171; Cu1,4790%, Mg2,3408%, Zn5,6901%.
Il Word7033_01_00/26 del solo OL1232 mantiene7150T76: incoerente con la fonte;
resta all'operatore correggerlo. Nessun dato/certificato modificato dall'audit.

Attivazione NON ancora eseguita: la guardia rileva attività da pagine utenti
(letture e refresh Quarta/Registro), perciò si ferma PRIMA di scrivere `.env`.
Chiesta breve chiusura delle schede Alpha per non interrompere lavoro.
Script pronto `tmp_eval/alpha_enable_word_reuse_20261009.py`: verifica attività,
backup privato `.env`, modifica del solo DDT_WORD_REUSE_ENABLED, ricreazione
solo backend e health. Non rimuovere la guardia né interrompere le attività.
App online; in attesa finestra libera il flag effettivo resta false.

## Attivazione autorizzata completata e controlli conclusivi

Silvano ha confermato di sospendere l'uso delle pagine. Attese le attività
in corso; corretto il solo comando diagnostico `docker top` affinché includa
la colonna PID richiesta da Docker. I tentativi precedenti si erano fermati
prima di modificare la configurazione.

Salvato backup privato `/srv/certi_nt/backup/env_before_word_reuse_20261009.env`;
modificato **solo `DDT_WORD_REUSE_ENABLED=true`**, ricreato soltanto backend,
health OK. Verificato nell'ambiente realmente caricato: **snapshot=true,
reuse=true**. Nessuna esclusione speciale per OL1232; restano le normali
protezioni del software. Dati, standard e Word di OL1232 non modificati.

Ciclo controllato `sync_ddt_words`: prepared0, review_or_waiting100, errors0.
Nessuna duplicazione dei 23 file appena recuperati. Il conteggio100 comprende
le normali quote senza Word/OL o non idonee, non100 errori. Il job resta
programmato ogni15 minuti; il ciclo controllato non prova ancora un successivo
avvio per timer dopo questa ultima ricreazione.

Confronto finale: **424 file del pacchetto identici**, compresi i due metadati
deploy; nell'ambiente è cambiato esclusivamente il flag autorizzato. Backend
e frontend alpha.10, API pubblica health OK, export19 PDF e ruolo
`certi_esolver_reader` presenti. Mapping PostgreSQL invariato.

Collaudo browser ripetuto aspettando il contenuto reale delle risposte:
**PASS**, zero errori JavaScript/HTTP e zero scritture. Coda, finestra PDF997
annullata, Esclusi con DDT1812 e motivo«Prova», Archivio con pulsante ripristino,
Standards, Reparti e Incoming verificati. Screenshot privati in `tmp_eval`.

**Deploy applicato e Alpha online.** Recupero Word/archivio/standard completati;
automa Word attivo per richiesta esplicita. Restano la correzione manuale
del Word OL1232 affidata al cliente e il poco spazio disco (circa770MiB,
da monitorare/valutare con IT, senza ulteriori pulizie automatiche).

## Ricontrollo successivo 11/10 e procedura per i prossimi deploy

Audit in sola lettura: servizi attivi senza riavvii anomali, health pubblico OK,
193 Word / 19 PDF finali referenziati presenti, nessun file mancante.
Nelle 40 ore osservate: 152 snapshot DDT riusciti, 154 sincronizzazioni Quarta
riuscite, ultima lettura alle 11:11 italiane. Snapshot e riuso Word entrambi true.
Questo controllo successivo conferma l'esecuzione periodica, oltre ai soli
cicli manuali verificati durante il deploy.

OL1232: dopo il primo tentativo HTTP409 compare una rigenerazione HTTP200;
ID174 aggiornato il 09/10 alle 20:23 italiane, nuova provenienza `generated`
con standard ID21 7075 T62. La correzione non va più presentata come pendente
sulla base della fotografia precedente. Verifica log/metadati; non un nuovo
controllo visivo del documento. Nessuna rigenerazione eseguita dall'audit.

Spazio circa 807 MiB liberi, 97% occupato. Inventario e proposta non eseguita
nel [controllo spazio 11/10](alpha_space_audit_20261011.md). Aggiornato il
[punto di ingresso deploy](alpha_soft_update_server.md): chiedere OK specifico
alla pulizia dei tre pacchetti duplicati prima del prossimo deploy, dopo
rivalidazione. Non ripetere archiviazione, recuperi, creazioni standard o vecchi
script di pulizia già conclusi. Le fasi precedenti del verbale restano come
storico di decisioni, rischi e verifiche, non come istruzioni ancora pendenti.
