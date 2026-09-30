# Nomi Word/PDF e nome PDF personalizzato

Data: 30/09/2026. Implementazione e verifiche locali; nessun deploy Alpha.

## Comportamento approvato

1. Il download Word usa solo il numero certificato: `7017_00_30_26.docx`.
2. Il PDF propone `7017_00_30_26.pdf`. Nella finestra di conferma si può
   scrivere un nome per il cliente e ripristinare il nome standard.
3. Il numero dentro al documento e i riferimenti OL/DDT restano invariati.
4. Il nome PDF viene salvato solo dopo conversione riuscita e chiusura; è
   conservato anche nella versione PDF. Un PDF chiuso non viene rinominato
   ripetendo la richiesta di generazione con un nome diverso.
5. La riapertura ripropone il nome precedente; una nuova generazione può
   cambiarlo, mantenendo il nome vecchio sulla versione storica.
6. Nome vuoto, caratteri non validi e nomi riservati sono rifiutati. Se manca
   l'estensione, viene aggiunta `.pdf`; sono ammessi spazi e lettere accentate.

## File esistenti ed eSolver

I percorsi fisici con identificativi univoci restano separati dal nome di
download. File di quote/versioni diverse non vengono sovrascritti, anche se
il numero certificato o il nome scelto coincidono. Un download ripetuto sul
PC può essere rinominato dal browser, come normalmente avviene.

La vista `esolver_export.certi_certificati_pdf` e l'endpoint JSON aggiungono
`NomeFilePdf` in coda ai campi precedenti. Il download attraverso `PdfUrl`
restituisce quel nome. Non cambia l'URL né l'identificazione della quota.
L'uso effettivo del nome da parte dell'importatore eSolver richiede un test
con Walter dopo il deploy: il software esterno potrebbe applicare una
propria convenzione di nomi.

Migrazione idempotente all'avvio: aggiunta di `pdf_file_name` nullable a
`quarta_taglio_final_certificates` e `quarta_taglio_certificate_pdf_versions`.
I vecchi record usano il nome standard senza aggiornamenti massivi.

## Verifiche locali

- Test numerazione, nomi download Word/PDF e contratto export.
- Salvataggio reale su DB di prova, download via API del PDF esportato,
  riapertura, seconda versione, richiesta ripetuta e errore conversione.
- Migrazione ripetuta e aggiornamento di una vista con il vecchio contratto
  su PostgreSQL temporaneo: nomi coerenti e permessi SELECT conservati.
- Browser Chromium con pagina React reale e API simulate: nome iniziale,
  annullamento, campo vuoto, errore correggibile, ripristino, nome lungo,
  invio del nome scelto; larghezze 1440, 1920 e 600 px.
- Build frontend. Le prove non generano certificati nei dati reali locali.

Esito finale: suite Certificazione 232 test eseguiti, 220 superati e 12
PostgreSQL opzionali saltati perché non configurati; suite export eSolver
6 test superati. Verifica PostgreSQL specifica di questa modifica eseguita
separatamente con successo su database temporaneo, poi rimosso. Build e
controllo visivo superati.

Il frontend abituale su porta 5173 serve ancora la pagina precedente.
L'utente ha richiesto di rimandare il riavvio: non è stato riavviato. La prova
visiva è stata eseguita con Vite separato su porta 5174, chiuso al termine.

Gli altri due punti concordati (LST 03 e filtro Gemba per ora di caricamento)
restano separati e non sono implementati da questo intervento.
