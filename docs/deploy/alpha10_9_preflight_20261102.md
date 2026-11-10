# Alpha 10.9 — DDT multipagina e ripartenze, 02/11/2026

## Stato: COMPLETATO — installata, riaperta e primo timer naturale verificato

Deploy richiesto esplicitamente dall'utente. Sorgente
`7485ff6e2480cfb21a0d7cdf5e1388a79d51eac1`, pacchetto
`b628288764dbd1beed39d1655b5f6df2745bfd37`, tag immutabile pubblicato
`v0.1.0-alpha.10.9-deploy`. Versione applicativa mantenuta `0.1.0.alpha.10`.

471 file sorgenti confrontati integralmente; solo README_ALPHA/SOURCE_COMMIT
aggiuntivi. Archivio12.933.120 byte, SHA256
`6189ef614fed2785a45d2bdaac07d3bab425647e61a55bafd370a4e6929f40a2`.
Niente temporanei, documenti cliente, segreti o Lab.

Cinque moduli backend nuovi/modificati. Nessuna migrazione, bonifica storica,
invalidazione cache, importazione locale, rigenerazione Word/PDF o test AI
operativo. I DDT401/righe290/295/296 corretti dall'utente restano invariati.
Nuove letture/evidenze si applicano soltanto al normale lavoro futuro.

## Preflight e candidata

Server verificato su `f74c2938`, Alpha10.8, 282 file runtime/configurazione
identici al commit installato. PostgreSQL healthy, mapping10.10.1.10:5432,
entrambi i flag snapshot/riuso Word true. Nessuna attività utenti negli ultimi
tre minuti, nessun run AI/upload/sessione DB attiva o conversione rilevata.
227 letture AI salvate e13 registrazioni consumo preesistenti, NON azzerate.

Spazio misurato prima: root24,63 GB totali,15,94 occupati,7,41 disponibili;
disco dati/backup105,09 GB totali,19,42 occupati,80,28 disponibili. Dati e backup
sono due mount dello stesso filesystem: non sommarli due volte. Backup esistenti
15,94 GB, storage2,31 GB, app12,38 MB, database logico111,45 MB (directory420,37 MB).
Preventivo: circa2,4 GB nuovi backup sul disco dati, meno di0,5 GB root per
pacchetto/candidata più margine. Nessuna pulizia necessaria o autorizzata.

Runtime esatto10.8 riutilizzato senza rete/pull/apt/pip:
base `sha256:60578cf31a617e2dd766b2f48abd6a58ff8a26288e88603b67ee048b7f37c6d3`,
candidata `sha256:8ade477031aeca276206d783d7718f35c5ce4d8f449ce01681a0608505582169`.
Layer preesistenti e Config immutati, directory app/scripts sostituite
integralmente nella sola candidata e confrontate con il pacchetto.
Frontend, requisiti, Dockerfile e compose invariati.

**207 test candidati server superati**,27 PostgreSQL opt-in saltati qui e già
superati separatamente in sviluppo sullo stesso sorgente. Suite generale locale
ripetuta prima del commit:839 superati/165 altri opt-in saltati, zero errori.
Le prove AI reali Metalba autorizzate sono nel suo verbale; questa manutenzione
non autorizza nuove chiamate AI. I nuovi prompt degli altri tre fornitori sono
collaudati con risposte simulate, non un nuovo test AI pagato.

## Manutenzione e backup

Unico TS `20261102_194500`. Backup server privato
`/srv/certi_nt/backup/alpha_deploy_20261102_194500`; copia esterna privata PC
`backups/alpha_deploy_20261102_194500`, ACL riservata. Nessuna cancellazione PC
implicita: conservare archivi/restore e immagini fino a nuova scelta dell'utente.

Tre nuovi controlli immediatamente prima del fermo di assenza utenti/AI/upload/
sessioni DB/conversioni. Fermati soltanto backend/frontend Alpha. PostgreSQL,
dati e l'altro stack restano intatti. Backup app/configurazione, dump logico e
storage, hash e contenuto; poi restore su PostgreSQL e filesystem isolati sul PC.
Prima dell'installazione servono confronto di tutte le tabelle, export e file,
collaudo del clone con AI vietata e nuova verifica della baseline congelata.

Backup reali verificati: app7.298.129 byte, database20.007.661 byte,
storage2.083.465.559 byte; copia PC con SHA256 identici e lettura completa.
Restore isolato riuscito:46 tabelle, vista export,467 file app e4.526 file
storage identici alla baseline congelata. Clone candidato in sola lettura:
227 cache riutilizzabili, sette manuali protetti, forme lega Metalba conservate,
13 record consumo storici intatti e nessuna chiamata AI aggiunta. Tutte le tabelle
del clone invariate dopo la prova.

Installazione completa del codice, `.env` preservato byte per byte, nessuna
preparazione schema/dati. Prima di riaprire: tutte le46 tabelle, export e4.526
file storage ancora identici; nessuna rigenerazione o recupero storico.
Riapertura con immagini già costruite, senza build/pull: PostgreSQL (ID/mount/
mapping) e l'altro stack invariati, entrambi i flag ordinari true.
Cinque moduli realmente in esecuzione confrontati con i byte del pacchetto.

Postcheck129 secondi dopo: quattro HTTP200 (frontend/API interni e pubblici),
backend e bundle `0.1.0.alpha.10`,227 cache valide e sette manuali protetti;
13 record consumo, nessun run AI attivo, nessun nuovo errore nei log.
**Zero delta nelle46 tabelle, file ed export identici.** Ruolo effettivo
`certi_esolver_reader` preservato con solo SELECT sulla vista e senza privilegi
amministrativi. Spazio: root7.398.162.432 byte disponibili, dati78.144.598.016.

Nel primo tentativo del solo script di postcheck una vecchia asserzione contava
solo `legacy_evidence`:219 letture storiche, non le otto nuove con fonte `ai` già
presenti prima del deploy. Diagnosi read-only:227/227 persistite riusabili, zero
inutilizzabili,13 consumi invariati. Corretto SOLO lo script privato di verifica
per contare ogni cache persistita valida; nessun codice operativo, cache o dato
modificato e nessuna rilettura. Il postcheck completo ripetuto è quello sopra.
Un certificato `needs_read_or_review` resta distinto dalla cache: non forzarne
la lettura né trattarlo automaticamente come regressione.

Riapertura circa19:58:47 italiane. Primo ciclo naturale successivo verificato,
senza chiamate manuali: **DDT2968 success alle20:13:50–51**,599 righe sorgente,
zero inserimenti; **Quarta10535 ok alle20:13:51–20:14:20**,16.110 OL e25.380
riferimenti CDQ. Entrambi successivi al riavvio e all'intervallo di15 minuti.
Durata Quarta28,55 secondi, precedente predeploy28,51: rimane il rallentamento
sincrono già documentato, non introdotto né corretto in questo deploy.

Postcheck finale963 secondi dopo la riapertura: quattro HTTP200, versioni/flag
coerenti,227 cache persistite riusabili, sette manuali protetti, consumi sempre13,
nessun run AI attivo o errore applicativo nei log. File storage ed export
identici, dati Incoming/match/certificati/standard/documenti protetti invariati.
Differenze DB limitate alle cinque normali tabelle di sincronizzazione:
`quarta_taglio_ddt_sync_runs`, `quarta_taglio_ddt_work_items`,
`quarta_taglio_esolver_links`, `quarta_taglio_rows`, `quarta_taglio_sync_runs`.
Non è una whitelist generale: tutti gli altri confronti sono rimasti identici.
Spazio finale: root7.398.060.032 byte disponibili, dati78.144.593.920.
Accesso pubblico dal PC200 e mapping effettivo PostgreSQL10.10.1.10:5432
confermati. Nessun recupero, pulizia server, preparazione DB o nuovo costo AI.

In caso di errore conservare lo stato e diagnosticare: nessun ripristino DB
automatico o cancellazione del lavoro successivo. Backup, restore PC e immagini
rollback restano conservati; non estendere vecchie autorizzazioni di pulizia.

Verbali privati JSON raccolti su PC e server, inclusa la prova del timer.
PostgreSQL QA locale `certi-alpha-qa-pg-20261102-194500`, ID verificato
`2ab19df705e700c80ef7387ba4a54e8fda03ca60eb75ad88e6faaa57f7b68b28`,
senza rete né volumi persistenti, rimosso dopo i controlli: solo dati usa-e-getta,
ricreabili dal backup. I quattro container applicativi locali lasciati intatti.
Archivi e `restore_check` PC conservati, nessuna pulizia dei backup autorizzata.
