# Alpha 10.8 — Arconic/Metalba, 30/10/2026

## Stato: COMPLETATO — installata, riaperta e primo timer naturale verificato

Deploy esplicitamente autorizzato dall'utente dopo la proposta mirata. Nessuna
migrazione, bonifica dati, rilettura AI, pulizia server o modifica dipendenze.

- Sorgente pubblicato: `f74c29384eb10e5b2ac6bd88555768bc938e6040`.
- Deploy: `8ab26e5d6ce5878a08ad9345da3c34fd04a8c3c5`.
- Tag immutabile pubblicato: `v0.1.0-alpha.10.8-deploy`.
- Archivio completo: 12.789.760 byte; SHA256
  `ee7e8e5304199fb2a0c03c64c81c9a13bba4addac5498a9d66896eca6a4ea4f6`.
- 464 file sorgenti confrontati integralmente con il commit; ammessi in piu
  solo `README_ALPHA.md` e `SOURCE_COMMIT`. Nessun segreto, temporaneo o Lab.
- Versione app ancora `0.1.0.alpha.10`, backend/footer coerenti. Frontend,
  Dockerfile, requirements e compose identici ad Alpha 10.7.
- Runtime backend riusato per ID esatto, senza rete, pull o apt/pip:
  base `sha256:b456f5615c5e5c7b9a84844353a9690d313ae2404f77c75b040ecf204f2a395b`;
  candidata `sha256:60578cf31a617e2dd766b2f48abd6a58ff8a26288e88603b67ee048b7f37c6d3`.
  Layer precedenti e configurazione runtime invariati; sostituite interamente
  app/scripts nella sola candidata, tutti i file confrontati col pacchetto.
- Candidata server: 136 test superati offline (28 cache, 32 manuali/rematch,
  18 bridge, 21 Metalba LST03, 16 tipo Leichtmetall, 8 Arconic stesso-run,
  13 recupero identita Arconic). Gli errori API/salvataggio nel log di collaudo
  sono guasti simulati; non sono errori Alpha o chiamate realmente pagate.
- Sviluppo: 830 test superati, inclusi 11 PostgreSQL isolati; 127 altri opt-in
  saltati. Tre ordini di arrivo provati sulle risposte reali gia salvate.

## Controlli prima del fermo

Confermata Alpha 10.7 da `fc1d1f74`: 282 file runtime/frontend/configurazione
identici alla sorgente distribuita. Nessuna elaborazione AI o sessione DB attiva,
nessuna conversione PDF e nessuna richiesta nei tre minuti del primo audit.
Il controllo viene ripetuto immediatamente prima del fermo, non e permanente.

Root disponibile circa 7,40 GB; dati/backup circa 82,51 GB sullo stesso secondo
filesystem. Non sommare due volte data e backup. Previsione: circa 2,1 GB nuovi
backup sul disco dati, meno di 0,5 GB per pacchetto/candidata sulla root, oltre
al margine operativo. Nessuna pulizia necessaria o autorizzata.

Unico TS: `20261030_214500`. Backup server privati
`/srv/certi_nt/backup/alpha_deploy_20261030_214500` e copia esterna PC
`backups/alpha_deploy_20261030_214500`, con ACL riservata. Non copiarli in Git,
web o mail. I backup della precedente 10.7 restano conservati sul server.

La copia PC serve per il restore isolato e come copia esterna. La vecchia
autorizzazione di pulizia 10.7 NON autorizza a eliminare questi nuovi backup:
conservarli salvo nuova scelta esplicita. Non eliminare immagini di rollback.

## Passaggi e criteri di chiusura

1. Tre controlli di assenza writer/upload/AI/richieste/conversioni, quindi fermo
   dei soli backend/frontend Alpha. PostgreSQL e altro stack restano attivi.
2. Snapshot integrale delle tabelle, export e file; backup coerenti app/.env,
   dump logico e storage. Hash e contenuto di tutti i membri verificati anche
   sulla copia PC. Nessun dato operativo cambiato per fare prove.
3. Restore PostgreSQL e documentale isolato sul PC; confronto con la baseline.
   Verifica read-only del codice candidato sul clone reale: riuso cache,
   protezione manuali, tre forme Metalba; nessuna AI o scrittura sulle tabelle.
4. Installazione del pacchetto completo preservando .env, configurazione, dati,
   mapping/grant e immagini rollback. Nessun comando di preparazione schema,
   backfill, recupero Word/DDT, rinumerazione o generazione PDF.
5. Prima della riapertura: tutte le tabelle, file storage ed export identici;
   solo sorgenti applicativi cambiano. Avvio senza build/pull impliciti, con
   `DDT_SNAPSHOT_ENABLED=true` e `DDT_WORD_REUSE_ENABLED=true` preservati.
6. HTTP interno/pubblico, bundle, processi/log, permessi export, dati/file e
   spazio; controllo del timer naturale separato da chiamate manuali. Non
   generare certificati reali come smoke test.

Rollback: immagini e backup della 10.7 disponibili. Nessun ripristino DB
implicito, soprattutto dopo la ripresa del lavoro utenti. Il vecchio codice
ripresenta i due limiti Arconic/Metalba, non annulla i match futuri gia creati.

## Avanzamento manutenzione

Dopo tre controlli positivi e assenza di utenti/AI/upload/conversioni, fermati
solo backend/frontend Alpha. Immagini di rollback marcate e configurazione,
identita/mount/porte PostgreSQL e altro stack registrati prima del fermo.

Backup server letti integralmente e verificati: app 7.280.347 byte, database
19.619.076 byte, storage 2.053.764.742 byte. Nessuna pulizia; root e disco dati
sempre sopra le soglie di sicurezza. Copia esterna/restore ancora in corso:
non considerare questa sezione prova di installazione o riapertura completata.

Ripetuto anche il workflow completo sul pacchetto effettivo con risposte gia
salvate e database QA nuovi: Arconic insieme/certificati-prima/DDT-prima crea
solo le due coppie corrette, senza duplicati alla rivalutazione; Metalba nei
tre ordini conserva la lega e applica LST03 dopo l'abbinamento. Zero API.
Evidenza privata locale:
`tmp_eval/ai_match_trial_20261030/package_10_8_reassessment_20261030_214559_745601.json`.

Copia PC verificata con SHA-256 identici e lettura completa di ogni membro.
Restore PostgreSQL e documentale concluso: **46 tabelle, vista export, 465 file
app e 4.454 file storage identici** alla baseline congelata. Il clone QA non ha
rete o volumi dell'app locale; il DB Alpha non e stato ripristinato/modificato.

## Installazione e riapertura riuscite

Sul clone reale: riuso delle 219 cache persistite, sette documenti manuali
protetti, tre forme Metalba conservate e nessun cambiamento delle 46 tabelle.
Nessuna chiamata AI; il collaudo e rimasto in transazione READ ONLY.

Installato e confrontato il pacchetto completo, preservando .env e configurazione
Compose. Prima della riapertura tutte le 46 tabelle, 4.454 file documentali e vista
export erano identici alla baseline; nessuna preparazione schema/dati eseguita.

Riaperta circa **21:54:26 italiane**, senza build/pull impliciti. Backend sulla
candidata verificata; frontend con la stessa immagine precedente. PostgreSQL,
mount, mapping, grant e altro stack invariati. Snapshot DDT e riuso Word true.

Postcheck 32 secondi dopo riapertura: quattro HTTP interni/pubblici 200,
versione/bundle `0.1.0.alpha.10`, 219 letture riusabili e protezione manuali
confermate. **Nessun delta nelle 46 tabelle, nessun file/export cambiato, nessun
run AI o consumo AI e nessun errore applicativo nei log.** Il solo ruolo export
esistente rimane `certi_esolver_reader`, SELECT senza privilegi amministrativi.

Spazio: root 7.387.287.552 byte disponibili; dati/backup 80.401.207.296 byte.
Il nuovo backup e lo staging sono sul disco dati; nessuna pulizia server.
Ultimi cicli prima del riavvio: DDT2700 success / Quarta10255 ok. Non considerarli
prova del nuovo timer: attendere e verificare il primo ciclo naturale successivo
alla riapertura, senza invocare sincronizzazioni manuali.

Verificati inoltre i byte dei quattro moduli realmente in esecuzione: identici
al pacchetto f74c2938. Raccolti i verbali privati su PC e server. Rimosso solo
il PostgreSQL QA effimero `certi-alpha-qa-pg-20261030-214500`, identificato per
ID dal manifest, senza rete e senza mount/volumi persistenti. I quattro servizi
locali sono rimasti attivi senza riavvio. Backup server e copie PC/restore_check
conservati; nessuna nuova autorizzazione alla loro cancellazione.

## Primo timer naturale e verifica finale

Senza invocare aggiornamenti manuali: DDT **2701** success alle 22:09:30–31
italiane, 664 righe lette/aggiornate, zero inserimenti; Quarta **10256** ok alle
22:09:31–22:10:00, 16.103 OL e 25.371 riferimenti CDQ. Entrambi successivi al
riavvio e all'intervallo naturale di 15 minuti.

Durante Quarta il monitor HTTP con timeout 5 secondi e scaduto; servizio poi
nuovamente 200. Durata Quarta attuale 28,956 s, precedente predeploy 28,920 s.
Scheduler, servizio Quarta e main sono invariati tra fc1d1f74 e f74c2938; il
rallentamento sincrono e gia documentato nel verbale 24/10. Non e stato corretto
in questo deploy e non va nascosto come semplice guasto del monitor, ne
attribuito senza evidenza alle quattro correzioni acquisizione.

Il postcheck finale, 1.084 secondi dalla riapertura, conferma quattro HTTP 200,
219 letture persistite, zero consumi/run AI, nessun errore applicativo nei log,
4.454 file e export identici. Le differenze DB sono solo le cinque normali
tabelle dei job e `users`: confronto puntuale col dump, hash della baseline e
log autenticazione dimostra **solo last_login dell'utente1 alle 21:56:01**,
coincidente col POST login 200. Tutti gli altri campi utenti, password, ruoli e
permessi identici; nessuna whitelist generica su `users`.

Nessuna modifica a dati Incoming, valori, match, certificati, standard, numeri,
Word/PDF o cache persistite. Immagine/ambiente/configurazione e altro stack
invariati salvo il backend candidato autorizzato. Spazio finale: root
7.387.082.752 byte disponibili, dati/backup 80.401.195.008 byte; nessuna pulizia.

Verbali privati e prova `timer_verified.json` conservati sia sul server sia sul
PC. Nuovi backup e immagini rollback restano; app locale non riavviata.
