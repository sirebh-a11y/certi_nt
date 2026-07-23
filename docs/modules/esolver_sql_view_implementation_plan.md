# Vista SQL CERTI verso ESOLVER - piano operativo

Data piano: 2026-07-23
Stato: implementazione locale completata; pubblicazione esterna in attesa dei dati IT
Blocco attuale per il collaudo esterno: in attesa dei soli parametri di rete e accesso
PostgreSQL predisposti da IT/Matteo

## Regola operativa

Questo documento definisce come realizzare la vista SQL letta da ESOLVER/Nemesi.

Non modificare codice, database, configurazione di rete o server finché Silvano non comunica
esplicitamente `procedi`.

Le credenziali e in particolare la password non devono essere salvate in questo file o
committate nel repository Git. Nel documento si registrano soltanto i parametri non segreti e
il nome del secret o della variabile usata per configurare la password.

## Obiettivo

Esporre a ESOLVER una vista PostgreSQL in sola lettura contenente i certificati PDF
definitivamente chiusi e ancora validi.

Ogni record deve permettere a ESOLVER di:

- identificare il certificato CERTI;
- individuare esattamente documento e riga DDT ESOLVER;
- distinguere OL, CodF3 e lotto;
- conoscere quantità e data del certificato;
- scaricare il PDF tramite URL;
- riconoscere una nuova versione del PDF;
- verificare quando la versione corrente è stata chiusa.

La vista non sostituisce il PDF: espone il collegamento HTTP già protetto dal token di download.

## Decisioni funzionali confermate

### Un certificato per ogni riga/quota ESOLVER

La regola confermata è:

> ogni combinazione reale di riga DDT, quota, OL, CodF3 e lotto produce il proprio record
> certificato.

Non vengono sommate automaticamente righe DDT differenti, anche quando appartengono allo
stesso OL o allo stesso ordine cliente.

Esempio:

- riga 7, OL 271, quantità 484: un certificato;
- riga 8, OL 271, quantità 45: un certificato distinto;
- riga 8, OL 455, quantità 455: un ulteriore certificato distinto.

La soluzione non deve collegare implicitamente lo stesso PDF a più righe DDT.

### Nome dell'identificativo riga

Il campo viene esposto come `IdRigaDoc`, coerentemente con:

- la vista ESOLVER `CertiRigheDDT`;
- il nome già letto da CERTI;
- l'endpoint HTTP già verificato da Walter/Nemesi.

Il campo documento viene esposto come `IdDocumento`.

### Versione e chiusura PDF

La vista espone anche:

- `PdfVersion`;
- `ClosedAt`.

La vista contiene soltanto PDF chiusi e attualmente validi.

Quando un certificato viene riaperto:

- sparisce dalla vista;
- la precedente versione resta nello storico interno CERTI;
- non viene più presentata come PDF valido.

Quando viene nuovamente chiuso:

- ricompare con lo stesso `IdCerti`;
- presenta un `PdfVersion` superiore;
- presenta nuovi valori di `ClosedAt` e `UpdatedAt`.

## Situazione applicativa verificata

CERTI dispone già della maggior parte dei dati richiesti.

La tabella principale è:

`quarta_taglio_final_certificates`

Contiene già:

- ID CERTI;
- OL;
- CodF3;
- DDT;
- `esolver_id_documento`;
- `esolver_id_riga_doc`;
- `esolver_rif_lotto_alfanum`;
- quantità;
- numero e data certificato;
- stato;
- percorso PDF;
- token di download;
- data chiusura;
- data ultimo aggiornamento.

La tabella:

`quarta_taglio_certificate_pdf_versions`

contiene già:

- numero versione PDF;
- versione attiva;
- versioni riaperte;
- data e motivo della riapertura;
- data di generazione.

La separazione per riga/quota è già rappresentata dalla `unit_key`, che include:

`OL + CodF3 + DDT + IdDocumento + IdRigaDoc + RifLottoAlfanum + ordini`

Su `unit_key` esiste già un indice univoco per i valori non vuoti.

## Esposizione attuale

Oggi non esiste alcuna vista SQL salvata.

È disponibile soltanto l'endpoint:

`/api/export/esolver/certificati-pdf`

L'endpoint funziona ed è stato verificato da Nemesi tramite il campo `PdfUrl`.

Verifica tecnica Alpha eseguita il 2026-07-23:

- URL pubblico:
  `http://certi-test.forgialluminio.it/api/export/esolver/certificati-pdf`;
- base URL configurata:
  `http://certi-test.forgialluminio.it`;
- autenticazione HTTP Basic attiva;
- username HTTP configurato: `Certi`;
- password HTTP presente nel `.env` del server e non riportata in questo documento;
- richiesta senza autenticazione: risposta `401`;
- richiesta autenticata: risposta valida con proprietà `Items` e `TotalItems`;
- al momento della verifica `TotalItems` era `0`, perché Alpha non conteneva PDF chiusi.

Le credenziali `CERTI_EXPORT_USERNAME` e `CERTI_EXPORT_PASSWORD` proteggono l'endpoint HTTP.
Non sono le credenziali PostgreSQL read-only della futura vista e non devono essere riutilizzate
automaticamente per l'accesso al database.

La nuova vista deve diventare la fonte dati canonica dell'export. L'endpoint HTTP deve
continuare a funzionare, leggendo gli stessi record della vista, così da evitare due logiche
parallele che in futuro potrebbero disallinearsi.

## Nome proposto

Schema PostgreSQL:

`esolver_export`

Vista:

`esolver_export.certi_certificati_pdf`

Lo schema separato consente di concedere a Nemesi l'accesso alla sola vista senza esporre le
tabelle applicative nello schema `public`.

Il nome definitivo può essere adeguato soltanto se IT/Nemesi ha già predisposto un nome
specifico.

## Contratto dati della vista

| Colonna | Tipo indicativo | Origine | Significato |
|---|---|---|---|
| `IdCerti` | integer | certificato finale | Identificativo stabile CERTI |
| `OL` | varchar | `cod_odp` | Ordine/lavorazione |
| `DDT` | text | `ddt` | Numero e data DDT |
| `IdDocumento` | varchar | identità ESOLVER | Documento ESOLVER |
| `IdRigaDoc` | varchar | identità ESOLVER | Riga del documento ESOLVER |
| `RifLottoAlfanum` | varchar | identità ESOLVER | Lotto/ORP esposto da ESOLVER |
| `CodF3` | text | certificato finale | Codice articolo certificato |
| `NumeroCertificato` | varchar | certificato finale | Numero definitivo |
| `DataCertificato` | timestamptz | certificato finale | Data del certificato |
| `Quantita` | double precision | unità certificabile | Quantità della riga/quota |
| `PdfUrl` | text | configurazione + ID + token | URL completo del PDF |
| `Stato` | varchar | valore derivato | Sempre `PDF_CHIUSO` nella vista valida |
| `PdfVersion` | integer | versioni PDF | Versione attiva del PDF |
| `ClosedAt` | timestamptz | certificato finale | Chiusura della versione valida |
| `UpdatedAt` | timestamptz | certificato finale | Ultima modifica del record |

## Regole di inclusione

Un record compare nella vista soltanto quando:

- lo stato del certificato è `pdf_final`;
- il percorso del PDF è valorizzato;
- il token di download è valorizzato;
- il file appartiene a una versione PDF attiva;
- `IdDocumento` è valorizzato e non vuoto;
- `IdRigaDoc` è valorizzato e non vuoto;
- `CodF3` è valorizzato e non vuoto;
- il DDT è valorizzato e non vuoto;
- il numero certificato è definitivo;
- la data certificato è valorizzata;
- `ClosedAt` è valorizzato.

I PDF storici senza `IdDocumento` o `IdRigaDoc` non devono essere esposti, perché ESOLVER non
potrebbe associarli in modo certo.

## Regole di esclusione

Non devono comparire:

- bozze Word;
- certificati in attesa DDT;
- PDF riaperti;
- certificati senza identità precisa della riga ESOLVER;
- record privi di PDF o token;
- versioni PDF annullate o riaperte;
- dati temporanei di test non chiusi.

## Nessun filtro degli ultimi 30 giorni

La vista in uscita da CERTI non applica il filtro degli ultimi 30 giorni.

Il limite dei 30 giorni riguarda la vista `CertiRigheDDT` fornita da ESOLVER a CERTI e non
l'esportazione dei certificati da CERTI verso ESOLVER.

Eventuali criteri temporali sull'acquisizione devono essere gestiti da Nemesi tramite
`UpdatedAt`, `ClosedAt` o `DataCertificato`, senza eliminare dalla vista certificati ancora
validi.

## Costruzione di PdfUrl

`PdfUrl` deve mantenere il formato già collaudato:

`<base-url>/api/quarta-taglio/certificates/<IdCerti>/pdf-file?download_token=<token>`

La base URL deve provenire dalla configurazione applicativa `CERTI_PUBLIC_BASE_URL`.

In Alpha il valore verificato è:

`http://certi-test.forgialluminio.it`

Non duplicare nel codice un dominio fisso valido soltanto per Alpha. La creazione o
l'aggiornamento della vista deve usare la base URL dell'ambiente corrente.

Il token è una credenziale di download incorporata nell'URL. Per questo la vista deve essere
accessibile esclusivamente all'utente read-only autorizzato.

## Accesso read-only

L'utente predisposto per Nemesi deve:

- poter effettuare il login al solo database previsto;
- avere `CONNECT` sul database;
- avere `USAGE` sullo schema `esolver_export`;
- avere `SELECT` sulla sola vista `certi_certificati_pdf`;
- non avere permessi di scrittura;
- non avere `SELECT` diretto sulle tabelle CERTI;
- non essere superuser;
- non poter creare database, ruoli, schemi o tabelle;
- avere, se possibile, transazioni predefinite in sola lettura.

La password deve essere:

- conservata in un secret o file di configurazione escluso da Git;
- comunicata tramite canale separato;
- mai riportata in questo documento;
- ruotabile senza modificare la definizione della vista.

## Parametri Alpha verificati e dati IT da completare

I valori marcati come verificati derivano dal deploy Alpha e dalla configurazione effettiva
del server. Completare soltanto i valori ancora assegnati a IT/Matteo o Nemesi.

| Parametro | Valore |
|---|---|
| Ambiente | `Alpha` - verificato |
| Hostname applicazione CERTI | `certi-test.forgialluminio.it` - verificato |
| Base URL applicazione/PDF | `http://certi-test.forgialluminio.it` - verificato |
| Motore database | `PostgreSQL 16` - verificato |
| Host PostgreSQL interno Docker | `postgres` - verificato |
| Porta PostgreSQL interna Docker | `5432` - verificato |
| Host o IP PostgreSQL da comunicare a Nemesi | proposto `certi-test.forgialluminio.it`, da confermare con IT |
| Porta PostgreSQL esterna | `DA_FORNIRE_IT` |
| Nome database | `certi_nt` - verificato |
| Nome schema | `esolver_export` salvo diversa indicazione |
| Nome vista richiesto da Nemesi | `certi_certificati_pdf` salvo diversa indicazione |
| Username endpoint HTTP | `Certi` - verificato, non è l'utente PostgreSQL |
| Password endpoint HTTP | configurata nel `.env` Alpha, non riportare nel repository |
| Username PostgreSQL read-only | `DA_FORNIRE_IT` |
| Nome secret password PostgreSQL read-only | `DA_DEFINIRE`, senza riportare la password |
| IP sorgente Nemesi autorizzato | `DA_FORNIRE_IT` |
| Rete/VPN autorizzata | `DA_FORNIRE_IT` |
| SSL richiesto | `DA_FORNIRE_IT` |
| Modalità SSL | `DA_FORNIRE_IT` |
| Certificato CA/client, se previsto | `DA_FORNIRE_IT` |
| Referente tecnico | Matteo / Nemesi, dettaglio da completare |

### Dati ESOLVER già noti ma relativi al flusso opposto

La documentazione Alpha contiene anche:

- server ESOLVER: `10.10.3.6`;
- porta SQL Server ESOLVER: `1433`;
- database: `ESOLVER`;
- viste lette da CERTI: `CertiCliForF3`, `CertiRigheDDT`, `CertiOL`.

Questi valori servono a CERTI per leggere ESOLVER e non definiscono l'accesso di Nemesi alla
nuova vista PostgreSQL di CERTI. Non devono quindi essere usati come host, porta o credenziali
della vista in uscita.

## Pagina Database - configurazione della vista in uscita

### Situazione attuale verificata

La pagina amministrativa `Database`, percorso `/integrations`, è accessibile soltanto agli
amministratori IT e presenta tre schede:

1. `eSolver`: connessione in ingresso usata da CERTI per leggere le viste ESOLVER;
2. `QuartaEVO`: connessione in ingresso usata da CERTI per leggere la tracciabilità Quarta;
3. `Certi verso eSolver`: endpoint HTTP in uscita usato da Nemesi per leggere i PDF chiusi.

Le prime due schede:

- salvano le password cifrate;
- non restituiscono la password al frontend;
- mostrano soltanto se la password è configurata;
- permettono di inserire una nuova password lasciando vuoto il campo per mantenere quella
  esistente.

La terza scheda è oggi soltanto informativa. Presenta però username e password dell'endpoint
scritti direttamente nel frontend e mostra la password in chiaro. Questo comportamento deve
essere corretto nello stesso intervento:

- nessuna password deve essere scritta nel codice frontend;
- la pagina deve ricevere dal backend soltanto `password_configured`;
- il valore visualizzato deve essere `••••••••` oppure `Configurata`;
- non deve esistere un pulsante per rivelare la password.

La correzione è solo di visualizzazione e sicurezza: non cambia le credenziali o il
funzionamento dell'endpoint.

### Struttura proposta della pagina

La pagina resta unica e contiene quattro schede:

1. `eSolver → CERTI`;
2. `QuartaEVO → CERTI`;
3. `CERTI → eSolver - Endpoint HTTP`;
4. `CERTI → eSolver - Vista PostgreSQL`.

Con quattro schede è preferibile usare una disposizione `2 × 2` sugli schermi desktop, invece
di comprimere tutti i moduli in quattro colonne strette. Su schermi più piccoli le schede
restano impilate.

Non serve creare una nuova voce di menu: la vista appartiene alla pagina `Database` già
riservata a IT.

### Dati mostrati nella nuova scheda Vista PostgreSQL

La quarta scheda mostra:

- stato generale: `Da configurare`, `Configurata`, `Test interno riuscito`,
  `Collaudo Nemesi riuscito`;
- ambiente;
- host/IP da comunicare a Nemesi;
- porta PostgreSQL esterna;
- database;
- schema;
- nome vista;
- username read-only;
- password: solo stato mascherato;
- IP/rete Nemesi autorizzati;
- modalità SSL;
- base URL usata per `PdfUrl`;
- data e risultato dell'ultimo test interno;
- data e risultato dell'ultimo collaudo esterno;
- elenco sintetico dei campi esposti.

I valori non ancora ricevuti da IT devono apparire come `DA_FORNIRE_IT`, non come campi vuoti
che potrebbero sembrare dimenticati.

### Gestione sicura della password PostgreSQL

La password del ruolo PostgreSQL read-only non deve essere leggibile dalla pagina.

Regole:

- il backend non restituisce mai password, hash o valore cifrato;
- la risposta contiene soltanto `password_configured: true/false`;
- l'interfaccia mostra `••••••••` quando configurata;
- nessun pulsante `Mostra password`;
- nessuna password nei log applicativi;
- nessuna password nel Markdown;
- nessuna password nel repository o nel pacchetto deploy;
- l'eventuale nuova password viene usata una sola volta per creare o aggiornare il ruolo
  PostgreSQL e poi viene scartata;
- PostgreSQL conserva soltanto il proprio hash della password.

Poiché l'Alpha usa attualmente HTTP e non HTTPS, la nuova password non deve essere inserita
attraverso il browser finché il trasporto non è protetto. Nella prima fase IT la configura
direttamente sul server tramite canale sicuro; la pagina mostra soltanto che è configurata.

Se in futuro l'app viene esposta in HTTPS, si può aggiungere per IT il comando
`Imposta/Reimposta password`, sempre senza possibilità di rileggere quella esistente.

### Dati modificabili e dati informativi

La pagina non deve fingere di poter modificare firewall, VPN o pubblicazione Docker.

Campi gestibili dall'app:

- schema;
- nome vista;
- username del ruolo read-only;
- base URL;
- abilitazione logica della vista;
- eventuale reimpostazione password soltanto in HTTPS;
- test interno della vista e dei permessi.

Campi informativi, applicati realmente da IT:

- host/IP esterno;
- porta esterna;
- IP/rete autorizzati;
- firewall;
- VPN/NAT;
- certificati e modalità SSL;
- esito del collaudo dalla macchina Nemesi.

La scheda deve indicare chiaramente `Configurato da IT` oppure `Da fornire IT`.

### Azioni disponibili

La nuova scheda prevede:

- `Verifica vista`: controlla che schema e vista esistano e siano interrogabili;
- `Verifica permessi read-only`: controlla che il ruolo legga la vista ma non possa leggere o
  modificare le tabelle CERTI;
- `Copia dati connessione`: copia host, porta, database, schema, vista, username e SSL senza
  includere la password;
- `Segna collaudo Nemesi completato`: registra data, utente ed eventuale nota dopo il test
  esterno.

Il pulsante attuale `Test rete` delle connessioni in ingresso non basta per la nuova vista:
esegue il test dal server verso un sistema esterno, mentre qui serve verificare il percorso
opposto, da Nemesi verso CERTI. Il collaudo esterno deve quindi essere confermato dopo una
prova reale dalla macchina Nemesi.

### Backend proposto per la pagina

Non riutilizzare come se fosse una connessione in uscita la tabella `external_connections`,
perché quella struttura descrive client SQL Server usati da CERTI per collegarsi a ESOLVER e
Quarta.

Per la vista serve una configurazione dedicata, limitata ai dati di pubblicazione:

- parametri non segreti;
- stato di configurazione del ruolo;
- stato dei test;
- date e note di collaudo;
- nessuna password recuperabile.

Le API della pagina devono restare protette da ruolo IT admin.

Anche la scheda dell'endpoint HTTP deve leggere dal backend:

- username configurato;
- `password_configured`;
- URL;
- campi esposti;
- stato del test;

senza valori sensibili scritti nel frontend.

### Tracciamento nel Markdown

La sezione `Parametri Alpha verificati e dati IT da completare` resta la checklist ufficiale
fino al collaudo.

Per ogni parametro mancante si registra:

- stato: `VERIFICATO`, `DA_FORNIRE_IT`, `CONFIGURATO`, `COLLAUDATO`;
- responsabile: CERTI, Matteo/IT oppure Nemesi;
- data dell'ultima verifica;
- nota o esito;
- per le password soltanto `configurata sì/no` e nome del secret, mai il valore.

Quando la pagina sarà implementata:

- la pagina rappresenterà la configurazione runtime corrente;
- il Markdown manterrà decisioni, responsabilità, cronologia del collaudo e dati ancora
  mancanti;
- dopo il test Nemesi tutti i parametri devono risultare `COLLAUDATO`.

## Vincolo di rete attuale

Nel deploy Alpha PostgreSQL non pubblica attualmente una porta verso la rete del server.

Per consentire la lettura diretta sono necessari:

1. scelta di IP e porta di ascolto;
2. pubblicazione controllata della porta PostgreSQL;
3. regola firewall limitata agli IP indicati da IT/Nemesi;
4. eventuale configurazione TLS;
5. verifica da una macchina Nemesi autorizzata.

Non pubblicare PostgreSQL genericamente su tutte le reti e non aprire la porta a Internet.

## Piano di implementazione

### Fase 1 - Contratto e configurazione

1. Ricevere i soli parametri IT ancora mancanti.
2. Confermare host esterno, porta esterna, username read-only e IP autorizzati.
3. Confermare il nome definitivo di schema e vista.
4. Confermare la base URL Alpha e quella futura di produzione.

### Fase 2 - Vista canonica

1. Creare lo schema `esolver_export` in modo idempotente.
2. Creare o aggiornare la vista senza operazioni distruttive sulle tabelle.
3. Leggere la versione PDF attiva.
4. Applicare tutti i filtri di validità e identità ESOLVER.
5. Costruire `PdfUrl` dalla configurazione dell'ambiente.
6. Garantire una riga per certificato/riga/quota ESOLVER.

### Fase 3 - Endpoint allineato

1. Fare leggere l'endpoint dalla stessa vista o dallo stesso contratto dati canonico.
2. Aggiungere `PdfVersion` e `ClosedAt` allo schema JSON.
3. Mantenere compatibili tutti i campi già verificati da Walter.
4. Correggere l'elenco interno dei campi export, che oggi non riporta `IdCerti` pur essendo
   presente nella risposta effettiva.

### Fase 4 - Sicurezza e rete

1. Creare o verificare il ruolo read-only.
2. Concedere permessi esclusivamente allo schema e alla vista export.
3. Pubblicare la porta solo sull'interfaccia/rete concordata.
4. Applicare il filtro firewall sugli IP autorizzati.
5. Verificare che l'utente non possa leggere le tabelle applicative.
6. Verificare che l'utente non possa eseguire operazioni di scrittura.

### Fase 5 - Pagina Database

1. Mascherare la password della scheda endpoint HTTP esistente.
2. Eliminare username/password hardcoded dal frontend.
3. Aggiungere la quarta scheda `Vista PostgreSQL`.
4. Mostrare i parametri verificati e i valori `DA_FORNIRE_IT`.
5. Mostrare soltanto lo stato della password.
6. Aggiungere test vista, test permessi e registrazione collaudo.
7. Verificare che la pagina resti accessibile esclusivamente a IT admin.

### Fase 6 - Verifica con Nemesi

1. Eseguire una query semplice sulla vista.
2. Verificare nomi e tipi delle colonne.
3. Verificare il collegamento tramite `IdDocumento` e `IdRigaDoc`.
4. Scaricare un PDF tramite `PdfUrl`.
5. Verificare una seconda versione dello stesso certificato.
6. Confermare che il processo ESOLVER usa `PdfVersion` e `UpdatedAt`.

## Test obbligatori

### Caso semplice

- un OL;
- un DDT;
- una riga ESOLVER;
- un PDF chiuso;
- una riga nella vista.

### Stesso OL su due righe DDT

- stesso OL e CodF3;
- stesso o diverso DDT;
- `IdRigaDoc` differenti;
- due certificati distinti;
- due righe nella vista.

### Stessa riga DDT con due OL

- stesso `IdDocumento`;
- stesso `IdRigaDoc`;
- OL differenti;
- due certificati distinti;
- due righe nella vista collegate alla stessa riga DDT.

### Riga con lotti differenti

- stesso documento e stessa riga;
- `RifLottoAlfanum` o OL differenti;
- nessuna fusione automatica delle quantità.

### Record storico senza ID ESOLVER

- PDF chiuso;
- `IdDocumento` o `IdRigaDoc` mancante;
- record escluso dalla vista.

### Riapertura

- PDF inizialmente presente;
- riapertura del certificato;
- record assente dalla vista;
- versione precedente conservata nello storico CERTI.

### Nuova chiusura

- certificato richiuso;
- stesso `IdCerti`;
- `PdfVersion` incrementato;
- nuovi `ClosedAt` e `UpdatedAt`;
- nuovo PDF scaricabile.

### Sicurezza

- utente read-only può leggere la vista;
- utente read-only non può leggere le tabelle;
- utente read-only non può inserire, modificare o cancellare dati;
- connessione rifiutata da IP non autorizzato.

### Parità endpoint-vista

- stesso numero di record;
- stessi identificativi;
- stessi valori per campi comuni;
- stesso `PdfUrl`;
- stessi criteri di esclusione.

## Controlli sui dati prima del rilascio

Prima di rendere la vista disponibile a Nemesi verificare:

- assenza di duplicati sulla chiave logica;
- assenza di record esposti senza `IdDocumento`;
- assenza di record esposti senza `IdRigaDoc`;
- assenza di record esposti senza versione PDF attiva;
- assenza di URL con base ambiente errata;
- corrispondenza tra file scaricato e certificato selezionato;
- nessuna esposizione di bozze o PDF riaperti.

## Deploy previsto

1. Backup applicazione e database.
2. Applicazione locale della vista.
3. Test automatici backend.
4. Test della query SQL con utente read-only locale.
5. Verifica parità endpoint-vista.
6. Commit e push soltanto dopo esito positivo.
7. Deploy soft Alpha.
8. Creazione/verifica ruolo e rete con i parametri IT.
9. Test da postazione Nemesi.
10. Conferma finale di Walter.

La creazione della vista non deve modificare i dati esistenti e non richiede una vista
materializzata o processi periodici di aggiornamento.

## Rollback

In caso di problema:

1. mantenere disponibile l'endpoint HTTP attuale;
2. revocare temporaneamente il permesso di lettura della vista;
3. chiudere la porta PostgreSQL esposta a Nemesi;
4. ripristinare la definizione precedente della vista o rimuovere solo la vista;
5. non modificare o cancellare i certificati e le versioni PDF;
6. verificare nuovamente endpoint e download PDF.

La vista deve essere considerata un livello di lettura: il rollback non deve interessare i
dati applicativi.

## Criteri di completamento

Il lavoro è concluso quando:

- la vista esiste con il contratto concordato;
- ogni riga è associabile tramite `IdDocumento` e `IdRigaDoc`;
- ogni riga/quota ESOLVER genera un record separato;
- sono esposti soltanto PDF chiusi e validi;
- `PdfVersion` e `ClosedAt` sono disponibili;
- l'endpoint e la vista restituiscono gli stessi dati;
- il PDF è scaricabile;
- l'utente Nemesi è realmente read-only;
- la rete è limitata agli IP autorizzati;
- Walter/Nemesi confermano lettura e collegamento corretti.

## Stato delle informazioni mancanti

L'ambiente Alpha, il server applicativo, la base URL, il motore PostgreSQL, la porta interna e
il nome database sono già noti e verificati.

Per implementare e testare la vista internamente non servono altri dati IT.

Per consentire a Nemesi il collaudo esterno mancano soltanto:

- conferma dell'host/IP PostgreSQL raggiungibile da Nemesi;
- porta PostgreSQL esterna;
- username PostgreSQL read-only;
- IP/rete autorizzati;
- requisiti SSL/firewall;
- nome del secret contenente la password PostgreSQL read-only.

Quando questi dati saranno disponibili, aggiornare la sezione
`Parametri Alpha verificati e dati IT da completare`
senza inserire nel repository la password in chiaro.

## Stato implementazione locale

Aggiornato il 23 luglio 2026.

### Completato

- creata la vista PostgreSQL canonica `esolver_export.certi_certificati_pdf`;
- aggiunti `IdCerti`, `PdfVersion` e `ClosedAt` al contratto completo;
- applicati i filtri per PDF chiuso, versione attiva e identificativi ESOLVER;
- allineato l'endpoint HTTP alla stessa vista PostgreSQL;
- mantenuto un fallback equivalente esclusivamente per i test SQLite;
- creata una configurazione separata per la pubblicazione della vista;
- aggiunta la quarta scheda nella pagina Database, con disposizione 2x2;
- rimossa dalla UI la password HTTP scritta in chiaro;
- password HTTP e PostgreSQL rappresentate soltanto come stato
  `configurata` / `mancante`;
- resi non modificabili in pagina database, schema e nome della vista canonica;
- aggiunti test vista, test permessi minimi e tracciamento verifica esterna;
- impedita l'abilitazione finché dati IT, password lettore e test non sono completi.

### Verifiche locali eseguite

- vista presente realmente su PostgreSQL;
- 15 colonne presenti con nomi e tipi attesi;
- nessuna riga storica incompleta esposta;
- build frontend completata;
- suite backend completa: 195 test superati;

### Mancante, da fornire o fare con IT

| Dato/attività | Stato |
| --- | --- |
| Host/IP PostgreSQL raggiungibile da Nemesi | `DA_FORNIRE_IT` |
| Porta PostgreSQL esterna | `DA_FORNIRE_IT` |
| Username PostgreSQL read-only | `DA_FORNIRE_IT` |
| Password PostgreSQL read-only | `DA_CONFIGURARE_SUL_SERVER` |
| IP/CIDR sorgente Nemesi | `DA_FORNIRE_IT` |
| Modalità SSL richiesta | `DA_FORNIRE_IT` |
| Regole firewall/NAT | `DA_FARE_IT` |
| Test dalla postazione Nemesi | `DA_FARE_CON_NEMESI` |
| Conferma finale Walter | `IN_ATTESA` |

La password del lettore PostgreSQL non deve essere aggiunta a questo file, alla UI,
alle API o al repository. La pagina mostra solo se la password del ruolo PostgreSQL
risulta configurata sul server.
