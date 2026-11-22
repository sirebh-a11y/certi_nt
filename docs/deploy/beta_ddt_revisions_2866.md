# Beta — DDT modificati e caso 2866 (da autorizzare)

Beta è in uso operativo. Nessun intervento è stato eseguito con questa procedura.
Restano validi spazio, backup database **e storage**, verifica di ripristino isolato, utenti/attività in corso e manutenzione del [runbook principale](alpha_soft_update_server.md).

## Prima dell’attivazione

1. Concordare un indirizzo interno presidiato di Qualità e verificare la configurazione SMTP con IT. Nessun invio automatico al cliente. Concordare con Amministrazione di **non spedire il vecchio PDF del 2866**; la vista di eSolver non attesta l'avvenuta consegna del PDF.
2. Distribuire codice e frontend insieme. Il bootstrap aggiunge le tabelle `quarta_taglio_ddt_shipment_changes` e `quarta_taglio_ddt_word_repairs`; verificarle prima di attivare il worker. Nessuna rinumerazione globale, né importazione del DB di sviluppo. Verificare che non ci siano due scheduler concorrenti di versioni diverse.
3. `DDT_REVISIONS_ENABLED` è spento per impostazione predefinita. In esercizio servono il lettore snapshot e il normale riuso Word già attivi; configurare anche `DDT_QUALITY_EMAIL`. L'avviso in CERTI è persistente anche se la mail non parte. In caso di consegna SMTP incerta indica «consegna da verificare»: verificare con IT, non reinviare alla cieca.
4. Non trattare la sola uscita di un intero documento dalla finestra eSolver come annullamento. Il confronto usa letture complete, identità e dati di spedizione; né gli orari di lettura né la somma dei pezzi dimostrano la discendenza di due righe. Un eventuale DDT completamente cancellato, senza altre evidenze, resta da chiarire con Amministrazione.

## Eccezione già avvenuta: DDT 2866 del 20/11/2026

Documento eSolver 5296723, OL2026001058, lavorazione 520002360. Le nuove righe erano già salvate prima della modifica software: non aspettare che il timer ripeta la transizione. Non usare **Riapri**, cancellazioni SQL o rigenerazioni da zero.

| Riga eSolver | ID CERTI | Prima del recupero atteso | Dopo |
| --- | ---: | --- | --- |
| 1 | 495 | PDF v1, 4.320 pezzi | PDF conservato per tracciabilità; fuori dall’esportazione e vecchio URL revocato |
| 4 | 496 | Word aperto, ordine 4500247815-22/07/2026 | stesso ID, quantità `3966 of 4320` |
| 6 | 497 | Word aperto, ordine 4500247816-22/07/2026 | stesso ID, quantità `354 of 4320` |

I due Word devono riportare **7028_00_60_01/26**; il documento del DDT 2575, ID 268, **7028_00_60/26**, non deve cambiare. Confrontare prima/dopo file, versioni, ordini, parti tecniche, seconde pagine, numero nel Word e nome file proposto. Non cambiare i nomi PDF personalizzati delle altre spedizioni.

**Preverifica Beta, 22/11/2026 ore 18:09 (Italia), in sola lettura.** Vista eSolver e righe correnti conservate in CERTI coincidono: 4 e 6, conferme rispettivamente 634-23/07/2026 e 635-23/07/2026. La riga 1 non compare più in eSolver; il suo PDF 495 v1 è ancora pubblicato nella vista di prelievo. I Word 496 e 497 sono aperti: contengono ancora il numero del DDT 2575 e solo la quantità di riga. Nessun nuovo PDF, esclusione o archiviazione; nessun allegato o seconda pagina separata su questi numeri. Entrambe le bozze risultano conformi e senza variazioni di materiale o standard. Le due nuove tabelle non sono ancora installate: questa verifica **non** è l'anteprima di applicazione.

Impronte di confronto (primi 16 caratteri SHA-256 dei file letti, non sono il parametro di approvazione): Word 495 `2d5ec42879e8dbe3`, PDF 495 `dfae9e623d9015df`; Word 496 `336049f4bd3ec9fa`, Word 497 `fb0fe0ada2d31f1f`; PDF 268 `bda8262ce8676b2c`. Se al deploy lo stato o un'impronta differiscono, fermarsi e verificare con Qualità prima di autorizzare una nuova anteprima. Nessuna evidenza sull'invio effettivo del PDF al cliente.

1. Provare prima sul ripristino isolato DB **e file** della stessa release con la fotografia eSolver verificata (mai aprire un collegamento eSolver o SMTP dal ripristino). In Beta, fermare gli accessi e i worker con la procedura principale; verificare assenza di utenti/operazioni. Montare i due backup con percorsi assoluti in sola lettura per la procedura.
2. In un container backend una tantum della nuova versione, con `DDT_SNAPSHOT_ENABLED=false` e `DDT_WORD_REUSE_ENABLED=false`, eseguire da `/app` **solo l'anteprima**: `python -m scripts.recover_ddt_2866 --preview`. Interroga la vista eSolver in lettura e il DB CERTI in transazione di sola lettura; non eseguire il bootstrap dal comando di recupero. Esaminare gli ID, il numero, il totale e l'impronta restituita. Se l'anteprima si ferma (es. nuova modifica, DDT non visibile, PDF già emesso), **non forzare**: rifare audit con Qualità.
3. Solo con autorizzazione specifica, stessi backup già ripristinati per prova e manutenzione attiva: `python -m scripts.recover_ddt_2866 --apply-digest IMPRONTA --maintenance-confirmed --backup /percorso/backup-db --storage-backup /percorso/backup-storage`. Ripete confronto e impronta; ritiro e due Word sono una sola transazione. File originali conservati, nessun nuovo PDF. Se l’esito del commit è incerto, controllare DB, eventi e riferimenti prima di qualsiasi nuovo tentativo.
4. Verificare: 495 non compare **né in SQL né in API eSolver**; vecchio URL non scaricabile, file storico invariato; due Word apribili, ordini distinti, nessun blocco spurio sulla revisione tecnica; 268 invariato; nessun altro ID ritirato. Aprire in consultazione le due bozze. Riattivare servizio con i flag concordati e controllare una lettura riuscita, la coda di correzione, il segnale in **DDT da certificare** e l'unica notifica interna. La prova del canale esterno di consegna compete a IT/eSolver: non si può revocare una copia che Amministrazione ha già scaricato.
5. Qualità verifica con Amministrazione l’invio del vecchio PDF: registra **PDF non inviato** oppure **PDF già inviato** e poi **Cliente avvisato**. Emette i due nuovi PDF. Il caso resta visibile fino alla gestione della comunicazione e delle righe correnti. Nessun invio automatico al cliente.

## Ripiego

Se si blocca l'anteprima o il confronto dei Word, non pubblicare documenti né allargare la selezione; preservare gli originali e coinvolgere il referente IT. Se manca la conferma del destinatario interno, non dare la mail per consegnata. Per tornare alla release precedente fermare prima i worker e verificare con IT i ritiri già registrati. **Non ripristinare automaticamente i link a PDF errati** e non ripristinare un backup sopra attività intervenute nel frattempo. Le tabelle additive possono restare; tenere gli avvisi pendenti sotto gestione Qualità anche se si sospende l’automatismo.
