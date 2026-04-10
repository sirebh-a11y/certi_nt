# DDT Supplier Template Analysis - Metalba

## Scopo

Analisi del template DDT osservato per `Metalba Aluminium S.p.A.` sui PDF reali presenti in:

```plaintext
esempi_locali/4-ddt/Metalba
```

---

## 1. Identificazione

* `fornitore_master`: `Metalba Aluminium S.p.A.`
* `alias_osservati`: `Metalba`, `Metalba Aluminium`
* `template_id`: `metalba_ddt_round_bar_v1`
* `stato_analisi`: `bozza`

---

## 2. Dataset Letto

* `pdf_letti`: `26-00957.pdf`, `26-00958.pdf`, `26-00959.pdf`, `26-00960.pdf`, `26-00961.pdf`, `26-00962.pdf`
* `documenti_rappresentativi`: `26-00957.pdf`, `26-00961.pdf`

Osservazione:

* il dataset certificati `Metalba Aluminium` esiste, ma sui DDT letti non e' ancora fissato un match documentale forte e verificato

Nota metodologica:

* i nomi file aiutano solo l'analisi del dataset storico
* il match runtime futuro non deve usare il nome file
* il match runtime deve usare solo i campi letti dal DDT e dal certificato

---

## 3. Regola Chiave Del Template

Descrizione breve del template:

* DDT classico italiano, una pagina
* una riga materiale principale per documento
* campi tecnici stampati e annotazioni manuali storiche spesso presenti sugli esempi

Il template si riconosce da:

* `DOCUMENTO DI TRASPORTO`
* `DDT26-00961` o simile
* descrizione `BARRA TONDA DIAM ...`
* `VOSTRO CODICE`
* `IN LUNGHEZZA DI`
* `Peso Netto Kg`

---

## 4. Guardrail Runtime

### 4.1 Campi Usabili Nel Runtime Futuro

* numero DDT
* data
* numero ordine / riferimento cliente
* alloy / temper nella descrizione
* diametro
* customer code
* lunghezza
* peso netto

### 4.2 Contesto Storico Da NON Usare Nel Runtime

* scritte a mano tipo `CdQ` e colata
* marcature manuali sul corpo del DDT

---

## 5. Struttura Documento

### 5.1 Pagine E Blocchi

* singola pagina
* header documento
* destinatario
* blocco riga materiale
* blocco trasporto

### 5.2 Regola Di Riga Acquisition

* in questo template una pagina coincide spesso con una riga materiale
* la riga si costruisce da:
  * alloy
  * diametro
  * customer code
  * lunghezza
  * peso netto

---

## 6. Campi Forti Per Match Futuro

* numero DDT
* customer code
* alloy
* diametro
* lunghezza
* peso netto

---

## 7. Note Runtime

* template semplice ma delicato, perche' i campi stampati sono pochi e le annotazioni manuali storiche sono fuorvianti
* qui il runtime dovra' restare molto disciplinato sui soli campi stampati
