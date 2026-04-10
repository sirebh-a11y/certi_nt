# DDT Supplier Template Analysis - Arconic Hannover

## Scopo

Analisi del template DDT osservato per `Arconic Extrusions Hannover` sui PDF reali presenti in:

```plaintext
esempi_locali/4-ddt/Arconic Hannover
```

---

## 1. Identificazione

* `fornitore_master`: `Arconic Extrusions Hannover`
* `alias_osservati`: `Arconic`, `Arconic Hannover`, `Arconic-Alcoa Hannover`
* `template_id`: `arconic_hannover_delivery_note_multiline_v1`
* `stato_analisi`: `bozza`

---

## 2. Dataset Letto

* `pdf_letti`: `27697432.pdf`, `27989796.pdf`, `28209127.pdf`, `28209129.pdf`, `28214518.pdf`, `28240083.pdf`
* `documenti_rappresentativi`: `27697432.pdf`, `28209127.pdf`

Match forti gia' verificati:

* `27697432.pdf` -> certificato `EEP66506` con stessi campi documentali
* `28209127.pdf` -> certificati `EEP73061` / `EEP73062` coerenti con le due famiglie materiale del DDT

Nota metodologica:

* i nomi file aiutano solo l'analisi del dataset storico
* il match runtime futuro non deve usare il nome file
* il match runtime deve usare solo i campi letti dal DDT e dal certificato

---

## 3. Regola Chiave Del Template

Descrizione breve del template:

* delivery note strutturato, multi-linea, spesso su piu' pagine
* header con molti campi ordine/cliente/spedizione
* ogni linea materiale ha:
  * customer item number
  * customer item description
  * arconic item number
  * die / dimension
  * cast number
  * package IDs
  * metri e pesi

Il template si riconosce da:

* `Delivery Note`
* `Sales Order Number`
* `Customer Purchase Order`
* `Customer Item number`
* `Arconic Item number`
* `CAST Number`

---

## 4. Guardrail Runtime

### 4.1 Campi Usabili Nel Runtime Futuro

* delivery note number
* sales order number
* customer purchase order
* customer item number
* customer item description
* arconic item number
* die / dimension
* cast number
* net/gross/tara
* package IDs

### 4.2 Contesto Da NON Usare Nel Runtime

* dati logistici del vettore come campo di match principale
* commenti normativi generici

---

## 5. Struttura Documento

### 5.1 Pagine E Blocchi

* pagina 1:
  * header documento
  * tabella linee materiale
  * package rows per ogni linea
* pagine successive:
  * continuazione linee materiale / packages

### 5.2 Regola Di Riga Acquisition

* una riga acquisition coincide con la singola linea materiale del DDT
* i package IDs della stessa linea si sommano come peso netto/lordo
* uno stesso DDT puo' generare piu' righe acquisition e piu' certificati

---

## 6. Campi Forti Per Match Futuro

* `Delivery Note No.`
* `Sales Order Number`
* `Customer Purchase Order`
* `Customer Item number`
* `Arconic Item number`
* `CAST Number`
* dimensione

---

## 7. Note Runtime

* template forte e ricco, molto adatto a parser strutturato
* il `CAST Number` e' il campo chiave tecnico, ma non basta da solo quando il DDT ha piu' linee
* serve sempre distinguere la linea materiale corretta prima del match col certificato
