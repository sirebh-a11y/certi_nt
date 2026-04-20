# DDT Supplier Template Analysis - Leichtmetall

## Scopo

Analisi del template DDT osservato per `Leichtmetall Aluminium Giesserei Hannover GmbH` sui PDF reali presenti in:

```plaintext
esempi_locali/4-ddt/Leichtmetall
```

Questo file serve a fissare:

* struttura reale del template
* campi originali usabili nel runtime futuro
* regole di ricerca e match validate su piu' DDT e piu' certificati

---

## Vincolo Guida Del Progetto

La lettura documentale corretta, orientata il piu' possibile al **100% di precisione**, e' la parte piu' vitale dell'app.

Per questo template:

* il DDT e' scansione
* `pdf_text` non basta
* la lettura migliore osservata e' OCR locale da render pagina
* le annotazioni manuali storiche non vanno usate come base del runtime futuro

---

## 1. Identificazione

* `fornitore_master`: `Leichtmetall Aluminium Giesserei Hannover GmbH`
* `alias_osservati`: `Leichtmetall`, `EGA`, `Leichtmetall A`
* `template_id`: `leichtmetall_delivery_note_packing_style_v1`
* `stato_analisi`: `bozza`

---

## 2. Dataset Letto

* `cartella`: `esempi_locali/4-ddt/Leichtmetall`
* `pdf_letti`: `80008518.pdf`, `80008519.pdf`, `80008535.pdf`, `80008577.pdf`, `80008578.pdf`, `80008657.pdf`
* `pagine_totali_lette`: `12`
* `documenti_rappresentativi`: `80008518.pdf`, `80008519.pdf`, `80008577.pdf`, `80008578.pdf`

Match forti gia' verificati:

* `80008518.pdf` -> `CdQ_94683_6082_Ø295.pdf`
* `80008519.pdf` -> `CdQ_94668_6082_Ø240.pdf`
* `80008577.pdf` -> `CdQ_94775_7075_Ø165.pdf`
* `80008578.pdf` -> `CdQ_94775_7075_Ø144.pdf`

Casi ancora da confermare meglio:

* `80008657.pdf`

Caso strutturale importante gia' verificato:

* `80008535.pdf`
  * pagina 1: materiale unico apparente `EN AW-6082`, `Diameter 228,00 mm`, `Quantity 17,225 KG`, `Purchase Number 19.2 + 4 + 5`
  * pagina 2: il DDT si spezza in due gruppi batch reali
    * batch `94668` con peso netto totale `5,014 KG`
    * batch `94752` con peso netto totale `12,211 KG`
  * conseguenza runtime:
    * un solo DDT puo' richiedere piu' certificati distinti
    * il totale pagina 1 non basta per chiudere il match

Nota metodologica:

* i nomi file sopra aiutano solo l'analisi del dataset storico
* il match runtime futuro non deve usare il nome file
* il match runtime deve usare solo i campi letti dal DDT e dal certificato

---

## 3. Regola Chiave Del Template

Descrizione breve del template:

* documento bilingue/inglese-tecnico
* pagina 1 con header, ordine, alloy, diameter, length, classi UT, certificato 3.1, quantity
* pagina 2 con dettaglio colli/pesi e codici batch/UIA

Il template si riconosce da:

* header `LEICHTMETALL`
* presenza di `Order Confirmation`
* `Customer Number`
* `Purchase Number`
* blocco `Configuration: Characteristic Value`
* righe `Inspection Certificate 3.1` / `according to EN 10204`
* pagina 2 con:
  * `Beleg`
  * `Datum`
  * righe colli/pesi

---

## 4. Guardrail Runtime

### 4.1 Campi Usabili Nel Runtime Futuro

* `Delivery Note` / `Beleg`
* data documento
* `Order Confirmation`
* `Purchase Number`
* alloy
* diameter
* length
* quantity
* `Inspection Certificate 3.1`
* classi ASTM / Class A
* dettagli pagina 2 sui colli/pesi

### 4.2 Contesto Storico Da NON Usare Nel Runtime

* `campo/annotazione`: `CdQ` scritto a mano
  * `utile per capire il processo storico`: `si`
  * `usabile nel runtime futuro`: `no`
  * `nota`: aiuta a capire alcuni match del dataset storico, ma non va usato come assunzione per DDT futuri
* `campo/annotazione`: `colata/batch` scritto a mano
  * `utile per capire il processo storico`: `si`
  * `usabile nel runtime futuro`: `no`
  * `nota`: runtime deve basarsi sui campi originali stampati e sul legame col certificato

---

## 5. Struttura Documento

### 5.1 Pagine E Blocchi

* pagina 1:
  * header fornitore
  * blocco destinatario/cliente
  * `Delivery Note` o layout equivalente
  * `Order Confirmation`
  * `Purchase Number`
  * `Configuration: Characteristic Value`
  * dati di prodotto
  * certificato 3.1 / ASTM / classi
* pagina 2:
  * `Beleg`
  * `Datum`
  * elenco colli/pesi/batch
  * talvolta note aggiuntive export control / tensile strength

### 5.2 Dove Cercare Prima

Ordine reale di lettura:

1. pagina 1 per alloy, diameter, order, quantity, classi
2. pagina 2 per batch/cdq e dettaglio colli/pesi
3. uso congiunto DDT + certificato per chiudere il match

### 5.3 Dove NON Cercare O Cosa Non Confondere

* footer bancario/aziendale
* testo legale export control
* note generali sui terms and conditions
* annotazioni manuali

---

## 6. Regola Di Riga Acquisition

* `unita materiale reale`: gruppo materiale del DDT, non il singolo collo
* `criterio di aggregazione`: `per batch/cdq` sul documento, con somma pesi colli coerenti
* `uso del peso`: `somma / conferma da pagina 2`
* `uso del dettaglio pagina 2`: `si`
* `regola pratica`: leggere prima alloy, diameter e quantity pagina 1; usare pagina 2 per dettaglio colli e chiusura batch/cdq

Se il peso o la riga vanno ricostruiti:

* i colli della pagina 2 vanno sommati solo se coerenti con lo stesso materiale reale
* il gruppo corretto si conferma con alloy, diameter, `Purchase Number`/ordine e certificato collegato
* se il gruppo non e' chiaro, lasciare il caso all'utente
* se pagina 2 mostra piu' batch distinti, il DDT va trattato come caso multi-certificato

---

## 7. Campi Da Ricercare

### 7.1 Campo: `numero_ddt`

* `obbligatorio nel runtime`: `si`
* `usato per match con certificato`: `no`
* `pagina/blocco principale`: pagina 1 o pagina 2
* `posizione precisa osservata`: `Delivery Note 80008577`, `Beleg 80008518`
* `ancore testuali`: `Delivery Note`, `Beleg`
* `tipo valore`: `documentale puro`
* `strumento di lettura migliore`: `ocr / regex`
* `contesto minimo necessario`: `blocco`

### 7.2 Campo: `data_documento`

* `obbligatorio nel runtime`: `si`
* `usato per match con certificato`: `debole`
* `pagina/blocco principale`: pagina 1 o pagina 2
* `posizione precisa osservata`: riga `Date ...` o `Datum ...`
* `ancore testuali`: `Date`, `Datum`
* `tipo valore`: `documentale puro`
* `strumento di lettura migliore`: `ocr / regex`
* `contesto minimo necessario`: `blocco`

### 7.3 Campo: `order_confirmation`

* `obbligatorio nel runtime`: `si`
* `usato per match con certificato`: `medio`
* `pagina/blocco principale`: pagina 1
* `posizione precisa osservata`: `Order Confirmation 2003244`, `2003243`, `2003225`
* `ancore testuali`: `Order Confirmation`
* `tipo valore`: `documentale puro`
* `strumento di lettura migliore`: `ocr / regex`
* `contesto minimo necessario`: `blocco`

### 7.4 Campo: `purchase_number`

* `obbligatorio nel runtime`: `si`
* `usato per match con certificato`: `forte`
* `pagina/blocco principale`: pagina 1
* `posizione precisa osservata`: `Purchase Number 19.2+4+5`, `19.1+3`
* `ancore testuali`: `Purchase Number`
* `tipo valore`: `documentale puro`
* `strumento di lettura migliore`: `ocr / regex`
* `contesto minimo necessario`: `blocco`
* `nota runtime`: campo molto utile per confermare il certificato corretto

### 7.5 Campo: `lega`

* `obbligatorio nel runtime`: `si`
* `usato per match con certificato`: `forte`
* `pagina/blocco principale`: pagina 1
* `posizione precisa osservata`: `Alloy EN AW-6082`, `Alloy EN AW-7175`, `Alloy EN AW-2618A`
* `ancore testuali`: `Alloy`
* `tipo valore`: `documentale puro`
* `strumento di lettura migliore`: `ocr`
* `contesto minimo necessario`: `riga`

### 7.6 Campo: `diametro`

* `obbligatorio nel runtime`: `si`
* `usato per match con certificato`: `forte`
* `pagina/blocco principale`: pagina 1
* `posizione precisa osservata`: `Diameter 295,00 mm`, `240,00 mm`, `165,00 mm`, `144,00 mm`
* `ancore testuali`: `Diameter`
* `tipo valore`: `numerico standardizzato`
* `unita implicita`: `mm`
* `strumento di lettura migliore`: `ocr`
* `contesto minimo necessario`: `riga`

### 7.7 Campo: `lunghezza`

* `obbligatorio nel runtime`: `si`
* `usato per match con certificato`: `medio`
* `pagina/blocco principale`: pagina 1
* `posizione precisa osservata`: `Length 1.500,00 mm`, `1.400,00 mm`, `1.450,00 mm`
* `ancore testuali`: `Length`
* `tipo valore`: `numerico standardizzato`
* `unita implicita`: `mm`
* `strumento di lettura migliore`: `ocr`
* `contesto minimo necessario`: `riga`

### 7.8 Campo: `peso`

* `obbligatorio nel runtime`: `si`
* `usato per match con certificato`: `forte`
* `pagina/blocco principale`: pagina 1 e pagina 2
* `posizione precisa osservata`: `Quantity: 6,730 KG`, `3,026 KG`, ecc.
* `ancore testuali`: `Quantity`
* `tipo valore`: `numerico standardizzato`
* `unita implicita`: `kg`
* `strumento di lettura migliore`: `ocr`
* `contesto minimo necessario`: `riga`
* `nota runtime`: va confermato o ricostruito con la pagina 2 quando necessario

### 7.9 Campo: `classe_ut`

* `obbligatorio nel runtime`: `no`
* `usato per match con certificato`: `medio`
* `pagina/blocco principale`: pagina 1
* `posizione precisa osservata`: `Ultrasonic inspection Class A`
* `ancore testuali`: `Class A`, `ASTM B 594`
* `tipo valore`: `documentale puro`
* `strumento di lettura migliore`: `ocr`
* `contesto minimo necessario`: `blocco`

### 7.10 Campo: `batch_cdq_runtime`

* `obbligatorio nel runtime`: `si`
* `usato per match con certificato`: `forte`
* `pagina/blocco principale`: pagina 2
* `posizione precisa osservata`: dettaglio colli/pesi/batch della seconda pagina
* `ancore testuali`: nessuna unica forte; va letto dal dettaglio strutturato della pagina 2 e confermato col certificato
* `tipo valore`: `documentale puro`
* `strumento di lettura migliore`: `ocr / tabellare`
* `contesto minimo necessario`: `tabella`
* `nota runtime`: non usare il valore scritto a mano; usare pagina 2 + certificato

---

## 8. Match DDT -> Certificato

### 8.1 Campi Forti Osservati

* batch/cdq
* lega
* diametro
* `Purchase Number`
* peso/quantity

### 8.2 Campi Medi

* `Order Confirmation`
* classe ASTM / Class A
* lunghezza

### 8.3 Regola Pratica Di Match

1. leggere alloy, diameter e purchase number dal DDT
2. recuperare batch/cdq dalla pagina 2 o dal dettaglio coerente
3. cercare il certificato dello stesso fornitore coerente con batch/cdq + alloy + diameter
4. confermare con peso e `PO-No.`

### 8.4 Match confermati

* `80008518.pdf` -> `CdQ_94683_6082_Ø295.pdf`
  * `purchase number`: `19.2+4+5`
  * `alloy`: `6082`
  * `diameter`: `295`
  * `weight`: `6730`
* `80008519.pdf` -> `CdQ_94668_6082_Ø240.pdf`
  * `purchase number`: `19.2+4+5`
  * `alloy`: `6082`
  * `diameter`: `240`
* `80008577.pdf` -> `CdQ_94775_7075_Ø165.pdf`
  * `purchase number`: `19.1+3`
  * `alloy`: `7175`
  * `diameter`: `165`
  * `weight`: `6037`
* `80008578.pdf` -> `CdQ_94775_7075_Ø144.pdf`
  * `purchase number`: `19.1+3`
  * `alloy`: `7175`
  * `diameter`: `144`
  * `weight`: `3026`

### 8.5 Casi Da Validare

* `80008535.pdf`: possibile famiglia `94668 / 6082 / Ø228`, ma da confermare meglio
* `80008657.pdf`: possibile famiglia `2618A / Ø220`, ma da confermare meglio

---

## 9. Similarità E Varianti Codici

* `nome codice`: `purchase number`
  * `formato tipico`: `19.2+4+5`, `19.1+3`
  * `similarità ammessa`: `bassa`
  * `match esatto obbligatorio`: `si`
* `nome codice`: `batch / cdq`
  * `formato tipico`: `94683`, `94668`, `94775`
  * `similarità ammessa`: `bassa`
  * `match esatto obbligatorio`: `si`
* `nome codice`: `diameter`
  * `formato tipico`: `295`, `240`, `165`, `144`
  * `similarità ammessa`: `bassa`
  * `match esatto obbligatorio`: `si`

---

## 10. Posizione E Contesto Per ML

* `blocchi visivi principali`: header, blocco configuration, dettagli certificazione, seconda pagina tabellare
* `aree stabili`: header pagina 1, blocco `Configuration: Characteristic Value`, righe `Inspection Certificate 3.1`
* `aree instabili`: tabella pagina 2, note export control
* `zone dove conviene fare crop mirati`:
  * blocco ordine/purchase number
  * blocco alloy/diameter/length
  * blocco classi ASTM
  * tabella pagina 2
* `necessità di pagina intera`: `si`
* `necessità di crop riga`: `si`
* `necessità di crop tabella`: `si`
* `necessità di bbox`: `alta`

---

## 11. Casi Deboli O Da Fermare

* batch non leggibile nella pagina 2
* piu' certificati possibili con stesso alloy + diameter
* mismatch tra purchase number DDT e PO-No. certificato
* weight non coerente
* totale pagina 1 compatibile con piu' gruppi batch diversi in pagina 2

Azione corretta:

* non inventare il match
* proporre solo se ci sono abbastanza campi forti
* chiedere verifica utente nei casi dubbi

---

## 12. Punti Forti Osservati

* template DDT abbastanza stabile
* `purchase number` molto utile
* alloy + diameter molto forti
* pagina 2 importante per chiudere batch/pesi

## 13. Punti Deboli Osservati

* pagina 2 OCR sporca
* annotazioni manuali possono trarre in inganno
* alcuni casi richiedono confronto stretto col certificato per chiudere il batch

## 14. Note Per Il Codice Futuro

* non usare le scritte a mano come campo runtime
* leggere pagina 1 e pagina 2 insieme
* usare il certificato per chiudere il batch/cdq corretto
* trattare `purchase number` come campo forte di famiglia materiale
* non assumere che il totale di pagina 1 corrisponda a un solo certificato

---

## 15. Placeholder Da Validare Insieme

* confermare meglio `80008535.pdf`
* confermare meglio `80008657.pdf`
* decidere se per `Leichtmetall` il criterio di riga va formalizzato come `per batch/cdq + materiale`, non solo per voce pagina 1
