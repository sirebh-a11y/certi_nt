# DDT Supplier Template Analysis Template

## Scopo

Template base da compilare **per ogni fornitore/template DDT** dopo la lettura reale dei PDF presenti in:

```plaintext
esempi_locali/4-ddt
```

Questo file serve a:

* fissare le regole documentali osservate davvero
* validarle insieme prima del codice
* trasformarle poi in logica runtime

Questo file NON serve a:

* scrivere direttamente il parser
* inventare regole non osservate
* assumere la presenza di annotazioni manuali nei DDT futuri caricati in app

---

## Vincolo Guida Del Progetto

La lettura documentale corretta, orientata il piu' possibile al **100% di precisione**, e' la parte piu' vitale dell'app.

Quindi, per ogni template:

* va cercata la lettura migliore possibile
* vanno combinati tutti i sistemi utili quando serve
* non vanno accettate assunzioni deboli come base del runtime
* la precisione della lettura viene prima della comodita' di implementazione

Strumenti possibili da valutare:

* `pdf_text`
* `regex`
* `ocr`
* `vision`
* `lettura tabellare`
* `confronto DDT-certificato`
* `validazione utente`

Se per un template/campo si valuta l'uso di ChatGPT/OpenAI:

* deve essere annotato esplicitamente
* deve essere scelto il modello migliore adatto al caso
* prima di ogni uso runtime o test va data una stima costi
* l'uso di OpenAI deve essere dichiarato prima dell'esecuzione

---

## 1. Identificazione

* `fornitore_master`:
* `alias_osservati`:
* `template_id`:
* `stato_analisi`: `bozza / validato / da rivedere`

---

## 2. Dataset Letto

* `cartella`:
* `pdf_letti`:
* `pagine_totali_lette`:
* `documenti_rappresentativi`:

Esempi principali:

* `...`
* `...`
* `...`

---

## 3. Regola Chiave Del Template

Descrizione breve del template:

* come si riconosce
* qual e' la struttura generale
* cosa lo distingue da altri template dello stesso fornitore

---

## 4. Guardrail Runtime

### 4.1 Campi Usabili Nel Runtime Futuro

Qui vanno solo i campi del **documento originale del fornitore** che possono essere usati davvero nel runtime.

* `...`
* `...`

### 4.2 Contesto Storico Da NON Usare Nel Runtime

Qui vanno annotazioni o comportamenti osservati nei PDF storici ma che NON devono diventare presupposto del sistema futuro.

Esempi tipici:

* `cdq` scritto a mano
* `colata` scritta a mano
* note operative incoming

Per ogni caso scrivere:

* `campo/annotazione`:
* `utile per capire il processo storico`: `si/no`
* `usabile nel runtime futuro`: `no`
* `nota`:

---

## 5. Struttura Documento

### 5.1 Pagine E Blocchi

* pagina 1:
* pagina 2:
* eventuali allegati/packing list:

### 5.2 Dove Cercare Prima

Ordine reale di lettura:

1. `...`
2. `...`
3. `...`

### 5.3 Dove NON Cercare O Cosa Non Confondere

* `...`
* `...`

---

## 6. Regola Di Riga Acquisition

Qui si descrive come nasce la riga acquisition da questo template DDT.

Compilare:

* `unità materiale reale`:
* `criterio di aggregazione`: `per riga / per batch / per charge / per colata / altro`
* `uso del peso`: `diretto / somma / altro`
* `uso del packing list`: `si/no`
* `regola pratica`:

Se il peso o la riga vanno ricostruiti, descrivere esplicitamente:

* dove si trova il dettaglio
* quali righe/collo/lotti sommare
* quando fermarsi e lasciare il caso all’utente

---

## 7. Campi Da Ricercare

Per ogni campo utile al runtime compilare questa scheda.

### 7.x Campo: `NOME_CAMPO`

* `obbligatorio nel runtime`: `si/no`
* `usato per match con certificato`: `forte / medio / debole / no`
* `pagina/blocco principale`:
* `posizione precisa osservata`:
* `relazione spaziale con altri campi`:
* `ancore testuali`:
* `vicinanza ad altri campi`:
* `varianti di scrittura`:
* `tipo valore`: `documentale puro / numerico standardizzato / codice / testo`
* `unita implicita`: `nessuna / mm / kg / % / altro`
* `strumento di lettura migliore`: `pdf_text / regex / ocr / vision / tabellare`
* `contesto minimo necessario`: `campo / riga / riga + header / blocco / pagina`
* `materiale utile per ML futuro`: `crop campo / crop riga / crop tabella / pagina / bbox / anchor text`
* `materiale fuorviante da evitare`: 
* `fallback di ricerca`:
* `falsi positivi noti`:
* `nota runtime`:

Campi minimi da compilare:

* `numero_ddt`
* `data_documento`
* `fornitore`
* `ordine`
* `lega`
* `dimensione`
* `peso`
* `codice materiale / codice cliente`
* `colata`
* `cast / batch / charge` se presente
* `numero certificato riportato sul DDT` se presente

---

## 8. Match DDT -> Certificato

### 8.1 Campi Forti Osservati

* `...`
* `...`

### 8.2 Campi Medi O Deboli

* `...`
* `...`

### 8.3 Regola Pratica Di Match

1. `...`
2. `...`
3. `...`

### 8.4 Eccezioni

* `peso diretto o da sommare`:
* `batch/cast/charge obbligatorio o no`:
* `ordine forte/medio/debole`:
* `mismatch apparenti noti`:

---

## 9. Similarità E Varianti Codici

Qui descrivere come vanno confrontati i codici del template.

Per ogni tipo codice utile:

* `nome codice`:
* `formato tipico`:
* `varianti osservate`:
* `spazi / slash / trattini`:
* `trasposizioni frequenti`:
* `similarità ammessa`: `alta / media / bassa`
* `match esatto obbligatorio`: `si/no`

---

## 10. Posizione E Contesto Per ML

Per questo template descrivere in modo globale:

* `blocchi visivi principali del documento`:
* `aree stabili tra PDF diversi`:
* `aree instabili tra PDF diversi`:
* `zone dove conviene fare crop mirati`:
* `zone dove serve più contesto`:
* `zone rumorose o fuorvianti`:
* `necessità di pagina intera`: `si/no`
* `necessità di crop riga`: `si/no`
* `necessità di crop tabella`: `si/no`
* `necessità di bbox`: `alta / media / bassa`

### 10.1 Evidenze da conservare per ML futuro

* `campo -> tipo evidenza utile`
* `campo -> livello di contesto necessario`
* `campo -> relazioni spaziali importanti`

---

## 11. Casi Deboli O Da Fermare

Quando il sistema NON deve forzare un valore o un match:

* `...`
* `...`

Per ogni caso scrivere:

* `segnale di debolezza`
* `cosa non assumere`
* `azione corretta`: `lasciare vuoto / proporre / chiedere verifica utente`

---

## 12. Punti Forti Osservati

* `...`
* `...`

## 13. Punti Deboli Osservati

* `...`
* `...`

## 14. Note Per Il Codice Futuro

Traduzione minima in regole implementabili:

* `regola 1`:
* `regola 2`:
* `regola 3`:

---

## 15. Placeholder Da Validare Insieme

Qui vanno i punti ancora non chiusi prima del codice.

* `...`
* `...`
