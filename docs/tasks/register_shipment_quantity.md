# Registro certificazione: quantità della spedizione

## Richiesta e perimetro

Punto 8 delle richieste cliente, audit e implementazione locale del 18/09/2026.
La colonna Quantità deve mostrare i pezzi spediti da eSolver, non il materiale
prelevato da Quarta. L'utente ha confermato che `QtaUmMag` nelle righe DDT eSolver
è il numero di pezzi. La vista `dbo.CertiRigheDDT` non espone un campo separato
per l'unità di misura; non vengono aggiunte conversioni o arrotondamenti.

## Causa verificata su Alpha (sola lettura)

- `certificate.quantita` può contenere una quantità eSolver oppure una quantità
  Quarta, secondo i dati disponibili al momento della creazione del certificato.
- Il Registro utilizzava questo campo, con ulteriore fallback alle quantità
  dei materiali in `cdq_values`: la fonte non era distinta.
- Il certificato `7039_00_00/26`, OL `OL2026001070`, aveva il valore 2 sia nella
  quantità salvata sia nello snapshot dei materiali, senza DDT eSolver collegato.
- Tutte le sei righe dello screenshot cliente risultavano senza righe DDT nella
  cache eSolver. Non è stato lanciato un aggiornamento operativo su Alpha.

## Correzione locale

- Cambia solamente la quantità restituita al Registro, non quella persistita
  nel certificato o usata per Word/PDF.
- Legge in batch la cache eSolver già presente, senza nuove chiamate esterne.
- Richiede OL, articolo e DDT coincidenti; rispetta inoltre gli identificativi
  documento/riga/lotto e i riferimenti ordine già associati al certificato.
- Un certificato storico senza identificativi può usare una sola riga DDT
  univoca. In caso di più righe o lotti possibili restituisce quantità assente.
- Non somma spedizioni parziali o righe diverse dello stesso OL.
- Duplicati identici contano una volta; valori discordanti o incompleti non
  diventano un totale parziale.
- Se il DDT o il dato attendibile manca, mostra `—`; lo zero reale resta `0`.
- Il normale aggiornamento del Registro continua a funzionare come prima e
  usa la stessa regola nella risposta aggiornata. Non si aggiunge polling.
- Titolo colonna invariato: Quantità. Nessuna colonna aggiuntiva.

## Protezioni e limiti

- Nessuna migrazione, modifica dello storico, di KPI, pesi, esiti, stati,
  numero certificato o identità delle spedizioni.
- La sola lettura del Registro non rigenera Word/PDF e non riapre certificati.
- Anche per i PDF chiusi la quantità visualizzata deriva dalla riga DDT
  collegata nella cache; il file e lo snapshot del certificato restano immutati.
- Se la cache eSolver è vuota o perde il riferimento univoco, il Registro
  mostra `—` invece di ripiegare sulla vecchia quantità di origine incerta.
- Nessuna installazione su Alpha con questo lavoro: commit/push e deploy
  restano operazioni separate su richiesta dell'utente.

## Verifiche completate in locale

- Assenza DDT con vecchie quantità 2, 208, 608 e 1126: nessun valore Quarta esposto.
- Collegamento della corretta riga DDT, spedizioni parziali e altri lotti/articoli/OL.
- Identità discordanti, record storici senza ID, duplicati identici o discordanti.
- Quantità nulla, zero, negativa, non finita e decimale senza arrotondamenti.
- Registro e risposta aggiornamento coerenti; PDF chiuso non rigenerato.
- Lettura batch con una sola query cache, nessuna scrittura né sync esterna.
- Regressione backend completa, build frontend e prova browser con API simulate.

Esito: 268 test backend superati (10 nuovi test mirati), build frontend riuscita.
Browser verificato su quantità assente, zero, formattazione italiana, ordinamento,
arrivo del DDT tramite aggiornamento esistente e riga PDF chiusa invariata.
Nessun errore JavaScript; schermata controllata visivamente.

Prova aggiuntiva della sola funzione locale su una copia delle 83 righe Registro
lette da Alpha: 78 righe senza DDT non espongono più quantità di materiale;
le 5 con DDT conservano i valori 1490, 380, 296, 653 e 798. Nessuna scrittura
su Alpha o sui database locali. La copia temporanea è stata rimossa dopo il test.
