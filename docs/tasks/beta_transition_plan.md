# Passaggio alla beta - decisioni e verifiche aperte

Aggiornato: 08/10/2026, dopo audit di riduzione arretrato locale e Alpha.
Stato: documento di lavoro, non autorizzazione a modificare codice o server.

La versione è `0.1.0.alpha.10`. Al controllo del 08/10 la coda DDT, il recupero
storico e la raccolta automatica sono già presenti su Alpha. Le correzioni
locali successive non vanno considerate installate senza verificarne il commit.
Le annotazioni del 29–30/09 sotto sono il resoconto di quelle date, non lo stato
attuale del deploy. La sezione 7 registra la nuova proposta, ancora da approvare.

**Decisione utente: Beta significa utilizzo reale in produzione, non più test.**
La data ufficiale di avvio e quanti giorni precedenti includere sono ancora da
decidere; non confondere questa scelta con la scadenza dei sette giorni.

Riferimenti:

- [Piano e audit DDT](ddt_certification_alert_queue_plan.md).
- [Procedura deploy soft Alpha](../deploy/alpha_soft_update_server.md).

## Regole di lavoro

Prima audit e proposta; codice solo dopo approvazione. Deploy separato, solo
quando richiesto e seguendo il relativo Markdown. Aggiornare questo documento
dopo ogni decisione, distinguendo proposta, approvazione, implementazione e test.
La futura beta non cambia implicitamente il comportamento dell'attuale Alpha.

## 1. Uniformare la pagina DDT alle altre pagine

Audit locale del 29/09:
- Le 13 intestazioni sono fisse e non hanno frecce di ordinamento.
- Il menu Ordine permette soltanto data crescente/decrescente.
- La scelta Righe esiste: 25, 50, 100, 200, applicata con Applica filtri.
- Valutazione usa intestazioni con frecce e scelte 25, 50, 75, 100, Tutte.
- Non è presente un selettore delle colonne visibili nella nuova pagina.
- I controlli funzionali precedenti non dimostrano un completo allineamento
  di stile e interazione: questo adeguamento resta aperto.

Decisione dell'utente: sulla pagina realizzare **solo le frecce su/giù** per
ordinare le intestazioni. La scelta delle righe già presente, i campi, i filtri
e le colonne visibili restano come sono. Azioni non è ordinabile.

Le frecce ordinano sul backend tutte le righe filtrate prima della paginazione.
Quantità è numerica, date cronologiche, testi senza distinzione maiuscole/minuscole,
valori mancanti in fondo e parità risolta con ID stabile. Stato, Incoming e
Certificazione seguono le etichette mostrate all'utente.

Test previsti: ordinamento su più pagine, filtri combinati, numeri/date/null,
ritorno dal dettaglio, dati lunghi, schermo stretto, conteggi e collegamento
alla quota corretta. Nascondere una colonna non deve cancellarne i valori.

Verifiche locali delle modifiche autorizzate: 38 test dedicati alla coda
superati; regressioni Quarta/eSolver 121 superate e 8 test opzionali saltati
in questo ambiente; 4 test sulla soglia e sul ripristino superati; build
frontend riuscita. Resta la verifica finale su Alpha dopo un deploy autorizzato.

## 2. Troppi campi: decidere con il cliente

Campi attuali: Data DDT, DDT, OL, Cod. F3, Cliente, Qta, Ordine cliente,
Conferma F3, Incoming, Certificazione, Stato, Ultima lettura, Azioni.

Non togliere campi ora. Marco è stato invitato nella mail preliminare a provare
la pagina e dire quali campi gli servono. La scelta resta aperta fino al suo
riscontro; non aggiungere un selettore colonne per semplice deduzione.

## 3. Storico DDT e numero nella sidebar

Il conteggio elevato, per ora, è accettato dall'utente: comprende lo storico
recuperato. Conta quote di lavoro attive, non documenti DDT distinti e neppure
soltanto nuovi arrivi. Un DDT collegato a tre OL può produrre tre righe.
I numeri del database locale non devono essere trasferiti come attesi su Alpha.

Proposta beta: mantenere lo storico nel database, ma iniziare la vista operativa
e il badge da una data concordata. «Tagliare» significa limitare la vista,
non cancellare lo storico e non dichiararlo certificato.

Esempio puramente illustrativo: scegliendo 01/11/2026, un DDT del 31/10 resta
consultabile nello storico ma non pesa sul badge operativo; quello del 01/11
entra nella vista operativa finché non ha il proprio PDF finale valido.
La data dell'esempio NON è una decisione.

Decisioni necessarie:
- Data di partenza: da concordare con l'utente/cliente.
- Criterio confermato il 30/09: **7 giorni di calendario dalla data sul DDT**;
  giorno DDT = giorno 1 anche alle 23:59. Scadenza = data DDT + 6 giorni.
  Weekend, festività e chiusure contano; non usare `first_seen_at`.
- DDT vecchi ancora realmente da certificare: stabilire eventuali eccezioni
  per non nascondere lavoro necessario.
- DDT senza data: proporre una segnalazione Da verificare, non esclusione muta.
- DDT arrivato oggi con data precedente alla soglia: decidere se segnalarlo
  come arrivo tardivo prima di relegarlo allo storico.
- Vista Storico/tutti e permessi: concordare come renderla consultabile.

La stessa soglia condivisa deve valere per badge e popolazione operativa della
pagina; non basta un filtro salvato nel browser. Ricerca e filtri di pagina
possono poi restringere la pagina, non trasformano il badge globale in un
conteggio della sola pagina corrente. Rendere visibile la data di partenza.

La soglia non deve ridurre la lettura e conservazione dei dati eSolver,
modificare le altre pagine, alterare i PDF o segnare completate le righe escluse.
Un nuovo DDT dopo la soglia relativo a un OL vecchio rimane lavoro operativo.

Test beta: giorno prima/uguale/dopo soglia, data mancante/corretta, arrivo tardivo,
OL storico con nuovo DDT, più quote nello stesso documento, coerenza badge/vista,
consultazione dello storico, rimozione della soglia senza perdita di dati.

## 4. Situazione registrata al 30/09: spiegazione pratica

Questa tabella è storica. Al 08/10 coda, recupero e sincronizzazione sono su
Alpha; non ripetere importazioni o attivazioni basandosi sulle voci sotto.

| Passaggio | Significato pratico | Situazione |
| --- | --- | --- |
| Adeguamento UI | Solo frecce sulle intestazioni, come deciso dall'utente | Implementato in locale; deploy Alpha non richiesto |
| Deploy Alpha | Installare sul server il codice già preparato in locale | Solo dopo richiesta esplicita |
| Recupero storico Alpha | Esaminare e importare i dati recuperabili del database Alpha, non copiare quelli locali | Rifare anteprima e backup al momento; isolare ambigui |
| Lettura automatica | Rileggere periodicamente eSolver per conservare nuovi DDT e correzioni | Codice predisposto, attivazione da fare; ciclo circa 15 minuti |
| Chiusura corretta | Il PDF della quota A chiude A, non anche B dello stesso DDT/OL | Logica e test locali presenti; verifica integrata Alpha dopo deploy |
| Collegamento fermo | Avvisare dopo 4 ore senza lettura riuscita | Soglia e testo concordati; implementato in locale |
| Scadenza certificazione | Sotto Data DDT: termine e colori a 2 giorni/ultimo giorno/termine superato | Implementato in locale il 30/09; nessun deploy |
| Data iniziale beta | Alleggerire il lavoro visibile senza cancellare lo storico | Data e regole ancora da concordare con Marco |

L'avviso usa il riquadro già esistente dell'ultima lettura eSolver. Dopo quattro
ore dall'ultimo successo diventa giallo tenue e mostra: «DDT eSolver non
aggiornati da almeno 4 ore. Potrebbero mancare nuovi DDT o modifiche recenti.
I dati già acquisiti restano disponibili. Contattare il referente interno IT.»
La data/ora dell'ultimo successo resta visibile. Un errore effettivo mantiene
il rosso già presente nello stesso riquadro. Nessun successo iniziale viene
segnalato espressamente; sincronizzazione disattivata mantiene il proprio
messaggio. La pagina controlla l'ora e lo stato ogni minuto mentre è aperta.
Quando una lettura riuscita ripristina il collegamento dopo un avviso, il
riquadro diventa verde tenue e comunica l'ora del ripristino. La pagina ricarica
la tabella DDT e solo dopo la risposta mostra «Elenco DDT aggiornato»; se il
caricamento della tabella fallisce lo segnala senza dichiarare l'elenco
aggiornato. Nessun numero di nuovi DDT è mostrato.

Non promettere «nessuna lacuna»: si conserva ciò che la sorgente rende
disponibile e viene letto correttamente. Per DDT mai transitati nella cache
e ormai assenti dalla vista serve una distinta estrazione storica eSolver.
L'avviso di collegamento fermo serve a intervenire prima che la finestra
temporale della sorgente faccia perdere la possibilità di recuperarli.

### Opzioni non necessarie per avviare il lavoro

- Nuovo: etichetta temporanea per distinguere un arrivo recente dal vecchio
  arretrato. Non cambia lo stato e non significa «tutto ciò che manca».
  Durata ancora da decidere.
- Non richiede certificazione: eventuale esclusione manuale motivata per casi
  concordati, con permessi e tracciamento. Autorizzata e implementata in locale
  il 30/09: vista Esclusi, ripristino, storico e riapertura per dati modificati.
  Non è un PDF completato e non va usata per togliere in massa lo storico.
  Dettagli in [Esclusioni manuali DDT](ddt_manual_exclusions.md).

## 5. Mail preliminare già inviata a Marco, Emilio e Walter

L'utente ha riportato il testo effettivamente inviato. Non inviare altre mail
senza sua richiesta. La mail anticipa una prova su Alpha con recupero dei DDT
storici **già raccolti su Alpha**, anche quando non sono più nella vista eSolver,
per testare casi anomali. Al momento della mail era un intento di prova;
al 08/10 recupero e raccolta risultano eseguiti su Alpha. Ogni ulteriore
recupero o modifica richiede una nuova anteprima e autorizzazione operativa.

Risposte ricevute e decisioni ancora aperte:

1. **Walter, risposta 30/09:** eSolver invierà i PDF disponibili alle 23:00,
   a partire dal giorno successivo alla registrazione DDT; riproverà i mancanti
   fino al termine configurato e ne terrà traccia nei propri log. I 7 giorni
   sono il limite ai tentativi, non prova di consegna al cliente. L'utente ha
   poi confermato con Marco 7 giorni di calendario, giorno DDT = giorno 1.
   Al collaudo allineare il giorno finale e l'ultima richiesta delle 23:00;
   CERTI non dichiara spedito un PDF solo perché pronto. Nessuna richiesta di
   inviare una nuova mail o modificare eSolver.
2. **Marco:** segnalazione confermata dall'utente: giallo quando restano due
   giorni contando oggi, arancione nell'ultimo, rosso dal giorno successivo.
   Implementata in locale il 30/09 sotto Data DDT, senza nuova colonna.
3. **Marco:** provare i molti campi della nuova pagina e indicare quali servono.
   I collegamenti `Apri certificazione` e `Apri Incoming` esistono già in locale
   quando la quota ha i dati necessari; verificarli poi su Alpha.
4. **Marco:** individuare i casi per l'azione `Non richiede certificazione`.
   L'utente ha inizialmente riservato la decisione all'**amministratore Qualità**;
   motivazione, autore, data e ripristino sono stati autorizzati e implementati
   in locale il 30/09. Successivamente, nello stesso giorno, ha autorizzato
   anche gli **admin IT**. Il controllo usa ora admin nei reparti Qualità o IT;
   manager, utenti ordinari e admin degli altri reparti restano esclusi.
   Restano da raccogliere i casi pratici di Marco nel collaudo Alpha.
5. **Marco:** decidere data iniziale beta, trattamento dei vecchi DDT ancora
   da lavorare e se una riga ormai scaduta debba uscire dalla vista operativa.
   «Togliere» non autorizza la cancellazione dei dati né la marcatura come PDF.
6. **Marco:** verificare con esempi il rapporto fra nuova pagina e Registro.
   Il Registro attuale mostra certificati con numero e Word, non tutti i DDT
   recuperati. Nell'audit **locale**: 489 quote storiche anteriori al 03/08,
   164 DDT distinti, solo 4 quote abbinate con certezza a voci visibili del
   Registro (tutte bozze Word, nessun PDF finale). Attendere il giudizio di
   Marco prima di cambiare la logica del Registro. Non attribuire questi numeri
   ad Alpha.
7. **Walter, Marco, Emilio:** chiarire il caso **locale** DDT
   `1934-17/07/2026`, documento/riga `5180631/2`, OL `OL2026000466`, con
   quantità 2100 e 1 negli stessi riferimenti. Walter il 30/09 comunica di aver
   attivato nella vista il raggruppamento delle righe con tutti i dati uguali,
   sommando le quantità. Verificare la sorgente aggiornata prima di riconciliare
   lo storico: nessuna somma locale automatica o correzione dei PDF già chiusi.
   Le due vecchie quote restano fuori dal recupero automatico finché non
   verificate. Non presentarlo come caso trovato su Alpha.
8. **Emilio** e, se necessario, altri referenti come Michele: raccogliere
   avvertenze sui casi pratici da provare in Alpha.

## 6. Scadenza software autorizzata e implementata in locale (30/09)

- Unico parametro backend `DDT_CERTIFICATION_DAYS`, default 7, intero 1–365,
  passato da entrambi i Compose. Nessuna nuova schermata impostazioni.
- L'API restituisce `certification_due_date` calcolata dalla data DDT;
  nessuna nuova colonna DB, nessuna scrittura durante la lettura della coda.
- La UI mostra sotto Data DDT il termine e l'avviso. Usa il giorno italiano
  (`Europe/Rome`) e il timer esistente di un minuto, anche senza nuova lettura
  eSolver. Aggiorna l'ora anche tornando sulla scheda del browser.
- Esempio: DDT 30/09 → termine 06/10; giallo 05/10, arancione 06/10,
  rosso 07/10. Arrivi tardivi e storico conservano il termine originale.
- Data assente/non leggibile: «Data DDT da verificare», nessun termine inventato.
- PDF finale valido: sparisce dagli attivi con la logica esistente; nelle
  viste completati/tutti non riceve più l'avviso di scadenza.
- Scadenza solo informativa: non modifica stati, permessi, filtri, badge,
  blocchi di certificazione o Registro; lo scaduto rimane lavoro attivo.
- Restano fuori da questo intervento esclusione manuale, soglia beta e
  riconciliazione del duplicato corretto da Walter. L'esclusione manuale è stata
  poi implementata con autorizzazione separata nello stesso giorno; vedere il
  documento dedicato. Soglia beta e riconciliazione restano aperte. Nessun deploy.

## 7. Riduzione arretrato Alpha e avvio reale Beta — audit 08/10/2026

### Richiesta e limiti

L'utente propone di alleggerire già Alpha togliendo i DDT vecchi senza lavoro
avviato, indicativamente per avere 75–100 righe da gestire. Prima della Beta
farà una cernita più precisa: data ufficiale di avvio più giorni precedenti
concordati. Non occorre districare adesso tutto lo storico di prova.

È autorizzato questo audit e l'aggiornamento del documento, **non** la
cancellazione, una modifica al codice, il deploy o un cambiamento dei dati Alpha.
I 75–100 sono un obiettivo indicativo, non un limite che nasconde nuovi arrivi.

### Verifica concreta, in sola lettura

Database locale e Alpha interrogati in transazioni `READ ONLY`, senza importare
dati, generare documenti o attivare sincronizzazioni. Conteggi Alpha alle
19:09–19:10 UTC del 08/10, destinati a cambiare con il lavoro degli utenti.

- Alpha: 678 quote DDT, 660 attive, 17 completate, 1 esclusa.
- Locale: 882 quote, 881 attive e 1 completata; i due database sono diversi.
- Alpha: 173 record certificato numerati, dei quali 165 con Word e 18 con PDF.
  Il Registro non è una copia della coda DDT: non cancellare certificati per
  obbligare anche il Registro a restare entro 100 voci.

Simulazione prudente: proteggere l'intero OL se esiste qualsiasi record
certificato, anche incompleto o preparato prima del DDT, e gli OL con allegati
o pagine aggiuntive. Proteggere decisioni manuali, anomalie e date mancanti.
Se una quota è protetta, proteggere tutto il suo documento DDT. Non dividere
documenti con date incoerenti. È una stima conservativa, non una lista da eliminare.

| Alpha: mantenere dal giorno incluso | Quote vecchie candidabili | Quote complessive rimaste | Attive rimaste |
| --- | ---: | ---: | ---: |
| 29/09/2026 | 531 | 147 | 129 |
| 01/10/2026 | 557 | 121 | 103 |
| 02/10/2026 | 587 | 91 | 73 |
| 05/10/2026 | 598 | 80 | 62 |

Proposta: usare il **01/10 come ipotesi per la prova Alpha**, non come data
Beta decisa. Circa 103 attive permette una settimana di esempi recenti senza
forzare il numero a 100. Con la stessa soglia il locale avrebbe solo 43 attive:
non deve essere fatto coincidere numericamente con Alpha.

### Perché non eseguire un DELETE per data

1. Delle 557 quote candidabili prima del 01/10, 387 sono ancora nella vista
   eSolver: cancellandole, la raccolta le ricreerebbe.
2. Il riuso Word locale esamina tutte le quote salvate, anche storiche: un
   semplice filtro grafico non impedisce di generare lavoro fuori perimetro.
3. Stato OL, conteggio sidebar, selezione DDT e Registro devono usare regole
   coerenti. Togliere la sola riga salvata potrebbe riattivare percorsi legacy
   basati sulla cache eSolver, oltre a perdere riferimenti utili.
4. Le decisioni hanno un vincolo al DDT; documenti e relative versioni hanno
   legami propri. Il PDF chiuso e i dati esposti a eSolver non vanno alterati.

### Proposta di intervento, da approvare

1. **Prima archiviazione reversibile fuori avvio**, distinta da `Non richiede
   certificazione`: togliere dall'operativo e dal badge, conservare i dati e
   permettere il ripristino a admin IT/Qualità. Non segnare completato un DDT.
   La cancellazione definitiva resta una possibile fase pre-Beta, dopo cernita
   e backup verificato, con approvazione separata e controllo dipendenze.
2. Un'unica regola persistente di perimetro, usata da coda, badge, stato OL,
   associazione automatica dei Word e percorsi di certificazione. Continuare
   a raccogliere e conservare eSolver; rileggere una quota archiviata invariata
   non la deve riattivare. Non usare il campo `source_present` per archiviarla.
3. Per le quote operative, usare anche il DDT conservato quando esce dalla
   vista eSolver: nessuna scadenza del collegamento a 60 giorni. La soglia di
   avvio è fissa, non una finestra mobile che scarta lavoro dopo due mesi.
4. Un OL vecchio con un nuovo DDT continua a funzionare e riusa il Word.
   Un DDT mai visto prima che arriva con data vecchia, oppure dati sostanziali
   modificati di uno archiviato, richiede una segnalazione/verifica: non
   scartarlo silenziosamente per la data. Nessuna ricostruzione OL per deduzione.
5. Proteggere Word, PDF, certificati anche incompleti, allegati, versioni e
   decisioni già esistenti. Il Registro conserva quei documenti; un'eventuale
   vista più corta è un filtro di consultazione, non cancellazione documentale.
6. Prima implementazione e simulazione sul locale: anteprima dettagliata,
   backup, applicazione dopo approvazione, controllo conteggi, ripristino,
   successiva sincronizzazione, arrivi tardivi, Word riutilizzato dopo mesi,
   PDF chiusi ed export invariati. Non promettere copertura di DDT mai acquisiti.
7. Alpha soltanto su richiesta: stessa versione di codice ma **nuova anteprima
   sui dati Alpha**, elenco e numeri aggiornati, backup DB/storage e consenso
   prima dell'applicazione secondo il Markdown deploy. Nessuna copia di database,
   ID o elenco dei candidati locali. Gestire worker e utenti nella finestra
   concordata, poi controllare anche il ciclo automatico successivo.

Da decidere prima dell'implementazione: approvazione dell'archiviazione reversibile,
data della prova (proposta 01/10), modalità semplice di consultazione/ripristino.
Data ufficiale Beta, giorni di recupero iniziale e cancellazione definitiva
restano decisioni successive. Il futuro piano deploy dovrà recepire il perimetro
prima di applicare un recupero Word massivo, evitando di lavorare lo storico
che è stato deliberatamente messo fuori avvio.

### Successiva richiesta: soglia dal primo certificato Alpha

L'utente chiede di simulare il recupero/aggancio dalla data del certificato
più vecchio, invece di usare il 01/10. Nessuna applicazione Alpha autorizzata.

Audit successivo del 08/10, transazione `READ ONLY`:

- Il record più vecchio che oggi possiede un Word è `7000_00_00/26`,
  OL `OL2026000970`, creato il **20/07/2026**. Non ha `cert_date` né DDT.
  `created_at` è la creazione del record, non una prova dell'istante di
  generazione del file. È comunque la soglia prudente per includere il lavoro
  iniziato. Ben 136 documenti preparati non hanno `cert_date`.
- La data documento valorizzata più vecchia è **27/07/2026**:
  `7015_02_00/26`, OL `OL2026000724`, DDT `2028-27/07/2026`, PDF finale.
  Il relativo record è stato creato il 21/09: le due date non sono intercambiabili.
- Per la simulazione principale si adotta quindi **20/07 incluso**, conservando
  le protezioni della sezione precedente. Restano 668 quote (246 documenti DDT):
  650 attive, 17 completate, 1 esclusa. Delle quote rimaste 161 sono storiche.
  Solo 10 quote / 4 documenti sarebbero archiviabili; una quota anteriore resta
  protetta. Questa soglia non realizza l'obiettivo indicativo delle 75–100 attive.
- La simulazione alternativa al 27/07 lascia 562 quote / 544 attive; non è stata
  scelta automaticamente al posto della soglia prudente.

Provata sui dati e sui file Alpha la funzione locale `plan_item`, caricata
solamente in memoria nel processo di audit, senza installarla o applicarla:

| Risultato sulle 668 quote mantenute | Quote |
| --- | ---: |
| Riuso Word compatibile proponibile | 18 |
| Documento della quota già presente e preservato | 20 |
| Word non ancora preparato | 555 |
| OL non fornito da eSolver | 73 |
| Incoming non pronto | 1 |
| Decisione manuale da preservare | 1 |

Le 18 quote riguardano 11 DDT e 16 OL; il planner controlla identità, materiale,
Word reale e campi di spedizione. Comprendono OL finali 997 e 998 già discussi.
Nelle 161 quote storiche mantenute, 160 non hanno ancora Word e una è esclusa:
non confondere conservazione del DDT con disponibilità immediata del certificato.

Esito: nessuna eccezione del planner, nessun oggetto DB modificato, nessuna
scrittura server. Non è una prova di applicazione completa su Alpha, né un
collaudo di una nuova funzione di archiviazione (ancora da implementare).
Regressione locale del riuso Word: 19 test superati, 22 test opzionali PostgreSQL
saltati nel comando eseguito; comprende storico, DDT successivo e preservazione
del PDF precedente. Per applicare servono comunque anteprima aggiornata, backup,
deploy autorizzato e verifica dell'esecuzione effettiva.

### Decisione successiva: 01/10 con protezione del lavoro parziale

L'utente sceglie nuovamente **01/10/2026 incluso**, chiedendo di mantenere anche
righe precedenti con certificato o parzialmente complete. Questa indicazione
supera l'ipotesi del 20/07: si richiedono ricalcolo e piano, non applicazione.

Ricalcolo Alpha 08/10 alle 19:23 UTC, `READ ONLY`. Per "parzialmente complete"
la proposta prudente comprende anche standard già scelto, scelte manuali
materiale/articolo e righe Incoming individuate dal valutatore esistente, pure
se non ancora pronte. I candidati ambigui vengono conservati, non abbinati
automaticamente. Restano tutte le protezioni precedenti, incluso l'intero
documento DDT quando una sua quota è protetta.

| Alpha | Quote |
| --- | ---: |
| Totale prima della simulazione | 678 |
| Vecchie candidabili ad archiviazione reversibile | 538 |
| Mantenute complessivamente (50 documenti DDT) | 140 |
| Attive mantenute / futuro badge con questi dati | 122 |
| Completate mantenute | 17 |
| Escluse manualmente mantenute | 1 |

Le 140 quote sono 102 dal 01/10 e 38 precedenti protette. Fra le attive ci sono
23 senza OL, 77 in attesa Incoming, 13 pronte lato Incoming e 9 con stato Word
pronto nella versione Alpha installata: non confondere questi stati con un
risultato post-deploy. Le quote archiviate sarebbero 50 senza OL e 488 in attesa
Incoming; 368 risultano ancora nella vista eSolver e non devono riapparire dopo
la successiva raccolta.

Rispetto alle 103 attive stimate inizialmente, vengono protette altre 19 quote:
5 segnalate dal contesto Incoming, più 14 appartenenti agli stessi documenti.
Esempi: DDT 2143 del 02/09 (Incoming #22), 2145 del 02/09 (#79), 2254 del 16/09
(#65). Tutte e tre le righe Incoming hanno un certificato fornitore e una
valutazione salvata; questo non garantisce che ogni collegamento OL/materiale
sia già coerente, e non autorizza a forzarlo.

Il planner locale in memoria, sui dati/file Alpha mantenuti, propone ancora
18 riusi Word su 11 DDT / 16 OL, preserva 20 documenti già presenti e non forza
le altre 102 quote (77 senza Word, 23 senza OL, 1 Incoming non pronto, 1 decisione
manuale). Nessuna scrittura Alpha. Tutti i 173 record certificato, inclusi i
165 con Word e i 18 con PDF, restano fuori dalla pulizia documentale.

La stessa simulazione sul database locale mantiene 222 quote (221 attive,
1 completata), propone 660 archiviazioni e 2 riusi Word. Le differenze derivano
dai dati locali, non devono essere corrette copiando dati o ID su Alpha.

Piano da approvare: implementare prima in locale un'archiviazione persistente,
reversibile e distinta dalle esclusioni manuali; applicare la regola comune a
coda/badge/stati OL e automazioni Word, mantenere il recupero da storico per le
quote operative anche oltre 60 giorni. Prevedere consultazione/ripristino
admin e segnalazione di arrivi tardivi o modifiche sostanziali. Verificare che
nessun documento, scelta o PDF sia perso e che il ciclo eSolver non reintroduca
lo storico archiviato. Poi nuova anteprima e backup specifici Alpha, consenso
e deploy separato secondo MD. I 122 non sono un tetto: i nuovi arrivi rimangono
visibili. Beta resta produzione reale con cernita e data ufficiale successive.

### Implementazione e prova locale autorizzate

L'utente ha successivamente approvato audit esteso e implementazione locale;
il deploy resta rinviato a sua indicazione. Implementati archivio reversibile,
protezione del lavoro parziale e dell'intero DDT, recupero operativo da storico
oltre la finestra eSolver e procedura separata per il DB Alpha nel MD deploy.

Prova locale 08/10: 660 quote archiviate, 222 mantenute (221 attive + 1 completata),
nessuna cancellazione. Impronte delle altre 43 tabelle e dei 45 file Word/PDF
invariate. 582 test backend superati, inclusi PostgreSQL isolato; verifica UI e
build superate. Alpha solo audit read-only: confermati 538 archiviabili e 140
mantenuti come simulazione, non come modifica già applicata.

Dettagli, eccezioni e prove:
[`ddt_archive_history_20261008.md`](ddt_archive_history_20261008.md).

## Registro aggiornamenti

| Data | Decisione o aggiornamento | Stato |
| --- | --- | --- |
| 29/09/2026 | Contatore alto per storico accettabile per ora | Indicazione utente, nessuna riduzione attuale |
| 29/09/2026 | Riduzione campi rimandata al cliente | Da discutere nella prossima email |
| 29/09/2026 | Soglia di partenza per beta | Intenzione utente; data e trattamento eccezioni da definire |
| 29/09/2026 | Frecce e avviso a 4 ore con referente interno IT | Autorizzati, implementati e verificati in locale; nessun deploy |
| 29/09/2026 | Messaggio di ripartenza e ricarica tabella DDT | Autorizzati, implementati e verificati in locale; nessun deploy |
| 29/09/2026 | Mail preliminare riportata dall'utente | Inviata a Marco, Emilio e Walter; risposte aperte annotate sopra |
| 30/09/2026 | Risposta Walter, 7 giorni calendario inclusivi e colori | Autorizzati e implementati in locale; nessun deploy |
| 30/09/2026 | Esclusione singola quota, ripristino e storico | Autorizzati e verificati in locale, riservati ad admin Qualità; nessun deploy |
| 30/09/2026 | Estensione esclusione e ripristino agli admin IT | Richiesta e implementata in locale; controlli server e UI allineati |
| 08/10/2026 | Beta = uso reale in produzione, non test | Decisione utente registrata; data ufficiale e giorni precedenti da scegliere |
| 08/10/2026 | Audit alleggerimento storico locale e Alpha | Sola lettura; proposta archiviazione reversibile e soglia 01/10, nessuna modifica applicativa o cancellazione |
| 08/10/2026 | Simulazione dalla data del primo certificato Alpha | Soglia prudente 20/07: 650 attive, 18 agganci Word proponibili; nessuna applicazione sul server |
| 08/10/2026 | Ritorno al 01/10, mantenere anche lavoro parziale | Ricalcolo Alpha: 122 attive, 538 quote archiviabili, 18 agganci Word proponibili; piano non applicato |
| 08/10/2026 | Implementazione e prova locale autorizzate | 660 quote archiviate reversibilmente, 221 attive; 582 test backend superati; Alpha non modificato, procedura nel MD deploy |
