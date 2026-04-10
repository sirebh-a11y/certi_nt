# DDT Supplier Template Analysis - AWW

## Scopo

Analisi del template DDT osservato per `Aluminium-Werke Wutöschingen AG & Co. KG` sui PDF reali presenti in:

```plaintext
esempi_locali/4-ddt/AWW
```

---

## 1. Identificazione

* `fornitore_master`: `Aluminium-Werke Wutöschingen AG & Co. KG`
* `alias_osservati`: `AWW`, `Wutoschingen`, `Aluminium-Werke Wutöschingen`
* `template_id`: `aww_delivery_note_extruded_bars_v1`
* `stato_analisi`: `bozza`

---

## 2. Dataset Letto

* `pdf_letti`: `14125443.pdf`, `14127594.pdf`, `14128157.pdf`, `14132220_1.pdf`, `14132220.pdf`, `14142236.pdf`
* `documenti_rappresentativi`: `14125443.pdf`, `14128157.pdf`

Osservazione:

* il dataset certificati `AWW` esiste, ma sui DDT letti non e' ancora fissato un match documentale forte e verificato

Nota metodologica:

* i nomi file aiutano solo l'analisi del dataset storico
* il match runtime futuro non deve usare il nome file
* il match runtime deve usare solo i campi letti dal DDT e dal certificato

---

## 3. Regola Chiave Del Template

Descrizione breve del template:

* delivery note testuale, molto leggibile
* una o piu' posizioni materiale nello stesso documento
* per ogni posizione sono presenti:
  * part number
  * customer part number
  * diametro
  * lega/stato
  * lunghezza
  * peso netto/lordo
  * batch number
  * packaging ID

Il template si riconosce da:

* header `Aluminium-Werke Wutöschingen`
* titolo `Delivery note`
* blocchi `Pos. | Part number | Order quantity | Net weight | Gross weight`
* righe `Your part number`
* righe `Legierung/Zustand`
* righe `Batch number (OC)`

---

## 4. Guardrail Runtime

### 4.1 Campi Usabili Nel Runtime Futuro

* delivery note number
* date
* `Part number`
* `Your part number`
* diametro
* lunghezza
* alloy / temper (`Legierung/Zustand`)
* peso netto / lordo
* `Batch number (OC)`
* packaging ID

### 4.2 Contesto Storico Da NON Usare Nel Runtime

* scritte a mano tipo colata/cdq presenti su alcuni esempi storici
* note manuali sul margine

---

## 5. Struttura Documento

### 5.1 Pagine E Blocchi

* pagina 1:
  * header fornitore
  * numero delivery note e data
  * tabella posizioni
  * dettaglio tecnico posizione
  * packaging IDs e pesi

### 5.2 Regola Di Riga Acquisition

* la riga acquisition coincide con la singola posizione materiale del DDT
* se la stessa posizione e' spezzata in piu' packaging IDs, i pesi si sommano
* il batch `OC` e' campo forte per la futura chiusura col certificato

---

## 6. Campi Forti Per Match Futuro

* `Your part number`
* `Part number`
* `Legierung/Zustand`
* diametro
* lunghezza
* `Batch number (OC)`

---

## 7. Note Runtime

* template molto leggibile e stabile
* candidato forte per parser classico a regole
* il batch e' piu' promettente del numero delivery note per il match col certificato
