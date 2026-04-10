# Certificate Supplier Template Analysis - Impol

## Scopo

Analisi del template certificato osservato per `Impol d.o.o.` sui certificati reali che matchano i DDT gia' studiati.

Dataset di riferimento:

```plaintext
esempi_locali/3-certificati/Impol
```

---

## 1. Identificazione

* `fornitore_master`: `Impol d.o.o.`
* `alias_osservati`: `Impol`, `Impol Group`
* `template_id`: `impol_inspection_certificate_extruded_bars_v1`
* `stato_analisi`: `bozza`

---

## 2. Dataset Letto

* `pdf_letti`: `CQF_1505_a_608232_2026.pdf`, `CQF_1505_b_6005A33_2026.pdf`, `CQF_1505_c_6005A35_2026.pdf`, `CQF_28691_a_608232_2025.pdf`, `CQF_3078_a_608224_2026.pdf`, `CQF_3078_b_6005A35_2026.pdf`
* `pagine_totali_lette`: `12`

Match forti verificati:

* `1505-11.pdf` -> serie `1505/a`, `1505/b`, `1505/c`
* `28691-11.pdf` -> `28691/a`
* `3078-11.pdf` -> `3078/a`, `3078/b`

Nota metodologica:

* i nomi file sopra aiutano solo l'analisi e la validazione del dataset storico
* il match runtime futuro non deve usare il nome file
* il match runtime deve usare solo i campi letti dal DDT e dal certificato

---

## 3. Regola Chiave Del Template

Descrizione breve del template:

* certificato tecnico strutturato
* page 1 molto ricca e sufficiente nella maggior parte dei casi
* campi forti subito in header
* tabella chimica con riga charge misurata
* tabella proprieta' meccaniche sotto
* blocchi note tecniche e conformita' in fondo

Il template si riconosce da:

* `No. 1505/a`, `No. 28691/a`, ecc.
* `Customer Order No.`
* `Supplier Order No.`
* `Packing list No.`
* `Chemical composition according to norm EN 573-3`
* `Mechanical properties according to norm EN 755-2/EN 603-2`

---

## 4. Guardrail Runtime

### 4.1 Campi Usabili Nel Runtime Futuro

* numero certificato con suffisso lettera
* `Customer Order No.`
* `Supplier Order No.`
* `Packing list No.`
* product code
* descrizione prodotto
* weight netto
* riga chimica della `Charge`
* tabella proprieta' meccaniche
* note come:
  * `AMS STD 2154 CLASS B`
  * `HYDROGEN CONTENT`
  * `RoHS`

### 4.2 Contesto Da NON Usare Come Dato Finale

* righe `Min` e `Max` della chimica come misurato
* righe `Min:` della tabella meccanica come prove reali
* testo legale finale o ISO come dato materiale

---

## 5. Tabelle

### Chimica

* orientamento osservato: `orizzontale`
* riga misurata: la riga della `Charge`
* righe limiti: `Min` e `Max`

Elementi osservati:

* standard:
  * `Si`, `Fe`, `Cu`, `Mn`, `Mg`, `Cr`, `Zn`, `Ti`
* in alcuni certificati anche:
  * `Mn+Cr`
  * `Cd`, `Hg`, `Pb`

Regola:

* salvare solo i valori misurati della `Charge`
* se un elemento non compare come misurato, resta `null`
* i combinati come `Mn+Cr` si salvano se presenti davvero

### Proprieta' meccaniche

* orientamento osservato: `orizzontale`
* righe misurate: i lotti/pallet reali
* righe limiti: `Min:`

Colonne osservate:

* `Rm`
* `Rpo,2`
* `Elongation A%`
* `Hardness HBW`

Regola:

* salvare solo le righe misurate reali
* non trattare `Min:` come valore prova

---

## 6. Regola Di Match Con DDT

### Campi Forti

* `Packing list No.`
* `Customer Order No.`
* `Supplier Order No.`
* product code
* alloy/temper
* diametro
* `Charge`

### Regola Pratica

1. entrare dal `Packing list No.`
2. separare le famiglie materiale con `Customer Order No.` / `Supplier Order No.`
3. confermare con alloy, diametro e `Charge`

---

## 7. Note Runtime

* `Impol` e' importante perche' le tabelle chimiche e meccaniche sono ricche ma pulite
* e' anche il caso piu' evidente in cui:
  * un DDT puo' generare piu' righe
  * e ogni riga puo' avere il suo certificato con suffisso lettera
