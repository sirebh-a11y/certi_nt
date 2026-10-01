# Deploy soft Alpha.10 — 01/10/2026

## Riferimenti

- Commit app installato: `3951822fa3790bd7e1b1b6ced33d384a2fb5edd1`.
- Commit pacchetto deploy: `c97c5b8`; tag `v0.1.0-alpha.10-deploy`.
- Archivio: `alpha-produzione-v0.1.0-alpha.10-deploy.tar`.
- SHA-256: `0aa09f4f000ced7cca93b7da8f30e3f8f382d811b583aa5b49bc7a60b34dff61`.
- Tutti i 390 file sorgente confrontati integralmente con il pacchetto Git.
- Versione backend e frontend pubblicato: `0.1.0.alpha.10`.

## Operazioni eseguite

Autorizzati commit/push, deploy e preparazioni; conferma ulteriore dell'utente
sul report definitivo per recupero e attivazione DDT.

1. Controllati run AI (nessuno attivo) e traffico recente; sospesi solo backend
   e frontend. PostgreSQL e altri servizi server non sono stati fermati.
2. Rimossa soltanto cache build inutilizzata da almeno sette giorni: circa
   2,1 GB ricreabili. Nessuna immagine di rollback, volume o backup eliminato.
3. Salvati app/configurazione, storage e dump DB; gzip verificati e dump
   ripristinato interamente in PostgreSQL locale temporaneo senza porte
   pubblicate. Conteggi ripristinati: 153 Incoming, 132 certificati, 11 versioni.
4. Installato il pacchetto senza sostituire `.env`; conservati anche i vecchi
   file applicativi in una directory backup. Costruite entrambe le immagini.
5. Aggiunte offline e in transazione le due colonne `pdf_file_name`.
6. Preview Alpha ufficiale senza problemi: 455 quote correnti e 162 storiche.
   Dopo conferma, importate nella stessa transazione; nessuna copia dati dal DB
   locale e nessuna sovrascrittura dei certificati esistenti.
7. Impostato soltanto `DDT_SNAPSHOT_ENABLED=true` nel `.env` Alpha e ricreati
   backend/frontend alle 18:06 UTC (20:06 italiane).
8. Bootstrap: tutte le 153 righe Incoming hanno `incoming_loaded_at`; vista
   eSolver aggiornata con `NomeFilePdf`, mantenendo SELECT a `certi_esolver_reader`.

## Esito dati e verifiche

- 617 quote DDT: 455 presenti nella fonte, 162 storiche conservate.
- Coda: 608 attive, 9 completate; 533 in attesa Incoming, 62 da collegare,
  5 pronte, 4 con Word pronto e 4 da verificare. La casella UI Pronti Incoming
  raggruppa 5 pronte + 4 Word pronti, mostrando 9.
- Quattro quote (DDT 2368 e 2375 del 01/10) restano da verificare: Word senza DDT
  associabile a più quote. Nessun abbinamento forzato.
- Conteggi preesistenti invariati: 153 Incoming, 132 certificati, 11 versioni PDF.
- Confrontate anche le impronte dell'intero contenuto di queste tre tabelle con
  la copia ripristinata del backup: identiche, escluse soltanto le nuove colonne.
- Tutti i 10 PDF finali verificati presenti e con versione attiva; 10 righe nella
  vista export. Nove corrispondono alle quote della coda, non a tutti i certificati.
- Verificati tutti i 10 URL PDF export tramite HTTP pubblico: risposta 200,
  contenuto PDF e nome di download corrispondente a `NomeFilePdf`.
- Health API e frontend pubblico HTTP 200; avvio backend senza errori.
- Suite anche nell'immagine backend realmente ricostruita su Alpha, in un
  container isolato senza rete e con SQLite in memoria: 493 superati, 15 test
  PostgreSQL saltati qui (già superati nel collaudo locale completo da 508 test).
  Il primo tentativo aveva bloccato il convertitore fittizio del test usando
  `/tmp` non eseguibile; ripetuto con filesystem temporaneo standard, senza
  cambiare il codice applicativo o le protezioni dei container in esercizio.
- Verifica browser reale con sessione IT temporanea: DDT da certificare,
  Incoming, Reparti e Valutazione caricati senza errori JS/HTTP. Richieste mutanti
  bloccate nel browser di collaudo; nessuna conferma, esclusione o generazione PDF.
- Aperte anche le finestre Gemba (giorno e due orari) ed esclusione DDT:
  conferma disabilitata senza motivo; dialogo annullato senza salvare decisioni.
- Mantenuto il mapping PostgreSQL `10.10.1.10:5432`, senza cambiare utenti,
  password, Nginx o firewall. Modulo Lab nuovi fornitori escluso.
- Primo ciclo automatico DDT verificato: run 2, **success**, 01/10/2026
  18:21:29 UTC (20:21:29 italiane). Letta la fonte con 455 quote, aggiornate
  le stesse 455; nessun inserimento duplicato, nessuna sparizione o errore.
  Confermata la conservazione delle 162 quote storiche (totale ancora 617).

## Backup e ripristino

Percorsi server, non pubblici:

- `/srv/certi_nt/backup/app_before_alpha10_20261001.tgz`
- `/srv/certi_nt/backup/storage_before_alpha10_20261001.tgz`
- `/srv/certi_nt/backup/db_before_alpha_20261001_alpha10.sql`
- `/srv/certi_nt/backup/app_directory_before_alpha10_20261001/`
- `/srv/certi_nt/backup/ddt_preview_alpha10_20261001.json`

Immagini precedenti conservate come `app-backend:before-alpha10-20261001` e
`app-frontend:before-alpha10-20261001`. Un eventuale rollback richiede fermo
concordato e backup dei dati successivi: non ripristinare il dump alla cieca.

## Note operative per i prossimi deploy

- `SOURCE_COMMIT` nell'archivio può avere CRLF: per confrontare l'hash su Linux
  usare `tr -d '\r\n' < SOURCE_COMMIT`, senza alterare il file installato.
- L'utente deploy può modificare il contenuto di `/srv/certi_nt/app`, ma non
  rinominare la cartella dal suo parent. Il vecchio contenuto è stato spostato
  nel backup lasciando `.env` al suo posto; nessuna elevazione o cambio permessi.
- Con script inviati via `ssh ... 'bash -s'`, i comandi Docker che non devono
  leggere stdin richiedono `</dev/null`; altrimenti possono consumare lo script.
- Il browser integrato non si è avviato: usato il percorso Playwright già
  documentato. Screenshot/script restano in `tmp_eval`, fuori da Git/deploy.
- Spazio dopo backup e build: circa 2,2 GB liberi. Va pianificata con IT la
  capacità/retention, senza cancellare automaticamente i backup.
- Restano le segnalazioni già note sulle dipendenze frontend; nessun `npm audit
  fix` o cambio requisiti eseguito durante il deploy.

Questo verbale documenta l'esecuzione: il codice server resta quello del commit
indicato sopra, anche se il verbale viene pubblicato con un commit successivo.
