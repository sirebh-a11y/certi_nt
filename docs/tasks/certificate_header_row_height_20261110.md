# Altezza delle righe DDT e Quantity nel certificato Word

## Richiesta e perimetro

Intervento locale autorizzato il 10/11/2026: dare alle righe DDT e Quantity
la stessa altezza di riferimento della riga Order/Drawing, mantenendo il
motore che ripristina la formattazione. Non cambiare font, colori, larghezze,
disposizione delle colonne, dati, numerazione o regole di ereditarieta.
Commit/push richiesti esplicitamente dall'utente dopo il collaudo del 10/11.
Deploy, correzione dati Alpha o chiamate AI non autorizzati da questa attivita.

Il modello scaricabile della seconda pagina non contiene il header del
certificato: lo riceve dall'app durante la composizione. Non aggiungere DDT
duplicati nel corpo del modello e non modificare le sue tabelle per questo fix.

## Misura e comportamento

Prima dell'intervento tutte le righe avevano un minimo OOXML di 355 twip.
Order/Drawing occupava comunque piu spazio perche contiene tre paragrafi;
DDT e Quantity soltanto due. Il PDF di riferimento misura rispettivamente
27,4 pt e circa 21 pt. Copiare il vecchio valore minimo non sarebbe bastato.

Il nuovo riferimento comune per Order/Drawing, DDT e Quantity e **538 twip**:
con i bordi e gli stili attuali il PDF misura **27,4 pt, circa 9,7 mm**, per
ognuna delle tre righe. La prima riga cliente/CodF3 conserva il minimo 355.
La regola resta `atLeast`, non `exact`: riferimenti eccezionalmente lunghi
possono andare a capo ed espandere la propria riga per non tagliare il testo.
L'uguaglianza riguarda l'altezza standard, non un limite che tronca descrizioni
multiriga. Nessuna riduzione di font aggiunta dal nuovo codice.

La riga DDT comprende anche C.d.O.: la maggiore altezza riguarda tutta la
riga. L'intestazione normale cresce di circa 13 pt; nel convertitore reale
il corpo si abbassa mantenendo la separazione. Firme e footer restano nelle
posizioni precedenti. Verificare di nuovo i documenti vicini al fondo pagina
al futuro deploy: non promettere la stessa paginazione per ogni Word possibile.

## Catena applicativa

- Il generatore e la normalizzazione usano lo stesso riferimento. Il motore
  riconosce le righe tramite i campi o le etichette legacy e non cambia
  tabelle aggiunte dall'utente in altre zone dell'intestazione.
- Aggiornamento campi, ricaricamento Word, composizione seconde pagine,
  aggiunta/rimozione allegati e riuso DDT mantengono la nuova misura.
- Un Word aperto valido viene adeguato anche se i valori DDT sono invariati:
  download/preparazione PDF crea una nuova copia tracciata, senza riscrivere
  il file originale. Un secondo download senza variazioni non crea un altro
  file. Restano tutte le protezioni su materiale, standard, fonte e quota.
- I file chiusi `pdf_final` non vengono normalizzati al download. Nessuna
  scansione o riscrittura massiva dello storico, nessun nuovo numero o ID.
- Gli hash reali dei file e la provenienza continuano a verificare i byte
  originali. Il solo confronto di equivalenza per riuso/ereditarieta e
  recupero offline considera equivalenti i due profili gestiti dall'app
  (355/538 con `atLeast`), senza cambiare i file. Testi, font, misure diverse,
  regole `exact`, allegati e dati tecnici diversi NON diventano equivalenti.
- Questo confronto e necessario per non bloccare il terzo DDT quando una
  fonte storica chiusa mantiene la vecchia altezza e la copia nuova ha gia
  quella aggiornata. Il caso ha riprodotto il falso conflitto prima del fix.
- Le normali regole di aggiornamento dei valori DDT/quantita restano attive:
  l'intervento non introduce un override manuale dei dati spedizione.

## Collaudo

Solo container locali senza collegamento a reti aziendali, database SQLite
temporanei e PostgreSQL dedicato effimero senza porte o volumi persistenti.
Nessun riavvio dell'app operativa, accesso Alpha o chiamata AI.

Nuovi test in `backend/tests/test_certificate_header_height.py`:
campi vuoti/normali/lunghi; ripristino da misure modificate, `exact` o mancanti;
parti OOXML e font invariati; altri header non toccati; etichette legacy;
compilazione dei controlli e preparazione base manuale; copia tracciata una
sola volta; integrita rigorosa per modifiche non pubblicate; PDF chiusi intatti;
storico vecchio/nuovo senza falsi conflitti e senza ignorare differenze reali.

Confronto Word/PDF reale in `tmp_eval/header_height_20261110/final/`:

- Vuoto, normale, DDT lungo, `200 of 23000`, `999,999 of 1,999,999`.
- Base ricaricabile manuale e DDT successivo.
- Modello seconda pagina da solo e composto con il certificato.
- Seconde pagine con due allegati PDF.
- Descrizioni e ordini che vanno a capo: nessun testo tagliato.
- Tre copie locali gia disponibili di OL1090, ID71/137/177: tutte restano
  di tre pagine, con testo, font, firme e parti diverse dal header invariati.

Ispezionate tutte le **25 pagine PNG** dei candidati, del modello e del PDF
finale prodotto tramite il vero servizio applicativo.
I confronti automatici controllano testo, font, footer, conteggio pagine,
assenza di sovrapposizione header/chimica e conservazione delle altre parti.
La digitazione e simulata dentro i controlli Word esistenti; non e stato
effettuato un collaudo interattivo su Microsoft Word desktop.
Il runtime dedicato della skill documenti non e disponibile: conversioni
eseguite con il vero convertitore dell'app nell'immagine backend locale,
immagini di verifica ottenute dai PDF tramite PyMuPDF.

Esiti delle ripetizioni, senza errori:

- Suite applicativa ampia: **899 passati, 170 opt-in saltati**. Comprende
  acquisizione/match, chimica, standard, certificazione, registro, file names,
  stato PDF e regole gia esistenti.
- Suite mirata su PostgreSQL isolato: **199 passati**, compresi riuso,
  ereditarieta, spedizioni/numerazione, integrita, chiusura concorrente PDF e
  verifica del recupero offline.
- Dopo le ultime due rifiniture difensive (proprieta XML di riga non standard
  e prima riga esclusa dalle equivalenze altezza): nuova esecuzione mirata
  con **29 passati, 15 opt-in PostgreSQL saltati**. Nessuna modifica alle
  transazioni rispetto alla suite PostgreSQL precedente.
- Chiusura end-to-end con il vero servizio PDF e convertitore, SQLite di
  fixture: `pdf_final`, due pagine, `7013_00_00_26.docx` e
  `7013_00_00_26.pdf`, riferimento originale invariato, integrita valida e
  download successivo del chiuso senza riscritture. La fixture richiede data
  certificato e conformita esplicite, come l'app: i due controlli sono rimasti
  attivi e non sono stati aggirati.
- Avvisi presenti nelle suite: deprecazioni delle librerie gia installate,
  nessun aggiornamento dipendenze eseguito.

Nessuna somma fra i conteggi delle suite: molte prove si sovrappongono.
PostgreSQL QA `certi-header-qa-pg-20261110`, ID
`8e41eb56600421038920d0a2eed890a9c5e6faf168a99123b3f3f2d9d0fdbfb0`, creato
senza rete esterna, porte o volumi, con dati solo tmpfs. Arrestato e rimosso
dopo la verifica finale; nessun servizio o dato dell'app rimosso.

## Pagina vuota fra allegati: audit iniziale e correzione autorizzata

Nel caso sintetico `with-attachments`, seconda pagina piu due pagine PDF A4,
all'audit iniziale compariva una pagina vuota **fra i due allegati**, con il
solo footer. Il file prima e dopo il solo cambio altezza aveva cinque pagine:
non era una regressione della nuova altezza. Questo confronto iniziale resta
la prova della causa distinta, non lo stato finale del software.

L'ispezione visiva conferma allegato 1 a pagina 3, pagina 4 vuota, allegato 2
a pagina 5. Gli allegati usano una sezione senza l'intestazione certificato,
con margini propri; il cambio altezza non la modifica. La probabile area da
verificare separatamente e la combinazione dimensione immagine/paragrafi e
salti pagina in `_append_pdf_attachments`/`_add_pdf_attachment_page`.
L'utente ha poi autorizzato esplicitamente anche la correzione di questa
anomalia, dopo aver chiesto se fosse stata gia risolta. Intervento effettuato
solo in sviluppo locale, senza modificare PDF gia emessi o dati Alpha.

### Causa e soluzione

Il vecchio `add_page_break()` creava un paragrafo separato dopo l'immagine.
Se l'allegato occupava quasi tutta la pagina, il paragrafo poteva finire
sulla successiva e provocare un secondo salto: una pagina vuota aggiunta.
Inoltre il vecchio margine di 0,10 pollici lasciato sotto l'immagine non era
sufficiente nel caso limite di pagine molto alte e strette.

- Il prossimo allegato inizia con `pageBreakBefore` sul suo marcatore nascosto,
  mantenuto insieme all'immagine. Non viene creato il paragrafo di salto vuoto.
- La riserva per marcatore e riquadro immagine passa a 0,20 pollici. Si conserva
  il rapporto larghezza/altezza e l'intera immagine, senza tagli ne ricampionamento
  dei pixel incorporati. Solo le immagini che raggiungono il limite pagina
  possono risultare fino a circa l'1% piu piccole; font visibili invariati.
- Per i Word aperti esistenti la normale copia tracciata adegua anche i vecchi
  separatori, riconoscendo soltanto il marcatore CERTI nascosto immediatamente
  seguito da una singola immagine. Non e un filtro che cancella pagine bianche.
- Il ridimensionamento legacy e limitato alle immagini di altezza compatibile
  col precedente limite app, nella sezione finale con i margini standard app.
  Sezioni personalizzate, immagini ritagliate/trasformate o marcatori non
  verificabili vengono conservati: non inventare una correzione dei Word manuali.
- Il confronto per equivalenza canonizza anche questi separatori app; gli
  hash reali rimangono rigorosi. Verificato il riuso da fonte storica chiusa
  con vecchi salti/immagini massime, poi due DDT successivi senza falso conflitto.
- La rimozione degli allegati durante preparazione della base manuale continua
  a preservare pagine laboratorio e firme. I PDF originali allegati restano
  identici; anche eventuali pagine realmente bianche gia presenti nei PDF
  sorgente rimangono nel certificato, per non eliminare contenuti dell'utente.
- Corretto anche il confronto A4 in twip, l'unita serializzata da Word: evita
  risalvataggi inutili causati dal confronto dei millimetri con misure arrotondate.

### Verifiche aggiuntive

`backend/tests/test_certificate_pdf_attachments_layout.py` copre due file
distinti, PDF multipagina, A4/A5, formato molto alto, pagine ruotate e pagine
bianche originali. Verifica numero e ordine pagine, presenza delle immagini,
pixel incorporati, firme, ricaricamento e ripristino legacy. Casi non
verificabili e testo utente sono protetti da prove negative.

Nel caso iniziale, certificato + seconda pagina + due allegati, il PDF ora
ha **quattro pagine, non cinque**. Una chiusura tramite il vero servizio PDF
dell'app, con Word manuale di due pagine e due allegati (uno molto alto),
produce quattro pagine, stato `pdf_final`, nomi file corretti e integrita
valida. Il vecchio Word e il successivo download del chiuso restano invariati.
Ispezionate tutte le quattro pagine di entrambi questi PDF finali.

Esiti finali dopo la correzione degli allegati (non sommare le suite):

- **915 passati, 171 opt-in saltati** nella suite applicativa completa, con
  `CERTI_TEST_RENDER_PDF=1`: inclusi i sei casi di conversione reale degli
  allegati. Nessun errore.
- **210 passati, 6 render opt-in saltati** nella suite mirata su PostgreSQL
  isolato. I sei render sono gia eseguiti nella suite completa sopra. Nessun
  errore su riuso, fonti legacy, integrita, transazioni, concorrenza, numerazione
  spedizioni e recupero offline.
- Ripetuti separatamente i sei render e il caso fonte chiusa con immagini
  riportate al vecchio massimo: **7 passati**. Nessun Word/PDF originale
  riscritto e nessun falso conflitto al DDT successivo.
- Confronto visivo rigenerato e controllato: altezze standard Order/DDT/Quantity
  confermate, tre copie reali di OL1090 sempre di tre pagine, caso con seconda
  pagina e due allegati ora di quattro pagine. Chiusura reale del servizio PDF
  con allegati: quattro pagine, file e stato corretti, integrita valida.
- Solo deprecazioni delle dipendenze gia presenti; nessuna nuova dipendenza,
  chiamata AI, migrazione o riavvio del servizio operativo.

PostgreSQL effimero finale `certi-layout-qa-pg-20261110`, ID
`15f8b316787d6834a11d53cc29628d24719093d87173dd3a695ed0e14174cd8f`,
senza rete esterna, porte o volumi persistenti. Arrestato e rimosso dopo le
prove con verifica esatta dell'ID; nessun container residuo. Manifest di
collaudo e documenti QA locali conservati, nessun servizio dell'app rimosso.

## Passaggio Alpha futuro

Seguire il runbook, non questo documento come autorizzazione al deploy.
Distribuire insieme `certificate_docx.py`, `service.py`, `ddt_word_reuse.py`,
`word_reference.py` e `word_lifecycle_recovery.py` dal commit approvato.
Nessuna migrazione DB, backfill, cache reset o recupero storico da eseguire.
Non copiare modelli/file QA o database locali in Alpha. Il modello seconda
pagina viene gia generato dall'app; la sua intestazione composta usa il
generatore aggiornato.

Sul clone verificare fonte vecchia chiusa + due DDT successivi, hash e firme,
Word aperto aggiornato una sola volta, Word/PDF chiusi immutati e conversione
multiplagina. Rollback del solo codice conserva tutti i documenti: il vecchio
normalizzatore ripristina le misure precedenti nelle successive operazioni
su Word aperti. Non cancellare copie tracciate, metadati o documenti chiusi.
