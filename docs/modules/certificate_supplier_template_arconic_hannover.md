# Certificate Supplier Template Analysis - Arconic Hannover

## Scopo

Analisi del template certificato osservato per `Arconic Extrusions Hannover`.

Dataset di riferimento:

```plaintext
esempi_locali/3-certificati/Arconic-Alcoa Hannover
```

---

## 1. Identificazione

* `fornitore_master`: `Arconic Extrusions Hannover`
* `alias_osservati`: `Arconic`, `Arconic Hannover`, `Arconic-Alcoa Hannover`
* `template_id`: `arconic_hannover_certificate_of_conformity_v1`
* `stato_analisi`: `bozza`

---

## 2. Dataset Letto

* `pdf_letti`: `CQF_EEP66506-43440412_6111A68_2023.pdf`, `CQF_EEP73062-44270958_608287_2025.pdf`

Match forti verificati:

* `27697432.pdf` -> `EEP66506`
* `28209127.pdf` -> `EEP73062`
* lo stesso `28209127.pdf` contiene anche una seconda linea materiale coerente con `EEP73061`

Nota metodologica:

* i nomi file aiutano solo l'analisi del dataset storico
* il match runtime futuro non deve usare il nome file
* il match runtime deve usare solo i campi letti dal DDT e dal certificato

---

## 3. Regola Chiave Del Template

Descrizione breve del template:

* `Certificate of Conformity`
* page 1 ricca, page 2 secondaria
* forte corrispondenza con i campi del DDT
* chimica e proprieta' meccaniche strutturate

Il template si riconosce da:

* `Cert Number EEP...`
* `Sales Order Number`
* `Customer P/O`
* `Delivery Note No.`
* `Customer Item No.`
* `CAST/JOB NUMBER`
* `Composition Results in %`
* `Mechanical Property - Test Limits`

---

## 4. Guardrail Runtime

### 4.1 Campi Usabili Nel Runtime Futuro

* cert number
* sales order number
* customer PO
* delivery note no
* internal ref / item no
* customer item no
* cast/job number
* composition results
* mechanical properties

### 4.2 Contesto Da NON Usare Come Dato Finale

* comments normativi come valori materiale
* test limits come misurato

---

## 5. Tabelle

### Chimica

* orientamento osservato: `orizzontale`
* risultati in una riga `Composition Results in %`
* limiti separati

### Proprieta' meccaniche

* orientamento osservato: `orizzontale`
* riga misurata distinta da `SPECLIMITS`

Regola:

* salvare solo la riga misurata
* non usare `SPECLIMITS` come prova reale

---

## 6. Regola Di Match Con DDT

Campi forti:

* `CAST/JOB NUMBER`: separare `CAST Number` e `job/package`
* `Customer Item No.`
* `Item No.` / `Arconic Item Number`
* `Line No.`
* `Delivery Note No.`
* `Sales Order Number`
* `Customer P/O`
* lega e diametro ricavati da `Item Description` quando presenti

Regola `CdQ` in lista:

* il campo `CdQ` del certificato deve usare `Cert Number` + `-` + primo job/package di `CAST/JOB NUMBER`
* esempio: `Cert Number EEP73417` e `CAST/JOB NUMBER C.../44281864` diventano `EEP73417-44281864`
* se il package/job non e' leggibile, usare solo `Cert Number`

Nota:

* template molto forte
* uno stesso DDT puo' matchare piu' certificati quando contiene piu' linee materiale
* uno stesso certificato puo' coprire piu' package/lot della stessa riga DDT
