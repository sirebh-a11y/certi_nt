# Alpha 10.4 — Arconic, 24/10/2026

## Autorizzazione e perimetro

Utente: commit/push e deploy Alpha secondo piano e runbook, autorizzati il 24/10.
**Esito: deploy completato e verificato, compreso il primo ciclo automatico.**
Alpha online dalle 13:50:24 UTC (15:50 italiane); timer verificato il 24/10
alle 14:06 UTC circa (16:06 italiane), poi nuovo confronto dati/file/export.
Pacchetto `v0.1.0-alpha.10.4-deploy`; versione applicativa resta
`0.1.0.alpha.10`, come per i pacchetti precedenti. Nessuna modifica frontend.

Solo prompt Arconic di certificato/DDT e rilettura identità facoltativa,
prima di normalizzazione/cache. Una sola rilettura aggiuntiva, timeout 45s,
nessun retry SDK. Se fallisce o resta contraddittoria: prima lettura conservata,
elaborazione prosegue. Nessuna nuova migrazione, bonifica, archiviazione,
rigenerazione documenti o cambio di matcher/protezioni manuali.

## Preflight in sola lettura

- Alpha installata: sorgente `62767a6e8009130c93c13b6d639d81161dfba402`.
- Frontend e `/api/health` rispondono 200. Nessun run AI/upload o processo
  LibreOffice attivo al controllo; subito prima del fermo ripetere la verifica.
- DDT ultimo ciclo ID2130: success, 615 righe, 24/10 13:24:50–13:24:51 UTC.
  Quarta ID9655: ok, 16.072 OL, 13:24:51–13:25:21 UTC.
- Flag snapshot/riuso true, mapping PostgreSQL `10.10.1.10:5432`, modello
  `gpt-5.5`, SDK OpenAI 1.79.0; preservare tutti i valori e il file `.env`.
- 291 certificati, 89 con PDF; 3.857 file storage. Sono una fotografia prima
  del fermo, non conteggi da imporre se gli utenti lavorano nel frattempo.
- Colonne shipment_context, word_reference, word_standard_snapshot ed
  elongation_basis presenti; vista export presente. Nessun ALTER richiesto.

## Spazio e backup

Root 24.627.232.768 byte totali, 14.648.123.392 occupati,
8.702.156.800 disponibili. Dati/backup condividono un filesystem distinto:
105.085.067.264 totali, 11.040.698.368 occupati, 88.659.095.552 disponibili.
Non sommare come liberi due volte data e backup. Directory operative:
storage 1.925.354.413 byte, backup 8.035.094.165, app 11.940.940;
PostgreSQL fisico 350.358.181, DB logico 108.575.767.

Budget prudenziale: 3–4 GB root build/immagini e 2–3 GB dati per backup.
Nessuna pulizia proposta o autorizzata. Non toccare vecchi backup, immagini di
rollback, altri stack, mount o dipendenze. Misurare durante backup/build.
Dockerfile, requirements, lock frontend e compose semanticamente invariati;
byte CRLF/LF diversi dal server, quindi non garantire cache-hit.

Con un solo TS: fermo dei soli backend/frontend Alpha dopo controllo attività;
backup privati app/.env, dump PostgreSQL e storage, SHA-256/contenuto/restore
isolato e copia esterna. PostgreSQL e altro stack restano attivi.
Non produrre stream binari con logging Docker: `--log-driver none`.

## Collaudi prima dell'installazione

766 test backend senza errori; anche i 98 test PostgreSQL inizialmente saltati
superati separatamente. 29 test Arconic e simulazione recupero su 1.000 documenti.
Sei chiamate OpenAI sulle funzioni applicative: $0.261255, 2 match corretti e
4 candidati errati rifiutati; recupero certificato/DDT riuscito. Chimica,
proprietà e note dei tre certificati invariate rispetto al collaudo precedente.
Nessun nuovo documento aziendale da generare come prova su Alpha.

## Pacchetto, immagini e imprevisti gestiti

- Commit sorgente pubblicato `89c5fe40578edf025ed8a4460625a5177de2e964`;
  deploy `5d2fdcd80b7018eceabab6433e72645b368398a7`.
- Tar SHA-256 `535c5de7321f5a7a1943b744d534375c12bbcac179eba643c4e58cfe2ad1ddde`.
  444 file sorgente confrontati con i blob Git; soli extra README_ALPHA.md e
  SOURCE_COMMIT. Nessun Lab, .env, storage, dataset o temporaneo nel pacchetto.
- La prima build ha risolto un nuovo digest di python:3.11-slim anche con
  `--pull=false`. Fermata la sola build candidata con app ancora online,
  prima di installare alcuna modifica. Nessuna pulizia cache/immagini.
- Per non aggiornare dipendenze è stato usato come base il runtime operativo
  esatto Alpha10.3, ID `6f3ce8b4dfa209ac42461ca0acaaf8967cca865f88aab7ea0223e33848d600ec`.
  Wrapper privato `candidate_alpha10_4_20261024_133535/backend_runtime.Dockerfile`:
  rete build disabilitata, sostituzione completa SOLO /app/app e /app/scripts
  nell'immagine candidata, copia requirements senza pip/apt. Verificati tutti
  gli strati runtime precedenti come prefisso e Env/Cmd/Entrypoint/User/WorkingDir
  identici. Nessun componente LibreOffice/OCR/runtimes modificato.
- Frontend sorgente invariato (confronto con pacchetto) e immagine effettiva
  riutilizzata. Nessun nuovo Node/npm o Nginx scaricato/installato.
- Sull'immagine candidata reale: 29 test Arconic e 53 lifecycle superati,
  import/versione riusciti; confronto completo di app/scripts con il tar.
- Rinomina atomica della directory app negata dal parent root-owned, senza
  modifiche ai file. Non aggirati i permessi: applicata la sostituzione dei soli
  contenuti prevista dal runbook, dopo copia privata completa `app_previous`.
  .env/configurazione preservati; database e storage fuori dal perimetro.

## Backup e conservazione

Un solo TS `20261024_133535`. Copie private verificate su server
`/srv/certi_nt/backup/alpha_deploy_20261024_133535` e PC
`backups/alpha_deploy_20261024_133535` (ACL solo utente).

- App/.env: 7.172.072 byte; SHA-256
  `2ccf07b11d9d6028ccb99cb4c65f5df64c5fbc2bba89ba674c59f54bf2b1aee6`.
- Dump SQL: 17.329.961 byte; SHA-256
  `7c7842845b9e5dcdcedf8be405c4b471f26d9c458eb41176cc2250ec3c5f6aeb`.
- Storage: 1.736.208.562 byte; SHA-256
  `44470739c04a5b9bdad7cee309c9b9558774a420d8dccaf08e82471961c8d0dc`.

Hash end-to-end identici; app e storage letti integralmente. Ripristino PostgreSQL
isolato sul PC: tutte le 44 tabelle identiche, senza esclusione di campi legacy.
Ripristino fisico: 443 file app e 3.857 documentali identici. Il container QA è
stato rimosso; archivi, baseline, manifest, log e impronte sono conservati.
Rimosse soltanto le copie temporanee locali di estrazione `restore_check` e
lo staging sorgente di questa manutenzione, dopo verifica. Archivi app/SQL/storage,
manifest, baseline, log e impronte restano sul PC e sul server; il tar tagged
resta disponibile nel repo deploy. Nessun backup storico o documento operativo
cancellato. La directory estratta temporanea si può ricreare dagli archivi verificati.
Nessuna copia DB locale importata su Alpha; nessuna migrazione o bonifica.

## Installazione e primo postcheck

Prima e dopo installazione, writer ancora fermi: tutte le 44 tabelle e tutti i
file precedenti invariati. Dopo riapertura: 291 certificati e 93 versioni PDF
precedenti identici, 3.857 file invariati, zero nuovi documenti. Export 89 righe,
hash `e94f6f4f2febbee520d7192396b22b14` invariato.

Health backend/frontend/pubblico 200; versioni backend/bundle 0.1.0.alpha.10;
flag raccolta/riuso true, mapping 10.10.1.10:5432 preservato. PostgreSQL e gli
altri cinque container non ricreati. Nessun traceback rilevato al controllo.
Spazio disponibile: root 7.640.027.136 byte, dati/backup 86.858.518.528.

Primo timer naturale verificato, senza chiamate sync manuali o cambio intervallo:
snapshot ID2131 `success`, 615 righe sorgente, 14:05:29–14:05:30 UTC;
Quarta ID9656 `ok`, 14:05:30–14:05:59 UTC, `triggered_by_user_id=NULL`.
Entrambi successivi ai 15 minuti dal riavvio. Nuovo postcheck: tutti i 291
certificati, 93 versioni PDF e 3.857 file precedenti invariati; zero documenti
nuovi, export 89 righe e stesso hash. Health 200 e nessun traceback rilevato.
Root finale 7.639.818.240 byte disponibili; dati/backup 86.858.518.528.
Non generati PDF reali per collaudo. Il rallentamento Quarta sincrono già
documentato resta distinto: il ciclo è durato circa 29,4 secondi e non è stato
modificato da questo intervento.

Rollback: immagini `before-alpha10_4-20261024`, app_previous privata e archivi
verificati conservati. Non ripristinare un vecchio DB sul nuovo lavoro utenti;
la correzione non ha richiesto modifiche schema o dati.
