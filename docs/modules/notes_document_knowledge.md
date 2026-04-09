# Notes Document Knowledge

## ⚠️ Stato del documento

Questo file e' un primo riferimento dedicato alle **note documentali**.

Non definisce ancora il motore finale delle note.

Serve per:

* fissare i campi note minimi da prevedere
* chiarire quali note possono essere popolate in automatico
* usare i certificati finali prodotto in `esempi_locali/6-esempi` come riferimento del formato finale atteso
* restare coerenti con:
  * `document_reader_strategy_first_draft.md`
  * `ddt_certificates_data_acquisition.md`
  * `certificates_supplier_document_knowledge.md`

---

## 1. Scopo

Nel sistema futuro le note devono essere trattate come un blocco autonomo del workflow documentale.

Per il primo pilota:

* il blocco `Note` entra nel workflow
* puo' essere letto, corretto e validato
* il contenuto puo' essere valorizzato, vuoto o `null`

Questo file definisce il livello minimo di conoscenza necessario per non lasciare le note come testo libero indistinto.

---

## 2. Origine delle note

Le note finali che compariranno nel certificato prodotto devono derivare, quando possibile, da evidenze trovate nel **certificato materiale del fornitore**.

Regola:

* le note standard vanno popolate in automatico solo se esiste evidenza documentale sufficiente nel certificato materiale del fornitore
* la nota libera utente NON va popolata automaticamente

I certificati finali prodotto presenti in `esempi_locali/6-esempi/CERTIFICATI_F3` sono usati qui come riferimento per capire:

* quali note finali servono
* quali formulazioni finali ricorrono

I certificati fornitore presenti in `esempi_locali/3-certificati` servono invece per capire:

* come le stesse evidenze compaiono davvero a monte
* con quali varianti linguistiche o di layout
* se l'evidenza compare nel blocco `Notes` oppure in altri blocchi del certificato

---

## 3. Campi note minimi

Per ora i campi note standard da prevedere sono questi:

### 3.1 `nota_us_control_classe`

Valori ammessi iniziali:

* `A`
* `B`
* `null`

Questa nota rappresenta la presenza di controllo U.S. / ASTM / AMS con classe finale `A` o `B`.

### 3.2 `nota_rohs`

Valori ammessi iniziali:

* `true`
* `false`
* `null`

Questa nota rappresenta la presenza di dichiarazioni tipo `RoHS`, `RoHS II` o formulazioni equivalenti.

### 3.3 `nota_radioactive_free`

Valori ammessi iniziali:

* `true`
* `false`
* `null`

Questa nota rappresenta la presenza di dichiarazioni tipo:

* materiale esente da contaminazione radioattiva
* free from radioactive contamination
* formulazioni equivalenti in altre lingue

### 3.4 `nota_libera_utente`

Campo testuale libero.

Regola:

* non va mai popolato automaticamente
* serve solo per integrazione o chiarimento manuale dell'utente

---

## 4. Forme finali osservate nei certificati prodotto

Dall'analisi dei certificati finali prodotto in `esempi_locali/6-esempi/CERTIFICATI_F3` emergono tre frasi standard.

### 4.1 Nota U.S. control

Forma finale ricorrente:

* `U.S. control ... class A`
* `U.S. control ... class B`

Varianti reali osservate:

* `U.S. control acc. to ASTM B 594, defect det. min. Ø1,98 mm ((class A)).`
* `U.S. control acc. to ASTM B 594, defect det. max. Ø1,98 mm ((class A)).`
* `U.S. control acc. to ASTM B 594 or SAE AMS STD 2154 class A`
* `U.S. control according to ASTM 594 or SAE AMS STD 2154 class B`
* `U.S. control according to ASTM B594 or SAE AMS STD 2154 class B`
* `U.S. control acc. to ASTM 594 or SAE AMS STD 2154 class B`

Interpretazione minima:

* se il certificato materiale contiene evidenze coerenti con `ASTM` o `AMS` e una `class A` o `class B`
* allora il sistema puo' valorizzare `nota_us_control_classe`

### 4.2 Nota RoHS

Forma finale ricorrente:

* `use of certain hazardous substances (ROHS II) in electrical and electronic equipment`

Interpretazione minima:

* se il certificato materiale contiene forme tipo `ROHS`, `RoHS`, `ROHS II`, `RoHS II`
* il sistema puo' valorizzare `nota_rohs`

### 4.3 Nota radioactive free

Forma finale ricorrente:

* `Material free from radioactive contamination`

Interpretazione minima:

* se il certificato materiale contiene forme tipo:
  * `free from radioactive contamination`
  * `free of radioactive contaminants`
  * varianti equivalenti anche in altre lingue
* il sistema puo' valorizzare `nota_radioactive_free`

---

## 5. Regole di popolamento automatico

### 5.1 Regola generale

Una nota standard viene popolata automaticamente solo se:

* esiste una evidenza nel certificato materiale del fornitore
* l'evidenza e' sufficientemente robusta
* il blocco `Note` resta comunque validabile dall'utente

### 5.2 Regola di prudenza

Il sistema NON deve:

* inventare note
* assumere note solo per analogia tra fornitori
* riempire `nota_libera_utente`

### 5.3 Regola di workflow

Le note standard:

* possono essere proposte automaticamente
* devono poter essere corrette
* devono poter essere confermate

La nota libera:

* puo' essere inserita solo dall'utente

---

## 6. Evidenze osservate nei certificati fornitore (`3-certificati`)

Le note standard NON vanno riconosciute solo cercando la frase finale del certificato prodotto.

Devono essere riconosciute partendo dalle evidenze reali presenti nei certificati materiale del fornitore.

### 6.1 Evidenze per `nota_us_control_classe = A`

Esempi osservati in `Leichtmetall A`:

* `U.S. control acc. to ASTM B 594-06: defect det. min. Ø1,98 mm ((class A)).`
* `U.S. control acc. to ASTM B 594-06, defect det. min. Ø1,98 mm ((class A)).`
* `U.S. control acc. to ASTM 594 or SAE AMS STD 2154 class A`

Osservazioni:

* la classe `A` puo' comparire in forma storica piu' lunga con `defect det. min. Ø1,98 mm`
* puo' comparire anche in forma piu' compatta con `ASTM 594 or SAE AMS STD 2154 class A`
* spesso compare nel blocco `Notes`, ma la logica di riconoscimento deve basarsi soprattutto su:
  * presenza `ASTM`
  * presenza `AMS`
  * presenza `class A`

### 6.2 Evidenze per `nota_us_control_classe = B`

Esempi osservati in `Aluminium Bz - Sapa Bz`:

* `Controllo US su Billetta secondo AMS STD 2154 Classe B su impianto Bonetti`

Esempi osservati in altri certificati e forme vicine:

* `U.S. control according to ASTM 594 or SAE AMS STD 2154 class B`
* `U.S. control according to ASTM B594 or SAE AMS STD 2154 class B`
* `U.S. control acc. to ASTM 594 or SAE AMS STD 2154 class B`

Osservazioni:

* la classe `B` puo' comparire in italiano o in inglese
* puo' comparire come `Classe B` o `class B`
* la presenza di `AMS STD 2154` e della classe e' gia' una evidenza molto forte

### 6.3 Evidenze per `nota_rohs`

Esempi osservati in `Aluminium Bz - Sapa Bz`:

* `Materiale conforme alla direttiva RoHS-2`
* `MATERIALE CONFORME ALLA DIR. RoHS-2`

Osservazioni:

* la forma puo' essere piena o abbreviata
* il testo puo' essere in maiuscolo o misto
* in alcuni certificati finali prodotto la forma finale compare come:
  * `use of certain hazardous substances (ROHS II) in electrical and electronic equipment`
* quindi il riconoscimento deve essere tollerante almeno verso:
  * `RoHS`
  * `RoHS-2`
  * `ROHS II`
  * `hazardous substances`

### 6.4 Evidenze per `nota_radioactive_free`

Esempi osservati nei certificati fornitore:

* `Materiale privo di contaminazione radioattiva`
* `Material free from radioactive contamination`
* `Material frei von radioaktiver Kontamination`
* `Matériel sans contamination radioactive`

Osservazioni:

* l'evidenza puo' comparire in piu' lingue nella stessa riga o nello stesso blocco
* il riconoscimento non deve dipendere solo dalla forma inglese
* la presenza di una qualunque di queste forme e' gia' una evidenza utile

### 6.5 Regola di posizione

Le evidenze delle note:

* possono comparire nel blocco `Notes`
* ma possono anche comparire in sezioni descrittive, righe di conformita', blocchi generali o note finali del certificato fornitore

Quindi:

* il reader non deve limitarsi a cercare solo dopo l'etichetta `Notes`
* deve poter leggere anche blocchi vicini di testo libero o conformita'

---

## 7. Varianti e normalizzazione

Il riconoscimento delle note deve essere tollerante rispetto a:

* maiuscole/minuscole
* presenza o assenza di punti e spazi
* `ASTM 594` vs `ASTM B594` vs `ASTM B 594`
* `AMS STD 2154` con piccole varianti di scrittura
* `ROHS` vs `RoHS`
* differenze linguistiche su radioactive contamination

Regola:

* la variabilita' della scrittura deve essere gestita nel riconoscimento
* ma l'output finale deve essere standardizzato nei campi minimi del punto 3

---

## 8. Rapporto con gli altri moduli

Questo file si lega in particolare a:

* `certificates_supplier_document_knowledge.md`
  * per il riconoscimento nei certificati materiale del fornitore
* `document_reader_strategy_first_draft.md`
  * per il blocco `Note` del reader e della UI quality
* `ddt_certificates_data_acquisition.md`
  * per il salvataggio dei dati documentali acquisiti

Nota:

* questo file NON definisce ancora il motore finale di interpretazione avanzata delle note
* definisce solo il primo livello utile per il pilota

---

## 9. Placeholder futuri

Da sviluppare in seguito:

* dizionario varianti multilingua
* regole per altri tipi di note ricorrenti
* motore di standardizzazione note
* eventuale classificazione automatica note con supporto AI
* logica finale di composizione delle note nel certificato prodotto
