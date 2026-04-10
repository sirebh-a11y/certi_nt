# Certificate Supplier Template Analysis - AWW

## Scopo

Analisi del template certificato osservato per `Aluminium-Werke Wutöschingen AG & Co. KG`.

Dataset di riferimento:

```plaintext
esempi_locali/3-certificati/AWW
```

---

## 1. Identificazione

* `fornitore_master`: `Aluminium-Werke Wutöschingen AG & Co. KG`
* `alias_osservati`: `AWW`, `Wutöschingen`
* `template_id`: `aww_inspection_certificate_extruded_bars_v1`
* `stato_analisi`: `bozza`

---

## 2. Dataset Letto

* `pdf_letti`: `CQF_Z21-42315_608240_2021.pdf`, `CQF_Z21-51796_6082L43_2021.pdf`

Osservazioni forti:

* `CQF_Z21-42315_608240_2021.pdf` contiene `Kunden-Teile-Nr. A62040070`
* `CQF_Z21-51796_6082L43_2021.pdf` contiene `Kunden-Teile-Nr. A6L043070`

Limite attuale:

* il template certificato e' chiaro
* ma il dataset oggi non consente ancora un match DDT↔certificato forte e contemporaneo sui DDT 2024 letti

Nota metodologica:

* i nomi file aiutano solo l'analisi del dataset storico
* il match runtime futuro non deve usare il nome file
* il match runtime deve usare solo i campi letti dal DDT e dal certificato

---

## 3. Regola Chiave Del Template

Descrizione breve del template:

* certificato monofoglio, bilingue tedesco/inglese/francese
* molto strutturato
* campi forti in alto
* chimica e proprieta' meccaniche ben separate
* tabella meccanica sia `as delivered` sia `simulated heat treatment`

Il template si riconosce da:

* `Abnahmeprüfzeugnis 3.1`
* `Zeugnis-Nr.`
* `Kunden-Teile-Nr.`
* `Auftragsbestätigung`
* `CHEMISCHE ZUSAMMENSETZUNG`
* `MECHANISCHE EIGENSCHAFTEN`
* `MECH. EIGENSCH. SIM. WÄRMEBEHANDLUNG`

---

## 4. Guardrail Runtime

### 4.1 Campi Usabili Nel Runtime Futuro

* certificate number
* customer part number
* order confirmation
* report number
* material / alloy
* temper
* article number
* composition charge number
* tabella chimica
* tabella meccanica
* simulated heat treatment properties

### 4.2 Contesto Da NON Usare Come Dato Finale

* righe `Soll min` / `Set value max` come se fossero misurato
* testo societario/footer

---

## 5. Tabelle

### Chimica

* orientamento osservato: `orizzontale`
* riga misurata: riga `Charge No.`
* limiti: `Soll min`, `Set value max`

Elementi osservati:

* `Si`, `Fe`, `Cu`, `Mn`, `Mg`, `Cr`, `Zn`, `Ti`, `Pb`

### Proprieta' meccaniche

* orientamento osservato: `orizzontale`
* ci sono due blocchi:
  * proprieta' meccaniche standard
  * proprieta' meccaniche dopo simulated heat treatment

Regola:

* salvare solo i valori reali della riga `Charge No.`
* distinguere i due blocchi, non fonderli

---

## 6. Regola Di Match Con DDT

Campi forti futuri:

* `Kunden-Teile-Nr.`
* `Artikel-Nr.`
* alloy / temper
* charge number

Nota:

* il template e' gia' utile per il runtime
* ma il match DDT↔certificato sul dataset corrente va consolidato con piu' coppie contemporanee
