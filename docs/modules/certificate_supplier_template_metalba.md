# Certificate Supplier Template Analysis - Metalba

## Scopo

Analisi del template certificato osservato per `Metalba Aluminium S.p.A.`.

Dataset di riferimento:

```plaintext
esempi_locali/3-certificati/Metalba Aluminium
```

---

## 1. Identificazione

* `fornitore_master`: `Metalba Aluminium S.p.A.`
* `alias_osservati`: `Metalba`, `Metalba Aluminium`
* `template_id`: `metalba_test_certificate_v1`
* `stato_analisi`: `avanzata`

---

## 2. Dataset Letto

* `pdf_letti`: `CQF_14-0961_2014.pdf`, `CQF_14-1232_2014.pdf`, `CQF_26-0743_608238_2026.pdf`, `CQF_26-0744_608228_2026.pdf`, `CQF_26-0745_700343_2026.pdf`, `CQF_26-0746_608248_2026.pdf`, `CQF_26-0747_608290_2026.pdf`, `CQF_26-0748_6082105_2026.pdf`

Osservazione forte:

* il dataset 2026 consente ora un match DDT↔certificato forte e contemporaneo sui 6 DDT letti

Nota metodologica:

* i nomi file aiutano solo l'analisi del dataset storico
* il match runtime futuro non deve usare il nome file
* il match runtime deve usare solo i campi letti dal DDT e dal certificato

---

## 3. Regola Chiave Del Template

Descrizione breve del template:

* certificato monofoglio italiano/inglese
* header con lega, stato, colata, valori meccanici
* sotto tabella chimica con `Min`, `Max` e valore misurato
* note forti come radioactivity free / AMS class

Il template si riconosce da:

* `Certificato di Collaudo 3.1`
* `Lega Stato Colata Nr.`
* `Rm`, `Rp`, `A%`
* `ANALISI CHIMICA / CHEMICAL COMPOSITION`

---

## 4. Guardrail Runtime

### 4.1 Campi Usabili Nel Runtime Futuro

* certificate number
* date
* alloy
* temper
* casting no
* `Commessa`
* `Ordine Cliente`
* mechanical values
* chemistry values
* note certificate

### 4.2 Contesto Da NON Usare Come Dato Finale

* limiti `Min` e `Max` come misurato
* note di processo come valore materiale

---

## 5. Tabelle

### Chimica

* orientamento osservato: `orizzontale`
* righe limiti: `Min`, `Max`
* riga misurata: riga della colata

Elementi osservati:

* `Si`, `Fe`, `Cu`, `Mn`, `Mg`, `Zn`, `Ti`, `Cr`, `Pb`, `Bi`, `Ni`, `Zr`, `Sn`, `Be`
* nota combinata possibile: `Zr+Ti`

### Proprieta' meccaniche

* valori riassunti in header / tabella alta
* `Rm`, `Rp`, `A%`

Regola:

* salvare solo i valori reali della colata
* i combinati tipo `Zr+Ti` si salvano solo se presenti davvero

---

## 6. Regola Di Match Con DDT

Campi forti futuri:

* casting no
* alloy / temper
* customer code
* dimensione
* `Commessa`
* `Ordine Cliente`

Nota:

* il template certificato e' maturo
* il match forte osservato nasce da:
  * `Commessa` <-> `Rif. Ord.` del DDT
  * `Ordine Cliente` <-> `Vs. Rif.` del DDT
  * alloy / temper
  * dimensione
  * peso
* il suffisso di `Commessa` (`/1`, `/2`, `/3`, `/4`) e' dettaglio di sottoriga certificato, mentre il root coincide col valore DDT

Casi gia' verificati:

* `Nr.26-0743` <-> DDT `26-00957.pdf`
* `Nr.26-0744` <-> DDT `26-00958.pdf`
* `Nr.26-0745` <-> DDT `26-00959.pdf`
* `Nr.26-0746` <-> DDT `26-00960.pdf`
* `Nr.26-0747` <-> DDT `26-00961.pdf`
* `Nr.26-0748` <-> DDT `26-00962.pdf`
