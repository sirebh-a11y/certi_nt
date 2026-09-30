# Gemba: filtro semplice per giorno e ora di caricamento

## Richiesta e decisione — 30/09/2026

Due camion dello stesso fornitore, caricati in momenti diversi, devono poter
essere stampati separatamente. Se vengono caricati insieme, la stampa congiunta
va bene. Deve funzionare anche con solo certificato, senza aggiungere colonne,
spunte o due date alla griglia Incoming.

Finestra esistente **Gemba walk**: `Giorno` (oggi in Italia), `Dalle ore`
(`00:00`), `Alle ore` (`23:59`), `Crea stampa`. I filtri e la vista Incoming
continuano ad applicarsi. L'intero minuto finale e incluso. Orari italiani
Europe/Rome, con conversione UTC e gestione ora legale. I vecchi URL con
date_from/date_to rimangono utilizzabili; senza ore comprendono giorni interi.

## Audit Alpha in sola lettura

- 151 righe: 148 abbinate, 2 solo DDT, 1 solo certificato.
- Metalba 29/09: 10 righe caricate 09:02–09:03 e 9 righe 14:34–14:36.
  L'ora di creazione era rispettivamente 10:01–10:05 e 15:44–15:50.
- Riga 68: upload DDT 22/07 08:43, creazione riga 14:47.
- Riga 134: DDT 03/09, certificato 11/09: usare l'ultimo aggiornamento
  farebbe spostare il materiale nella giornata sbagliata.
- 25 eventi di unione certificate-first/DDT; 26 righe hanno certificato
  caricato prima del DDT. Nessun certificato attuale condiviso tra DDT distinti,
  ma tale possibilita e supportata dal codice e coperta nei test.
- I batch upload vengono azzerati promuovendo i documenti a persistenti:
  non sono un riferimento durevole del camion.

## Regola implementata

Nuova colonna interna `datimaterialeincoming.incoming_loaded_at`, non editabile
dalle API utente. Una sola scritta nella sottoriga fornitore gia presente:
`Caricato gg/mm/aaaa, hh:mm`. Il filtro usa esattamente questo riferimento.

- Creazione automatica/manuale: ora upload del documento che genera la riga,
  non fine AI. Con DDT e certificato gia insieme, origine DDT.
- Riga senza documenti: ora iniziale della riga.
- Certificato prima del DDT: conserva il riferimento quando viene collegato.
- Unione effettiva di due righe: conserva il riferimento piu vecchio delle due;
  lock insieme ai valori qualita e nessuna copia alle altre righe sorelle.
- Certificato riusato su una nuova consegna: mantiene l'origine del nuovo DDT.
- Duplicazione di una riga DDT per altro certificato dello stesso carico:
  conserva l'ora del carico. Separazione manuale: entrambe le parti conservano
  il riferimento; se il certificato separato viene riusato per un'altra
  consegna, non retrodata quest'ultima. L'evento di separazione identifica il caso.
- Nessuna modifica alle date originali dei documenti, accettazione, match,
  chimica/proprieta/note, KPI o Registro per calcolare il filtro.

Il filtro indica il caricamento in CERTI, non prova l'ora fisica di arrivo del
camion. Gli orari non sono usati per creare o modificare abbinamenti.

## Migrazione e futuro deploy

Bootstrap additivo e ripetibile: colonna nullable + indice. Per lo storico con
riferimento assente: upload DDT, altrimenti upload certificato, altrimenti
creazione riga. Non ricostruire come certa un'origine eliminata dalle vecchie
unioni. I valori gia assegnati non vengono sovrascritti agli avvii successivi.

Applicata automaticamente nel solo ambiente locale dal reload backend:
96 righe presenti, 96 riferimenti valorizzati. Alpha non e stato modificato.
Per il deploy futuro seguire `docs/deploy/alpha_soft_update_server.md`, fare
backup e verificare la nuova colonna prima di considerare il deploy concluso.

## Verifiche

- Test su DB SQLite isolati: mattina/pomeriggio, AI tardiva, solo certificato,
  caricamenti simultanei, estremi del minuto, cambio ora/giorno italiano,
  merge in entrambi gli ordini, riuso, separazione, clone, backfill idempotente,
  mantenimento filtri/vista e serializzazione della data unica.
- Regressioni: package count, unioni qualita, ciclo match, chiusure pendenti e
  Metalba LST03. Verifica API del passaggio ore e formato invalido.
- Browser Chromium, frontend reale su 5174, API simulate: giorno italiano
  anche da un browser in altro fuso, predefiniti, errore intervallo, query
  stampa, data unica, layout a 1440/1920/600 px, 13 colonne stampa come prima.
- Build frontend e controllo diff. Frontend abituale riavviato su richiesta
  dell'utente; container attivo e moduli aggiornati serviti su porta 5173.

Esito: 98 test del gruppo di regressione superati; dopo l'aggiunta del test
API, 11 test dedicati Gemba superati (99 casi distinti complessivamente).
Build e collaudo browser riusciti. Dopo il riavvio, la risposta HTTP 200 sulla
porta abituale 5173 contiene `incoming_loaded_at` e `gembaTimeFrom`. La prova
visiva e stata eseguita sul frontend temporaneo 5174, poi arrestato. Nessun
deploy Alpha eseguito.

Artefatti temporanei: `tmp_eval/packages_qa/gemba_load_time_check.mjs`,
`tmp_eval/gemba-filter-*.png`, `tmp_eval/gemba-incoming-time.png`.
