# DDT Supplier Template Analysis - Grupa Kety

## Scopo

Analisi del template DDT osservato per `Grupa Kety S.A.` sui PDF reali presenti in:

```plaintext
esempi_locali/4-ddt/Grupa Kety
```

---

## 1. Identificazione

* `fornitore_master`: `Grupa Kety S.A.`
* `alias_osservati`: `Grupa Kety`, `Kety`
* `template_id`: `grupa_kety_delivery_note_packing_slip_v1`
* `stato_analisi`: `bozza`

---

## 2. Dataset Letto

* `pdf_letti`: `12594.pdf`, `201138817.pdf`, `201144562.pdf`, `201149900.pdf`, `201154858.pdf`, `201177772.pdf`
* `documenti_rappresentativi`: `12594.pdf`, `201149900.pdf`

Match forte gia' verificato:

* `12594.pdf` -> certificato `10033541/25` con stessi campi documentali

Nota metodologica:

* i nomi file aiutano solo l'analisi del dataset storico
* il match runtime futuro non deve usare il nome file
* il match runtime deve usare solo i campi letti dal DDT e dal certificato

---

## 3. Regola Chiave Del Template

Descrizione breve del template:

* delivery note / packing slip leggibile
* una linea ordine puo' contenere piu' lotti
* sono presenti sia codici interni sia customer part number

Il template si riconosce da:

* `Delivery Note` o `Packing Slip`
* `Shipment ID`
* `Line / Part No / Description`
* `Sales Order`
* `Lot Batch No / Batch Melt`
* `Qty Shipped`
* `Net weight`

---

## 4. Guardrail Runtime

### 4.1 Campi Usabili Nel Runtime Futuro

* delivery note / packing slip number
* shipment ID
* sales order
* part number
* customer part number
* alloy
* temper
* length
* qty / pcs
* net/gross
* lot batch no / batch melt

### 4.2 Contesto Da NON Usare Nel Runtime

* firme / ricezione
* dati autista e mezzo come campi di match

---

## 5. Struttura Documento

### 5.1 Pagine E Blocchi

* singola pagina
* header spedizione
* tabella linee / lotti
* totali ordine

### 5.2 Regola Di Riga Acquisition

* la riga acquisition coincide con il lotto materiale coerente
* se la stessa linea contiene piu' lotti diversi, vanno distinte
* i lotti sono il ponte naturale verso il certificato

---

## 6. Campi Forti Per Match Futuro

* packing slip / delivery note
* lot batch no
* alloy
* customer part number
* dimensione
* customer order / PO

---

## 7. Note Runtime

* `Grupa Kety` e' forte perche' il lotto compare in modo pulito sia nel DDT sia nel certificato
* la chimica e le proprieta' certificate sembrano poi agganciarsi al lotto, non al documento intero
