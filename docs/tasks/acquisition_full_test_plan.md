# Piano test completo acquisizione, match e overlay

Scopo: verificare il flusso reale dell'app con documenti PDF veri, usando Vision AI e non OCR grezzo, prima della pulizia completa della lista acquisizione.

Il piano va eseguito in tre fasi:

1. Audit sul DB attuale, per sfruttare i casi gia presenti e non perdere contaminazioni utili da diagnosticare.
2. Backup e pulizia controllata di DB, lista acquisizione, pendenti e persistiti.
3. Test pulito su lista acquisizione ripulita, con run controllati per fornitore e run misti.

## Regole guida

- Non usare OCR come fonte di verita per decidere se un dato e corretto: per audit visivo usare Vision o dati AI gia persistiti.
- Non correggere a mano il DB durante il test, salvo backup/annotazione esplicita.
- Ogni test deve controllare sia i dati alti della riga acquisizione sia i dati bassi AI/persistiti usati da chimica, proprieta, note, overlay e rematch.
- Il match automatico del secondo run deve comportarsi come il primo import: se i campi ponte coincidono, accoppia senza chiedere conferma all'utente.
- I campi ponte sono quelli logici da Excel utente: fornitore, lega, diametro, CDQ, colata, DDT, peso, ordine quando disponibile e utile.
- DDT multiriga e certificati gia accoppiati non vanno esclusi dal rematch: una riga DDT puo avere piu certificati, e in casi rari un certificato puo riguardare piu DDT.

## Stima costo

Prima di partire con AI:

- Contare numero PDF e pagine effettive.
- Evitare doppie chiamate sugli stessi documenti gia analizzati se i raw AI sono presenti e affidabili.
- Fare prima run piccolo di conferma su un sottoinsieme.
- Solo dopo eseguire run misto completo.

Stima prudente per il primo giro pulito: circa 12-16 PDF. Il costo va confermato al momento contando pagine e modello Vision effettivamente configurato.

## Audit prima della pulizia

Usare il DB attuale per controllare:

- Righe gia accoppiate: devono restare forti e non degradare.
- Righe DDT-only: non devono agganciarsi a certificati sbagliati.
- Righe certificate-first: devono avere campi ponte nello stesso formato del DDT.
- Chimica: valori collegati all'elemento corretto, non alla sola posizione.
- Proprieta: IACS solo se realmente presente o calcolato, non inventato dal certificato.
- Note: overlay deve evidenziare solo righe note reali, non blocchi troppo grandi o righe non pertinenti.
- AWW: evitare contaminazioni tipo lega `T1` al posto di `6082A T1`.
- Neuman: verificare overlay chimica con Mg/elementi mancanti da OCR.

## Pulizia prima del test pulito

Prima di lanciare nuovi run AI bisogna ripulire in modo controllato, non a mano e non a meta.

Sequenza obbligatoria:

1. Fare backup del DB e annotare commit corrente.
2. Salvare eventuali raw/debug utili dei casi sporchi prima di cancellarli.
3. Pulire lista acquisizione, righe pendenti, accoppiamenti temporanei, stati di conferma e dati persistiti collegati ai test precedenti.
4. Verificare che non restino righe contaminate, ad esempio AWW con `lega_base=T1`.
5. Verificare che non restino overlay blu/verdi o conferme persistite su documenti che saranno ricaricati.
6. Riavviare servizi se necessario e aprire la lista acquisizione vuota o nello stato atteso.
7. Solo dopo partire con Run 1.

Non procedere al test pulito se la pulizia non e verificabile: un dato vecchio rimasto nel DB renderebbe inutile il risultato del run AI.

## Run 1: import misto controllato

Obiettivo: simulare un carico reale con fornitori diversi, alcuni match immediati e alcuni casi complessi.

| Fornitore | DDT | Certificato | Scopo |
| --- | --- | --- | --- |
| Neuman | `esempi_locali/4-ddt/Neuman/75724077.pdf` | `esempi_locali/3-certificati/Vari/Neuman Aluminium Austria/CQF_26088_6082190_2026.pdf` | Match noto, chimica/proprieta/note, overlay Mg e tabella Neuman. |
| AWW | `esempi_locali/4-ddt/AWW/14142236.pdf` | `esempi_locali/3-certificati/AWW/CQF_Z25-02034_6082L35_2025.pdf` | DDT multiposizione, protezione lega AWW, match parziale e righe residue. |
| Impol | `esempi_locali/4-ddt/Impol/1505-11.pdf` | `esempi_locali/3-certificati/Impol/CQF_1505_a_608232_2026.pdf` | Match, note, classe US A/B, overlay note. |
| Leichtmetall | `esempi_locali/4-ddt/Leichtmetall/80008535.pdf` | `esempi_locali/3-certificati/Leichtmetall A/Certificati Origine/CdQ_94668_6082_Ø228.pdf` | DDT con piu righe e primo certificato collegabile. |
| Leichtmetall | `esempi_locali/4-ddt/Leichtmetall/80008535.pdf` | `esempi_locali/3-certificati/Leichtmetall A/Certificati Origine/CdQ_94752_6082_Ø228.pdf` | Stesso DDT con secondo certificato collegabile. |
| Metalba | `esempi_locali/4-ddt/Metalba/26-00957.pdf` | `esempi_locali/3-certificati/Metalba Aluminium/CQF_26-0746_608248_2026.pdf` | Verifica match/candidate, materiale, ordine, overlay proprieta. |
| Aluminium Bozen | da definire con DDT piu coerente | `esempi_locali/3-certificati/Aluminium Bz - Sapa Bz/CQF_100036_201452_2023.pdf` | Certificate-first o no-match controllato, chimica con Sn finale. |

Nota: per Metalba e Aluminium Bozen bisogna accettare il test come diagnostico se il DDT scelto non e la coppia reale perfetta; non va usato per giudicare falso negativo senza verifica sui campi Excel.

## Run 2: rematch su documenti arrivati dopo

Obiettivo: simulare il lavoro reale dell'utente su piu run.

Casi da coprire:

- DDT caricato nel run 1, certificato caricato nel run 2.
- Certificato caricato nel run 1, DDT caricato nel run 2.
- DDT multiriga dove arriva un secondo certificato dopo il primo.
- Certificato gia accoppiato che puo essere rilevante per un altro DDT, senza rompere il match esistente.
- Documento non matchabile che deve restare libero.

Documenti candidati:

- Impol: `10341-11.pdf` con `CQF_10341_6082H90_2025.pdf`.
- Impol: `17126-11.pdf` con certificati `CQF_17126_*`.
- AWW: righe residue di `14142236.pdf` con certificati Z24/Z25 coerenti.
- Neuman: DDT e certificati 25531/25537/26088 per verificare certificate-first e DDT-later.
- Leichtmetall: DDT `80008535.pdf` e certificati multipli 94668/94752 per uno-a-molti.

## Verifiche per ogni riga

Per ogni riga generata:

- Stato semaforico coerente: colori campo documento, match, conferma finale.
- Campi acquisizione coerenti con Excel utente.
- Provenienza dato chiara: AI, utente, calcolato, confermato.
- Overlay DDT sul campo giusto, non su packing list o indirizzo.
- Overlay certificato sul valore giusto, non solo su riga generica se il valore esiste.
- Chimica con elementi corretti anche se nel PDF compaiono altri elementi.
- Proprieta con valori reali e IACS non inventato.
- Note con box su righe note corrette e non troppo largo.
- Dopo uscita/rientro pagina, overlay blu persistente dove confermato.

## Placeholder futuro: overlay pagina match DDT/certificato

La parte overlay della finestra match DDT/certificato resta da riprendere con audit dedicato.

Motivo: la logica documentale e' piu complessa di chimica/proprieta/note, perche deve guidare l'utente su due documenti separati, con DDT multiriga, certificati gia accoppiati, casi uno-a-molti e casi molti-a-molti.

Regola per il prossimo intervento:

- non fare patch puntuali su un solo fornitore;
- prima separare chiaramente overlay DDT e overlay certificato;
- sul DDT cercare sempre il blocco della riga materiale corretta, non il primo valore simile nel documento;
- sul certificato cercare valori e campi del certificato come documento autonomo, coerente con certificate-first;
- evitare box fuorvianti: se il box puo indicare una riga o un campo sbagliato, meglio non mostrarlo o mostrarlo come dubbio;
- documentare per ogni fornitore quali campi sono affidabili per centrare il box e quali sono solo fallback.

Questo placeholder non blocca il resto del flusso, ma impedisce di considerare conclusa la pagina match finche l'overlay non sara robusto lato operatore.

## Criteri di stop

Fermare il test e non proseguire con altri documenti se succede uno di questi casi:

- Un valore chimico viene associato all'elemento sbagliato.
- Un campo ponte viene normalizzato in modo diverso tra DDT e certificato.
- Un rematch accoppia documenti palesemente diversi.
- Una modifica utente rompe la possibilita di match sui campi Excel.
- Overlay mostra un box fuorviante che puo guidare l'operatore su un valore sbagliato.

## Output atteso

Alla fine del ciclo test dobbiamo avere:

- Elenco righe OK per fornitore.
- Elenco errori per fornitore, separati in AI, parser, match, rematch, overlay, UI.
- Decisione su quali bug correggere prima di fare il test AI completo.
- Decisione su quando ripulire lista acquisizione e pendenti.
