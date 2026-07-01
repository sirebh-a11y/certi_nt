# Nuova nota Class A estesa - piano prompt AI e implementazione

## Obiettivo

Gestire una nuova nota hardcoded:

`U.S. control acc. to SAE AMS-STD-2154-E Class A Type 1, single indication size >2mm and control of backwall echo drop > 50% BSH`

Questa nota e' una estensione della nota esistente `US control Class A`.

Regola funzionale:

- se il certificato fornitore contiene la nuova frase, o una variante equivalente, l'app deve salvare la nuova nota estesa;
- la nuova nota estesa e' una specializzazione della vecchia `US control Class A`;
- internamente puo' valere come copertura Class A per evitare falsi mancanti, ma nel certificato finale non deve mai essere stampata insieme alla vecchia Class A;
- la frase finale da stampare va scelta con regola specifica descritta sotto;
- se non e' presente, non deve diventare un errore bloccante e non deve rendere gialle righe che prima erano corrette.

## Prompt AI

La ricerca deve essere aggiunta a tutti i prompt fornitori e al prompt generico note/vision.

Non si devono fare nove logiche diverse per fornitore: il blocco di istruzioni deve essere comune e poi inserito nei prompt esistenti.

### Blocco logico da aggiungere

L'AI deve cercare nelle note/requisiti del certificato una frase o variante equivalente che contenga il concetto:

- `US control`
- `SAE AMS-STD-2154` o variante simile
- `Class A`
- `Type 1`
- `single indication`
- limite `2 mm`
- `backwall echo drop`
- limite `50% BSH`

Varianti accettabili:

- `SAE AMS STD 2154 E`
- `AMS-STD-2154-E`
- `AMS STD 2154E`
- `single indication size > 2mm`
- `single indication greater than 2 mm`
- `back wall echo drop >50% BSH`
- piccoli errori OCR su spazi, punti e trattini.

Regole da dare all'AI:

- non inventare la nota se non e' presente;
- se trova la nuova nota estesa, deve restituire il testo reale trovato nel certificato;
- se trova la nuova nota estesa, deve indicarla nel campo nuovo; il codice la trattera' come specializzazione della Class A;
- se trova solo una Class A normale, non deve segnare la nuova nota estesa;
- `LST 00` resta legato alla Class B, non alla nuova Class A.

### Output atteso AI

Aggiungere un campo nuovo alle note, mantenendo quelli esistenti:

```json
{
  "nota_us_control_class_a": "...",
  "nota_us_control_class_b": "...",
  "nota_us_control_class_a_type1_bsh": "...",
  "nota_rohs": "...",
  "nota_radioactive_free": "..."
}
```

Per `nota_us_control_class_a_type1_bsh`:

- valore pieno = frase trovata nel certificato;
- vuoto/null = frase non trovata;
- mai sintesi inventata.

## Codice da adeguare

### Note hardcoded

Aggiungere una nuova nota di sistema:

- codice indicativo: `us_control_class_a_type1_bsh`
- note key indicativa: `nota_us_control_class_a_type1_bsh`
- label UI indicativa: `US control Class A Type 1`
- testo completo: frase standard sopra.

### Normalizzazione interna

Se in qualunque percorso viene trovata `nota_us_control_class_a_type1_bsh`, il codice deve considerarla compatibile con `nota_us_control_class_a` per i controlli interni.

Attenzione: compatibile non significa stampare entrambe le frasi.

Nel certificato finale deve uscire una sola frase tra:

- vecchia `US control Class A`;
- nuova `US control Class A Type 1 / backwall`.

Questo deve valere per:

- prompt AI supplier-specific;
- prompt AI generico note;
- prompt vision note;
- fallback testuale;
- eventuale inserimento manuale dalla pagina note.

### Fallback testuale

Creare un riconoscimento non basato solo su match esatto.

Regola consigliata:

- match forte se ci sono tutti i blocchi principali: `AMS/2154`, `Class A`, `Type 1`, `single indication/2mm`, `backwall/50%/BSH`;
- match accettabile se ci sono `AMS/2154`, `Class A`, `Type 1` e almeno uno tra `2mm` e `50% BSH`, con contesto vicino a `US control`;
- se manca `Class A`, non settare la nuova nota.

### Valutazione finale note

La nuova nota deve comparire nel riepilogo note come nota distinta, ma nel certificato finale va scelta con questa regola.

#### Regola stampa certificato finale

Caso 1 - OL con un solo certificato collegato:

- se il certificato ha la nuova nota estesa, stampare solo la nuova nota;
- se il certificato ha solo la vecchia Class A, stampare solo la vecchia Class A.

Caso 2 - OL con piu' certificati collegati:

- se tutti i certificati hanno la nuova nota estesa, stampare solo la nuova nota;
- se tutti i certificati hanno la vecchia Class A e almeno uno ha la nuova nota estesa, ma non tutti, stampare solo la vecchia Class A;
- se tutti i certificati hanno solo la vecchia Class A, stampare solo la vecchia Class A.

Regola assoluta:

- non stampare mai insieme vecchia Class A e nuova nota estesa;
- la nuova nota sostituisce la vecchia Class A solo quando e' uniforme su tutti i certificati collegati.

Attenzione: non deve essere trattata come nota obbligatoria sempre attesa. Se manca, non deve generare blocco.

## UI

Pagina note Incoming:

- aggiungere la nuova nota come voce visibile;
- se l'utente conferma manualmente la nuova nota, l'app deve sapere che quella nota copre anche la famiglia Class A;
- evitare stati contraddittori lato controlli: nuova Class A estesa presente ma famiglia Class A considerata assente.

Certificato materiale:

- se la nuova nota e' presente su tutti i certificati collegati, il Word finale deve riportare la nuova nota;
- se e' presente solo su alcuni certificati, ma tutti hanno comunque Class A vecchia o nuova, il Word finale deve riportare la vecchia Class A;
- se manca anche la copertura Class A su uno o piu' certificati, resta la logica esistente di nota non uniforme/mancante.

## Test necessari

### Test positivi

1. Certificato con frase esatta:
   - nuova nota presente;
   - vecchia Class A presente.

2. Certificato con variante:
   - `SAE AMS STD 2154 E Class A Type 1`
   - nuova nota presente;
   - vecchia Class A presente.

3. Piu' certificati dello stesso OL tutti con nuova nota:
   - nuova nota OK;
   - certificato finale stampa solo nuova nota.

4. Piu' certificati dello stesso OL, uno con Class A vecchia e uno con nuova nota:
   - famiglia Class A coperta su tutti;
   - nuova nota non uniforme;
   - certificato finale stampa solo vecchia Class A.

### Test negativi

1. Certificato con Class A normale ma senza Type 1/backwall:
   - vecchia Class A presente;
   - nuova nota estesa assente.

2. Certificato con `LST 00`:
   - Class B presente;
   - nuova Class A estesa assente.

3. Piu' certificati dello stesso OL, nuova nota presente solo su uno e Class A assente sugli altri:
   - nuova nota non uniforme;
   - Class A non coperta su tutti;
   - non riportare automaticamente la nuova nota nel certificato finale.

4. Certificato senza note US control:
   - nessuna nota Class A/Class B aggiunta.

## Rischi

- Se la nuova nota viene inserita tra le note obbligatorie senza gestione opzionale, molte righe diventano gialle per errore.
- Se il prompt e' troppo generico, l'AI puo' confondere Class A normale con la nuova Class A Type 1.
- Se il fallback e' troppo stretto, piccoli errori OCR fanno perdere la nota.
- Se il codice stampa insieme Class A vecchia e nuova nota estesa, il certificato finale diventa ridondante e non conforme alla regola scelta.
- Se il codice non tratta la nuova nota come copertura Class A interna, i casi misti possono risultare falsamente mancanti.

## Regola operativa

Non implementare questa attivita' senza conferma esplicita.

Prima dell'implementazione:

1. rileggere i prompt note esistenti;
2. individuare tutti i punti in cui sono elencate le note hardcoded;
3. applicare la modifica in modo uniforme su tutti i fornitori;
4. testare almeno un certificato per fornitore o, se non disponibile, almeno i fornitori con note US control note.
