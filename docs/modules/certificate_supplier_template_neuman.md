# Certificate Supplier Template Analysis - Neuman

## Scopo

Analisi del template certificato osservato per `Neuman Aluminium Austria GmbH`.

Dataset di riferimento:

```plaintext
esempi_locali/3-certificati/Vari/Neuman Aluminium Austria
```

---

## 1. Identificazione

* `fornitore_master`: `Neuman Aluminium Austria GmbH`
* `alias_osservati`: `Neuman`, `Neuman Aluminium Austria`
* `template_id`: `neuman_inspection_certificate_round_bars_v1`
* `stato_analisi`: `bozza`

---

## 2. Dataset Letto

* `pdf_letti`: `CQF_25450_6082100_2025.pdf`, `CQF_25537_6082190_2026.pdf`

Match forti verificati:

* `75706589.pdf` -> certificato lotto `25450`
* `75716074.pdf` -> certificato lotto `25537`

Nota metodologica:

* i nomi file aiutano solo l'analisi del dataset storico
* il match runtime futuro non deve usare il nome file
* il match runtime deve usare solo i campi letti dal DDT e dal certificato

---

## 3. Regola Chiave Del Template

Descrizione breve del template:

* certificato monofoglio inglese
* molto forte su delivery note, lot, materiale e customer material number
* chimica in tabella semplice
* proprieta' meccaniche come limiti richiesti / conferme

Il template si riconosce da:

* `Inspection certificate 3.1 acc. to EN 10204`
* `Delivery note`
* `Product: Round bars, peeled`
* `Customer material number`
* `Chemical composition [wt.%]`

---

## 4. Guardrail Runtime

### 4.1 Campi Usabili Nel Runtime Futuro

* delivery note
* date
* product
* material
* customer material number
* length
* quantity / net weight
* lot
* chimica
* note certificate

### 4.2 Contesto Da NON Usare Come Dato Finale

* limiti richiesti come se fossero valori prova reali
* testo di conformita' generico

---

## 5. Tabelle

### Chimica

* orientamento osservato: `orizzontale`
* riga misurata: lotto (`25450`, `25537`)
* limiti: `min`, `max`

Elementi osservati:

* `Si`, `Fe`, `Cu`, `Mn`, `Mg`, `Cr`, `Zn`, `Ti`
* `Andere` / `summe`

### Proprieta'

* non c'e' una tabella meccanica misurata classica
* compaiono limiti richiesti / conferme di compliance

Regola:

* non inventare valori meccanici misurati se il certificato riporta solo limiti richiesti

---

## 6. Regola Di Match Con DDT

Campi forti:

* `Delivery note`
* `Lot`
* `Customer material number`
* materiale
* diametro

Nota:

* `Neuman` e' uno dei casi piu' puliti del dataset per match DDT↔certificato
