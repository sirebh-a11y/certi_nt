# Document OpenAI Double Check Strategy

## Scopo

Questo file definisce il ruolo corretto di ChatGPT/OpenAI nel reader documentale.

ChatGPT/OpenAI **non** deve essere il lettore principale del sistema.

Deve essere un livello di:

* secondo lettore indipendente
* validazione strutturale
* disambiguazione dei casi difficili
* controllo di coerenza tra quanto letto dal parser tradizionale e il documento reale

---

## 1. Principio guida

La lettura documentale deve puntare al massimo livello realistico di precisione.

Quindi:

* il parser tradizionale resta obbligatorio
* il riconoscimento strutturale locale resta obbligatorio
* OpenAI entra come **double check forte**
* il dato finale non deve nascere da una sola lettura cieca

Formula guida:

```plaintext
lettura locale -> candidato strutturato -> OpenAI double check -> decisione finale
```

---

## 2. Cosa deve fare il codice tradizionale

Il codice tradizionale deve continuare a fare in autonomia:

* riconoscimento pagina utile
* riconoscimento blocco utile
* distinzione tra DDT, packing list, certificato, pagina secondaria
* riconoscimento tabella orizzontale / verticale
* riconoscimento di righe e colonne
* esclusione di righe o colonne `min` e `max`
* selezione della riga o colonna del valore misurato
* normalizzazione dei valori
* raccolta di evidenze e contesto

OpenAI non sostituisce questa logica.

La valida o la aiuta nei casi difficili.

---

## 3. Cosa deve fare OpenAI

OpenAI deve essere usato soprattutto per:

* confermare se una tabella e' orizzontale o verticale
* confermare quale riga o colonna contiene il valore misurato
* distinguere il misurato da `min` / `max`
* confermare che il crop scelto dal parser contiene davvero il campo giusto
* validare match DDT ↔ certificato quando i campi sono coerenti ma non banali
* fare check di coerenza tra piu' campi gia' letti
* leggere note complesse o blocchi tecnici difficili

OpenAI non deve essere usato come:

* lettore cieco di pagina intera per default
* sostituto del parser deterministico
* generatore diretto del dato finale senza prova

---

## 4. Input consentito a OpenAI

L'input preferito deve essere:

* crop mirato del campo
* crop della riga
* crop della tabella
* pagina mascherata solo se necessario

L'input da evitare come default:

* PDF intero
* pagina intera non mascherata
* piu' pagine insieme senza ragione forte

L'input ideale deve includere:

* immagine del blocco utile
* eventuale OCR locale gia' disponibile
* contesto minimo utile
* richiesta di output strutturato JSON

---

## 5. Masking obbligatorio

Prima di inviare dati a OpenAI vanno mascherati o tagliati i dati non necessari.

In particolare:

* dati di `Forgialluminio 3`
* indirizzi
* partita IVA
* email
* telefono
* dati societari generali
* dati del fornitore non necessari alla lettura tecnica

Regola:

* si deve mandare solo il **minimo dato necessario**
* il crop deve contenere il blocco tecnico utile e non il resto

Se il crop mirato basta, non si manda altro.

---

## 6. Task consigliati per OpenAI

### 6.1 Tabelle chimiche

OpenAI puo' validare:

* orientamento tabella
* posizione della riga misurata
* esclusione di `min` / `max`
* presenza reale o assenza reale degli elementi
* lettura di combinati solo se presenti davvero

### 6.2 Tabelle proprieta' meccaniche

OpenAI puo' validare:

* quale blocco contiene i valori misurati
* se esiste solo `min` o anche `max`
* quale riga e' quella reale della colata/charge
* distinzione tra:
  * proprieta' standard
  * proprieta' dopo trattamento simulato

### 6.3 Match DDT ↔ certificato

OpenAI puo' validare:

* se i campi letti dal DDT e dal certificato sono coerenti
* se il match e' forte, debole o da rifiutare
* se il certificato giusto e' uno tra piu' candidati

---

## 7. Modelli consigliati

### Modello default

* `gpt-5.4`

Ruolo:

* secondo lettore
* validazione di crop
* disambiguazione
* ranking di candidati

### Modello escalation

* `gpt-5.4-pro`

Ruolo:

* casi rari molto ambigui
* conflitto tra parser locale e validazione `gpt-5.4`
* casi ad alto impatto dove serve massimo approfondimento

Regola:

* `gpt-5.4-pro` non deve essere il default

---

## 8. Regola decisionale finale

Il dato finale non deve dipendere da una sola fonte.

Schema base:

* `parser locale` produce:
  * valore candidato
  * evidenza
  * confidenza
* `OpenAI` produce:
  * conferma / smentita
  * valore candidato
  * spiegazione strutturata

Decisione consigliata:

* locale forte + OpenAI coerente -> stato forte
* locale forte + OpenAI incoerente -> da verificare
* locale debole + OpenAI coerente con il documento -> quasi
* locale debole + OpenAI incoerente -> rosso
* locale forte + nessun OpenAI necessario -> accettabile se il template lo consente

OpenAI quindi deve essere pensato piu' come:

* **double check**

che come:

* semplice fallback

---

## 9. Stato operativo suggerito

Per ogni blocco/campo il sistema dovrebbe sapere se:

* letto solo localmente
* validato anche da OpenAI
* corretto dall'utente
* confermato finale

Questo aiuta:

* semaforico
* audit
* futuro ML

---

## 10. Casi dove OpenAI non serve

OpenAI non serve quando:

* il testo PDF e' pulito
* il template e' stabile
* la regola locale e' forte
* il valore e' chiaramente leggibile
* il match e' univoco per campi forti

Obiettivo:

* usare OpenAI solo dove aumenta davvero la qualita'
* non usarlo dove il parser tradizionale e' gia' robusto

---

## 11. Casi dove OpenAI e' particolarmente utile

OpenAI e' particolarmente utile quando:

* la tabella e' rumorosa
* l'orientamento non e' chiaro
* `min/max` e misurato sono vicini o ambigui
* ci sono piu' righe o piu' charge possibili
* il certificato ha piu' blocchi simili
* il DDT scansione e' sporco ma il crop utile e' leggibile

---

## 12. Regola economica

OpenAI non va usato in massa senza ragione.

Uso consigliato:

* singolo crop
* singolo blocco
* singolo documento difficile
* validazione mirata

Non:

* batch cieco di tutte le pagine
* PDF interi senza classificazione preliminare

---

## 13. Regola di trasparenza operativa

Prima di ogni uso OpenAI va sempre dichiarato:

* obiettivo
* modello
* stima costi
* test singolo o batch

Questa regola resta mandatory.
