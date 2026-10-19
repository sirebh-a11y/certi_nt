# Progressivo certificato per DDT e quantità parte del totale

## Perimetro approvato

Implementazione locale, nessuna pubblicazione o scrittura Alpha autorizzata.
Il numero della spedizione è distinto dal riferimento tecnico Word OL/F3.
Si conservano le tre componenti storiche e l'anno del numero base; i successivi
documenti DDT aggiungono una quarta componente `_01`, `_02`, ecc. prima di `/26`.
Il primo DDT senza precedenti conserva il numero base. Un Word anticipato senza
DDT non consuma un progressivo. L'ordine è di assegnazione in CERTI: un vecchio
DDT acquisito tardi non rinumera i certificati già assegnati.

- Esempio nuovo flusso: `7051_00_00/26`, `7051_00_00_01/26`, `7051_00_00_02/26`.
- Stesso IdDocumento, OL e F3: stesso numero per tutte le righe, ma documenti e
  PDF distinti per le singole quote. Ordini cliente diversi non separano il totale.
- Riga 29 + riga 91: `29 of 120`, `91 of 120`. Una sola riga: `118`.
- La quantità numerica resta separata dal testo; nessun peso Quarta come ripiego.
- Quantità singola assente: il Word preliminare può rimanere vuoto come prima.
  Gruppo con quantità sconosciute/negative o identità ambigue: non inventare un totale.
- Il totale comprende le quote fisiche conservate, anche fuori finestra eSolver
  o escluse/nascoste nella coda; non somma record certificato o versioni PDF.

## Compatibilità e dati storici

Nuova colonna JSON nullable `shipment_context`: base, sequenza, gruppo, quantità
totale e impronta delle righe. È indipendente da `word_reference` e dalla norma.
Preparazione `ddt_shipments.ensure_schema(connection)`, idempotente, solo DDL:
nessun backfill, scelta del riferimento storico o modifica a file/numero esistenti.

I numeri già assegnati sono preservati, compresi i vecchi Word aperti. Non
rinumerare automaticamente il DDT2418 di OL1090 né gli altri PDF chiusi con
numeri condivisi. La nuova numerazione vale per nuovi documenti DDT; le quote
di un DDT già numerato recuperano il numero assegnato a quel gruppo.
`preview_legacy(db)` produce soltanto conteggi/ID di Word aperti e numeri
storici condivisi tra DDT, anche PRIMA dell'aggiunta della nuova colonna.
La rigenerazione esplicita può adottare il nuovo totale mantenendo il numero;
un semplice accesso non migra i Word storici. Nessuna riapertura massiva.

I nuovi Word gestiti aggiornano i soli campi di spedizione. Un totale cambiato
viene ricontrollato dopo la conversione PDF; la chiusura condivide brevemente
il lock della raccolta snapshot, per evitare un aggiornamento tra verifica e
commit. Se il collegamento è impegnato si richiede di riprovare, non lo si forza.
Le copie automatiche con impronta integra possono aggiornare il totale; una
modifica manuale non viene sovrascritta dal worker. I PDF chiusi sono immutabili.

## Riuso ed ereditarietà

Il confronto tecnico può ignorare il numero della spedizione, ma verifica che
il controllo CERT_NUMBER presente corrisponda al numero salvato. L'impronta
storica di `word_reference` resta nel suo formato originale: non invalidare
i riferimenti già pubblicati cambiando retroattivamente l'algoritmo hash.
Tra lavorazioni diverse resta Raw-first; per DDT successivi della stessa
lavorazione restano le sue pagine complete e gli allegati. Il progressivo non
deve provocare falsi conflitti tra copie equivalenti o una riga base duplicata.

## Nomi file ed export

Il nome standard deriva dal numero effettivo: `7051_00_00_01_26.docx` e
`7051_00_00_01_26.pdf`. Anteprima PDF, download, registro, versione PDF e
`NomeFilePdf` per eSolver devono coincidere. I percorsi interni mantengono UUID.
Il nome PDF personalizzato scelto dall'utente rimane valido; nessuna rinomina di
PDF chiusi. Due quote dello stesso DDT possono avere lo stesso nome standard:
l'identità rimane documento/riga/lotto, non il nome del file.

## Audit sui documenti reali e impaginazione

Autorizzata copia locale dei tre Word/PDF OL1090 (ID71/137/177); Alpha invariata.
DDT2375: 29 + 91 = 120, stesso numero `7051_00_00/26` dentro tutti i documenti;
DDT2418: 118, ancora stesso numero storico. Sono Word caricati dall'utente.
Copie e simulazioni private sotto `tmp_eval/audit_1090_20261019`, non in Git.
Verificate 6 ulteriori simulazioni/18 pagine, inclusi `200 of 23000`,
`23000 of 123456`, `999999 of 23000000`, `1234567 of 23000000`.
Nessun cambio di pagine, posizione del corpo/firme o immagini; font non ridotto.
Le intestazioni ripetute riportano i nuovi valori su tutte e tre le pagine.

La terza pagina manuale del DDT2418 contiene «from no. 1 to no. 120» pur con
quantità 118: potrebbe essere la numerazione del lotto, NON un errore provato.
Non sostituire numeri liberi nelle pagine manuali con il totale della spedizione.

## Verifiche

Test dedicati: generazione reale Word, prima spedizione/anticipato, più quote,
DDT successivi, storico immutabile, totali decimali/zero/assenti, conflitti,
impronte del gruppo, download/nome PDF/export, concorrenza PostgreSQL, registro.
Esiti locali 19/10:

- Regressione completa Quarta su PostgreSQL isolato: 486 casi, nessuno saltato.
  I 456 casi preesistenti/registro sono passati. Nei 30 dedicati risultavano
  due problemi delle sole fixture (ID ORM letto dopo chiusura sessione e vista
  SQL export non installata nello schema temporaneo). Corretti senza cambiare
  il codice applicativo; ripetuti tutti i 30 casi: tutti passati, nessuno saltato.
  La vista test usa davvero l'SQL canonico e il numero/nome con quarto segmento.
- Ulteriore regressione mirata storico/registro/prima generazione/nome export:
  44 casi passati; 11 casi export/convertitore/nome PDF passati.
- 12 test frontend API/registro/filtri/generazione passati; build Vite riuscita.
  Rimangono gli avvisi preesistenti su Browserslist e dimensione bundle.
- Preparazione da schema senza colonna verificata: preview leggibile prima
  del DDL, helper idempotente, numero/stato PDF invariati e valore JSON NULL.
- Isolamento: PostgreSQL locale temporaneo senza porte/volumi persistenti,
  nessuna connessione eSolver o aziendale nei test. Alpha non modificata.

Commit/push e deploy richiedono successiva indicazione dell'utente.
