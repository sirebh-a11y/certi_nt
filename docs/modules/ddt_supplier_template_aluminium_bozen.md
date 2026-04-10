# DDT Supplier Template Analysis - Aluminium Bozen

## Scopo

Analisi del template DDT osservato per `Aluminium Bozen S.r.l.` sui PDF reali presenti in:

```plaintext
esempi_locali/4-ddt/Aluminium Bz
```

Questo file serve a fissare:

* struttura reale del template
* campi originali usabili nel runtime futuro
* regole di ricerca e match da validare prima del codice

---

## Vincolo Guida Del Progetto

La lettura documentale corretta, orientata il piu' possibile al **100% di precisione**, e' la parte piu' vitale dell'app.

Per questo template:

* il documento e' principalmente scansione, quindi `pdf_text` non basta
* la lettura deve combinare `ocr`, `vision`, lettura tabellare e contesto spaziale
* le annotazioni manuali osservate nei PDF storici NON devono entrare nel runtime futuro

---

## 1. Identificazione

* `fornitore_master`: `Aluminium Bozen S.r.l.`
* `alias_osservati`: `Aluminium Bz`, `aluminium bozen`
* `template_id`: `aluminium_bozen_delivery_note_packing_list_v1`
* `stato_analisi`: `bozza`

---

## 2. Dataset Letto

* `cartella`: `esempi_locali/4-ddt/Aluminium Bz`
* `pdf_letti`: `101.pdf`, `150.pdf`, `176.pdf`, `261.pdf`, `320.pdf`, `419.pdf`
* `pagine_totali_lette`: `14`
* `documenti_rappresentativi`: `101.pdf`, `176.pdf`, `261.pdf`, `419.pdf`

Esempi principali:

* `101.pdf`: 2 pagine, delivery note + packing list, due gruppi materiale
* `176.pdf`: 2 pagine, delivery note + packing list, un solo gruppo materiale
* `261.pdf`: 4 pagine, delivery note, pagina comunicazione, packing list multipagina
* `419.pdf`: 2 pagine, delivery note + packing list, piu' gruppi materiale

---

## 3. Regola Chiave Del Template

Descrizione breve del template:

* pagina 1 = `Delivery note / Documento di trasporto`
* pagina 2 o pagine successive = `PACKING LIST`
* il template si riconosce da:
  * header `Aluminium Bozen S.r.l.`
  * riga `Delivery note / Documento di trasporto`
  * righe materiale con `CAST Nr.` e `Alloy and physical status`
  * codice articolo interno spesso tra parentesi nella descrizione riga, tipo `14BT185-B21`
  * packing list con `Rif. ordine AB ODV`, `Cert. N°`, `COD. COLATA`

Cosa lo distingue:

* il DDT principale contiene gia' molte informazioni di riga
* il packing list aggiunge dettagli forti per certificato, colli, peso netto e `COD. COLATA`
* il packing list puo' occupare piu' pagine

---

## 4. Guardrail Runtime

### 4.1 Campi Usabili Nel Runtime Futuro

Qui vanno solo i campi del documento originale del fornitore usabili davvero nel runtime:

* `Num.` del DDT
* data del DDT
* header fornitore
* `Rif. ns. Odv N.`
* `Vs. Odv`
* codice cliente/materiale nella riga materiale
* articolo interno tra parentesi nella descrizione riga materiale
* descrizione materiale e dimensione
* `CAST Nr.`
* `Alloy and physical status`
* peso della riga materiale
* `Rif. ordine AB ODV`
* `Cert. N°` nel packing list
* `COD. COLATA` nel packing list
* `P.NETTO KG` e `TOTALI` nel packing list

### 4.2 Contesto Storico Da NON Usare Nel Runtime

* `campo/annotazione`: `cdq` scritto a mano in blu
  * `utile per capire il processo storico`: `si`
  * `usabile nel runtime futuro`: `no`
  * `nota`: compare vicino a righe peso/colata ma non va assunto per i DDT futuri caricati in app
* `campo/annotazione`: `colata` o codice certificato scritto a mano in blu
  * `utile per capire il processo storico`: `si`
  * `usabile nel runtime futuro`: `no`
  * `nota`: puo' aiutare a capire i match storici ma non deve guidare parser o match runtime
* `campo/annotazione`: note operative manuali di incoming
  * `utile per capire il processo storico`: `si`
  * `usabile nel runtime futuro`: `no`
  * `nota`: contesto umano, non dato fornitore

---

## 5. Struttura Documento

### 5.1 Pagine E Blocchi

* pagina 1:
  * header fornitore e indirizzi
  * blocco cliente/destinazione
  * riga `Delivery note / Documento di trasporto`
  * piu' righe materiale, ciascuna con descrizione, dimensione, articolo interno tra parentesi, `CAST Nr.`, lega/stato e peso riga
  * footer con truck / package unit / gross / net / firme
* pagina 2:
  * normalmente `PACKING LIST`
  * gruppo per `Rif. ordine AB ODV`
  * righe colli con `P.NETTO KG` e `COD. COLATA`
* pagine successive:
  * possibile continuazione packing list
  * possibile pagina comunicazione/legenda rumorosa, come in `261.pdf`

### 5.2 Dove Cercare Prima

Ordine reale di lettura:

1. pagina 1, riga materiale stampata
2. packing list, gruppo coerente con la riga materiale
3. footer/totali del packing list per controlli e validazioni

### 5.3 Dove NON Cercare O Cosa Non Confondere

* paragrafi multilingua di comunicazione e protezione materiale
* firme, date/ora di pesatura e footer logistici
* annotazioni manuali in blu
* `Inspection certificate EN 10204 3.1`: indica il tipo di certificato, non il numero certificato

---

## 6. Regola Di Riga Acquisition

* `unita materiale reale`: di norma la riga materiale stampata nel DDT
* `criterio di aggregazione`: `per riga`, con uso del packing list come dettaglio di supporto
* `uso del peso`: `diretto` dalla riga materiale; packing list usato per validare o ricostruire casi deboli
* `uso del packing list`: `si`
* `regola pratica`: leggere prima la riga materiale di pagina 1; usare il packing list per trovare il gruppo coerente e recuperare `Cert. N°`, `COD. COLATA`, colli e pesi netti di conferma

Se il peso o la riga vanno ricostruiti:

* il dettaglio sta nel gruppo corretto del packing list
* vanno considerati solo i colli del gruppo coerente per `Rif. ordine AB ODV`, articolo/codice cliente, lega-stato e dimensione
* se la coerenza del gruppo non e' forte, il caso va lasciato all'utente

---

## 7. Campi Da Ricercare

### 7.1 Campo: `numero_ddt`

* `obbligatorio nel runtime`: `si`
* `usato per match con certificato`: `no`
* `pagina/blocco principale`: pagina 1, header documento
* `posizione precisa osservata`: riga `Delivery note / Documento di trasporto ... Num. ... Date ...`
* `relazione spaziale con altri campi`: sulla stessa riga della data
* `ancore testuali`: `Delivery note`, `Documento di trasporto`, `Num.`, `Date`
* `vicinanza ad altri campi`: data documento
* `varianti di scrittura`: `Num.` seguito da numero semplice
* `tipo valore`: `documentale puro`
* `unita implicita`: `nessuna`
* `strumento di lettura migliore`: `ocr / vision`
* `contesto minimo necessario`: `riga + header`
* `materiale utile per ML futuro`: `crop campo`, `crop riga`, `anchor text`
* `materiale fuorviante da evitare`: footer e dati di pesatura
* `fallback di ricerca`: visione dell'intera header line
* `falsi positivi noti`: numeri truck, page, package units
* `nota runtime`: forte se letto nella riga header documento

### 7.2 Campo: `data_documento`

* `obbligatorio nel runtime`: `si`
* `usato per match con certificato`: `debole`
* `pagina/blocco principale`: pagina 1, header documento
* `posizione precisa osservata`: stessa riga del `Num.`
* `relazione spaziale con altri campi`: immediatamente vicino al numero DDT
* `ancore testuali`: `Date`
* `vicinanza ad altri campi`: `Num.`
* `varianti di scrittura`: formato giorno/mese/anno
* `tipo valore`: `documentale puro`
* `unita implicita`: `nessuna`
* `strumento di lettura migliore`: `ocr / vision`
* `contesto minimo necessario`: `riga + header`
* `materiale utile per ML futuro`: `crop riga`, `anchor text`
* `materiale fuorviante da evitare`: date/ora di pesatura e packing list
* `fallback di ricerca`: visione della riga header completa
* `falsi positivi noti`: date ordini cliente, date footer
* `nota runtime`: non usare altre date del documento come sostituto

### 7.3 Campo: `fornitore`

* `obbligatorio nel runtime`: `si`
* `usato per match con certificato`: `forte`
* `pagina/blocco principale`: header pagina 1
* `posizione precisa osservata`: in alto, vicino al logo
* `relazione spaziale con altri campi`: sopra indirizzo e contatti
* `ancore testuali`: `Aluminium Bozen S.r.l.`
* `vicinanza ad altri campi`: contatti e headquarters
* `varianti di scrittura`: `Aluminium Bozen S.r.l.`, `aluminium bozen`
* `tipo valore`: `documentale puro`
* `unita implicita`: `nessuna`
* `strumento di lettura migliore`: `ocr / vision`
* `contesto minimo necessario`: `blocco`
* `materiale utile per ML futuro`: `crop header`, `pagina`, `anchor text`
* `materiale fuorviante da evitare`: destinazione cliente
* `fallback di ricerca`: logo + ragione sociale
* `falsi positivi noti`: nome cliente `FORGIALLUMINIO 3 SRL`
* `nota runtime`: mappare sempre al master fornitore

### 7.4 Campo: `ordine`

* `obbligatorio nel runtime`: `si`
* `usato per match con certificato`: `medio`
* `pagina/blocco principale`: pagina 1 e packing list
* `posizione precisa osservata`: `Rif. ns. Odv N.` su pagina 1, `Rif. ordine AB ODV` nel packing list
* `relazione spaziale con altri campi`: sopra la riga materiale o sopra il gruppo packing list
* `ancore testuali`: `Rif. ns. Odv N.`, `Rif. ordine AB ODV`
* `vicinanza ad altri campi`: `Vs. Odv`, `ODP`, `Cert. N°`
* `varianti di scrittura`: `2512006.4`, `2025.2512006.4`, `2610183.1`, `2026.2610183.1`
* `tipo valore`: `documentale puro`
* `unita implicita`: `nessuna`
* `strumento di lettura migliore`: `ocr / regex`
* `contesto minimo necessario`: `riga + header` o `blocco gruppo`
* `materiale utile per ML futuro`: `crop riga`, `crop gruppo`, `anchor text`
* `materiale fuorviante da evitare`: `Vs. Odv` cliente
* `fallback di ricerca`: packing list
* `falsi positivi noti`: `ODP`, ordine cliente
* `nota runtime`: normalizzare senza perdere punteggiatura utile

### 7.4 bis Campo: `ordine_cliente`

* `obbligatorio nel runtime`: `si`
* `usato per match con certificato`: `medio`
* `pagina/blocco principale`: pagina 1, subito sotto `Rif. ns. Odv N.`
* `posizione precisa osservata`: riga `Vs. Odv ... - data`
* `relazione spaziale con altri campi`: attaccata alla riga ordine AB della stessa voce materiale
* `ancore testuali`: `Vs. Odv`
* `vicinanza ad altri campi`: `Rif. ns. Odv N.`
* `varianti di scrittura`: nel DDT appare come `1 - 2026-01-07`, nel certificato come `2026-01-07 1`
* `tipo valore`: `documentale puro`
* `unita implicita`: `nessuna`
* `strumento di lettura migliore`: `ocr / regex`
* `contesto minimo necessario`: `riga + header`
* `materiale utile per ML futuro`: `crop riga`, `anchor text`
* `materiale fuorviante da evitare`: altri numeri ordine cliente nel packing list non collegati alla riga corrente
* `fallback di ricerca`: packing list `Rif. ordine cliente`
* `falsi positivi noti`: confusione con ordine AB / ODP
* `nota runtime`: va riconosciuta la stessa informazione anche quando il fornitore la rimodula invertendo `numero` e `data`

### 7.5 Campo: `lega`

* `obbligatorio nel runtime`: `si`
* `usato per match con certificato`: `forte`
* `pagina/blocco principale`: pagina 1 riga materiale, packing list gruppo
* `posizione precisa osservata`: dopo `CAST Nr.` su pagina 1; riga `Lega stato fisico` nel packing list
* `relazione spaziale con altri campi`: vicina a colata e descrizione articolo
* `ancore testuali`: `Alloy and physical status`, `Lega stato fisico`
* `vicinanza ad altri campi`: `CAST Nr.`, descrizione articolo, cod. cliente
* `varianti di scrittura`: `6082/F`, `6082HF/F`, `2014/F`, `2014 G/F`, `7075 F`
* `tipo valore`: `documentale puro`
* `unita implicita`: `nessuna`
* `strumento di lettura migliore`: `ocr / tabellare`
* `contesto minimo necessario`: `riga` o `gruppo`
* `materiale utile per ML futuro`: `crop riga`, `crop gruppo`, `anchor text`
* `materiale fuorviante da evitare`: righe comunicazione
* `fallback di ricerca`: packing list gruppo
* `falsi positivi noti`: leggere solo la lega senza lo stato fisico
* `nota runtime`: mantenere coppia lega + stato fisico

### 7.6 Campo: `dimensione`

* `obbligatorio nel runtime`: `si`
* `usato per match con certificato`: `forte`
* `pagina/blocco principale`: descrizione riga materiale o packing list gruppo
* `posizione precisa osservata`: dentro `BARRA TONDA 75`, `BARRA TONDA 98`, ecc.
* `relazione spaziale con altri campi`: subito dopo descrizione articolo
* `ancore testuali`: `BARRA TONDA`
* `vicinanza ad altri campi`: codice articolo, lega
* `varianti di scrittura`: numero intero, a volte con zero iniziale OCR o spazi
* `tipo valore`: `numerico standardizzato`
* `unita implicita`: `mm`
* `strumento di lettura migliore`: `ocr / tabellare`
* `contesto minimo necessario`: `riga`
* `materiale utile per ML futuro`: `crop riga`, `crop gruppo`
* `materiale fuorviante da evitare`: lunghezza barra `4850`, `5390`, `5500`
* `fallback di ricerca`: packing list `Des. art. cliente`
* `falsi positivi noti`: confusione con lunghezza in mm
* `nota runtime`: distinguere dimensione nominale da lunghezza del collo

### 7.7 Campo: `peso`

* `obbligatorio nel runtime`: `si`
* `usato per match con certificato`: `medio`
* `pagina/blocco principale`: pagina 1 riga materiale
* `posizione precisa osservata`: ultima parte della riga materiale stampata
* `relazione spaziale con altri campi`: a destra di lunghezza e pezzi
* `ancore testuali`: nessuna forte; va letto per posizione nella riga
* `vicinanza ad altri campi`: lunghezza, pezzi
* `varianti di scrittura`: valore con virgola europea; OCR puo' perdere la virgola
* `tipo valore`: `numerico standardizzato`
* `unita implicita`: `kg`
* `strumento di lettura migliore`: `ocr / tabellare`
* `contesto minimo necessario`: `riga`
* `materiale utile per ML futuro`: `crop riga`, `crop tabella`, `bbox`
* `materiale fuorviante da evitare`: `Gross`, `Net`, `P.NETTO KG` di altre sezioni, totale packing list
* `fallback di ricerca`: packing list del gruppo coerente
* `falsi positivi noti`: peso totale documento, pesi lordi, singoli colli
* `nota runtime`: usare il peso riga pagina 1 come primario; packing list per validare o ricostruire casi deboli

### 7.8 Campo: `codice_materiale / codice_cliente`

* `obbligatorio nel runtime`: `si`
* `usato per match con certificato`: `forte`
* `pagina/blocco principale`: riga materiale pagina 1, gruppo packing list
* `posizione precisa osservata`: all'inizio riga materiale; in packing list come `Cod. art. cliente`
* `relazione spaziale con altri campi`: vicino alla descrizione materiale
* `ancore testuali`: `Cod. art. cliente`
* `vicinanza ad altri campi`: descrizione, articolo, lega
* `varianti di scrittura`: `A6H075040`, `62130020`, `A210520`, OCR puo' perdere `A`, confondere `0/O`, aggiungere `4` iniziale
* `tipo valore`: `codice`
* `unita implicita`: `nessuna`
* `strumento di lettura migliore`: `ocr / regex / tabellare`
* `contesto minimo necessario`: `riga`
* `materiale utile per ML futuro`: `crop riga`, `crop gruppo`, `anchor text`
* `materiale fuorviante da evitare`: `Articolo` interno `14BT...`
* `fallback di ricerca`: packing list
* `falsi positivi noti`: articolo `14BT...` e cod. cliente sono due codici diversi
* `nota runtime`: tenere distinti `Articolo` interno e `Cod. art. cliente`

### 7.9 Campo: `colata`

* `obbligatorio nel runtime`: `si`
* `usato per match con certificato`: `forte`
* `pagina/blocco principale`: pagina 1 `CAST Nr.`, packing list `COD. COLATA`
* `posizione precisa osservata`: sotto la riga materiale o nell'ultima colonna packing list
* `relazione spaziale con altri campi`: vicino a lega e gruppo articolo
* `ancore testuali`: `CAST Nr.`, `COD. COLATA`
* `vicinanza ad altri campi`: lega, articolo, `Cert. N°` nel packing list
* `varianti di scrittura`: alfanumerico tipo `525238C1`, `925314A4`, `44346`, `44422`
* `tipo valore`: `documentale puro`
* `unita implicita`: `nessuna`
* `strumento di lettura migliore`: `ocr / regex / tabellare`
* `contesto minimo necessario`: `riga` o `gruppo`
* `materiale utile per ML futuro`: `crop riga`, `crop gruppo`, `bbox`, `anchor text`
* `materiale fuorviante da evitare`: codici scritti a mano vicino alle righe
* `fallback di ricerca`: packing list gruppo coerente
* `falsi positivi noti`: numeri articolo, cert. number, ordine
* `nota runtime`: usare solo il valore stampato del fornitore

### 7.9 bis Campo: `articolo_interno`

* `obbligatorio nel runtime`: `si`
* `usato per match con certificato`: `forte`
* `pagina/blocco principale`: pagina 1 e packing list
* `posizione precisa osservata`: spesso tra parentesi nella riga materiale pagina 1, e come `Articolo` nel packing list/certificato
* `relazione spaziale con altri campi`: vicino a descrizione `BARRA TONDA`, dimensione e codice cliente
* `ancore testuali`: `Articolo`
* `vicinanza ad altri campi`: codice cliente/materiale, lega, descrizione
* `varianti di scrittura`: `14BT185-B21`, `14BT147-B03`, `14BT182-B04`
* `tipo valore`: `codice`
* `unita implicita`: `nessuna`
* `strumento di lettura migliore`: `ocr / regex / tabellare`
* `contesto minimo necessario`: `riga`
* `materiale utile per ML futuro`: `crop riga`, `crop gruppo`, `anchor text`
* `materiale fuorviante da evitare`: codice cliente/materiale, che e' un codice diverso
* `fallback di ricerca`: packing list e certificato
* `falsi positivi noti`: OCR che perde `T` o aggiunge cifre
* `nota runtime`: campo molto forte per il match con il certificato dello stesso fornitore

### 7.10 Campo: `numero certificato riportato sul DDT`

* `obbligatorio nel runtime`: `no`
* `usato per match con certificato`: `forte`
* `pagina/blocco principale`: packing list
* `posizione precisa osservata`: riga `Rif. ordine AB ODV ... Cert. N° ...`
* `relazione spaziale con altri campi`: nello stesso gruppo di articolo, lega e `COD. COLATA`
* `ancore testuali`: `Cert. N°`
* `vicinanza ad altri campi`: `Rif. ordine AB ODV`, `ODP`, articolo, `COD. COLATA`
* `varianti di scrittura`: numero semplice a 5-6 cifre
* `tipo valore`: `documentale puro`
* `unita implicita`: `nessuna`
* `strumento di lettura migliore`: `ocr / regex`
* `contesto minimo necessario`: `blocco gruppo`
* `materiale utile per ML futuro`: `crop gruppo`, `anchor text`, `bbox`
* `materiale fuorviante da evitare`: `Inspection certificate EN 10204 3.1` su pagina 1
* `fallback di ricerca`: nessuno forte se manca il packing list
* `falsi positivi noti`: `EN 10204 3.1` non e' il numero certificato
* `nota runtime`: se manca il packing list, lasciare vuoto

---

## 8. Match DDT -> Certificato

### 8.1 Campi Forti Osservati

* fornitore
* numero certificato nel packing list
* codice cliente/materiale
* articolo interno `14BT...`
* lega + stato fisico
* dimensione
* colata stampata

### 8.2 Campi Medi O Deboli

* ordine AB ODV
* ordine cliente, tenendo conto della rimodulazione `1 - 2026-01-07` -> `2026-01-07 1`
* peso

### 8.3 Regola Pratica Di Match

1. trovare il gruppo packing list coerente con la riga materiale
2. usare prima `Cert. N°`, articolo interno `14BT...`, codice cliente/materiale, lega-stato e dimensione
3. usare colata, ordine AB, ordine cliente rimodulato e peso come conferma/coerenza

### 8.4 Eccezioni

* `peso diretto o da sommare`: di base diretto dalla riga materiale; usare packing list per ricostruzione solo se il caso e' debole
* `batch/cast/charge obbligatorio o no`: `CAST/COD. COLATA` molto forte
* `ordine forte/medio/debole`: medio
* `mismatch apparenti noti`: articolo interno e cod. cliente non vanno confusi; `EN 10204 3.1` non e' numero certificato

---

## 9. Similarità E Varianti Codici

* `nome codice`: `codice cliente/materiale`
  * `formato tipico`: alfanumerico tipo `A6H075040`, `A210520`, `62130020`
  * `varianti osservate`: perdita di `A`, `0/O`, cifre attaccate
  * `spazi / slash / trattini`: normalmente assenti
  * `trasposizioni frequenti`: OCR su `0/O`, `1/I`, `A/4`
  * `similarità ammessa`: `media`
  * `match esatto obbligatorio`: `no`, dopo normalizzazione OCR
* `nome codice`: `articolo interno`
  * `formato tipico`: `14BT147-B03`
  * `varianti osservate`: `14B7291-B07`, `14BT185-B21`, OCR parziale
  * `spazi / slash / trattini`: trattino centrale stabile
  * `trasposizioni frequenti`: `7/T`, `1/I`
  * `similarità ammessa`: `media`
  * `match esatto obbligatorio`: `no`, dopo normalizzazione
* `nome codice`: `ordine AB ODV`
  * `formato tipico`: `2610183.1` o `2026.2610183.1`
  * `varianti osservate`: con o senza anno prefisso
  * `spazi / slash / trattini`: punti stabili
  * `trasposizioni frequenti`: OCR sui punti
  * `similarità ammessa`: `bassa`
  * `match esatto obbligatorio`: `si`, dopo normalizzazione del prefisso anno
* `nome codice`: `ordine cliente`
  * `formato tipico`: DDT `1 - 2026-01-07`, certificato `2026-01-07 1`
  * `varianti osservate`: inversione tra numero progressivo e data
  * `spazi / slash / trattini`: trattino e spazi possono cambiare
  * `trasposizioni frequenti`: ordine dei token invertito
  * `similarità ammessa`: `media`
  * `match esatto obbligatorio`: `no`, dopo normalizzazione dei token
* `nome codice`: `colata`
  * `formato tipico`: `525238C1`, `925314A4`, `44346`
  * `varianti osservate`: alfanumerico o numerico puro
  * `spazi / slash / trattini`: assenti
  * `trasposizioni frequenti`: `A/4`, `1/I`
  * `similarità ammessa`: `bassa`
  * `match esatto obbligatorio`: `si`
* `nome codice`: `numero certificato`
  * `formato tipico`: `150763`, `151238`, `151868`
  * `varianti osservate`: 5-6 cifre
  * `spazi / slash / trattini`: assenti
  * `trasposizioni frequenti`: poche
  * `similarità ammessa`: `bassa`
  * `match esatto obbligatorio`: `si`

---

## 10. Posizione E Contesto Per ML

* `blocchi visivi principali del documento`: header fornitore, blocco cliente, righe materiale, footer logistico, packing list
* `aree stabili tra PDF diversi`: header, riga documento, struttura riga materiale, struttura packing list
* `aree instabili tra PDF diversi`: numero righe materiale, numero pagine packing list, presenza pagina comunicazione
* `zone dove conviene fare crop mirati`: riga header DDT, singola riga materiale, gruppo packing list, colonna `COD. COLATA`
* `zone dove serve piu' contesto`: peso riga, ordine AB ODV, gruppo packing list completo
* `zone rumorose o fuorvianti`: footer, comunicazioni multilingua, firme, annotazioni manuali blu
* `necessità di pagina intera`: `si`
* `necessità di crop riga`: `si`
* `necessità di crop tabella`: `si`
* `necessità di bbox`: `alta`

### 10.1 Evidenze da conservare per ML futuro

* `numero_ddt -> crop riga header + anchor text Num./Date`
* `fornitore -> crop header/logo + contesto indirizzo`
* `codice cliente/materiale -> crop riga materiale + crop gruppo packing list`
* `lega -> crop riga CAST + crop gruppo packing list`
* `dimensione -> crop descrizione materiale + crop gruppo packing list`
* `peso -> crop riga materiale; se debole anche crop gruppo packing list`
* `colata -> crop riga CAST + crop colonna COD. COLATA`
* `numero certificato -> crop gruppo packing list con anchor Cert. N°`
* `ordine cliente -> crop riga Vs. Odv + crop campo Customer's Order No. nel certificato`

---

## 11. Casi Deboli O Da Fermare

* packing list assente o non leggibile
* piu' gruppi simili senza legame forte con la riga materiale
* OCR ambiguo sul codice cliente/materiale
* peso riga non leggibile e packing list non permette ricostruzione forte

Per ogni caso:

* `segnale di debolezza`: manca l'ancora forte o il gruppo coerente
* `cosa non assumere`: numero certificato, colata o peso da annotazioni manuali
* `azione corretta`: `lasciare vuoto / proporre solo se medio / chiedere verifica utente`

---

## 12. Punti Forti Osservati

* template molto riconoscibile e stabile
* packing list ricca di campi forti per match
* `CAST Nr.` e `COD. COLATA` stampati dal fornitore
* codice cliente/materiale molto utile per allineare DDT e certificato
* articolo interno `14BT...` molto riusabile tra DDT, packing list e certificato
* ordine cliente riusabile se normalizzato sulla rimodulazione data/numero

## 13. Punti Deboli Osservati

* scansione: `pdf_text` debole
* OCR puo' sporcare codici e virgole nei pesi
* pagina comunicazione puo' distrarre la ricerca
* le annotazioni manuali storiche possono ingannare se non escluse esplicitamente

## 14. Note Per Il Codice Futuro

* `regola 1`: leggere sempre prima pagina 1 e poi packing list, non il contrario
* `regola 2`: distinguere sempre dati stampati fornitore da annotazioni manuali storiche
* `regola 3`: usare `Cert. N°` del packing list come campo forte, mai `EN 10204 3.1`
* `regola 4`: tenere distinti `articolo interno 14BT...` e `cod. art. cliente`
* `regola 5`: se il packing list e' multipagina, proseguire fino ai totali o al cambio gruppo

---

## 15. Placeholder Da Validare Insieme

* confermare se in questo template la riga acquisition resta sempre la riga stampata di pagina 1 o se in alcuni casi va ricostruita dal gruppo packing list
* confermare se il peso di pagina 1 e' sempre abbastanza forte o se per alcuni layout va preferita la ricostruzione da packing list
* verificare se esistono DDT Aluminium Bozen senza packing list allegato nel dataset completo futuro
