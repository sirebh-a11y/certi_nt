# eSolver/Quarta — attesa senza scadenza

11/11/2026. Audit/proposta approvati, implementazione locale autorizzata.
Nessun commit/push o deploy implicito, nessuna modifica al DB dell'app locale
o ad Alpha: le prove DB usano soltanto fixture e PostgreSQL isolato in tmpfs.

## Regola per l'utente

Una lettura esterna valida può impiegare quanto serve. Non viene interrotta
perché supera 30, 120 o 300 secondi. In Certificazione compare:

> Attendo eSolver/Quarta. Puoi continuare a usare le altre pagine.

Il browser fa richieste brevi e mostra l'esito quando il lavoro finisce.
Un nuovo clic identico dello stesso utente si aggancia al lavoro già avviato.
Gli errori reali rimangono distinti dall'attesa, con le segnalazioni/fallback
già previsti dai singoli percorsi. Il filtro requisiti non li scambia per
assenza di requisiti e lo snapshot DDT conserva l'ultimo successo valido.
Se il processo si interrompe realmente, non si ripetono automaticamente
operazioni che potrebbero aver già scritto dati. Si chiede di controllare lo
stato prima di riprovare. Non è un timer che decide di interromperle.

## Perimetro tecnico

- `read_policy.py`: timeout query zero sui due profili, anche se il DB
  contiene ancora 30. Tutti i sei punti di connessione SQL usano la policy.
  Nessuna modifica a prompt/AI, match/rematch, regole LST03/Leichtmetall,
  numerazione/eredità o timeout PDF/AI/lock. Apertura connessione distinta.
- Editor: accetta e preserva zero (`??`, non `||`); un vecchio client che invia
  30 non ripristina un limite nei due profili. Credenziali e altri parametri
  restano invariati. I vecchi record non sono aggiornati in massa.
- `integration_background_jobs` + `integration_background_receipts`: schema
  additivo creato dal bootstrap. Richieste/risposte cifrate con APP_SECRET_KEY;
  le ricevute persistono anche per il secondo clic o una risposta HTTP persa.
- Due slot globali PostgreSQL limitano le letture contemporanee senza
  consumare tutto il pool dell'app. Ogni worker usa la propria Session, sulla
  stessa connessione fisica dei lock di proprietà. Una riconnessione senza
  lock viene bloccata prima delle successive scritture. Un lavoro lento non
  viene riassegnato per età; un vero orfano è segnalato, non rieseguito.
- Il timer 15 minuti accoda soltanto: nessun SQL sincrono sul ciclo asyncio.
  La rilettura completa Quarta è serializzata e il risultato completato durante
  l'attesa è condiviso. La breve scrittura della cache eSolver è protetta da
  inserimenti simultanei e da risposte più vecchie applicate dopo le nuove.
  Snapshot e riuso Word conservano Session/commit atomici distinti ma, nel
  worker, usano la stessa connessione protetta. Prima di avviare queste Session
  il coordinatore chiude soltanto la transazione di lettura incidentale: non
  annulla i commit legittimi delle fasi precedenti. Prova dedicata SQLite/PG.
- Cambi di host/database/vista/credenziali durante una lettura invalidano
  quel risultato prima di applicarlo. In Quarta il conflitto non viene
  reinterpretato come materiale assente o cache vuota.
- Router con protocollo opzionale `Prefer: respond-async` → ticket 202 → poll
  autenticato. Risposta isolata per utente e permessi; nessun dispatcher di
  funzioni selezionabile dal client. Sessione/permessi ricontrollati nel worker.
  Il cambio reparto (anche nome) o ruolo in coda impedisce l'esecuzione.
- Il client conserva l'ID dopo una risposta persa e riprende il poll senza
  rilanciare l'azione. Sessione rinnovata mentre aspetta; logout/cambio account
  sospendono il solo client, non il lavoro. Un vecchio 401 non invalida la
  sessione nuova. Gli errori 409 strutturati conservano dati e scelta della data.
- Upload Word/seconde pagine/allegati: copia privata verificata con SHA-256,
  indipendente dalla chiusura della richiesta multipart. I PATCH mantengono
  i campi effettivamente inviati. Download Word restituisce i byte originali,
  non il JSON del ticket con estensione docx. PDF chiusi/export pubblico e
  modello seconda pagina mantengono i percorsi precedenti.
- In StrictMode la pagina non dichiara completata la sincronizzazione alla
  sola presentazione della richiesta: l'entrata ripetuta condivide il lavoro.
  Filtri, ordinamenti e risposte diventate obsolete mantengono le protezioni.

## Prove locali

- SQLite e PostgreSQL temporaneo, schemi casuali e vincolo esplicito
  localhost:55440 / database `certi_ddt_test_external_wait`; mai DB reale.
- Doppi clic simultanei, replay dopo completamento/risposta persa, due worker,
  slot globali, operazione molto vecchia ancora valida, orfani veri senza
  replay, perdita connessione/riconnessione, revisione codice e permessi cambiati.
- Addizione delle tabelle a uno schema precedente, ripetibilità, valori
  preesistenti intatti, multipart chiuso, PATCH omessi, hash file, isolamento
  utente, risultato binario, errori strutturati e messaggi senza segreti.
- Client con 721 poll e tempo simulato oltre 300 s: una sola presentazione.
  Proxy TCP locale 0,5 s: lavoro superiore a tale durata, poll e health
  ancora disponibili. Due fixture DB superate; nessuna attesa aziendale forzata.
- Browser Chromium reale su Vite e production, API tutte simulate: una sola
  richiesta iniziale, navigazione ad altra pagina e ritorno mentre il lavoro
  è in corso, completamento e nessun errore JavaScript. Schermate 1440 px.
  La prima prova Vite ha individuato due richieste iniziali diverse
  (`sync=true` / `false`), dovute al flag segnato prima del completamento.
  Corretto quel momento, poi ripetute entrambe le prove: una sola richiesta,
  senza disattivare StrictMode per far passare il test.
- Sei rendering PDF reali LibreOffice superati, compresi due allegati,
  pagina originariamente bianca, rotazioni, seconda pagina e legacy.
- Build frontend riuscita e 66 test frontend superati. Avvisi preesistenti
  Browserslist/bundle e deprecazioni non corretti con aggiornamenti impliciti.
- Suite finale sul codice definitivo: **1.105 superati, 214 saltati,
  zero fallimenti/errori**, 290,38 s. I saltati sono prove opt-in non
  attivate (in prevalenza altri database PostgreSQL dedicati), rendering
  eseguiti separatamente e casi PostgreSQL non applicabili alla fixture SQLite.
  Il PostgreSQL dedicato a questo intervento è stato attivato nella suite.
  Mirati finali: 112 superati, 4 non applicabili/opt-in non attivati. Non
  sommare queste suite sovrapposte. Le sei conversioni reali sono tutte verdi.
- Artefatti privati `tmp_eval/external_wait_20261111/`: `acceptance.xml` è
  l'esito generale finale, `target_owned_children.xml` quello mirato;
  `render.xml`, `proxy.xml`, `config_guard.xml`, schermate attesa/esito.
  Le esecuzioni intermedie sono conservate per audit, non sostituiscono
  l'accettazione finale. Nessuna chiamata AI o interrogazione Alpha per queste prove.
- Chiusi solo i frontend QA 5174/5175, non il servizio abituale 5173.
  Il PostgreSQL sintetico `certi-external-wait-qa-20261111`, ID
  `7f832cf19b54`, usa esclusivamente tmpfs e nessun volume reale: rimosso
  dopo i test. I dati fittizi sono ricreabili dalle fixture; risultati e script
  locali conservati. Nessuna pulizia dei dati dell'app o dei vecchi artefatti utente.

## Prossimo deploy e limiti espliciti

Seguire [runbook Alpha](../deploy/alpha_soft_update_server.md), che contiene
anche schema, spazio, backup, lavori attivi e rollback. Non sostituire DB Alpha
con quello locale e non rilanciare vecchi recuperi Word/DDT/AI.

La directory privata `storage/integration_jobs`, accanto ai documenti,
deve essere persistente e compresa nei backup insieme alla chiave esistente.
Non c'è cancellazione automatica per età: misurare crescita DB/spool; eventuale
pulizia dei soli terminali va concordata, mai di lavori pendenti o documenti.
I risultati tecnici non vanno scambiati per copie certificate da conservare.

Ricaricare il frontend dopo il deploy; le vecchie schede conservano il
protocollo sincrono e il limite proxy. Il server IT/Nginx non viene modificato.
Prima del deploy riconfermare i timeout PostgreSQL di sessione/transazione.
Il controllo in sola lettura pre-commit 11/11 ha rilevato i tre valori a zero
con il ruolo applicativo e isolamento `read committed`: nessun limite
incompatibile emerso, nessuna impostazione Alpha cambiata. Spazio/schema e
riscontro sono registrati nel preflight cumulativo, da rinnovare al deploy.
Le prove con servizi simulati non promettono che una fonte guasta risponderà.
Non è necessario fare una chiamata AI per provare questo intervento.
