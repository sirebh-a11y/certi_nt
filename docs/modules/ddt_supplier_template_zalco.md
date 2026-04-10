# DDT Supplier Template Analysis - Zalco

## Scopo

Analisi del template DDT osservato per `Zeeland Aluminium Company / Zalco` sui PDF reali presenti in:

```plaintext
esempi_locali/4-ddt/Zalco
```

Questo file serve a fissare:

* struttura reale del template
* varianti osservate del DDT/packing list
* campi originali usabili nel runtime futuro
* regole di match validate su piu' DDT e piu' certificati

---

## 1. Identificazione

* `fornitore_master`: `Zeeland Aluminium Company`
* `alias_osservati`: `Zalco`, `Zeeland Aluminium Company`
* `template_id`: `zalco_tally_sheet_packing_list_v1`
* `stato_analisi`: `bozza`

---

## 2. Dataset Letto

* `pdf_letti`: `20067.pdf`, `20285.pdf`, `20858.pdf`
* `pagine_totali_lette`: `4`
* `documenti_rappresentativi`: tutti e 3

Match forti gia' verificati:

* `20285.pdf` -> `CdQ_20285_Ø203G.pdf`
* `20858.pdf` -> `CdQ_20858_Ø203G.pdf`

Casi da tenere distinti:

* `20067.pdf` non ha oggi un certificato corrispondente nel dataset letto
* `CdQ_20389_6082_Ø203G.pdf` e' certificato reale dello stesso template ma non matcha i DDT sopra

Nota metodologica:

* i nomi file sopra aiutano solo l'analisi del dataset storico
* il match runtime futuro non deve usare il nome file
* il match runtime deve usare solo i campi letti dal DDT e dal certificato

---

## 3. Regola Chiave Del Template

Descrizione breve del template:

* il DDT puo' presentarsi come:
  * `AVIS D'EXPEDITION / TALLY SHEET`
  * `LISTE DE COLISAGE / PACKING LIST`
  * documento di trasporto + packing list separati
* il layout e' molto vicino al certificato e in alcuni casi contiene gia' analisi chimica inline

Il template si riconosce da:

* header `Zeeland Aluminium Company`
* `AVIS D'EXPEDITION / TALLY SHEET`
* oppure `LISTE DE COLISAGE / PACKING LIST`
* blocchi:
  * `ORDER FORGIALLUMINIO`
  * `No. AVIS / TALLY SHEET Nr.`
  * `SYMBOLE 608213`
  * `CODE ART`
  * `COULEE`
  * `ANALYSE`

---

## 4. Guardrail Runtime

### 4.1 Campi Usabili Nel Runtime Futuro

* `No. AVIS / TALLY SHEET Nr.`
* data documento
* order cliente
* `SYMBOLE`
* `CODE ART`
* diameter/section
* length
* bundles / pieces
* net/gross weight
* `COULEE`
* analisi chimica inline quando presente

### 4.2 Contesto Da NON Usare Nel Runtime

* scritte a mano storiche `CdQ` o `CL`
* marcature manuali su scansione

---

## 5. Struttura Documento

### 5.1 Varianti Osservate

* `20067.pdf`: un foglio `AVIS D'EXPEDITION` con rinvio a packing list non presente nel file
* `20285.pdf`: due pagine
  * pagina 1: CMR/spedizione
  * pagina 2: `LISTE DE COLISAGE / PACKING LIST` con analisi
* `20858.pdf`: un foglio packing list con analisi inline

### 5.2 Regola Di Lettura

1. cercare prima il foglio `PACKING LIST` o `TALLY SHEET` con i dati riga
2. se il PDF ha anche pagina CMR/spedizione, usarla solo come supporto logistico
3. leggere `COULEE`, pesi, dimensione, `CODE ART` e analisi dal foglio packing utile

### 5.3 Tabella / Riga Dati

Il cuore del template e' una riga o micro-tabella tipo:

* `COULEE`
* `FAR`
* `PCS`
* `NET`
* `TARE`
* `BRUT`
* `LONG`
* `ANALYSE`

La chimica e' spesso inline nella stessa area:

* `Si`, `Fe`, `Cu`, `Mn`, `Mg`, `Cr`, `Zn`, `Ti`

Regola:

* non separare artificialmente DDT e analisi se il fornitore le stampa insieme
* ma il valore utile resta sempre quello misurato stampato, non note manuali

---

## 6. Regola Di Riga Acquisition

* `unita materiale reale`: gruppo `COULEE` + prodotto + dimensione del packing list
* `criterio di aggregazione`: somma colli/pieces della stessa `COULEE`
* `uso del peso`: somma o totale `NET`

---

## 7. Regola Di Match Con Certificato

### 7.1 Campi Forti

* `No. AVIS / TALLY SHEET Nr.` <-> numero certificato/tally
* `COULEE`
* `SYMBOLE`
* `CODE ART`
* diameter
* weight

### 7.2 Regola Pratica

1. usare prima il numero documento (`20285`, `20858`)
2. confermare con `COULEE`
3. chiudere con `SYMBOLE`, `CODE ART`, dimensione e peso

---

## 8. Note Runtime

* questo fornitore e' importante perche' DDT e certificato sono molto vicini come struttura
* il software deve riconoscere se il foglio utile e':
  * packing list con analisi
  * oppure packing list + certificato separato ma quasi gemello
