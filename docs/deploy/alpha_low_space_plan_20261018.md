# Alpha — piano di deploy con backup esterni, 18/10/2026

Stato: piano, NON esecuzione del deploy. Integra il runbook soft update senza
revocare controlli, autorizzazioni, backup o protezioni del lavoro utenti.
L'utente ha chiesto recupero dello spazio storico già proposto e poi un piano
che minimizzi l'occupazione; non si esegue qui l'aggiornamento applicativo.

**Ripresa operativa successiva:** l'utente ha poi autorizzato il deploy. Esiti
e incidente del backup nel [verbale 18/10](alpha10_2_preflight_20261018.md).
Deploy completato: primo ciclo automatico e confronto finale dati/file superati;
spazio residuo circa 1,95 GB. Questo piano resta storico, non un'autorizzazione
a ripetere pulizie o manutenzioni già effettuate.
In particolare gli stream binari da container richiedono `--log-driver none`:
il logging predefinito può consumare il disco anche con destinazione esterna.
Non considerare questo piano iniziale prova di deploy completato.

## Perimetro del recupero autorizzato

- Vecchia directory `/srv/certi_nt/data/storage_before_hard_reset_20260715_080925`:
  copia ridondante di 815 file, confronto completo con il relativo archivio,
  nessun mount container e nessun riferimento al nome della directory nei 16
  campi file/percorso verificati nel DB Alpha in transazione READ ONLY.
- Tre archivi `app_before` di luglio, precisamente 9.5 del 20/07 20:37:30,
  9.5.1 del 21/07 09:25:54, 9.5.2 del 21/07 10:50:00. Contengono anche `.env`:
  backup privati, non temporanei, mai Git o allegati mail.
- Prima di rimuovere qualunque copia server: trasferimento PC, SHA-256 identico,
  controllo gzip/tar, leggibilità di tutti i membri e percorsi di ripristino.
  Copie PC in `backups/alpha_space_20261018`, esclusa da Git e con ACL limitata
  all'utente Windows. L'archivio dello storage storico RESTA anche sul server.
- Nuova verifica immediata di hash, contenuti della directory, percorsi risolti,
  file regolari, mount, riferimenti e usi. Se differiscono, fermarsi.
- Conservare storage operativo, DB, backup recenti 01/10 e 09/10, log, swap,
  cache dipendenze, tutte le immagini e altro stack `/srv/certi`.
- Trasferire indietro gli archivi PC consente ripristino; lo storage storico si
  ripristina dal suo archivio anche sul server. Non è eliminazione dell'unica copia.

## Variante a basso consumo per il prossimo deploy

Esito del recupero: tre archivi applicativi rimossi dal server solo dopo
verifica delle copie PC, 728.580.096 byte fisici recuperati; disponibili
2.094.161.920 byte (circa 2,09 GB). La directory storage storica NON è stata
rimossa: tentativo negato dai permessi root, 815 file e 664.986.000 byte di
contenuto verificati ancora tutti presenti dopo l'errore. Nessun aggiramento
dei privilegi, chmod/chown o cancellazione tramite container. Anche il suo
archivio è conservato sia sul PC sia sul server. I 665 MB non vanno conteggiati
come spazio recuperato. Per liberare questa copia serve IT.

1. Confermare commit main pubblicato, pacchetto integrale, esclusione Lab,
   versione, test e tutte le preview C/D del runbook. Non ripetere vecchi recuperi.
2. Preparare PRIMA un trasferimento binario sicuro server-PC con file di prova,
   hash e gestione dell'errore. Non usare redirezione PowerShell testuale per
   tar, gzip o dump binari. Destinazione privata fuori Git, spazio PC e ACL verificati.
3. Concordare finestra, controllare utenti/AI/Word/PDF/job, fermare soltanto
   writer Alpha come da runbook. PostgreSQL e altro stack rimangono attivi.
4. Con un solo TS creare backup coerenti app/.env, pg_dump e storage direttamente
   sul PC tramite stream binario: NON un nuovo archivio da 1,7 GB sul disco root.
   Registrare anche manifest dei file sorgenti. Un trasferimento interrotto non
   vale come backup; non cambiare codice/schema fino a completamento e verifica.
5. Verificare hash, completamento dump, gzip/tar, tutti i file/manifest e restore
   del DB in PostgreSQL isolato sul PC. Provare ripristino documentale isolato.
   Non provare restore su Alpha e non esporre i backup via Git/web/mail.
6. Conservare immagini attuali per rollback. Preparare backend/frontend coerenti
   senza avvio, in sequenza, evitando build parallele e `--no-cache`/pull forzati.
   Dockerfile, requirements e package/lock confrontati: contenuto normalizzato
   uguale ad Alpha al 18/10, ma byte CRLF/LF diversi: NON è garanzia di cache-hit.
   Anche il tag base può risolversi a digest diverso: verificare prima. Non
   modificare file tracciati o packaging per forzare il riuso della cache.
7. Budget attuale dopo recupero: circa 2,09 GB decimali, NON i 2,76 GB stimati
   includendo la directory protetta. Il pacchetto codice è dell'ordine di decine
   di MB. Consentire al massimo circa 1 GB di crescita complessiva temporanea
   a pacchetto/immagini/build e lasciare almeno 1 GB libero.
   È un budget operativo, NON una garanzia. Monitorare continuamente `df` e
   processi build; arrestare la build se il margine scende verso 1 GB o se emerge
   una ricostruzione non compatibile col budget. Se non si può confermare il
   riuso degli strati pesanti delle dipendenze, NON iniziare la build ridotta:
   richiedere prima lo spazio aggiuntivo IT. Nessuna pulizia automatica di
   immagini/file per farla finire. Con writer già fermi, concordare la ripresa
   dell'Alpha precedente se non si può proseguire, prima di migrazioni/nuovo avvio.
8. Solo dopo immagini collaudate, backup validi e margine: preparazione additiva
   `word_reference` con app/job fermi come da sezione C/D, niente backfill,
   adozioni storiche o rigenerazioni massive. Verifiche dati, file, PDF ed export.
9. Riaprire con pacchetto coerente, flag snapshot/riuso preservati, controlli
   health, permessi, timer e spazio. Non generare PDF reali per collaudo.
   I Word storici ambigui richiedono scelta utente, non correzione automatica.
10. Rollback codice/schema additivo e tutela dei nuovi dati come da runbook.
    Backup PC disponibili e recuperabili per tutta la finestra; nessuna pulizia
    dei backup o delle immagini di sicurezza per chiudere il deploy.

L'estensione del volume rimane raccomandata per l'esercizio futuro: questa
variante limita il picco temporaneo, non risolve la crescita di documenti/backup.
Qualunque uso del disco `/srv/certi` richiede accordo IT e verifica dei permessi;
nessuno spostamento implicito dell'app su quel disco.

## Preflight ripresa 18/10, 16:39 UTC — nessuna manutenzione avviata

SSH di nuovo raggiungibile, frontend HTTP 200, circa 2,09 GB liberi, nessun
run AI in coda/esecuzione, nessuna build e nessuna richiesta nei tre minuti
di log backend controllati. Colonna `word_reference` ancora assente, atteso.
Codice main pubblicato `f504dd3443b14abeb6a3532349e1c09feed10cc8`;
le successive note di spazio/deploy sono ancora modifiche documentali locali.

Controllo manifest senza pull di layer: Python 3.11-slim e nginx 1.27-alpine
coincidono con i digest della cache precedente. **Node 24-alpine no**:
cache `sha256:ebfe2f90462722a7a4de65e91990e97fe0d401c70e0e762c5b53302f905ec1c1`,
tag attuale `sha256:44fce696f38ba8c987c4db89954051000bbd05ffd8d8659ba15ed4a8602e937f`.
Quindi una build ordinaria può scaricare una nuova base e ricostruire le
dipendenze frontend: non dichiarare confermato il riuso completo della cache.
Nessuno stop, backup nuovo, installazione, build o migrazione eseguiti.
Prima di procedere, concordare e collaudare una variante che conservi la base
frontend già verificata, oppure ottenere più spazio; non modificare Dockerfile
o packaging di nascosto per superare il controllo.

### Variante approvata successivamente

L'utente ha approvato l'uso della base Node precedente e il successivo
commit/push della modifica e delle note. `frontend/Dockerfile.alpha` ora
fissa `node:24-alpine` al digest della cache 09/10 indicato sopra. Nessun
aggiornamento delle dipendenze applicative. Build immagine Linux locale
con il digest fissato riuscita; anche build Vite locale riuscita. Restano
gli avvisi npm sulle dipendenze esistenti (16 vulnerabilità nel collaudo
immagine); non eseguire audit fix o aggiornamenti automatici nel deploy.
Questo supera il fermo sul tag Node mobile, non i restanti controlli:
pacchetto da commit pubblicato, backup esterni e restore, budget/monitoraggio
build reale e preparazione schema controllata ancora obbligatori.

## Pulizia PC e rotazione futura — conferma utente 18/10

Dopo completamento e verifica del deploy, pulire soltanto i temporanei creati
per il lavoro, con inventario e target controllati. Non confonderli con le
copie private in `backups/alpha_space_20261018` o i nuovi backup di sicurezza.
Conservarle ora; quando arriveranno altri backup completi verificati, rivalutare
e proporre all'utente quali vecchie copie possano essere eliminate. Servono
copertura dei contenuti storici/configurazioni, verifica delle copie residue e
OK specifico: la sola data più recente non prova che un backup sostituisca il
precedente. Tenere nel runbook traccia di sostituzioni, hash/ubicazioni e rimozioni.
