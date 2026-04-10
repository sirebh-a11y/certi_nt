# DDT Supplier Template Analysis - Neuman

## Scopo

Analisi del template DDT osservato per `Neuman Aluminium Austria GmbH` sui PDF reali presenti in:

```plaintext
esempi_locali/4-ddt/Neuman
```

---

## 1. Identificazione

* `fornitore_master`: `Neuman Aluminium Austria GmbH`
* `alias_osservati`: `Neuman`, `Neuman Aluminium Austria`
* `template_id`: `neuman_delivery_note_lot_based_v1`
* `stato_analisi`: `bozza`

---

## 2. Dataset Letto

* `pdf_letti`: `75706589_1.pdf`, `75706589.pdf`, `75706590.pdf`, `75712652.pdf`, `75716074.pdf`, `75724077.pdf`
* `documenti_rappresentativi`: `75706589.pdf`, `75716074.pdf`

Match forti gia' verificati:

* `75706589.pdf` -> certificato con `Delivery note 75706589`, lot `25450`, materiale `6082`, diametro `100`
* `75716074.pdf` -> certificati del lotto `25537`, diametro `190`, materiale `6082`

Nota metodologica:

* i nomi file aiutano solo l'analisi del dataset storico
* il match runtime futuro non deve usare il nome file
* il match runtime deve usare solo i campi letti dal DDT e dal certificato

---

## 3. Regola Chiave Del Template

Descrizione breve del template:

* delivery note monofoglio molto leggibile
* una linea ordine principale
* dettaglio colli/lotto nella parte bassa

Il template si riconosce da:

* `Delivery Note 75706589`
* `Delivering Plant`
* `Load`
* `Order Line Item Qty Shipped`
* `Rundstangen`
* `Werkstoff`
* `Art-Nr.`
* `Customer Order Number`
* `Contract`
* `HU` / `Lot`

---

## 4. Guardrail Runtime

### 4.1 Campi Usabili Nel Runtime Futuro

* delivery note number
* date
* load
* order line/item
* diametro
* lunghezza
* materiale
* article number
* customer order number
* contract
* `Lot`
* pesi net/gross

### 4.2 Contesto Da NON Usare Nel Runtime

* scritte a mano storiche sugli esempi
* dati societari/footer

---

## 5. Struttura Documento

### 5.1 Pagine E Blocchi

* singola pagina
* header documento
* blocco prodotto principale
* blocco dettagli `HU` / `Lot`
* totali finali

### 5.2 Regola Di Riga Acquisition

* la riga acquisition coincide con il gruppo prodotto/lotto coerente
* i colli `HU` dello stesso lotto si sommano
* il `Lot` e' il campo tecnico piu' forte per il match col certificato

---

## 6. Campi Forti Per Match Futuro

* delivery note number
* `Lot`
* article number
* materiale
* diametro
* customer order number

---

## 7. Note Runtime

* template molto buono per match documentale, perche' `Lot` e `Delivery note` passano anche nel certificato
* ottimo caso per pipeline riga->certificato con alta affidabilita'
