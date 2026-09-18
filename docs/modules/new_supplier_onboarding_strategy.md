# Linea generale per nuovi fornitori

## Stato del documento

- Audit applicativo completato in locale il 30/07/2026.
- Audit tecnico dell'innesto isolato completato in locale il 10/08/2026.
- Documento di analisi e piano: nessuna parte descritta qui è stata implementata.
- Nessuna modifica al codice applicativo, al database o al server Alpha è autorizzata da questo documento.
- Prima di iniziare il codice serve un nuovo `ok` o `procedi` esplicito dell'utente.
- Le soglie numeriche di match riportate sono una proposta iniziale da approvare.
- Il futuro laboratorio non deve essere incluso nei deploy Alpha durante lo sviluppo locale.

## Obiettivo

Creare una linea generale configurabile per:

- nuovi fornitori;
- fornitori oggi gestiti come generici;
- fornitori che in futuro dovranno passare da generici a preferenziali.

La linea dovrà coprire l'intero percorso:

1. anagrafica e riconoscimento del fornitore;
2. caricamento DDT e certificati;
3. classificazione del tipo di documento;
4. estrazione locale, OCR e mascheratura;
5. analisi assistita dall'AI;
6. creazione delle righe Incoming;
7. match DDT-certificato, compresa la conferma automatica quando è realmente sicura;
8. chimica, proprietà, note e forma materiale;
9. valutazione qualità;
10. proposta e conferma dello standard;
11. collegamento con Quarta ed eSolver;
12. generazione Word e chiusura del PDF finale.

Il risultato operativo deve essere simile a quello dei fornitori preferenziali esistenti, senza dover scrivere da zero un nuovo ramo Python per ogni fornitore.

## Decisioni già confermate

1. Deve esistere una pagina di configurazione per ogni nuovo fornitore.
2. La configurazione deve raccogliere dal cliente le informazioni specifiche del fornitore.
3. L'app può usare l'AI sui documenti campione per proporre la configurazione.
4. L'AI assiste la configurazione ma non la attiva autonomamente.
5. I campi di match devono poter avere pesi da 1 a 10.
6. Alcuni campi devono poter essere obbligatori o bloccanti.
7. Quando il risultato è sufficientemente forte e univoco, il match deve essere confermato automaticamente.
8. Devono funzionare sia il percorso DDT prima sia il percorso certificato prima.
9. Un certificato deve poter coprire più righe, quando la regola reale del fornitore lo permette.
10. Non esiste un numero fisso obbligatorio di tre DDT o tre certificati.
11. I nove fornitori dedicati esistenti non devono cambiare comportamento nella prima fase.
12. La mascheratura finale deve usare i margini reali iniziale e finale di ogni nome, scritta, icona o logo, coprendo tutto l'oggetto ma non i campi tecnici vicini.
13. Lo sviluppo della linea generale deve rimanere su un branch dedicato e separato da `main` finché non è completo e approvato.
14. Durante lo sviluppo il laboratorio deve funzionare solamente in locale ed essere accessibile esclusivamente a un utente con ruolo `admin` e reparto `IT`.
15. Il laboratorio potrà essere installato su Alpha solamente dopo test locali, audit conclusivo e un nuovo `procedi` esplicito dell'utente.
16. La prima installazione futura su Alpha resterà comunque separata dal flusso operativo: nessuna scrittura in Incoming e nessuna attivazione produttiva.

## Significato di “insegnare all'app”

Non viene addestrato o modificato permanentemente il modello AI.

Il processo corretto è:

1. l'AI analizza esempi reali;
2. propone campi, formati, regole e relazioni;
3. l'utente controlla e corregge;
4. l'app salva queste decisioni in un profilo versionato del fornitore;
5. il motore generale usa quel profilo sui documenti futuri.

Quindi ciò che rimane nell'app non è una memoria nascosta dell'AI, ma una configurazione leggibile, verificabile e modificabile.

---

## Audit dello stato attuale

### 1. Fornitori attualmente gestiti

Il registro dei reader contiene nove fornitori dedicati:

- Aluminium Bozen;
- AWW;
- Arconic Hannover;
- Grupa Kety;
- Impol;
- Leichtmetall;
- Metalba;
- Neuman;
- Zalco.

L'audit del database locale del 30/07/2026 ha trovato solamente questi nove fornitori:

| Fornitore | Documenti | Righe Incoming |
|---|---:|---:|
| Aluminium Bozen | 12 | 13 |
| AWW | 2 | 2 |
| Arconic Hannover | 9 | 5 |
| Grupa Kety | 12 | 14 |
| Impol | 22 | 15 |
| Leichtmetall | 22 | 17 |
| Metalba | 30 | 17 |
| Neuman | 7 | 4 |
| Zalco | 7 | 5 |

Ogni fornitore dedicato ha oggi una propria `reader_template_key`.

Un fornitore importato da eSolver entra invece:

- attivo;
- collegato all'anagrafica eSolver;
- senza `reader_template_key`;
- senza un flusso automatico completo equivalente ai nove fornitori.

### 2. Limite della chiave template attuale

La funzione che cerca un fornitore tramite `reader_template_key` usa una ricerca che presuppone un solo fornitore per chiave.

Di conseguenza non è sicuro assegnare a tutti i nuovi fornitori una stessa chiave come:

```text
general_ai
```

Se più fornitori condividessero quella chiave, la ricerca potrebbe diventare ambigua o generare errore.

La linea generale deve quindi avere:

- un motore comune;
- un profilo distinto per ogni fornitore;
- un identificativo e una versione del profilo separati dalla chiave dei nove parser dedicati.

### 3. Caricamento e batch

Il caricamento attuale:

- accetta DDT e certificati;
- calcola l'hash del file;
- blocca un duplicato già persistente;
- riutilizza o elimina correttamente un temporaneo fallito;
- indicizza le pagine PDF;
- prova a correggere automaticamente il tipo documento;
- prova a riconoscere il fornitore;
- mantiene un batch temporaneo recuperabile o scartabile;
- non avvia l'Assistente AI finché tutti i documenti non hanno un fornitore.

Questa base è riutilizzabile.

Limiti per la linea generale:

- la classificazione DDT/certificato usa marker generali più alcune eccezioni dedicate;
- i layout nuovi possono contenere intestazioni diverse;
- l'identità del fornitore viene cercata principalmente nel nome file e nelle prime due pagine;
- un nome breve o simile a un altro fornitore può lasciare il documento senza assegnazione;
- non esiste ancora una configurazione per marker e layout specifici del nuovo fornitore.

### 4. Lettura documentale

La sequenza locale già prevista è valida:

1. testo PDF;
2. render della pagina;
3. OCR;
4. crop del blocco utile;
5. parser locale;
6. AI sui casi o sui percorsi configurati.

I nove fornitori hanno però:

- parser DDT specifici;
- regole diverse di suddivisione delle righe;
- payload e prompt AI specifici;
- normalizzazioni e controlli specifici;
- logiche di estrazione dei certificati specifiche.

Il fornitore generico può beneficiare di alcuni parser generali di chimica e proprietà, ma oggi non dispone dell'intero percorso autonomo dei fornitori dedicati.

### 5. Mascheratura

I nove fornitori hanno funzioni di mascheratura e crop dedicate.

Il fallback generale usa aree centrali del documento, per esempio corpo alto, medio e basso. Questi crop riducono il rischio, ma non dimostrano che:

- logo;
- ragione sociale;
- cliente;
- indirizzi;
- contatti;
- footer;

siano sempre coperti.

L'audit del codice mostra inoltre due strategie differenti:

- per le scritte sono già disponibili bounding box OCR di parola o gruppo di parole;
- per alcuni elementi grafici sono disponibili componenti connesse dentro una zona di ricerca;
- diversi loghi sono però ancora coperti con rettangoli percentuali fissi;
- alcuni rettangoli vengono allargati con margini generici e possono coprire più del necessario.

Per la linea generale il rettangolo fisso non deve essere la maschera finale. Può essere usato solamente come area nella quale cercare l'oggetto.

La maschera finale deve essere calcolata sul contenuto realmente trovato:

- `x_min`: inizio reale più a sinistra;
- `y_min`: inizio reale più in alto;
- `x_max`: fine reale più a destra;
- `y_max`: fine reale più in basso;
- piccolo margine di sicurezza controllato per bordi, antialiasing e imprecisioni di lettura.

Per un nome composto il bounding box deve comprendere tutte e sole le parole appartenenti al nome. Per un logo composto deve comprendere simbolo, icona ed eventuale scritta collegata.

Quindi per un nuovo fornitore la dicitura “dati sensibili mascherati” non può basarsi solamente sui crop generici.

La mascheratura deve essere configurata e approvata per ciascun layout prima di inviare i campioni all'AI.

### 6. Utilizzo attuale dell'AI

La pipeline AI completa è abilitata esplicitamente solamente per i nove `supplier_key`.

Esistono:

- prompt DDT specifici;
- prompt certificato specifici;
- normalizzatori specifici;
- conservazione di payload AI come evidenza;
- salvataggio di valore grezzo, standardizzato e finale.

Esiste inoltre una regola comune corretta per i controlli US:

- Class A e Class B vanno considerate separatamente;
- un controllo limitato alle estremità non certifica tutto il materiale;
- `100% inspection ends of bars` significa tutte le estremità, non tutto il materiale.

Questa regola deve essere riutilizzata anche dalla linea generale.

Limiti attuali:

- il modello, la versione del prompt e la versione del profilo non sono legati in modo completo e consultabile a ogni lettura;
- alcune evidenze conservano il payload raw, ma manca un vero tentativo di elaborazione versionato;
- non esiste una procedura AI che trasformi campioni di un nuovo fornitore in una bozza di profilo.

### 7. Valori raw, normalizzazione e maiuscole/minuscole

Il modello dati già distingue:

- valore grezzo;
- valore standardizzato;
- valore finale;
- evidenza;
- metodo di lettura;
- confidenza.

Questo è corretto e va mantenuto.

Regola obbligatoria per la linea generale:

- il valore raw visibile deve conservare esattamente maiuscole, minuscole e segni del documento;
- la normalizzazione usata per il confronto deve essere separata;
- ogni campo deve poter dichiarare se il confronto è case-sensitive;
- una normalizzazione non deve mai sovrascrivere il raw.

Esempio:

```text
Raw certificato: 17394#a
Normalizzato per confronto: 17394#A
Valore mostrato: 17394#a
```

### 8. Creazione delle righe DDT

Oggi le regole cambiano molto per fornitore:

- un DDT può produrre una riga;
- un DDT può produrre più righe;
- righe stampate diverse possono essere aggregate;
- il peso può essere diretto oppure somma di colli;
- il dettaglio utile può essere in seconda pagina;
- packing list, lotto, colata o charge possono determinare la riga.

Questa parte non può essere dedotta solo dalla forma grafica della tabella.

Il profilo dovrà descrivere esplicitamente:

- l'unità materiale;
- la chiave di raggruppamento;
- come si calcola il peso;
- come si trattano totali e sottorighe;
- quando fermarsi e chiedere verifica.

### 9. Match attuale

Il motore attuale possiede:

- filtro per stesso fornitore;
- normalizzazioni di lega, diametro, peso, colata e codici;
- campi forti diversi per alcuni fornitori;
- blocchi sui mismatch critici;
- ranking di candidati;
- gestione cross-run;
- protezione contro il riaggancio immediato dopo uno scollegamento manuale;
- possibilità che lo stesso certificato sia valutato contro più righe.

Per un fornitore generico esistono già combinazioni generali, per esempio:

- CDQ;
- colata + diametro + peso;
- ordine + lega + diametro + colata.

Tuttavia:

- i pesi sono fissi nel codice;
- le combinazioni forti sono fisse;
- alcune eccezioni dipendono dal nome del fornitore;
- le soglie non sono configurabili;
- il percorso automatico normalmente crea un match `proposto`;
- la conferma avviene successivamente quando i campi documentali risultano confermati.

Questo non soddisfa completamente la nuova richiesta: nella linea generale un match realmente forte e univoco deve poter nascere direttamente come confermato automaticamente.

### 10. Percorso certificato prima

Il certificate-first è oggi abilitato esplicitamente per i nove fornitori.

Il flusso può:

- creare una riga da un certificato;
- leggere chimica, proprietà e note;
- collegare successivamente il DDT;
- unire la riga certificato con quella DDT;
- mantenere i blocchi già confermati.

La linea generale dovrà rendere questa possibilità parte del profilo, non di un elenco fisso di nove chiavi.

### 11. Incoming e valutazione qualità

Quando una riga contiene correttamente i dati, le funzioni successive sono già in gran parte indipendenti dal fornitore:

- Incoming;
- conferma chimica;
- conferma proprietà;
- conferma note;
- forma materiale;
- tipo estrusione;
- nota valutazione;
- accettato, accettato con riserva o respinto;
- data di accettazione;
- KPI.

La linea generale non deve creare una seconda logica di qualità.

Deve alimentare i campi canonici esistenti e lasciare invariato il comportamento successivo.

### 12. Forma materiale e standard

Il classificatore comune distingue:

- billetta;
- barra;
- profilo;
- estruso generico;
- materiale da verificare;
- dati discordanti.

La proposta standard usa poi:

- lega;
- variante;
- forma materiale;
- trattamento;
- diametro o spessore.

La scelta finale dello standard resta dell'utente.

Per la linea generale è quindi necessario estrarre e conservare la descrizione reale del prodotto, senza dedurla dal solo nome del fornitore o da note US.

### 13. Quarta, eSolver, Word e PDF finale

La parte finale è già sostanzialmente indipendente dal parser del fornitore, ma richiede dati corretti a monte.

Per creare il Word servono almeno:

- standard confermato;
- riga Incoming trovata tramite CDQ e colata;
- certificato collegato;
- chimica, proprietà e note confermate;
- qualità accettata o accettata con riserva;
- codice Ref. del fornitore;
- dati Quarta/eSolver coerenti.

Per chiudere il PDF servono inoltre:

- Word presente;
- DDT presente;
- data certificato;
- conformità standard confermata.

Conseguenza:

un errore nella configurazione di CDQ, colata, righe o match può arrivare fino alla Certificazione. I test non possono fermarsi alla griglia Incoming.

### 14. Versionamento e storico

Oggi il reader viene risolto dinamicamente dal fornitore.

Se si cambiasse semplicemente il template assegnato al fornitore:

- documenti vecchi riaperti potrebbero essere riletti con regole nuove;
- righe aperte e chiuse potrebbero comportarsi in modo diverso;
- diventerebbe difficile capire con quale configurazione è stato prodotto un dato.

La linea generale deve quindi salvare la versione effettivamente utilizzata.

### 15. Copertura test attuale

Esistono test per:

- parser generici di chimica e proprietà;
- riconoscimento tipo documento;
- nove fornitori dedicati;
- masking di alcuni fornitori;
- match e rematch;
- certificate-first;
- conservazione dei blocchi già confermati;
- forma materiale e proposta standard;
- Quarta/eSolver;
- Word e PDF;
- KPI.

Mancano test per:

- creazione di un profilo da interfaccia;
- configurazione proposta dall'AI;
- validazione del profilo;
- match configurabile con pesi 1-10;
- conferma automatica tracciata come decisione del sistema;
- versionamento del profilo;
- cambio layout;
- promozione da generico a preferenziale.

### 16. Audit tecnico dell'innesto isolato

L'innesto è fattibile, ma non deve essere sviluppato direttamente dentro il servizio operativo di Acquisition.

L'audit del codice ha rilevato:

- il controllo frontend `isItAdmin` è già disponibile;
- il controllo backend `require_it_admin` è già disponibile e deve proteggere ogni API, file e anteprima del laboratorio;
- la pagina Fornitori normale è accessibile anche al reparto Qualità e quindi non è una posizione sufficientemente isolata;
- il servizio operativo Acquisition supera 32.000 righe e contiene numerosi rami specifici per fornitore;
- caricamento, indicizzazione, OCR, creazione righe, evidenze e match eseguono oggi scritture e `commit` sulle entità operative;
- il controllo dei run attivi è principalmente legato all'utente che li ha avviati e non protegge da ogni possibile sovrapposizione tra un test Lab e un run operativo;
- il progetto usa `Base.metadata.create_all` e procedure additive, senza una gestione completa delle migrazioni tipo Alembic.

Conseguenza:

- durante lo sviluppo il laboratorio deve essere un modulo autonomo;
- non deve importare o chiamare i servizi che creano righe Incoming;
- può riutilizzare algoritmi tecnici solo dopo averli separati dalle scritture operative;
- le prime modifiche dati devono aggiungere esclusivamente nuove tabelle Lab, senza alterare le tabelle esistenti;
- il futuro collegamento produttivo deve passare da una decisione centralizzata sul percorso del fornitore, mantenendo invariati i nove rami dedicati.

---

## Architettura proposta

### 1. Motore generale e profilo specifico

La soluzione proposta è:

```text
Motore generale
└── Profilo fornitore A, versione 1
└── Profilo fornitore B, versione 3
└── Profilo fornitore C, versione 2
```

Il motore contiene solamente operazioni controllate e riutilizzabili.

Il profilo contiene:

- identità e alias;
- layout DDT e certificato;
- marker di classificazione;
- regole di mascheratura;
- campi da leggere;
- formato dei campi;
- regole di normalizzazione;
- regole di riga;
- campi e pesi del match;
- cardinalità;
- soglie;
- prompt aggiuntivi;
- test approvati.

### 2. Niente codice arbitrario scritto dall'AI

L'AI non deve generare Python da eseguire.

Deve scegliere o proporre operazioni dichiarative consentite, per esempio:

- cerca etichetta;
- leggi a destra;
- leggi sotto;
- estrai dalla stessa riga;
- prendi una colonna tabellare;
- raggruppa per colata;
- somma i pesi;
- rimuovi spazi nel confronto;
- conserva zeri iniziali;
- confronto esatto;
- confronto numerico con tolleranza.

Se un documento non può essere descritto con queste operazioni, la pagina deve indicare:

```text
Layout troppo specifico: necessario parser dedicato.
```

### 3. Profilo versionato e immutabile dopo l'attivazione

Ogni modifica produce una nuova versione:

```text
Bozza → Test → Approvata in laboratorio → Pilota operativo → Attiva in produzione → Archiviata
```

Una versione attiva non viene modificata direttamente.

I documenti devono conservare la versione usata durante la lavorazione.

Regola proposta:

- nuovi caricamenti: usano la nuova versione attiva;
- righe chiuse: non vengono modificate;
- righe storiche aperte: non vengono rilette automaticamente;
- eventuale rilettura: solo tramite azione esplicita e con anteprima dell'impatto.

### 4. Modello dati futuro proposto

Entità minime:

#### `supplier_processing_profiles`

- `id`;
- `supplier_id`, univoco;
- `mode`: `configurable` o `dedicated`;
- `status`;
- `active_version_id`;
- autore e date.

#### `supplier_processing_profile_versions`

- `id`;
- `profile_id`;
- numero versione;
- stato;
- configurazione JSON validata;
- versione dello schema configurazione;
- versione prompt;
- modello AI previsto;
- autore;
- approvatore;
- data attivazione;
- note.

#### `supplier_profile_samples`

- versione profilo;
- documento campione;
- ruolo: DDT, certificato, match, no-match, ambiguo;
- layout;
- relazione attesa;
- risultato atteso.

#### `supplier_profile_test_runs`

- versione profilo;
- data;
- documenti usati;
- risultato per fase;
- errori;
- chiamate AI;
- modello;
- token/costo stimato;
- utente che ha eseguito il test.

#### Collegamenti runtime

Da valutare in progettazione tecnica:

- `processing_profile_version_id` sul documento;
- versione usata sulla riga o sul tentativo di lettura;
- versione regole, punteggio e motivi sul match;
- modalità conferma match: `automatica` o `utente`;
- tentativo di elaborazione con modello, prompt, esito e payload raw.

Non è necessario duplicare chimica, proprietà, note o campi Incoming: devono continuare a usare le entità esistenti.

### 5. Laboratorio isolato durante lo sviluppo

Il laboratorio deve affiancare l'applicazione senza entrare nel flusso operativo:

```text
Applicazione CERTI_nt
├── Flusso operativo attuale
│   └── nove fornitori dedicati invariati
│
└── Laboratorio nuovi fornitori
    ├── accesso esclusivo Admin IT
    ├── profili e versioni in prova
    ├── campioni e risultati separati
    ├── OCR, mascheratura, AI e simulazione match
    └── nessuna scrittura in Incoming
```

Struttura tecnica futura proposta:

```text
backend/app/modules/supplier_lab/
frontend/src/pages/supplierLab/
storage/supplier_lab/
```

Le entità profilo e versione possono avere fin dall'inizio la struttura definitiva. Campioni, esecuzioni e file di prova devono invece rimanere separati dai documenti operativi.

Il laboratorio non deve usare direttamente:

- `documenti_fornitore` per i campioni;
- `datimaterialeincoming` per simulare le righe;
- i run autonomi di Acquisition;
- le notifiche email operative;
- le funzioni che applicano direttamente risultati AI, match o valori alle righe reali.

Durante lo sviluppo non devono ancora esistere nel branch `main`:

- route frontend del laboratorio;
- API `/api/supplier-lab`;
- tabelle e storage Lab;
- flag di abilitazione Lab;
- collegamenti dal motore operativo.

Questi elementi devono vivere nel branch locale dedicato proposto:

```text
feature/supplier-lab
```

Il nome identifica il ramo futuro: il branch non esiste ancora e verrà creato solamente quando inizierà lo sviluppo autorizzato.

### 6. Separazione tra approvazione Lab e produzione

Gli stati devono distinguere chiaramente configurazione e utilizzo operativo:

```text
Bozza
  ↓
Test
  ↓
Approvata in laboratorio
  ↓  solo dopo nuova autorizzazione e installazione controllata
Pilota operativo
  ↓
Attiva in produzione
```

Durante lo sviluppo locale si può arrivare solamente a `Approvata in laboratorio`.

Quando in futuro il laboratorio verrà installato su Alpha, dovranno esistere due blocchi indipendenti:

```dotenv
SUPPLIER_LAB_ENABLED=true
GENERAL_SUPPLIER_RUNTIME_ENABLED=false
```

Il primo rende disponibile il laboratorio solamente ad Admin IT. Il secondo mantiene disabilitato qualsiasi uso del profilo nel caricamento reale.

Per attivare in futuro un fornitore serviranno contemporaneamente:

1. abilitazione generale del motore sul server;
2. abilitazione operativa del singolo profilo fornitore;
3. un nuovo `procedi` esplicito dell'utente.

---

## Nuova pagina “Configurazione lettura fornitore”

### Posizione proposta

```text
Amministrazione
└── Laboratorio nuovi fornitori
    └── Configurazione fornitore
```

Percorso frontend futuro proposto:

```text
/admin/supplier-lab
```

La pagina deve essere distinta dal normale dettaglio Fornitore. Nel dettaglio fornitore potrà comparire un collegamento solamente per Admin IT, ma non deve essere il controllo di sicurezza principale.

Ogni route frontend deve usare una regola `itAdminOnly`. Ogni API, anteprima, PDF campione e file derivato deve usare il controllo backend `require_it_admin` e restituire `403` agli altri utenti.

La pagina deve mostrare sempre il banner:

```text
LABORATORIO IT
I risultati non entrano nel flusso operativo.
```

La pagina deve mostrare sempre:

- nome fornitore;
- collegamento eSolver;
- modalità attuale;
- versione attiva;
- stato;
- ultima prova;
- eventuali errori;
- pulsanti consentiti per stato.

### Sezione 1 - Identità

Informazioni richieste:

- fornitore locale;
- codice eSolver;
- ragione sociale ufficiale;
- alias;
- vecchi nomi;
- lingue dei documenti;
- codice Ref. da usare nel certificato finale;
- eventuali stabilimenti con layout diversi.

L'AI può proporre gli alias trovati, ma l'utente decide quali salvare.

### Sezione 2 - Documenti campione

Caricamento separato di:

- DDT;
- certificati;
- eventuali packing list o allegati.

Per ogni documento l'utente deve poter indicare:

- tipo corretto;
- layout;
- se appartiene allo stesso caso materiale di un altro documento;
- se è un esempio positivo, negativo o ambiguo;
- se il certificato copre una o più righe.

Non va imposto un numero fisso di documenti.

Regola pratica:

- minimo tecnico per iniziare l'analisi: un DDT e un certificato correttamente abbinati;
- serve almeno un esempio per ogni layout realmente usato;
- prima dell'attivazione del match automatico serve anche dimostrare che un certificato sbagliato o ambiguo non venga confermato;
- il numero finale dipende dalla varietà reale, non da una quota prefissata.

### Sezione 3 - Layout e classificazione

Per ogni layout:

- DDT o certificato;
- digitale o scansione;
- numero tipico di pagine;
- pagina principale;
- pagine tabellari;
- marker forti;
- marker da non usare;
- regole nome file;
- rotazione;
- lingue OCR;
- presenza di più righe;
- presenza di più colate;
- presenza di allegati.

L'app mostra:

- classificazione proposta;
- motivi;
- affidabilità;
- conflitti con altri layout.

### Sezione 4 - Mascheratura

Per ogni layout:

- elementi sensibili da coprire;
- ancore testuali;
- blocchi grafici;
- logo;
- indirizzo;
- cliente;
- contatti;
- footer;
- aree tecniche che devono restare visibili.

Per ogni elemento da coprire la configurazione deve conservare:

- tipo: nome, scritta, icona, simbolo, logo o blocco misto;
- area di ricerca approssimativa;
- metodo di individuazione;
- margine iniziale e finale rilevato;
- bounding box finale;
- margine di sicurezza applicato;
- confidenza;
- campi tecnici protetti nelle vicinanze.

Metodi previsti:

- OCR e unione delle bounding box per nomi e scritte;
- componenti grafiche e analisi del contrasto per icone e simboli;
- template/layout matching per loghi stabili;
- rilevazione dell'intero oggetto per loghi composti da simbolo e testo.

Regola:

```text
Area configurata = zona nella quale cercare.
Bounding box rilevato = zona precisa da coprire.
```

Non si deve coprire automaticamente tutta l'area di ricerca.

Per un nome su più parole:

- individuare la prima parola;
- seguire solamente le parole contigue appartenenti allo stesso nome;
- fermarsi prima dell'etichetta o del campo tecnico successivo;
- unire i margini della prima e dell'ultima parola.

Per un'icona o un logo:

- individuare tutti i componenti grafici appartenenti allo stesso oggetto;
- includere eventuale scritta integrata nel marchio;
- calcolare il rettangolo esterno dell'intero gruppo;
- non includere linee, tabelle o testi tecnici vicini.

Flusso obbligatorio:

1. rilevazione locale;
2. calcolo dei margini reali;
3. controllo che il bounding box non intersechi campi tecnici protetti;
4. generazione anteprima con bordo visibile prima dell'applicazione;
5. generazione anteprima mascherata;
6. controllo visivo;
7. approvazione dell'utente;
8. solo dopo invio all'AI.

Se la mascheratura è incerta:

- nessuna chiamata AI;
- profilo non attivabile;
- messaggio chiaro.

### Sezione 5 - Regole di riga DDT

Domande al cliente:

- che cosa rappresenta una riga Incoming?
- il DDT è monoriga o pluririga?
- più righe vanno aggregate?
- qual è la chiave: colata, lotto, charge, certificato o combinazione?
- il peso è di riga, totale o somma colli?
- lo stesso DDT può richiedere più certificati?
- un certificato può coprire più righe?
- quali righe sono totali e non devono generare materiale?
- quali dati possono essere ripetuti su pagine successive?

L'AI può proporre la struttura osservata, ma la regola viene confermata dall'utente.

### Sezione 6 - Campi DDT e certificato

Per ogni campo canonico:

- nome del campo nel documento;
- esempio reale;
- documento origine;
- pagina/blocco;
- metodo di lettura;
- formato;
- lunghezza;
- caratteri ammessi;
- separatori;
- zeri iniziali;
- maiuscole/minuscole;
- prefissi e suffissi;
- valore obbligatorio o facoltativo;
- fallback;
- prova documentale richiesta.

Campi iniziali:

- fornitore;
- numero DDT;
- data DDT;
- CDQ;
- colata;
- ordine;
- lega;
- variante documentale;
- diametro o dimensione;
- peso;
- articolo;
- profilo/codice cliente;
- lotto, batch o charge;
- descrizione prodotto;
- numero colli, se realmente presente.

Ogni campo deve mostrare tre valori:

```text
Raw | Normalizzato | Finale
```

### Sezione 7 - Dati tecnici del certificato

Configurazione per:

- riga chimica misurata;
- righe min/max da escludere;
- proprietà misurate;
- unità;
- note standard;
- requisiti cliente;
- Class A;
- Class A Type 1 BSH;
- Class B;
- descrizione prodotto;
- barra, billetta, profilo o forma incerta;
- eventuali prove riferite a una sola colata.

Regole comuni da mantenere:

- non inventare valori;
- non trasformare min/max in misurato;
- non dedurre Class A o B da controlli limitati a estremità o zone locali;
- non dedurre la forma materiale da una semplice nota UT;
- conservare la frase raw e l'evidenza.

### Sezione 8 - Configurazione match

Tabella proposta:

| Campo | Uso | Peso 1-10 | Confronto | Obbligatorio | Bloccante se diverso |
|---|---|---:|---|---|---|
| CDQ | match | 10 | esatto/configurato | sì/no | sì/no |
| Colata | match | 10 | esatto/normalizzato | sì/no | sì/no |
| Ordine | match | 8 | esatto/normalizzato | sì/no | sì/no |
| Articolo | match | 7 | esatto | sì/no | sì/no |
| Lega | supporto | 6 | lega normalizzata | sì/no | sì/no |
| Diametro | match | 6 | numerico/tolleranza | sì/no | sì/no |
| Peso | supporto | 4 | numerico/tolleranza | sì/no | sì/no |
| DDT | supporto | 3 | esatto/normalizzato | sì/no | sì/no |

Questi valori sono solo un esempio. Devono essere proposti dall'AI e approvati dall'utente per il singolo fornitore.

Per ogni campo si sceglie:

- non usato;
- supporto;
- obbligatorio;
- bloccante;
- sufficiente da solo se è un identificativo realmente univoco.

### Sezione 9 - Prova completa

La pagina deve mostrare:

- righe DDT create;
- valori estratti;
- raw e normalizzati;
- evidenze e pagina;
- anteprima mascherata;
- candidati certificato;
- punteggio per candidato;
- campi uguali;
- campi mancanti;
- mismatch;
- motivo dell'esclusione;
- risultato: conferma automatica, proposta o nessun match;
- chimica, proprietà e note;
- forma materiale;
- simulazione dei prerequisiti per Incoming e Certificazione.

### Sezione 10 - Attivazione

Stati:

```text
Bozza
  ↓
Test
  ↓
Approvata in laboratorio
  ↓
Pilota operativo
  ↓
Attiva in produzione
```

Il pulsante `Approva in laboratorio` deve essere disponibile solo se:

- mascheratura approvata;
- layout coperti;
- campi obbligatori configurati;
- test positivi superati;
- test negativi o ambigui non confermati erroneamente;
- codice Ref. presente quando necessario;
- nessun errore bloccante.

Il laboratorio locale non deve mostrare un pulsante utilizzabile per `Pilota operativo` o `Attiva in produzione`.

### Percorso pratico Admin IT

```text
Seleziona fornitore
        ↓
Carica DDT e certificati campione
        ↓
Indica documenti collegati e risultati attesi
        ↓
Controlla e approva la mascheratura
        ↓
Valuta le proposte AI per campi e regole
        ↓
Configura pesi e vincoli del match
        ↓
Esegue test positivi, negativi e ambigui
        ↓
Approva il profilo in laboratorio
```

L'Admin IT configura e verifica il comportamento; non scrive codice. Il codice resta responsabilità dello sviluppo e le decisioni dell'Admin vengono salvate come configurazione versionata e leggibile.

---

## Configurazione assistita dall'AI

### Sequenza sicura

#### Fase A - Analisi locale

Prima dell'AI:

- estrazione testo PDF;
- OCR;
- riconoscimento pagine;
- rilevazione delle ancore;
- identificazione locale delle aree sensibili;
- rilevazione precisa dei margini di nomi, scritte, icone e loghi;
- raggruppamento dei componenti appartenenti allo stesso oggetto;
- controllo delle intersezioni con campi tecnici protetti;
- generazione mascheratura.

#### Fase B - Approvazione mascheratura

L'utente controlla visivamente ogni layout campione.

Nessun documento non approvato viene inviato all'AI.

#### Fase C - Estrazione indipendente

L'AI riceve un documento alla volta.

Per ogni campo restituisce:

- valore raw;
- pagina;
- immagine/crop sorgente;
- frase o riga di evidenza;
- nome dell'etichetta trovata;
- formato osservato;
- affidabilità;
- eventuali alternative;
- motivazione dell'incertezza.

Il DDT e il certificato non devono essere presentati subito come coppia certa, per evitare che l'AI forzi una corrispondenza.

#### Fase D - Confronto strutturato

Dopo l'estrazione indipendente, una seconda chiamata riceve principalmente i dati strutturati, non di nuovo tutti i PDF.

L'AI propone:

- campi comuni;
- differenze di formato;
- normalizzazioni;
- possibili chiavi forti;
- campi deboli;
- campi bloccanti;
- pesi 1-10;
- cardinalità;
- casi dubbi.

#### Fase E - Bozza del profilo

La proposta AI viene tradotta solamente nelle operazioni ammesse dal motore generale.

Ogni proposta resta marcata:

```text
Proposta AI
```

finché l'utente non la conferma.

#### Fase F - Test

La configurazione viene eseguita in ambiente di prova sui campioni.

Non crea righe Incoming di produzione e non modifica documenti già presenti.

### Perché due fasi AI sono preferibili

Una sola richiesta con tutti i PDF:

- costa di più;
- aumenta il contesto;
- rende più difficile capire da quale pagina arriva un dato;
- può spingere l'AI ad abbinare documenti per supposizione;
- rende più difficile confrontare il risultato con quello precedente.

L'estrazione singola seguita dal confronto dei JSON è più controllabile e più economica.

### Informazioni AI da tracciare

Per ogni chiamata:

- obiettivo;
- fornitore e versione profilo;
- documento e pagine;
- modello;
- versione prompt;
- data;
- esito;
- payload raw;
- risultato normalizzato;
- token;
- costo stimato;
- errore o retry;
- utente che ha avviato il test.

### Limiti dell'AI

L'AI non deve:

- attivare il profilo;
- inventare etichette assenti;
- decidere da sola la cardinalità definitiva;
- scrivere codice eseguibile;
- modificare l'anagrafica;
- sovrascrivere valori raw;
- confermare un match se mancano le protezioni configurate.

---

## Motore di match configurabile

### 1. Selezione dei candidati

Prima del punteggio:

- stesso fornitore obbligatorio;
- documento di tipo certificato;
- documento non escluso manualmente;
- compatibilità con il layout;
- rispetto della cardinalità configurata;
- riga non chiusa o bloccata;
- nessun conflitto forte già noto.

### 2. Stato di ogni campo

Ogni confronto produce:

- `match`;
- `match parziale`;
- `mancante DDT`;
- `mancante certificato`;
- `mismatch`;
- `non applicabile`.

La spiegazione deve essere visibile.

### 3. Punteggio

Proposta:

```text
punteggio = somma dei pesi ottenuti / somma dei pesi applicabili × 100
```

Protezione necessaria:

- un campo mancante non può trasformare un confronto povero in 100%;
- oltre al punteggio serve una copertura minima dei pesi configurati;
- serve un numero sufficiente di prove indipendenti;
- un solo campo può bastare soltanto se l'utente lo ha dichiarato identificativo univoco e sufficiente.

### 4. Condizioni proposte per conferma automatica

Proposta iniziale da approvare:

- punteggio almeno `90/100`;
- copertura almeno `80%` del peso previsto;
- tutti i campi obbligatori presenti e coerenti;
- nessun campo bloccante diverso;
- distanza dal secondo candidato almeno `15` punti;
- almeno due prove forti indipendenti, salvo identificativo univoco configurato;
- nessun blocco manuale;
- versione profilo attiva;
- nessun errore di lettura sui campi usati.

Esito:

```text
MATCH CONFERMATO AUTOMATICAMENTE
```

Nel database deve risultare:

- stato `confermato`;
- fonte `sistema`;
- utente conferma vuoto;
- punteggio;
- versione regole;
- motivi;
- candidati confrontati;
- timestamp.

### 5. Altri esiti proposti

```text
90-100 e tutte le protezioni rispettate → confermato automaticamente
70-89 oppure candidato vicino          → proposto all'utente
sotto 70                              → nessun match
mismatch bloccante                    → candidato escluso
```

Le soglie devono essere configurabili per fornitore entro limiti di sicurezza stabiliti dall'app.

### 6. Esempio

Configurazione:

- CDQ peso 10, obbligatorio;
- colata peso 10, bloccante;
- ordine peso 8;
- lega peso 6;
- diametro peso 6;
- peso peso 4.

Candidato A:

- tutti i campi coerenti;
- punteggio 100;
- nessun secondo candidato vicino;
- conferma automatica.

Candidato B:

- stesso ordine e stessa lega;
- colata diversa;
- escluso anche se il punteggio parziale fosse alto.

Candidato C:

- CDQ e colata coerenti;
- altri dati mancanti;
- risultato dipendente dalla copertura minima, non confermato automaticamente se le prove sono insufficienti.

### 7. Correzione manuale

L'utente deve poter:

- scollegare un match automatico;
- scegliere un altro certificato;
- indicare il motivo;
- creare un blocco contro il riaggancio immediato della stessa coppia.

Le righe già chiuse non devono essere cambiate automaticamente.

---

## Percorsi operativi

### DDT prima

1. carico il DDT;
2. il profilo crea una o più righe;
3. legge i campi DDT;
4. cerca certificati già presenti;
5. se il certificato arriva dopo, viene eseguito il rematch;
6. se le regole sono forti, il match viene confermato automaticamente;
7. vengono letti chimica, proprietà e note.

### Certificato prima

1. carico il certificato;
2. nasce una riga certificate-first;
3. vengono letti CDQ, colata, chimica, proprietà e note;
4. quando arriva il DDT, il sistema cerca la riga certificate-first corretta;
5. unisce le due parti;
6. mantiene i blocchi tecnici già confermati;
7. applica le regole di match del profilo.

### Un certificato per più righe

Consentito solamente quando il profilo lo dichiara.

Il match viene calcolato separatamente per ogni riga e deve conservare:

- stessa sorgente PDF;
- campi della riga specifica;
- evidenza della colata/lotto/charge;
- motivazione del collegamento.

### Un DDT con più certificati

Il DDT viene suddiviso secondo la chiave configurata.

Ogni riga cerca il proprio certificato. Il numero DDT comune non può, da solo, collegare lo stesso certificato a tutte le righe.

---

## Promozione da generico a preferenziale

Flusso proposto:

1. importare o collegare il fornitore da eSolver;
2. verificare anagrafica e alias;
3. inserire il codice Ref.;
4. creare il profilo in bozza;
5. caricare campioni;
6. approvare la mascheratura;
7. eseguire l'analisi AI assistita;
8. confermare campi, righe e match;
9. eseguire test positivi, negativi e ambigui;
10. attivare in modalità pilota;
11. controllare i primi casi reali;
12. attivare definitivamente.

Lo storico già chiuso non viene ricalcolato.

Se il fornitore è troppo particolare:

- resta generico;
- oppure viene sviluppato un parser dedicato;
- il profilo può comunque conservare campioni, analisi e decisioni raccolte.

---

## Informazioni da chiedere al cliente

La pagina deve aiutare il cliente con domande semplici.

### Anagrafica

- Qual è il nome corretto del fornitore?
- Esistono vecchi nomi o abbreviazioni?
- Qual è il codice eSolver?
- Qual è il codice Ref. da riportare nel certificato?

### DDT

- Come si riconosce il numero DDT?
- Quale campo rappresenta il vostro ordine?
- Dove si trova il CDQ?
- Come sono scritte colata e lega?
- Una riga stampata corrisponde sempre a una riga Incoming?
- Il peso è di riga o totale?
- I colli vanno sommati?

### Certificato

- Qual è il vero numero certificato?
- Quale campo collega il certificato al DDT?
- Il certificato può coprire più colate o più righe?
- Dove sono la riga chimica misurata e le proprietà misurate?
- Quali righe sono solamente min/max?
- Quali note devono essere rilevate?

### Match

- Qual è il campo più affidabile?
- Quali campi devono coincidere obbligatoriamente?
- Quale differenza rende il match impossibile?
- Quali campi aiutano ma non bastano?
- Un codice cambia formato tra DDT e certificato?
- Maiuscole e minuscole sono significative?
- Quali tolleranze sono ammesse per peso e dimensione?

### Privacy e mascheratura

- Quali nomi devono essere coperti?
- Il logo va coperto?
- Quali indirizzi e contatti sono presenti?
- Quali aree tecniche non devono mai essere coperte?

Ogni risposta può avere stato:

- `mancante`;
- `proposta AI`;
- `confermata utente`;
- `da rivedere`.

---

## Rischi principali e protezioni

### Match errato confermato automaticamente

Protezione:

- campi bloccanti;
- copertura minima;
- margine sul secondo candidato;
- test negativo;
- motivazione completa;
- correzione manuale con blocco.

### Profilo condiviso tra fornitori

Protezione:

- un profilo per `supplier_id`;
- niente chiave generale condivisa nel campo attuale.

### Perdita di maiuscole/minuscole

Protezione:

- raw immutato;
- normalizzato separato;
- confronto case-sensitive configurabile.

### Mascheratura incompleta

Protezione:

- area fissa usata solamente per la ricerca;
- bounding box finale ricavato dai margini reali dell'oggetto;
- unione controllata delle parole di un nome;
- raggruppamento di simbolo, icona e testo dello stesso logo;
- piccolo padding controllato, non rettangoli ampi arbitrari;
- controllo che la maschera non intersechi campi tecnici protetti;
- anteprima obbligatoria;
- nessuna chiamata AI se non approvata;
- profilo non attivabile.

### AI che forza il match

Protezione:

- estrazione dei documenti separata;
- confronto successivo sui JSON;
- decisione finale del motore deterministico;
- l'AI propone, non conferma direttamente.

### Cambio layout del fornitore

Protezione:

- riconoscimento layout;
- confidenza minima;
- documento sconosciuto fermato;
- nuova versione del profilo;
- nessuna modifica automatica allo storico.

### Righe DDT create male

Protezione:

- regola di aggregazione esplicita;
- anteprima righe;
- totali esclusi;
- test multi-pagina e multi-collo.

### Errore che arriva fino al Word/PDF

Protezione:

- test end-to-end;
- controllo CDQ/colata;
- codice Ref.;
- standard;
- qualità;
- Word e PDF compresi nel collaudo.

### Costi e tempi AI

Protezione:

- analisi locale prima;
- chiamate per documento;
- seconda chiamata sui dati strutturati;
- cache;
- budget e costo visibili;
- nessun batch cieco.

### Regressioni sui nove fornitori

Protezione:

- mantenere i rami dedicati;
- introdurre il motore generale senza sostituirli;
- suite di regressione completa prima del pilota.

---

## Piano di implementazione futuro

### Fase 0 - Documentazione e separazione branch

- aggiornare questo piano e la procedura di deploy Alpha;
- mantenere `main` come unica fonte dei deploy Alpha correnti;
- creare `feature/supplier-lab` solamente quando parte lo sviluppo autorizzato;
- non unire il branch Lab in `main` durante lo sviluppo locale;
- non creare ancora route, API, tabelle, flag o storage Lab su Alpha.

### Fase 1 - Chiusura decisioni

Prima del codice confermare:

- soglie del match;
- copertura minima;
- margine tra candidati;
- primo fornitore pilota;
- politica di conservazione dei campioni;
- modello e budget AI;
- trattamento delle righe aperte dopo una nuova versione.

### Fase 2 - Guscio isolato e sicurezza locale

- creare il modulo Lab separato;
- aggiungere route frontend `itAdminOnly`;
- proteggere tutte le API e i file con `require_it_admin`;
- aggiungere il flag Lab solamente all'ambiente locale del branch dedicato;
- verificare `403` per ogni ruolo non autorizzato;
- verificare che il flusso operativo non importi il modulo Lab.

### Fase 3 - Modello profilo e versioni

- creare entità profilo;
- validare schema configurazione;
- gestire stati;
- legare campioni e tentativi alla versione;
- impedire modifiche dirette a una versione approvata;
- aggiungere audit.

Le nuove tabelle devono essere additive. Non aggiungere colonne alle tabelle operative durante questa fase.

### Fase 4 - Pagina di configurazione

- pagina autonoma Admin IT;
- wizard;
- domande;
- campioni;
- layout;
- campi;
- regole riga;
- match;
- test;
- approvazione in laboratorio.

### Fase 5 - Laboratorio documentale e AI

- ambiente di prova separato da Incoming;
- OCR e classificazione;
- mascheratura e preview;
- estrazione AI singola;
- confronto strutturato;
- proposta profilo;
- tracciamento costi.

Durante questa fase campioni e risultati restano nello storage e nelle tabelle Lab. Nessuna email operativa deve essere inviata.

### Fase 6 - Motore generale di lettura in simulazione

- riconoscimento layout;
- estrazione DDT;
- simulazione delle righe senza creare Incoming;
- estrazione certificato;
- chimica;
- proprietà;
- note;
- descrizione prodotto e forma materiale;
- evidenze.

### Fase 7 - Match configurabile in simulazione

- pesi 1-10;
- campi obbligatori;
- campi bloccanti;
- tolleranze;
- cardinalità;
- ranking;
- conferma automatica simulata;
- proposta manuale simulata;
- cross-run simulato sui campioni;
- certificate-first;
- scollegamento e blocco.

### Fase 8 - Collaudo locale e approvazione Lab

- un solo test Lab alla volta;
- nessun test mentre è in corso un run operativo locale;
- test positivi, negativi, ambigui, DDT-first e certificate-first;
- controllo che le tabelle operative non cambino;
- regressione completa sui nove fornitori;
- audit conclusivo prima di qualsiasi merge.

### Fase 9 - Prima installazione futura su Alpha

Questa fase richiede un nuovo `procedi` esplicito.

- unire il branch Lab in `main` solamente dopo approvazione;
- aggiornare intenzionalmente la procedura deploy che oggi blocca il modulo Lab;
- installare il laboratorio con accesso esclusivo Admin IT;
- mantenere `GENERAL_SUPPLIER_RUNTIME_ENABLED=false`;
- ripetere su Alpha i test di sicurezza e isolamento;
- non creare righe operative.

### Fase 10 - Integrazione completa futura

Questa fase richiede un'ulteriore autorizzazione separata.

- Incoming;
- Valutazione;
- KPI;
- standard;
- Quarta;
- eSolver;
- codice Ref.;
- Word;
- PDF;
- Registro certificazione.

Non devono essere create logiche qualità parallele.

Il collegamento deve usare una decisione centralizzata:

```text
fornitore dedicato         → percorso attuale invariato
profilo generale abilitato → motore generale
altro fornitore            → comportamento attuale
```

Il codice attuale contiene molti smistamenti specifici. Non deve essere rifattorizzato integralmente insieme al primo Lab: si aggiunge inizialmente solamente il percorso generale nei punti di ingresso controllati.

### Fase 11 - Pilota operativo

- un solo nuovo fornitore;
- modalità Pilota;
- controllo manuale dei primi casi;
- confronto dati estratti con i PDF;
- nessuna estensione ad altri fornitori finché il pilota non è stabile.

### Fase 12 - Estensione e regressione

- regressione sui nove fornitori;
- attivazione di un secondo nuovo fornitore con layout diverso;
- verifica che la configurazione sia realmente riutilizzabile;
- eventuale decisione su parser dedicati.

---

## Test obbligatori

### Isolamento preliminare

Prima dei test funzionali devono essere superati questi controlli:

- il branch Lab non viene usato per creare un pacchetto Alpha durante lo sviluppo;
- il modulo Lab non è presente sul server Alpha prima dell'autorizzazione;
- solamente Admin IT vede il collegamento e la pagina locale;
- utenti Qualità, manager, utenti normali e Admin non-IT ricevono `403` dalle API Lab;
- file e anteprime Lab non sono scaricabili tramite URL diretto da utenti non autorizzati;
- caricamento, elaborazione e cancellazione di un campione non modificano documenti operativi;
- nessuna riga Incoming, match, valutazione, KPI, Quarta, Word, PDF o Registro viene creata o modificata;
- nessuna email operativa viene inviata;
- disabilitando il flag Lab, pagina e API non sono disponibili;
- un riavvio locale conserva profili e campioni Lab senza toccare i dati operativi.

### Configurazione

1. Creazione profilo in bozza.
2. Nuova versione senza alterare quella attiva.
3. Campi mancanti impediscono l'attivazione.
4. Configurazione non valida rifiutata.
5. Permessi utente verificati.

### Documenti e identità

6. DDT digitale.
7. DDT scansione.
8. Certificato digitale.
9. Certificato scansione.
10. Tipo documento corretto.
11. Tipo ambiguo lasciato da verificare.
12. Fornitore corretto tramite alias.
13. Fornitore ambiguo non assegnato automaticamente.
14. Duplicato persistente bloccato.
15. Temporaneo fallito ricaricabile.

### Mascheratura

16. Nome singolo coperto dal primo all'ultimo margine reale.
17. Nome composto coperto dalla prima all'ultima parola corretta, senza inglobare il campo successivo.
18. Icona coperta sul proprio bounding box completo.
19. Logo composto coperto includendo simbolo e scritta collegata.
20. Cliente, indirizzo e contatti coperti completamente.
21. Area di ricerca più grande del logo: viene coperto solamente il logo rilevato.
22. Margine di sicurezza sufficiente a coprire bordi e antialiasing.
23. Campi tecnici vicini completamente visibili.
24. Linee e celle della tabella non scambiate per parti del logo.
25. Oggetto grafico non riconosciuto con sufficiente confidenza: documento bloccato.
26. Layout sconosciuto bloccato.
27. Nessuna chiamata AI senza approvazione.

### Lettura DDT

28. DDT monoriga.
29. DDT pluririga.
30. Raggruppamento per colata/lotto.
31. Peso diretto.
32. Peso somma colli.
33. Totale non trasformato in riga.
34. Dettaglio in seconda pagina.
35. Raw preservato.
36. Maiuscole/minuscole preservate.

### Lettura certificato

37. CDQ corretto.
38. Colata corretta.
39. Riga chimica misurata.
40. Min/max esclusi.
41. Proprietà misurate.
42. Unità normalizzate.
43. Note standard.
44. Class A/B con controllo generale.
45. Class A/B limitata alle estremità esclusa.
46. Descrizione prodotto e forma materiale.

### AI

47. Estrazione indipendente.
48. Evidenza e pagina presenti.
49. Campo incerto restituito vuoto.
50. Payload raw conservato.
51. Modello, prompt, costo e versione tracciati.
52. Timeout/retry senza duplicare righe.
53. Proposta AI non attivata automaticamente.

### Match

54. Match forte e unico confermato automaticamente.
55. Fonte sistema e nessun utente conferma.
56. Match medio solamente proposto.
57. Match basso non creato.
58. Mismatch bloccante escluso.
59. Secondo candidato vicino impedisce la conferma automatica.
60. Campo mancante riduce la copertura.
61. Identificativo unico sufficiente solamente se configurato.
62. Stesso certificato su più righe quando consentito.
63. Stesso certificato bloccato su più righe quando non consentito.
64. Un DDT con più certificati.
65. Scollegamento manuale e blocco riaggancio.
66. Match di un altro fornitore sempre escluso.

### Ordine di arrivo

67. DDT prima, certificato dopo.
68. Certificato prima, DDT dopo.
69. Certificate-first mantiene chimica, proprietà e note confermate.
70. Cross-run trova documenti già presenti.
71. Riga chiusa non modificata dal rematch.

### Flusso finale

72. Riga visibile in Incoming con fornitore corretto.
73. Chimica, proprietà e note confermabili.
74. Valutazione invariata.
75. KPI invariati.
76. Forma materiale coerente.
77. Standard proposto nello stesso modo in Incoming e Certificazione.
78. CDQ/colata trovati da Quarta.
79. Codice Ref. presente.
80. Word generato.
81. PDF chiuso.
82. Registro aggiornato.

### Regressione

83. Test completi sui nove fornitori dedicati.
84. Nessun cambio delle loro mascherature.
85. Nessun cambio dei loro prompt.
86. Nessun cambio dei loro match.
87. Nessun ricalcolo dello storico.

---

## Criteri di accettazione del pilota

Il primo fornitore può uscire dalla modalità Pilota quando:

- tutti i layout noti sono coperti;
- nessun dato sensibile è visibile nelle preview approvate;
- ogni nome, scritta, icona e logo è coperto fino ai propri margini reali;
- nessun campo tecnico vicino viene coperto dalla maschera;
- i campi critici hanno evidenza;
- i test positivi vengono confermati correttamente;
- i casi negativi e ambigui non vengono confermati automaticamente;
- DDT-first e certificate-first funzionano;
- righe e pesi sono corretti;
- chimica, proprietà e note sono corrette;
- il flusso arriva a Word e PDF;
- non ci sono regressioni sui nove fornitori;
- cliente e qualità approvano il risultato.

---

## Decisioni ancora aperte

| Decisione | Proposta iniziale | Stato |
|---|---|---|
| Soglia conferma automatica | 90/100 | Da confermare |
| Copertura minima | 80% | Da confermare |
| Margine sul secondo candidato | 15 punti | Da confermare |
| Minimo prove forti | 2, salvo ID unico | Da confermare |
| Ruoli modifica profilo durante sviluppo | Solo Admin IT | Confermato |
| Ruoli approvazione in laboratorio | Solo Admin IT | Confermato |
| Presenza su Alpha durante sviluppo | Esclusa | Confermato |
| Branch di sviluppo | `feature/supplier-lab`, da creare all'avvio | Confermato |
| Attivazione produttiva | Separata e soggetta a nuovo `procedi` | Confermato |
| Primo fornitore pilota | Non scelto | Mancante |
| Modello AI onboarding | Da scegliere prima dei test | Mancante |
| Budget AI onboarding | Da stabilire per fornitore | Mancante |
| Conservazione campioni | Da definire | Mancante |
| Nuova versione e righe aperte | Nessuna rilettura automatica | Da confermare |
| Eccezioni case-sensitive | Per singolo campo | Da confermare |

Questa tabella è il punto unico per tenere traccia di ciò che manca prima del codice.

## File collegati

- `docs/modules/ddt_supplier_template_analysis_template.md`
- `docs/modules/ddt_certificates_data_acquisition.md`
- `docs/modules/document_reading_tools_sequence.md`
- `docs/modules/document_openai_double_check_strategy.md`
- `docs/modules/masking_strategy_placeholder.md`
- `docs/modules/fornitori.md`
- `docs/modules/fornitori_produzione.md`
- `docs/tasks/material_form_standard_selection_plan.md`
