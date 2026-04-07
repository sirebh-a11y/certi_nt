# Fornitori Module

## ⚠️ IMPORTANTE — POSIZIONAMENTO NEL PROGETTO

Questo modulo NON fa parte del core del sistema.

Deve essere implementato dopo la stabilizzazione del core, tramite prompt Codex dedicato.

Questo modulo definisce l’anagrafica fornitori utilizzata dal sistema di acquisizione dati (DDT e certificati).

---

## 1. Scopo

Gestire i fornitori del materiale che:

* emettono DDT
* emettono certificati di qualità (CDQ)

Obiettivi:

* normalizzare i fornitori
* evitare duplicati
* gestire varianti di nome (OCR, abbreviazioni)
* mantenere storico modifiche

---

## 2. Entità principali

* Fornitore (anagrafica)
* Alias fornitore
* Storico modifiche

---

## 3. Modello dati

### 3.1 fornitori

Rappresenta l’anagrafica principale del fornitore.

Questa tabella contiene lo **stato corrente** del fornitore.

Struttura:

* id (PK)
* ragione_sociale
* partita_iva (nullable)
* codice_fiscale (nullable)
* indirizzo (nullable)
* cap (nullable)
* citta (nullable)
* provincia (nullable)
* nazione (nullable)
* email (nullable)
* telefono (nullable)
* attivo
* note (campo libero)

Regola:

* `indirizzo` contiene solo via/piazza e numero civico
* `cap` contiene solo il CAP / postal code
* `citta` contiene solo la città
* `provincia` contiene solo sigla o denominazione provincia/stato locale quando utile
* `nazione` resta separata

---

### 3.2 fornitori_alias

Gestione dei nomi alternativi del fornitore.

Serve per intercettare varianti provenienti da:

* OCR
* DDT
* certificati
* abbreviazioni

Struttura:

* id (PK)
* fornitore_id (FK → fornitori.id)
* nome_alias
* fonte (es: OCR, manuale)
* attivo

---

### 3.3 fornitori_storico

Storico modifiche dell’anagrafica fornitori.

Ogni modifica rilevante deve:

* aggiornare il dato corrente in `fornitori`
* registrare la modifica nello storico

Lo storico è append-only e rappresenta l’audit trail delle modifiche.

Struttura:

* id (PK)
* fornitore_id (FK → fornitori.id)
* campo_modificato
* valore_precedente
* valore_nuovo
* data_modifica
* utente (nullable)

---

## 4. Regole di gestione

### 4.1 Regola generale

Il sistema deve utilizzare sempre:

```plaintext
fornitore_id
```

come riferimento principale.

---

### 4.2 Acquisizione da documenti

Durante l’acquisizione:

1. il nome fornitore viene letto dal documento
2. salvato in:

   ```plaintext
   fornitore_raw
   ```
3. il sistema tenta il match con:

   ```plaintext
   fornitori_alias
   ```
4. se trovato → assegna `fornitore_id`
5. se non trovato → gestione manuale o creazione nuovo fornitore

---

### 4.3 Alias

* ogni variante di nome deve essere salvata come alias
* un alias appartiene a un solo fornitore
* nome_alias deve essere univoco per evitare ambiguità nel mapping
* evitare duplicati tra alias

---

### 4.4 Storico

* il record corrente del fornitore viene aggiornato quando necessario
* ogni modifica deve essere registrata
* lo storico è solo append (non modifica)
* lo storico non sostituisce l’anagrafica corrente, la accompagna

---

## 5. Vincoli

* un fornitore è univoco (no duplicati logici)
* alias non devono creare ambiguità
* `fornitore_id` è obbligatorio SOLO dopo il processo di mapping
* durante l’acquisizione può essere temporaneamente NULL

---

## 6. Collegamento con altri moduli

### Certificates Data Acquisition Module

Il collegamento avviene tramite:

```plaintext
datimaterialeincoming.fornitore_id
```

e

```plaintext
datimaterialeincoming.fornitore_raw
```

### Dataset / fogli storici

Dataset o fogli storici possono essere organizzati per fornitore e il nome del foglio può rappresentare un indizio utile nel contesto di analisi.

Tuttavia il sistema deve sempre atterrare su:

* `fornitore_raw`
* `fornitore_id`
* eventuali `fornitori_alias`

---

## 7. Obiettivo

Separare:

* dato reale (nome letto)
* entità normalizzata (fornitore)

Garantire:

* qualità dei dati
* robustezza OCR
* scalabilità futura (GUI)

---

## 8. Estensione futura

Il modulo sarà gestito tramite GUI per:

* creazione fornitori
* gestione alias
* revisione mapping
* aggiornamento dati anagrafici
