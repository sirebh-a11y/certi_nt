# Manutenzione Alpha del 28 ottobre 2026

## Stato prima del completamento

Alpha10.5 installata ma non riaperta. Questa nota non è un esito di deploy.
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
- Autorizzata una copia Word per quota894, OL1087/F3 449000700, DDT2626 del
  27/10/2026, quantità2330, fonte62. Entrambi i tentativi falliti senza commit
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
generatore CERTI (valori tabella blu, Times New Roman 10/9; numero/data Arial10).
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
preview con una sola azione quota894, apply riuscito con un solo Word e nessun
PDF. Tutti i sette campi corretti; impronta tecnica e fonte invariati. Seconda
preview con zero riusi. Il numero ID313 della prova è SOLO locale, non quello da
imporre ad Alpha. Suite finale: 826 casi scoperti, 699 generali superati e127
PostgreSQL saltati nel runtime senza DB. Eseguiti separatamente tutti i127 su
DB dedicato: superati. Sei test mirati sui controlli e ripetizione del nuovo
ciclo PostgreSQL dopo lo stile blu: superati. Nessun caso richiesto rimasto
saltato. Prima prova della fixture corretta per assegnare il DDT iniziale prima
di confrontare il progressivo successivo; nessuna modifica alla numerazione.

## Condizioni per il completamento

1. Test unitari/regressioni e PostgreSQL dedicato prima del nuovo commit.
2. Pacchetto completo da commit pubblicato, nuovo tag10.6; confronto integrale
   alberi/hash. Frontend riutilizzabile solo con sorgenti/configurazioni identici.
3. Verificare ancora writer fermi e baseline: tutti i vecchi dati/file invariati
   salvo i quattro soli metadati approvati. Conservare anche lo stato 10.5.
4. Installare solo il pacchetto verificato, `.env` intatto, nessuna migrazione.
5. Nuova preview con codice candidato: deve proporre soltanto quota894 da62.
   Nuovo piano/OK esatto prima di applicare; non riusare il piano scaduto 10.5.
6. Verificare un solo nuovo Word/destinazione, nessun PDF nuovo; tutti i312
   record precedenti protetti, PDF/versioni/export98 e3983 file invariati.
7. Seconda preview senza ulteriore azione sulla quota; riaprire e verificare
   salute, bundle, UI, flag snapshot/riuso e timer ordinario. Nessuna falsa
   chiusura se una prova fallisce. Aggiornare qui l'esito effettivo.

## Ripresa e rollback

Non ripetere i quattro recuperi metadati già committati. Backup iniziale più
journal descrivono esattamente le variazioni; non restaurare il DB operativo
per annullare il solo codice. Non cancellare originali, copie valide, vecchie
basi, quote o immagini di rollback. Una regressione richiede diagnosi e piano
compatibile con i dati correnti, non riapertura automatica o flag riuso spento.
OL986/quote898–899 mantiene i reali impedimenti Incoming/materiale: non forzare.
