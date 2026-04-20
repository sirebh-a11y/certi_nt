# Strategia Inserimento Nuovo Fornitore

## Scopo
Questa strategia definisce il processo standard per introdurre un nuovo fornitore nel flusso acquisition, mantenendo:

- schema canonico acquisition invariato
- caricamento coerente con gli altri fornitori
- masking corretto
- prompt AI allineati
- match robusto

## Principi fermi

- I campi finali restano quelli canonici acquisition.
- I nomi reali dei campi nel documento possono cambiare per fornitore.
- I campi runtime di supporto possono esistere, ma non devono cambiare il modello canonico.
- Le annotazioni a penna non vanno mai usate.
- Il raw AI utile va sempre conservato.
- Il match non va chiuso su numeri documento soltanto se i campi materiale non sono coerenti.

## Processo

### 1. Analisi documenti reali
Partire sempre da:

- DDT in `esempi_locali`
- certificati in `esempi_locali`

Obiettivi:

- capire i campi stampati reali
- distinguere campi affidabili e campi deboli
- capire il vero legame DDT-certificato
- capire quali blocchi descrittivi vanno conservati come raw

### 2. Capire se il DDT e monoriga o pluririga
Non va assunto a priori.

Bisogna:

- analizzare i DDT reali
- proporre una lettura
- farla confermare o correggere dall'utente

Regola:

- io propongo
- l'utente conferma o corregge

### 3. Punto di controllo con l'utente
Dopo la prima analisi bisogna fermarsi e riportare:

- come sono fatti DDT e certificati
- quali campi sembrano giusti
- quali campi sembrano deboli
- come sembra costruito il match

In questa fase l'utente puo:

- correggere
- aggiungere informazioni
- cambiare priorita
- chiarire regole specifiche del fornitore

Solo dopo si prosegue.

### 4. Catalogazione fornitore e caricamento
Il nuovo fornitore va catalogato come nella lista fornitori.

Il caricamento deve:

- riconoscere il fornitore
- distinguere `ddt` e `certificato`
- mostrare subito tipo e fornitore nei documenti caricati

### 5. Batch e persistenza
Regole:

- `caricato ma non lavorato` = `temporaneo`
- `caricato e lavorato bene` = `persistente`
- se il run fallisce, il documento resta `temporaneo`
- un temporaneo fallito non deve bloccare il reupload come se fosse persistente

Duplicati:

- temporanei: gestiti nel batch
- persistenti: bloccati

Regola pratica importante:

- il duplicato vero e' lo stesso file digitale, non lo stesso nome file
- il controllo va fatto per hash/contenuto
- se due file hanno nome uguale o root simile ma contenuto diverso, devono entrare come documenti distinti
- questo vale in particolare per i certificati

Il batch utente deve essere:

- recuperabile
- scartabile

### 6. Mascheramento
Si mascherano solo:

- cliente
- fornitore / logo / riferimenti del fornitore

Non si mascherano:

- campi tecnici
- numeri utili al match
- scritte a mano

Regola tecnica:

- masking con logica posizionale reale
- trovare il blocco OCR corretto
- coprire solo quel blocco
- niente box fissi stimati a occhio

Il masking va sempre validato visivamente su preview.

### 7. Prompt AI DDT
Il prompt DDT deve seguire lo schema consolidato dei fornitori gia introdotti.

Deve:

- rispettare il fatto che il DDT sia monoriga o pluririga
- esplicitare i campi stampati corretti del fornitore
- dire chiaramente quali campi non vanno confusi
- restituire i campi canonici utili
- restituire i campi runtime utili al match
- restituire i raw descrittivi utili per parsing futuri

### 8. Prompt AI certificato
Il prompt certificato deve restare nel bundle unico:

- `core`
- `chemistry_raw`
- `mechanical_raw.measured_rows`
- `notes_raw`

Regole:

- note sempre canoniche
- nessuna nota nuova inventata per fornitore
- proprieta con tutte le righe misurate vere
- raw descrittivi sempre mantenuti

### 9. Persistenza raw AI
Il raw AI utile va sempre conservato.

Soprattutto:

- blocchi descrittivi prodotto
- eventuali campi tecnici raw che oggi servono a derivare valori canonici

Motivo:

- oggi servono per lega, diametro, peso o altri campi
- domani possono servire per barra, estruso, lunghezza, classificazioni o altri calcoli

### 10. Mapping verso acquisition
Non va cambiato il modello canonico acquisition.

Il backend deve:

- leggere i nomi reali del documento
- mapparli nei campi canonici
- tenere separati i campi runtime di supporto

Regola importante:

- non portare scorciatoie legacy da un fornitore all'altro

### 11. Match
Prima si capisce il match vero del fornitore, poi si implementa.

Il processo giusto e:

- analizzare dai documenti quali campi legano davvero DDT e certificato
- proporre il criterio
- farlo confermare o correggere dall'utente
- solo dopo implementarlo

Regola:

- i numeri documento possono aiutare
- ma il match va chiuso sui campi forti reali del fornitore
- se ci sono mismatch forti sui campi chiave, il match va scartato

Cardinalita' da verificare sempre:

- un DDT puo' restare monoriga oppure spezzarsi in piu' gruppi materiali
- un certificato puo' essere monoriga anche se esistono piu' certificati della stessa famiglia/root
- non assumere mai:
  - `1 DDT = 1 certificato`
  - `1 root certificato = 1 solo documento`
- se lo stesso DDT contiene piu' batch o gruppi coerenti, il sistema deve prevedere piu' certificati collegati
- se esistono piu' certificati distinti con stessa famiglia/root ma campi diversi, devono entrare tutti e poter completare righe diverse

### 12. Validazione finale
Preparare sempre un set test con:

- DDT
- certificati match
- certificati no-match

Verificare:

- caricamento
- riconoscimento fornitore e tipo documento
- masking
- raw AI
- mapping verso acquisition
- match
- no-match

Ordine corretto delle correzioni:

1. correggere campi vuoti o mappati male
2. correggere raw o parsing errati
3. correggere il match
4. solo dopo fare commit finale

## Punti emersi dall'esperienza

### Distinguere sempre tre livelli

- campo canonico acquisition
- campo reale nel documento
- campo runtime di supporto

### Non fidarsi dei numeri documento da soli
Packing list, numero certificato o riferimenti simili aiutano, ma spesso non bastano da soli a chiudere il match.

### Correggere prima il dato e poi il match
Se il dato DDT o certificato e vuoto o mappato male, il match viene distorto.

### I raw descrittivi sono obbligatori
Non sono opzionali. Servono al debug oggi e a parsing futuri domani.

### Distinguere multi-file da multi-riga
Non va confuso:

- un singolo PDF davvero multiriga
- piu' PDF distinti della stessa famiglia/root

Prima si verifica il caso reale sui file veri del fornitore, poi si decide la strategia.

### Guardare anche la seconda pagina o i dettagli di colli/batch
Per alcuni fornitori la pagina 1 mostra solo il totale materiale, ma il vero criterio di riga sta nei dettagli pagina 2.

Esempio tipico:

- stessa lega e stesso ordine in pagina 1
- ma pagina 2 spezza il DDT in due batch diversi
- quindi il flusso deve prevedere piu' certificati per lo stesso DDT

### Il masking va sempre controllato visivamente
Una regola teorica corretta non basta. Va sempre verificata sulle immagini generate.

### I fallimenti di run non devono contaminare i re-test
Un documento non deve diventare persistente se il run e fallito o interrotto.

### Distinguere problema backend da problema UI
Se qualcosa sembra sbagliato, va sempre capito se il problema e:

- estrazione dato
- risposta API
- visualizzazione frontend

## Checklist minima per ogni nuovo fornitore

- letti DDT reali in `esempi_locali`
- letti certificati reali in `esempi_locali`
- deciso con l'utente se DDT e monoriga o pluririga
- fissati campi forti di match
- fissato cosa non va mai usato
- riconoscimento fornitore in upload
- riconoscimento `ddt/certificato`
- masking cliente/fornitore validato
- prompt DDT scritto
- prompt certificato scritto
- raw AI conservato
- mapping acquisition verificato
- test set con match e no-match
- validazione finale
