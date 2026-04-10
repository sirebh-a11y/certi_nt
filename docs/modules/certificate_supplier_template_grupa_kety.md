# Certificate Supplier Template Analysis - Grupa Kety

## Scopo

Analisi del template certificato osservato per `Grupa Kety S.A.`.

Dataset di riferimento:

```plaintext
esempi_locali/3-certificati/Grupa Kety
```

---

## 1. Identificazione

* `fornitore_master`: `Grupa Kety S.A.`
* `alias_osservati`: `Grupa Kety`, `Kety`
* `template_id`: `grupa_kety_inspection_certificate_v1`
* `stato_analisi`: `bozza`

---

## 2. Dataset Letto

* `pdf_letti`: `CQF_10033541_25_715044_2025.pdf`, `CQF_10033543_25_715044_2025.pdf`

Match forti verificati:

* `12594.pdf` -> `10033541/25`
* `12594.pdf` -> `10033543/25`

Nota metodologica:

* i nomi file aiutano solo l'analisi del dataset storico
* il match runtime futuro non deve usare il nome file
* il match runtime deve usare solo i campi letti dal DDT e dal certificato

---

## 3. Regola Chiave Del Template

Descrizione breve del template:

* certificato monofoglio bilingue polacco/inglese
* molto forte su:
  * lot / packing slip
  * order no
  * alloy
  * heat
* chimica, proprieta' meccaniche e metallografia nello stesso foglio

Il template si riconosce da:

* `Swiadectwo odbioru 3.1`
* `Packing Slip / Lot`
* `Order No`
* `Heat`
* `SKLAD CHEMICZNY - CHEMICAL COMPOSITION`
* `WEASNOSCI MECHANICZNE - MECHANICAL PROPERTIES`

---

## 4. Guardrail Runtime

### 4.1 Campi Usabili Nel Runtime Futuro

* certificate / lot number
* order no
* sales order
* packing slip
* item specification
* alloy grade
* heat
* pieces
* temper
* chimica
* proprieta' meccaniche

### 4.2 Contesto Da NON Usare Come Dato Finale

* righe descrittive su conformita'
* limiti minimi come misurato

---

## 5. Tabelle

### Chimica

* orientamento osservato: `orizzontale`
* riga misurata della `Heat`
* elementi osservati:
  * `Si`, `Fe`, `Cu`, `Mn`, `Mg`, `Cr`, `Zn`, `Ti`, `Zr`

### Proprieta' meccaniche

* orientamento osservato: `orizzontale`
* righe misurate per sample `T00x`
* limiti minimi separati

Regola:

* salvare la riga sample misurata
* non usare il blocco limiti come valore prova

---

## 6. Regola Di Match Con DDT

Campi forti:

* packing slip / lot
* order no
* customer part
* alloy
* heat

Nota:

* `Grupa Kety` e' forte e coerente su DDT e certificato
