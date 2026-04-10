# Certificate Supplier Template Analysis - Zalco

## Scopo

Analisi del template certificato osservato per `Zeeland Aluminium Company / Zalco`.

Dataset di riferimento:

```plaintext
esempi_locali/3-certificati/Vari/Zalco/Certificati Origine
```

---

## 1. Identificazione

* `fornitore_master`: `Zeeland Aluminium Company`
* `alias_osservati`: `Zalco`, `Zeeland Aluminium Company`
* `template_id`: `zalco_tally_sheet_certificate_v1`
* `stato_analisi`: `bozza`

---

## 2. Dataset Letto

* `pdf_letti`: `CdQ_20285_Ø203G.pdf`, `CdQ_20389_6082_Ø203G.pdf`, `CdQ_20858_Ø203G.pdf`
* `pagine_totali_lette`: `5`

Match forti verificati:

* `20285.pdf` -> `CdQ_20285_Ø203G.pdf`
* `20858.pdf` -> `CdQ_20858_Ø203G.pdf`

Certificato reale dello stesso template ma non usato nei DDT sopra:

* `CdQ_20389_6082_Ø203G.pdf`

Nota metodologica:

* i nomi file sopra aiutano solo l'analisi e la validazione del dataset storico
* il match runtime futuro non deve usare il nome file
* il match runtime deve usare solo i campi letti dal DDT e dal certificato

---

## 3. Regola Chiave Del Template

Descrizione breve del template:

* documento bilingue francese/inglese
* layout molto simile al DDT/packing list
* contiene identificazione spedizione + riga analisi chimica
* in alcuni casi e' di fatto un `tally sheet` certificato

Il template si riconosce da:

* `CERTIFICATE DE RECEPTION, SUITE EN 10204 3.1`
* `No. AVIS / TALLY SHEET Nr.`
* `DESCRIPTION OF MATERIAL`
* `SYMBOLE 608213`
* blocco finale con:
  * `CAST Nr.`
  * `Si`, `Fe`, `Cu`, `Mn`, `Mg`, `Cr`, `Zn`, `Ti`

---

## 4. Guardrail Runtime

### 4.1 Campi Usabili Nel Runtime Futuro

* numero certificato/tally
* data
* order cliente
* `SYMBOLE`
* `CODE`
* dimensione
* bundles / pieces
* net/gross
* `CAST Nr.`
* valori chimici misurati inline

### 4.2 Contesto Da NON Usare Come Dato Finale

* testo legale bilingue in basso
* note di trasporto / veicolo se non servono al match

---

## 5. Tabelle

### Chimica

* non e' una tabella classica separata
* i valori chimici sono inline nella riga finale del foglio
* gli elementi osservati sono:
  * `Si`, `Fe`, `Cu`, `Mn`, `Mg`, `Cr`, `Zn`, `Ti`

Regola:

* salvare solo i valori misurati presenti
* se un elemento non compare, resta `null`
* non inventare colonne mancanti

### Proprieta'

* non osservata tabella meccanica nel dataset letto
* placeholder: verificare se altri certificati `Zalco` contengono proprieta' meccaniche separate

---

## 6. Regola Di Match Con DDT

### Campi Forti

* `No. AVIS / TALLY SHEET Nr.`
* `CAST Nr.`
* `SYMBOLE`
* `CODE`
* diameter
* weight

### Regola Pratica

1. matchare prima sul numero documento/tally
2. confermare su `CAST Nr.`
3. controllare `SYMBOLE`, `CODE`, diametro e peso

---

## 7. Note Runtime

* su `Zalco` DDT e certificato hanno forte parentela strutturale
* il software deve saper distinguere:
  * foglio di trasporto puro
  * packing list utile
  * tally/certificate utile
