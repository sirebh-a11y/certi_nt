# Normalizzazione visiva lega - soluzione A

## Stato decisione

Soluzione scelta per ora: **solo visuale**.

Non si normalizza il dato salvato. Non si cambia il dato usato per match, AI, fallback, Word, PDF o export.

## Scopo

Mostrare nelle pagine operative una lega piu pulita e leggibile per l'utente, senza modificare il dato originale salvato nel database.

Il problema nasce da valori letti o inseriti in forme diverse, per esempio:

- `6082 F`
- `6082F F`
- `6082 T6`
- `2024 Sigma T4`
- `5083 H111`

Nelle liste operative l'utente deve vedere la lega utile, non il trattamento termico o stato fisico.

Esempi:

- `6082 F` -> `6082`
- `6082F F` -> `6082`
- `6082 T6` -> `6082`
- `6082 T62` -> `6082`
- `6005A F` -> `6005A`
- `2024 Sigma T4` -> `2024 Sigma`
- `5083 H111` -> `5083`
- `5754 H22` -> `5754`

Devono invece rimanere invarianti le varianti reali:

- `6082L`
- `6082H`
- `6005A`
- `2024 Sigma`
- `7075`
- `7175`

## Regola base

Il valore originale resta quello acquisito da AI, DDT, certificato o fallback manuale.

La UI mostra una versione pulita solo dove la riga e gia una riga letta, riepilogata o stampata.

Non si cambia:

- database
- match
- rematch
- disaccoppio
- fallback manuale
- overlay
- cattura campi
- payload di salvataggio
- dati usati per Word/PDF

## Regole precise lega/trattamento

### Cosa tenere

Tenere sempre:

- la lega base
- eventuali varianti reali della lega
- eventuali descrizioni/varianti testuali non riconosciute come trattamento

Serie alluminio da riconoscere come leghe valide:

| Serie | Esempi | Regola |
| --- | --- | --- |
| `1xxx` | `1050`, `1070` | tenere |
| `2xxx` | `2014`, `2024`, `2618` | tenere |
| `3xxx` | `3003`, `3103` | tenere |
| `4xxx` | `4032` | tenere |
| `5xxx` | `5083`, `5754` | tenere |
| `6xxx` | `6005A`, `6061`, `6082` | tenere |
| `7xxx` | `7075`, `7175`, `7050`, `7150` | tenere |
| `8xxx` | `8006`, `8011` | tenere |

Varianti da conservare:

| Valore | Output visuale | Motivo |
| --- | --- | --- |
| `6005A` | `6005A` | `A` e parte della lega |
| `6082L` | `6082L` | `L` e variante lega, non trattamento |
| `6082H` | `6082H` | `H` attaccata alla lega resta variante se non e un trattamento `Hxx` separato |
| `2024 Sigma` | `2024 Sigma` | `Sigma` identifica variante/specifica |

### Cosa togliere

Togliere solo stati fisici/trattamenti riconosciuti, quando sono separati dalla lega oppure attaccati in modo chiaro al valore letto.

| Tipo | Esempi da togliere | Note |
| --- | --- | --- |
| Stato grezzo | `F` | anche caso sporco `6082F F` -> `6082` |
| Ricotto | `O` | solo token separato o riconosciuto |
| Solubilizzato | `W` | solo token separato o riconosciuto |
| T | `T1`, `T2`, `T3`, `T4`, `T42`, `T5`, `T6`, `T62`, `T66`, `T7`, `T73`, `T76`, `T651`, `T6511` | togliere dalla visualizzazione |
| H | `H12`, `H14`, `H16`, `H18`, `H22`, `H24`, `H26`, `H32`, `H34`, `H111`, `H112`, `H116`, `H321` | togliere dalla visualizzazione |

### Casi da non toccare

Non togliere lettere generiche finali se non sono chiaramente trattamento.

| Input | Output visuale corretto | Perche |
| --- | --- | --- |
| `6082L` | `6082L` | `L` resta variante |
| `6082H` | `6082H` | non e `Hxx` |
| `6005A` | `6005A` | `A` e parte della lega |
| `2024 Sigma` | `2024 Sigma` | variante testuale |
| `7150 F` | `7150` | `F` separato e trattamento |
| `7150 T76` | `7150` | `T76` e trattamento |

### Matrice esempi

| Valore originale | Visuale lista | DB/match resta |
| --- | --- | --- |
| `6082 F` | `6082` | `6082 F` |
| `6082F F` | `6082` | `6082F F` |
| `6082 T6` | `6082` | `6082 T6` |
| `6082 T62` | `6082` | `6082 T62` |
| `6005A F` | `6005A` | `6005A F` |
| `2024 Sigma T4` | `2024 Sigma` | `2024 Sigma T4` |
| `5083 H111` | `5083` | `5083 H111` |
| `5754 H22` | `5754` | `5754 H22` |
| `7075 T76` | `7075` | `7075 T76` |
| `6082L` | `6082L` | `6082L` |
| `6082H` | `6082H` | `6082H` |

## Dove applicare

### Incoming materiale

File individuato:

- `frontend/src/pages/acquisition/AcquisitionListPage.jsx`

Uso previsto:

- cella colonna `Lega`
- ordinamento colonna `Lega`
- ricerca testuale, includendo sia valore originale sia valore pulito

Esempio:

DB: `6082F F`

UI lista: `6082`

Filtro:

- cercando `6082` la riga si trova
- cercando `6082F` la riga si trova comunque

### Valutazione fornitori

File individuato:

- `frontend/src/pages/quality/QualityEvaluationPage.jsx`

Uso previsto:

- cella colonna `Lega`
- ordinamento colonna `Lega`
- ricerca testuale, includendo sia valore originale sia valore pulito

### Registro certificazione

File da verificare:

- `frontend/src/pages/quartaTaglio/QuartaTaglioCertificatesRegisterPage.jsx`

Uso previsto:

- solo se espone la lega in colonne o riepiloghi read-only
- non cambiare dati scaricati, Word, PDF o export

### Certificazione OL

File da verificare:

- `frontend/src/pages/quartaTaglio/QuartaTaglioDetailPage.jsx`

Uso previsto:

- riepiloghi leggibili all'utente, se presenti

Uso vietato:

- selezione standard
- materiali del certificato
- header Word
- generazione Word/PDF

### Gemba Walk

File individuato:

- `frontend/src/pages/acquisition/AcquisitionGembaWalkPrintPage.jsx`

Uso previsto:

- stampa con lega pulita, per rendere il foglio piu leggibile

Importante:

- il foglio Gemba Walk resta un documento operativo/visivo
- non deve cambiare la riga Incoming originale

### Riepilogo riga

File individuato:

- `frontend/src/pages/acquisition/AcquisitionRowSummaryCard.jsx`

Uso previsto:

- schede riepilogo/read-only dove l'utente deve leggere la lega, non modificarla

### Dettaglio riga Incoming

File da valutare con attenzione:

- `frontend/src/pages/acquisition/AcquisitionDetailPage.jsx`

Uso consentito:

- solo intestazioni o riepiloghi read-only

Uso vietato:

- valori inviati in salvataggio
- campi modificabili

## Dove non applicare

### Match DDT/certificato

File individuato:

- `frontend/src/pages/acquisition/AcquisitionDocumentMatchingSectionPage.jsx`

Motivo:

Qui l'utente controlla e corregge il valore reale letto da DDT/certificato. Deve vedere il dato vero, anche se sporco.

Esempio:

Se il DDT ha `6082F F`, nel match deve restare `6082F F`, perche l'utente deve capire cosa e stato letto e correggere se serve.

### Fallback manuale

File individuato:

- `frontend/src/pages/acquisition/AcquisitionManualDdtPage.jsx`
- `frontend/src/pages/acquisition/AcquisitionManualCertificatePage.jsx`

Motivo:

Qui l'utente crea o corregge una riga. Il valore deve restare quello effettivo che verra salvato.

### Chimica e proprieta

Non applicare nei campi operativi di:

- pagina Chimica
- pagina Proprieta
- overlay
- cattura singolo valore
- cattura tabella

Motivo:

Sono pagine tecniche dove l'utente deve vedere il valore reale della riga.

### Backend

Non applicare in:

- servizi di match
- normalizzazione usata dal matching
- export
- endpoint
- modelli DB
- generazione certificato

## Funzione proposta

Creare una funzione frontend unica, per evitare logiche duplicate.

Nome possibile:

- `normalizeAlloyForDisplay(value)`

File possibile:

- `frontend/src/utils/alloyDisplay.js`

Regola:

1. pulire spazi doppi
2. individuare una lega base valida nelle serie `1xxx` - `8xxx`
3. conservare eventuale variante reale (`A`, `L`, `H`, `Sigma`, ecc.)
4. togliere solo trattamenti/stati fisici finali riconosciuti
5. se non si riconosce con sicurezza, mostrare il valore originale

## Ricerca e ordinamento

La ricerca deve usare sia dato originale sia dato pulito.

Esempio:

Valore DB: `6082F F`

Valore visuale: `6082`

Testo indicizzato:

`6082F F 6082`

Questo evita che l'utente perda righe cercando il valore sporco o quello pulito.

L'ordinamento puo usare il valore pulito, perche e piu coerente lato utente.

Se due righe hanno lo stesso valore pulito, l'ordinamento secondario puo usare il valore originale per stabilita.

## Rischi

### Rimuovere una variante vera

Rischio:

Una lettera finale potrebbe essere parte della lega e non trattamento.

Contromisura:

Usare solo una lista chiusa di trattamenti da togliere. Non togliere lettere generiche.

### Nascondere un dato utile in pagina tecnica

Rischio:

L'utente non vede piu il valore originale mentre deve correggere un match.

Contromisura:

Applicare solo a liste e riepiloghi read-only. Non applicare a match, fallback, overlay e campi modificabili.

### Differenza tra lista e dettaglio

Rischio:

L'utente vede `6082` in lista ma, entrando nel match, vede `6082F F`.

Motivo corretto:

Nel match si vede il dato originale per poterlo correggere.

Eventuale nota futura:

Se serve, si puo aggiungere un tooltip discreto nei casi in cui il valore visuale e diverso dal valore originale.

### Filtri incoerenti

Rischio:

L'utente cerca `6082F` e non trova piu una riga che vede come `6082`.

Contromisura:

Nei filtri testuali includere sia valore originale sia valore visuale.

### Pagina dimenticata

Rischio:

Una pagina continua a mostrare il valore sporco.

Contromisura:

Dopo l'implementazione usare ricerca trasversale su:

- `alloy`
- `composeLega`
- `lega_designazione`
- `lega_base`
- `variante_lega`
- `Lega`

## Test richiesti

### Test helper

Verificare:

- `6082 F` -> `6082`
- `6082F F` -> `6082`
- `6082 T6` -> `6082`
- `6082 T62` -> `6082`
- `6005A F` -> `6005A`
- `2024 Sigma T4` -> `2024 Sigma`
- `5083 H111` -> `5083`
- `5754 H22` -> `5754`
- `7075 T76` -> `7075`
- `7150 T6511` -> `7150`
- `6082L` -> `6082L`
- `6082H` -> `6082H`
- `6005A` -> `6005A`
- valori non riconosciuti restano invariati

### Test UI

Verificare:

- Incoming materiale mostra lega pulita
- Valutazione mostra lega pulita
- Gemba Walk stampa lega pulita
- riepilogo riga mostra lega pulita
- eventuale Registro certificazione, se espone la lega
- match/fallback continuano a mostrare il dato originale

### Test ricerca

Con valore originale `6082F F`:

- ricerca `6082` trova la riga
- ricerca `6082F` trova la riga

### Test non regressione

Verificare che non cambino:

- match automatico
- conferma match
- rematch
- disaccoppio
- riapertura match
- fallback manuale
- salvataggio riga
- Word/PDF
- export verso eSolver
- creazione PDF
- selezione standard

## Piano implementazione

1. Creare helper frontend unico.
2. Scrivere test/casi rapidi sull'helper.
3. Applicarlo solo alle pagine read-only individuate.
4. Adeguare ricerca e ordinamento dove necessario.
5. Non toccare backend e DB.
6. Eseguire build frontend.
7. Eseguire audit con `rg` per trovare altri punti `Lega`.
8. Verificare manualmente almeno Incoming, Valutazione, Registro e Gemba Walk.

## Decisione aperta

Decidere se mostrare anche il valore originale in tooltip quando il valore visuale e diverso.

Proposta iniziale:

Non mostrarlo, per non appesantire la UI. Il dato originale resta visibile nelle pagine di match e fallback.

## Sintesi per utente

L'utente vede la lega pulita nelle liste:

- `6082 F` diventa `6082`
- `2024 Sigma T4` diventa `2024 Sigma`
- `5083 H111` diventa `5083`

Quando invece deve correggere o confermare un documento, vede il valore vero letto dal documento.

Quindi:

- meno rumore nelle liste
- nessun rischio sul match
- nessun cambio al database
- nessun cambio a certificati Word/PDF
