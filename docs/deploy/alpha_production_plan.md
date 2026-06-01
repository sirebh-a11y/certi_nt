# Piano alpha produzione

Versione riferimento: `0.1.0.alpha`.

Questo documento descrive come portare Certi_nt in una prima installazione alpha su server Forgialluminio, mantenendo semplice il rilascio e riducendo i rischi.

## Scelta per alpha

Per la prima alpha non introduciamo subito:

- Alembic
- worker separato/Celery per i job AI lunghi

Motivo: sono utili, ma in questa fase aumentano il rischio di rompere flussi gia' funzionanti. Li teniamo come interventi successivi, dopo i primi test reali in produzione.

Per alpha usiamo invece:

- Docker Compose
- Postgres persistente
- storage documenti persistente
- LibreOffice dentro immagine backend
- backup DB + storage prima di ogni aggiornamento
- recupero job interrotti gia' presente all'avvio backend

## Componenti da installare

Servono sul server:

- Docker Engine
- Docker Compose
- accesso rete verso eSolver
- accesso rete verso Quarta
- accesso SMTP aziendale se vogliamo email reali
- cartella persistente per backup

LibreOffice non va installato sui PC degli utenti. E' gia' previsto nel container backend tramite `backend/Dockerfile`.

## Persistenza dati

Questi dati devono sopravvivere a riavvii e aggiornamenti:

- database Postgres
- `backend/storage`
- file `.env` reale di produzione

Il codice puo' essere aggiornato, ma questi tre blocchi non devono essere cancellati.

## Primo utente

Se il database e' vuoto, all'avvio viene creato:

- email: `admin@certi.local`
- password iniziale: `admin123`
- ruolo: admin
- cambio password obbligatorio al primo accesso

Se invece importiamo un database gia' esistente, gli utenti presenti restano quelli del database importato e questo seed non crea un nuovo admin.

Per alpha va bene lasciare questo primo admin, ma subito al primo accesso va cambiata la password.

## Configurazione `.env` produzione

In produzione non usare i default di sviluppo. Preparare un `.env` reale con almeno:

```env
ENV=production
APP_SECRET_KEY=<chiave lunga casuale>
DATABASE_URL=postgresql+psycopg://certi_nt:<password>@postgres:5432/certi_nt
CORS_ORIGINS=http://<server>:5173,http://<server>

SMTP_HOST=<smtp aziendale>
SMTP_PORT=587
SMTP_USER=<utente smtp>
SMTP_PASSWORD=<password smtp>
SMTP_TLS=true
MAIL_FROM_EMAIL=<mail mittente>
MAIL_FROM_NAME=CERTI_nt

ESOLVER_PASSWORD=<password eSolver>
QUARTA_PASSWORD=<password Quarta>

CERTI_PUBLIC_BASE_URL=http://<server>:8000
CERTI_EXPORT_USERNAME=Certi
CERTI_EXPORT_PASSWORD=Certi

PDF_CONVERSION_ENABLED=true
PDF_CONVERTER=libreoffice
LIBREOFFICE_BIN=/usr/bin/soffice
PDF_CONVERSION_TIMEOUT_SECONDS=120

DOCUMENT_VISION_MODEL=gpt-5.5
CERTI_OPENAI_API_KEY=<chiave OpenAI o vuoto se gestita solo per utente>
```

Nota: `CERTI_EXPORT_USERNAME=Certi` e `CERTI_EXPORT_PASSWORD=Certi` sono la coppia prevista per l'accesso eSolver alla vista/API Certi.

## Docker alpha

Il `docker-compose.yml` attuale e' comodo per sviluppo, ma non e' ancora ideale per produzione perche':

- backend usa `--reload`
- frontend usa server Vite dev
- monta il codice come volume
- espone Mailhog

Per alpha usiamo la variante dedicata `docker-compose.alpha.yml`, che:

- rimuove `--reload`
- non monta `./backend:/app`
- builda il frontend statico con nginx
- mantiene Postgres e storage su cartelle persistenti host
- rimuove Mailhog: in alpha si usa SMTP reale o SMTP lasciato non configurato

Il frontend alpha usa:

- `frontend/Dockerfile.alpha`
- `frontend/docker/nginx.alpha.conf`

La configurazione ambiente di esempio e':

- `.env.alpha.example`

Verifiche gia' fatte in preparazione alpha:

- `docker compose --env-file .env.alpha.example -f docker-compose.alpha.yml config`
- `npm run build` nel frontend
- `docker compose --env-file .env.alpha.example -f docker-compose.alpha.yml build backend frontend`

Nota: la build puo' mostrare un warning Vite sulla dimensione del bundle frontend. Non blocca l'alpha.

## LibreOffice e PDF

Nel backend Docker e' gia' installato:

- `libreoffice-writer`
- font DejaVu
- font Liberation

Questo permette la conversione Word -> PDF lato server.

Controlli da fare in alpha:

- generare Word
- generare PDF
- aprire PDF
- verificare logo Forgialluminio
- verificare header
- verificare seconda pagina
- verificare allegati/pagine aggiuntive

Se su server il PDF differisce dai test locali, controllare prima:

- font disponibili
- versione LibreOffice
- dimensione immagini/logo
- path `LIBREOFFICE_BIN`
- permessi cartelle temporanee

## Backup

Prima di ogni aggiornamento:

1. Fermare o mettere in pausa uso utenti se possibile.
2. Backup Postgres.
3. Backup `backend/storage`.
4. Annotare commit/versione installata.
5. Solo dopo aggiornare.

Backup minimo:

- dump DB: contiene utenti, righe incoming, certificati, configurazioni, stati
- cartella storage: contiene PDF, Word, immagini, documenti caricati

Senza storage, il DB resta leggibile ma i file non sono recuperabili.

## Aggiornamento versione

Procedura alpha consigliata:

1. Verificare `git status` pulito sul server.
2. Fare backup DB + storage.
3. Portare nuovo codice.
4. Ricostruire container.
5. Avviare.
6. Controllare log backend.
7. Fare smoke test.

Smoke test minimo:

- login admin
- pagina Incoming
- caricamento piccolo batch
- apertura riga
- conferma standard
- pagina Certificazione
- generazione Word
- generazione PDF
- vista/API export per eSolver

## Rollback

Rollback alpha semplice:

1. Fermare container.
2. Tornare al commit precedente.
3. Ripristinare DB se lo schema/dati sono stati modificati male.
4. Ripristinare storage se sono stati generati/cancellati file errati.
5. Riavviare.

Nota: senza Alembic il rollback DB non e' automatico. Per questo il backup prima dell'aggiornamento e' obbligatorio.

## Debug in produzione

Si puo' continuare a fare debugging, ma con regole:

- mai modificare direttamente dati senza backup
- mai testare batch distruttivi sul DB reale senza accordo
- usare log backend
- usare piccoli documenti di test
- annotare commit e ora intervento

In alpha possiamo lavorare sul server per correggere errori reali, ma ogni intervento deve essere tracciato con commit.

## Job AI lunghi

Stato attuale:

- i job AI girano dentro il backend FastAPI
- se il backend resta vivo, il job finisce
- se backend/server si riavvia, il job puo' interrompersi
- all'avvio il sistema recupera i run rimasti in corso e li chiude come errore/interrotti

Per alpha:

- accettabile
- evitare riavvii durante batch lunghi
- usare email di fine lavoro
- controllare log in caso di errore

Intervento futuro:

- worker separato per AI lunghi
- coda lavori
- retry piu' robusti
- job indipendenti dal processo web

Non lo mettiamo prima dell'alpha per non rendere fragile il rilascio.

## Alembic

Stato attuale:

- il DB viene creato/aggiornato dal bootstrap all'avvio
- il codice usa `Base.metadata.create_all`
- molte modifiche schema sono fatte con funzioni `ensure_*`

Per alpha:

- accettabile
- richiede backup prima di ogni aggiornamento

Intervento futuro:

- introdurre Alembic
- congelare lo schema reale
- creare una migrazione base
- spostare le future modifiche DB in migrazioni versionate

Non lo mettiamo prima dell'alpha perche' ora bisogna riallineare con attenzione lo schema gia' evoluto.

## Hardcoded e default rilevati

| Ambito | Dove | Valore/nota | Decisione alpha |
| --- | --- | --- | --- |
| Admin iniziale | `backend/app/startup/bootstrap.py` | `admin@certi.local` / `admin123` | OK alpha, cambio password al primo accesso |
| Secret app | `.env.example`, `docker-compose.yml`, `backend/app/core/config.py` | `change-me-certi-nt-secret` | Da sostituire in `.env` produzione |
| DB default | `.env.example`, `docker-compose.yml` | `certi_nt/certi_nt` | Da sostituire se IT richiede password forte |
| SMTP sviluppo | `.env.example`, `docker-compose.yml`, docs email | Mailhog | Produzione usa SMTP aziendale |
| Frontend API | `frontend/src/app/api.js`, `.env.example` | `http://localhost:8000/api` fallback | In produzione impostare `VITE_API_BASE_URL` |
| eSolver | `backend/app/core/integrations/service.py` | `10.10.3.6`, DB `ESOLVER`, user `certi`, viste `CertiCliForF3`, `CertiRigheDDT`, `CertiOL` | OK come default modificabile da pagina admin |
| Quarta | `backend/app/core/integrations/service.py` | `10.10.6.10`, DB `INT_Q3`, user `INT_Q3`, vista `CFG_Q3ESS_ONGIUDET_TRACMP` | OK come default modificabile da pagina admin |
| Password eSolver/Quarta | env + DB criptato | `ESOLVER_PASSWORD`, `QUARTA_PASSWORD` | Da impostare in `.env` o pagina admin |
| Export Certi verso eSolver | `backend/app/core/config.py`, `backend/app/modules/esolver_export/router.py` | user `Certi`, password `Certi` | OK come concordato |
| PDF | `backend/app/core/config.py`, `backend/Dockerfile` | LibreOffice `/usr/bin/soffice` | OK alpha, testare su server |
| Modello AI | `backend/app/core/config.py` | `gpt-5.5` default | Le chiavi restano per utente; modello configurabile poi |
| Fornitori core | `backend/app/modules/suppliers/service.py` | 9 fornitori importanti + alias + link eSolver | Da mantenere, fondamentali per lettura documenti |
| Codici fornitori installazione | `backend/app/modules/supplier_codes/service.py` | AA, AB, AH, ecc. | Seed utile, modificabile da admin |
| Note sistema | `backend/app/modules/notes/service.py` | RoHS, radioactive, US classi, ecc. | OK, base app |
| Standard | `backend/app/modules/standards/data/standards_seed.json` | standard chimici/meccanici iniziali | OK, dati funzionali |
| Requisiti cliente | `backend/app/modules/customer_requirements/data/customer_requirements_seed.json` | requisiti per CodF3 | OK, dati funzionali |
| Sync Quarta | `backend/app/modules/quarta_taglio/scheduler.py` | 15 minuti | OK alpha |
| Batch eSolver | `backend/app/modules/quarta_taglio/service.py` | batch query 500 | OK alpha |
| Prompt/template fornitori | `backend/app/modules/acquisition/service.py`, docs supplier template | logiche specifiche fornitori | Core del sistema, non rimuovere |

## Cose da non perdere in produzione

- i 9 fornitori core
- alias fornitori
- `reader_template_key`
- link eSolver dei fornitori
- standard
- note sistema
- requisiti cliente
- codici fornitore installazione
- configurazione eSolver/Quarta
- utenti e chiavi OpenAI utente

## Cose aperte prima di produzione stabile

- introdurre Alembic
- valutare worker separato per job AI lunghi
- definire retention/log cleanup
- definire backup automatico schedulato
- definire reverse proxy/HTTPS
- definire procedura restore provata davvero
- definire monitoraggio spazio disco
- definire email admin reale

## Richieste IT/server

Da chiedere a IT:

- IP/nome server dove installare Certi_nt
- accesso Docker
- spazio disco disponibile
- cartella backup
- accesso rete a `10.10.3.6:1433`
- accesso rete a `10.10.6.10:1433`
- credenziali SMTP aziendali
- URL interno definitivo per utenti
- politica backup server
- eventuale proxy/firewall per OpenAI

## Istruzioni operative per IT

Questa sezione e' il blocco pratico da consegnare a IT per preparare la prima installazione alpha.

## Pacchetto da consegnare a IT

Per la prima alpha non consegniamo istruzioni sparse: consegniamo un pacchetto unico composto da repository, tag, file di configurazione di esempio e questo documento.

### Materiale da dare a IT

| Oggetto | Cosa contiene | Nota |
| --- | --- | --- |
| Repository Git | codice applicazione | `https://github.com/sirebh-a11y/certi_nt.git` |
| Tag alpha | versione congelata da installare | esempio `v0.1.0-alpha.1`; il tag reale verra' comunicato al rilascio |
| Documento IT | istruzioni installazione, backup, update, rollback | questo file: `docs/deploy/alpha_production_plan.md` |
| File env esempio | elenco variabili da compilare | `.env.alpha.example` |
| Compose alpha | avvio Docker per server | `docker-compose.alpha.yml` |
| Frontend alpha | build statico nginx | `frontend/Dockerfile.alpha` + `frontend/docker/nginx.alpha.conf` |
| Checklist test | controlli minimi dopo installazione | contenuta in questo documento |

### Cosa deve compilare IT

IT non deve modificare codice. Deve solo compilare i parametri ambiente reali:

- password database;
- `APP_SECRET_KEY`;
- credenziali SMTP;
- password eSolver;
- password Quarta;
- URL interno dell'app;
- eventuali proxy/firewall per OpenAI;
- cartelle persistenti su server.

### Cosa non va messo su Git

Non devono mai finire nel repository:

- password reali;
- file `.env` reale;
- dump database;
- Word/PDF/documenti caricati dagli utenti;
- backup.

### Regola di rilascio alpha

Il server non deve inseguire qualunque commit di sviluppo.

Regola semplice:

1. sviluppo e debug continuano qui nel repository;
2. quando decidiamo una versione alpha, creo un tag Git;
3. IT installa o aggiorna solo quel tag;
4. prima di ogni cambio tag si fa backup DB + storage.

Esempio:

```text
Sviluppo continuo: main
Versione server alpha: v0.1.0-alpha.1
Aggiornamento futuro: v0.1.0-alpha.2
```

Questo permette di continuare a lavorare qui senza rendere instabile il server.

### Obiettivo

Installare Certi_nt alpha su server aziendale mantenendo persistenti:

- database Postgres
- documenti caricati
- Word/PDF generati
- configurazioni reali di produzione

Il codice applicativo puo' essere aggiornato nel tempo, ma i dati non devono essere cancellati durante aggiornamenti o riavvii.

### Cartella server consigliata

Su server Windows:

```text
C:\CertiNT\
  app\
  data\
    postgres\
    storage\
    backups\
```

Su server Linux:

```text
/opt/certi_nt/
  app/
  data/
    postgres/
    storage/
    backups/
```

`app` contiene il repository Git.

`data/postgres` contiene il database persistente.

`data/storage` contiene Word, PDF, documenti caricati e file generati.

`data/backups` contiene i backup prima degli aggiornamenti.

### Repository da installare

Repository:

```text
https://github.com/sirebh-a11y/certi_nt.git
```

Installazione iniziale:

```bash
git clone https://github.com/sirebh-a11y/certi_nt.git C:\CertiNT\app
cd C:\CertiNT\app
git checkout v0.1.0-alpha.1
```

Su Linux:

```bash
git clone https://github.com/sirebh-a11y/certi_nt.git /opt/certi_nt/app
cd /opt/certi_nt/app
git checkout v0.1.0-alpha.1
```

Nota: `v0.1.0-alpha.1` e' un esempio. Prima dell'installazione reale verra' comunicato il tag alpha effettivo.

### File `.env`

IT deve creare il file:

```text
C:\CertiNT\app\.env
```

oppure:

```text
/opt/certi_nt/app/.env
```

Il file `.env` deve contenere i parametri reali di produzione: password DB, secret app, SMTP, eSolver, Quarta, export Certi verso eSolver.

I valori di esempio sono nella sezione "Configurazione `.env` produzione".

Il file `.env` e' un dato sensibile e deve essere salvato nei backup. Non deve essere pubblicato su Git.

### Avvio alpha

L'avvio alpha usa `docker-compose.alpha.yml`:

```bash
docker compose -f docker-compose.alpha.yml up -d --build
```

Controllo container:

```bash
docker compose -f docker-compose.alpha.yml ps
```

Controllo log backend:

```bash
docker compose -f docker-compose.alpha.yml logs backend --tail=100
```

### Test tecnico Docker per IT

Dopo l'avvio IT deve verificare:

```bash
docker compose -f docker-compose.alpha.yml ps
docker compose -f docker-compose.alpha.yml logs backend --tail=100
docker compose -f docker-compose.alpha.yml exec backend python -c "print('backend ok')"
```

Se uno di questi comandi fallisce, non procedere con test utenti: prima correggere avvio, env o permessi.

### Test funzionale minimo

Dopo il test tecnico:

1. aprire Certi_nt da browser;
2. fare login con admin iniziale;
3. cambiare password;
4. aprire pagina Incoming;
5. aprire pagina Connettori eSolver/Quarta;
6. verificare che eSolver risponda;
7. verificare che Quarta risponda;
8. generare un Word di prova se sono presenti dati idonei;
9. generare un PDF di prova;
10. controllare logo, header, pagine aggiuntive e allegati PDF.

### Dati da non cancellare

Durante aggiornamenti, riavvii o rebuild container, non cancellare:

```text
C:\CertiNT\data\postgres
C:\CertiNT\data\storage
C:\CertiNT\app\.env
```

oppure:

```text
/opt/certi_nt/data/postgres
/opt/certi_nt/data/storage
/opt/certi_nt/app/.env
```

Se queste cartelle vengono cancellate, si perdono dati applicativi e documenti.

### Backup prima di ogni aggiornamento

Prima di ogni nuova versione alpha:

1. avvisare gli utenti;
2. evitare batch AI in corso;
3. fare backup database Postgres;
4. fare backup storage;
5. copiare `.env`;
6. annotare tag/commit installato.

Backup minimo richiesto:

```text
DB Postgres
storage documenti
.env
tag Git installato
```

### Aggiornamento alpha

Esempio aggiornamento da `v0.1.0-alpha.1` a `v0.1.0-alpha.2`:

```bash
cd C:\CertiNT\app
git fetch
git checkout v0.1.0-alpha.2
docker compose -f docker-compose.alpha.yml up -d --build
docker compose -f docker-compose.alpha.yml logs backend --tail=100
```

Su Linux:

```bash
cd /opt/certi_nt/app
git fetch
git checkout v0.1.0-alpha.2
docker compose -f docker-compose.alpha.yml up -d --build
docker compose -f docker-compose.alpha.yml logs backend --tail=100
```

Nota: il tag `v0.1.0-alpha.2` e' un esempio. Ogni aggiornamento verra' comunicato con tag preciso.

### Modifiche DB durante aggiornamento

Per alpha il backend aggiorna molte parti dello schema DB all'avvio.

Esempio:

- se manca una colonna semplice, il bootstrap la crea;
- i dati gia' presenti restano;
- il backup prima dell'aggiornamento resta obbligatorio.

Se una futura modifica DB sara' piu' pesante, verra' preparata una procedura dedicata prima del rilascio.

### Rollback

Se una versione alpha crea problemi:

```bash
cd C:\CertiNT\app
git checkout v0.1.0-alpha.1
docker compose -f docker-compose.alpha.yml up -d --build
```

Se il problema ha modificato male dati o file:

- ripristinare backup DB;
- ripristinare backup storage;
- riavviare container.

## Bozza mail per IT

Oggetto: Preparazione server per installazione alpha Certi_nt

Testo:

```text
Ciao,

stiamo preparando la prima installazione alpha di Certi_nt su server Forgialluminio.

L'applicazione verra' rilasciata tramite repository Git e Docker Compose.

Vi chiediamo di predisporre:

- server con Docker Engine e Docker Compose;
- accesso rete verso eSolver: 10.10.3.6:1433;
- accesso rete verso Quarta: 10.10.6.10:1433;
- accesso internet/API OpenAI, se il server dovra' eseguire il flusso AI;
- accesso SMTP aziendale per invio email;
- cartella persistente per database, storage documenti e backup.

Cartella consigliata Windows:

C:\CertiNT\
  app\
  data\
    postgres\
    storage\
    backups\

Il repository sara':

https://github.com/sirebh-a11y/certi_nt.git

La versione alpha da installare sara' comunicata con tag Git, ad esempio:

v0.1.0-alpha.1

Punto importante:
durante aggiornamenti e riavvii non devono essere cancellati database, storage documenti e file .env.

Nel documento allegato sono indicate istruzioni operative, test Docker, backup e aggiornamento.

Grazie
```

## Documento sintetico per IT

Questo e' il testo breve che puo' essere incollato in un documento di consegna IT insieme alla mail.

```text
Certi_nt alpha - installazione server

Obiettivo:
installare Certi_nt in versione alpha su server Forgialluminio con Docker Compose.

Repository:
https://github.com/sirebh-a11y/certi_nt.git

Versione:
installare solo il tag alpha comunicato, ad esempio v0.1.0-alpha.1.

Cartelle persistenti richieste:
- database Postgres
- storage documenti
- backup
- file .env reale

Cartella consigliata Windows:
C:\CertiNT\app
C:\CertiNT\data\postgres
C:\CertiNT\data\storage
C:\CertiNT\data\backups

Accessi rete richiesti:
- eSolver 10.10.3.6:1433
- Quarta 10.10.6.10:1433
- SMTP aziendale
- OpenAI/API internet se il server esegue il flusso AI

Regola backup:
prima di ogni aggiornamento fare backup di DB, storage e .env.

Regola aggiornamento:
aggiornare solo passando da un tag alpha al successivo.

Regola dati:
non cancellare mai le cartelle data/postgres, data/storage e il file .env.

Test minimo dopo installazione:
- login admin
- cambio password
- controllo connettori eSolver/Quarta
- caricamento piccolo batch
- generazione Word
- generazione PDF
- apertura PDF
- controllo log backend
```
