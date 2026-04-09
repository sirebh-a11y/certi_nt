# Certificates Supplier Document Knowledge Module

## ⚠️ IMPORTANTE — POSIZIONAMENTO NEL PROGETTO

Questo modulo NON fa parte del core del sistema.

Deve essere implementato dopo la stabilizzazione del core, tramite prompt Codex dedicato.

Questo modulo NON implementa parsing runtime dei PDF.

Questo modulo serve a costruire una base di conoscenza dei certificati dei fornitori, utilizzando i PDF esempio come materiale di analisi.

L'output attuale del modulo è conoscenza documentale strutturata, NON codice di estrazione.

---

## ⚠️ IMPORTANTE — COERENZA CON IL SISTEMA

Questo modulo deve essere coerente con:

* `docs/modules/ddt_certificates_data_acquisition.md`
* `docs/modules/fornitori.md`
* `docs/modules/ddt_supplier_document_knowledge.md`

In particolare:

* `cdq` è la chiave principale del sistema
* `colata` è un identificativo materiale critico
* `lega_base`, `lega_designazione` e `variante_lega` devono restare coerenti con il modello acquisition
* le proprietà certificate devono restare coerenti con il vocabolario e le categorie del sistema

Questo modulo NON definisce la struttura finale dei dati acquisiti.
Definisce la conoscenza necessaria per capire come riconoscerli nei certificati reali.

Questa conoscenza deve servire anche a:

* unire correttamente certificati e DDT nella raccolta dati documentale
* supportare il popolamento coerente del modulo `ddt_certificates_data_acquisition`
* descrivere il lato certificato del legame documentale che completa la futura riga acquisition

---

## 1. Scopo

Utilizzare i PDF certificati presenti nella cartella:

```plaintext
esempi_locali/3-certificati
```

e in tutte le sue sottocartelle fornitore/template.

Regola operativa obbligatoria:

* l'analisi deve essere eseguita sulla cartella specifica del dominio documentale
* l'analisi NON deve fermarsi ai file presenti nella root della cartella
* le sottocartelle fornitore fanno parte del dataset reale da analizzare

per:

* comprendere la struttura reale dei certificati dei fornitori
* identificare pattern ricorrenti per fornitore
* distinguere template diversi dello stesso fornitore
* capire dove si trovano i dati chiave
* definire regole documentali di riconoscimento
* costruire una base di conoscenza documentale strutturata
* contribuire al corretto collegamento tra certificato e riga DDT corretta
* contribuire alla raccolta dati finale del modulo `ddt_certificates_data_acquisition`

---

## 1.1 Regola di lettura del dataset

I file presenti direttamente nella root di:

```plaintext
esempi_locali/3-certificati
```

NON devono essere assunti automaticamente come dataset principale di lavoro.

Il dataset reale di analisi deve essere cercato prima di tutto nelle sottocartelle per fornitore e nelle eventuali sottocartelle dedicate ai certificati di origine o a famiglie specifiche di documenti.

Conseguenze:

* la lettura deve partire dalla cartella `3-certificati` e proseguire ricorsivamente nelle sottocartelle
* il nome della sottocartella fornitore è un indizio utile di contesto
* il file va preparato per descrivere template reali per fornitore, non solo file isolati della root

---

## 1.2 Prime osservazioni da certificati reali letti

Una prima lettura diretta di certificati reali nelle sottocartelle fornitore ha già mostrato pattern utili.

Campione osservato in modo affidabile:

* `esempi_locali/3-certificati/Aluminium Bz - Sapa Bz/CQF_ 19116_608255_2017.pdf`
* `esempi_locali/3-certificati/Aluminium Bz - Sapa Bz/CQF_ 69556_6082H70_2020.pdf`
* `esempi_locali/3-certificati/Leichtmetall A/CQF_1856A_2015.pdf`
* `esempi_locali/3-certificati/Leichtmetall A/CQF_1899B_2015.pdf`

Osservazioni già confermate:

* esistono template per fornitore chiaramente diversi
* nei certificati letti sono presenti vere tabelle chimiche
* nei certificati letti sono presenti vere tabelle di proprietà certificate
* le note del certificato sono presenti e stanno in un'area documentale riconoscibile
* `cdq` e `charge / colata` compaiono in posizioni tecnicamente centrali

Osservazioni specifiche emerse:

### Template osservato: Aluminium Bz - Sapa Bz

* layout multilingua
* intestazione strutturata con dati documento, cliente, articolo, peso netto, lega e stato fisico
* tabella chimica con:

  * una riga di valori misurati per colata
  * righe separate `min` e `max`
  * elementi distribuiti orizzontalmente in molte colonne

* tabella proprietà certificate con colonne osservate:

  * `Rm`
  * `Rp0.2`
  * `A5%`
  * `HB`
  * conducibilità

* presenza di timbri o annotazioni nell'area bassa del certificato, anche sovrapposti alla zona delle proprietà

### Template osservato: Leichtmetall A

* layout compatto, una pagina, con intestazione documento molto leggibile
* blocco chimica chiaramente separato dal blocco proprietà
* tabella chimica con:

  * valore misurato per elemento
  * righe `min` e `max`
  * elementi disposti in due sottoblocchi

* presenza esplicita di una riga `Notes:` tra chimica e proprietà meccaniche
* tabella proprietà certificate con colonne osservate:

  * `HB`
  * `Ø`
  * `S`
  * `Rp 0,20`
  * `Rm`
  * `A50mm`
  * `Rp/Rm`
  * `Date`
  * `Hour`

* `C.d.Q.` e `Charge` compaiono insieme nell'intestazione tecnica del certificato

Conseguenza importante per il modulo:

* il file deve descrivere non solo la presenza dei campi, ma anche la struttura delle tabelle
* le note devono essere trattate come parte significativa del certificato
* la distinzione `valore misurato` vs `min/max` deve essere esplicita per ogni template

---

## 2. Principio fondamentale

Il sistema NON deve partire cercando di estrarre dati in modo cieco.

Deve prima costruire conoscenza documentale.

Flusso corretto:

```plaintext
PDF esempi → analisi documentale → pattern → regole → base di conoscenza
```

---

## 3. Ruolo di Codex

Codex deve comportarsi come un analista documentale e non come un parser.

Per ogni PDF deve:

1. identificare il fornitore
2. analizzare la struttura del certificato
3. individuare sezioni e blocchi principali
4. capire come sono rappresentati i dati chiave
5. formalizzare la conoscenza in regole strutturate
6. preparare una base di conoscenza riutilizzabile in futuro

Codex NON deve:

* implementare ora il parser runtime
* inventare dati mancanti
* applicare logiche normative
* calcolare valori
* produrre ora codice finale di parsing

---

## 4. Identificazione fornitore

Codex deve:

* leggere il nome del fornitore dal certificato
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

Se il fornitore non è riconosciuto:

* NON deve essere inventato
* può restare non mappato
* deve essere segnalato come nuovo caso/template futuro

---

## 5. Concetto di template

Un template rappresenta:

* un layout specifico di certificato
* associato a un fornitore
* con regole coerenti di naming, posizione e struttura

Un fornitore può avere più template.

---

## 6. Cosa deve essere compreso nei certificati

Codex NON deve solo trovare valori.
Deve capire:

* come riconoscerli
* dove si trovano
* come si presentano
* come cambiano tra certificati e fornitori
* come si collegano ai DDT e al modulo acquisition

---

### 6.1 Dati documento

* numero certificato
* data certificato
* tipo documento
* eventuale revisione o riferimento documento

---

### 6.2 Dati fornitore

* nome fornitore
* posizione nel documento
* eventuale area intestazione
* eventuali riferimenti di stabilimento o unità produttiva

---

### 6.3 Dati materiale

Per ogni certificato comprendere la presenza e la forma di:

* `lega_base`
* `lega_designazione`
* `variante_lega`
* `diametro`
* eventuale lunghezza o spessore
* eventuale forma prodotto
* eventuale trattamento termico
* eventuale tipo prodotto

---

### 6.4 Identificativi tecnici

Campi critici da comprendere:

* `cdq`
* `colata`
* eventuale numero lotto
* eventuale numero fusione / heat / charge
* eventuale codice materiale
* eventuale riferimento ordine
* eventuale riferimento DDT

Osservazione già confermata:

* in alcuni template `C.d.Q.` e `Charge` compaiono insieme nella stessa area dell'intestazione tecnica
* questo legame visivo/documentale deve essere descritto nel template

### 6.4-bis Match con il DDT corretto

Il certificato non deve essere pensato come documento isolato.

Codex deve capire anche quali campi del certificato possono servire al match con la riga corretta del DDT.

#### Primo vincolo di match

Il primo vincolo è l'emittente:

* DDT e certificato devono appartenere allo stesso fornitore/emittente

Questo è il primo filtro prima di confrontare i campi tecnici.

#### Campi forti da ricercare nel certificato per il match con il DDT

Per ogni template certificato comprendere se e come compaiono:

* numero certificato
* `cdq`
* `colata`
* `cast` / `batch` / `charge`
* codice profilo / codice cliente
* descrizione profilo / materiale
* misura nominale
* lega e stato fisico
* riferimento ordine cliente o ordine del fornitore
* peso netto

Regola importante:

* nei certificati futuri caricati dall'utente NON bisogna assumere la presenza di `cdq` o `colata` scritti a mano
* eventuali scritte manuali di questo tipo NON devono essere considerate base affidabile del match
* il match deve basarsi prima di tutto sui campi documentali stampati/strutturati del certificato

#### Regola pratica di match

Il match corretto verso il DDT deve essere cercato in modo assistito, confrontando soprattutto:

1. stesso fornitore/emittente
2. numero certificato riportato sul DDT, se presente
3. codice profilo / codice cliente
4. misura nominale
5. lega e stato fisico
6. ordine
7. `cast` / `batch` / `charge`
8. peso netto

#### Varianti di scrittura

Codex deve descrivere anche le varianti che possono indebolire il match pur restando corrette, per esempio:

* inversioni o trasposizioni parziali di cifre
* spazi mancanti o aggiunti
* trattini, slash o separatori diversi
* sigle diverse per `cast`, `batch`, `charge`, `order`
* piccole differenze di formattazione nei codici cliente o profilo

Queste varianti sono particolarmente importanti per:

* ordine
* `cast`
* `batch`
* `charge`
* codici profilo / cliente

#### Peso netto come controllo forte

Il peso netto del certificato deve essere trattato come controllo importante di coerenza con il DDT.

Regola:

* se il peso netto è coerente con la riga o con il blocco DDT, il match si rafforza

#### Placeholder eccezioni per fornitore

Le eccezioni di match devono essere registrate per fornitore/template.

Esempio già noto:

* `Leichtmetall`
  * il peso effettivo da confrontare può richiedere la somma dei pesi di più righe con lo stesso `batch`

Placeholder da mantenere:

```plaintext
Eccezioni di match certificato-DDT
- uso del peso: diretto / somma / altro
- uso del batch/cast/charge: obbligatorio / secondario / assente
- uso dell'ordine: forte / medio / debole
- varianti frequenti di scrittura
- casi noti di mismatch apparente
```

Queste eccezioni vanno analizzate e mantenute caso per caso, a seconda del fornitore.

---

### 6.5 Standard e classificazione

Codex deve capire come sono rappresentati:

* eventuale norma
* eventuale classe standard
* eventuale trattamento termico
* eventuali diciture speciali di variante

Questa parte è importante per mantenere coerenza con:

* `lega_base`
* `lega_designazione`
* `variante_lega`
* modulo `engine_normative_standards`

---

### 6.6 Chimica

Codex deve comprendere:

* quali elementi chimici compaiono
* come vengono nominati
* se sono in tabella o in blocchi testo
* con quale formato numerico compaiono
* come vengono presentati eventuali composti come:

  * `Zr+Ti`
  * `Mn+Cr`
  * `Bi+Pb`

* se i valori sono presentati come range o come valori misurati

Placeholder da preparare per ogni fornitore/template:

```plaintext
Tabella chimica
- presente: si / no
- forma: tabella / blocco testo / altro
- posizione: alto / centro / basso / colonna laterale
- struttura colonne: elemento | valore | min | max | altro
- orientamento: orizzontale / verticale / misto
- formato numerico: virgola / punto
- elementi osservati
- presenza di righe misurate / min / max
- cardinalita delle colate rappresentate
- note sulla leggibilita / OCR
```

Osservazione già confermata:

* nei template letti la tabella chimica non contiene solo valori misurati
* contiene anche righe di riferimento `min` / `max`
* questa distinzione va sempre registrata

---

### 6.7 Proprietà certificate

Codex deve comprendere:

* quali proprietà certificate compaiono
* la loro categoria documentale:

  * meccanica
  * elettrica
  * eventuale altra

* come vengono presentate proprietà come:

  * `HB`
  * `Rp0.2`
  * `Rm`
  * `A%`
  * `Rp0.2 / Rm`
* `IACS%`

* se i valori sono misurati, minimi garantiti o entrambi

Placeholder da preparare per ogni fornitore/template:

```plaintext
Tabella proprieta certificate
- presente: si / no
- forma: tabella / blocco testo / altro
- posizione: alto / centro / basso / colonna laterale
- struttura colonne: proprieta | valore | min | max | unita | altro
- categorie osservate: meccanica / elettrica / altra
- formato numerico: virgola / punto
- proprieta osservate
- presenza di piu provette / specimen
- presenza di colonne aggiuntive come data / ora / conducibilita
- note sulla leggibilita / OCR
```

Osservazioni già confermate:

* nei template letti le proprietà certificate sono presentate in vere tabelle
* possono esserci più righe prova / specimen
* possono comparire anche colonne aggiuntive oltre alle sole proprietà meccaniche standard

---

### 6.8 Distinzione obbligatoria: valori misurati vs limiti / standard

Codex deve distinguere in modo esplicito tra:

#### Valori misurati del certificato

Esempi:

* composizione chimica effettiva
* proprietà certificate effettive

#### Valori di riferimento / limiti / standard riportati nel certificato

Esempi:

* minimi garantiti
* intervalli ammessi
* richiami normativi

Questa distinzione è critica per non confondere:

* dato reale del certificato
* regola normativa o soglia di riferimento

---

### 6.9 Distinzione obbligatoria: dati globali vs dati per riga / colata

Codex deve capire se un dato è:

* globale del certificato
* riferito a una specifica colata
* riferito a un singolo blocco materiale

Questo è importante soprattutto per:

* `cdq`
* `colata`
* chimica
* proprietà certificate

---

### 6.10 Dati aggiunti manualmente

Se nei certificati reali compaiono annotazioni manuali, Codex deve distinguerle da:

* dati stampati dal fornitore
* valori tecnici del certificato

Le annotazioni manuali NON devono essere inventate né confuse con i dati tecnici originari.

Regola pratica per il match:

* eventuali annotazioni manuali contenenti `cdq` o `colata` non devono essere trattate come fonte standard del collegamento con il DDT
* nei certificati futuri il sistema deve aspettarsi soprattutto dati stampati/strutturati, non scritte manuali di collegamento

---

### 6.11 Note del certificato

I certificati possono contenere note importanti che influenzano la corretta interpretazione dei dati raccolti.

Le note possono riguardare, per esempio:

* stato del materiale
* condizioni di fornitura
* eccezioni di misura
* riferimenti a norme
* osservazioni del fornitore
* timbri o annotazioni che danno contesto ai valori tecnici

Queste note devono essere analizzate come contenuto documentale significativo.

Placeholder da preparare per ogni fornitore/template:

```plaintext
Tabella / area note
- presente: si / no
- tipo: tabella / blocco note / timbro / testo libero
- posizione: alto / centro / basso / margine
- origine: stampata / timbro / manuale / mista
- relazione con i dati tecnici: globale / per colata / per blocco materiale
- impatto atteso sulla raccolta dati: nessuno / contestuale / critico
- esempi note osservate
```

Osservazioni già confermate:

* in alcuni template la nota è una riga esplicita `Notes:`
* in altri template possono esserci blocchi finali con prescrizioni, controlli, condizioni o timbri
* l'area note può quindi stare:

  * tra tabella chimica e tabella proprietà
  * in fondo al certificato
  * nell'area bassa vicino a firme o timbri

Nota futura importante:

* potra esistere una tabella o struttura dedicata alle note raccolte
* tale struttura dovra interagire con il modulo di acquisition per chiarire se una nota e:

  * documentale
  * interpretativa
  * operativa interna

Per ora questo file prepara solo il placeholder concettuale.

---

## 7. Output atteso da Codex

Codex NON deve produrre codice di estrazione.

Deve produrre conoscenza strutturata.

Il primo deliverable del modulo è una knowledge base documentale, non un parser runtime.

Esempio concettuale:

```plaintext
fornitore: X

template: C1

campo: cdq
- posizione: intestazione
- tipo: stampato
- cardinalita: singolo

campo: colata
- posizione: blocco tecnico
- sinonimi: heat, charge
- relazione: associata ai valori chimici e meccanici

campo: Rp0.2
- categoria: meccanica
- tipo: valore certificato
- unita: MPa
```

---

## 8. Persistenza (base dati di conoscenza)

Il sistema deve essere progettato per salvare in modo strutturato:

* fornitori
* template
* campi
* pattern
* esempi documento
* relazioni tra campi
* distinzione tra valore misurato e limite / standard
* distinzione tra dato globale e dato riferito a colata / materiale
* presenza e ruolo delle note documento

Strutture suggerite:

* `document_templates`
* `template_fields`
* `field_patterns`
* `template_examples`
* `field_relations`
* `template_notes`

---

## 9. Vincoli

* NON inventare dati
* NON applicare logica normativa
* NON calcolare valori
* NON implementare parsing runtime
* NON confondere valori misurati e limiti di riferimento
* NON confondere il certificato con la norma

---

## 10. Integrazione con altri moduli

### Fornitori Module

Utilizzare:

* `fornitore_id`
* `fornitori_alias`

### Certificates Data Acquisition Module

Questo modulo deve essere coerente con il fatto che:

* `cdq` è la chiave primaria
* `colata` è campo critico
* `lega_base`, `lega_designazione` e `variante_lega` devono restare coerenti
* chimica e proprietà certificate devono essere riconosciute secondo i vocabolari del sistema

### DDT Supplier Document Knowledge Module

Questo modulo deve essere coerente con il fatto che:

* DDT e certificati sono due fonti documentali diverse
* il collegamento tra i due passa da campi critici come `cdq`, `colata`, materiale, fornitore, ordine, `cast/batch/charge` e peso netto
* i template certificato e i template DDT devono poter convivere nella stessa conoscenza di dominio
* il knowledge certificati e il knowledge DDT devono essere pensati insieme per far confluire i due documenti nella stessa raccolta dati acquisition

---

## 11. Estensione futura

Questo modulo potrà evolvere in seguito verso:

* parsing runtime guidato dalle regole
* revisione umana dei template
* teach operatore
* supporto a dataset futuri
