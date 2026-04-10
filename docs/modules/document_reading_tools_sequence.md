# Document Reading Tools Sequence

## Scopo

Questo file consolida:

* gli strumenti di lettura testati davvero sui DDT scansione
* la sequenza consigliata di utilizzo
* i rischi osservati
* i candidati successivi da provare

Questo file non sostituisce i knowledge file per fornitore/template.

Serve come regola trasversale del reader.

---

## 1. Vincolo guida

La lettura corretta del documento, orientata il piu' possibile al **100% di precisione**, e' la parte piu' vitale dell'app.

Quindi:

* non va scelto il tool piu' comodo in astratto
* va scelto il tool migliore **per campo e per template**
* i tool vanno misurati su casi reali
* prima di OpenAI/ChatGPT vanno provati seriamente i tool locali forti

---

## 2. Casi reali usati per il confronto

Campioni testati:

* `Aluminium Bz/176.pdf`
  * pagina 1 `Delivery note`
  * pagina 2 `PACKING LIST`
* `Leichtmetall/80008518.pdf`
  * pagina 1 documento principale
  * pagina 2 dettaglio pesi/lotti

Punti difficili usati nel confronto:

* numeri DDT
* ordine AB
* ordine cliente
* codici alfanumerici materiale
* articolo interno `14BT...`
* `CAST / COD. COLATA`
* `Cert. N°`
* peso con virgola europea
* lega/stato fisico
* stringhe tecniche tipo `Inspection certificate EN 10204 3.1`

---

## 3. Strumenti testati

### 3.1 Testati davvero

* `pdftotext`
* `PyMuPDF text`
* `pdftoppm + Tesseract`
* `pdfimages + Tesseract`
* pre-processing locale:
  * grayscale
  * otsu
  * deskew
* `OCRmyPDF`
* `RapidOCR`

### 3.2 Valutati ma non ancora testati

* `PaddleOCR`
* `PP-StructureV3`
* `docTR`
* `EasyOCR`
* `keras-ocr`
* `mutool` come supporto render/extract, non come OCR principale

---

## 4. Risultato consolidato

### 4.1 Baseline vincente attuale

La baseline piu' robusta oggi e':

1. `pdf_text` come probe iniziale
2. se il testo e' povero: render pagina con `pdftoppm -r 300`
3. OCR con `Tesseract`
   * `psm 6` per pagina principale
   * `psm 4` per packing list/tabella
4. crop del blocco utile prima del parsing campo

Questa e' oggi la sequenza migliore osservata sui campioni reali.

### 4.2 Strumenti deboli sui DDT scansione testati

* `pdftotext`: troppo debole sui DDT scansione
* `PyMuPDF text`: troppo debole sui DDT scansione
* `pdfimages + Tesseract`: non affidabile come base sui campioni provati

### 4.3 RapidOCR

`RapidOCR` e' promettente come candidato leggero, ma nei campioni testati oggi e' sotto la baseline:

* buono su alcuni numeri semplici
* piu' debole su:
  * codici
  * ordini
  * stringhe tecniche
  * righe tabellari piu' dense

Conclusione:

* non e' il primo candidato da mettere in pipeline base
* resta interessante come prova futura o fallback specializzato

### 4.4 OCRmyPDF

`OCRmyPDF` e' utile, ma non va applicato in modo rigido su tutti i template.

Osservazione chiave:

* `OCRmyPDF default` va bene su template tipo `Aluminium Bozen`
* `OCRmyPDF rotate+deskew` aiuta di piu' template tipo `Leichtmetall`
* lo stesso pre-processing puo' aiutare un template e peggiorarne un altro

Conclusione:

* `OCRmyPDF` va usato come strato opzionale **template-aware**
* non come step universale e cieco per tutti i DDT

---

## 5. Sequenza consigliata oggi

### 5.1 Sequenza standard

1. `pdf_text` probe rapido
2. classificazione iniziale:
   * testo digitale utile
   * scansione
3. se scansione:
   * render `300 dpi`
4. classificazione pagina:
   * pagina principale
   * packing list / tabella
   * pagina rumorosa / comunicazione
5. OCR:
   * `Tesseract psm 6` per pagina principale
   * `Tesseract psm 4` per packing list/tabella
6. crop del blocco utile
7. parsing campo con regole per template

### 5.2 Sequenza fallback

Usare solo se il caso e' debole:

1. crop piu' stretto
2. OCR ripetuto con lingua diversa o piu' lingue
3. `OCRmyPDF` mirato al template
4. controllo utente
5. solo dopo valutare OpenAI/ChatGPT

---

## 6. Regole di pre-processing

### 6.1 Cosa fare di default

* `300 dpi`
* niente deskew globale come default
* niente binarizzazione aggressiva come default
* usare il crop del blocco utile come miglioramento principale

### 6.2 Cosa NON fare sempre

* `400 dpi` non porta vantaggi stabili osservati
* `deskew` globale non va fatto sempre
* `rotate+deskew` non va fatto sempre
* `binarizzazione forte` non va fatta sempre

### 6.3 Rotazione

La rotazione va applicata solo se un controllo serio di orientazione dice che serve.

Non basta una stima geometrica grezza della pagina intera.

---

## 7. Rischi principali

### 7.1 Falso senso di precisione

Un OCR puo' sembrare buono ma sbagliare proprio i campi critici:

* codice
* colata
* ordine
* peso

### 7.2 Perdita della struttura documento

OCR puro legge testo ma non sempre capisce:

* quale riga e' quella giusta
* quale gruppo packing list e' quello corretto
* quali campi appartengono insieme

### 7.3 Pre-processing che rovina

Rotate, deskew, cleanup o threshold possono:

* cancellare dettagli
* spezzare cifre
* peggiorare codici piccoli

### 7.4 Benchmark sbagliato

Il benchmark non va fatto solo per tool.

Va fatto anche per:

* campo
* template
* pagina
* blocco

---

## 8. Candidati successivi da testare

Ordine consigliato:

1. consolidare `OCRmyPDF` come pre-processing opzionale per template
2. tenere `Tesseract + pdftoppm` come baseline
3. valutare `PaddleOCR`
4. valutare `PP-StructureV3` per layout/tabelle
5. valutare `docTR`

`RapidOCR` resta disponibile ma oggi non sale in priorita' rispetto a questi.

---

## 9. OpenAI / ChatGPT

OpenAI/ChatGPT non e' escluso.

Ma viene dopo:

* probe locale
* OCR locale forte
* crop mirati
* parsing e fallback locali

Prima di qualunque uso OpenAI/ChatGPT va sempre dichiarato:

* obiettivo
* modello scelto
* stima costi
* test singolo o batch

---

## 10. Placeholder da validare insieme

* definire per quali template conviene davvero usare `OCRmyPDF`
* decidere quando introdurre `PaddleOCR / PP-StructureV3`
* decidere se il benchmark successivo va fatto per:
  * DDT
  * certificati
  * oppure entrambi in parallelo
