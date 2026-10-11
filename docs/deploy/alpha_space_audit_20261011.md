# Alpha — audit spazio e proposta di pulizia 11/10/2026

Audit in sola lettura. **Nessuna cancellazione eseguita né autorizzata** da
questo documento. L'OK dell'utente riguarda l'aggiornamento dei Markdown.
Procedura operativa: [deploy soft Alpha](alpha_soft_update_server.md), punto
di ingresso e sezione spazio. Prima del prossimo deploy chiedere esplicitamente
se autorizza la prima proposta sotto, dopo nuovo inventario e confronto copie.

## Fotografia, non budget garantito per il futuro

- Filesystem: 24.627.232.768 byte totali, 845.799.424 disponibili all'ultimo
  controllo (circa 23 GiB / 807 MiB, 97% occupato).
- Backup circa 5,2 GiB; immagini Docker 4,984 GB decimali; build cache 1,730 GB,
  dei quali 1,617 GB privati dichiarati. Strati condivisi: non sommare le righe
  delle immagini come spazio fisico recuperabile.
- PostgreSQL Alpha misurato dentro il container: 315,8 MiB. Il `du` dell'utente
  SSH sull'host non può leggere tutta la directory DB; non considerare completo
  un totale con errori di permesso. Non usare privilegi aggiuntivi per pulire il DB.
- Nessuna build attiva al controllo `docker buildx history ls --filter status=running`;
  health Alpha OK. Questi controlli scadono: ripeterli prima di una pulizia.

Il 09/10 prima pulizia cache: 1,428 GB fisici recuperati; dopo backup e nuova
build lo spazio era nuovamente ridotto. Seconda pulizia: circa 733 MB fisici
(Docker dichiarava 1,044 GB nominali). A fine deploy circa 776 MiB liberi:
non c'è evidenza di un nuovo riempimento tra fine deploy e questo audit.
Base Python risolta nuovamente e dipendenze ricostruite: conservare questa
lezione nella stima dei prossimi deploy, insieme a backup e immagini di rollback.

## Prima proposta: tre pacchetti duplicati, circa 802 MB

Directory server esatta: `/srv/certi_nt/backup`.
Copie esterne verificate sul PC:
`C:\Users\sireb\VScodeProjects\certi_nt\deploy_repo\certi_nt_deploy`.

| Nome file, identico nelle due directory | Byte file | SHA-256 verificato uguale |
|---|---:|---|
| `alpha-produzione-v0.1.0-alpha.9.4-deploy.tar` | 267223040 | `59a59364726017a2488731d3cb770d7ac22f9a52f9a96f540129f4bf0524e627` |
| `alpha-produzione-v0.1.0-alpha.9.5-deploy.tar` | 267294720 | `eb7cc77acdbcc2a6b90bf2cf0ba1d79136d4e5b5626b5550bf0fe6993ea32b53` |
| `alpha-produzione-v0.1.0-alpha.9.5.1-deploy.tar` | 267325440 | `949ffd8a84c712f23574e90c6476e0d735fcccb8457842dc26aaea1f0c838203` |

Verifiche: archivi leggibili, nessun `.env`, circa 256 MB di materiale di test
`tmp`/`tmp_eval` per archivio (errore storico di packaging già documentato).
Non sono file usati dai container né pacchetti dell'ultimo rollback.
File regolari, non symlink, un solo hard link; occupazione fisica complessiva
801.857.536 byte al controllo. **Copie locali non tracciate in Git**: non
considerare il repository remoto una copia dei byte senza ulteriore verifica.

Proposta: eliminare esclusivamente le tre copie server dopo OK specifico.
Prima: rivalidare percorsi risolti, hash di entrambe le copie e assenza di
operazioni che usino quei pacchetti. Conservare le copie sul PC, non pulirle
contestualmente. Possibilità di recupero: ritrasferimento della copia identica.
Nessuna rimozione di programmi, immagini Docker, configurazioni o dati applicativi.
Nessun comando di cancellazione pronto da eseguire è incluso qui.

## Seconda proposta, condizionata: vecchio storage di luglio

- Directory: `/srv/certi_nt/data/storage_before_hard_reset_20260715_080925`.
- Archivio: `/srv/certi_nt/backup/storage_before_hard_reset_20260715_080925.tgz`,
  620.236.680 byte; radice interna `storage/`.
- Confronto completo: **815 file su entrambi i lati**, 664.986.000 byte di
  contenuto, hash di ogni file uguale, nessun file aggiuntivo/mancante,
  nessuna voce speciale nell'archivio o errore di scansione.
- La directory non è montata da alcuno dei container inventariati. Lo storage
  operativo è invece `/srv/certi_nt/data/storage`: deve rimanere intatto.

Non eliminare ancora la directory. Per massima sicurezza prima copiare
l'archivio in una destinazione esterna privata concordata e verificarne hash,
leggibilità e possibilità di ripristino isolato. Poi ricontrollare contenuti,
riferimenti/usi, perimetro e chiedere OK separato. Recupero indicativo circa
665 MB di contenuto / 637 MiB su disco, da rimisurare. Conservare archivio e
dump `db_before_hard_reset_20260715_080925.sql` per il contesto storico.

## Elementi non proposti per rimozione immediata

Tre backup in `/srv/certi_nt/backup`, complessivamente 728.565.434 byte:

- `app_before_v0.1.0-alpha.9.5-deploy_20260720_203730.tgz`;
- `app_before_v0.1.0-alpha.9.5.1-deploy_20260721_092554.tgz`;
- `app_before_v0.1.0-alpha.9.5.2-deploy_20260721_105000.tgz`.

Contengono materiale di test ma **anche `.env` storico**: non sono equivalenti
ai tre pacchetti pulibili. Nessuna copia esterna completa verificata in questo
audit; conservarli. Eventuale spostamento futuro: destinazione privata, hash,
verifica ripristino e OK separato. Non pubblicarli in Git o sul web.

Cache Docker: circa 1,6 GB privati nominali, ma catene con dipendenze e record
recenti, alcuni mutabili. Non è stata approvata una nuova lista di rimozione.
I vecchi ID puliti il 09/10 non sono riutilizzabili. Nuovo inventario di ogni
ID, genitori/discendenti, shared/reclaimable/mutable e build attive prima di
una proposta mirata. Preservare le immagini: rimuovere cache non equivale a
disinstallare LibreOffice/OCR in esecuzione, ma può richiedere nuovi download
e ricompilazioni al prossimo deploy. Guadagno fisico non garantito.

Conservare anche le immagini senza container attivi destinate al rollback:

- `app-backend:before-alpha10_1-20261009` (`97b62cf61bea`);
- `app-frontend:before-alpha10_1-20261009` (`e498de3ae71d`);
- `app-backend:before-alpha10-20261001` (`d22378138875`);
- `app-frontend:before-alpha10-20261001` (`8729d66e3314`).

Il loro eventuale ritiro richiede una decisione sulla conservazione dei rollback,
non una deduzione da «zero container». Anche il rollback del codice richiede
verifica di compatibilità: archivio DDT, A50mm e snapshot Word non sono
compresi nel vecchio codice. Non tornare a generare documenti con quello senza piano.

## Protezioni e chiusura dell'eventuale pulizia

Non toccare DB/documenti correnti, backup completi 01/10 e 09/10, `.env`,
manifest/report/journal dei recuperi, immagini attive e altro stack `/srv/certi`.
Niente `system prune`, `image prune`, `volume prune`, rimozioni generiche o
cancellazioni manuali sotto `/var/lib/docker`. Nessuna pulizia database/DDT.

Subito prima dell'azione: nuovo inventario, target precisi, copie valide,
assenza di usi concorrenti, spazio stimato e OK registrato. Dopo: `df`, health,
container/immagini preservati, controllo dei file rimasti e resoconto dei soli
elementi rimossi con ubicazione delle copie. Fermarsi se l'esito diverge;
non allargare il perimetro per raggiungere una quantità di spazio promessa.
Anche recuperando 802 MB occorre rifare il budget backup/build: non basta
da solo ad autorizzare il prossimo deploy.
