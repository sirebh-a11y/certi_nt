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
* `docs/modules/fornitori.md`
* `docs/modules/overview.md`

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

Nota importante:

* il modulo `fornitori` non e' piu' solo in analisi
* e' gia' entrato in implementazione con DB, backend e frontend dedicati
* il reader documentale deve quindi riusare questo modulo come anagrafica master, senza aggiornarlo automaticamente dai PDF

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
* il fatto che il join reale passa da campi documentali critici come `cdq`, `colata`, ordine, codici profilo/cliente, `batch/charge` e peso netto

Quindi:

* il documento e' sorgente
* la riga incoming e' l'oggetto operativo

Placeholder di allineamento futuro:

* il workflow reader e la UI sono fortemente centrati sulla `riga incoming`
* il modello `acquisition` documentato oggi usa ancora una formulazione semplificata "una riga logica per `cdq`"
* questo punto dovra' essere riallineato in un passaggio successivo, senza forzarlo in questo draft

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
5. Il primo pilota deve partire con DDT e certificati insieme, con perimetro aperto a tutti i fornitori ma focus principale sui fornitori meglio strutturati presenti in `esempi_locali/3-certificati` fuori da `Vari`.
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
15. Il workflow DDT/certificati appartiene al reparto `quality`.
16. Gli altri reparti non devono svolgere il lavoro tecnico di caricamento, lettura, correzione e validazione documentale.
17. In futuro potra' esistere un passaggio successivo separato per `administration` sul certificato finale/prodotto.
18. Lo stato tecnico della riga e lo stato di workflow umano devono restare distinti.
19. Nello storico devono essere tracciati almeno:
   * utente di caricamento
   * utente di scelta/match
   * utente di modifica
   * utente di chiusura
20. Ogni evento storico deve avere almeno:
   * utente
   * timestamp
   * azione
   * blocco coinvolto
   * prima/dopo se c'e' modifica
21. Lo storico deve distinguere tra:
   * storico eventi
   * storico valori
22. Il motivo di modifica deve restare semplice, leggero e non bloccante.
23. Il principio guida della UX deve essere:
   * chiaro
   * semplice
   * robusto
   * veloce
   * non bloccante
24. L'analisi deve essere progressiva per blocchi, non monolitica.
25. La riga deve comparire subito in lista anche se ancora parziale.
26. La lista righe e' il cruscotto operativo principale del reparto `quality`.
27. I filtri minimi del cruscotto devono includere:
   * stato tecnico
   * stato workflow
   * priorita'
   * fornitore
   * presenza/mancanza certificato
   * presenza di rossi/gialli
28. Dal cruscotto l'utente deve poter entrare direttamente nel blocco critico.
29. Nel blocco si mostra prima l'evidenza e poi il dato proposto.
30. Per chimica e proprieta' va prevista una doppia vista:
   * crop/tabella
   * vista strutturata dei campi letti
31. La UI deve evidenziare soprattutto le anomalie; cio' che e' ok deve restare visivamente leggero.
32. La correzione manuale deve essere puntuale sul singolo campo/elemento.
33. La conferma deve poter essere sia puntuale sia a livello di blocco.
34. Un blocco confermato puo' essere riaperto se arriva nuova evidenza o cambia un dato correlato.
35. Quando un blocco viene riaperto, il sistema deve mostrare chiaramente il motivo della riapertura.
36. I messaggi in UI devono essere brevi, concreti e operativi.
37. Il pilota deve restare aperto a tutti i fornitori, con focus principale sui fornitori meglio strutturati presenti in `esempi_locali/3-certificati` fuori da `Vari`.
38. I casi difficili non devono essere esclusi dal pilota: devono entrare per far emergere le debolezze del sistema.
39. Il focus iniziale del pilota deve restare sui dati piu' importanti:
   * `cdq`
   * `colata`
   * dimensione
   * peso
   * match certificato
   * chimica
   * proprieta'
   * note
40. I dati operativi esterni possono esistere nel pilota, ma non devono definire il successo del reader.
41. Il successo del pilota deve essere misurato soprattutto su quanto bene supporta il lavoro del reparto `quality`, non sull'automazione pura.
42. Nel tempo il sistema dovra' rendere leggibili anche le debolezze ricorrenti, distinguendo almeno tra:
   * debolezze di lettura documentale
   * debolezze di standardizzazione
   * debolezze di mapping fornitore
   * debolezze di modello acquisition
43. Le debolezze ricorrenti e le forze ricorrenti osservate durante il pilota devono retroalimentare soprattutto i file knowledge:
   * `docs/modules/ddt_supplier_document_knowledge.md`
   * `docs/modules/certificates_supplier_document_knowledge.md`
44. Nei file knowledge queste osservazioni devono restare semplici, ricorrenti e utili, non diventare un catalogo di singoli casi isolati.
45. La regola concreta di aggregazione della riga acquisition non e' universale e deve essere capita nella fase knowledge leggendo insieme DDT e certificati, potendo dipendere da `batch`, `charge`, `colata` o altre combinazioni coerenti di materiale.

---

## 10. Semaforico e UX

Il semaforico non deve essere solo una decorazione grafica.

Deve essere una vista operativa della robustezza.

### 10.1 Semaforico per sezione

Ogni sezione deve poter mostrare almeno:

* verde -> pronto
* giallo -> da verificare
* rosso -> non pronto

Il semaforico deve sintetizzare due dimensioni interne:

* qualita' di lettura
* qualita' di coerenza / match

Verso l'utente il risultato deve restare semplice e non ambiguo.

### 10.2 Semaforico per riga

Ogni riga deve avere uno stato macroscopico che permetta all'utente di:

* capire cosa e' gia' valido
* capire cosa manca
* entrare nel dettaglio del blocco da correggere

### 10.3 Colore + etichetta + azione

Il solo colore non basta.

Il sistema dovrebbe mostrare sempre:

* colore semaforico
* etichetta breve
* azione chiara

Esempi:

* `OK`
* `Da verificare`
* `Mancante`

Con azioni del tipo:

* `Apri`
* `Correggi`
* `Conferma`

### 10.4 Regole semaforiche dei blocchi

#### DDT

* `Verde` -> la base DDT della riga e' pronta
* `Giallo` -> la base DDT esiste ma richiede verifica
* `Rosso` -> mancano i dati minimi per considerare pronta la base DDT

Nota:

* alcuni dati DDT possono arrivare da database esterno
* se sono robusti e bloccati, possono contribuire a portare il blocco verso il verde
* la provenienza deve comunque restare visibile

#### Match Certificato

* `Verde` -> esiste un match chiaro tra riga DDT e certificato corretto
* `Giallo` -> esistono candidati da verificare o scegliere
* `Rosso` -> non esiste ancora un match affidabile

Regola importante:

* il blocco `Match` diventa davvero verde solo quando il certificato e':
  * selezionato
  * confermato da `quality`

#### Chimica

* `Verde` -> chimica pronta
* `Giallo` -> chimica letta ma da verificare
* `Rosso` -> chimica non pronta

Regole pratiche:

* giallo se c'e' dubbio su uno o piu' elementi
* rosso se mancano elementi chiave o la lettura non e' utile

#### Proprieta'

* `Verde` -> proprieta' pronte
* `Giallo` -> proprieta' lette ma da verificare
* `Rosso` -> proprieta' non pronte

#### Note

* `Verde` -> blocco note preso in carico e validato
* `Giallo` -> note presenti o possibili, ma da verificare
* `Rosso` -> blocco note non ancora esaminato

Regola importante:

* il blocco `Note` e' obbligatorio nel workflow
* il contenuto puo' essere valorizzato, vuoto o `null`
* strategia e standardizzazione note restano un placeholder futuro in file dedicato

#### Validazione finale

La `Validazione finale` non e' un blocco semaforico normale come gli altri.

E' il passaggio finale di chiusura della riga e si puo' eseguire solo quando tutti i blocchi obbligatori sono verdi.

### 10.5 Semaforico globale della riga

Il semaforo globale della riga segue queste regole:

* `Verde` -> tutti i blocchi obbligatori sono verdi
* `Giallo` -> nessun rosso, ma almeno un blocco obbligatorio e' giallo
* `Rosso` -> almeno un blocco obbligatorio e' rosso

### 10.6 Correzione semplice

La UX dovra' permettere in futuro:

* visualizzazione del crop della tabella o del blocco
* selezione visiva di elemento e valore
* scrittura manuale quando necessario
* validazione esplicita del blocco

La semplicita' operativa e' parte integrante della strategia, non una rifinitura successiva.

### 10.7 Blocchi macro nella lista righe

Nel riepilogo riga i blocchi macro da mostrare sempre devono essere:

* `DDT`
* `Match Certificato`
* `Chimica`
* `Proprieta'`
* `Note`
* `Validazione finale`

Le `Note` sono un blocco obbligatorio nel workflow, ma il loro contenuto puo' essere vuoto o `null`.

Strategia e standardizzazione delle note restano un placeholder futuro da trattare in file dedicato.

### 10.8 Struttura costante del dettaglio blocco

Ogni blocco nel dettaglio riga dovrebbe seguire sempre lo stesso schema:

1. stato
2. motivo
3. evidenza
4. valore proposto
5. correzione manuale
6. conferma

### 10.9 Dettaglio del blocco `Match Certificato`

Il blocco `Match Certificato` deve mostrare in modo semplice:

* certificato selezionato o proposto
* altri candidati, se esistono
* motivo breve del match
* azione disponibile

Regole:

* quando esiste un candidato plausibile, il sistema deve proporre un candidato principale
* gli altri candidati devono restare pochi, ordinati e non dispersi
* per ogni candidato alternativo mostrare solo:
  * riferimento certificato
  * `cdq`
  * `colata`
  * fornitore
  * motivo breve

Azioni minime del blocco:

* conferma il match proposto
* scegli un altro candidato
* nessun certificato corretto

Regole operative aggiuntive:

* se l'utente sceglie `nessun certificato corretto`, il blocco resta aperto e la riga non e' chiudibile
* il blocco `Match` puo' essere confermato anche se `Chimica`, `Proprieta'` e `Note` non sono ancora chiuse
* la lettura/import preliminare di `Chimica`, `Proprieta'` e `Note` puo' avvenire anche prima della conferma del match
* la validazione di questi blocchi dipende pero' dal match confermato
* se il match cambia, i blocchi tecnici derivati dal certificato devono essere riaperti
* la lettura del certificato precedente non si perde, ma resta nello storico come candidato non piu' attivo

Provenienza candidati:

* il blocco deve mostrare anche la provenienza dei candidati
* nella prima versione basta una etichetta breve, per esempio:
  * `Upload utente`
  * `Archivio`
  * `Suggerito`
  * `AI`

Regola di cautela:

* un candidato suggerito da `AI` o da una proposta automatica debole deve essere presentato con maggiore cautela rispetto a un match documentale forte

Regola di spiegazione:

* il motivo del match deve essere breve e basato sui campi chiave che l'utente gia' conosce:
  * `cdq`
  * `colata`
  * dimensione
  * peso
  * fornitore

Esempi:

* `CDQ coincidente`
* `CDQ e colata coerenti`
* `Colata coerente, CDQ dubbio`
* `Fornitore coerente, piu candidati`

---

## 11. Card compatta della lista righe

La lista principale deve essere una vista alto livello:

* chiara
* semplice
* corta
* centrata sui `cdq`
* con dati mostrati in blocchi essenziali

La riga va pensata piu' come una **card compatta** che come una tabella classica densa.

### 11.1 Ordine di lettura della card

Ordine consigliato:

1. priorita'
2. stato tecnico riga
3. stato workflow quality
4. blocchi principali
5. azione

### 11.2 Dati minimi da mostrare

Nella card mostrare solo gli identificativi utili:

* fornitore
* id / riferimento riga
* `cdq`
* `colata`
* dimensione
* peso
* priorita'
* stato
* blocchi

### 11.3 Campi visivamente forti

`cdq` e `colata` devono avere evidenza visiva piu' forte degli altri campi, perche' sono il cuore del join DDT <-> certificato.

### 11.4 Fasce semplici della card

La card compatta deve includere:

#### Fascia 1

* `cdq`
* `colata`
* fornitore

#### Fascia 2

* dimensione
* peso
* id/riferimento riga

#### Fascia 3

* blocchi:
  * `DDT`
  * `Match`
  * `Chim.`
  * `Prop.`
  * `Note`
* priorita'
* stato tecnico
* stato workflow quality

### 11.5 Blocchi compatti

I blocchi nella card devono essere:

* compatti
* brevi
* cliccabili

Forma consigliata:

* piccoli badge / pill operative
* non pannelli grandi
* non testo lungo

Etichette sintetiche consigliate:

* `DDT`
* `Match`
* `Chim.`
* `Prop.`
* `Note`

### 11.6 Conferma utente nella card

Nella card il blocco deve far capire anche se e' stato confermato dall'utente.

Regola:

* il colore indica lo stato del blocco
* la conferma utente si mostra con un marker secondario semplice

La conferma non deve usare un altro colore, per non mescolare i significati.

### 11.7 Comportamento del click

Se un blocco nella card e' rosso o giallo:

* il click deve portare direttamente alla vista di correzione

Se un blocco e' verde e confermato:

* il click puo' aprire una vista piu' leggera di sola revisione

---

## 12. Cruscotto operativo

La lista righe deve essere il vero cruscotto operativo del reparto `quality`.

### 12.1 Presenza immediata della riga

La riga deve comparire subito in lista anche se ancora parziale.

### 12.2 Filtri minimi

Il cruscotto deve permettere almeno:

* filtro per stato tecnico
* filtro per stato workflow
* filtro per priorita'
* filtro per fornitore
* filtro per presenza/mancanza certificato
* filtro per presenza di rossi/gialli

### 12.3 Priorita' operativa

La lista righe deve avere anche una priorita' operativa semplice:

* Alta
* Media
* Bassa

Il colore dice lo stato.

La priorita' dice da cosa conviene partire.

La priorita' deve essere calcolata in modo semplice e prevedibile, non opaco.

Regole indicative iniziali:

* `Alta`
  * riga rossa
  * oppure match certificato mancante
  * oppure un solo ultimo blocco critico impedisce la chiusura
* `Media`
  * riga gialla con piu' verifiche aperte
* `Bassa`
  * riga verde
  * oppure riga quasi completata senza criticita' reali

### 12.4 Ingresso diretto nel blocco critico

Dal cruscotto l'utente deve poter entrare:

* nella riga completa
* oppure direttamente nel blocco critico

---

## 13. Workflow `quality` e storico

Tutta l'attivita' di:

* inserimento DDT
* caricamento certificati
* lettura
* correzione
* validazione blocchi
* validazione finale di riga

deve appartenere al reparto `quality`.

Gli altri reparti non devono svolgere questo lavoro tecnico.

### 13.1 Due stati distinti

Il sistema deve distinguere tra:

* stato tecnico della riga
* stato di workflow del reparto `quality`

Esempio di workflow umano:

* `Nuova`
* `In lavorazione`
* `Validata quality`
* `Riaperta`

### 13.2 Storico utenti

Lo storico deve tracciare almeno:

* chi ha caricato
* chi ha scelto il match
* chi ha modificato
* chi ha chiuso

### 13.3 Storico eventi e valori

Servono due livelli distinti:

* storico eventi
* storico valori

Per ogni evento minimo:

* utente
* timestamp
* azione
* blocco coinvolto
* prima/dopo se presente

### 13.4 Motivo di modifica

Il motivo di modifica deve esistere, ma in forma leggera:

* pochi motivi standard
* opzionale
* non deve rallentare l'utente

### 13.5 Storico minimo del primo rilascio

Nel primo rilascio lo storico deve restare leggero.

Eventi minimi da salvare:

* caricamento DDT
* caricamento certificato
* selezione/cambio match certificato
* modifica blocco
* conferma blocco
* chiusura finale riga
* riapertura riga o blocco

Campi minimi per evento:

* `riga_id`
* `blocco`
* `azione`
* `utente`
* `timestamp`
* `nota breve` opzionale

### 13.6 Storico valori minimo

Nel primo rilascio lo storico valori deve salvare solo i cambi manuali rilevanti fatti dall'utente.

Casi principali:

* cambio match certificato
* modifica di un valore chimico
* modifica di una proprieta'
* modifica di una nota
* modifica di un dato chiave DDT, se permessa nel workflow
* cambio di stato finale / chiusura

Campi minimi:

* `campo`
* `valore prima`
* `valore dopo`
* `utente`
* `timestamp`

Regola di leggerezza:

* non salvare tutto il rumore interno
* non duplicare crop o immagini
* lo storico rimanda all'evidenza gia' presente nel sistema

### 13.7 UI minima dello storico

Nel dettaglio riga lo storico deve essere:

* semplice
* consultabile
* cronologico inverso
* breve e leggibile

Nel primo rilascio non servono filtri avanzati.

Al massimo:

* mostra tutto
* mostra solo modifiche

---

## 14. UX di correzione e conferma

La UX deve essere:

* chiara
* semplice
* robusta
* veloce
* non bloccante

### 14.1 Analisi progressiva

L'analisi deve essere progressiva per blocchi, non monolitica e bloccante.

### 14.2 Doppia vista per i blocchi tabellari

Per `Chimica` e `Proprieta'` deve esistere:

* vista immagine/crop della tabella
* vista strutturata dei campi letti

### 14.3 Evidenza prima del dato

Quando l'utente entra in un blocco, il sistema deve mostrare prima:

1. evidenza
2. proposta automatica
3. eventuale mismatch o dubbio
4. correzione
5. conferma

### 14.4 Evidenziare le anomalie

Nella vista strutturata dei blocchi tabellari:

* i campi ok devono restare visivamente leggeri
* i campi dubbi, mancanti o incoerenti devono emergere subito

### 14.5 Correzione granulare

La correzione deve poter avvenire sul singolo campo/elemento.

### 14.6 Conferma granulare e aggregata

La conferma deve poter avvenire:

* sul singolo campo
* oppure sull'intero blocco

Il sistema deve distinguere tra:

* conferma senza modifiche
* conferma con correzione

E deve mantenere traccia di:

* proposta automatica
* correzione utente
* valore finale confermato

### 14.7 Riapertura controllata

Un blocco confermato puo' essere riaperto se:

* arriva nuova evidenza
* cambia il match
* cambia un dato correlato

Quando questo avviene, il sistema deve mostrare chiaramente il motivo della riapertura.

### 14.8 Messaggi brevi

I messaggi in UI devono essere brevi, concreti e operativi.

Esempi:

* `Manca certificato`
* `Chimica incompleta`
* `Possibile mismatch su Si`
* `Due certificati candidati`
* `Riaperto: modificato CDQ`

---

## 15. Campi documentali, operativi e calcolati

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

## 16. Strategia implementativa consigliata

Ordine consigliato:

1. mantenere e rafforzare i file knowledge per fornitore/template
2. progettare il reader come sistema di evidenze, non come parser cieco
3. fare nascere le righe incoming gia' dal DDT, anche senza certificato presente
4. gestire il join DDT <-> certificato come proposta assistita, non come match cieco definitivo
5. integrare OpenAI GPT-5.2 come supporto controllato e mascherato
6. costruire la UI di validazione/correzione
7. salvare storico strutturato
8. solo dopo ragionare su machine learning vero e proprio

Regole operative aggiuntive del pilota:

* il pilota deve accettare anche casi deboli o poco coperti, senza fingere di gestirli bene
* i casi dentro `Vari` devono essere inclusi, ma non sono il focus principale iniziale
* i casi difficili devono essere usati per capire dove il sistema e' debole
* il giudizio sul pilota deve concentrarsi sul supporto reale al lavoro `quality`
* punti forti e punti deboli ricorrenti devono essere riportati progressivamente nei file knowledge DDT e certificati

---

## 17. Domande aperte da chiarire con l'utente

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

3. Il pilota deve restare aperto a tutti i fornitori, ma va chiarito e mantenuto esplicito quali sono i fornitori principali da usare come focus iniziale di verifica e miglioramento, in particolare quelli presenti in `esempi_locali/3-certificati` fuori da `Vari`.

4. Il livello di crop/evidenza che vuoi conservare fin da subito deve essere chiarito meglio:
   * solo bounding box e testo
   * oppure anche immagine/crop della cella o del blocco

5. Va deciso quando una riga puo' considerarsi "utilizzabile" per il processo successivo:
   * solo dopo validazione completa
   * oppure anche in stato parziale per alcuni flussi interni

6. Va chiarito con quale forma rendere visibili nel tempo le debolezze ricorrenti del sistema, senza appesantire il primo rilascio:
   * per fornitore
   * per template
   * per blocco (`Match`, `Chimica`, `Proprieta'`, `Note`)
   * per tipo di problema (lettura, standardizzazione, mapping, acquisition)

7. Va chiarito quando iniziare ad aggiornare in modo sistematico i file knowledge con sezioni semplici del tipo:
   * `Punti forti osservati`
   * `Punti deboli osservati`
   * `Note per il reader`

---

## 18. Raccomandazione attuale

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

## 19. Prossimo passo consigliato

Dopo questo primo draft consolidato, il passo successivo consigliato e':

* chiarire le risposte alle domande aperte del punto 17
* esplicitare nel tempo i fornitori focus del pilota, senza chiudere il perimetro agli altri fornitori
* definire meglio il semaforico per blocchi e per riga
* definire la UI di validazione obbligatoria in modo semplice e chiaro
* definire una forma leggera per osservare le debolezze ricorrenti del sistema durante il pilota
* riportare progressivamente nei file knowledge solo osservazioni ricorrenti e davvero utili al reader

Solo dopo conviene disegnare in dettaglio:

* componenti software
* tabelle DB
* UI di revisione
* interazione precisa con il modulo acquisition
