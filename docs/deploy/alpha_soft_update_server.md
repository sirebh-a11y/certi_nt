# Aggiornamento soft alpha su server

Questo documento descrive come aggiornare la alpha sul server `certi-test.forgialluminio.it` partendo dall'app locale gia modificata e da GitHub aggiornato, senza cancellare database, storage documentale o configurazioni server.

## Obiettivo

Aggiornare solo il codice applicativo alpha sul server.

Devono restare intatti:

- database PostgreSQL;
- file caricati e generati dall'app;
- file `.env` del server;
- configurazioni Nginx/server fatte da IT.

## Percorsi

Sviluppo locale:

- repo app: `C:\Users\sireb\VScodeProjects\certi_nt`
- repo deploy: `C:\Users\sireb\VScodeProjects\certi_nt\deploy_repo\certi_nt_deploy`
- cartella alpha deploy: `deploy_repo\certi_nt_deploy\alpha-produzione`

Server:

- app: `/srv/certi_nt/app`
- dati persistenti: `/srv/certi_nt/data`
- database: `/srv/certi_nt/data/postgres`
- storage documenti: `/srv/certi_nt/data/storage`
- backup: `/srv/certi_nt/backup`

SSH dal PC locale, usando PowerShell:

```powershell
ssh -i "$env:USERPROFILE\.ssh\certi_nt_admcerti01_ed25519" admcerti01@certi-test.forgialluminio.it
```

La chiave da usare qui e la chiave privata locale `certi_nt_admcerti01_ed25519`, non il file `.pub`.

## Flusso corretto

1. Sviluppo e test in locale.
2. Commit e push del repo app.
3. Aggiornamento della cartella `alpha-produzione` nel repo deploy.
4. Commit, push e tag del repo deploy.
5. Creazione archivio `.tar` pulito dalla cartella `alpha-produzione`.
6. Copia archivio sul server in `/srv/certi_nt/backup`.
7. Backup dell'app server attuale.
8. Sostituzione soft del codice, preservando `.env`, database e storage.
9. Avvio Docker.
10. Verifica.

## Prima di aggiornare

Controllare che il server sia sano:

```bash
cd /srv/certi_nt/app
docker compose --env-file .env -f docker-compose.alpha.yml ps
test -f .env
test -d /srv/certi_nt/data/postgres
test -d /srv/certi_nt/data/storage
```

Non procedere se:

- manca `.env`;
- PostgreSQL non e attivo o non e healthy;
- mancano le cartelle `data/postgres` o `data/storage`;
- l'app e in mezzo a un caricamento importante.

### Controllare run AI attivi

Prima di fermare backend/frontend controllare che non ci siano elaborazioni AI in corso.

Il nome tabella corretto e `acquisition_processing_runs`.

```bash
cd /srv/certi_nt/app
docker compose --env-file .env -f docker-compose.alpha.yml exec -T backend \
  python -c "from app.core.database import SessionLocal; from sqlalchemy import text; db=SessionLocal(); rows=db.execute(text(\"select id, stato, fase_corrente from acquisition_processing_runs where stato in ('in_coda', 'in_esecuzione') order by id desc limit 10\")).mappings().all(); print([dict(r) for r in rows]); db.close()"
```

Se torna `[]`, non ci sono run attivi.

Se ci sono run `in_coda` o `in_esecuzione`, non aggiornare subito: si rischia di interrompere un caricamento documenti o una lettura AI lunga.

## Creare archivio dal deploy repo

Dal PC locale, nel repo deploy:

```powershell
cd C:\Users\sireb\VScodeProjects\certi_nt\deploy_repo\certi_nt_deploy
git status
git tag v0.1.0-alpha.X-deploy
git push origin main
git push origin v0.1.0-alpha.X-deploy
git archive --format=tar --output alpha-produzione-v0.1.0-alpha.X-deploy.tar v0.1.0-alpha.X-deploy:alpha-produzione
```

`X` va sostituito con il numero reale della versione.

## Copiare archivio sul server

Da PowerShell locale:

```powershell
scp -i "$env:USERPROFILE\.ssh\certi_nt_admcerti01_ed25519" `
  C:\Users\sireb\VScodeProjects\certi_nt\deploy_repo\certi_nt_deploy\alpha-produzione-v0.1.0-alpha.X-deploy.tar `
  admcerti01@certi-test.forgialluminio.it:/srv/certi_nt/backup/
```

## Backup prima dell'aggiornamento

Sul server:

```bash
set -e
TAG=v0.1.0-alpha.X-deploy
TS=$(date +%Y%m%d_%H%M%S)
cd /srv/certi_nt

tar -czf "backup/app_before_${TAG}_${TS}.tgz" app
```

Questo backup salva il codice applicativo corrente e il `.env`, ma non duplica tutto il database.

### Backup database

Fare sempre un dump DB prima di aggiornamenti che cambiano tabelle, colonne o logiche dati.

Sul server alpha attuale usare esplicitamente utente e database:

```bash
cd /srv/certi_nt/app
TS=$(date +%Y%m%d_%H%M%S)
docker compose --env-file .env -f docker-compose.alpha.yml exec -T postgres \
  pg_dump -U certi_nt certi_nt \
  > "/srv/certi_nt/backup/db_before_alpha_${TS}.sql"
```

Nota: il comando con `"$POSTGRES_USER"` e `"$POSTGRES_DB"` dentro `sh -lc` puo fallire se quelle variabili non sono disponibili nel processo shell del container. In quel caso `pg_dump` prova l'utente `root` e fallisce. Per questo, nella procedura alpha, usare `pg_dump -U certi_nt certi_nt`.

Per aggiornamenti solo frontend/backend senza modifiche DB, il dump e consigliato ma non sempre obbligatorio. In alpha conviene farlo spesso.

## Aggiornamento soft

Sul server:

```bash
set -e
TAG=v0.1.0-alpha.X-deploy
ARCHIVE=alpha-produzione-${TAG}.tar
TS=$(date +%Y%m%d_%H%M%S)

cd /srv/certi_nt
test -f "backup/$ARCHIVE"
test -f app/.env
test -d data/postgres
test -d data/storage

tar -czf "backup/app_before_${TAG}_${TS}.tgz" app

cd app
docker compose --env-file .env -f docker-compose.alpha.yml stop backend frontend

find . -mindepth 1 -maxdepth 1 ! -name .env -exec rm -rf {} +
tar -xf "../backup/$ARCHIVE" -C .

docker compose --env-file .env -f docker-compose.alpha.yml up -d --build
docker compose --env-file .env -f docker-compose.alpha.yml ps
```

Nota importante: non usare `docker compose down -v`, perche puo cancellare volumi se la configurazione cambia.

## Controlli dopo aggiornamento

Sul server:

```bash
cd /srv/certi_nt/app
docker compose --env-file .env -f docker-compose.alpha.yml ps
docker compose --env-file .env -f docker-compose.alpha.yml logs --tail=120 backend
curl -I http://127.0.0.1:8080/
curl -I http://127.0.0.1:8001/docs
```

Controllare anche la versione backend:

```bash
cd /srv/certi_nt/app
docker compose --env-file .env -f docker-compose.alpha.yml exec -T backend \
  python -c "from app.main import app; print(app.version)"
```

Per alpha 5 deve tornare:

```text
0.1.0.alpha.5
```

Da browser:

- login;
- pagina `Carica documenti`;
- pagina `Incoming materiale`;
- pagina `Certificazione`;
- pagina `Registro certificazione`;
- pagina `Connettori eSolver/Quarta`, se serve verificare i collegamenti.

## Rollback codice

Usare se il nuovo codice non parte o rompe l'app, ma il database non e stato modificato.

Sul server:

```bash
set -e
BACKUP=app_before_v0.1.0-alpha.X-deploy_YYYYMMDD_HHMMSS.tgz
TS=$(date +%Y%m%d_%H%M%S)

cd /srv/certi_nt
docker compose --env-file app/.env -f app/docker-compose.alpha.yml stop backend frontend

mv app "app_failed_${TS}"
tar -xzf "backup/$BACKUP" -C .

cd app
docker compose --env-file .env -f docker-compose.alpha.yml up -d --build
docker compose --env-file .env -f docker-compose.alpha.yml ps
```

Il rollback codice non tocca `/srv/certi_nt/data`.

## Rollback database

Da usare solo se abbiamo cambiato struttura dati o se il database e stato alterato in modo sbagliato.

Regola pratica:

- prima si ferma l'app;
- si conserva una copia dello stato rotto;
- si ripristina il dump SQL fatto prima dell'aggiornamento;
- si riavvia l'app con il codice coerente con quel database.

Esempio operativo da adattare con attenzione:

```bash
cd /srv/certi_nt/app
docker compose --env-file .env -f docker-compose.alpha.yml stop backend frontend

docker compose --env-file .env -f docker-compose.alpha.yml exec -T postgres \
  sh -lc 'dropdb -U "$POSTGRES_USER" "$POSTGRES_DB" && createdb -U "$POSTGRES_USER" "$POSTGRES_DB"'

docker compose --env-file .env -f docker-compose.alpha.yml exec -T postgres \
  sh -lc 'psql -U "$POSTGRES_USER" "$POSTGRES_DB"' \
  < /srv/certi_nt/backup/db_before_alpha_YYYYMMDD_HHMMSS.sql

docker compose --env-file .env -f docker-compose.alpha.yml up -d backend frontend
```

Questo punto va fatto solo quando necessario e con backup verificato.

## Caso colonne nuove nel DB

Oggi l'alpha non ha ancora una gestione migrazioni completa tipo Alembic.

Quindi, se una nuova versione introduce colonne o tabelle:

1. va capito prima quali modifiche DB servono;
2. va fatto dump DB;
3. va preparata una piccola migrazione SQL o una procedura controllata;
4. va testato che il backend parta con il DB esistente;
5. solo dopo si fa aggiornamento server.

Il rischio e questo: il codice nuovo parte aspettandosi una colonna che nel DB server non esiste ancora.

## Cose da non fare

Non fare:

- cancellare `/srv/certi_nt/data`;
- cancellare `/srv/certi_nt/data/postgres`;
- cancellare `/srv/certi_nt/data/storage`;
- sovrascrivere `.env`;
- usare `docker compose down -v`;
- pulire database o documenti senza decisione esplicita;
- aggiornare mentre un caricamento AI lungo e in corso.

## Aggiornamento pulito completo

Da usare solo quando deciso esplicitamente.

In quel caso si puo:

- salvare dump DB;
- salvare storage;
- pulire dati applicativi caricati;
- mantenere hardcoded, standard, fornitori base e configurazioni necessarie;
- riavviare una alpha pulita per test.

Questo non e l'aggiornamento soft.
