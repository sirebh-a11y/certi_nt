# Reparti: matrice accessi aggiornata (30/09/2026)

## Scopo

Aggiornare la pagina amministrativa Reparti, senza cambiare autorizzazioni,
ruoli, reparti o dati. La vecchia matrice era statica e descriveva solo 8
combinazioni scelte a mano, mentre l'app consente di assegnare ciascuno dei 3
ruoli (`user`, `manager`, `admin`) a ciascuno dei 7 reparti: 21 combinazioni.
Il reparto Incoming non compariva. Mancavano nuove funzioni come DDT da
certificare, Gemba, Calendario, requisiti cliente e codici fornitori.

## Comportamento rappresentato

La matrice mostra l'accesso **attraverso l'interfaccia normale**. Riutilizza
`canAccessPage` e i predicati di azione di `frontend/src/app/access.js`; non
crea una seconda politica di autorizzazione. Tre viste selezionabili per ruolo
mostrano sempre i 7 reparti nelle colonne. Le righe separano lettura da azioni
importanti: DDT esclusione/ripristino, conferme Incoming, riapertura, standard,
Word, PDF finale. `Opera` non aggira i normali prerequisiti del documento.

La pagina è larga sul desktop e la tabella scorre solo orizzontalmente su
schermi stretti. Prima colonna fissa per leggere la funzione mentre si scorre.

## Disallineamenti non corretti da questo intervento

Questa matrice **non certifica la sicurezza delle API**. Alcuni endpoint
richiedono solo un utente autenticato mentre la pagina restringe l'accesso
per reparto. Da decidere separatamente con l'utente prima di cambiare regole:

- Valutazione: Direzione può modificare dalla pagina (non solo consultare,
  come indicava la vecchia tabella); le API della sezione usano `CurrentUser`.
- Standards: Laboratorio può creare/aggiornare, non solo consultare; le API di
  scrittura usano `CurrentUser`.
- Calendario: creazione/eliminazione chiusure usa `CurrentUser` anche per
  reparti ai quali la pagina non è visibile.
- Molte operazioni di Incoming e Certificazione accettano `CurrentUser`; alcuni
  controlli specifici esistono invece per eliminazione, decisioni DDT,
  generazione PDF e riaperture. Nessuno è stato alterato qui.
- Registro: la pagina è visibile a tutti i reparti, anche Produzione e
  Incoming; la vecchia tabella non lo rifletteva.

Su richiesta dell'utente, l'avvertenza tecnica gialla non compare nella
pagina perché poco chiara; il problema resta qui documentato. L'eventuale
allineamento di backend e frontend è un intervento distinto, da approvare
dopo una scelta dei permessi voluti, non una conseguenza automatica di questa
matrice.

## Verifiche

- Test della matrice: 7 reparti × 3 ruoli e controlli puntuali delle funzioni
  con regole speciali; `node --test src/pages/departments/permissionMatrix.test.js`.
- Build frontend.
- Browser Chromium con utente e API simulati; nessuna scrittura ai dati reali.
  Larghezze verificate: 1920, 1366, 981 e 600 px. Tutte le colonne sono
  visibili senza scorrimento orizzontale da 981 px in su; a 600 px lo
  scorrimento rimane all'interno della tabella. Nessun errore JavaScript.
- Frontend locale abituale riavviato e verificato sulla porta 5173; l'avviso
  giallo rimosso non compare piu. Alpha non toccato.
