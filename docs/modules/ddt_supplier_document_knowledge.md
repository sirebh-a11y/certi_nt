# DDT Supplier Document Knowledge Module

## ⚠️ IMPORTANTE — POSIZIONAMENTO NEL PROGETTO

Questo modulo NON fa parte del core del sistema.

Deve essere implementato dopo la stabilizzazione del core, tramite prompt Codex dedicato.

Questo modulo NON implementa parsing runtime dei PDF.

Questo modulo serve a costruire una base di conoscenza dei documenti DDT dei fornitori, utilizzando i PDF esempio come materiale di analisi.

L’output attuale del modulo è conoscenza documentale strutturata, NON codice di estrazione.

---

## ⚠️ IMPORTANTE — COERENZA CON IL SISTEMA

Questo modulo deve essere coerente con:

* `docs/modules/ddt_certificates_data_acquisition.md`
* `docs/modules/fornitori.md`

In particolare:

* `cdq` è la chiave principale del sistema
* `cdq` può essere presente sul DDT, anche scritto a mano
* `colata` è un identificativo materiale critico
* il DDT non è solo documento del fornitore, ma anche documento arricchito internamente dall’incoming

Questo modulo NON definisce la struttura finale dei dati acquisiti.
Definisce la conoscenza necessaria per capire come riconoscerli nei DDT reali.

Questa conoscenza deve servire anche a:

* unire correttamente DDT e certificati nella raccolta dati documentale
* supportare il popolamento coerente del modulo `ddt_certificates_data_acquisition`
* descrivere il lato DDT del legame documentale che porta alla futura riga acquisition

---

## 1. Scopo

Utilizzare i PDF DDT presenti nella cartella:

```plaintext
esempi_locali/4-ddt
```

e in tutte le sue sottocartelle fornitore/template.

Regola operativa obbligatoria:

* l'analisi deve essere eseguita sulla cartella specifica del dominio documentale
* l'analisi NON deve fermarsi ai file presenti nella root della cartella
* le sottocartelle fornitore fanno parte del dataset reale da analizzare

per:

* comprendere la struttura reale dei DDT dei fornitori
* identificare pattern ricorrenti per fornitore
* distinguere dati stampati e dati aggiunti manualmente
* capire dove si trovano i dati chiave
* definire regole documentali di riconoscimento
* costruire una base di conoscenza documentale strutturata
* contribuire al corretto collegamento tra riga DDT e certificato corretto
* contribuire alla raccolta dati finale del modulo `ddt_certificates_data_acquisition`

---

## 2. Principio fondamentale

Il sistema NON deve partire cercando di estrarre dati in modo cieco.

Deve prima costruire conoscenza documentale.

Flusso corretto:

```plaintext
PDF esempi → analisi documentale → pattern → regole → base di conoscenza
```

Questo modulo serve a far sì che Codex capisca:

* come sono fatti i DDT
* come cambiano tra fornitori
* dove stanno i campi importanti
* come collegare i DDT ai certificati

---

## 3. Ruolo di Codex

Codex deve comportarsi come un analista documentale e non come un parser.

Per ogni PDF deve:

1. identificare il fornitore
2. analizzare la struttura del documento
3. individuare sezioni e blocchi principali
4. capire come sono rappresentati i dati chiave
5. identificare campi stampati e campi aggiunti manualmente
6. riconoscere pattern ricorrenti
7. formalizzare la conoscenza in regole strutturate
8. preparare una base di conoscenza riutilizzabile in futuro

Codex NON deve:

* implementare ora il parser runtime
* inventare dati mancanti
* applicare logiche normative
* calcolare valori
* implementare ora teach operatore
* implementare ora machine learning
* produrre ora codice finale di parsing

---

## 4. Identificazione fornitore

Codex deve:

* leggere il nome del fornitore dal documento
* confrontarlo con:

  * `fornitori`
  * `fornitori_alias`

Output atteso:

* `fornitore_raw`
* `fornitore_id` (se riconosciuto)

Vincolo:

* questo modulo può aiutare il mapping del fornitore
* ma NON deve aggiornare automaticamente l'anagrafica del fornitore
* ogni modifica dell'anagrafica appartiene al modulo `fornitori`

Il nome del dataset o del foglio storico può essere un indizio utile di contesto, ma NON sostituisce il mapping strutturato verso `fornitore_id`.

Se il fornitore non è riconosciuto:

* NON deve essere inventato
* può restare non mappato
* deve essere segnalato come nuovo caso/template futuro

---

## 5. Concetto di template

Un template rappresenta:

* un layout specifico di DDT
* associato a un fornitore
* con regole coerenti di naming, posizione e struttura

Un fornitore può avere più template.

Codex deve:

* raggruppare documenti simili
* distinguere template diversi dello stesso fornitore
* descrivere per ogni template:

  * sezioni
  * campi
  * pattern
  * varianti

---

## 6. Cosa deve essere compreso nei DDT

Codex NON deve solo trovare valori.
Deve capire:

* come riconoscerli
* dove si trovano
* come si presentano
* come cambiano tra documenti e fornitori
* come si collegano ai certificati

---

### 6.1 Dati documento

* numero documento
* data documento
* tipo documento

---

### 6.2 Dati fornitore

* nome fornitore
* posizione nel documento
* eventuale area intestazione

---

### 6.3 Dati ordine

* numero ordine
* riferimento cliente
* eventuali codici ordine interni/esterni

---

### 6.4 Dati trasporto

* numero colli
* peso lordo
* peso netto

---

### 6.5 Righe materiale

Per ogni riga materiale comprendere la presenza e la forma di:

* descrizione materiale
* lega
* dimensione (diametro / lunghezza / altra misura)
* quantità
* peso riga
* eventuali codici articolo
* eventuali codici cliente

---

### 6.6 Identificativi tecnici

Campi critici da comprendere:

* colata
* CDQ
* codici materiale
* eventuale stato materiale
* eventuale norma
* eventuale tipo prodotto

---

## 7. ⚠️ Dati aggiunti manualmente (CRITICI)

Nei DDT reali, l’ufficio incoming aggiunge spesso a mano informazioni fondamentali.

Questi dati NON fanno parte del documento originale del fornitore, ma sono essenziali per il sistema.

Esempi:

* `cdq` scritto a mano
* `colata` scritta a mano
* annotazioni operative
* appunti di ricezione o collegamento

Questi dati devono essere trattati come:

* validi
* significativi
* centrali per la tracciabilità

NON devono essere trattati come rumore OCR.

---

## 8. ⚠️ CDQ — CASO PIÙ IMPORTANTE

Il `cdq` scritto a mano NON deve essere trattato come campo globale del documento.

Nel caso reale, il `cdq` può essere:

* scritto a mano
* ripetuto più volte nello stesso DDT
* associato a righe materiale diverse

### Regola fondamentale

Possono esistere più `cdq` nello stesso DDT.

Ogni `cdq` è associato alla specifica riga materiale a cui si riferisce.

Il legame reale da comprendere è:

```plaintext
riga materiale → peso riga → CDQ
```

### Posizione tipica

Il `cdq` manuale si trova spesso:

* vicino al peso della riga materiale
* nella stessa area visiva della riga
* accanto o vicino ai dati principali del materiale
* non necessariamente in una colonna ufficiale stampata

### Conseguenza per Codex

Codex deve capire che:

* `cdq` può essere multiplo nello stesso documento
* NON va interpretato come metadato unico del DDT
* deve essere associato alla singola riga materiale corretta
* il riferimento spaziale/visivo vicino al peso è fondamentale

### Conseguenza per il sistema

Questa conoscenza serve per alimentare correttamente il modulo di acquisition, dove:

* `cdq` è campo documentale critico di tracciabilità e collegamento
* una riga logica di acquisizione corrisponde al materiale corretto
* il collegamento DDT ↔ certificato dipende da questa associazione

Più in generale:

* il knowledge DDT e il knowledge certificati devono lavorare insieme
* il loro obiettivo comune non è solo descrivere i documenti, ma permettere che i due documenti confluiscano nella stessa raccolta dati acquisition

---

## 9. ⚠️ Colata — caso critico

La `colata` è un identificativo materiale fondamentale.

Può essere:

* stampata
* scritta a mano
* rappresentata con sinonimi:

  * lot
  * charge
  * heat

Codex deve:

* riconoscere questi sinonimi
* capire se la colata è per documento o per riga
* distinguere i casi in cui è associata alla riga materiale
* formalizzare il legame con il certificato

La `colata`, insieme al `cdq`, è una delle chiavi più importanti di collegamento reale tra DDT e certificato.

---

## 10. Match reale DDT ↔ certificato

Il collegamento corretto NON è:

```plaintext
DDT documento -> certificato documento
```

Il collegamento corretto è:

```plaintext
riga materiale del DDT -> certificato corretto o certificati candidati
```

### 10.1 Primo legame forte

Il primo legame da comprendere è il soggetto che emette i documenti:

* il DDT e il certificato devono appartenere allo stesso fornitore/emittente
* questo è il primo vincolo di coerenza prima di valutare i campi tecnici

Esempio osservato:

* `Aluminium Bozen / Aluminium Bz - Sapa Bz`

### 10.2 Campi forti di match da ricercare nel DDT

Per ogni riga materiale Codex deve ricercare e descrivere, quando presenti:

* numero certificato riportato sul DDT (`Cert. n°` o varianti)
* `cdq` associato alla riga
* `colata`
* codice profilo / codice cliente
* descrizione profilo / materiale
* misura nominale (esempio: diametro)
* lega e stato fisico
* riferimento ordine
* `cast` / `batch` / `charge` se presente
* peso netto della riga o del blocco coerente

### 10.3 Gerarchia pratica del match

Nel caso reale il match verso il certificato corretto deve essere cercato con una logica di priorità, per esempio:

1. stesso fornitore/emittente
2. numero certificato riportato sul DDT, se presente
3. coerenza tra codice profilo / codice cliente
4. coerenza tra misura nominale
5. coerenza tra lega e stato fisico
6. coerenza tra ordine
7. coerenza tra `cast` / `batch` / `charge`
8. coerenza tra peso netto

### 10.4 Varianti e scritture deboli

Questi campi non devono essere confrontati in modo cieco.

Codex deve osservare e registrare:

* piccole varianti di scrittura
* spazi mancanti o aggiunti
* trattini e slash
* inversione o trasposizione parziale di cifre
* acronimi diversi per lo stesso concetto

Questo vale in particolare per:

* ordine
* `cast`
* `batch`
* `charge`
* codici profilo / cliente

### 10.5 Peso netto come controllo di coerenza

Il peso netto è un campo importante di collegamento tra riga DDT e certificato.

Non deve essere trattato come chiave unica, ma come controllo forte di coerenza.

Regola:

* se il peso netto del certificato è coerente con il peso netto della riga o del blocco DDT, il match si rafforza

### 10.6 Placeholder eccezioni per fornitore

Le eccezioni di match non vanno hardcodate in astratto.

Devono essere analizzate per fornitore/template.

Esempio già noto:

* `Leichtmetall`
  * il peso effettivo da confrontare può richiedere la somma dei pesi di più righe dello stesso `batch`
* `Impol`
  * il peso effettivo può essere ricostruito sulla stessa `charge`
  * il DDT può già riportare la somma dei kg netti per `charge`

Regola più generale:

* il criterio corretto per capire quando più righe o colli del DDT rappresentano una sola riga acquisition NON è universale
* può dipendere da `batch`, `charge`, `colata` o da altre combinazioni coerenti di materiale
* questo criterio non va capito leggendo solo il DDT
* deve essere capito leggendo insieme DDT e certificati dello stesso fornitore/template

Placeholder da mantenere per ciascun fornitore/template:

```plaintext
Eccezioni di match DDT-certificato
- uso del peso: diretto / somma / altro
- uso del batch/cast/charge: obbligatorio / secondario / assente
- criterio di aggregazione della riga acquisition: per riga / per batch / per charge / per colata / altro
- uso dell'ordine: forte / medio / debole
- varianti frequenti di scrittura
- casi noti di mismatch apparente
```

Queste eccezioni devono essere aggiornate caso per caso nei file knowledge, non inventate in anticipo.

---

## 11. Distinzione obbligatoria: dati stampati vs dati manuali

Codex deve sempre distinguere tra:

### Dati stampati dal fornitore

Esempi:

* numero documento
* data
* fornitore
* righe materiale stampate
* codici, pesi, colli

### Dati aggiunti manualmente dall’incoming

Esempi:

* `cdq`
* `colata`
* note operative
* eventuali marcature a penna

Questa distinzione deve essere esplicita nella base di conoscenza.

---

## 12. Regole da derivare

Per ogni campo rilevante Codex deve definire:

### 12.1 Pattern testuali

Esempi:

```plaintext
col = lot = charge = heat
Ø = diameter = D=
```

### 11.2 Posizione

* vicino a quali parole chiave
* in quale blocco del documento
* in tabella o in testo libero
* se stampato o scritto a mano

### 11.3 Struttura

* tabella
* intestazione
* blocco testo
* margine
* area annotazioni

### 11.4 Relazione con altri campi

Esempi:

* `cdq` vicino al peso riga
* `colata` vicino a descrizione o peso
* dimensione dentro descrizione materiale
* lega dentro descrizione o colonna separata

### 11.5 Variabilità

* differenze tra fornitori
* differenze tra template dello stesso fornitore
* differenze tra campi stampati e manuali

---

## 12. Output atteso da Codex

Codex NON deve produrre codice di estrazione.

Deve produrre conoscenza strutturata.

Il primo deliverable del modulo è una knowledge base documentale, non un parser runtime.

Esempio concettuale:

```plaintext
fornitore: X

template: T1

campo: colata
- sinonimi: lot, charge, heat
- tipo: stampato
- posizione: tabella principale
- relazione: vicino alla descrizione materiale

campo: cdq
- tipo: manuale
- posizione: vicino al peso della riga
- cardinalità: multiplo nello stesso DDT
- relazione: associato alla singola riga materiale
```

---

## 13. Persistenza (base dati di conoscenza)

Il sistema deve essere progettato per salvare in modo strutturato:

* fornitori
* template
* campi
* pattern
* esempi documento
* relazioni tra campi
* distinzione stampato/manuale

Strutture suggerite:

* `document_templates`
* `template_fields`
* `field_patterns`
* `template_examples`

Queste strutture devono essere pensate per:

* estensione futura
* revisione umana
* utilizzo operativo come base di conoscenza

Teach operatore e machine learning sono estensioni future, NON obiettivi del rilascio iniziale di questo modulo.

---

## 14. Vincoli

* NON inventare dati
* NON applicare logica normativa
* NON calcolare valori
* NON implementare parsing runtime
* NON assumere che il `cdq` sia unico per documento
* NON assumere che il `cdq` sia sempre stampato
* NON assumere che `colata` e `cdq` siano globali e non di riga

---

## 15. Integrazione con altri moduli

### Fornitori Module

Utilizzare:

* `fornitore_id`
* `fornitori_alias`

### Certificates Data Acquisition Module

Questo modulo deve essere coerente con il fatto che:

* `cdq` è campo documentale critico di tracciabilità e collegamento
* `colata` è campo critico
* `datimaterialeincoming` rappresenta i dati reali da documento

Le regole prodotte qui serviranno per guidare l’acquisizione futura e l’associazione corretta tra:

* riga materiale
* peso
* colata
* `cdq`

---

## 16. Estensione futura (CRITICA)

### 16.1 Teach operatore (NON ORA)

Il sistema deve essere progettato per supportare in futuro:

* inserimento manuale regole
* correzione mapping
* onboarding nuovi fornitori
* insegnamento della relazione tra riga, peso, colata e `cdq`

### 16.2 Machine Learning (NON ORA)

La base dati deve essere pensata per supportare in futuro:

* classificazione template
* riconoscimento layout
* suggerimento campi
* riconoscimento di campi manuali
* miglioramento automatico

Per questo motivo:

* i dati devono essere strutturati
* i documenti devono essere collegati alle regole
* le relazioni tra campi devono essere esplicite
* deve essere distinguibile ciò che è stampato da ciò che è scritto a mano

Queste estensioni NON fanno parte dello scope attuale del modulo.

---

## 17. Obiettivo finale

Costruire un sistema:

* guidato dalla conoscenza
* basato su documenti reali
* coerente con il modulo di acquisition
* capace di capire fornitori e template
* capace di riconoscere correttamente i campi critici
* robusto su dati stampati e manuali
* evolvibile verso teach operatore e machine learning
