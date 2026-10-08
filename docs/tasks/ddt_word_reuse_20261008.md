# Word unico per lavorazione, quote DDT successive — audit e correzione

Data: 08/10/2026. Piano approvato dall'utente; implementazione solo locale.
Alpha consultata in sola lettura, senza deploy, cambi dati o documenti.

## Regola

Il Word della lavorazione gia preparato si riutilizza per ogni quota DDT
successiva, anche dopo mesi. Nuova riga e dati della sua spedizione, PDF chiuso
dall'utente. Non si conosce il numero finale di DDT dell'OL. I messaggi riguardano
i DDT ricevuti, non una chiusura definitiva dell'OL.

## Errore Word e riproduzione

Sul codice Alpha `3951822f`: ricerca fonte che esclude il medesimo numero
certificato, selezione del record recente vuoto invece del Word gia creato,
Registro che nasconde i record senza Word, propagazione assente nel contesto
DDT puntuale. Il job snapshot da solo non prepara tutte le associazioni Word.

OL2026000997: Word preparato il 28/07 senza DDT (backup Alpha del 01/10).
Riga certificato 16: DDT 2354-29/09/2026, 3000 pezzi, PDF chiuso.
Riga 148: DDT 2397-05/10/2026, 1398 pezzi, Word mancante.

Nuova pianificazione verificata sulle otto quote Alpha con database read-only,
codice di verifica eseguito solo in memoria, nessun file installato o generato:

| Quota | OL | DDT | Destinazione | Fonte Word | Esito |
|---|---|---|---|---|---|
| 300 | OL2026000995 | 2293-23/09/2026 | 108 | 9 | Riutilizzabile |
| 453 | OL2026001090 | 2375-01/10/2026 | 137 | 71 | Riutilizzabile |
| 626 | OL2026000967 | 2386-02/10/2026 | 153 | 2 | Riutilizzabile |
| 627 | OL2026000967 | 2386-02/10/2026 | 154 | 2 | Riutilizzabile |
| 646 | OL2026001001 | 2394-05/10/2026 | 152 | 12 | Riutilizzabile |
| 652 | OL2026000997 | 2397-05/10/2026 | 148 | 16 | Riutilizzabile |
| 662 | OL2026001083 | 2413-07/10/2026 | 159 | 85 | Riutilizzabile |
| 665 | OL2026001043 | 2416-07/10/2026 | 158 | 31 | Riutilizzabile |

Le quote 626/627 sono distinte: non deduplicare per solo numero DDT.
Questa verifica non autorizza il recupero e non sostituisce la preview al deploy.

## Nuovo caso: 73 DDT "Da collegare"

Confrontata direttamente la vista eSolver corrente (507 righe) con lo snapshot
Alpha: 73 righe hanno ORP/OL assente in entrambe le fonti, tutte ancora presenti
in eSolver; nessuna differenza nel campo OL per le identita confrontabili.
Non e la conseguenza del Word mancante e non e una perdita del parser CERTI.

- 33 hanno lotto numerico; tutti corrispondono al nome di un OL presente in Quarta
  se si antepone `OL`. E un indizio, NON una regola di associazione verificata.
- 36 hanno lotto `SPRING`; le altre 4 hanno altri riferimenti.
- Esempi: DDT 2424/documento 5241445/riga 1 e 2421/documento 5241368/riga 1
  hanno `SPRING`, ORP assente. DDT 2417/documento 5240354/riga 1 ha lotto
  `2026001054`, ma ORP assente. DDT 2392/documento 5236230 righe 1 e 2 ha
  lotti `2026000958` e `2026000957`, ORP assente.

Da chiarire con Walter/Nemesi: perche ORP non viene valorizzato nei casi numerici;
quali righe `SPRING`/altre riguardano articoli senza OL o senza certificazione.
Nessun collegamento automatico aggiunto da lotto/CodF3/cliente. Quando eSolver
fornisce ORP, rimane la riconciliazione esistente (solo sostituzione univoca di
identita); duplicati/conflitti restano da verificare. Admin Qualita/IT puo usare
l'esclusione gia presente, dopo decisione operativa, senza cancellare lo storico.

## Implementazione locale

- `ddt_word_reuse.py`: pianificazione in sola lettura e copia su nuovo file per
  la stessa lavorazione. Verifica OL, CodF3, CDQ/colate/articolo/lotti, numero,
  contenuto Word e allegati; fonti discordanti non sono scelte per recenza.
- Si modificano solo controlli dinamici di spedizione. Contenuti tecnici, testo
  manuale e seconde pagine restano nel Word; vengono conservati gli allegati.
  Se mancano i controlli necessari, nessuna generazione da zero automatica.
- Record vuoti esistenti riutilizzati; nuovi record solo per quote certe e senza
  conflitti. Word gia presenti, PDF chiusi, versioni e numerazioni preservati.
- Worker predisposto ogni 15 minuti, attivazione esplicita `DDT_WORD_REUSE_ENABLED`
  (default false). Nessun nuovo campo/tabella. Non dipende dall'apertura pagine.
- Dettaglio trova il Word gia creato anche se la riga piu recente e vuota;
  richiesta ripetuta non rigenera il documento. Contesto DDT e rigenerazione
  esplicita restano distinti. Protezioni dei PDF chiusi mantenute.
- Registro include righe numerate senza Word con messaggio di verifica, senza
  abilitare PDF. Coda distingue incompatibilita Word da assenza OL in eSolver.
- Riepilogo OL considera le quote conservate, incluse quelle fuori finestra
  eSolver, e le esclusioni valide. Non cambia i due filtri in nuovi automatismi.
- Controllo live di conformita prima del PDF mantenuto; il riuso non conferma
  Incoming, non sceglie standard e non invia documenti al cliente.

## Verifiche e limiti

- Suite generale backend rieseguita sul codice finale: 535 test superati,
  nessuno saltato, inclusi PostgreSQL isolato, concorrenza e lock di recupero
  (writer attivo rifiutato, applicazione consentita a writer fermi).
- Frontend: build riuscita; avvisi preesistenti Browserslist/bundle, nessun
  aggiornamento automatico delle dipendenze.
- Chromium locale, pagina React reale e API simulate: PDF chiuso, nuova quota
  in attesa, Word riutilizzato; niente Genera Raw quando Word presente, blocchi
  corretti, 1440/1920 px, nessun errore JS o richiesta mutante. Artefatti in
  `tmp_eval`, fuori Git. Il frontend abituale non viene riavviato per questi test.
- Casi coperti: arrivo dopo mesi/PDF chiuso, Word anticipato e piu DDT,
  idempotenza, quote storiche, testo manuale/allegati, fonti discordanti, colata
  diversa, Incoming incompleto, controlli Word mancanti, errori file, preview
  read-only, report superato, Word riutilizzato fino alla chiusura PDF simulata.
- Non e una garanzia di assenza assoluta di difetti: recupero effettivo, primo
  ciclo Alpha e nuovo DDT reale devono essere verificati al deploy/successivo arrivo.

Procedura e comandi: `docs/deploy/alpha_soft_update_server.md`, sezione 08/10.
Nessun commit, push, deploy o recupero Alpha implicito in questo lavoro.
