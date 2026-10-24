# Alpha 10.4 — Arconic, 24/10/2026

## Autorizzazione e perimetro

Utente: commit/push e deploy Alpha secondo piano e runbook, autorizzati il 24/10.
Stato iniziale: preflight concluso, installazione ancora da eseguire.
Nuovo pacchetto previsto `v0.1.0-alpha.10.4-deploy`; versione applicativa resta
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

## Passi ancora da eseguire

Commit sorgente pubblicato, pacchetto completo da Git con confronto blob e
soli extra README_ALPHA.md/SOURCE_COMMIT; tag nuovo non forzato. Build candidate
e test del contenuto/immagine effettivi; backup verificati; installazione senza
ALTER e preservando .env/storage/DB; health/versioni, dati/file/export invariati,
timer reale e spazio finale. Nessuna chiamata mutante per il solo audit.
Conservare rollback codice e backup, senza ripristinare un vecchio DB sopra
eventuale lavoro utenti successivo. Il precedente rallentamento Quarta
sincrono resta una questione distinta, non risolta da questa modifica.
