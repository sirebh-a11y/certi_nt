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
* `stato_analisi`: `avanzata`

---

## 2. Dataset Letto

* `pdf_letti`: `26-00957.pdf`, `26-00958.pdf`, `26-00959.pdf`, `26-00960.pdf`, `26-00961.pdf`, `26-00962.pdf`
* `documenti_rappresentativi`: `26-00957.pdf`, `26-00961.pdf`, `26-00962.pdf`

Osservazione:

* il dataset certificati `Metalba Aluminium` consente ora un match documentale forte e verificato su tutti i 6 DDT letti

Nota metodologica:

* i nomi file aiutano solo l'analisi del dataset storico
* il match runtime futuro non deve usare il nome file
* il match runtime deve usare solo i campi letti dal DDT e dal certificato

---

## 3. Regola Chiave Del Template

Descrizione breve del template:

* DDT classico italiano, una pagina
* una riga materiale principale per documento nella maggior parte dei casi
* non assumere pero' monoriga come vincolo assoluto: se il documento contiene piu' righe materiali, il runtime deve saperle trattare separate
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

Campi ponte forti osservati verso il certificato:

* `Vs. Rif.`
* alloy / temper
* diametro
* peso netto

Campi documentali di supporto osservati verso il certificato:

* `Rif. Ord.`

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
* non trasformare questa osservazione in una regola rigida: se compaiono piu' righe materiali, vanno mantenute separate
* la riga si costruisce da:
  * alloy
  * diametro
  * customer code
  * lunghezza
  * peso netto
* `Vs. Rif.` e' il campo documento piu' forte per il match col certificato
* `Rif. Ord.` resta un campo di supporto utile, coerente con `Commessa`, ma non e' il ponte principale

---

## 6. Campi Forti Per Match Futuro

* numero DDT
* customer code
* alloy
* diametro
* lunghezza
* peso netto
* `Vs. Rif.`

Campi di supporto:

* `Rif. Ord.`

Casi gia' verificati:

* `26-00957.pdf` -> `Nr.26-0743`
  * DDT: `Vs. Rif. 27/26`, `Rif. Ord. 26/0173`, `6082F F`, `diam 38`, `Kg 2.233`
  * certificato: `Ordine Cliente 27/26`, `Commessa 26/0173/1`, `6082F F`, `diam 38`, `Kg 2.233`
* `26-00958.pdf` -> `Nr.26-0744`
  * DDT: `11/26`, `26/0082`, `6082F F`, `diam 28`, `Kg 3.205`
  * certificato: `Ordine Cliente 11/26`, `Commessa 26/0082/2`, `diam 28`, `Kg 3.205`
* `26-00959.pdf` -> `Nr.26-0745`
  * DDT: `25/26`, `26/0187`, `7003 F`, `diam 43`, `Kg 4.133`
  * certificato: `Ordine Cliente 25/26`, `Commessa 26/0187/2`, `7003 F`, `diam 43`, `Kg 4.133`
* `26-00960.pdf` -> `Nr.26-0746`
  * DDT: `45/26`, `26/0310`, `6082F F`, `diam 48`, `Kg 1.334`
  * certificato: `Ordine Cliente 45/26`, `Commessa 26/0310/4`, `diam 48`, `Kg 1.334`
* `26-00961.pdf` -> `Nr.26-0747`
  * DDT: `86/26`, `26/0499`, `6082F F`, `diam 90`, `Kg 2.334`
  * certificato: `Ordine Cliente 86/26`, `Commessa 26/0499/3`, `diam 90`, `Kg 2.334`
* `26-00962.pdf` -> `Nr.26-0748`
  * DDT: `31/26`, `26/0179`, `6082F F`, `diam 105`, `Kg 4.870`
  * certificato: `Ordine Cliente 31/26`, `Commessa 26/0179/1`, `diam 105`, `Kg 4.870`

---

## 7. Note Runtime

* template semplice ma delicato, perche' i campi stampati sono pochi e le annotazioni manuali storiche sono fuorvianti
* il match runtime puo' essere forte anche senza colata scritta a mano, usando prima di tutto `Vs. Rif.` e poi alloy/diametro/peso
* `Rif. Ord.` resta utile come supporto coerente con `Commessa`, ma non deve sostituire `Vs. Rif.` come ponte principale
* qui il runtime dovra' restare disciplinato sui soli campi stampati
