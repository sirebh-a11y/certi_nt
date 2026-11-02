# DDT multipagina e gruppi — estensione fornitori 02/11/2026

## Perimetro e autorizzazione

Audit e implementazione locali autorizzati con «audit poi applica piano e verifica
regressioni». Nessun commit, push o deploy implicito. Alpha, documenti originali
e database applicativi non sono usati per scritture di collaudo. Nessuna nuova
chiamata AI a pagamento: le prove di questa estensione sono offline e PostgreSQL
temporaneo; non costituiscono una prova AI reale sui nuovi prompt degli altri
fornitori. I test AI Metalba già autorizzati sono descritti nel verbale distinto.

## Audit iniziale: errori riprodotti, non bonifiche Alpha

Nove prove controllate hanno riprodotto:

- Leichtmetall: dettagli500+400, testata1000; il precedente ripiego attribuiva100
  alla colata più pesante. Altra prova: due letture100+200 dello stesso batch,
  la seconda sostituiva la prima lasciando200 anziché300.
- Neuman: lettura locale HU corretta a300, ma output AI diviso100/200 non veniva
  riconciliato nel percorso automatico.
- Grupa Kety: la ripetizione della stessa sottoriga poteva raddoppiare il peso;
  diametri/ordini discordanti della stessa coppia root+Heat erano sommati prendendo
  il primo materiale/ordine.
- Pagine: sette percorsi potevano proseguire con due pagine indicizzate su tre
  previste. Leichtmetall e il nuovo Metalba avevano già una protezione.
- Salvataggio interrotto Grupa Kety: tre gruppi letti, due righe persistite;
  ripartenza con due sole righe, senza completare la terza.
- Otto lettori DDT inviavano la stessa pagina mascherata due volte con ruoli
  diversi. Non è dimostrazione che l'AI sbagli sempre, ma ripetizione inutile.

Queste condizioni simulate non dimostrano che tutti i difetti siano già avvenuti
su Alpha. Negli snapshot read-only già disponibili, Bozen1383 presenta due gruppi
di colata distinti e Impol17394-11 due posizioni distinte: non sono duplicati da
eliminare. Per Bozen/Impol/AWW/Arconic/Zalco le unità di raggruppamento specifiche
restano invariate; non si applica indiscriminatamente il modello Metalba.

## Implementazione

### Protezioni comuni

- Tutte le pagine numerate attese e relative immagini sono necessarie prima
  dell'AI. I controlli tipo documento Leichtmetall restano distinti.
- Ogni immagine integrale mascherata DDT viene inviata una sola volta; restano
  mascheramento, etichette canoniche, ordine delle pagine e regole Arconic di
  recupero identità. Nessun taglio delle continuazioni.
- Il lock per documento comprende controllo righe esistenti, lettura e creazione
  di tutti i gruppi, anche con lavoratori PostgreSQL simultanei.
- Per nuovi DDT automatici si conserva prima la lettura verificata in
  `DocumentEvidence`; per i non-Metalba tipo `supplier_ddt_groups_v1`, più
  `supplier_ddt_group_complete_v1` per distinguere una riga finita da una riga
  creata ma non ancora applicata. Metalba mantiene il formato precedente.
- Dopo un'interruzione si riprende dalle evidenze persistite, senza nuova AI
  quando la lettura è stata salvata. Riga parziale recuperabile solo in modo
  univoco; manuali e righe confermate/validate non vengono sovrascritti.
- Anche i codici articolo/profilo/prodotto interni partecipano alla distinzione
  dei gruppi nel solo percorso autonomo: due prodotti realmente diversi con
  stessi peso/colata/diametro non sono collassati. Non cambiano punteggi o soglie
  di match/rematch.
- Nessuna espansione automatica dello storico privo delle nuove evidenze. Non
  si ricostruisce una lettura AI usando dati Incoming manuali.

### Tre interventi specifici

- **Leichtmetall:** tolta l'attribuzione del residuo sia dal lettore locale sia
  dal percorso AI. Dettagli completi e coerenti possono riparare un gruppo AI
  spezzato; OCR parziale non viene usato per inventare il peso mancante. Rimangono
  validi totali AI completi quando il solo OCR testuale è incompleto. Il percorso
  preliminare di verifica tipo salva/riusa la lettura DDT, senza ripagarla a ogni
  ripartenza; la correzione del tipo resta sottoposta alle protezioni precedenti.
- **Neuman:** somma applicativa dei componenti HU per gruppo coerente
  prodotto+Lot+lega+diametro+ordine. Identità di collo/posizione, non peso uguale,
  determina una ripetizione. Prodotti diversi dello stesso Lot restano separati.
- **Grupa Kety:** somma applicativa dei componenti; doppia lettura della stessa
  sottoriga non raddoppia il peso, sottolotti distinti di uguale peso restano.
  Non vengono sommati materiali/ordini discordanti della stessa coppia lotto+Heat.

Solo i prompt DDT di questi tre fornitori richiedono `pages_read`, totale netto
stampato se presente e `weight_components` con identificativo o posizione fisica
di ciascun contributo. Un totale stampato può essere un componente unico se non
esiste il dettaglio: mai sommarlo di nuovo ai colli. Conti con Decimal nell'app;
non si inventano residui, certificati o riferimenti mancanti. Un errore semantico
consente una sola rilettura mirata; se persiste, viene fermato quel DDT, non forzato
il match. Gli errori di questo controllo non sono riavviati dal retry generico.
Restano i retry di trasporto preesistenti e separati.

La consultazione di [OpenAI Docs sulle immagini](https://developers.openai.com/api/docs/guides/images-vision)
ha guidato il mantenimento degli input multipagina e la separazione tra
trascrizione visiva e verifiche deterministiche. Nessuna migrazione modello/SDK
o modifica alla configurazione delle chiamate.

## Prove e limiti

Test dedicati in `backend/tests/test_ddt_packing_safety.py`: pagine assenti,
continuazioni, duplicazione ruoli nella richiesta reale simulata di otto lettori,
copertura pagine dichiarata, totale stampato, collo attribuito a due materiali,
pesi uguali e colli diversi, ripetizioni/conflitti, casi500+400/1000 e100+200/300,
caso Leichtmetall80008535 (5014+12211), materiali diversi, conservazione legacy,
manuali, interruzione prima della prima riga o durante l'applicazione, ripartenza,
identità documento cambiata, preflight Leichtmetall e lavoratori concorrenti.

Esito conclusivo: **839 test superati, 165 opt-in saltati**, 1.004 totali della
suite generale, zero errori/fallimenti. Eseguiti separatamente anche **27 test
PostgreSQL** (10 di questa estensione e17 Metalba), tutti superati: 866 casi
eseguiti complessivamente tra i due insiemi, senza contare due volte i saltati.
I messaggi timeout/AI/cache e rifiuto dei comandi di recupero nei log sono
scenari simulati attesi. Nessuna regressione rilevata nei percorsi coperti;
non è una garanzia su qualsiasi documento futuro.

39 test dedicati della nuova estensione: 20 controlli puri/richieste simulate,
9 integrazioni SQLite e10 PostgreSQL (gli ultimi9 ripetono gli scenari SQLite
su PostgreSQL, uno verifica i due lavoratori simultanei). I test Arconic e
workflow tipo Leichtmetall conservano le stesse asserzioni comportamentali,
con fixture aggiornate ai metadati pagina ora obbligatori e ai veri tipi di
candidate persistibili. Backend locale verificato con health200/statusok,
senza riavvii manuali e senza modifiche frontend.

Le prove PostgreSQL
sono limitate all'URL opt-in `127.0.0.1:55439/certi_ai_reuse`, schemi UUID, container
`certi-ddt-safety-qa-20261102` etichettato `certi.qa=ddt-safety-20261102`, dati in RAM,
senza volumi persistenti. ID verificato
`cb54e2d8eaa278d3f0f0958fbf10f7a3e5fd60292d2a907f9a62114e5bafaf18`.
Container rimosso dopo i test e le verifiche di identità: eliminati solo i dati
usa-e-getta, ricreabili dalle fixture. I quattro container applicativi sono
rimasti attivi e intatti.

## Futuro deploy e rollback

Vedere il runbook Alpha: distribuzione di tutti i moduli importati insieme,
backup e clone isolato, nessun DDL/backfill/reset o rilettura dello storico.
Le nuove evidenze usano tabelle e colonne esistenti. Non copiare DB/fixture QA.
Rollback conserva evidenze e documenti; prima di arretrare il codice non lasciare
DDT parziali in lavorazione: il codice precedente non sa completarli con le nuove
protezioni. Non cancellare evidenze per rendere possibile il rollback.
