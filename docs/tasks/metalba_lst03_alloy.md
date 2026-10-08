# Metalba: LST03 e lega 6082H

## Stato

Implementazione locale autorizzata il 30/09/2026. Alpha consultato esclusivamente
con SELECT in transazioni `BEGIN READ ONLY` / `ROLLBACK`. Nessun deploy, nessuna
correzione dei dati Alpha, nessuna chiamata AI a pagamento per questa attivita.

## Audit sui documenti reali

Nei PDF locali `CQF_26-0597_6082H55_2026.pdf` e
`CQF_26-0395_6082H60_2026.pdf`, la lega stampata e `6082F F`.
La distinzione e nelle **Note**, rispettivamente:

- `MATERIALE SECONDO SPECIFICA LST 03`;
- `MATERIALE SECONDO SPECIFICA LST 03-A`.

Il nome file e servito solo a individuare i campioni: non viene usato dalla regola.
Il primo PDF e stato anche verificato visivamente dopo rendering.

Su Alpha sono stati individuati sette documenti Metalba con queste specifiche:

| Riga | CDQ | Documento | Lega della riga al controllo | Stato |
| --- | --- | --- | --- | --- |
| 28 | 26-1799 | 9 | 6082H | chiusa |
| 57 | 26-1863 | 50 | 6082H | chiusa |
| 64 | 26-1869 | 56 | 6082H | chiusa |
| 148 | 26-2163 | 188 | 6082H F | chiusa |
| 167 | 26-2220 | 213 | 6082F F | chiusa |
| 168 | 26-2221 | 214 | 6082H F | chiusa |
| 199 | 26-2401 | 268 | 6082H F | match confermato, non chiusa |

La risposta AI salvata nei requisiti contiene gia LST03/LST03-A in sei delle
sette righe; sulla 28 il campo requisiti non risultava presente nella query.
Nei campi Match delle altre righe corrette risulta il metodo `utente`.
La riga **167** conserva invece la lettura `6082F F`, confermata: va segnalata
all'utente, senza correggerla retroattivamente in questa attivita.

Nei sette certificati LST00 e LST03 possono coesistere. LST00 mantiene la
propria logica delle note US; non determina 6082H. I profili chimici includono
inoltre LST05 (2024) e LST07 (6182), da non confondere con LST03.

## Comportamento implementato

1. L'AI continua a restituire la lega stampata. Il prompt Metalba ribadisce
   di riportare tutte le specifiche nelle Note nel campo requisiti esistente.
2. Il parser accetta la frase affermativa `Materiale secondo specifica LST03`
   o `LST03-A`, con spazi/separatori previsti. Una sigla isolata, LST030,
   LST03-B, negazioni/deroghe o specifiche materiali differenti non attivano
   la trasformazione. LST00 puo coesistere.
3. La regola opera su una coppia DDT/certificato Metalba gia individuata:
   ordine, diametro e peso devono essere presenti e coerenti su entrambi
   i lati; le leghe documentali devono coincidere. Eventuali CDQ/colate
   contrari impediscono la trasformazione. Nessuna equivalenza globale
   6082 = 6082H e nessuna riduzione delle soglie di match.
4. Un'altra riga plausibile o piu materiali differenti sullo stesso
   certificato impediscono la trasformazione. Le proposte Metalba a pari
   punteggio restano da verificare; la selezione dei documenti richiede
   anche un margine tra i primi due candidati.
5. Solo dopo questi controlli vengono proposte le leghe `6082H` sui due
   lati del Match e sulla riga. L'eventuale stato fisico resta conservato.
   La provenienza in Match e indicata come `ddt - LST03` / `certificato - LST03`.
6. `valore_grezzo` conserva la lega documentale; `valore_finale` contiene
   quella interpretata. Il metodo `metalba_lst03` distingue l'interpretazione.
   Il confronto automatico continua a usare gli originali conservati.
7. La conferma del valore mostrato preserva tale provenienza. Se l'utente
   separa o cambia il certificato, i valori derivati tornano agli originali;
   un vero cambio manuale di lega mantiene invece la scelta dell'utente.

## Limiti e ricadute

- Il certificato da solo mantiene per ora la lega documentale: la trasformazione
  dei due campi avviene quando la coppia e verificabile. Anche ordine/peso
  mancanti o ambiguita mantengono i valori originali per il controllo utente.
- Leghe manuali, campi gia confermati, match confermati e righe chiuse sono
  protetti. Non e prevista una migrazione dei casi storici.
- Il valore 6082H fa utilizzare i profili/proposte standard gia esistenti per
  questa variante. Questo puo cambiare gli avvisi del confronto chimico:
  i valori misurati e le conferme tecniche non vengono riscritti dalla regola.
- PDF originali, note, proprieta, accettazione, date e Registro non vengono
  modificati da questa regola. Nessun nuovo standard o limite chimico e creato.
- Rilettura Vision, payload completo e unione certificato-prima sono coperti;
  l'OCR non deve sovrascrivere una lega gia derivata da LST03.

## Verifica

Test con database SQLite temporanei: frase esatta e varianti, altre LST,
contraddizioni, dati mancanti, duplicati, altro fornitore, righe protette,
conservazione raw, conferma manuale, distacco reale, payload AI normalizzato,
unione certificato-prima, materiali differenti sullo stesso PDF.
Nessun test scrive sul DB Alpha o modifica le righe del DB locale dell'utente.

Verifica finale: **479 test backend superati, 12 saltati**, inclusi 14 test
dedicati a Metalba LST03. Build frontend riuscita, `git diff --check` pulito.
Gli avvisi di deprecazione, Browserslist e dimensione bundle restano quelli
delle dipendenze esistenti. Nessun riavvio frontend effettuato.

## Chiarimento nella schermata Match (08/10/2026)

Audit locale riconfermato prima della modifica informativa: 27 test LST03 e
confronto dei dati documentali, piu 53 test del ciclo di match, tutti superati.
La classificazione avviene su coppia verificabile; non basta caricare il secondo
documento. I valori originali restano usati dal confronto, mentre i due campi
visibili possono diventare 6082H con lo stato fisico conservato. Le conferme
e le modifiche manuali precedenti possono impedire tale trasformazione.

La normalizzazione nella lista Incoming e invece solo visiva: per esempio
6082F F appare come 6082, e 6082H F come 6082H. Non cambia i campi Match.

Testo finale approvato: la nota generale conserva la formulazione iniziale;
quella Metalba chiarisce che la proposta puo arrivare quando entrambi i
documenti sono collegati, la lettura e completa e i dati concordano. Carattere
portato da 12 a 18 px, anche per lo stato LST03 gia applicato.

Aggiunta una nota azzurra tenue in apertura della schermata Match:

- per tutti, spiega valore completo e stato fisico nascosto nella lista;
- per Metalba, spiega la possibile proposta LST03 dopo le verifiche e la
  protezione dei valori confermati/manuali;
- solo quando entrambi i campi riportano il metodo metalba_lst03 e i due
  documenti sono presenti, indica che 6082H e stata proposta da LST03;
- durante una modifica manuale non ancora salvata torna alla spiegazione
  generale, evitando di presentare il valore digitato come proposta automatica.

Nessuna modifica alle regole di classificazione, ai salvataggi o ai documenti.
Build frontend riuscita. Componente reale verificato in Chromium per altro
fornitore, documento Metalba solo, coppia interpretata, modifica manuale e
modifica non salvata; larghezze 600/1440/1920 px senza debordi o errori JS.
Prova visiva isolata senza chiamate API. Nessun intervento su Alpha.
