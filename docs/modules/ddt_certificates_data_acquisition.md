# Certificates Data Acquisition Module

## ⚠️ IMPORTANTE — POSIZIONAMENTO NEL PROGETTO

Questo modulo NON fa parte del core del sistema.

Il core deve essere completato e stabilizzato prima di implementare questo modulo.

Questo modulo deve essere implementato successivamente tramite un prompt dedicato per Codex.

---

## ⚠️ IMPORTANTE — DEFINIZIONE CDQ (CRITICO)

Il campo `cdq` NON è un identificativo tecnico generato dal sistema.

Il campo `cdq` rappresenta:

→ il numero del CERTIFICATO DI QUALITÀ del FORNITORE (identificativo legacy)

Regole:

* deve corrispondere ESATTAMENTE al valore presente nei documenti (PDF, Excel, DDT)
* NON deve essere modificato
* NON deve essere rigenerato
* NON deve essere sostituito con ID interno

Il sistema può avere ID tecnici interni, ma `cdq` rimane il riferimento principale per:

* tracciabilità
* collegamento ai documenti
* validazione dati

---

## 1. Scopo

Gestire l’acquisizione dei dati da:

* certificati di qualità (CDQ) del fornitore materiale
* DDT del fornitore materiale

Obiettivi:

* estrarre dati dai documenti
* salvare SOLO valori presenti nei certificati
* strutturare i dati in database

---

## 2. Entità principali

* Certificato (CDQ)
* Dati materiale incoming
* Proprietà chimiche
* Proprietà meccaniche

Chiave logica principale:

* `cdq` = CERTIFICATO DI QUALITÀ del FORNITORE

---

## 3. Modello dati

### 3.1 datimaterialeincoming

Una riga per certificato.

Campi:

* cdq (PK, identificativo legacy)
* numero
* data_ricezione
* data_accettazione
* fornitore
* lega
* diametro
* colata
* ddt
* peso
* ordine
*	data richiesta
*	ritardo (= data ricezione – data richiesta)
*	tempo_controllo (= data accettazione – data ricezione in giorni lavorativi, eliminati quindi feriali e ferie italiane)
*	tempo_medio 
*	Valutazione (che può essere A di Accettato o AR di Accettato con Riserva o R di Respinto)
*	Note che è campo libero testuale


---

### 3.2 elementi_chimici

Lista controllata e CHIUSA.

Elenco ufficiale:

* Fe
* Cu
* Mn
* Mg
* Cr
* Ni
* Zn
* Ti
* Pb
* V
* Bi
* Sn
* Zr
* Be
* Zr+Ti
* Mn+Cr
* Bi+Pb

Struttura:

* id (PK)
* nome (unico)
* attivo

---

### 3.3 proprieta_meccaniche_def

Lista controllata e CHIUSA.

Elenco ufficiale:

* HB
* Rp0.2
* Rm
* A%
* Rp0.2 / Rm

Struttura:

* id (PK)
* nome (unico)
* attivo

---

### 3.4 proprietachimiche

Valori chimici letti dal certificato.

* id (PK)
* cdq (FK)
* elemento_id (FK)
* valore

---

### 3.5 proprietameccaniche

Valori meccanici letti dal certificato.

* id (PK)
* cdq (FK)
* proprieta_id (FK)
* valore

---

## 4. Regole di acquisizione dati

### 4.1 Regola generale

Il database deve contenere SOLO dati letti dal certificato.

NON devono essere salvati:

* valori calcolati
* valori derivati non presenti nel certificato
* stime

---

### 4.2 Regola unificata per derivati

Vale per:

* chimica
* meccanica
* processo

Regola:

* se presente nel certificato → SALVARE
* se NON presente → NON salvare
* calcolo SOLO runtime

---

### 4.3 Chimica

* salvare elementi singoli se presenti
* salvare composti SOLO se presenti

---

### 4.4 Meccanica

* salvare solo valori presenti
* salvare rapporti SOLO se presenti

---

### 4.5 Processo

* salvare se presenti
* altrimenti calcolare runtime

---

## 5. Logica runtime

### Chimica

Zr+Ti:

* se presente → usare valore salvato
* altrimenti:

  * se Zr e Ti presenti → Zr + Ti
  * altrimenti → NULL

---

### Meccanica

Rp0.2 / Rm:

* se presente → usare valore salvato
* altrimenti:

  * se Rp0.2 e Rm presenti e Rm ≠ 0 → calcolare
  * altrimenti → NULL

---

### Regola generale

Un valore derivato è calcolabile SOLO se:

* tutti i valori sono presenti
* operazione valida

Altrimenti:
→ NULL

---

## 6. Pipeline

Documenti → OCR → mapping → validazione → DB

---

## 7. OCR / AI

* NO calcoli
* NO dati inventati
* SOLO mapping su vocabolario controllato

---

## 8. Vincoli

* cdq obbligatorio
* cdq univoco
* tracciabilità completa

---

## 9. Obiettivo

Separare:

* dati reali
* logica applicativa

Sistema robusto e tracciabile.

---

## 10. Estensione futura

Altri file saranno creati per:

* OCR
* mapping
* UI
* workflow
