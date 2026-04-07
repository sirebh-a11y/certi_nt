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
* salvare i dati sorgente realmente presenti nei documenti
* strutturare i dati in database in modo tracciabile

Questo modulo definisce il livello:

* `acquisition`

Questo modulo NON definisce in dettaglio:

* `incoming review`
* `kpi / derived data`

---

## 2. Livelli logici del sistema

Per evitare ambiguità, il sistema distingue tre livelli:

### 2.1 Acquisition

Contiene i dati sorgente/documentali realmente letti da certificati e DDT.

Questo è l’unico livello definito in dettaglio in questo file.

### 2.2 Incoming review

Contiene eventi e decisioni interne del processo qualità/incoming, per esempio:

* data_ricezione
* data_accettazione
* n_analisi
* valutazione
* note operative interne

Questo livello NON fa parte del modello `acquisition`.

### 2.3 KPI / derived data

Contiene valori calcolati, per esempio:

* ritardo
* tempo_controllo
* tempo_medio_controllo

Questo livello NON fa parte del modello `acquisition`.

---

## 3. Entità principali

* Certificato (CDQ)
* Dati materiale acquisition
* Proprietà chimiche
* Proprietà certificate

Chiave logica principale:

* `cdq` = CERTIFICATO DI QUALITÀ del FORNITORE

---

## 4. Modello dati (`acquisition`)

### 4.1 datimaterialeincoming

Una riga logica per `cdq`.

Rappresenta solo dati sorgente/documentali.

Campi:

* `cdq` (PK, identificativo legacy)
* `fornitore_id` (FK → fornitori.id, nullable finché il mapping non è completato)
* `fornitore_raw` (testo originale letto da OCR / DDT / certificato)
* `lega_base`
* `lega_designazione`
* `variante_lega` (nullable)
* `diametro`
* `colata`
* `ddt`
* `peso`
* `ordine` (solo se realmente presente nella fonte documentale)
* `data_documento` (nullable, solo se presente nella fonte documentale)
* `note_documento` (nullable, solo se la nota appartiene al documento sorgente)

Campi ESCLUSI da questa entità:

* `data_ricezione`
* `data_accettazione`
* `data_richiesta_consegna` se dato interno/ERP
* `n_analisi`
* `valutazione`
* `ritardo`
* `tempo_controllo`
* `tempo_medio`
* note operative interne

---

### 4.2 elementi_chimici

Lista controllata iniziale.

La lista è ufficiale per l’avvio del sistema, ma deve poter essere estesa in futuro se emergono nuovi elementi reali o nuovi standard.

Elenco ufficiale iniziale:

* Si
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

* `id` (PK)
* `nome` (unico)
* `attivo`

---

### 4.3 proprieta_certificato_def

Lista controllata iniziale delle proprietà certificate.

Questa lista non deve essere limitata alle sole proprietà meccaniche.
Il sistema deve poter distinguere la categoria della proprietà.

Elenco ufficiale iniziale:

* HB
* Rp0.2
* Rm
* A%
* Rp0.2 / Rm
* IACS%

Struttura:

* `id` (PK)
* `nome` (unico)
* `categoria` (esempio: `meccanica`, `elettrica`)
* `attivo`

---

### 4.4 proprietachimiche

Valori chimici letti dal certificato.

* `id` (PK)
* `cdq` (FK)
* `elemento_id` (FK)
* `valore`

---

### 4.5 proprietacertificato

Valori di proprietà certificate letti dal certificato.

* `id` (PK)
* `cdq` (FK)
* `proprieta_id` (FK)
* `valore`

---

### 4.6 fornitori (riferimento modulo esterno)

La gestione dei fornitori è definita in un modulo dedicato:

→ `docs/modules/fornitori.md`

Ogni certificato (`cdq`) è associato a un fornitore tramite:

* `fornitore_id` (FK)

Il campo:

* `fornitore_raw`

mantiene il valore originale letto dai documenti per garantire:

* tracciabilità
* supporto al mapping verso fornitori normalizzati
* possibilità di revisione umana

---

## 5. Regole di acquisizione dati

### 5.1 Regola generale

Il livello `acquisition` deve contenere SOLO dati sorgente/documentali.

NON devono essere salvati nel livello `acquisition`:

* valori calcolati
* valori derivati non presenti nel certificato
* stime
* decisioni interne di processo

Questa regola vale per:

* chimica
* proprietà certificate
* anagrafica documentale del record

---

### 5.2 Regola unificata per derivati

Vale per:

* chimica
* proprietà certificate
* processo

Regola:

* se presente nel certificato → SALVARE
* se NON presente → NON salvare nel livello `acquisition`
* eventuale calcolo SOLO runtime o in livelli separati

---

### 5.3 Chimica

* salvare elementi singoli se presenti
* salvare composti SOLO se presenti
* non inventare elementi non presenti

---

### 5.4 Proprietà certificate

* salvare solo valori presenti
* salvare rapporti SOLO se presenti
* la categoria della proprietà non cambia la regola di acquisizione

---

### 5.5 Fornitori

Il nome del fornitore viene acquisito dai documenti e gestito secondo la seguente logica:

* il valore letto viene salvato in `fornitore_raw`
* il sistema associa un `fornitore_id` tramite mapping (automatico o manuale)
* il database utilizza sempre `fornitore_id` come riferimento principale

Nota:

* `automatico o manuale` si riferisce solo al mapping verso un fornitore già censito
* il processo documentale NON deve aggiornare automaticamente l'anagrafica del fornitore
* l'anagrafica fornitori viene gestita nel modulo `fornitori` tramite import iniziale e poi tramite modifica manuale da GUI

Questo garantisce:

* normalizzazione dei fornitori
* gestione di varianti (alias)
* tracciabilità del dato originale

---

## 6. Logica runtime

Il sistema può avere logiche runtime sui derivati, ma i derivati non entrano nel livello `acquisition` se non compaiono esplicitamente nel certificato.

### Chimica

Zr+Ti:

* se presente → usare valore salvato
* altrimenti:
  * se Zr e Ti presenti → Zr + Ti
  * altrimenti → NULL

### Proprietà certificate

Rp0.2 / Rm:

* se presente → usare valore salvato
* altrimenti:
  * se Rp0.2 e Rm presenti e Rm ≠ 0 → calcolare
  * altrimenti → NULL

### Regola generale

Un valore derivato è calcolabile SOLO se:

* tutti i valori necessari sono presenti
* l’operazione è valida

Altrimenti:

→ NULL

---

## 7. Pipeline

Documenti → OCR → mapping → validazione → DB (`acquisition`)

---

## 8. OCR / AI

* NO calcoli
* NO dati inventati
* SOLO mapping su vocabolario controllato iniziale
* vocabolario estendibile quando emergono nuovi casi reali

---

## 9. Rapporto con i fogli Excel operativi

I fogli Excel storici possono rappresentare una vista operativa arricchita che mescola:

* dati acquisiti
* dati di processo interno
* KPI

Questa vista è utile come riferimento di business, ma NON coincide con il modello `acquisition`.

Il modello `acquisition` deve isolare solo la componente sorgente/documentale.

---

## 10. Vincoli

* `cdq` obbligatorio
* `cdq` univoco
* tracciabilità completa
* separazione netta tra dato sorgente e dato operativo/calcolato

---

## 11. Obiettivo

Separare:

* dati reali/documentali
* logica applicativa
* decisioni di processo
* KPI

Sistema robusto e tracciabile.

---

## 12. Estensione futura

Altri file o moduli potranno definire in seguito:

* workflow incoming review
* KPI e calcoli di processo
* UI
* logiche di validazione operativa
