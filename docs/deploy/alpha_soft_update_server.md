# Aggiornamento soft alpha su server

Questo documento descrive come aggiornare la alpha sul server `certi-test.forgialluminio.it` partendo dall'app locale gia modificata e da GitHub aggiornato, senza cancellare database, storage documentale o configurazioni server.

## Obiettivo

Aggiornare solo il codice applicativo alpha sul server.

Devono restare intatti:

- database PostgreSQL;
- file caricati e generati dall'app;
- file `.env` del server;
- configurazioni Nginx/server fatte da IT.

### Coda DDT: deploy del codice distinto dal recupero dati

La funzione `DDT da certificare` conserva uno snapshot locale e richiede un
recupero storico iniziale. **Non copiare sul server le righe importate nel
database di sviluppo.** Il recupero Alpha deve usare esclusivamente la cache,
i certificati e il database Alpha, confrontati con la vista eSolver corrente.
Prima occorrono backup e dry-run Alpha in sola lettura; conflitti/duplicati
restano in verifica. L'importazione reale e l'attivazione di
`DDT_SNAPSHOT_ENABLED` sono due decisioni distinte, ciascuna con OK esplicito.
Lo script `backend/scripts/import_ddt_legacy_cache.py` è solo per il Compose
locale e non va lanciato su Alpha. Dettagli e controlli nel piano
`docs/tasks/ddt_certification_alert_queue_plan.md`, sezione «Passaggio futuro
su Alpha: dati propri, non copia del locale».

La scadenza visiva DDT usa `DDT_CERTIFICATION_DAYS` (default 7; giorni di
calendario, data DDT inclusa come giorno 1). Il parametro è passato dal Compose
Alpha; non occorre migrare dati per la scadenza. Preservare il valore server se
configurato e mantenerlo concordato con il termine eSolver. Il deploy non deve
attivare il job DDT, importare lo storico o cambiare la configurazione eSolver
implicitamente. Gli avvisi sono informativi, non confermano l'invio al cliente.

Aggiornamento 30/09 — **esclusioni manuali DDT**: il bootstrap aggiunge la tabella
`quarta_taglio_ddt_decisions`, senza ALTER sulle tabelle esistenti. Contiene
motivi/autori/date e storico di esclusioni, ripristini e riaperture per dati
modificati. Includerla nei normali backup PostgreSQL e conservarla nei rollback.
Verificare dopo deploy permessi admin Qualità e admin IT (estesi su richiesta
dell'utente il 30/09), vista Esclusi e conteggio sidebar.
Il report recupero passa a **versione 2** e controlla anche le decisioni:
rifare sempre preview; un vecchio report non è riutilizzabile. Nessuna
esclusione va importata dal database di sviluppo. Dettagli nel documento
`docs/tasks/ddt_manual_exclusions.md`.

#### Recupero DDT Alpha protetto (procedura pronta in locale, non ancora eseguita)

Comando dedicato: `backend/scripts/recover_ddt_alpha.py`; non usare quello locale.
Serve autorizzazione specifica al recupero, oltre a quella al deploy. La verifica
visiva integrata locale è completata; resta il collaudo sui dati Alpha: non attivare
il job come conseguenza automatica di questa procedura.

Ordine, nella finestra di manutenzione concordata:

1. Verificare run/caricamenti conclusi; sospendere accessi e writer applicativi.
   Fermare backend/frontend, non PostgreSQL. Non aprire la pagina Certificazione:
   un refresh della vecchia cache potrebbe rimuovere storico ancora da recuperare.
2. Fare/verificare backup DB **Alpha**, storage e app secondo questo documento,
   prima del cambio codice. Il backup deve appartenere a questa manutenzione.
3. Installare il pacchetto verificato come nel deploy soft ma **non eseguire ancora
   `up -d --build`**. Costruire la nuova immagine backend con `compose build backend`.
4. Eseguire `--preview` nel container one-off con configurazione/storage Alpha,
   senza avviare l'app. Presentare il report all'utente; solo dopo OK, `--apply`.
5. Confrontare il risultato con il report: quantità/chiavi, storico, PDF completati,
   duplicati esclusi. Poi riprendere l'avvio e le verifiche del normale deploy soft.
   Se non si prosegue con il recupero, lasciare il job disattivato e annotare che
   riaprire la vecchia app può aggiornare la cache. Non dichiarare recupero concluso.

Esempio di comandi **futuri**, dal server `/srv/certi_nt/app`, dopo backup e
sostituzione codice. Sostituire i nomi segnaposto con i file di questa esecuzione:

```bash
docker compose --env-file .env -f docker-compose.alpha.yml build backend

# Report nuovo: il comando non sovrascrive un file esistente.
docker compose --env-file .env -f docker-compose.alpha.yml run --rm --no-deps \
  -e DDT_SNAPSHOT_ENABLED=false \
  -v /srv/certi_nt/backup:/audit \
  backend python -m scripts.recover_ddt_alpha \
  --preview --report /audit/ddt_preview_TIMESTAMP.json

# Solo dopo esame/OK sul report, con accessi e writer ancora sospesi.
docker compose --env-file .env -f docker-compose.alpha.yml run --rm --no-deps \
  -e DDT_SNAPSHOT_ENABLED=false \
  -v /srv/certi_nt/backup:/audit:ro \
  backend python -m scripts.recover_ddt_alpha \
  --apply --report /audit/ddt_preview_TIMESTAMP.json \
  --maintenance-confirmed --backup /audit/db_before_alpha_TIMESTAMP.sql
```

Usare la forma `python -m scripts.recover_ddt_alpha` dalla directory `/app`
del container: l'esecuzione diretta del file non trova il package `app`.
L'avvio con `--help` è stato verificato nel container locale.

Lo script verifica ambiente Alpha, database `certi_nt`, host Compose `postgres`,
host pubblico e identità del cluster, e richiede il job disabilitato. Il report
scade dopo un'ora. Prima di scrivere rilegge vista eSolver e dati Alpha sotto lock:
se sono cambiati sorgente/cache/certificati/coda/file/codice, richiede nuova
preview e nuova verifica. Non riutilizzare il vecchio report dopo un'applicazione.
Un writer concorrente, sorgente non affidabile o errore annulla l'importazione;
anche la creazione delle tre tabelle DDT (quote, sincronizzazioni, decisioni) è
transazionale. I record ambigui restano
nella vecchia cache, esclusi dall'importazione automatica: non vengono eliminati
né sommati. Le righe correnti vengono aggiornate dalla sorgente corrente, lo
storico già conservato non viene sovrascritto dalla vecchia cache.

Il dump deve essere verificato realmente: il controllo automatico accerta solo
leggibilità/intestazione, non completezza/ripristinabilità. Il ruolo di manutenzione
deve poter leggere `pg_control_system()`; un errore va diagnosticato, non aggirato.
Non esporre report/backup sul web e non inserirli in Git. Il Compose Alpha attuale
non passa `DDT_SNAPSHOT_ENABLED` al backend: aggiungerlo solo con successiva
approvazione esplicita; scriverlo soltanto nel `.env` non attiva il job.

### Separazione obbligatoria della futura linea nuovi fornitori

Il futuro laboratorio per configurare nuovi fornitori non esiste ancora e non deve essere presente su Alpha durante il suo sviluppo.

Regola corrente:

```text
main                         → unica fonte autorizzata per i deploy Alpha
feature/supplier-lab         → futuro branch di sviluppo esclusivamente locale
```

Il nome `feature/supplier-lab` è riservato al futuro ramo: il branch non è ancora stato creato.

Durante lo sviluppo della linea generale:

- il codice Lab resta nel branch dedicato;
- il branch Lab non viene unito in `main`;
- il pacchetto `alpha-produzione` continua a essere generato esclusivamente da `origin/main`;
- route, API, tabelle, flag e storage Lab non devono essere installati su Alpha;
- i Markdown di analisi possono essere presenti in `main`: documentano il lavoro futuro ma non abilitano alcuna funzione;
- nessun controllo deve essere rimosso con la motivazione che la pagina sarebbe comunque nascosta agli utenti.

Quando il laboratorio sarà completo in locale serviranno, nell'ordine:

1. audit conclusivo e test di isolamento;
2. nuovo `procedi` esplicito dell'utente;
3. merge intenzionale del branch in `main`;
4. modifica intenzionale dei controlli di esclusione riportati in questo documento;
5. nuovo pacchetto e deploy Alpha;
6. laboratorio visibile solamente ad Admin IT e motore produttivo ancora disabilitato.

L'installazione futura del Lab su Alpha non autorizzerà automaticamente il suo utilizzo in Incoming. L'attivazione produttiva richiederà un'altra decisione separata.

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

## Parametri infrastrutturali Alpha verificati

Informazioni confermate da IT:

- DNS: `certi-test.forgialluminio.it` → `10.10.1.10`;
- frontend Alpha pubblicato localmente sulla porta host `8080`;
- backend Alpha pubblicato localmente sulla porta host `8001`;
- il 28 luglio 2026 PostgreSQL risultava disponibile soltanto nella rete Docker interna;
- il compose Alpha ora prevede un mapping host persistente e configurabile tramite `.env`;
- Nginx esistente instrada l'host `certi-test.forgialluminio.it` al frontend;
- Nginx instrada `certi-test.forgialluminio.it/api` al backend;
- pubblicazione applicativa attuale in HTTP, senza HTTPS;
- backup della VM ogni quattro ore, dalle 07:00 alle 19:00.

Parametri Nginx confermati da IT:

```nginx
client_max_body_size 200m;
proxy_connect_timeout 300s;
proxy_send_timeout 300s;
proxy_read_timeout 300s;
```

Queste impostazioni appartengono alla configurazione server gestita da IT e devono restare
intatte durante un deploy soft.

### Mapping PostgreSQL persistente

Il mapping della porta PostgreSQL fa parte di `docker-compose.alpha.yml` e usa:

```dotenv
POSTGRES_BIND_HOST=127.0.0.1
POSTGRES_HOST_PORT=5432
```

Con `127.0.0.1` PostgreSQL è raggiungibile soltanto dal server Alpha. È l'impostazione sicura
da usare finché IT non ha verificato firewall, IP sorgente e utenti read-only.

Per rendere disponibile la vista a eSolver/Nemesi, dopo la conferma di Matteo:

```dotenv
POSTGRES_BIND_HOST=10.10.1.10
POSTGRES_HOST_PORT=5432
```

Il collegamento diventa:

```text
10.10.1.10:5432 -> container postgres:5432
```

Questi valori stanno nel `.env` del server, che il deploy soft preserva. Non aggiungere il
mapping manualmente al compose presente soltanto sul server: il file viene sostituito dal
pacchetto e la modifica andrebbe persa al deploy successivo.

Non impostare `POSTGRES_BIND_HOST=0.0.0.0`. Prima di usare `10.10.1.10` devono essere
confermati:

- firewall TCP `5432` limitato agli IP di Nemesi/eSolver e Quarta;
- ruoli PostgreSQL dedicati in sola lettura;
- assenza di accesso alle tabelle applicative;
- modalità SSL concordata con IT.

SSH dal PC locale, usando PowerShell:

```powershell
ssh -i "$env:USERPROFILE\.ssh\certi_nt_admcerti01_ed25519" admcerti01@certi-test.forgialluminio.it
```

La chiave da usare qui e la chiave privata locale `certi_nt_admcerti01_ed25519`, non il file `.pub`.

Non inserire password SSH in questo documento, nel repository o nei pacchetti di deploy.
L'accesso deve usare la chiave locale oppure un secret gestito fuori dal repository.

Se PowerShell crea problemi di quoting con comandi lunghi, usare anche la forma con path esplicito:

```powershell
ssh -i C:\Users\sireb\.ssh\certi_nt_admcerti01_ed25519 admcerti01@certi-test.forgialluminio.it
```

## Flusso corretto

1. Sviluppo e test in locale sul ramo corretto.
2. Verifica che il deploy corrente provenga da `main` e non dal futuro branch Lab.
3. Verifica che il commit `main` non contenga il modulo Lab non ancora autorizzato.
4. Commit e push del repo app.
5. Registrazione del commit app esatto in `alpha-produzione/SOURCE_COMMIT`.
6. Rigenerazione completa di `alpha-produzione` dal commit app, senza copie parziali e senza file non tracciati.
7. Confronto integrale tra commit app e pacchetto deploy.
8. Verifica che backend, footer e bundle frontend riportino la stessa versione.
9. Test del contenuto del pacchetto deploy.
10. Commit, push e tag del repo deploy.
11. Creazione archivio `.tar` pulito dalla cartella `alpha-produzione`.
12. Copia archivio sul server in `/srv/certi_nt/backup`.
13. Backup dell'app server attuale.
14. Sostituzione soft del codice, preservando `.env`, database e storage.
15. Verifica dei parametri PostgreSQL preservati nel `.env`.
16. Avvio Docker.
17. Verifica del contenuto, delle versioni, dell'assenza del Lab non autorizzato e del mapping PostgreSQL realmente installati.

## Prima di aggiornare

Controllare che il server sia sano:

```bash
cd /srv/certi_nt/app
docker compose --env-file .env -f docker-compose.alpha.yml ps
test -f .env
test -d /srv/certi_nt/data/postgres
test -d /srv/certi_nt/data/storage
grep -E '^POSTGRES_(BIND_HOST|HOST_PORT)=' .env || true
```

Non procedere se:

- manca `.env`;
- PostgreSQL non e attivo o non e healthy;
- mancano le cartelle `data/postgres` o `data/storage`;
- l'app e in mezzo a un caricamento importante.

Se i due parametri PostgreSQL non sono ancora presenti, aggiungerli al `.env` prima di
installare la versione del compose che contiene il mapping. Usare `127.0.0.1` finché Matteo
non ha confermato l'apertura controllata verso Nemesi:

```dotenv
POSTGRES_BIND_HOST=127.0.0.1
POSTGRES_HOST_PORT=5432
```

Se è già prevista la pubblicazione esterna, verificare prima che la porta host scelta non sia
occupata:

```bash
ss -ltn | grep ':5432 ' || true
```

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

Alternativa piu semplice via PostgreSQL, utile quando il quoting Python da PowerShell diventa fragile:

```bash
cd /srv/certi_nt/app
docker compose --env-file .env -f docker-compose.alpha.yml exec -T postgres \
  psql -U certi_nt -d certi_nt \
  -c "select id, stato, fase_corrente from acquisition_processing_runs where stato in ('in_coda', 'in_esecuzione') order by id desc limit 10;"
```

Se torna `(0 rows)`, non ci sono run attivi.

## Allineamento obbligatorio tra app e pacchetto deploy

Il pacchetto non deve essere aggiornato copiando soltanto i file dell'ultima modifica e non deve essere creato copiando la cartella di lavoro locale. Entrambi i metodi hanno gia prodotto pacchetti incompleti o contenenti file temporanei.

La fonte del pacchetto deve essere un commit preciso e gia pubblicato del repo app. Quel commit deve essere scritto in:

```text
alpha-produzione/SOURCE_COMMIT
```

Sono ammessi nel pacchetto soltanto:

- tutti i file tracciati dal commit app indicato in `SOURCE_COMMIT`, con contenuto identico;
- `README_ALPHA.md`, specifico del repository deploy;
- `SOURCE_COMMIT`, contenente l'hash completo del commit app.

Qualsiasi altro file deve bloccare la creazione del tag.

### Perche questo controllo e obbligatorio

Audit del 21 luglio 2026:

- il backend del pacchetto `alpha.9.5` riportava `0.1.0.alpha.9.5`, ma il footer riportava ancora `0.1.0.alpha.9.4`;
- il pacchetto conteneva 518 file di lavoro sotto `backend/tmp` e `backend/tmp_eval`, per circa 244 MiB;
- due file di documentazione non tracciati dal repo app erano entrati nel deploy;
- nei pacchetti `alpha.9.1` e `alpha.9.2` erano rimasti temporaneamente file backend diversi dal commit app disponibile al momento del tag.

Le cause individuate sono:

- sincronizzazione manuale per elenco parziale di file;
- copia dalla working tree invece che da un commit Git;
- assenza dell'hash del commit sorgente nel pacchetto;
- assenza di un confronto completo tra i due alberi Git;
- verifica della sola versione backend, senza controllare footer e bundle frontend.

### Generare il pacchetto da un commit pulito

Da PowerShell usare una directory temporanea generata esclusivamente da `git archive`. Il comando include solo file tracciati dal commit scelto e non puo quindi includere PDF, immagini, cache o script temporanei presenti nella working tree.

```powershell
$appRepo = 'C:\Users\sireb\VScodeProjects\certi_nt'
$deployRepo = 'C:\Users\sireb\VScodeProjects\certi_nt\deploy_repo\certi_nt_deploy'
$alphaDir = Join-Path $deployRepo 'alpha-produzione'
$expectedAlphaDir = 'C:\Users\sireb\VScodeProjects\certi_nt\deploy_repo\certi_nt_deploy\alpha-produzione'

$sourceCommit = (git -C $appRepo rev-parse HEAD).Trim()
$remoteCommit = (git -C $appRepo rev-parse origin/main).Trim()
$currentBranch = (git -C $appRepo branch --show-current).Trim()
if ($currentBranch -ne 'main') {
    throw "Deploy Alpha vietato dal branch '$currentBranch': usare esclusivamente main."
}
if ($sourceCommit -ne $remoteCommit) {
    throw 'Il commit app locale non coincide con origin/main: fare push prima del deploy.'
}
git -C $appRepo diff --quiet
if ($LASTEXITCODE -ne 0) {
    throw 'Il repo app contiene modifiche tracciate non committate.'
}
git -C $appRepo diff --cached --quiet
if ($LASTEXITCODE -ne 0) {
    throw 'Il repo app contiene modifiche in staging non committate.'
}

# Protezione temporanea: resta obbligatoria finche il laboratorio nuovi fornitori
# non e completo, approvato e autorizzato per la prima installazione Alpha.
$forbiddenLabPaths = @(
    'backend/app/modules/supplier_lab',
    'frontend/src/pages/supplierLab'
)
foreach ($relativePath in $forbiddenLabPaths) {
    if (Test-Path -LiteralPath (Join-Path $appRepo $relativePath)) {
        throw "Modulo Lab non ancora autorizzato presente in main: $relativePath"
    }
}

$labMarkers = @(
    git -C $appRepo grep -n -E `
      'app/modules/supplier_lab|app\.modules\.supplier_lab|/supplier-lab|SUPPLIER_LAB_ENABLED|GENERAL_SUPPLIER_RUNTIME_ENABLED' `
      $sourceCommit -- backend/app frontend/src docker-compose.alpha.yml 2>$null
)
if ($LASTEXITCODE -eq 0 -and $labMarkers.Count) {
    $labMarkers | ForEach-Object { Write-Host "Riferimento Lab non autorizzato: $_" }
    throw 'Il commit main contiene codice o configurazione Lab non ancora autorizzati per Alpha.'
}
if ($LASTEXITCODE -notin @(0, 1)) {
    throw 'Controllo riferimenti Lab fallito.'
}

$shortCommit = $sourceCommit.Substring(0, 12)
$stageDir = Join-Path $deployRepo ".alpha-stage-$shortCommit"
$sourceArchive = Join-Path $deployRepo ".alpha-source-$shortCommit.tar"
if (Test-Path -LiteralPath $stageDir) {
    throw "Directory temporanea gia presente: $stageDir"
}
if (Test-Path -LiteralPath $sourceArchive) {
    throw "Archivio temporaneo gia presente: $sourceArchive"
}

New-Item -ItemType Directory -Path $stageDir | Out-Null
git -C $appRepo archive --format=tar --output=$sourceArchive $sourceCommit
if ($LASTEXITCODE -ne 0) { throw 'git archive del repo app fallito.' }
tar -xf $sourceArchive -C $stageDir
if ($LASTEXITCODE -ne 0) { throw 'Estrazione del commit app fallita.' }

Copy-Item -LiteralPath (Join-Path $alphaDir 'README_ALPHA.md') -Destination $stageDir
Set-Content -LiteralPath (Join-Path $stageDir 'SOURCE_COMMIT') -Value $sourceCommit -NoNewline

$forbiddenPaths = @(
    '.env',
    'backend/tmp',
    'backend/tmp_eval',
    'backend/storage',
    'frontend/node_modules',
    'frontend/dist'
)
foreach ($relativePath in $forbiddenPaths) {
    if (Test-Path -LiteralPath (Join-Path $stageDir $relativePath)) {
        throw "Contenuto vietato nel pacchetto: $relativePath"
    }
}

if ([IO.Path]::GetFullPath($alphaDir) -ne [IO.Path]::GetFullPath($expectedAlphaDir)) {
    throw "Target alpha non valido: $alphaDir"
}

robocopy $stageDir $alphaDir /MIR /R:1 /W:1 /NFL /NDL /NJH /NJS /NP
$copyExitCode = $LASTEXITCODE
if ($copyExitCode -gt 7) {
    throw "Sincronizzazione alpha fallita con codice robocopy $copyExitCode"
}

Remove-Item -LiteralPath $stageDir -Recurse -Force
Remove-Item -LiteralPath $sourceArchive -Force
git -C $deployRepo status --short
```

`robocopy /MIR` elimina dal solo percorso validato `alpha-produzione` i file che non appartengono al nuovo pacchetto. Non riutilizzare il comando cambiando il target senza ripetere il controllo del percorso assoluto.

Prima di continuare, controllare che lo stato del repo deploy mostri soltanto l'allineamento previsto. In particolare non devono comparire file sotto `backend/tmp`, `backend/tmp_eval`, storage, cache o build locali.

### Verificare integralmente i due alberi Git

Dopo il commit locale del repo deploy, ma prima di tag e push, eseguire questo controllo. Non basta verificare soltanto i file modificati nell'ultimo commit.

```powershell
$appRepo = 'C:\Users\sireb\VScodeProjects\certi_nt'
$deployRepo = 'C:\Users\sireb\VScodeProjects\certi_nt\deploy_repo\certi_nt_deploy'
$sourceCommit = (git -C $appRepo rev-parse HEAD).Trim()
$deployCommit = (git -C $deployRepo rev-parse HEAD).Trim()

function Read-GitTree([string]$repo, [string]$tree) {
    $result = @{}
    foreach ($line in (git -C $repo ls-tree -r $tree)) {
        if ($line -match '^\d+ blob ([0-9a-f]+)\t(.+)$') {
            $result[$Matches[2]] = $Matches[1]
        }
    }
    return $result
}

$sourceTree = Read-GitTree $appRepo $sourceCommit
$deployTree = Read-GitTree $deployRepo "${deployCommit}:alpha-produzione"
$allowedDeployOnly = @('README_ALPHA.md', 'SOURCE_COMMIT')

$missingFromDeploy = @(
    $sourceTree.Keys |
        Where-Object { -not $deployTree.ContainsKey($_) } |
        Sort-Object
)
$differentContent = @(
    $sourceTree.Keys |
        Where-Object { $deployTree.ContainsKey($_) -and $sourceTree[$_] -ne $deployTree[$_] } |
        Sort-Object
)
$unexpectedInDeploy = @(
    $deployTree.Keys |
        Where-Object { -not $sourceTree.ContainsKey($_) -and $allowedDeployOnly -notcontains $_ } |
        Sort-Object
)

$recordedSource = (git -C $deployRepo show "${deployCommit}:alpha-produzione/SOURCE_COMMIT").Trim()
if ($recordedSource -ne $sourceCommit) {
    throw "SOURCE_COMMIT non valido: atteso $sourceCommit, trovato $recordedSource"
}

if ($missingFromDeploy.Count -or $differentContent.Count -or $unexpectedInDeploy.Count) {
    $missingFromDeploy | ForEach-Object { Write-Host "Manca nel deploy: $_" }
    $differentContent | ForEach-Object { Write-Host "Contenuto diverso: $_" }
    $unexpectedInDeploy | ForEach-Object { Write-Host "File inatteso nel deploy: $_" }
    throw 'Pacchetto deploy non allineato: non creare tag e non fare push.'
}

Write-Host "Pacchetto allineato al commit app $sourceCommit"
```

Il confronto usa gli hash Git dei blob, quindi rileva anche differenze non visibili con un semplice elenco di nomi.

### Verificare versione backend, footer e bundle

La stessa versione deve essere presente nel backend e nel footer prima della build:

```powershell
$backendFile = Join-Path $appRepo 'backend/app/main.py'
$footerFile = Join-Path $appRepo 'frontend/src/components/layout/Footer.jsx'
$backendMatch = Select-String -LiteralPath $backendFile -Pattern 'version="([^"]+)"'
$footerMatch = Select-String -LiteralPath $footerFile -Pattern 'Versione sistema ([0-9A-Za-z._-]+)'

if (-not $backendMatch -or -not $footerMatch) {
    throw 'Versione backend o footer non trovata.'
}

$backendVersion = $backendMatch.Matches[0].Groups[1].Value
$footerVersion = $footerMatch.Matches[0].Groups[1].Value
if ($backendVersion -ne $footerVersion) {
    throw "Versioni disallineate: backend=$backendVersion footer=$footerVersion"
}
```

Costruire poi il frontend dal pacchetto, non dalla sola cartella app:

```powershell
Push-Location (Join-Path $deployRepo 'alpha-produzione/frontend')
try {
    npm ci
    if ($LASTEXITCODE -ne 0) { throw 'Installazione dipendenze frontend del pacchetto fallita.' }
    npm run build
    if ($LASTEXITCODE -ne 0) { throw 'Build frontend del pacchetto fallita.' }
    $expectedText = "Versione sistema $footerVersion"
    $bundleMatch = Get-ChildItem -LiteralPath 'dist' -Recurse -File |
        Select-String -SimpleMatch $expectedText |
        Select-Object -First 1
    if (-not $bundleMatch) {
        throw "Il bundle frontend non contiene: $expectedText"
    }
}
finally {
    Pop-Location
}
```

Se uno qualsiasi di questi controlli fallisce, non creare il tag e non trasferire l'archivio.

## Creare archivio dal deploy repo

Dal PC locale, nel repo deploy:

```powershell
cd C:\Users\sireb\VScodeProjects\certi_nt\deploy_repo\certi_nt_deploy
git status
git add alpha-produzione
git diff --cached --check
git commit -m "Update alpha deploy package 0.1.0.alpha.X"
```

Eseguire ora il confronto integrale e i controlli versione descritti nella sezione precedente. Solo se terminano senza errori creare tag e archivio:

```powershell
git tag v0.1.0-alpha.X-deploy
git archive --format=tar --output alpha-produzione-v0.1.0-alpha.X-deploy.tar v0.1.0-alpha.X-deploy:alpha-produzione

$archive = 'alpha-produzione-v0.1.0-alpha.X-deploy.tar'
$archiveEntries = @(tar -tf $archive)
$forbiddenEntries = @(
    $archiveEntries | Where-Object {
        $_ -match '(^|/)(tmp|tmp_eval|storage|node_modules|dist|__pycache__)(/|$)' -or
        $_ -eq '.env'
    }
)
if ($forbiddenEntries.Count) {
    $forbiddenEntries | ForEach-Object { Write-Host "Contenuto vietato nell'archivio: $_" }
    throw 'Archivio deploy non pulito.'
}
if ($archiveEntries -notcontains 'SOURCE_COMMIT') {
    throw "SOURCE_COMMIT manca dall'archivio deploy."
}

$archiveSize = (Get-Item -LiteralPath $archive).Length
if ($archiveSize -gt 50MB) {
    throw "Archivio insolitamente grande: $archiveSize byte. Verificare prima del trasferimento."
}

Get-FileHash -Algorithm SHA256 -LiteralPath $archive
git push origin main
git push origin v0.1.0-alpha.X-deploy
```

`X` va sostituito con il numero reale della versione.

Se il tag esiste gia e si scopre che non rappresenta il pacchetto corretto, non spostare il tag con force push.
Creare invece un tag progressivo, per esempio `v0.1.0-alpha.6.1-deploy`.
In quel caso la versione applicativa resta `0.1.0.alpha.6`, mentre il suffisso `.1` indica solo il pacchetto deploy aggiornato.

Gli archivi `.tar` creati localmente servono solo per il trasferimento sul server. Possono rimanere non tracciati nel repo deploy e non vanno aggiunti al commit.

La soglia di 50 MiB e intenzionalmente superiore alla dimensione normale osservata del codice. Non aumentarla per far passare il controllo: prima identificare e documentare quali file hanno aumentato il pacchetto.

## Copiare archivio sul server

Da PowerShell locale:

```powershell
scp -i "$env:USERPROFILE\.ssh\certi_nt_admcerti01_ed25519" `
  C:\Users\sireb\VScodeProjects\certi_nt\deploy_repo\certi_nt_deploy\alpha-produzione-v0.1.0-alpha.X-deploy.tar `
  admcerti01@certi-test.forgialluminio.it:/srv/certi_nt/backup/
```

Confrontare sempre SHA-256 locale e server prima di estrarre:

```powershell
(Get-FileHash -Algorithm SHA256 `
  C:\Users\sireb\VScodeProjects\certi_nt\deploy_repo\certi_nt_deploy\alpha-produzione-v0.1.0-alpha.X-deploy.tar).Hash

ssh -i "$env:USERPROFILE\.ssh\certi_nt_admcerti01_ed25519" `
  admcerti01@certi-test.forgialluminio.it `
  'sha256sum /srv/certi_nt/backup/alpha-produzione-v0.1.0-alpha.X-deploy.tar'
```

I due hash devono essere identici, ignorando maiuscole e minuscole. Se non coincidono, non proseguire.

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

**Se è autorizzato anche il primo recupero DDT**, applicare la variante sopra:
backup con writer fermi e pausa prima del comando finale `up -d --build`, per
preview/import con la nuova immagine. Non avviare prima l'app, che aggiorna la
cache utilizzata per recuperare lo storico.

Sul server:

```bash
set -e
TAG=v0.1.0-alpha.X-deploy
ARCHIVE=alpha-produzione-${TAG}.tar
EXPECTED_SOURCE_COMMIT=HASH_COMPLETO_COMMIT_APP
TS=$(date +%Y%m%d_%H%M%S)

cd /srv/certi_nt
test -f "backup/$ARCHIVE"
test -f app/.env
test -d data/postgres
test -d data/storage
test "$(tar -xOf "backup/$ARCHIVE" SOURCE_COMMIT)" = "$EXPECTED_SOURCE_COMMIT"

tar -czf "backup/app_before_${TAG}_${TS}.tgz" app

cd app
test "$(pwd -P)" = "/srv/certi_nt/app"
docker compose --env-file .env -f docker-compose.alpha.yml stop backend frontend

find . -mindepth 1 -maxdepth 1 ! -name .env -exec rm -rf {} +
tar -xf "../backup/$ARCHIVE" -C .
test "$(cat SOURCE_COMMIT)" = "$EXPECTED_SOURCE_COMMIT"

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
docker port app-postgres-1 5432/tcp
ss -ltn | grep ':5432 '
curl -I http://127.0.0.1:8080/
curl -I http://127.0.0.1:8001/docs
```

Il controllo PostgreSQL deve corrispondere al valore conservato nel `.env`:

- con `POSTGRES_BIND_HOST=127.0.0.1` deve comparire `127.0.0.1:5432`;
- con `POSTGRES_BIND_HOST=10.10.1.10` deve comparire `10.10.1.10:5432`;
- se `docker port` non restituisce il mapping previsto, il deploy non è concluso;
- non correggere il compose direttamente sul server: correggere configurazione tracciata o
  `.env`, poi ricreare il servizio.

Quando la vista eSolver è attiva, controllare inoltre che il ruolo read-only esista ancora e
che la vista sia presente:

```bash
docker compose --env-file .env -f docker-compose.alpha.yml exec -T postgres \
  psql -U certi_nt -d certi_nt -P pager=off \
  -c "select to_regclass('esolver_export.certi_certificati_pdf') as export_view;" \
  -c "select rolname from pg_roles where rolname in ('certi_esolver_reader', 'certi_quarta_reader');"
```

La query non mostra password. I nomi effettivi dei ruoli devono essere aggiornati nel comando
se Matteo sceglie nomi diversi.

Controllare che i file installati corrispondano all'archivio. Le differenze di UID e GID sono normali nel passaggio da archivio Windows a server Linux; qualsiasi altra differenza deve bloccare la chiusura del deploy:

```bash
set -e
TAG=v0.1.0-alpha.X-deploy
ARCHIVE=alpha-produzione-${TAG}.tar
EXPECTED_SOURCE_COMMIT=HASH_COMPLETO_COMMIT_APP

cd /srv/certi_nt/app
test "$(cat SOURCE_COMMIT)" = "$EXPECTED_SOURCE_COMMIT"
test ! -e backend/tmp
test ! -e backend/tmp_eval
test ! -e backend/app/modules/supplier_lab
test ! -e frontend/src/pages/supplierLab
! grep -R -E 'SUPPLIER_LAB_ENABLED|GENERAL_SUPPLIER_RUNTIME_ENABLED' \
  backend/app frontend/src docker-compose.alpha.yml

content_differences=$(
  tar --compare \
    --file="/srv/certi_nt/backup/$ARCHIVE" \
    --directory=/srv/certi_nt/app 2>&1 |
  grep -Ev ': (Uid|Gid) differs$' || true
)
if [ -n "$content_differences" ]; then
  printf '%s\n' "$content_differences"
  exit 1
fi
```

Controllare insieme versione backend e versione realmente incorporata nel bundle frontend servito da Nginx:

```bash
cd /srv/certi_nt/app
BACKEND_VERSION=$(
  docker compose --env-file .env -f docker-compose.alpha.yml exec -T backend \
    python -c "from app.main import app; print(app.version)"
)
FRONTEND_VERSION=$(
  docker compose --env-file .env -f docker-compose.alpha.yml exec -T frontend \
    grep -Roh 'Versione sistema 0.1.0.alpha.[0-9.]*' /usr/share/nginx/html |
    sed 's/^Versione sistema //' |
    sort -u
)

printf 'Backend: %s\nFrontend: %s\n' "$BACKEND_VERSION" "$FRONTEND_VERSION"
test "$BACKEND_VERSION" = "$FRONTEND_VERSION"
```

Entrambi devono riportare la versione appena installata, per esempio:

```text
Backend: 0.1.0.alpha.9.5
Frontend: 0.1.0.alpha.9.5
```

### Controlli HTTP pubblici

Dal PC locale, se la rete/VPN lo consente:

```powershell
C:\Windows\System32\curl.exe -I -s http://certi-test.forgialluminio.it/
C:\Windows\System32\curl.exe -I -s http://certi-test.forgialluminio.it/api/auth/me
```

Interpretazione:

- `/` deve rispondere `200 OK`: frontend pubblico raggiungibile;
- `/api/auth/me` con `HEAD` puo rispondere `405 Method Not Allowed` con `allow: GET`: e comunque utile, perche dimostra che la richiesta arriva al backend attraverso Nginx;
- non usare `/api/docs` come controllo: puo rispondere `404` perche la documentazione FastAPI non e esposta sotto `/api/docs`;
- non usare `/docs` come prova backend pubblica: puo essere servito dal frontend, quindi non dimostra che il proxy API funzioni.

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

- preparare `alpha-produzione` copiando soltanto i file dell'ultimo commit;
- copiare nel deploy la working tree locale invece del contenuto di un commit Git;
- creare o pubblicare il tag prima del confronto integrale tra app e deploy;
- accettare file deploy aggiuntivi diversi da `README_ALPHA.md` e `SOURCE_COMMIT`;
- creare un pacchetto Alpha dal futuro branch `feature/supplier-lab` o da qualsiasi branch diverso da `main`;
- unire o installare il modulo Lab prima dell'audit conclusivo e del nuovo `procedi` esplicito;
- rimuovere i controlli temporanei di esclusione Lab senza autorizzazione;
- includere `backend/tmp`, `backend/tmp_eval`, `.env`, storage, cache, `node_modules` o `dist` nell'archivio;
- verificare soltanto `app.version` senza controllare anche il bundle frontend servito;
- cancellare `/srv/certi_nt/data`;
- cancellare `/srv/certi_nt/data/postgres`;
- cancellare `/srv/certi_nt/data/storage`;
- sovrascrivere `.env`;
- aggiungere il mapping PostgreSQL soltanto al compose presente sul server;
- esporre PostgreSQL su `0.0.0.0`;
- concludere il deploy senza verificare `docker port app-postgres-1 5432/tcp`;
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
