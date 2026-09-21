# Certificazione: separazione dei filtri Word

## Decisione approvata e perimetro

Implementazione locale autorizzata il 18 settembre 2026, dopo audit e simulazione
in sola lettura su Alpha. Commit, push e deploy richiedono richieste separate.

- **Solo certificati da fare**: OL senza Word gia preparati, con certificato
  presente in Incoming e controlli Incoming completati.
- **Altri Word da preparare**: OL con un Word gia presente e almeno un ulteriore
  Word mancante collegato a certificati con controlli Incoming completati.
- Accettato, accettato con riserva e respinto entrano nelle code. Un respinto
  resta bloccato quando si tenta di creare il Word, ma non viene nascosto.
- Standard non confermato, riferimento fornitore o altri blocchi di creazione
  non nascondono l'OL: restano visibili nel dettaglio e continuano a impedire
  la generazione finche non vengono risolti.
- I due filtri sono alternativi, anche rispetto a **Nascondi completati**, come
  gia accadeva per il filtro precedente. Disattivandoli si torna alla vista generale.
- Gli OL con tutti i Word presenti e in attesa soltanto di DDT/PDF non sono
  inclusi, salvo ulteriori candidati individuati dalla logica esistente.
- Non cambiano generazione Word/PDF, standard, conferme Incoming, match,
  valutazione, Registro o struttura del database.

## Evidenza dell'audit Alpha (fotografia, non conteggi permanenti)

79 OL superavano i controlli attuali: 0 nel primo filtro, 39 nel secondo,
40 esclusi. I 39 inclusi erano Parziali e senza DDT di spedizione disponibile;
6 avevano soltanto candidati con confidenza `medium`.
Nessuna sovrapposizione o perdita rispetto all'insieme del vecchio filtro.
Questo non dimostra che tutti i candidati richiedano effettivamente un certificato.

## Messaggi e UI

Nella colonna Stato, senza nuove colonne:

- DDT identificato: `Word mancante per DDT ..., articolo ...`.
- Articolo base: `Word da preparare per articolo base ...`.
- Candidato senza DDT, sia `ready` sia `medium`:
  `Articolo proposto ...: verificare se serve il certificato`, giallo tenue.

Solo la prima indicazione e visibile per esteso; le altre sono espandibili.
I controlli vanno a capo se manca spazio. Il filtro viene salvato nella sessione
con ricerca e ordinamento, anche prima di entrare nel dettaglio.

## Implementazione

- Conservato `only_word_pending`, ora riferito agli OL da iniziare.
- Aggiunto `only_additional_words`; una richiesta con entrambi attivi viene
  rifiutata prima di sincronizzare o accedere al database.
- Separazione basata sui Word presenti (o su un PDF finale legacy), non sulla
  sola etichetta Da fare/Parziale/Completato.
- La visibilita richiede certificato fornitore, corrispondenza CDQ/colata,
  chimica/proprieta/note confermate e valutazione qualita conclusa. Lo standard
  e gli altri requisiti tecnici vengono controllati soltanto nell'azione di
  creazione Word.
- Riutilizzati gli abbinamenti ai singoli DDT: lo stesso articolo puo avere piu
  spedizioni e un Word puo coprire soltanto una di esse.
- Motivi e appartenenza al filtro derivano dalla stessa funzione. Conteggio e
  filtro vengono calcolati prima della paginazione.
- Nei filtri Word viene riutilizzata la lettura DDT gia aggiornata per la selezione,
  evitando un secondo aggiornamento della stessa pagina.
- Le letture ordinarie della pagina conservano le sincronizzazioni preesistenti;
  non e stato introdotto un nuovo processo in background.

## Verifiche locali

- Aggiornamento del 21 settembre 2026: aggiunti test per OL senza standard,
  respinto, certificato Incoming mancante, controlli incompleti e separazione
  fra primo e secondo filtro. Suite backend completa: 321 test superati.
- 10 nuovi test backend: separazione, tutti i Word presenti, blocchi, riserva,
  candidati probabili, due DDT dello stesso articolo, conteggi, ricerca,
  paginazione, messaggi e rifiuto di filtri incompatibili.
- Suite Certificazione: 79 test superati (inclusi i 10 nuovi).
- Verifica precedente alla modifica del 21 settembre: 294 test backend superati.
- 3 nuovi test frontend: esclusivita, ripristino sessione e dati salvati incoerenti.
- Suite frontend disponibile: 8 test superati.
- Build frontend riuscita; avvisi non bloccanti sulla dimensione bundle e sui
  dati Browserslist non recenti.
- Controllo visivo nel browser non eseguito: nessun browser disponibile nel
  collegamento di questa sessione. Restano da verificare manualmente la resa
  a schermo e il giro completo dettaglio -> ritorno alla lista.

## Prima del futuro deploy

Verificare in UI locale i due pulsanti, espansione delle indicazioni, ricerca e
ritorno dal dettaglio. Aggiornare backend e frontend insieme seguendo il MD
del deploy soft; non servono migrazioni DB. Alpha non e stato modificato durante
questa implementazione.

Resta aperta la conferma del cliente su quali articoli proposti richiedano
effettivamente un certificato: il nuovo filtro non li rende obbligatori.
