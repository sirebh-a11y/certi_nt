# DDT Supplier Template Analysis - Impol

## Scopo

Analisi del template DDT osservato per `Impol d.o.o.` sui PDF reali presenti in:

```plaintext
esempi_locali/4-ddt/Impol
```

---

## 1. Identificazione

* `fornitore_master`: `Impol d.o.o.`
* `alias_osservati`: `Impol`, `Impol Group`
* `template_id`: `impol_packing_list_multiriga_v1`
* `stato_analisi`: `bozza`

---

## 2. Dataset Letto

* `pdf_letti`: `1505-11.pdf`, `28691-11.pdf`, `29289-11.pdf`, `3078-11.pdf`, `5445-11.pdf`, `636-11.pdf`
* `pagine_totali_lette`: `6`

Match forti verificati:

* `1505-11.pdf` -> `CQF_1505_a_608232_2026.pdf`, `CQF_1505_b_6005A33_2026.pdf`, `CQF_1505_c_6005A35_2026.pdf`
* `28691-11.pdf` -> `CQF_28691_a_608232_2025.pdf`, `CQF_28691_b_608232_2025.pdf`
* `29289-11.pdf` -> `CQF_29289#a_6005A35_2025.pdf`, `CQF_29289#b_618236_2025.pdf`
* `3078-11.pdf` -> `CQF_3078_a_608224_2026.pdf`, `CQF_3078_b_6005A35_2026.pdf`
* `5445-11.pdf` -> `CQF_5445_a_6005A33_2026.pdf`, `CQF_5445_b_6005A35_2026.pdf`, `CQF_5445_c_6005A36_2026.pdf`, `CQF_5445_d_6005A35_2026.pdf`
* `636-11.pdf` -> `CQF_636_a_608224_2026.pdf`, `CQF_636_b_6005A36_2026.pdf`

Nota metodologica:

* i nomi file sopra aiutano solo l'analisi del dataset storico
* il match runtime futuro non deve usare il nome file
* il match runtime deve usare solo i campi letti dal DDT e dal certificato
* nel dataset storico il root del packing list (`1505`, `28691`, `29289`, `3078`, `5445`, `636`) consente di entrare nel gruppo certificati corretto; la chiusura runtime resta comunque a livello di riga

---

## 3. Regola Chiave Del Template

Descrizione breve del template:

* packing list monofoglio
* piu' posizioni prodotto nello stesso documento
* ogni posizione puo' avere:
  * product code
  * descrizione materiale
  * `Your order No.`
  * `Order date`
  * piu' packing unit
  * `Charge`

Il template si riconosce da:

* header `Impol d.o.o.`
* titolo `PACKING LIST`
* tabella con:
  * `Pos.`
  * `Product code`
  * `Product description`
  * `Your order No.`
  * `Order date`
* righe `Packing unit Gross (kg) Net (kg) Charge`

---

## 4. Guardrail Runtime

### 4.1 Campi Usabili Nel Runtime Futuro

* packing list number
* customer number
* product code
* descrizione prodotto
* order cliente
* order date
* gross/net
* charge
* diametro e lunghezza dentro la descrizione
* alloy / temper dentro la descrizione

### 4.2 Contesto Da NON Usare Nel Runtime

* testo societario/footer
* dati fiscali
* note di trasporto generiche

---

## 5. Struttura Documento

### 5.1 Varianti Osservate

* `1505-11.pdf`: packing list con piu' posizioni materiale e piu' charge
* `28691-11.pdf`: packing list piu' semplice, una famiglia materiale coerente
* `29289-11.pdf`: packing list con almeno due famiglie materiale
* `3078-11.pdf`: packing list con almeno due famiglie materiale, quindi piu' certificati
* `5445-11.pdf`: packing list con gruppo ampio di righe/certificati
* `636-11.pdf`: packing list corto ma comunque multi-certificato

### 5.2 Regola Di Riga Acquisition

* la riga acquisition non coincide col packing list intero
* coincide con la singola posizione materiale coerente per:
  * alloy/temper
  * diametro
  * `Your order No.`
  * `Charge`

Regola:

* uno stesso DDT/packing list puo' produrre piu' righe acquisition
* e puo' richiedere piu' certificati collegati

---

## 6. Regola Di Match Con Certificato

### Campi Forti

* `Packing list No.`
* `Customer Order No.`
* `Supplier Order No.`
* alloy/temper
* diametro
* `Charge`

### Regola Pratica

1. usare il packing list number per entrare nel gruppo giusto (`1505`, `28691`, `29289`, `3078`, `5445`, `636`)
2. distinguere poi le righe con `Customer Order No.` e `Supplier Order No.`
3. chiudere il match con alloy, diametro e `Charge`

---

## 7. Note Runtime

* `Impol` e' un caso importante perche' un solo DDT puo' avere piu' certificati
* il dataset storico conferma gruppi certificato completi anche per `29289`, `5445` e `636`, non solo per `1505`, `28691` e `3078`
* qui il software deve ragionare davvero a livello di riga materiale e non di documento intero
