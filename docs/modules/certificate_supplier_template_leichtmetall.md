# Certificate Supplier Template Analysis - Leichtmetall

## Scopo

Analisi del template certificato osservato per `Leichtmetall Aluminium Giesserei Hannover GmbH` sui certificati reali che matchano i DDT gia' studiati.

Dataset di riferimento:

```plaintext
esempi_locali/3-certificati/Leichtmetall A/Certificati Origine
```

Questo file serve a fissare:

* struttura reale del template certificato
* campi originali usabili nel runtime futuro
* struttura vera della tabella chimica
* regole di match con i DDT `Leichtmetall`

---

## 1. Identificazione

* `fornitore_master`: `Leichtmetall Aluminium Giesserei Hannover GmbH`
* `alias_osservati`: `Leichtmetall`, `EGA`, `Leichtmetall A`
* `template_id`: `leichtmetall_cast_billet_certificate_v1`
* `stato_analisi`: `bozza`

---

## 2. Dataset Letto

* `pdf_letti`: `CdQ_94683_6082_Ø295.pdf`, `CdQ_94668_6082_Ø240.pdf`, `CdQ_94668_6082_Ø228_1.pdf`, `CdQ_94775_7075_Ø165.pdf`
* `pagine_totali_lette`: `4`
* `documenti_rappresentativi`: gli stessi 4 file

Match forti gia' verificati con i DDT:

* `80008518.pdf` -> `CdQ_94683_6082_Ø295.pdf`
* `80008519.pdf` -> `CdQ_94668_6082_Ø240.pdf`
* `80008535.pdf` -> almeno un certificato famiglia `94668`, coerente con il gruppo batch da `5,014 KG`
* `80008577.pdf` -> `CdQ_94775_7075_Ø165.pdf`
* `80008578.pdf` -> `CdQ_94775_7075_Ø144.pdf` stesso template osservato, stesso impianto dati

Nota metodologica:

* i nomi file sopra aiutano solo l'analisi e la validazione del dataset storico
* il match runtime futuro non deve usare il nome file
* il match runtime deve usare solo i campi letti dal DDT e dal certificato
* stessa famiglia/root certificato non significa documento uguale
* `Charge/Cast No` da solo non basta a distinguere i certificati quando esistono piu' PDF diversi della stessa famiglia

---

## 3. Regola Chiave Del Template

Descrizione breve del template:

* certificato monofoglio, bilingue tedesco/inglese
* header con cliente, produttore, `Charge/Cast No`, alloy e `PO-No.`
* blocco prodotto con quantity, diameter, length e weight
* tabella chimica orizzontale con righe `Min.`, `Max.` e `Ist/act.`
* blocco note/special requirements sotto la chimica

Il template si riconosce da:

* `Abnahmeprufzeugnis / Inspection Certificate 3.1`
* `Charge/ Cast No`
* `Bestellnr./ PO-No.`
* `Chemische Analyse / Chemical Analysis`
* riga misurata `Ist/act.`
* blocco `Customer Special Requirements`

---

## 4. Guardrail Runtime

### 4.1 Campi Usabili Nel Runtime Futuro

* `Charge/ Cast No`
* `PO-No.`
* alloy
* quantity
* diameter
* length
* weight
* riga chimica `Ist/act.`
* note certificate come `ASTM B 594 / AMS-STD 2154 class A`
* nota radioactivity free

### 4.2 Contesto Da NON Usare Come Dato Finale

* righe `Min.` e `Max.` come se fossero valori misurati
* testo normativo generico come se fosse proprieta' misurata
* frase `Hardness Test acc. ISO 6506` se non seguita da un valore reale

---

## 5. Struttura Documento

### 5.1 Pagine E Blocchi

* pagina 1 unica:
  * header cliente/produttore
  * identificazione batch/cast
  * blocco prodotto
  * tabella chimica
  * customer special requirements
  * firma quality manager

### 5.2 Tabelle

#### Chimica

* orientamento osservato: `orizzontale`
* riga misurata: `Ist/act.`
* righe limiti: `Min.` e `Max.`
* elementi osservati:
  * `Si`, `Fe`, `Cu`, `Mn`, `Mg`, `Cr`, `Zn`, `Ti`
  * `Andere/others` con sottocampi `Einzel/each` e `zus./total`

Regola:

* in `acquisition` si salva solo la riga `Ist/act.`
* `Min.` e `Max.` restano limiti documentali, non valori misurati
* se il certificato non mostra un elemento come valore misurato, quel campo resta `null`

#### Proprieta'

* nei certificati letti non compare una tabella meccanica misurata
* compare solo riferimento a prova durezza / requisito cliente

Regola:

* non inventare proprieta' misurate da testo descrittivo
* placeholder: verificare se esistono altri template `Leichtmetall` con tabella meccanica reale

---

## 6. Regola Di Match Con DDT

### 6.1 Campi Forti

* `Charge/ Cast No`
* `PO-No.`
* alloy
* diameter
* weight

### 6.2 Regola Pratica

1. usare `PO-No.` e alloy per restringere il gruppo corretto
2. confermare con diameter
3. chiudere il match con `Charge/Cast No`
4. usare weight come ulteriore controllo

Nota pratica importante:

* possono esistere piu' certificati distinti con lo stesso `Charge/Cast No`
* in questi casi il match va chiuso con `PO-No.` + alloy + diameter + weight e non solo con il cast

---

## 7. Note Runtime

* il certificato e' molto forte su batch/cast, PO-No. e chimica
* il DDT da solo e' piu' debole, quindi il match corretto nasce dall'uso congiunto DDT + certificato
* per questo template la chimica e' centrale, le proprieta' meccaniche no
