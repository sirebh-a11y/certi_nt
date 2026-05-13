# Flusso finale certificati Word/PDF

Questo documento è il placeholder operativo per completare il flusso finale dei certificati generati dalla pagina Certificazione.

## Scopo

Portare un certificato numerato da Word aperto a PDF finale archiviato, mantenendo tracciabilità, scarico Word, scarico PDF e futura esposizione verso eSolver.

## Stato attuale

- Il numero certificato nasce quando l'utente genera il primo Word dalla pagina OL.
- Il Word generato può essere scaricato.
- L'utente può ricaricare un Word modificato.
- Il Word ricaricato sostituisce il Word scaricabile per quel certificato aperto.
- Il registro certificati mostra i certificati numerati.

## Flusso da implementare

1. L'utente scarica il Word numerato dalla pagina OL.
2. L'utente modifica il Word e aggiunge eventuali pagine aggiuntive.
3. L'utente ricarica il Word modificato sulla stessa pagina OL.
4. L'app normalizza il Word finale: header, footer e numerazione pagine.
5. L'app genera il PDF finale dal Word normalizzato.
6. L'app salva Word finale e PDF finale nel DB certificati.
7. L'app chiude il certificato con stato `pdf_final`.
8. Il registro mostra il PDF finale e mantiene anche il Word.
9. L'OL chiuso esce dalla lista operativa o viene marcato come non più da lavorare.
10. Il DB dei certificati chiusi diventa la base per esposizione/raccolta da eSolver.

## Decisioni aperte

- Data chiusura: automatica alla generazione PDF o scelta dall'utente.
- Conversione Word -> PDF: motore locale/LibreOffice, servizio esterno, o altra strategia.
- Validazione minima prima della chiusura: solo presenza Word, oppure controllo campi/standard.
- Gestione pagine aggiuntive: quali stili/header/footer applicare se il Word ricaricato contiene sezioni nuove.

## Regole da non rompere

- Il numero certificato non deve cambiare dopo il primo Word.
- Il Word ricaricato deve sostituire il Word precedente per quel certificato aperto.
- Un certificato chiuso non deve essere sovrascritto dal flusso Word aperto.
- Il registro deve distinguere chiaramente Word aperto e PDF chiuso.
