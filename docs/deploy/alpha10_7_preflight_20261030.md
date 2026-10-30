# Alpha 10.7 — preparazione 30/10/2026

## Stato: COMPLETATO — Alpha 10.7 riaperta, timer e pulizia PC verificati

L'utente ha richiesto il deploy. Questa fase non ha fermato servizi, installato
codice nell'app operativa o modificato dati/schema Alpha. Sono stati creati
soltanto pacchetto, staging privato, immagine candidata e report di anteprima.
Prima delle scritture serve approvazione della preview corrente, backup
app/DB/storage coerenti e restore isolato verificato, secondo il runbook.

- Sorgente app pubblicato: fc1d1f74effc7b38a61f15b1bdbf275a91eb0367.
- Commit deploy: 8c0f33e19c6a713cc4c5dda9f320a5cd0de5f7ec.
- Tag pubblicato immutabile: v0.1.0-alpha.10.7-deploy.
- Archivio: 12.728.320 byte, SHA256
  420282d4b1a460f0a6e44433548be2ff13a7da32afbd05c1d7a73377afa121f3.
- 462 file sorgenti confrontati integralmente; ammessi in piu soltanto
  README_ALPHA.md e SOURCE_COMMIT. Esclusi temporanei, segreti, storage e Lab.
- Versione app sempre 0.1.0.alpha.10, backend e footer coerenti.
- Test sul pacchetto effettivo Windows: 183 superati con rete esterna vietata.
- Immagine candidata server:
  app-backend:alpha10_7-candidate-20261030,
  sha256:b456f5615c5e5c7b9a84844353a9690d313ae2404f77c75b040ecf204f2a395b.
- Runtime derivato dall'immagine operativa esatta
  sha256:7e1860b00bf626a592a2add72f87f28418a26e37cb47841055fc561ed3dd30d8.
  Layer/configurazione precedenti verificati, directory app/scripts sostituite
  integralmente nella SOLA candidata. Nessun apt/pip, pull o aggiornamento
  dipendenze. Dockerfile e requirements sorgenti invariati.
- Frontend interamente identico a quello installato: riuso consentito solo
  preservando l'immagine e verificando nuovamente il bundle alla riapertura.
- Candidata server: 26 cache/riuso, 32 manuali/rematch, 18 ponte rematch,
  14 Metalba LST03 e 16 tipo Leichtmetall: 106 test superati, rete disabilitata.
  Il messaggio di salvataggio AI fallito nel test e un guasto simulato, non
  un errore dell'Alpha. Nessuna chiamata AI reale effettuata.

## Preflight operativo

Alpha operativa ancora sul sorgente 9a2a98e5 / pacchetto 10.6.
PostgreSQL healthy; altro stack preservato. Zero run AI attivi e zero sessioni
DB impegnate nella prima lettura; nessun processo soffice rilevato.
Ricontrollare immediatamente prima di fermare i writer, non usare questi
controlli come autorizzazione permanente.

Il 30/10 alle 19:26 italiane: health backend HTTP 200 in 0,003 s,
frontend HTTP 200 in 0,001 s. Snapshot/riuso Word restano entrambi true
nell'app operativa; gli override false appartengono soltanto ai test one-off.

Spazio disponibile: root 7.403.102.208 byte (filesystem totale 24.627.232.768),
dati/backup 84.592.443.392 byte (totale 105.085.067.264). Dati e backup sono
lo stesso filesystem: NON sommare due volte lo spazio. Storage circa 2,28 GB,
backup gia presenti 11,73 GB, PostgreSQL fisico 0,335 GB e DB logico 0,110 GB.
Stimati 3 GB per nuovi backup piu margine operativo; candidata sotto 0,5 GB
aggiuntivi sulla root. Nessuna pulizia proposta/autorizzata/eseguita.

Docker Desktop locale non risultava avviato; chiesta l'attivazione per il
restore QA su PC. Non fermare l'app per un aggiornamento dati senza poter
completare il restore isolato richiesto. Nessun vecchio backup e stato eliminato.

## Preview DB candidata — nessuna applicazione

Eseguita con candidata read-only, modello/bootstrap solo importato dopo verifica
AST delle sole dichiarazioni/import, SENZA chiamare initialize_application,
create_all, seed, app startup o job. Transazione PostgreSQL REPEATABLE READ,
READ ONLY, timeout; volume root container read-only. Risultati restituiti
soltanto come metadati, conteggi e digest, senza esportazione dell'archivio.

- Digest:
  8b2ebf64c8f5518f36c5e5a09c2862d0eacaf6c6226109828be4a1a8161cc485.
- Due tabelle nuove assenti: documenti_ai_estrazioni e documenti_ai_consumi
  da creare nella sola preparazione autorizzata.
- 219 letture pregresse recuperabili senza AI.
- Quattro certificati manuali: documenti 9, 60, 206, 277.
- Tre DDT con inserimenti manuali: documenti 43, 205, 401.
- Un certificato senza lettura, Bozen #326, senza riga Incoming: non parte
  dello storico automatico; non avviarne una lettura o bonifica nel deploy.
- Nessun run AI attivo nella preview.

Il DDT #401, 26-03514.pdf, contiene righe 290/295/296: eventi esatti di
creazione manuale delle righe 295 e 296 il 30/10 alle 08:09/08:10 italiane,
successivi al caricamento del documento gia letto. Come #43, e un inserimento
misto con dati umani da proteggere: non escluderlo solo perche ha evidenza AI.
Il conteggio 4+2 del giorno precedente e pertanto SUPERATO: l'anteprima attuale
richiede sette marcatori documento (4+3), non sei.

Applicazione proposta nella prima fase (successivamente autorizzata, vedi sotto):
due tabelle additive, recupero 219 letture, sette nuove evidenze interne di
provenienza manuale. Nessun valore/record originario riscritto, nessuna
rigenerazione Word/PDF, nuovo numero, bonifica match, modifica standard o AI.

Prima di apply: finestra concordata senza utenti/run, backup coerenti con un
solo TS, hash e restore verificati. Rifare preview se cambia il digest e
ottenere nuova approvazione; NOWAIT e verifica integrale non vanno aggirati.
Conservare report, hash e ID delle sole evidenze aggiunte, verificare seconda
preview idempotente e dati/file protetti invariati.

L'eccezione Neuman Incoming #91 resta separata: nessuna correzione/scollegamento
automatico di A62082BIU/A62082BTU, gia confermati/validati. Nessun recupero Word
del 28/10 va ripetuto. Per rollback conservare nuove tabelle/marcatori/letture:
il vecchio codice perde le nuove protezioni e riprende letture costose;
non riattivare batch in downgrade senza valutazione.

## Ripresa autorizzata 30/10

L'utente ha autorizzato a procedere solo con controlli positivi. Docker Desktop
29.5.2 verificato; i quattro servizi locali non vengono fermati o usati per il
restore. Nuova preview identica al digest e ai conteggi approvati.

Alle 19:37 circa, dopo tre controlli di assenza run/upload, sessioni DB attive,
richieste utenti e processi di conversione, fermati soltanto backend/frontend
Alpha. PostgreSQL e altro stack rimasti attivi. Snapshot completo senza
esclusioni di colonne, immagini di rollback e impronte di configurazione salvati.

Unico TS: `20261030_194000` (identificatore conservato per tutta la manutenzione).
Backup privati sul server `/srv/certi_nt/backup/alpha_deploy_20261030_194000` e
copia esterna sul PC `backups/alpha_deploy_20261030_194000`.
Archivi server interamente letti e dump completo verificati:

- app/configurazione, incluso `.env`: 7.237.200 byte;
- database logico: 18.189.686 byte;
- storage documentale: 2.053.764.742 byte.

Trasferimento esterno e restore isolato ancora da completare in questa fase.
Non installare/applicare fino alla loro verifica. Nessuna pulizia, rilettura AI,
rigenerazione Word/PDF o modifica ai dati originari eseguita.

L'utente ha poi chiesto la pulizia del PC a conclusione positiva: tre archivi
copiati, estrazioni di restore e container QA, ma soltanto dopo nuovo confronto
integrale con i backup server. Regola/perimetro aggiunti al runbook principale.
I backup server e i piccoli manifest/prove resteranno; nessuna autorizzazione
a cancellare altri backup o documenti/database dell'app locale.

## Restore e prova integrale riusciti

Copia esterna: hash identici, archivi letti integralmente, 457 file app e 4.454
file storage coincidenti con la baseline. Restore fisico e PostgreSQL conclusi
positivamente sul PC: tutte le **44 tabelle originali** e l'export eSolver
coincidono integralmente; 323 record certificato presenti nella baseline.
QA creato senza rete e senza volumi dell'app locale.

Provata poi sul clone la preparazione del pacchetto effettivo fc1d1f74, con
controllo del percorso dei moduli realmente importati. Esito: due tabelle nuove,
219 letture memorizzate, sette marcatori per documenti 9/60/206/277/43/205/401,
zero consumi AI e tutte le 44 tabelle originali identiche escludendo soltanto i
sette ID aggiunti nell'evidenza interna. Una seconda applicazione non aggiunge
alcun marcatore e mantiene 219 letture: idempotenza verificata.

`legacy_evidence` e la provenienza conservata del JSON anche dopo il salvataggio
nella cache: NON significa lettura mancante o richiesta di AI. Alla riapertura
verificare anche `_reuse_persisted` per distinguere il recupero realmente salvato.

Con questi esiti positivi, nel perimetro dell'approvazione condizionata
dell'utente, avviata l'installazione soft mantenendo Alpha in manutenzione.

## Installazione, applicazione e riapertura riuscite

Installato e confrontato integralmente il pacchetto; `.env` e configurazione
Compose esattamente conservati. Frontend e dipendenze invariati, nessuna build
o pull alla riapertura. PostgreSQL (ID/mount/mapping) e altro stack invariati.

Applicazione atomica sul DB Alpha riuscita con lo stesso digest approvato:
219 letture recuperate, marcatori evidenza 6853..6859 per i sette documenti
previsti, due tabelle additive. SHA dump verificato:
`7732b0ef0949ab6f52e9fa819f6b4f42728fe705236e84934a326c02db3a192e`.
Tutte le 44 tabelle originali identiche, escludendo solo quei sette nuovi ID;
4.454 file storage, dati/valori/match, Word/PDF, numeri e export intatti.

Riapertura circa 19:51 italiane. HTTP 200 sia interno sia pubblico, backend e
bundle `0.1.0.alpha.10`; snapshot DDT e riuso Word entrambi true. Verificate
219 risposte realmente persistite (`_reuse_persisted`), manuali esclusi, nessun
run attivo e zero record di consumo AI. Nessuna differenza nelle tabelle neppure
dopo il bootstrap. Nessun errore applicativo nei log.

Un'asserzione iniziale del controllo ausiliario presumeva due ruoli locali:
verificato invece dal dump e dal server che esisteva soltanto
`certi_esolver_reader`, con solo SELECT e senza privilegi amministrativi.
Corretto esclusivamente il controllo, NON creati/cambiati ruoli o permessi;
chiarimento aggiunto al runbook. Non era un errore dell'app o della migrazione.

Al primo postcheck: root libera 7.395.995.648 byte, disco dati/backup libero
82.510.516.224 byte. Ultimo ciclo precedente ancora DDT 2693 / Quarta 10248;
attendere il primo ciclo naturale del nuovo processo prima della chiusura e
della pulizia PC autorizzata. Nessuna sincronizzazione manuale o PDF reale usato
come test. Conservare i backup server integralmente.

## Primo ciclo naturale confermato

Alle 20:06 italiane: DDT run **2694** success (664 righe lette/aggiornate,
zero inserimenti), Quarta run **10249** ok (16.103 OL / 25.371 riferimenti CDQ).
Nessun richiamo manuale degli aggiornamenti. Il nuovo processo ha rispettato
l'intervallo automatico di 15 minuti.

Postcheck dopo 983 secondi dalla riapertura: sito/API interni e pubblici 200,
219 cache persistite, nessun run AI e zero consumi AI. Tutti i 4.454 file,
Word/PDF e relativo export identici. I soli delta DB rispetto al fermo sono
le cinque tabelle normalmente aggiornate dai job: `quarta_taglio_ddt_sync_runs`,
`quarta_taglio_ddt_work_items`, `quarta_taglio_esolver_links`,
`quarta_taglio_rows`, `quarta_taglio_sync_runs`. Nessun'altra differenza,
nessun errore applicativo nei log. Non interpretare questi aggiornamenti
ordinari come una modifica delle righe Incoming o dei documenti.

Spazio finale: root disponibile 7.395.897.344 byte; dati/backup disponibile
82.510.512.128 byte. Nessuna pulizia server necessaria/eseguita.
Avviata nuova lettura integrale dei backup server prima della sola pulizia PC
richiesta dall'utente. La successiva proposta di test AI sotto 1 euro non e stata
eseguita: nessuna nuova chiamata a pagamento autorizzata/avviata da una domanda.

## Pulizia PC completata alle 20:08 italiane

Dopo un nuovo confronto SHA-256 e di ogni contenuto degli archivi server,
rimosse soltanto le copie PC `app.tgz`, `database.sql`, `storage.tgz` e la loro
estrazione `restore_check`. Rimossi **4.367.180.422 byte** (circa 4,37 GB).
Percorsi assoluti verificati, nessun reparse point; ogni file estratto era ancora
identico alla baseline prima della rimozione.

Arrestato il solo container QA effimero
`certi-alpha-qa-pg-20261030-194000`, identificato anche per ID originale,
senza rete/volumi persistenti e con rimozione automatica. App/database/documenti
locali non toccati. Backup completi restano verificati e recuperabili sul server
nel percorso di questa manutenzione; nessuna cancellazione server.
Sul PC restano soltanto i piccoli manifest, impronte e verbali del collaudo:
la copia esterna completa di questa operazione non e piu presente, per richiesta
esplicita dell'utente. Non eliminare questi backup server implicitamente in futuro.

La proposta successiva riguarda una prova AI isolata sotto 1 euro, con coppie
Arconic/Metalba e verifica dell'abbinamento applicativo, dei rifiuti e del riuso.
E distinta dal deploy concluso: non avviate chiamate AI da questa sola richiesta
di proposta, nessun costo aggiuntivo e nessuna modifica Alpha per provarla.
