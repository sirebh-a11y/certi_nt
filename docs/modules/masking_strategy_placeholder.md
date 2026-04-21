# Masking Strategy Placeholder

## Stato
- Placeholder creato il 21/04/2026.
- Tema aperto: migliorare il masking documentale oltre Tesseract.

## Problema
- Tesseract funziona abbastanza bene per testo + box locali.
- Tesseract non e robusto sui loghi e sui blocchi grafici fornitore.
- Alcuni certificati, come Impol, restano parzialmente scoperti proprio sui loghi o sui blocchi misti testo/grafica.

## Strategia da valutare
1. Tenere la logica attuale per i campi testuali semplici:
- nome cliente
- indirizzo
- contatti
- footer legale

2. Separare il problema logo/blocco fornitore:
- non trattarlo come puro OCR
- valutare layout detection / object detection / image-template matching

3. Valutare un motore migliore di Tesseract per testo + posizioni:
- PaddleOCR / PP-Structure
- docTR
- Surya

## Regola da tenere ferma
- blocco sensibile locale
- stop sulle scritte utili
- mantenimento dei campi tecnici
- audit visivo immediato dopo ogni nuovo masking

## Quando riprendere
Quando si riapre questo tema, la prima domanda da fare e:

`E il momento di procedere con la strategia di masking oltre Tesseract?`

## Nota operativa
- In questa chat non posso inviare messaggi automatici ogni 3 giorni senza una nuova interazione utente.
- Pero questo placeholder resta nel repo come promemoria stabile.
