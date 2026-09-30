# Passaggio alla beta - decisioni e verifiche aperte

Aggiornato: 30/09/2026, dopo risposta Walter e regole scadenza confermate dall'utente.
Stato: documento di lavoro, non autorizzazione a modificare codice o server.

La versione locale pubblicata è `0.1.0.alpha.10`. La nuova coda DDT è stata
sviluppata e collaudata in locale; il suo deploy, recupero storico e avvio
automatico su Alpha richiedono ancora il via libera dell'utente.

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

## 4. Cosa manca: spiegazione pratica

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
per testare casi anomali. Questo è un intento di prova, non un deploy già fatto:
anteprima, backup, recupero e attivazione richiedono ancora l'autorizzazione
operativa dell'utente secondo il piano Alpha.

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
   L'utente ha stabilito che può deciderla solo l'**amministratore Qualità**;
   motivazione, autore, data e ripristino sono stati autorizzati e implementati
   in locale il 30/09. Il controllo permessi verifica specificamente reparto
   Qualità e ruolo admin: l'helper generico di area Qualità include anche IT.
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
