# Preparazione Alpha — ciclo Word/DDT/PDF, 28/10/2026

## Stato e autorizzazioni

Preparazione richiesta dall'utente, **non deploy**. Alpha interrogata solo in
lettura; codice candidato caricato in memoria in un processo Python separato,
transazione PostgreSQL `REPEATABLE READ, READ ONLY`, nessun bootstrap/job o
endpoint mutante. Report salvati soltanto sul PC, in area privata.
Non sono stati eseguiti commit/push, installazioni, fermi servizi, pulizie o
correzioni dei dati Alpha. La procedura apply è stata implementata solo in locale.

Questo verbale aggiorna i conteggi precedenti del piano del 28/10, non li cancella.
Prima della manutenzione rifare la fotografia: l'app continua a essere usata.

## Esito del controllo server

Controlli alle 11:25–11:40 UTC circa (12:25–12:40 italiane):

- Sorgente installato `89c5fe40578edf025ed8a4460625a5177de2e964`, pacchetto 10.4.
- Frontend e health pubblico HTTP200; PostgreSQL Alpha healthy. Altri stack
  presenti sul server: esclusi dal perimetro di ogni futuro fermo.
- Nessun AI/upload attivo nelle due fotografie. Due richieste HTTP negli ultimi
  cinque minuti, zero 5xx/traceback: **non equivale a una finestra di manutenzione**.
- Snapshot e riuso Word entrambi true, da preservare. Ultimo ciclo osservato
  ID2488: success, 648 righe, 11:33:56–11:33:58 UTC; nessuna sync manuale avviata.
- **312 certificati: 214 draft, 98 PDF chiusi; export 98 righe.**
  3.983 file storage; database logico 109.460.503 byte. Nessun ID fonte scambiato
  fra OL/F3 nei controlli; nessun percorso principale condiviso fra più record.
- Riletti i testi dei 98 PDF chiusi: nessuna discordanza rilevata per numero,
  OL, F3 e DDT. Questo NON certifica ogni valore tecnico, firma o seconda pagina.
- Nessun record allegato PDF e nessun marcatore PDF incorporato nei Word correnti;
  nessun riferimento attuale `ddt_reused` promosso con allegati. Non c'è evidenza
  di un caso corrente R2/R3 da bonificare, ma non è una prova di tutta la storia.

### Spazio e budget

Valori decimali GB, non GiB; `df` distingue spazio disponibile e riserva filesystem.

| Filesystem | Totale | Occupato | Disponibile |
| --- | ---: | ---: | ---: |
| Root, codice/immagini Docker | 24,63 GB | 15,73 GB | 7,62 GB |
| Disco dati e backup, unico filesystem | 105,09 GB | 13,09 GB | 86,61 GB |

Mount reali confermati: `/srv/certi_nt/data` e `/srv/certi_nt/backup` sono bind
dal disco `vg_certi-lv_certi`. **Non sommare due volte i loro 86,61 GB liberi.**
Directory: app 13.377.536 byte; storage 1.996.161.024; backup 9.840.992.256.
Docker: immagini 5,009 GB, cache 3,115 GB nominali; non sommarli nuovamente a `df`
né considerarli tutti cancellabili (strati condivisi/rollback).

Budget prudenziale per il futuro deploy: **3–4 GB root** per candidate/build e
**2–3 GB dati** per nuovi backup; lasciare almeno circa 3 GB root dopo la build.
Rimisurare prima/dopo backup e build; fermarsi se il consumo supera la previsione.
**Nessuna pulizia proposta o necessaria sulla fotografia attuale.** Nessun backup,
immagine, cache, componente LibreOffice/OCR o file aziendale da cancellare.

Dockerfile backend/frontend, requirements, lock frontend e Compose equivalenti
al server dopo normalizzazione CRLF/LF. Nessun aggiornamento dipendenze necessario.
Per backend è applicabile la variante già collaudata del runbook: esatto runtime
operativo immutabile, sostituzione completa app/scripts nell'immagine candidata,
senza apt/pip/rete. ID osservato: `b4d5be5b44dfbb70bca976e8679e1ba36226ecfae2cf16770265ae76c77f9b35`.
Il frontend invece **va ricostruito** perché ci sono modifiche UI; toolchain Node
già fissata nel Dockerfile Alpha, non risolvere nuovi tag runtime implicitamente.
Il tag Nginx nel Dockerfile è ancora mutabile: confrontare il runtime risultante
con quello operativo. Se differisce, non avviare la candidata; usare la variante
documentata con runtime verificato per ID e nuovo bundle completo, dopo aver
confermato invariata la configurazione Nginx. Riutilizzare il runtime non significa
riutilizzare il vecchio bundle frontend. Conservare wrapper e confronto nel verbale.
Riconfermare le immagini reali al deploy; preservare rollback e gli altri stack.

## Recupero proposto, non applicato

| ID | OL | Azione strettamente limitata |
| --- | --- | --- |
| 62 | OL2026001087 | Riallineare `word_reference.template_hash` al Word completo verificato |
| 268 | OL2026001058 | Riallineare solo `word_reference.storage_key` al percorso corrente equivalente |
| 285 | OL2026001025 | Come sopra |
| 308 | OL2026001137 | Come sopra; nuovo caso emerso nella fotografia aggiornata |

ID62: Word invariato nei membri/contenuti rispetto allo storage backup del
24/10, verifica ripetuta. SHA256 corrente
`4b372aba3dfa8c34adbfa924782a585ad1203caaef827cd175957b9dfc4568dc`.
La vecchia impronta registrata non coincide già con quel documento storico.
Il recupero conserva file, ID, numero, revisione, origine e date: non è una nuova
approvazione normativa, un upload fittizio o una rigenerazione tecnica.

Per ID268/285/308 verificata equivalenza tecnica vecchio/nuovo percorso.
I tre PDF sono chiusi: file, versioni, nomi personalizzati, token, export e date
di chiusura devono rimanere identici. Il nuovo caso 308 non è un nuovo PDF da fare.

**Simulazione solo in memoria** del riallineamento: quota894, OL1087/F3449000700,
DDT2626-27/10/2026 passa da `reference_file_changed` a `reuse`, fonte ID62,
destinazione ancora assente, numero `7044_00_00/26`. Non è stata creata su Alpha
alcuna copia. Nel recupero successivo il Word della quota riceverà il suo nuovo
ID ordinario, non sostituirà ID62 e non chiuderà il PDF.

Quattro vecchie basi condivise, 10 record nei gruppi 71/137/177, 99/189,
74/194 e 88/208/225, più la base singola ID62: **nessuna cancellazione/copia
preventiva**. Il codice corretto non usa più una base comune per numero:
ricava quando serve la base del proprio documento/versione, mantenendo i file
precedenti. Non è stata accertata una pagina sbagliata da ripristinare nello storico.

OL986 resta un caso di dati reali mancanti (CDQ24-0985 in Incoming): apertura
corretta dal nuovo software, nessun riuso forzato. OL1148 e i suoi PDF restano intatti.

Report privati: `.tmp_server_audit/anomalia_20261028/predeploy_20261028_1130.json`
e `predeploy_repair_proposal_20261028.json`. Quest'ultimo è intenzionalmente
**non eseguibile**: algoritmo marcato `PREDEPLOY_ONLY_REQUIRES_FRESH_INSTALLED_PREVIEW`.
Non usarlo come report approvato. Richieste/hash devono essere ricontrollati e la
preview esecutiva rifatta con la candidata realmente installata, writer fermi.

## Procedura locale preparata

Nuovi modulo `word_lifecycle_recovery.py` e CLI
`python -m scripts.recover_word_lifecycle_alpha` (separati dal normale flusso).

- Due sole azioni: percorso con equivalenza tecnica dimostrata; impronta di
  riferimento draft mai chiuso, solo con SHA256 esplicitamente verificato e nota
  di evidenza. Niente accettazione generalizzata dei mismatch o dei PDF chiusi.
- Anteprima senza scritture; elenco ID esplicito, target DB/storage, impronta
  dell'intero codice, record e file. Nessun segreto/token riportato.
- Apply richiede ID del piano approvato, manutenzione, backup DB/storage.
  Scadenza un'ora; cluster/codice/dati/file cambiati impongono una nuova preview.
- Lock PostgreSQL NOWAIT: rifiuta writer attivi, non li interrompe. Un'unica
  transazione, soli campi `word_reference` approvati; conserva anche `updated_at`.
- Journal nuovo esclusivo e sincronizzato su disco prima del commit, con
  valori prima/dopo e hash backup; evento `committed` dopo successo. Esito incerto
  → controllo, mai riapplicazione cieca o cancellazione. Report già usato/journal
  esistente non sovrascritti; il core riconosce l'applicazione già completata.
- Nessun Word/PDF creato/modificato dal recupero metadati, nessuna modifica a
  numerazione, ID, versioni o export. Il successivo recupero della copia DDT è una
  fase distinta con la CLI Word già esistente e nuova preview approvata.

## Sequenza del futuro deploy, dopo OK separato

1. Commit/push espliciti; pacchetto da commit esatto, senza Lab, report privati,
   documenti, dataset, `.env` o temporanei. Tag nuovo libero e confronto integrale.
2. Ricontrollare spazio e attività, concordare finestra. Fermare solo writer,
   backend/frontend Alpha, lasciando PostgreSQL e gli altri stack attivi.
3. Backup app/config/DB/storage stesso TS; hash, leggibilità/restore isolato e
   copia esterna verificati. I backup del 24/10 non sostituiscono quelli nuovi.
4. Installare/collaudare le candidate senza avviare l'app. Nessun ALTER previsto:
   le tre colonne JSON necessarie sono già presenti. Non ripetere migrazioni,
   archiviazioni o recuperi di ottobre descritti come storici nel runbook.
5. Preview metadati sui dati Alpha fermi; presentare i quattro ID aggiornati,
   piano/hash e ottenere OK al recupero. Applicare con storage read-only, poi
   confrontare tutte le tabelle/file protetti: cambiano solo i quattro JSON attesi.
6. **Nuova preview recupero Word** dopo i metadati. L'azione prevista è solo
   quota894; se emerge un altro perimetro, fermarsi e concordarlo. Dopo OK, creare
   la sola copia ammissibile con la procedura esistente `recover_ddt_words_alpha`.
   Verificare nuovo ID, riferimento fonte, numero, DDT, quantità, corpo/pagine,
   nomi e link; nessun PDF generato. Seconda preview senza ulteriori recuperi.
7. Export e 98 PDF preesistenti invariati rispetto alla NUOVA baseline; il numero
   98 è una fotografia, non va imposto se gli utenti hanno lavorato nel frattempo.
8. Riaprire con i normali flag snapshot/riuso true, già autorizzati; verificare
   health, UI, messaggi, primo ciclo naturale e spazio. Niente PDF reali di prova.

Comandi **solo dopo installazione candidata, backup e manutenzione autorizzati**,
da `/srv/certi_nt/app`; sostituire tutti i placeholder con la manutenzione corrente:

```bash
docker compose --env-file .env -f docker-compose.alpha.yml run --rm --no-deps \
  -e DDT_SNAPSHOT_ENABLED=false -e DDT_WORD_REUSE_ENABLED=false \
  -v /srv/certi_nt/data/storage:/app/storage:ro -v /srv/certi_nt/backup:/audit \
  backend python -B -m scripts.recover_word_lifecycle_alpha \
  --preview --requests /audit/metadata_requests_TIMESTAMP.json \
  --report /audit/metadata_preview_TIMESTAMP.json

# Solo con approvazione dei valori e dell'esatto plan_id prodotto sopra.
docker compose --env-file .env -f docker-compose.alpha.yml run --rm --no-deps \
  -e DDT_SNAPSHOT_ENABLED=false -e DDT_WORD_REUSE_ENABLED=false \
  -v /srv/certi_nt/data/storage:/app/storage:ro -v /srv/certi_nt/backup:/audit \
  backend python -B -m scripts.recover_word_lifecycle_alpha \
  --apply --report /audit/metadata_preview_TIMESTAMP.json \
  --approved-plan-id PLAN_ID_APPROVATO --maintenance-confirmed \
  --backup /audit/BACKUP_DATABASE_VERIFICATO.sql \
  --storage-backup /audit/BACKUP_STORAGE_VERIFICATO.tgz
```

I flag false valgono SOLO nei container one-off; `.env` operativo resta invariato.
La CLI controlla intestazione/leggibilità del dump e presenza/hash degli archivi:
**non sostituisce la prova di ripristino e coerenza dei backup** richiesta sopra.
I nomi dei file backup sono segnaposto, non file da creare per aggirare i controlli.

Errore prima del commit → rollback transazione, nessun file prodotto. Esito
incerto/differenza inattesa → mantenere manutenzione e confrontare journal/DB;
non ripristinare un vecchio database globale perdendo lavoro recente. I quattro
metadati corretti non richiedono automaticamente un rollback dati se si rinvia
il codice: valutare compatibilità prima della riapertura, specialmente per le
basi manuali nuove/vecchie. Conservarle tutte, nessuna pulizia implicita.

## Collaudo conclusivo della preparazione

- Suite generale backend nel runtime Linux isolato: **732 superati**.
- Ripetute tutte le suite PostgreSQL dedicate sul database temporaneo locale:
  **126 superati**, più i **7 test SQLite** del nuovo recupero ripetuti nella
  stessa esecuzione (133 superati complessivi in questa esecuzione). I 7 sono
  già compresi nei 732, non vanno sommati come nuovi casi distinti.
- Verificate realmente anche commit e journal della nuova CLI su PostgreSQL,
  rifiuto di journal già presente con rollback, writer concorrente, piano
  scaduto/manomesso, modifica dei file/dati dopo preview, applicazione parziale,
  ripetibilità e passaggio dal recupero metadati al normale riuso della quota.
- La prima prova CLI isolata ha rilevato un ordine errato della fixture: alcuni
  modelli erano registrati dopo la creazione dello schema di test. Corretto
  l'ordine d'importazione nella sola fixture; nessuna guardia del prodotto rimossa.
- **34 test frontend superati**, build Vite riuscita nella sola cartella QA
  `tmp_eval/predeploy_20261028/frontend_build`, senza riavviare servizi ordinari.
  Il primo tentativo di build era bloccato dai permessi esbuild di Windows;
  ripetuto con autorizzazione, non era un errore applicativo.
- Restano warning di deprecazione, Browserslist datato e dimensione bundle:
  nessun aggiornamento dipendenze inserito in questo intervento.
- Chiuso il solo container PostgreSQL QA `certi-recovery-qa-20261028`, con
  auto-remove e dati sintetici in tmpfs; nessun dato aziendale cancellato.
  Anche il container della suite Linux era temporaneo con auto-remove.
- `git diff --check` senza errori di whitespace. Restano da fare, soltanto dopo
  autorizzazione, commit/push, pacchetto dal commit e collaudo delle immagini
  candidate effettive sul server. La preparazione non equivale al post-deploy.
