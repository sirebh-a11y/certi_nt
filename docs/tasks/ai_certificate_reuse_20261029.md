# Riuso letture AI dei certificati — 29/10/2026

## Perimetro autorizzato

Sviluppo e collaudo locali. Alpha esclusivamente in lettura: nessun fermo,
riavvio, migrazione, nuova lettura AI o aggiornamento dati su Alpha autorizzato.
Budget massimo 5 EUR per collaudi AI locali. Commit/push e deploy separati.

## Causa e audit

Ogni batch DDT include i certificati storici del fornitore per poterli abbinare.
Lo scopo e corretto; era errata la rilettura AI ad ogni run, con cache solo in
memoria. Il match e eseguito dall'app, non da OpenAI. Nella fotografia Alpha:
53 run conclusi, 166 DDT, 2162 letture/candidati certificato. Non sono token
misurati: la vecchia versione non salvava response.usage.

Su 224 certificati: 212 risposte AI JSON conservate, quattro con soli valori
confermati, sette nuovi nel run attivo e un Bozen senza riga/risposta salvata.
Tutte le 212 risposte sono normalizzabili offline; questo non significa che
ogni campo sia presente (alcune leghe sono vuote anche nei dati storici).

### Rettifica obbligatoria: documenti manuali (audit Alpha 29/10, 16:54 UTC)

**La precedente proposta di rileggere una volta i quattro documenti senza JSON
e superata e NON va applicata. La protezione manuale e implementata in locale;
nessuna distribuzione, backfill o attivazione su Alpha eseguiti.**

L'audit in sola lettura trova su questi documenti valori identificativi manuali,
evidenze utente e nessuna estrazione AI dei dati del certificato:

- 9, Metalba `26-1799`, riga 28: sette valori match manuali; la nota descrive
  l'aggancio manuale del certificato. Nessun run AI associato alla riga.
- 60, Metalba `26-1868`, riga 63: sette valori match manuali; nota di creazione
  manuale. Il DDT era stato letto prima del caricamento di questo certificato.
- 206, Arconic `EEP74865-44451810`, riga 134: sette valori match manuali; il run
  26 della riga e precedente al caricamento del certificato e riguarda il DDT.
- 277, Leichtmetall `94967.68`, riga 204: sette valori match manuali; stesso
  fenomeno con il run 36. Esistono tre controlli AI del tipo di documento, NON
  un'estrazione dei dati. Anche ripetere questo controllo sui manuali va evitato.
- DDT 205, file `80010594.pdf`, riga 163: evento `ddt_manuale_creato`, nove
  valori DDT manuali e nessuna estrazione AI dei dati. La regola vale anche qui.

Non usare `origine_upload=utente`, la sola nota o `ai_processing_run_id` come
classificatori: anche i caricamenti destinati all'AI hanno origine utente;
la nota puo descrivere il lato complementare. DDT 12/13, per esempio, hanno
una nota di aggancio manuale ma cinque valori DDT letti con ChatGPT. Il run di
una riga accoppiata non identifica necessariamente la lettura del certificato.

Il merge certificate-first sposta evidenze/valori, ma conserva solo eventi dei
blocchi chimica/proprieta/note/quality: l'evento manuale nel blocco match viene
eliminato con la riga origine. Occorre una provenienza durevole sul documento,
indipendente da merge, numero di righe, sgancio o run del lato complementare.

Protezione aggiuntiva implementata dopo approvazione:

1. Registrare esplicitamente la modalita manuale sul singolo documento nuovo.
   Per lo storico classificare con prove del lato corretto, conservando gli
   incerti come tali; nessuna deduzione automatica dal solo JSON assente.
2. Escludere i manuali da TUTTE le chiamate AI automatiche: precaricamento
   certificati, controllo tipo Leichtmetall, DDT, completamento blocchi e retry.
   Un dato assente resta assente: non deve attivare una lettura automatica.
   L'eventuale intervento AI resta un'azione esplicita dell'utente, non il
   significato di inviare un normale batch o caricare il documento complementare.
3. Mantenere i manuali candidati al match applicativo tramite i loro valori
   salvati, senza AI, senza abbassare soglie o perdere abbinamenti nello stesso
   run. Collaudare anche la competizione fra candidati manuali e letti con AI.
4. Non trattare i valori manuali come JSON originale di un PDF: conservare
   fonte/riga specifica, senza accorpare pesi di consegne diverse. Metalba 9
   contiene gia 6082H interpretato, non necessariamente il valore originale
   stampato: non inventare un ripristino F/H per renderlo compatibile.
5. Preservare anche le correzioni manuali di documenti originariamente letti
   con AI. Caso 357: numero finale completo `EEP75132-44475952`, mentre il
   vecchio JSON AI e parziale. Non richiedere una nuova lettura automaticamente
   solo perche manca il suffisso nel JSON, se l'utente lo ha gia corretto.
6. Prove con API vietata per manuali: arrivo del complementare in entrambi gli
   ordini, nuovi run, merge/sgancio, piu righe sullo stesso PDF, valori assenti,
   controllo tipo e confronto con candidati contrastanti. Verificare in modo
   distinto sia ZERO chiamate AI sia la conservazione del match corretto.

Implementazione locale: modulo `manual_document_protection`, marcatura documento
`manual_document_entry` in `documenti_evidenze`, senza legame alla riga destinata
al merge. Nessun campo UI nuovo. Le prove storiche richiedono dati manuali del
lato corretto o l'evento di creazione manuale; non bastano origine utente/note/run.
Un documento con lettura AI e un campo corretto a mano resta distinto da un
documento interamente inserito manualmente. Gli incerti non vengono inventati.

La marcatura impedisce le chiamate automatiche anche se mancano tutti i campi.
Il guard finale e ripetuto subito prima della richiesta a pagamento. L'azione
esplicita ha un contesto limitato ai documenti richiesti, che non resta attivo
nei batch successivi. Le correzioni manuali restano separate dal JSON originale.

Match/rematch: non congelare l'abbinamento e NON confrontare soltanto i sette
campi UI. Lo scoring iniziale dei JSON e la proposta iniziale restano invariati;
la seconda revisione ha invece corretto vincoli, pianificazione e applicazione
del rematch sui valori salvati (dettaglio sotto). Per documenti manuali o identita
corrette dall'utente, il batch rinvia al rematcher sui valori delle
righe, dopo che anche le nuove righe certificato esistono; non protegge per errore
quel DDT dal rematch del medesimo run. I candidati concorrenti sono rivalutati,
non viene data priorita automatica ai manuali. Se il vecchio JSON darebbe ancora
un match ma la correzione manuale lo ha indebolito/escluso, non ripristinare il
match usando il vecchio JSON. Non si accorpano letture di righe diverse.

SGANCIO: cambiare/confermare un dato incompatibile segna il match in conflitto,
non separa fisicamente i documenti. `Disaccoppia documenti` separa i due lati
e registra `ManualMatchBlock`; una riga gia validata richiede prima riapertura
con i permessi esistenti. Il blocco era gia rispettato dal rematch ma mancava
nel filtro della prima proposta del batch: aggiunto lo STESSO filtro anche li,
senza cambiare punteggi. Resta specifico alla coppia/riga: non vieta di abbinare
quel certificato a un nuovo DDT legittimo. Campi interni e storico si conservano.

Nessuna scrittura o chiamata AI su Alpha. Inventario locale dell'audit in
`tmp_eval/alpha_manual_inventory_20261029.json` e dettaglio cronologico in
`tmp_eval/alpha_manual_origins_20261029.json` (non sono migrazioni da applicare).

**Piu righe con lo stesso PDF certificato o DDT sono normali.** Caso reale Bozen
documento 281: pesi di riga 2438 e 8533, totale nel JSON 10971. Non e un errore
da bonificare. Vietato far diventare una riga Incoming la cache globale del PDF.

## Regole implementate

- Cache persistente per documento, hash del file, fornitore/template, tipo,
  identita delle pagine e versione dello schema di lettura. Non per solo CDQ.
- Stessi prompt, modello, normalizzatori e soglie di match. Lo storico resta
  candidato anche mesi dopo. I DDT non vengono esclusi o accorpati.
- Recupero dei JSON gia salvati; normalizzazione locale, nessuna chiamata AI.
  Non vengono riscritti righe, valori confermati o file durante il recupero.
- Nuove letture salvate anche prima del match. Un dato opzionale assente non
  invalida la lettura e non causa riletture cicliche. Risultati vuoti, pagine
  errate e tipi rifiutati non sono accettati come letture riuscite.
- Valori manuali e interpretazione LST03 restano separati dalla lettura del PDF.
  Non vengono trasformati in una lettura globale, ne usati per inventare dati
  originali mancanti. Rimangono invariati i trasferimenti fra righe gia esistenti.
  Il blocco delle nuove chiamate e una protezione separata sul documento,
  non un blocco della modifica manuale o della rivalutazione del match.
- Copie profonde: applicare note/LST03 a una riga non modifica la lettura comune
  o i dati che ricevera un'altra riga.
- Leichtmetall: controllo tipo nuovo/rifiutato conservato; riuso solo di letture
  gia verificate oppure di storico gia definitivamente validato. Un blocco tipo
  vince anche su una cache in memoria. Rilettura valida puo superare un vecchio
  controllo fallito senza consentire di riclassificare documenti gia usati.
- Rilettura esplicita: una nuova lettura per azione utente, poi condivisa tra
  identita, chimica, proprieta e note. Non quattro chiamate per lo stesso PDF.
- PostgreSQL: advisory lock per documento su connessione dedicata/autocommit,
  senza lock di riga durante la richiesta AI; due worker non rileggono insieme.
  Connessione/short writer separati dal pool business (test anche con pool da una
  sola connessione), per evitare attese incrociate. Attesa limitata che include
  il possibile recupero identita Arconic; mai una seconda lettura per aggirarla.
  Cache e contabilita sono salvate in transazioni brevi indipendenti dalle
  modifiche Incoming pendenti. SQLite temporaneo usa la transazione di test.
- Ledger tentativi con response ID/modello/token input, output, cached e
  reasoning. Timeout/costi non noti rimangono NULL, non zero. Non salva chiavi,
  prompt, immagini o messaggi di errore contenenti dati sensibili.
- Una risposta gia pagata rimane nella memoria del run se il salvataggio fallisce:
  prima vengono ritentate solo le scritture. Se non e recuperabile dopo arresto
  o riavvio, una futura elaborazione puo rileggerla; non esiste un blocco permanente.
  Un guasto persistente non viene presentato come completamento riuscito.
- Provenienza: nomi dei ritagli e pagine dei normalizzatori sono conservati;
  Impol usa i testi PDF/OCR gia salvati per riconoscere la pagina delle note.
  Non si inventano coordinate o pagine quando la citazione resta ambigua.
- Nessuna modifica a numerazione, Word, PDF, seconde pagine, allegati,
  ereditarieta, standard, export eSolver o schema Quarta.

Riferimenti ufficiali verificati con OpenAI Docs:
[uso token](https://developers.openai.com/api/docs/guides/token-counting),
[modello e prezzi gpt-5.5](https://developers.openai.com/api/docs/models/gpt-5.5).
Il ledger non e una fattura in EUR: prezzi/cambio/tasse e usage non restituito
richiedono riconciliazione con il pannello del fornitore.
I reasoning token sono gia inclusi nell'output e non vanno sommati una seconda
volta. I cached input token OpenAI non sono il riuso locale del documento:
quest'ultimo evita interamente una chiamata.

## Compatibilita e test

- Baseline iniziale: 145 test match/LST03/tipo/fornitori superati.
- Replay offline di 31.164 coppie Alpha: nessuna differenza di punteggio o
  scarto fra normalizzazione dei JSON precedenti e letture recuperate.
  Valori Incoming invariati. Scoring/proposta iniziali dei JSON identici all'HEAD
  precedente. Non confondere questa equivalenza della cache con l'equivalenza
  dei due percorsi di match: il successivo audit del rematch ha trovato i tre
  difetti descritti sotto e ne ha autorizzato la correzione locale.
- Nuovi test: riavvio/run successivo, file diverso, cache corrotta, campi assenti,
  righe multiple/pesi distinti, valori manuali e LST03, tipo Leichtmetall,
  rilettura esplicita, token e timeout, cancellazione del solo documento fixture.
- PostgreSQL isolato: due sessioni/un'unica estrazione; cache sopravvive al
  rollback senza confermare modifiche business; preview/apply idempotente e
  rifiuto se la sorgente e cambiata. Nessun DB dell'app usato dai test.
- Protezione manuali iniziale: 22 test specifici superati con API vietata. Entrambi gli
  ordini di arrivo, batch completo, merge/sgancio, dati assenti, PDF su piu righe,
  pesi Leichtmetall distinti, conflitti e candidati concorrenti manuali/AI.
  Prove reali sui metodi applicativi di conferma e disaccoppio; variazione dei
  codici interni Arconic indebolisce/esclude il candidato, non solo dei campi UI.
  Provato anche il rifiuto del vecchio match raw dopo una correzione manuale.
- PostgreSQL dedicato iniziale: sette test eseguiti (non saltati), compresa protezione
  manuale concorrente e migrazione idempotente dei marcatori, valida anche quando
  i valori sono successivamente svuotati. Il digest prova invariati tutti i
  record originari, escludendo soltanto gli ID dei marcatori appena autorizzati.
- Suite locale estesa al primo controllo riuscito: 755 passati, 130 saltati
  (principalmente test di altri percorsi PostgreSQL opt-in), nessun fallimento.
  Prima esecuzione con blocco rete troppo largo impediva socketpair Windows:
  corretto il solo harness per consentire loopback, non il prodotto.
- Prima chiusura locale dopo protezione manuali/correzioni/sgancio: **794 passati,
  127 saltati, nessun fallimento**, rete esterna bloccata e DB PostgreSQL effimero
  dedicato. I sette PostgreSQL di questa modifica sono eseguiti; i 127 saltati
  appartengono ad altri percorsi opt-in non abilitati, non al collaudo richiesto
  qui. Ultimo replay 31.164 coppie: zero differenze di scoring e valori originari
  invariati; 212 JSON riusabili, 4 certificati manuali separati, 8 nuovi/da esaminare.
  Il frontend non cambia; nessun riavvio dei servizi dell'app necessario ai test.
  Nessuna nuova chiamata AI a pagamento per il collaudo della protezione manuale.
- Collaudo AI reale: gpt-5.5, tre certificati (Metalba + due Arconic) e un DDT
  Arconic multiriga, 7 pagine totali. Quattro risposte riuscite, stima costo API
  0,36845 USD secondo token/listino, ampiamente nel budget 5 EUR autorizzato.
  Tre run di riuso dei certificati in nuove sessioni: zero nuove chiamate,
  identita/chimica/proprieta/campi fornitore identici. DDT con due righe:
  2.1 -> EEP73062-44270958, 3.1 -> EEP73061-44262209; gli incroci sono respinti.
  Nessuna scrittura su Alpha o sul database dell'app locale. Chiave solo in
  memoria, mai nei report/file. Le variazioni successive di hardening su pool,
  salvataggio/provenienza e tipo sono ricollaudate offline e su PostgreSQL isolato,
  senza ripagare gli stessi test di lettura.

### Seconda revisione indipendente e correzioni rematch (29/10, solo locale)

I 794 test precedenti passavano ma non coprivano tre difetti riprodotti con API
vietata. L'utente ha autorizzato le correzioni locali; Alpha rimane invariata.

- Il percorso sui valori salvati poteva ignorare contraddizioni gia rifiutate
  dal matcher fornitore (es. Metalba: 6082 contro una vera modifica manuale a
  7075, oppure pesi/ordini diversi). Aggiunti gli stessi vincoli di contraddizione
  sui dati disponibili di Metalba, Impol, Leichtmetall, AWW, Neuman, Arconic e
  Grupa Kety. Nessun nuovo campo obbligatorio o punteggio piu permissivo.
  Riutilizzate le tolleranze peso gia proprie dei fornitori e i campi interni.
  Leichtmetall conserva i discriminanti peso/ordine delle singole righe.
- I candidati non utilizzabili erano filtrati DOPO la scelta: il secondo poteva
  essere promosso senza sufficiente affidabilita. Ora il filtro precede ranking,
  soglia forte e verifica di ambiguita. Separati target protetti da fonti protette:
  una riga gia elaborata/accoppiata resta una fonte di sola lettura; le righe
  rifiutate dal controllo tipo non vengono utilizzate come fonti.
- Due righe potevano riferirsi allo stesso certificato-only: dopo il primo merge
  la seconda seguiva un ID appena eliminato. Il piano viene ricalcolato sui dati
  attuali per ogni destinazione e ritrova la fonte accoppiata. Merge concorrenti:
  lock ordinati e rivalutazione sotto lock; se un'altra transazione ha assorbito
  la fonte, si rilegge il piano senza altra chiamata AI o riscrittura manuale.
  Restano conferme, vincoli di sgancio e scelta della data accettazione esistenti.

LST03 NON e un conflitto: conserva `metalba_lst03` e `valore_grezzo` originale;
il rematch usa quest'ultimo, Incoming puo mostrare 6082H. Non equiparare invece
una vera lega manuale diversa, o un 6082H storico senza prova della lega raw.
Il confronto offline ha inoltre trovato ordini storici manuali abbreviati
(`169` contro `169/26`): l'assenza dell'anno non e una contraddizione ma non
assegna un nuovo bonus. Radici diverse e due anni espliciti diversi restano
incompatibili. Nessun campo viene completato o normalizzato nel DB per questo.

Replay su copia locale della fotografia Alpha: 31.164 confronti JSON/cache senza
differenze; 31.551 confronti tra righe salvate. I nuovi vincoli scartano 10
incroci Metalba con dati discordanti e un confronto Neuman con articolo diverso.
**Eccezione dati da ricontrollare in lettura prima del deploy:** riga 91,
certificato documento 90, DDT `75732547`, CDQ `26141`: articolo DDT
`A62082BIU`, certificato `A62082BTU`. Non dedurre automaticamente che I sia T;
non rileggere con AI e non correggere/sganciare lo storico come parte del deploy.
Il confronto segnala la discordanza, non dimostra quale documento sia corretto.
Nella fotografia la riga e validata e il match e confermato dall'utente: il
rematcher non la modifica. Le associazioni gia presenti non vengono bonificate
o cancellate dal deploy.

Nessuna nuova migrazione per queste tre correzioni: rimangono solo le due
tabelle cache/consumi e i marcatori manuali gia previsti. Nessuna modifica a
Word/PDF/standard/ereditarieta o al frontend. Test di applicazione solo su DB
isolati. Chiusura dopo le correzioni: **811 test superati, 127 altri opt-in
saltati, nessun fallimento**. Eseguiti tutti i nove PostgreSQL dedicati (non
saltati), incluso merge concorrente con una sola fonte assorbita, e 32 test
specifici manuali/rematch. Provati anche sganci persistenti dopo merge multiplo
e riuso di una fonte validata senza riaprirla o riscriverla. Test concorrente
ripetuto separatamente con esito positivo. Nessuna chiamata AI aggiuntiva,
nessuna scrittura sul DB dell'app o su Alpha; PostgreSQL di prova effimero.

### Ricontrollo Alpha 29/10, ore 20:30 italiane — sola lettura

Alpha usa ancora il sorgente 9a2a98e5, senza nuove tabelle cache e senza run AI
attivi al controllo. Su 224 certificati: 219 letture salvate riutilizzabili
(le sette elaborazioni prima attive sono terminate), quattro manuali protetti
e un Bozen #326, CDQ 159233, privo di lettura salvata e di righe Incoming.
Quest'ultimo non entra nella ricerca automatica dello storico, che seleziona i
certificati gia presenti su righe Incoming. Nessun certificato storico oggi
selezionabile richiede quindi una nuova chiamata AI con il codice candidato.

Nel controllo delle provenienze risultano anche due DDT protetti, #205 e #43:
#43 ha una lettura AI pregressa ma anche un evento esatto `ddt_manuale_creato`
per la riga #68 (oltre alla #61) e valori manuali. La politica documento
protegge anche questo inserimento misto; non classificarlo dai soli contatori AI.
Pertanto la futura preview puo aggiungere marcatori per quattro certificati e
due DDT, non applicare alla cieca il precedente conteggio 4+1. Ricalcolare ancora
al deploy e sottoporre la preview corrente con digest all'utente.

Verifica con sole SELECT READ ONLY e normalizzatori installati eseguiti in RAM:
nessun bootstrap/job, nuova chiamata AI, scrittura o modifica file su Alpha.
Esportati solo conteggi ed eccezioni necessarie, non l'archivio documentale.

## Procedura Alpha futura

Seguire il runbook principale; questa nota NON autorizza il deploy.

1. Audit spazio, utenti/writer, run AI e generazioni. Se un run e attivo, attendere;
   non fermarlo per installare questa modifica.
2. Backup coerente e restore isolato verificato secondo runbook. Non copiare il
   DB locale in Alpha. Nessun recupero dati applicativo massivo.
3. In contesto di codice candidato senza avviare bootstrap/job, eseguire preview
   `python -m scripts.prepare_certificate_ai_reuse`. E read-only e funziona anche
   quando le due nuove tabelle non esistono. Riconfermare conteggi/eccezioni:
   la fotografia del 29/10 non e una lista di ID da applicare alla cieca.
   La preview distingue `manual_no_automatic_ai` dai casi `needs_read_or_review`
   e riporta separatamente i DDT manuali. Non approvare una lista di nuove
   letture che includa i manuali citati. Nel replay: 212 JSON + 4 manuali + 8
   nuovi/non completi; il DDT manuale 205 e nell'inventario separato.
4. Dopo approvazione, in manutenzione concordata e senza writer, applicare la
   preview corrente con digest esatto, backup e flag manutenzione. NOWAIT rifiuta
   writer concorrenti; digest rifiuta dati cambiati. La sola transazione crea
   `documenti_ai_estrazioni` e `documenti_ai_consumi`, recupera le letture gia
   presenti e aggiunge i soli marcatori `manual_document_entry` dei documenti
   classificati dalla preview approvata (nella fotografia 4 certificati + 1 DDT).
   Il digest prima/dopo deve essere identico escludendo ESCLUSIVAMENTE gli ID di
   queste nuove evidenze autorizzate; nessun record originario cambia. Il report
   espone ID documenti/evidenze aggiunti. Non scrive valori/righe, non riscrive
   altre evidenze o eventi, non genera file e non chiama AI. Secondo apply: zero
   nuove marcature; la nuova preview ha il digest comprensivo dei marcatori.
5. Avvio controllato nuovo backend; verificare schema, cache, campioni/multiriga,
   letture riusate senza nuovi consumi e normale ricezione DDT. Nessuna chiamata
   a pagamento o generazione reale di prova su Alpha senza autorizzazione.
6. Seconda preview idempotente; conteggi/file/Word/PDF/export invariati. Eccezioni
   non complete restano distinte: non abbassare soglie e non inventare dati.

Rollback: conservare le due tabelle additive e tutto il resto. Il vecchio codice
non le usa e riprenderebbe le riletture costose, senza applicare il nuovo guard
dei manuali: dichiarare il ritorno di questi limiti, non presentarlo come rollback
equivalente o riaprire l'automatismo senza valutazione. Non eliminare
cache, righe, documenti o ledger per fare rollback del codice.
