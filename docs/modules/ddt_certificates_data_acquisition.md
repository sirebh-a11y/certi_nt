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

* Documento
* Pagina documento
* Evidenza documentale
* Match certificato
* Candidati match certificato
* Dati materiale acquisition
* Valori letti
* Proprietà chimiche
* Proprietà certificate

Campi documentali critici di collegamento:

* `cdq` = CERTIFICATO DI QUALITÀ del FORNITORE
* `colata`

Unità logica principale del modulo:

* la riga materiale / riga acquisition

Nota importante:

* il `cdq` resta un campo documentale critico di tracciabilità e collegamento
* ma NON deve più essere interpretato come unico centro logico del record
* il record principale del modulo è la riga materiale generata dal DDT e completata dal certificato corretto

---

## 4. Modello dati (`acquisition`)

### 4.0 Livello repository documentale minimo

Per supportare:

* tracciabilita' documentale reale
* audit
* validazione utente
* futuro machine learning

il modulo deve prevedere anche un repository documentale minimo.

Regola architetturale:

* il DB business non deve contenere direttamente i file pesanti
* PDF originali, immagini pagina e crop devono stare in storage/repository documentale dedicato
* il DB deve salvare riferimenti, hash, metadati e collegamenti logici

#### 4.0.1 document

Rappresenta un file sorgente caricato.

Puo' essere:

* `ddt`
* `certificato`

Campi minimi:

* `id`
* `tipo_documento`
* `fornitore_id` (nullable finche' il mapping non e' completato)
* `nome_file_originale`
* `storage_key`
* `hash_file`
* `mime_type`
* `numero_pagine`
* `data_upload`
* `utente_upload`
* `stato_elaborazione`
* `origine_upload`
* `documento_padre_id` (nullable, per derivati/versioni future)

Nota importante:

* la riga acquisition deve poter salvare il riferimento specifico al PDF DDT e al PDF certificato realmente usati
* non basta salvare solo `cdq` o numero DDT

#### 4.0.2 document_page

Rappresenta una pagina del documento.

Serve per:

* OCR
* testo PDF
* coordinate
* crop
* masking
* invio controllato a ChatGPT/OpenAI

Campi minimi:

* `id`
* `document_id`
* `numero_pagina`
* `larghezza`
* `altezza`
* `rotazione` (nullable)
* `testo_estratto` (nullable)
* `ocr_text` (nullable)
* `immagine_pagina_storage_key` (nullable)
* `stato_estrazione`
* `hash_render` (nullable)

#### 4.0.3 document_evidence

Rappresenta la prova concreta usata dal reader o dall'utente.

Campi minimi:

* `id`
* `document_id`
* `document_page_id`
* `acquisition_row_id` (nullable)
* `blocco`
* `tipo_evidenza`
* `bbox` (nullable)
* `testo_grezzo` (nullable)
* `storage_key_derivato` (nullable)
* `metodo_estrazione`
* `mascherato`
* `confidenza` (nullable)
* `data_creazione`
* `utente_creazione` (nullable)

#### 4.0.4 valore_letto

Rappresenta il dato proposto, standardizzato e poi eventualmente confermato.

Campi minimi:

* `id`
* `acquisition_row_id`
* `blocco`
* `campo`
* `valore_grezzo`
* `valore_standardizzato` (nullable)
* `valore_finale` (nullable)
* `stato`
* `document_evidence_id` (evidenza principale)
* `metodo_lettura`
* `fonte_documentale`
* `confidenza` (nullable)
* `utente_ultima_modifica` (nullable)
* `timestamp_ultima_modifica`

Regola:

* ogni `valore_letto` ha una evidenza principale
* puo' avere anche evidenze secondarie in una relazione dedicata

Valori ammessi iniziali per `fonte_documentale`:

* `ddt`
* `certificato`
* `ddt_certificato`
* `utente`
* `db_esterno`
* `calcolato`

#### 4.0.5 match_certificato

Rappresenta il certificato proposto o confermato per una riga acquisition.

E' un oggetto autonomo di collegamento documentale.

Campi minimi:

* `id`
* `acquisition_row_id`
* `document_certificato_id`
* `stato`
* `motivo_breve` (nullable)
* `fonte_proposta`
* `utente_conferma` (nullable)
* `timestamp`

#### 4.0.6 match_certificato_candidato

Rappresenta eventuali candidati alternativi del match.

Campi minimi:

* `id`
* `match_certificato_id`
* `document_certificato_id`
* `rank`
* `motivo_breve` (nullable)
* `fonte_proposta`
* `stato`

### 4.1 datimaterialeincoming

Una riga logica per materiale / riga acquisition.

Questa riga nasce dal DDT e viene completata con i dati documentali del certificato corretto.

Non rappresenta il documento certificato in astratto.

Rappresenta la singola unità materiale su cui poi si lavora.

Regola importante:

* questa unita' materiale non coincide automaticamente con il singolo collo o con la singola riga stampata del DDT
* in alcuni fornitori/template la riga acquisition puo' richiedere aggregazione di piu' colli o sottorighe omogenee
* il criterio corretto di aggregazione deve essere capito nella fase knowledge leggendo insieme DDT e certificati

Esempi possibili di criterio reale:

* stesso `batch`
* stessa `charge`
* stessa `colata`
* stessa combinazione coerente di materiale, lega, diametro e certificato

Rappresenta solo dati sorgente/documentali.

Campi:

* `id` (PK tecnico interno)
* `document_ddt_id` (FK → document.id, riferimento specifico al PDF DDT usato)
* `document_certificato_id` (FK → document.id, riferimento specifico al PDF certificato finale usato, nullable fino alla conferma)
* `cdq` (identificativo legacy del certificato qualità, campo documentale critico)
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

#### 4.1.1 Regola operativa campo per campo: documentale vs standardizzato

Per evitare ambiguita' tra backend API e frontend, i campi della riga acquisition devono essere trattati cosi':

| Campo | Natura | Regola di visualizzazione |
| ----- | ------ | ------------------------- |
| `cdq` | documentale puro | mostrare esattamente il valore documentale |
| `colata` | documentale puro | mostrare esattamente il valore documentale |
| `ddt` | documentale puro | mostrare esattamente il numero DDT documentale |
| `ordine` | documentale puro | mostrare esattamente il valore documentale se presente |
| `fornitore_raw` | documentale puro | mostrare il testo documentale o il mapping fornitore coerente |
| `diametro` | numerico standardizzato | in UI mostrare solo il numero, senza `mm` |
| `peso` | numerico standardizzato | in UI mostrare solo il numero, senza `kg` |
| `note_documento` | documentale sintetico | mostrare solo contenuto o sintesi utile, non testo tecnico di servizio |
| `proprietachimiche.valore` | numerico standardizzato | in UI mostrare solo il numero, con `%` implicita di sistema |
| `proprietacertificato.valore` | numerico standardizzato | in UI mostrare solo il numero, con unità implicita definita dalla proprietà (`MPa`, `%`, `% IACS`, nessuna) |

Regola forte:

* il `valore_grezzo` puo' contenere unita' e testo originale del documento
* il `valore_standardizzato` NON deve contenere unita'
* il `valore_finale` usato in UI lista/dettaglio deve seguire la stessa regola del valore standardizzato per i campi numerici
* le unita' devono stare nelle label di sistema o nelle intestazioni colonna, non nel valore mostrato
* il sistema deve controllare che il numero letto sia coerente con il contesto del documento origine e con l'unita' attesa del campo
* se il documento origine non supporta in modo sufficiente l'unita' attesa, il valore non deve essere considerato robusto automaticamente

Esempi corretti:

* colonna `Ø (mm)` -> cella `295,00`
* colonna `peso Kg` -> cella `6,730`
* proprieta' `Rp0.2 (MPa)` -> valore `310`
* proprieta' `A%` -> valore `12,5`
* chimica `Mg %` -> valore `0,80`

Esempi errati:

* `295,00 mm`
* `6,730 KG`
* `310 MPa`
* `12,5 %`
* `0,80 %`

Cardinalità concettuale minima:

* un DDT può generare più righe `datimaterialeincoming`
* una riga `datimaterialeincoming` può nascere anche prima del caricamento/conferma del certificato
* uno stesso `cdq` può essere riutilizzato su più righe se il certificato corretto copre più unità materiali
* una riga `datimaterialeincoming` ha un solo DDT e un solo certificato finale associato

Conseguenza:

* `cdq` NON deve essere usato come vincolo di unicità assoluta della tabella
* la tracciabilità documentale resta forte, ma il record resta centrato sulla riga materiale
* la riga deve conservare il riferimento preciso ai documenti sorgente realmente associati

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

La lista è ufficiale e bloccata per l’avvio del sistema, ma deve poter essere estesa in futuro solo quando emergono nuovi casi reali documentati.

Nota importante:

* questa lista non contiene solo elementi singoli
* contiene anche campi combinati realmente osservati nei certificati
* i campi combinati fanno parte del vocabolario controllato del sistema e NON devono essere inventati runtime nel livello `acquisition`

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

Valori chimici letti dal certificato e associati alla riga acquisition.

Questa parte va progettata in modo piu' rigoroso di una semplice tabella `elemento + valore`.

La fonte di verita' del blocco `chimica` nel livello `acquisition` e':

* il `valore_letto` con `blocco = chimica`
* associato alla riga acquisition corretta
* collegato alla sua evidenza documentale

La tabella `proprietachimiche`, se mantenuta, deve essere intesa come proiezione normalizzata dei soli valori chimici effettivi/misurati del certificato.

Regole obbligatorie:

* salvare un solo valore per `riga acquisition + campo chimico`
* il `campo chimico` deve appartenere al vocabolario controllato iniziale
* salvare solo il valore effettivo/misurato riferito alla riga/cast/charge/colata corretta
* NON salvare in `proprietachimiche` righe `min`, `max`, limiti, target o richiami normativi
* in lettura automatica iniziale NON calcolare in `acquisition` campi combinati assenti nel certificato
* campi come `Zr+Ti`, `Mn+Cr`, `Bi+Pb` si salvano se:
  - compaiono davvero nel certificato
  - oppure vengono costruiti nel workspace `Chimica` e confermati dall'utente come valori `calcolato`
* il `valore_grezzo` puo' contenere `%`, testo di riga o frammenti del certificato
* il `valore_standardizzato` e il `valore_finale` devono contenere solo il numero, senza `%`
* se il certificato contiene piu' analisi, piu' colate o piu' righe chimiche, va scelta solo quella coerente con la riga acquisition
* se questa coerenza non e' chiara, il blocco `chimica` non deve essere considerato robusto automaticamente

Origini ammesse rilevanti per il blocco `chimica`:

* `certificato`
* `utente`
* `calcolato`

Regola specifica workspace `Chimica`:

* `certificato` = valore letto dal caricamento automatico
* `utente` = valore inserito o corretto manualmente
* `calcolato` = valore derivato costruito nel workspace e confermato dall'utente

Unità implicita di sistema:

* per i valori chimici l'unita' implicita e' `%`
* l'unita' NON deve comparire nel valore mostrato in UI

* `id` (PK)
* `datimaterialeincoming_id` (FK)
* `elemento_id` (FK)
* `valore_grezzo`
* `valore_standardizzato`
* `valore_finale`
* `document_evidence_id` (o riferimento equivalente all'evidenza principale)
* `stato`

---

### 4.5 proprietacertificato

Valori di proprietà certificate letti dal certificato e associati alla riga acquisition.

* `id` (PK)
* `datimaterialeincoming_id` (FK)
* `proprieta_id` (FK)
* `valore`

---

### 4.6 fornitori (riferimento modulo esterno)

La gestione dei fornitori è definita in un modulo dedicato:

→ `docs/modules/fornitori.md`

Ogni riga acquisition è associata a un fornitore tramite:

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

* salvare elementi singoli solo se presenti come valori effettivi/misurati
* salvare composti/campi combinati SOLO se presenti esplicitamente nel certificato
* non inventare elementi non presenti
* non trasformare automaticamente righe `min` / `max` / target in valori acquisition
* non confondere valore misurato con limite documentale
* se esistono piu' righe chimiche, scegliere solo la riga coerente con la colata / cast / batch / charge corretta
* se la coerenza non e' sufficientemente forte, la chimica resta da verificare

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

* se presente nel certificato → usare valore salvato
* altrimenti:
  * se Zr e Ti presenti → Zr + Ti
  * altrimenti → NULL

Mn+Cr:

* se presente nel certificato → usare valore salvato
* altrimenti:
  * se Mn e Cr presenti → Mn + Cr
  * altrimenti → NULL

Bi+Pb:

* se presente nel certificato → usare valore salvato
* altrimenti:
  * se Bi e Pb presenti → Bi + Pb
  * altrimenti → NULL

Placeholder da chiudere:

* se il campo combinato e' presente nel certificato e anche gli elementi singoli sono presenti, va definita la regola di coerenza tra:
  * valore combinato esplicito del certificato
  * somma runtime degli elementi singoli
* se il campo combinato NON e' presente e compare solo uno dei due elementi singoli, il combinato resta `NULL`
* se uno o entrambi gli elementi singoli compaiono solo come `min` / `max` / limite e non come valore misurato, il combinato runtime resta `NULL`
* se il certificato presenta piu' righe analisi o piu' contesti chimici, la verifica di coerenza del combinato deve avvenire solo sulla riga chimica gia' scelta come corretta per la riga acquisition

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

Regola forte:

* questi derivati appartengono alla logica runtime / vista derivata
* NON devono riscrivere o sporcare il dato `acquisition` se il campo combinato non era presente nel certificato origine

---

## 7. Pipeline

DDT → creazione riga acquisition → ricerca/match certificato → validazione documentale → DB (`acquisition`)

Nota:

* la gestione dei certificati candidati, dello storico di match e della validazione di workflow appartiene ai moduli/documenti reader e knowledge
* questo file descrive il dato documentale finale raccolto nella riga acquisition

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

* `id` obbligatorio come PK tecnico
* `cdq` resta campo documentale critico
* `cdq` non deve essere modificato
* `cdq` non deve essere assunto come univoco assoluto della tabella
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
