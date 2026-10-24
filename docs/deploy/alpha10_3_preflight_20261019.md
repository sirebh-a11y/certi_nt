# Alpha 10.3 — manutenzione autorizzata 19/10/2026

## Perimetro e stato

Utente: deploy autorizzato e richiesta di riportare sul server i backup
temporaneamente conservati sul PC, liberando spazio dopo verifica.
**Esito: deploy completato e verificato il 19/10 alle 19:12 UTC circa
(21:12 Roma).** Alpha online. Preservati documenti e dati storici;
nota separata sotto sul rallentamento Quarta già presente.

- Sorgente applicativo: `62767a6e8009130c93c13b6d639d81161dfba402`.
- Pacchetto `v0.1.0-alpha.10.3-deploy`, commit deploy `2a31915`.
- SHA-256 tar: `748e29f84c4c8d8091476f07b4602fad2604a864bf2159f716e29f0017b2c554`.
- Confronto integrale: 440 file app identici ai blob sorgente; soli extra
  `README_ALPHA.md` e `SOURCE_COMMIT`. Nessun Lab, `.env`, storage o temporaneo.
- Immagini candidate costruite senza cambiare l'app attiva: strati dipendenze
  backend/frontend in cache, nessun aggiornamento librerie.
- Versione applicativa invariata `0.1.0.alpha.10`.
- Unica nuova preparazione DB: `shipment_context JSON` nullable; nessun backfill,
  rinumerazione storica, nuova archiviazione DDT o generazione di PDF reali.

## Nuovo assetto disco IT verificato

Ore 18:40 UTC: root 24.627.232.768 byte totali, 14.626.119.680 occupati,
8.724.160.512 disponibili; disco dati 105.085.067.264 totali,
6.874.378.240 occupati, 92.825.415.680 disponibili. Quote riservate ext4
spiegano perché totale meno occupato non coincide con disponibile.

`/srv/certi_nt/data` e `/srv/certi_nt/backup` sono bind mount del nuovo disco
`vg_certi/lv_certi`, rispettivamente `/certi_nt/data` e `/certi_nt/backup`.
App e immagini/build Docker rimangono sulla root: i 92,83 GB non sono spazio
automaticamente disponibile per Docker. Non occorre pulizia per questo deploy.
Non modificare mount, fstab, PostgreSQL o l'altro stack applicativo.

## Backup e ritorno dal PC

Ritrasferire in directory privata server
`/srv/certi_nt/backup/returned_pc_20261019/`:

- tre backup app di luglio da `backups/alpha_space_20261018`;
- app, DB, storage e manifest/baseline del backup 18/10 16:49:43 UTC.

Lo storico `storage_before_hard_reset_20260715_080925.tgz` esiste già sul
server: confrontare l'hash e verificare gzip/tar, senza duplicarlo inutilmente.
Questi archivi includono configurazioni private: directory 700/file 600,
nessun contenuto in Git o nell'app pubblica.

Prima della rimozione locale: SHA-256 end-to-end, decompressione/lettura tar
completa, nuova copia di sicurezza esterna del deploy attuale verificata,
inventario dei percorsi esatti. Conservare manifest/log locali e registrare
byte recuperati. Non cancellare directory per glob, altri backup o dati utente.
Un backup recente non sostituisce gli archivi storici unici: essi vengono
trasferiti, non scartati. Restano sulla macchina server e quindi non equivalgono
a un backup esterno: conservare il nuovo backup completo anche sul PC.

## Cautele operative

Nessuna attività AI/HTTP rilevata nel preflight; ripetere subito prima del fermo.
Fermare solo backend/frontend, senza ricreare PostgreSQL o altro stack.
Un solo identificativo backup `20261019_184500`, directory privata server e PC.
Backup app/configurazione, pg_dump e storage con writer fermi; tar Docker
`--log-driver none`, rete disabilitata, mount applicativi readonly.
Restore DB isolato e confronto di tutte le tabelle/file prima della migrazione.
Preservare `.env`, flag snapshot/riuso true, mapping PostgreSQL e PDF chiusi.
Controllo del primo ciclo automatico, senza chiamata manuale sostitutiva.

## Esito finale

- Collaudo reale immagine candidata: **486 test Quarta passati, nessun salto**
  (212,685 secondi), PostgreSQL isolato senza rete esterna o volumi persistenti.
- Backup nuovo: app 7.158.135 byte, SQL 16.678.982, storage 1.619.582.050.
  Copie server/PC con SHA-256 identici; 439 file app e 3.537 documentali
  confrontati integralmente con la baseline, 44 tabelle ripristinate con hash
  identici. Schema provato sul restore: preview 246 certificati/72 chiusi,
  colonna JSON nullable idempotente, nessun backfill.
- Il container PostgreSQL di collaudo va atteso con `pg_isready -h 127.0.0.1`:
  il socket della fase init temporanea non prova l'avvio definitivo.
  Per invocare `preview_legacy` con sessione ORM importare i modelli tramite
  `from app.startup import bootstrap`, **senza chiamare** initialize/bootstrap:
  il solo helper non registra tutte le classi delle relazioni ORM.
- Backup storici restituiti e verificati, copie PC ancora presenti fino alla
  conclusione del deploy. Manifest privato in
  `.tmp_server_audit/returned_pc_20261019.json`; totale 2.967.009.159 byte,
  comprendente baseline/manifest che saranno conservati anche sul PC.

## Installazione e controlli conclusi

- Backend avviato 18:55:30 UTC (20:55:30 Roma). `.env` identico, flag raccolta
  DDT e riuso Word true; PostgreSQL e altro stack preservati (cinque container
  complessivi non ricreati), mapping `10.10.1.10:5432` confermato. Nessun componente disinstallato.
- Migrazione Alpha: sola colonna `shipment_context`, idempotenza e NULL
  verificati, tutte le 44 tabelle/file identici prima/dopo il DDL.
- Preview su 813 quote: 534 archiviate, 185 senza Word, 71 documenti
  preservati, 2 decisioni manuali, 20 senza OL, 1 Incoming non pronto;
  **zero riusi da applicare**. Nessun recupero o rigenerazione massiva.
- Postcheck: tutti i 246 certificati preesistenti e 3.537 file identici;
  nessun nuovo certificato/file. Vista export 72 righe, hash identico
  `cf44a7a06a460af27fdf435253737369`.
- Codice installato confrontato byte per byte col tar. Health backend/frontend
  HTTP200, versioni backend/bundle coerenti; nessun traceback/errore rilevato.
- Backend in esecuzione con l'immagine candidata; SHA-256 del modulo shipment
  uguale al tar. Frontend riavviato ma non ricreato da Compose perché invariato:
  confrontati RootFS/layer e Config dell'immagine eseguita e candidata, identici.
  L'ID superiore differisce solo per l'attestazione della nuova build, non per
  codice/configurazione; non forzare un riavvio aggiuntivo per la sola data del container.
- Browser reale: DDT, Registro OL1091 (sola quota chiusa, base non duplicata),
  tag requisiti OL962, standard/reparti/caricamento. Nessun errore JavaScript
  o HTTP; refresh mutante registro simulato, lista OL `sync=false`, nessun PDF
  aziendale generato. Screenshot privati nel nuovo backup PC, ispezionati.
- Simulazioni SELECT-only su Alpha: OL1090 nuovo DDT -> `7051_00_00_01/26`,
  OL1091 -> `7051_01_00_01/26`, OL997 -> `7013_00_00_01/26`, nomi file
  coerenti. DDT2375: `29 of 120` / `91 of 120`; DDT2418: `118`.
  Numeri/file salvati lasciati invariati, nessun documento di prova creato.
- Provata anche l'estrazione fisica app/storage in cartella privata isolata
  server: hash dei 439+3.537 file identici. Rimossa soltanto tale copia di prova,
  archivi di sicurezza conservati.
- Rivalidate tutte le nove copie/manifest restituiti al server; rimosse solo
  le sette copie archivio locali (2.966.364.544 byte). Manifest, log, screenshot
  e backup nuovo completo restano sul PC. Guadagno netto dei soli archivi,
  sottraendo il nuovo backup 1.643.419.167 byte: **1.322.945.377 byte**.

Primo ciclo automatico verificato senza chiamata manuale né modifica intervallo:
snapshot ID1693, 19:10:34–19:10:36 UTC, `success`, 580 righe sorgenti, zero
errori/nuovi inserimenti; Quarta ID9185 19:10:36–19:11:05 UTC, `ok`, 16.032 OL
e 25.290 righe CDQ. `triggered_by_user_id=NULL` e tempi successivi al normale
intervallo dopo avvio. Log interni snapshot/riuso senza errori. Ripetuto
postcheck dopo il ciclo: 246 certificati e 3.537 file precedenti identici,
72 export con hash invariato; nessun nuovo documento di collaudo.

### Osservazione distinta: breve blocco HTTP durante sync Quarta

Nel primo ciclo la successiva sync Quarta è durata circa 29,8 secondi.
Durante questa fase due controlli health con timeout 5 secondi non hanno
ricevuto risposta; a fine ciclo HTTP200 in 0,033 secondi, servizi sani e dati
integri. Il monitor iniziale è uscito per timeout HTTP, **non per fallimento
snapshot**: conservato `timer_check.log`, poi registrato esito positivo reale
in `timer_result.log`, senza invocare job manuali.

Il codice `scheduler.py` è identico tra sorgente Alpha precedente `ec5b9498`
e nuova `62767a6e`: la chiamata sincrona `sync_and_list_quarta_taglio(db)`
è dentro il ciclo async e occupa l'event loop. Il ritardo osservato è quindi
coerente con una limitazione preesistente, non con la nuova numerazione.
Da proporre separatamente: audit degli accessi sincroni e spostamento del
lavoro in thread con sessione DB dedicata e controlli di concorrenza.
Non implementato né mascherato aumentando i timeout dell'app. L'utente va
informato: l'esito positivo del deploy non significa assenza di questo difetto.

## Spazio dopo installazione e ritorno backup

- Root: circa 8,72 GB disponibili; dati/backup: circa 88,81 GB disponibili.
- PostgreSQL fisico: 332.335.781 byte; DB logico CERTI: 107.363.351 byte.
- Storage operativo: 1.794.373.495 byte; backup: 8.035.094.165 byte;
  sorgenti app: 11.940.940 byte (misure `du -sb`, non sempre allocazione fisica).
- Docker: immagini 5,005 GB nominali, cache build 1,748 GB nominali;
  layer condivisi, non sommarli ingenuamente a `df`. Nessun prune.
- L'aumento sul disco dati è previsto: circa 2,35 GB di copie tornate dal PC
  più 1,64 GB del nuovo backup, pacchetto/candidato e report. I 620 MB dello
  storage storico erano già sul server, quindi non sono stati trasferiti due volte.
- Nuova copia di restore fisico temporanea rimossa; nessun container QA rimasto.
  Rimangono immagini operative e di rollback e i backup verificati.
