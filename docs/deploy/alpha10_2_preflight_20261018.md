# Alpha 10.2 — verbale deploy 18/10/2026

Verbale operativo: leggere l'esito finale, quando aggiunto, prima di ripetere
comandi. Non autorizza recuperi, cancellazioni, modifiche dati o deploy futuri.

**ESITO FINALE: deploy completato, Alpha online; controlli conclusi il 18/10
alle 17:21 UTC circa.** Le fasi di fermo/incidente sotto sono storiche.

## Pacchetto e collaudi

- Sorgente main pubblicato `ec5b949804070fd17219d5b5221e96ddce33eb16`.
- Repo deploy commit `3168cef`, tag nuovo `v0.1.0-alpha.10.2-deploy`.
- App version resta `0.1.0.alpha.10`; numero 10.2 identifica il pacchetto.
- Archivio 12.277.760 byte, SHA-256
  `644734ad5ac18a98870a654ec2ce205ed18f565a342dbcc85298fc817a2d677e`.
- 436 file sorgente + README_ALPHA/SOURCE_COMMIT: alberi Git identici,
  archivio confrontato integralmente (sole conversioni CRLF dei file testuali).
  Niente Lab, storage, `.env`, build locali, node_modules o temporanei.
- Base Node fissata al digest precedente approvato. Build immagine del pacchetto
  locale riuscita, 25 test mjs + 6 requisiti cliente, 455 test Quarta backend
  tutti superati anche con PostgreSQL temporaneo isolato. In precedenza 45 C/D
  PostgreSQL passati; il primo tentativo col driver psycopg2 errato era solo
  configurazione di collaudo, ripetuto correttamente con psycopg.
- Preview Alpha READ ONLY, codice planner solo in memoria: 228 certificati,
  17 basi nascoste in presentazione (ID99 ->189), quattro riusi ammissibili
  684/711/767/800; OL1012 ancora Incoming non pronto. Variazioni materiali
  OL986/1012/1251, nessuna correzione/adottazione automatica dei Word storici.

## Finestra e backup esterni

Controllati run AI, query attive, conversioni e richieste utenti prima del fermo.
Fermati soltanto backend/frontend Alpha; PostgreSQL e altro stack preservati.
Un solo timestamp UTC `20261018_164943`.

Destinazione privata sul PC: `backups/alpha_deploy_20261018_164943`, esclusa da
Git e ACL solo utente. Baseline JSON con impronte di tutte le tabelle public
(escludendo la futura sola colonna word_reference) e di tutti i file app/storage.
App e dump DB trasferiti con hash end-to-end; restore isolato da completare
prima di qualunque installazione o migrazione.

Alcuni Word non sono leggibili dall'utente SSH: usare il volume corrente già
assegnato all'app tramite container isolato con `--volumes-from app-backend-1:ro`.
Questo non autorizza ad accedere a cartelle storiche esterne al volume o a
cambiarne i permessi. Nessun chmod/chown o intervento sulla vecchia directory.

## Incidente del trasporto backup — NON ripetere

Il primo flusso tar binario da `docker run --rm ...` usava il logging Docker
predefinito: il daemon ha registrato il flusso binario, saturando temporaneamente
il volume root. La creazione dello staging ha fallito per ENOSPC PRIMA di
estrarre/installare codice o avviare build/migrazione.

Arrestato esclusivamente il container temporaneo tar readonly identificato
`bd897095986a82d10e75d9d4b8e8b24ec9901d4110077a2f004dcb33fa14eb3d`;
AutoRemove ha eliminato container/log temporanei. Nessuna pulizia generale.
Spazio tornato a circa 2,016 GB; l'aumento residuo dei log di sistema resta
conservato per diagnosi, non cancellato per nascondere l'incidente.

PostgreSQL Alpha ha registrato PANIC checkpoint per spazio insufficiente alle
16:54:42 e 16:54:43 UTC, avviando recovery interno. Successivamente risponde,
`pg_is_in_recovery()` false. Non basta questo per dichiarare i dati integri:
confrontare tutte le impronte con il baseline e verificare il restore isolato.
Altro PostgreSQL: nessun PANIC/FATAL rilevato nella finestra controllata.

**Regola obbligatoria per stream binari:** container temporanei di backup con
`--log-driver none`, mount dati readonly, `--network none`, `--rm`, hash server/PC
e monitoraggio spazio; mai lasciare che il tar venga salvato anche nei log.
Non modificare globalmente la configurazione Docker del server.
Prova binaria 1 MiB con logging none verificata prima del nuovo tentativo.
Guardia del lettore: interrompere se il disponibile scende sotto 1,5 GB.
Backup parziale interrotto conservato sul PC come temporaneo da pulire solo
dopo backup completo/restore verificato e chiusura attività.

## Stato al rilevamento dell'incidente (fase superata, non stato corrente)

Nessun nuovo codice installato, nessuna build server iniziata, nessuna colonna
aggiunta e nessun backfill/Word/PDF aziendale generato da questo intervento.
SOURCE_COMMIT installato ancora `b91c0b0973bbae3d4095c947bb91b822dbc434e0`.
Backend/frontend ancora fermi durante il completamento delle verifiche.
Questo non è un verbale di deploy completato.

## Ripresa autorizzata e installazione 18/10

L'utente ha autorizzato il completamento soltanto se tutte le verifiche
passavano. Confrontate integralmente le 44 tabelle e i 3.498 file storage con
la baseline precedente all'incidente: nessuna differenza. Backup completo
nuovamente acquisito con logging disattivato e ripristinato su PostgreSQL
isolato e filesystem del PC: corrispondenza integrale verificata.

Backup privato `backups/alpha_deploy_20261018_164943`, escluso da Git:

| File | Byte | SHA-256 |
| --- | ---: | --- |
| app.tgz | 7100933 | 810f86dd55424655fc1985ee464a881a4982016b8b371d6232ce6e5e762d8427 |
| database.sql | 16476060 | 865adce0f27f3b0ce817d291052ad8a988c9d6bda2f70564f88a107e1200dd8b |
| storage.tgz | 1593985437 | 65cd6d351e659fd53dbac7904e37660af6eb26de7e457bcaf674dca2433727c5 |

Build server con dipendenze in cache e immagini candidate collaudate: 35 test
backend mirati, nginx e bundle corretti. Preparazione schema solo additiva:
colonna JSON nullable `word_reference`, nessun backfill. Tutti i 228 record
certificato e i file preesistenti ancora identici prima e dopo la riapertura.

Avviati soltanto backend/frontend alle 17:03:58 UTC circa; PostgreSQL e altro
stack non ricreati. `.env`, mapping DB privato e flag snapshot/riuso invariati.
SOURCE_COMMIT `ec5b949804070fd17219d5b5221e96ddce33eb16`; pacchetto deploy
`3168cef`, tag immutabile `v0.1.0-alpha.10.2-deploy`.

Collaudo UI sulla Alpha pubblicata superato: DDT, Registro (OL1091 una sola
riga chiusa), tag requisiti OL962, Standard, Reparti e Incoming. Nessuna
generazione PDF reale. Verifiche C/D sul bundle pubblicato con API simulate
superate a 1440/1920 px; non confonderle con modifiche a documenti aziendali.
Health pubblico 200, nessun errore JavaScript/HTTP nel collaudo riuscito.

Il controllo del primo ciclo automatico era condizione di chiusura ed è stato
superato, come documentato sotto: l'aggiornamento da pagina non prova il timer.

Ulteriore confronto dopo il collaudo UI: tutti i 228 record certificato e i
3.498 file ancora identici; modificate soltanto cache righe/collegamenti e log
delle letture Quarta. Vista `esolver_export.certi_certificati_pdf`: 63 righe,
hash integrale identico al database ripristinato. PostgreSQL non in recovery,
spazio disponibile circa 1.947 MB decimali, senza ulteriore pulizia server.

Pulizia PC autorizzata eseguita: rimossi soltanto `restore_check/`, il flusso
`storage_attempt1_interrupted.partial` e staging/tar sorgente `ec5b94980407`
nel repo deploy. I tre archivi completi, manifesto, baseline ed evidenze restano
privati sul PC; conservati anche i backup storici recuperati per liberare spazio.
La copia di restore era riproducibile dai backup verificati, non un originale.
Non eliminare automaticamente queste copie quando arriverà un nuovo backup:
confrontare copertura storica/configurazioni e chiedere prima all'utente.

## Chiusura — primo ciclo automatico verificato

- Snapshot DDT ID1597: 17:19:01–17:19:02 UTC, successo, 567 righe sorgente,
  nessuna scomparsa o inserimento inatteso.
- Quarta ID9080: 17:19:02–17:19:31 UTC, successo, avvio automatico
  (`triggered_by_user_id=NULL`), 16.024 OL / 25.282 righe CDQ.
- Riuso automatico: create esattamente le quattro copie previste, nuovi record
  229–232 per OL977/1128/1071/1156, DDT2436/2453/2473/2517. Non sono nuovi
  PDF né adozioni automatiche di Word storici ambigui.
- Confronto dopo il ciclo: 228 record preesistenti e 3.498 file originali
  integralmente invariati; soltanto quattro nuovi record e quattro file.
  Le 63 righe export PDF sono ancora identiche al backup ripristinato.
- Spazio finale circa 1.946 MB decimali (1,81 GiB). Resta raccomandata
  l'estensione del volume: il riuso cache non risolve la crescita futura.

Restano scelte documentali dell'utente, non riparazioni automatiche del deploy:
Word storici contrastanti OL1091/1095/972 e variazioni materiali OL986/1012/1251.
Esempio OL1012: aggiunto sull'OL il CDQ26-0969, ancora assente da Incoming;
completare/verificare Incoming prima di aggiornare il Word. PDF chiusi intatti.

Nessuna cancellazione di dati aziendali, nuovo backfill o modifica a materiali
per superare i controlli. Conservati backup esterni e immagini rollback.
