# Alpha server - aggiornamento forte e pulizia hard dati di test

Questo documento descrive la procedura da usare quando vogliamo aggiornare il server alpha
e, nello stesso intervento, azzerare i dati operativi di test.

Non e' una procedura ordinaria di aggiornamento: serve solo quando vogliamo ripartire puliti
senza perdere configurazioni, standard e dati base.

## Regola obbligatoria

Questa procedura NON deve mai essere eseguita automaticamente.

Quando Silvano chiede una pulizia hard, Codex deve prima fermarsi e chiedere una riconferma
chiara, per esempio:

> Confermi di voler eseguire la PULIZIA HARD sul server certi-test?
> Verranno cancellati documenti caricati, Incoming, match, righe Quarta, certificati Word/PDF,
> allegati e dati di test. Verranno mantenuti configurazioni eSolver/Quarta/email e dati base.
> Per procedere scrivi: CONFERMO PULIZIA HARD.

Frasi generiche come "pulisci", "resetta", "riparti pulito" o simili non bastano.
Serve riconferma esplicita.

## Differenza rispetto alla procedura soft

La procedura soft aggiorna il codice e mantiene tutto il database e lo storage.

La pulizia hard invece:

- mantiene configurazioni e dati base;
- cancella i dati operativi di test;
- svuota lo storage documentale collegato ai test;
- lascia il server pronto per nuovi test alpha.

Questa procedura puo' essere usata in due modi:

1. **Pulizia hard senza aggiornare app**
   - si mantiene la versione applicativa gia' installata;
   - si cancellano solo i dati operativi di test.

2. **Aggiornamento forte app + pulizia hard**
   - prima si aggiorna il codice come nella procedura soft;
   - poi si puliscono database operativo e storage;
   - e' il caso da usare quando vogliamo installare una nuova alpha e ripartire con test puliti.

## Cosa deve restare

Devono restare sempre:

- file `.env` del server;
- configurazioni connessioni eSolver e Quarta salvate in app;
- configurazioni email salvate in app;
- configurazioni AI/modelli, se presenti;
- reparti;
- fornitori base/locali e collegamenti eSolver;
- alias fornitori;
- codici fornitori;
- note/template;
- standard chimici e meccanici;
- requisiti cliente;
- parametri di export Certi verso eSolver letti da `.env`.

## Utenti: due varianti

### Variante A - mantiene utenti

Usare quando vogliamo solo pulire i dati di test ma lasciare gli utenti creati durante alpha.

Resta tutto quanto riguarda gli utenti, ruoli e reparti.

### Variante B - reset utenti

Usare quando vogliamo ripartire anche con gli utenti puliti.

La procedura elimina gli utenti applicativi e lascia che il bootstrap ricrei solo l'utente base:

- `admin@certi.local`

Questa variante va scelta esplicitamente nella riconferma.

## Cosa viene cancellato

Dati caricamento e Incoming:

- batch upload;
- documenti fornitori;
- pagine documento;
- evidenze documento;
- valori letti;
- righe Incoming;
- match e candidati match;
- blocchi manuali;
- storico eventi e storico valori;
- run Assistente AI.

Dati Quarta/Certificazione:

- righe Quarta sincronizzate;
- run sincronizzazione Quarta;
- selezioni standard per OL;
- link eSolver caricati per le righe;
- override manuali;
- certificati finali numerati;
- versioni Word/PDF;
- pagine aggiuntive;
- allegati PDF.

Storage:

- file PDF caricati;
- immagini pagina;
- Word generati;
- PDF chiusi;
- allegati;
- file temporanei collegati ai test.

## Export Certi verso eSolver

L'export verso eSolver non e' una vista SQL salvata.
E' un endpoint API:

- `/api/export/esolver/certificati-pdf`

Espone solo certificati PDF chiusi, con almeno:

- `IdCerti`;
- `OL`;
- `DDT`;
- `CodF3`;
- `NumeroCertificato`;
- `DataCertificato`;
- `PdfUrl`;
- `Stato`;
- `UpdatedAt`.

Le credenziali di accesso per eSolver/Nemesi sono lette da `.env`, quindi restano dopo la
pulizia hard.

Dopo una pulizia hard l'export sara' vuoto, perche' i PDF chiusi vengono cancellati. Appena si
generano nuovi PDF chiusi, l'endpoint torna automaticamente a esporli.

## Preflight obbligatorio

Prima di qualsiasi pulizia:

1. verificare di essere sul server corretto;
2. verificare che non ci siano run AI in corso;
3. fare backup database;
4. fare backup storage;
5. annotare timestamp e variante scelta;
6. mostrare a Silvano il riepilogo e chiedere riconferma finale.

Controllo run AI:

```bash
cd /srv/certi_nt/app
docker compose --env-file .env -f docker-compose.alpha.yml exec -T postgres \
  psql -U certi_nt -d certi_nt \
  -c "select id, status, started_at, updated_at from acquisition_processing_runs where status in ('in_coda', 'in_esecuzione') order by id desc;"
```

Se esistono run in corso, fermarsi.

## Backup obbligatori

Database:

```bash
cd /srv/certi_nt/app
TS=$(date +%Y%m%d_%H%M%S)
docker compose --env-file .env -f docker-compose.alpha.yml exec -T postgres \
  pg_dump -U certi_nt certi_nt \
  > "/srv/certi_nt/backup/db_before_hard_reset_${TS}.sql"
```

Storage:

```bash
TS=$(date +%Y%m%d_%H%M%S)
tar -czf "/srv/certi_nt/backup/storage_before_hard_reset_${TS}.tgz" \
  -C /srv/certi_nt/data storage
```

App/env:

```bash
TS=$(date +%Y%m%d_%H%M%S)
tar -czf "/srv/certi_nt/backup/app_before_hard_reset_${TS}.tgz" \
  -C /srv/certi_nt app
```

## Procedura operativa

La procedura deve essere eseguita in modo controllato, non lanciata a mano a pezzi.

### Variante 1 - solo pulizia hard

1. backup come sopra;
2. stop temporaneo di frontend/backend, lasciando PostgreSQL attivo;
3. pulizia tabelle operative;
4. eventuale pulizia utenti, solo variante B;
5. svuotamento storage operativo;
6. riavvio servizi;
7. controlli finali.

### Variante 2 - aggiornamento forte app + pulizia hard

Usare quando vogliamo portare sul server una nuova alpha e ripartire senza dati operativi di test.

Sequenza prevista:

1. backup database, storage e app/env;
2. aggiornamento codice come da procedura soft `alpha_soft_update_server.md`;
3. verifica che i container siano ripartiti con la nuova versione;
4. stop temporaneo di frontend/backend, lasciando PostgreSQL attivo;
5. pulizia tabelle operative;
6. eventuale pulizia utenti, solo variante B;
7. svuotamento storage operativo;
8. riavvio servizi;
9. controlli finali.

La pulizia hard va fatta solo dopo aver verificato che l'aggiornamento codice sia andato a buon fine.
Se l'aggiornamento app fallisce, non procedere con la pulizia.

Non usare mai:

```bash
docker compose down -v
```

perche' cancellerebbe volumi/dati in modo non controllato.

## Tabelle da preservare

Lista logica da non cancellare:

- `external_connections`;
- `email_settings`;
- `departments`;
- `users` solo in variante A;
- `ai_providers`;
- `ai_models`;
- `fornitori`;
- `fornitori_alias`;
- `fornitori_esolver_link`;
- `fornitori_codici_installazione`;
- `note_templates`;
- `normative_standards`;
- `normative_standard_chemistry`;
- `normative_standard_properties`;
- `customer_requirements`.

## Tabelle operative da cancellare

Lista logica da cancellare:

- `documenti_fornitore`;
- `acquisition_upload_batches`;
- `documenti_fornitore_pagine`;
- `documenti_evidenze`;
- `datimaterialeincoming`;
- `valori_letti_acquisition`;
- `match_certificato`;
- `match_certificato_candidati`;
- `match_blocchi_manual`;
- `storico_eventi_acquisition`;
- `storico_valori_acquisition`;
- `acquisition_processing_runs`;
- `quarta_taglio_sync_runs`;
- `quarta_taglio_rows`;
- `quarta_taglio_standard_selections`;
- `quarta_taglio_esolver_links`;
- `quarta_taglio_article_overrides`;
- `quarta_taglio_incoming_row_overrides`;
- `quarta_taglio_final_certificates`;
- `quarta_taglio_certificate_pdf_versions`;
- `quarta_taglio_certificate_extra_pages`;
- `quarta_taglio_certificate_pdf_attachments`.

Prima di scrivere lo script definitivo, verificare le foreign key reali e usare una transazione.

## Pulizia storage

Lo storage va archiviato e poi ricreato vuoto.

Esempio concettuale:

```bash
TS=$(date +%Y%m%d_%H%M%S)
mv /srv/certi_nt/data/storage "/srv/certi_nt/data/storage_before_hard_reset_${TS}"
mkdir -p /srv/certi_nt/data/storage
```

Prima di farlo deve gia' esistere il tar di backup dello storage.

## Rollback

Rollback database:

```bash
cd /srv/certi_nt/app
docker compose --env-file .env -f docker-compose.alpha.yml exec -T postgres \
  psql -U certi_nt -d certi_nt \
  < /srv/certi_nt/backup/db_before_hard_reset_YYYYMMDD_HHMMSS.sql
```

Rollback storage:

```bash
rm -rf /srv/certi_nt/data/storage
tar -xzf /srv/certi_nt/backup/storage_before_hard_reset_YYYYMMDD_HHMMSS.tgz \
  -C /srv/certi_nt/data
```

Poi riavviare i servizi.

## Controlli dopo la pulizia

Verificare:

- login funzionante;
- configurazione eSolver/Quarta ancora presente;
- configurazione email ancora presente;
- fornitori presenti;
- clienti eSolver consultabili se connessione attiva;
- standard presenti;
- requisiti cliente presenti;
- codici fornitori presenti;
- Incoming vuoto;
- Registro certificazione vuoto;
- Certificazione/Quarta vuota fino alla nuova sincronizzazione;
- upload documenti funzionante;
- endpoint export eSolver raggiungibile ma senza PDF esposti.

## Stato finale atteso

Dopo pulizia hard:

- il server resta installato;
- le configurazioni restano;
- i dati di test sono rimossi;
- lo storage e' pulito;
- la app e' pronta per un nuovo ciclo di test alpha.
