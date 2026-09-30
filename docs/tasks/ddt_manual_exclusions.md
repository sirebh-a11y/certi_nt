# Esclusioni manuali DDT da certificare

30/09/2026 — implementazione autorizzata e verificata in locale. Deploy Alpha separato.

## Uso della pagina

- Solo ruolo `admin` nel reparto **Qualità** può escludere o ripristinare una
  quota. Admin IT e manager Qualità possono consultare lo storico, ma non decidere.
- Nelle Azioni della singola quota: **Non richiede certificazione**. Il dialogo
  mostra DDT, OL, Cod. F3, quantità, documento, riga e lotto, e richiede il motivo.
- La quota esce dagli Attivi e dal badge sidebar e compare in **Vista → Esclusi**.
  I contatori separano Attivi, Completati ed Esclusi. Non viene creata una
  certificazione e non viene dichiarato pronto un PDF.
- Nella vista Esclusi il pulsante **Ripristina** richiede il motivo. La quota torna
  negli Attivi con la scadenza originale, se il suo PDF finale non è già valido.
- Motivo, autore e data della decisione più recente sono nella cella Stato.
  **Storico decisioni** apre tutte le decisioni, comprese le riaperture automatiche.
- Nessuna nuova colonna. Le righe escluse non mostrano urgenza di scadenza.
  La vista Tutti permette di trovare anche quote escluse poi completate con PDF.

## Sincronizzazione e protezioni

L'esclusione vale per l'ID della singola quota, non per tutti gli OL/DDT con lo
stesso nome. Una nuova lettura identica, la scomparsa dalla finestra eSolver o
il cambio del flag eSolver relativo alla presenza del certificato conservano
la decisione.

Una modifica a documento/riga/lotto, OL, Cod. F3, DDT/data, cliente, ordine,
conferma, quantità o segnalazione di identità sorgente richiede nuova verifica:
la sincronizzazione registra una riapertura **Sistema** e la quota torna attiva
con **Verifica richiesta**. Se in seguito tornano i vecchi dati, l'esclusione non
si riattiva da sola. Admin Qualità può confermare una nuova esclusione oppure
premere Ripristina per tornare al normale flusso.

L'aggancio di un OL prima mancante invalida la vecchia decisione. Se l'identità
diventa ambigua, la decisione non viene trasferita automaticamente a un'altra quota.

Un PDF finale valido continua ad avere precedenza: la quota è Completata, anche
se prima era esclusa. Un ripristino non riapre artificialmente un PDF valido.
Lo stato Incoming effettivo viene conservato separatamente: un respinto rimane
riconoscibile come Qualità respinta anche nella vista Esclusi.

Finestre obsolete e doppi invii sono rifiutati con messaggio di aggiornamento.
Il server controlla sia l'ultima decisione sia i dati sorgente visualizzati.
Le operazioni condividono il lock PostgreSQL di sincronizzazione/recupero;
un errore annulla decisione e scritture della relativa transazione.

## Persistenza e rilascio

Nuova tabella `quarta_taglio_ddt_decisions`: eventi append-only con quota,
azione, motivo, utente, nome al momento della decisione, data e dati sorgente.
Nessuna modifica alle colonne delle tabelle esistenti. Il normale bootstrap
crea la tabella mancante. Nuove API per scrivere la decisione e leggere lo storico.
Le letture della coda non scrivono eventi e non chiamano eSolver.

Il recupero Alpha include ora tre tabelle DDT, compresa quella delle decisioni.
Il report è versione 2 e considera anche decisioni e codice di esclusione:
rifare la preview al momento del recupero. Creazione e rollback della nuova
tabella verificati su PostgreSQL isolato. Seguire il Markdown deploy soft.

## Verifiche completate

- 120 test backend passati, zero saltati: coda, decisioni, snapshot, storico e
  recupero; PostgreSQL temporaneo senza rete esterna o volumi applicativi.
  Aggiunta una prova specifica su qualità respinta e Word già presente:
  rieseguiti i 12 test decisioni, tutti passati (121 casi distinti complessivi).
- 8 test frontend su scadenza e avvisi di sincronizzazione passati.
- Build frontend riuscita; avvisi preesistenti su Browserslist e bundle.
- Playwright sulla UI reale con API simulate: annullamento, motivo obbligatorio,
  esclusione di una sola quota, filtro Esclusi, sidebar/conteggi, ripristino,
  storico, risposta 409 e assenza dei pulsanti per admin IT/manager Qualità.
- Screenshot esaminati a 1920 e 1440 px: 13 colonne, scorrimento tabella interno.
  Script temporaneo: `tmp_eval/packages_qa/ddt_decisions_check.mjs`.
- Nessuna prova mutante sui dati applicativi reali, nessun accesso Alpha.

Il backend locale ha ricaricato automaticamente i sorgenti: verificati in sola
lettura la nuova rotta OpenAPI e la tabella delle decisioni creata dal bootstrap.
Il frontend abituale è stato riavviato per riallineare il codice servito su 5173.
Il collaudo visivo ha usato il frontend temporaneo 5174 e i test backend un DB isolato.
