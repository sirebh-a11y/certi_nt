# Certificate Supplier Template Analysis - Aluminium Bozen

## Scopo

Analisi del template certificato osservato per `Aluminium Bozen S.r.l.` sui certificati reali che matchano i DDT gia' studiati.

Dataset di riferimento:

```plaintext
esempi_locali/3-certificati/Aluminium Bz - Sapa Bz
```

Questo file serve a fissare:

* struttura reale del template certificato
* campi originali usabili nel runtime futuro
* struttura vera delle tabelle chimiche e meccaniche
* regole di match con i DDT `Aluminium Bozen`

---

## Vincolo Guida Del Progetto

La lettura documentale corretta, orientata il piu' possibile al **100% di precisione**, e' la parte piu' vitale dell'app.

Per questo template:

* il certificato e' leggibile bene con OCR locale da render pagina
* la pagina 1 contiene quasi tutto il contenuto tecnico utile
* la pagina 2 e' secondaria, ma va letta per confermare eventuali note/origine
* non vanno inventati valori da righe `min/max`

---

## 1. Identificazione

* `fornitore_master`: `Aluminium Bozen S.r.l.`
* `alias_osservati`: `Aluminium Bz`, `aluminium bozen`
* `template_id`: `aluminium_bozen_certificate_multilingual_v1`
* `stato_analisi`: `bozza`

---

## 2. Dataset Letto

* `cartella`: `esempi_locali/3-certificati/Aluminium Bz - Sapa Bz`
* `pdf_letti`: `CQF_151238_608298_2026.pdf`, `CQF_151323_7075127_2026.pdf`, `CQF_151675_6082130_2026.pdf`
* `pagine_totali_lette`: `6`
* `documenti_rappresentativi`: gli stessi 3 file

Match gia' verificati con i DDT:

* `176.pdf` -> `CQF_151238_608298_2026.pdf`
* `261.pdf` -> `CQF_151675_6082130_2026.pdf`
* `419.pdf` -> `CQF_151323_7075127_2026.pdf`

---

## 3. Regola Chiave Del Template

Descrizione breve del template:

* certificato multilingua
* pagina 1 con struttura tecnica completa
* pagina 2 di conformita'/origine, con riepilogo header e dati prodotto

Il template si riconosce da:

* header `Statement of Compliance / Dichiarazione di Conformita`
* blocco documento `Inspection Certificate EN 10204 3.1`
* intestazione compatta con:
  * `CERT.NO.`
  * `A.B. ORDER No.`
  * `ARTICLE`
  * `Customer's Order No.`
  * `NET WEIGHT`
  * `CUSTOMER'S SECTION DESC.`
  * `ALLOY & Phys.State`
* tabella chimica orizzontale con riga misurata + righe `Min.` e `Max.`
* tabella proprieta' meccaniche sotto la chimica
* note in fondo alla pagina 1

---

## 4. Guardrail Runtime

### 4.1 Campi Usabili Nel Runtime Futuro

* `CERT.NO.`
* data certificato
* `A.B. ORDER No.`
* `No. DE COMMANDE AB.`
* `ARTICLE`
* `Customer's Order No.`
* `NET WEIGHT`
* `CUSTOMER'S SECTION DESC.`
* `ALLOY & Phys.State`
* `CAST BATCH Nr`
* riga misurata della chimica
* righe `Min.` e `Max.` come limiti, non come misurato
* tabella proprieta' meccaniche
* note finali del certificato

### 4.2 Contesto Da NON Usare Come Dato Finale

* righe `Min.` e `Max.` della chimica come se fossero valori misurati
* righe `NORMA / LIMIT / NORME` della tabella meccanica come se fossero prove reali
* testo legale multilingua sulle norme come se fosse nota materiale di runtime
* pagina 2 come sostituto della pagina 1 se la pagina 1 e' leggibile

---

## 5. Struttura Documento

### 5.1 Pagine E Blocchi

* pagina 1:
  * header fornitore e statement
  * blocco identificazione certificato
  * blocco prodotto
  * tabella chimica
  * tabella proprieta' meccaniche
  * note certificate
  * firma/quality manager
* pagina 2:
  * ripetizione sintetica dell'header tecnico
  * informazioni su origine del primary aluminium
  * firma/quality manager

### 5.2 Dove Cercare Prima

Ordine reale di lettura:

1. header tecnico di pagina 1
2. tabella chimica pagina 1
3. tabella meccanica pagina 1
4. note fondo pagina 1
5. pagina 2 solo come supporto o conferma

### 5.3 Dove NON Cercare O Cosa Non Confondere

* testo legale multilingua sulle norme
* blocchi di traduzione ripetuti
* pagina 2 come sorgente primaria dei dati tecnici
* riga `EN 10204 3.1`: tipo certificato, non numero certificato

---

## 6. Regola Di Match Con DDT

### 6.1 Campi Forti Osservati

* `CERT.NO.` <-> `Cert. N°` nel packing list DDT
* `ARTICLE` <-> articolo interno `14BT...`
* `CUSTOMER'S SECTION DESC.` <-> codice cliente/materiale + descrizione
* `ALLOY & Phys.State` <-> lega/stato del DDT
* `CAST BATCH Nr` <-> `CAST Nr.` / `COD. COLATA` del DDT

### 6.2 Campi Medi

* `A.B. ORDER No.`
* `Customer's Order No.`
* `NET WEIGHT`

### 6.3 Regola Pratica Di Match

1. cercare prima `CERT.NO.` dal packing list DDT
2. confermare con `ARTICLE`, codice cliente/materiale, lega/stato e colata
3. usare ordine cliente rimodulato e peso netto come controllo aggiuntivo

### 6.4 Rimodulazione Ordine Cliente

Osservazione confermata:

* nel DDT `Vs. Odv` puo' apparire come `1 - 2026-01-07`
* nel certificato `Customer's Order No.` appare come `2026-01-07 1`

Quindi:

* stessa informazione
* token invertiti
* va normalizzata, non trattata come mismatch

---

## 7. Campi Da Ricercare

### 7.1 Campo: `numero_certificato`

* `obbligatorio nel runtime`: `si`
* `usato per match con DDT`: `forte`
* `pagina/blocco principale`: pagina 1, header tecnico
* `posizione precisa osservata`: riga `CERT.NO.`
* `relazione spaziale con altri campi`: vicino alla data certificato
* `ancore testuali`: `CERT.NO.`, `No.CERT`
* `varianti di scrittura`: numero semplice tipo `151238`, `151323`, `151675`
* `tipo valore`: `documentale puro`
* `strumento di lettura migliore`: `ocr / regex`
* `contesto minimo necessario`: `blocco`
* `nota runtime`: campo critico, molto forte

### 7.2 Campo: `data_certificato`

* `obbligatorio nel runtime`: `si`
* `usato per match con DDT`: `debole`
* `pagina/blocco principale`: pagina 1, header tecnico
* `posizione precisa osservata`: riga `CERT.DATE`
* `relazione spaziale con altri campi`: vicino a `CERT.NO.`
* `ancore testuali`: `CERT.DATE`, `DATE`
* `tipo valore`: `documentale puro`
* `strumento di lettura migliore`: `ocr / regex`
* `contesto minimo necessario`: `blocco`

### 7.3 Campo: `ordine_ab`

* `obbligatorio nel runtime`: `si`
* `usato per match con DDT`: `medio`
* `pagina/blocco principale`: pagina 1, header tecnico
* `posizione precisa osservata`: riga `A.B. ORDER No.`
* `ancore testuali`: `A.B. ORDER No.`, `No. DE COMMANDE AB.`
* `varianti di scrittura`: `2026.2610046.2`, `2026.2.255.0`
* `tipo valore`: `documentale puro`
* `strumento di lettura migliore`: `ocr / regex`
* `contesto minimo necessario`: `blocco`

### 7.4 Campo: `articolo_interno`

* `obbligatorio nel runtime`: `si`
* `usato per match con DDT`: `forte`
* `pagina/blocco principale`: pagina 1, header tecnico
* `posizione precisa osservata`: riga `ARTICLE`
* `ancore testuali`: `ARTICLE`, `PROFIL`
* `varianti di scrittura`: `14BT147-B03`, `14BT182-B04`, `14BT185-B21`
* `tipo valore`: `codice`
* `strumento di lettura migliore`: `ocr / regex`
* `contesto minimo necessario`: `blocco`

### 7.5 Campo: `ordine_cliente`

* `obbligatorio nel runtime`: `si`
* `usato per match con DDT`: `medio`
* `pagina/blocco principale`: pagina 1, header tecnico
* `posizione precisa osservata`: riga `Customer's Order No.`
* `ancore testuali`: `Customer's Order No.`
* `varianti di scrittura`: `2026-01-07 1`, `2025-12-18 400`
* `tipo valore`: `documentale puro`
* `strumento di lettura migliore`: `ocr / regex`
* `contesto minimo necessario`: `blocco`
* `nota runtime`: va confrontato col DDT con normalizzazione dei token invertiti

### 7.6 Campo: `peso_netto`

* `obbligatorio nel runtime`: `si`
* `usato per match con DDT`: `medio`
* `pagina/blocco principale`: pagina 1, header tecnico
* `posizione precisa osservata`: riga `NET WEIGHT`
* `ancore testuali`: `NET WEIGHT`, `NETGEWICHT`, `POIDS NET`
* `varianti di scrittura`: `5,920`, `3,719`, `2,541`
* `tipo valore`: `numerico standardizzato`
* `unita implicita`: `kg`
* `strumento di lettura migliore`: `ocr / regex`
* `contesto minimo necessario`: `blocco`

### 7.7 Campo: `codice_cliente_materiale`

* `obbligatorio nel runtime`: `si`
* `usato per match con DDT`: `forte`
* `pagina/blocco principale`: pagina 1, header tecnico
* `posizione precisa osservata`: dentro `CUSTOMER'S SECTION DESC.`
* `ancore testuali`: `CUSTOMER'S SECTION DESC.`
* `varianti di scrittura`: `A62098020`, `A62130020`, `A751270`
* `tipo valore`: `codice`
* `strumento di lettura migliore`: `ocr / regex`
* `contesto minimo necessario`: `blocco`
* `nota runtime`: va tenuto distinto da `ARTICLE`

### 7.8 Campo: `descrizione_materiale_dimensione`

* `obbligatorio nel runtime`: `si`
* `usato per match con DDT`: `forte`
* `pagina/blocco principale`: pagina 1, header tecnico
* `posizione precisa osservata`: stessa area di `CUSTOMER'S SECTION DESC.`
* `ancore testuali`: `BARRA TONDA`
* `varianti di scrittura`: `BARRA TONDA 98`, `127`, `130`
* `tipo valore`: `documentale puro` + `numerico standardizzato`
* `strumento di lettura migliore`: `ocr`
* `contesto minimo necessario`: `blocco`
* `nota runtime`: estrarre separando codice cliente, descrizione e dimensione

### 7.9 Campo: `lega_stato`

* `obbligatorio nel runtime`: `si`
* `usato per match con DDT`: `forte`
* `pagina/blocco principale`: pagina 1, header tecnico
* `posizione precisa osservata`: riga `ALLOY & Phys.State`
* `ancore testuali`: `ALLOY & Phys.State`
* `varianti di scrittura`: `6082 F`, `7075 F`
* `tipo valore`: `documentale puro`
* `strumento di lettura migliore`: `ocr`
* `contesto minimo necessario`: `blocco`

### 7.10 Campo: `colata`

* `obbligatorio nel runtime`: `si`
* `usato per match con DDT`: `forte`
* `pagina/blocco principale`: tabella chimica
* `posizione precisa osservata`: riga `CAST BATCH Nr`
* `ancore testuali`: `CAST BATCH Nr`, `CHARGE Num.`
* `varianti di scrittura`: `525301A1`, `525335A3`, `525335A4`
* `tipo valore`: `documentale puro`
* `strumento di lettura migliore`: `ocr / tabellare`
* `contesto minimo necessario`: `tabella`
* `nota runtime`: e' il valore materiale misurato a cui appartiene la riga chimica

---

## 8. Struttura Della Tabella Chimica

Osservazione confermata:

* la tabella e' orizzontale
* una riga porta la colata reale misurata
* sotto compaiono righe `Min.` e `Max.`

Regola:

* la riga con `CAST BATCH Nr` e' la riga dei valori misurati
* le righe `Min.` e `Max.` sono limiti normativi/template, non misurati

Elementi osservati nel template:

* `Si`
* `Fe`
* `Cu`
* `Mn`
* `Mg`
* `Cr`
* `Ni`
* `Zn`
* `Ga`
* `V`
* `Ti`
* `Pb`
* `Zr`
* `Bi`
* `Sn`
* `Al`

Placeholder da validare insieme:

* in alcuni certificati possono comparire vincoli combinati come `Ti+Zr`; va distinto se e' nota/limite o valore misurato vero

---

## 9. Struttura Della Tabella Proprieta' Meccaniche

Osservazione confermata:

* la tabella meccanica e' sotto la chimica
* contiene una o piu' righe `SAMPLE No.`
* sotto compare una riga `NORMA Min.`

Colonne osservate:

* `Rm [MPa]`
* `Rp0.2 [MPa]`
* `A%`
* `Hardness Brinell [HBW]`
* `Conducibilita [MS/m]` come intestazione template, ma spesso senza valore misurato nella riga

Regola:

* le righe numerate `1`, `2`, ecc. sono prove reali
* `NORMA Min.` e `NORM EN 755-2` sono limiti/riferimenti, non prove

Nota:

* in alcuni certificati le prove reali possono essere poco leggibili o mancanti nella OCR, ma la struttura resta la stessa

---

## 10. Struttura Delle Note

Le note utili stanno nella parte bassa della pagina 1, dopo le tabelle.

Note osservate ricorrenti:

* `Materiale privo di contaminazione radioattiva`
* `Materiale conforme alla direttiva RoHS-2`
* `Materiale destinato a prodotti di sicurezza`
* `Controllo US su Billetta secondo AMS STD 2154 Classe B`
* `Billette ultrasuonate secondo procedura interna "CQ02I07"`
* `Materiale fornito in stato "F"`
* `Collaudo secondo specifica "LST 00 Rev. 01"`

Regola:

* queste note fanno parte del contenuto utile del certificato
* non sono rumore
* vanno distinte da testi legali multilingua piu' lunghi

---

## 11. Pagina 2

Osservazione confermata:

* la pagina 2 non aggiunge nuova chimica o nuove proprieta'
* ripete l'header tecnico principale
* aggiunge informazioni sull'origine del primary aluminium:
  * `Country of largest smelt`
  * `Country of second largest smelt`
  * `Country of Most Recent Cast`

Regola:

* pagina 2 = pagina secondaria
* utile per conformita'/origine
* non sostituisce la pagina 1 come sorgente tecnica principale

---

## 12. Posizione E Contesto Per ML

* `blocchi visivi principali`: header tecnico, tabella chimica, tabella meccanica, note, pagina 2 origine
* `aree stabili`: quasi tutta la pagina 1 tecnica
* `aree instabili`: contenuto delle note finali e numero righe di prova meccanica
* `zone dove conviene fare crop mirati`:
  * header tecnico
  * riga `CAST BATCH`
  * blocco tabella chimica
  * blocco tabella meccanica
  * blocco note fondo pagina
* `necessità di pagina intera`: `si`
* `necessità di crop tabella`: `si`
* `necessità di bbox`: `alta`

---

## 13. Punti Forti Osservati

* template molto stabile
* match con DDT molto forte grazie a `CERT.NO.`, `ARTICLE`, codice cliente/materiale, colata, lega e peso
* chimica e proprieta' sono in blocchi molto chiari
* note certificate rilevanti e ricorrenti

## 14. Punti Deboli Osservati

* OCR puo' confondere colonne dense della chimica
* alcune righe meccaniche risultano sporche o parziali
* la pagina 2 puo' far perdere tempo se trattata come primaria

## 15. Note Per Il Codice Futuro

* leggere prima sempre la pagina 1
* trattare la chimica come `riga misurata + min/max`, non come tabella unica piatta
* trattare la meccanica come `prove reali + riga norma`
* distinguere `ARTICLE` da `CUSTOMER'S SECTION DESC.`
* usare pagina 2 solo come supporto secondario

---

## 16. Placeholder Da Validare Insieme

* decidere se per questo template serve un file base anche per i vincoli combinati di chimica come `Ti+Zr`
* decidere se la conducibilita' va gestita come proprieta' standard o opzionale, visto che l'intestazione e' presente ma i valori non sempre sono chiari
