# Manutenzione Alpha del 28 ottobre 2026

## Esito conclusivo — Alpha riaperta e timer verificato

Alpha riaperta alle 14:24 italiane del 28/10/2026 (13:24:04 UTC). Backend,
frontend e accesso pubblico 200; versione applicativa 0.1.0.alpha.10 coerente.
Restano attivi entrambi i flag snapshot/riuso, PostgreSQL e altro stack invariati.
Timer naturale 15 minuti verificato separatamente alle 14:39 italiane; nessuna
sincronizzazione manuale. Il resoconto aggiorna lo stato storico della
manutenzione, non autorizza altre operazioni.

- Sorgente app pubblicato: `9a2a98e53aed53db6a61224aebf6f6fb444056b0`.
- Deploy pubblicato: `322a9f0b2bb2e19fc2be2dd44207aa280ad698d5`.
- Tag immutabile `v0.1.0-alpha.10.6-deploy`; archivio SHA256
  `3e71bbf9ef5b786076439cd179c125e91f2cd30f222a4b146d088ef7002d8184`.
- 454 file sorgenti confrontati integralmente. Runtime backend derivato dalla
  candidata 10.5 verificata, tutti i layer precedenti/configurazione conservati,
  nessun aggiornamento dipendenze. Frontend riutilizzato solo dopo confronto
  completo identico di sorgenti/configurazione; nessuna build Node aggiuntiva.
- Collaudo della candidata server: 6 controlli vuoti, 6 DOCX, 16 ciclo Word,
  7 recupero metadati superati. I 29 casi PostgreSQL saltati nella candidata
  senza DB erano inclusi nei 127 dedicati eseguiti localmente.
- Piano Word nuovo `d56298de2c86cd3d0243b82d4e9701055fcb3bae937067092c61610189e7709b`,
  nuova approvazione esplicita. Commit recupero riuscito: quota 894→certificato 313,
  fonte 62, numero 7044_00_00/26, DDT 2626-27/10/2026, quantità 2330.
- Tutti i 312 record precedenti invariati salvo i quattro metadati approvati;
  tutte le 102 versioni PDF e le 98 righe export identiche. Tutti i 3983 file precedenti
  invariati, un solo nuovo Word, nessun PDF generato. Nessuna copia del DB locale.
- Tutte le 24 parti del Word pubblicato identiche alla copia locale renderizzata
  e verificata. SHA256 Word nuovo
  `a260b0666896cb0098f9af0a9dff1335c3440c60456f1e9974bf8b903c8f4ebc`.
  Ordine/conferma/DDT/quantità blu; numero/data invariati, confermato dall'utente.
- Seconda preview `072f7f83888ef8a8d615458acfc777d642701f8cb7f3884aefac4193fdec0986`,
  zero riusi: quota 894 già predisposta. Non rieseguire i recuperi.
- Proiezione read-only reale: 894 `word_ready` con azione PDF 313;
  895/896 `completed` con PDF 296/297 invariati; 898/899 restano Incoming in attesa
  per CDQ 24-0985 mancante/materiale cambiato. Nessuna forzatura dei casi reali.
- Controllo Chromium sul bundle pubblico, con TUTTE le API simulate e nessuna
  scrittura: riferimenti/avvisi corretti, nessun errore JS/debordo. Non è una
  generazione PDF reale né una verifica interattiva autenticata dei dati Alpha.
- Ulteriore prova UI con la quota 894 rilevata in transazione READ ONLY e poi
  riprodotta nel browser isolato: Word presente, pulsante Genera PDF abilitato,
  collegamento alla quota corretta, conferma con numero 7044_00_00/26 e nome
  `7044_00_00_26.pdf`. Finestra aperta e annullata senza generazione; tutte le API
  intercettate, zero scritture, zero errori JS e nessun debordo della pagina.
  Schermate di riga e finestra esaminate; lo scroll interno della tabella rimane.
- Audit lifecycle read-only dopo riapertura: 313 certificati (215 draft,
  98 PDF finali), 87 riferimenti controllati da conservare, zero problemi di
  identità e zero riferimenti con integrità discordante. I 12 riferimenti a
  basi manuali storiche restano conservati: non sono una lista da cancellare.
- Timer ordinario: run DDT 2491 `success`, 648 righe sorgente, dalle
  13:39:08 alle 13:39:09 UTC; successivo run Quarta 10028 `ok`, dalle 13:39:09
  alle 13:39:39 UTC, senza utente trigger. `timer_monitor.json` verificato
  alle 13:39:47 UTC. Non confondere le 648 righe lette con nuovi DDT o certificati.
- Controllo conclusivo alle 13:40:19 UTC: backend/frontend/pubblico HTTP 200,
  risposte rispettivamente 0,032/0,001/0,002 secondi; zero riavvii dei tre servizi
  verificati e zero traceback backend dal riavvio autorizzato. Entrambi i flag
  snapshot/riuso restano attivi. Durante il ciclo Quarta la precedente prova
  health ha superato il timeout di 15 secondi: conservare questa evidenza,
  non dichiarare assenza di rallentamenti. Quarta ha terminato autonomamente
  dopo circa 30 secondi; nessun riavvio o forzatura per far passare il controllo.
  Il rallentamento del refresh Quarta sincrono era già documentato nel verbale
  24/10; la concomitanza odierna è coerente ma non prova da sola la causa interna.
  Il deploy corregge il ciclo Word, non questo limite prestazionale.
- Spazio dopo riapertura: root 7.409.623.040 byte disponibili, dati 84.758.839.296.
  Dati e backup condividono lo stesso filesystem: non sommare due volte.
  Nessuna pulizia effettuata; backup e immagini precedenti conservati.

Il container PostgreSQL QA temporaneo locale è stato chiuso dopo i collaudi;
conteneva soltanto copie di test in RAM. Backup SQL/storage/app, report e
journal restano conservati. I servizi CERTI locali ordinari non sono stati
riavviati né modificati da questo collaudo.

### Differenza del report Windows risolta senza cambiare dati

Il confronto record completo ha inizialmente segnalato solo il nome cliente
dei record 73/277: `Ü` era stato decodificato come `Ãœ` dal `text=True` di Python
su Windows nel report privato. Non era una modifica Alpha o corruzione del dump.
Riconfrontate tutte le 44 tabelle del restore originario con le impronte SQL del
backup: identiche. Riesportati i record con decodifica UTF-8 esplicito; differenza
limitata e dimostrata ai due soli testi. Conservato `protected_records.json`
originario e aggiunto `protected_records_utf8.json`, hash verificato PC/server.
Le guardie restano integrali, non ignorano i campi cliente. Per futuri audit
usare sempre encoding esplicito per JSON/SQL cross-platform.

## Stato storico prima del completamento

Alpha 10.5 installata ma non riaperta. Questa nota non è un esito di deploy.
La successiva approvazione dell'utente autorizza correzione in locale e nuovo
pacchetto; nessun intervento diretto ai sorgenti sul server.

- Sorgente 10.5 `dd6ce47a313f4aa6d34693f2a349f156eef21fe3`, deploy `043aecf`.
- Tag `v0.1.0-alpha.10.5-deploy`, archivio SHA256
  `5896d10a7b45a7d61dc73bfa400c3f7782adf53033b80f321281a3398cb84f46`.
- Backup unico `20261028_120400`, sul server e nel PC; ripristino DB isolato
  verificato su tutte le 44 tabelle e confronto fisico di 447 file app e
  3983 file storage. Conservare backup, baseline e journal, mai Git/web.
- Solo backend/frontend Alpha fermi; PostgreSQL e altro stack restano attivi.
- Quattro recuperi metadati approvati/applicati: ID62/268/285/308, piano
  `ea3efafaccfba921c1797d57d9475370fc54fac98671cda61c16f4fa9261adc0`.
  Nessun ID, numero, Word, PDF, versione o export modificato.
- Autorizzata una copia Word per quota 894, OL1087/F3 449000700, DDT 2626 del
  27/10/2026, quantità 2330, fonte 62. Entrambi i tentativi falliti senza commit
  e senza nuovo file pubblicato: `shipment_fields_not_updated`.

## Causa e correzione locale

Il Word anticipato conserva i tag ma cinque campi sono SDT plain-text con
`sdtContent` completamente vuoto: data, ordine, conferma, DDT, quantità.
Il vecchio updater sostituiva solo un nodo testo già presente. Non è un errore
dell'operatore né un motivo per togliere i controlli d'integrità.

La correzione riempie quei controlli vuoti, anche con run vuoto o testo
self-closing, senza cercare dati nei campi vicini. Non ricostruisce controlli
mancanti, rich content, disegni, campi Word o strutture non riconosciute.
Preserva stile esistente; quando il run manca del tutto usa lo stile del
generatore CERTI (valori tabella blu, Times New Roman 10/9; numero/data Arial 10).
La verifica dei valori, delle impronte e dell'identità resta obbligatoria.

Prova sul Word reale nel backup read-only: fonte SHA256
`4b372aba3dfa8c34adbfa924782a585ad1203caaef827cd175957b9dfc4568dc`.
Cambiano solo i sette valori previsti in `word/header1.xml`; tutte le altre
parti identiche, impronta tecnica invariata. Copia attuale e simulazione
successiva `200 of 23000` restano di due pagine, con laboratorio, immagine e
firmatari invariati. Rendering eseguito col convertitore reale dell'app in
container locale senza rete; immagini controllate. Nessun PDF Alpha generato.
Le prove visive non sono una nuova validazione normativa del contenuto storico.

Simulazione completa sul database del backup, clonato in un secondo DB locale
isolato (mai sul database operativo): dopo i quattro metadati già approvati,
preview con una sola azione quota 894, apply riuscito con un solo Word e nessun
PDF. Tutti i sette campi corretti; impronta tecnica e fonte invariati. Seconda
preview con zero riusi. Il numero ID313 della prova è SOLO locale, non quello da
imporre ad Alpha. Suite finale: 826 casi scoperti, 699 generali superati e 127
PostgreSQL saltati nel runtime senza DB. Eseguiti separatamente tutti i 127 su
DB dedicato: superati. Sei test mirati sui controlli e ripetizione del nuovo
ciclo PostgreSQL dopo lo stile blu: superati. Nessun caso richiesto rimasto
saltato. Prima prova della fixture corretta per assegnare il DDT iniziale prima
di confrontare il progressivo successivo; nessuna modifica alla numerazione.

## Condizioni applicate per il completamento — non rieseguire

1. Test unitari/regressioni e PostgreSQL dedicato prima del nuovo commit.
2. Pacchetto completo da commit pubblicato, nuovo tag 10.6; confronto integrale
   alberi/hash. Frontend riutilizzabile solo con sorgenti/configurazioni identici.
3. Verificare ancora writer fermi e baseline: tutti i vecchi dati/file invariati
   salvo i quattro soli metadati approvati. Conservare anche lo stato 10.5.
4. Installare solo il pacchetto verificato, `.env` intatto, nessuna migrazione.
5. Nuova preview con codice candidato: deve proporre soltanto quota 894 da 62.
   Nuovo piano/OK esatto prima di applicare; non riusare il piano scaduto 10.5.
6. Verificare un solo nuovo Word/destinazione, nessun PDF nuovo; tutti i 312
   record precedenti protetti, 102 versioni PDF, 98 righe export e 3983 file invariati.
7. Seconda preview senza ulteriore azione sulla quota; riaprire e verificare
   salute, bundle, UI, flag snapshot/riuso e timer ordinario. Nessuna falsa
   chiusura se una prova fallisce. Aggiornare qui l'esito effettivo.

## Ripresa e rollback

Non ripetere i quattro recuperi metadati già committati. Backup iniziale più
journal descrivono esattamente le variazioni; non restaurare il DB operativo
per annullare il solo codice. Non cancellare originali, copie valide, vecchie
basi, quote o immagini di rollback. Una regressione richiede diagnosi e piano
compatibile con i dati correnti, non riapertura automatica o flag riuso spento.
OL986 / quote 898–899 mantiene i reali impedimenti Incoming/materiale: non forzare.
