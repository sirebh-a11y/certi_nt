# Passaggio alla beta - decisioni e verifiche aperte

Aggiornato: 29/09/2026.
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

Non togliere campi ora. Chiedere quali servono subito e quali possono stare
nel dettaglio o essere nascosti su scelta dell'operatore. Decidere anche se
alcuni filtri possono stare in una sezione aggiuntiva. Riportare il punto nella
prossima email richiesta dall'utente, senza inviarla autonomamente.

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
- Proposta di criterio: Data DDT, non giorno di importazione; da confermare.
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
| Data iniziale beta | Alleggerire il lavoro visibile senza cancellare lo storico | Data e regole ancora da concordare |

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
  concordati, con permessi e tracciamento. Non è un PDF completato e non va
  usata per togliere in massa lo storico. Non implementata né autorizzata.

## 5. Punti per la futura email al cliente

Quando l'utente chiederà l'email:
1. Far scegliere campi essenziali, campi di dettaglio ed eventuali filtri avanzati.
2. Spiegare che ogni riga è una quota DDT/OL e che lo storico alza il conteggio.
3. Concordare data iniziale beta ed eccezioni per arretrati ancora da lavorare.
4. Richiamare il caso locale DDT 1934-17/07/2026, OL2026000466,
   documento/riga 5180631/2, con quantità discordanti 2100 e 1: dettagli nel
   piano DDT. Chiedere chiarimento, senza attribuire una causa non dimostrata;
   nessuna scelta/somma automatica. Non presentarlo come caso trovato su Alpha.
5. Concordare tempi degli avvisi di lettura ferma ed eventuali opzioni aggiuntive.

## Registro aggiornamenti

| Data | Decisione o aggiornamento | Stato |
| --- | --- | --- |
| 29/09/2026 | Contatore alto per storico accettabile per ora | Indicazione utente, nessuna riduzione attuale |
| 29/09/2026 | Riduzione campi rimandata al cliente | Da discutere nella prossima email |
| 29/09/2026 | Soglia di partenza per beta | Intenzione utente; data e trattamento eccezioni da definire |
| 29/09/2026 | Frecce e avviso a 4 ore con referente interno IT | Autorizzati, implementati e verificati in locale; nessun deploy |
| 29/09/2026 | Messaggio di ripartenza e ricarica tabella DDT | Autorizzati, implementati e verificati in locale; nessun deploy |
