# Document Reader Strategy — First Draft

## ⚠️ Stato del documento

Questo file e' un **primo draft di valutazione strategica**.

Non definisce ancora il design finale del lettore documentale.

Serve per:

* ragionare sulla strategia
* restare coerenti con i file knowledge gia' esistenti
* chiarire il ruolo degli strumenti
* separare cio' che serve subito da cio' che serve in futuro per machine learning

---

## ⚠️ Coerenza obbligatoria con i documenti esistenti

Questo draft deve restare coerente con:

* `docs/modules/ddt_supplier_document_knowledge.md`
* `docs/modules/certificates_supplier_document_knowledge.md`
* `docs/modules/ddt_certificates_data_acquisition.md`
* `docs/modules/engine_normative_standards.md`

In particolare deve rispettare queste scelte gia' fissate:

* i PDF di esempio servono prima di tutto per costruire **conoscenza documentale**
* DDT e certificati hanno template diversi per fornitore
* `cdq` e `colata` sono campi critici di collegamento
* i certificati contengono tabelle chimiche, tabelle di proprieta' certificate e note importanti
* i DDT possono contenere dati stampati e dati aggiunti manualmente
* il sistema non deve partire da estrazione cieca, ma da comprensione documentale
* i dati documentali, operativi e calcolati devono restare distinti

Questo draft NON sostituisce i file knowledge.

Li usa come base e prova a definire la strategia complessiva del futuro lettore.

---

## 1. Punto di partenza

I file knowledge esistenti descrivono gia' molto bene:

* come osservare i PDF reali
* come ragionare per fornitore e template
* come distinguere campi, tabelle, note, dati stampati e dati manuali
* come collegare DDT, certificati e acquisition

Quello che manca ancora e' un file ponte che dica:

* come trasformare questa conoscenza in un lettore reale dentro l'app
* quali strumenti usare
* quale ruolo dare a OpenAI GPT-5.2
* come costruire uno storico utile per machine learning
* come progettare una UI di correzione e validazione realmente usabile

Questo documento nasce per coprire quel ponte.

---

## 2. Obiettivo strategico consolidato

L'obiettivo NON dovrebbe essere:

* fare subito un parser AI generico
* far decidere tutto al modello
* arrivare subito al full-auto

L'obiettivo dovrebbe essere:

* costruire un lettore **evidence-first**
* capace di leggere documenti reali
* capace di generare righe incoming
* capace di restituire valore + prova + posizione
* capace di essere corretto dall'utente
* capace di accumulare storico utile per migliorare il sistema

Formula sintetica:

```plaintext
documento -> riga incoming -> evidenze -> proposta di lettura -> validazione -> storico
```

---

## 3. Strategia proposta

### 3.1 Livelli separati

Il sistema futuro dovrebbe essere separato in 4 livelli:

#### Livello A — Anagrafiche e conoscenza master

Gia' presenti o in corso:

* `fornitori`
* `fornitori_alias`
* knowledge DDT
* knowledge certificati

Questo livello definisce il contesto.

#### Livello B — Reader documentale runtime

Responsabile di:

* classificare il documento
* riconoscere fornitore e template
* trovare blocchi, tabelle, aree note
* generare candidati per i campi
* proporre i match tra DDT e certificati

Questo e' il lettore vero e proprio.

#### Livello C — Risoluzione del dato

Responsabile di:

* scegliere il valore finale
* distinguere misurato vs limite
* distinguere globale vs per riga/colata
* mantenere il legame con la prova documentale
* distinguere:
  * dato grezzo
  * dato standardizzato
  * dato validato finale

Questo livello e' cruciale per evitare estrazioni "magiche" non verificabili.

#### Livello D — Storico / apprendimento

Responsabile di salvare:

* cosa e' stato letto
* da dove
* con quale metodo
* con quale confidenza
* se l'utente ha confermato o corretto

Questo livello e' la base per il futuro machine learning.

---

## 4. Ruolo degli strumenti

### 4.1 Parsing deterministico

Il lettore non dovrebbe dipendere solo da OpenAI.

Serve un livello deterministico che usi:

* testo digitale del PDF quando disponibile
* OCR quando necessario
* coordinate / bounding box
* riconoscimento tabelle
* pattern per fornitore/template

Perche':

* e' piu' controllabile
* permette 1-to-1 reale tra campo letto e posizione
* produce prove riusabili

### 4.2 OpenAI GPT-5.2

OpenAI GPT-5.2 dovrebbe essere usato come **supporto di lettura forte**, ma non come unica fonte di verita'.

Ruoli consigliati:

* classificazione fornitore/template
* interpretazione di tabelle difficili
* lettura di note complesse
* disambiguazione di campi vicini
* ranking di piu' match candidati
* fallback nei casi sporchi o poco strutturati

Ruolo NON consigliato:

* produrre direttamente il dato finale senza prova documentale associata

### 4.3 Regola obbligatoria di masking prima di OpenAI

Prima di qualunque invio a ChatGPT/OpenAI devono essere mascherati in modo obbligatorio:

* i dati di `Forgialluminio 3`
* i dati aziendali del soggetto che emette il DDT
* i dati aziendali del soggetto che emette il certificato
* in generale tutti i dati identificativi aziendali non necessari alla lettura tecnica

Conseguenze:

* il canale preferito verso OpenAI deve essere il **crop mirato**
* l'invio del PDF intero o di pagine intere e' ammesso solo dopo mascheratura obbligatoria
* il sistema deve tracciare se la lettura OpenAI e' avvenuta su:
  * crop mascherato
  * pagina mascherata
  * documento mascherato

Il masking non e' una best practice facoltativa.

E' un requisito di pipeline.

### 4.4 Validazione umana

Nella fase iniziale il sistema dovrebbe prevedere sempre la possibilita' di:

* confermare
* correggere
* rifiutare
* aggiungere note

Questa parte non e' un "extra".

E' il modo corretto per costruire uno storico di qualita'.

La conferma utente deve essere **mandatory** sui vari blocchi funzionali.

---

## 5. Miglioramenti di interazione con i file knowledge

### 5.1 Miglioramento rispetto al file DDT knowledge

Il file DDT knowledge spiega bene:

* `cdq` manuale
* legame riga materiale -> peso -> `cdq`
* distinzione stampato/manuale

Miglioramento strategico proposto:

* il lettore runtime deve salvare ogni candidato `cdq` con:
  * pagina
  * area
  * metodo di lettura
  * relazione alla riga materiale

In questo modo la conoscenza DDT non resta solo descrittiva, ma diventa base operativa del reader.

### 5.2 Miglioramento rispetto al file certificati knowledge

Il file certificati knowledge spiega bene:

* presenza tabelle chimiche
* presenza tabelle proprieta'
* distinzione valori misurati vs `min/max`
* importanza delle note

Miglioramento strategico proposto:

* il lettore runtime deve poter salvare per ogni tabella:
  * posizione
  * struttura osservata
  * celle o blocchi sorgente
  * interpretazione finale

In particolare:

* chimica e proprieta' certificate non dovrebbero essere salvate solo come valore finale
* dovrebbero avere anche una evidenza tabellare tracciabile

### 5.3 Miglioramento comune

I file knowledge oggi sono molto forti sul piano documentale.

Il miglioramento da introdurre in futuro e' aggiungere una vista comune basata su:

* `document_type`
* `fornitore_id`
* `template_id`
* `field_name`
* `field_evidence`
* `field_resolution`
* `section_status`
* `row_status`

Questo permette di:

* trattare DDT e certificati in modo coerente
* non forzare un parser unico troppo presto
* costruire uno storico uniforme

---

## 6. Principio 1-to-1

Se l'obiettivo include anche uno storico utile per machine learning, il sistema deve garantire una corrispondenza il piu' possibile 1-to-1 tra:

* dato finale
* evidenza letta
* posizione nel documento

Per ogni campo estratto il sistema dovrebbe poter salvare almeno:

* documento sorgente
* pagina
* bounding box o area logica
* testo o crop associato
* metodo di lettura
  * PDF text
  * OCR
  * table parser
  * pattern/template
  * OpenAI GPT-5.2
  * operatore
* confidenza
* valore grezzo
* valore normalizzato
* stato
  * proposto
  * confermato
  * corretto
  * rifiutato

Per la strategia corrente, il livello 1-to-1 deve puntare almeno a:

* testo o valore osservato
* posizione
* crop o area visiva quando utile

Questo vale in modo particolare per:

* `cdq`
* `colata`
* tabella chimica
* tabella proprieta'
* note

Senza questo livello, il futuro machine learning rischia di basarsi su dati non spiegabili.

---

## 7. Strategia di apprendimento futuro

Il machine learning NON dovrebbe essere il primo obiettivo implementativo.

Prima viene:

* conoscenza documentale
* lettura tracciabile
* validazione
* storico strutturato

Solo dopo ha senso usare lo storico per:

* classificazione template
* suggerimento campi
* ranking delle ipotesi
* miglioramento OCR / table understanding
* confronto tra letture automatiche e conferme utente

Formula consigliata:

```plaintext
knowledge first
reader second
learning third
```

Questa sequenza resta coerente anche con il fatto che:

* l'utente dovra' confermare i blocchi
* le correzioni devono essere semplici
* il sistema deve costruire uno storico utile, non solo una lettura immediata

---

## 8. Strutture concettuali da prevedere

Senza ancora definire il DB finale, questo draft suggerisce di ragionare almeno su alcuni oggetti concettuali.

### 8.1 Document

Rappresenta il PDF caricato e il suo contesto.

### 8.2 Incoming row

La vera unita' operativa del sistema deve essere la **riga incoming**.

Questa decisione e' coerente con:

* `ddt_certificates_data_acquisition.md`
* il fatto che il DDT crea una o piu' righe
* il fatto che uno o piu' certificati completano la riga
* il fatto che il join reale passa da `cdq`, `colata`, peso e dimensione

Quindi:

* il documento e' sorgente
* la riga incoming e' l'oggetto operativo

### 8.3 Field evidence

Rappresenta la prova osservata nel documento.

Esempi:

* testo in intestazione
* cella tabella chimica
* riga proprieta'
* nota
* annotazione manuale

### 8.4 Field resolution

Rappresenta il valore finale deciso dal sistema o confermato dall'utente.

### 8.5 Section status

Ogni riga deve essere composta da sezioni funzionali con stato autonomo, per esempio:

* DDT
* match certificato
* chimica
* proprieta'
* note
* dati operativi

Ogni sezione deve avere:

* robustezza
* stato semaforico
* evidenze
* correzioni
* validazione

### 8.6 Row status

Ogni riga deve avere anche uno stato globale.

La riga non si considera chiusa solo perche' alcune sezioni sono verdi.

Serve una validazione finale obbligatoria di riga.

---

## 9. Decisioni strategiche gia' fissate

Questo draft consolida anche le decisioni gia' emerse nel confronto:

1. Una riga incoming nasce subito dal DDT, anche se il certificato non e' ancora stato caricato.
2. Se ci sono piu' certificati candidati per la stessa riga, il sistema deve proporre piu' match.
3. Il semaforico deve riflettere sia la qualita' della lettura sia la qualita' del match.
4. La standardizzazione avviene dopo il salvataggio del grezzo con evidenza.
5. Il primo pilota deve partire con DDT e certificati insieme, ma su pochi fornitori selezionati.
6. OpenAI GPT-5.2 e' un supporto forte ma non il motore unico della prima versione.
7. Prima di qualunque invio a OpenAI i dati aziendali di `Forgialluminio 3` e dell'emittente del documento devono essere mascherati obbligatoriamente.
8. La validazione deve esistere per sezione e anche come validazione finale di riga.
9. Il sistema deve tenere sempre distinti:
   * dato letto grezzo
   * dato standardizzato
   * dato validato finale
10. Le note sono una sezione autonoma importante, non testo accessorio.
11. I campi devono essere separati tra:
   * documentali
   * operativi/processo
   * calcolati
12. Per i campi operativi e calcolati deve essere salvata anche la provenienza del dato.
13. La prima versione deve essere assistita, non full-auto.
14. La conferma utente dei blocchi e' mandatory, ma la UI deve restare semplice e chiara.

---

## 10. Semaforico e UX

Il semaforico non deve essere solo una decorazione grafica.

Deve essere una vista operativa della robustezza.

### 10.1 Semaforico per sezione

Ogni sezione deve poter mostrare almeno:

* verde -> lettura robusta e coerente
* giallo -> lettura debole, dubbia o mismatch parziale
* rosso -> dato mancante, non leggibile o mismatch grave

### 10.2 Semaforico per riga

Ogni riga deve avere uno stato macroscopico che permetta all'utente di:

* capire cosa e' gia' valido
* capire cosa manca
* entrare nel dettaglio del blocco da correggere

### 10.3 Correzione semplice

La UX dovra' permettere in futuro:

* visualizzazione del crop della tabella o del blocco
* selezione visiva di elemento e valore
* scrittura manuale quando necessario
* validazione esplicita del blocco

La semplicita' operativa e' parte integrante della strategia, non una rifinitura successiva.

---

## 11. Campi documentali, operativi e calcolati

Questo punto deve restare coerente con `ddt_certificates_data_acquisition.md`.

### 11.1 Documentali

Esempi:

* dati letti da DDT
* dati letti da certificato
* chimica
* proprieta'
* note documento

### 11.2 Operativi / processo

Esempi:

* data ricezione
* data accettazione
* accettazione materiale
* dati inseriti da utente
* dati importati da database esterno

### 11.3 Calcolati

Esempi:

* ritardo
* altri conti o indicatori applicativi

Queste tre famiglie devono convivere sulla stessa riga, ma non devono essere confuse tra loro.

Per dati operativi e calcolati deve essere tracciata anche la provenienza:

* utente
* db esterno
* combinazione
* calcolo app

---

## 12. Strategia implementativa consigliata

Ordine consigliato:

1. mantenere e rafforzare i file knowledge per fornitore/template
2. progettare il reader come sistema di evidenze, non come parser cieco
3. fare nascere le righe incoming gia' dal DDT, anche senza certificato presente
4. gestire il join DDT <-> certificato come proposta assistita, non come match cieco definitivo
5. integrare OpenAI GPT-5.2 come supporto controllato e mascherato
6. costruire la UI di validazione/correzione
7. salvare storico strutturato
8. solo dopo ragionare su machine learning vero e proprio

---

## 13. Domande aperte da chiarire con l'utente

Questo e' il punto in cui servono chiarimenti sulle intenzioni finali del progetto.

Dubbi aperti da chiarire insieme:

1. Lo storico per machine learning deve servire soprattutto a:
   * migliorare riconoscimento template
   * migliorare estrazione campi
   * migliorare interpretazione di tabelle e note
   * tutte e tre le cose, ma con priorita' da definire

2. Le note documento devono diventare nel tempo:
   * solo contenuto consultabile
   * oppure anche oggetto strutturato da usare nelle decisioni di acquisizione?

3. Il primo set di fornitori pilota va deciso in modo esplicito:
   * quali sono i 2-3 fornitori migliori da usare per il primo reader?

4. Il livello di crop/evidenza che vuoi conservare fin da subito deve essere chiarito meglio:
   * solo bounding box e testo
   * oppure anche immagine/crop della cella o del blocco

5. Va deciso quando una riga puo' considerarsi "utilizzabile" per il processo successivo:
   * solo dopo validazione completa
   * oppure anche in stato parziale per alcuni flussi interni

---

## 14. Raccomandazione attuale

La raccomandazione attuale di questo draft e':

* non partire da "AI che legge tutto"
* partire da "sistema che salva prove, decisioni e correzioni"

Questa scelta e':

* coerente con i file knowledge esistenti
* coerente con il bisogno di 1-to-1
* coerente con l'obiettivo futuro di machine learning
* piu' solida di un parser interamente affidato al modello
* coerente con una UX semaforica e validata blocco per blocco

---

## 15. Prossimo passo consigliato

Dopo questo primo draft consolidato, il passo successivo consigliato e':

* chiarire le risposte alle domande aperte del punto 13
* decidere il primo gruppo di fornitori pilota
* definire meglio il semaforico per blocchi e per riga
* definire la UI di validazione obbligatoria in modo semplice e chiaro

Solo dopo conviene disegnare in dettaglio:

* componenti software
* tabelle DB
* UI di revisione
* interazione precisa con il modulo acquisition
