# DDT persistenti e perimetro di avvio — 08/10/2026

## Stato e autorizzazioni

Audit locale e Alpha, implementazione e applicazione **solo locali**, autorizzati
dall'utente. Nessun commit/push o deploy Alpha eseguito in questa attività.
Alpha è stato interrogato in transazioni read-only, senza installare codice,
modificare dati o generare documenti. Procedura futura:
[`alpha_soft_update_server.md`](../deploy/alpha_soft_update_server.md), sezione
«Perimetro operativo e storico persistente».

## Regola implementata

- Dal **01/10/2026 incluso** mantenere le quote; prima di tale data archiviare
  soltanto documenti senza lavoro avviato, secondo un'anteprima approvata.
- Proteggere anche certificati incompleti, Word/PDF, allegati, standard e scelte
  manuali, decisioni, Incoming parziale/in elaborazione o candidati ambigui,
  sorgenti da verificare. Una quota protetta conserva l'intero documento DDT.
- Archivio reversibile e separato dalle esclusioni Qualità: nessuna cancellazione,
  nessun limite mobile, nessuna archiviazione automatica dei nuovi arrivi tardivi.
- Gli archiviati non contano negli Attivi/badge e non alimentano il riuso Word.
  In `Vista → Archiviati per avvio`, admin IT/Qualità possono ripristinare tutto
  il DDT con un motivo. Nessuna nuova colonna nella tabella.
- Correzioni della sorgente, nuove quote o nuovo lavoro rendono nuovamente
  operativo il DDT; lo snapshot registra poi l'evento di riapertura. Una nuova
  lettura di dati invariati non fa ricomparire lo storico archiviato.
- Certificazione combina la vista corrente con i DDT operativi già conservati,
  senza scriverli nuovamente nella cache né duplicare le quote. Il riuso Word
  continua a utilizzare questi DDT anche oltre la finestra eSolver.

Non vengono inventati OL mancanti né forzati abbinamenti. Il registro conserva
i certificati già numerati; non si creano certificati per il solo fatto di avere
uno storico. La conservazione non può recuperare documenti mai ricevuti da eSolver.

## Audit Alpha (08/10, ultima conferma 19:46 UTC)

| Esito simulato sul DB Alpha | Quote |
| --- | ---: |
| Totali | 678 |
| Archiviabili, 200 documenti | 538 |
| Mantenute, 50 documenti | 140 |
| Attive mantenute | 122 |
| Completate / escluse mantenute | 17 / 1 |

Sono protette 38 quote anteriori al 01/10. La protezione del lavoro parziale
aggiunge 19 quote rispetto alla prima ipotesi più restrittiva. Esempi:
DDT 2143 del 02/09 (Incoming #22), 2145 del 02/09 (#79), 2254 del 16/09 (#65).
368 quote archiviate sono ancora esposte da eSolver: controllato esplicitamente
che il loro ritorno nella vista non annulli l'archiviazione invariata.

Il planner Word, eseguito solo in memoria sui dati Alpha, propone 18 riusi
su 11 DDT / 16 OL; preserva 20 documenti presenti e non forza gli altri casi.
Restano protetti tutti i 173 record certificato (165 con Word, 18 con PDF).
I 23 casi senza OL rimasti nel perimetro operativo necessitano comunque della
correzione/chiarimento eSolver: questo intervento non li risolve artificialmente.
Questi numeri sono una fotografia, da ricalcolare prima di ogni applicazione.

## Collaudo e applicazione locale

- **582 test backend superati**, inclusi test PostgreSQL su database/container
  isolato. Verificati schema additivo ripetibile/rollback, lock con writer attivo,
  report scaduto/manomesso/di altro DB, protezioni, riapertura/ripristino,
  storico fuori vista, deduplicazione e regressioni dei precedenti flussi DDT.
- Build frontend riuscita; 24 test JavaScript superati (incluse scadenze,
  sincronizzazione, requisiti cliente, permessi, filtri e payload).
  Restano gli avvisi preesistenti su Browserslist e dimensione del bundle.
- Playwright/Chromium locale, API simulate: vista archivio, 13 colonne invariate,
  ripristino intero DDT, payload/revisione, restrizioni utente, assenza di scadenza
  attiva/link di certificazione sui documenti archiviati; screenshot verificati.
  Computer Use non avviabile in questa sessione: usato il percorso alternativo
  documentato in `docs/development/browser_verification_windows.md`.
- Backend locale fermato durante la manutenzione, backup PostgreSQL 13.309.760
  byte con intestazione verificata; report locale e identità DB propri.
- Applicazione atomica: **660 archiviati, 222 mantenuti = 221 attivi + 1 completato**.
  Nuova anteprima: 660 già archiviati, 222 mantenuti, zero nuove archiviazioni.
- Impronta dell'intero contenuto delle altre **43 tabelle** identica prima/dopo;
  **36 record certificato e 45 file Word/PDF** invariati, nessun file mancante.
  Nessun riuso Word applicato durante questa archiviazione.
- Backend e frontend locali riavviati al termine; API risponde HTTP 200.
  Rimosso solo il PostgreSQL temporaneo dei test e il suo volume anonimo,
  senza toccare il database dell'app. Backup e report privati, esclusi da Git:
  `backend/tmp/backups/ddt_archive_20261008/` (`before.sql`, `preview.json`,
  `preview.applied.json`, `after.json`). Il journal `pending_commit` non basta:
  commit e stato effettivo sono stati verificati separatamente.

Le quantità locali non devono coincidere con Alpha: i due database contengono
lavori diversi. Nessun ID, report, evento archivio o dump locale va copiato su Alpha.

## Rischi residui e prossimo deploy

1. Lo stesso algoritmo va eseguito sul DB Alpha fermo, con nuova anteprima,
   backup e consenso. Prima archivio, poi nuova anteprima del recupero Word;
   autorizzazioni e applicazioni restano separate.
2. Tutti i certificati/file/export esistenti devono essere ricontrollati prima
   e dopo. Nessuna generazione PDF o spedizione automatica introdotta.
3. Un rollback al codice precedente ignora l'archivio: tenere fermo il worker
   Word e concordare il ritorno operativo; non sovrascrivere nuovi lavori con
   un vecchio dump. Il ripristino ordinario è tracciato tramite l'app.
4. Protezioni prudenti possono conservare più righe delle 75–100 ipotizzate.
   Non ridurre i numeri sacrificando lavori parziali o casi dubbi.
5. Beta è **produzione reale**, non test. Data ufficiale, giorni precedenti e
   successiva cernita saranno decisi separatamente con l'utente.
