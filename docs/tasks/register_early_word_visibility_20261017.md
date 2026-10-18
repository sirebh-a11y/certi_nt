# Registro: Word base e certificati DDT — 17/10/2026

**Aggiornamento decisioni C/D:** per la ripresa prevale il
[piano concordato C e D](word_reference_and_material_changes_resume_20261017.md).
Le proposte precedenti sotto sono conservate come storia dell'audit, non come
richiesta di nuove scelte a ogni DDT. C/D sono implementati nei sorgenti locali
il 18/10; collaudo e preparazione deploy sono nel piano collegato.

## Perimetro e autorizzazione

Approvati in locale: correggere la doppia riga del registro e l'attesa DDT
non vera; verificare regressioni ed ereditarietà. Il conflitto fra versioni
Word richiede un piano separato (punto 4), NON viene risolto in questo intervento.
Nessun commit/push, riavvio del frontend abituale o deploy implicito.
Alpha consultato soltanto in lettura: SQL in transazione READ ONLY e rollback,
file verificati senza modificarli, nessuna chiamata GET/refresh mutante.

## Riscontri Alpha

- Caso segnalato: OL2026001091, F3 531000300, certificato 7051_01_00/26.
  ID99 è il Word base del 22/09 senza DDT. ID189 è il documento della quota
  DDT 2418-08/10/2026, 86 pezzi, PDF chiuso. I file esistono; un solo PDF
  è pubblicato per quella quota. La base serve al motore, non è un secondo
  lavoro di spedizione ancora da completare.
- Alla verifica: 228 record numerati, 165 senza DDT, 63 con DDT. La simulazione
  della nuova proiezione, eseguita solo in memoria sui record Alpha, nasconde
  17 basi e mostra 211 record. Per OL1091 nasconde ID99 e conserva ID189.
  Sono dati fotografati al 17/10, da ricalcolare al futuro deploy.
- 14 gruppi con stesso OL/F3/DDT contengono quote distinte: NON sono doppioni.
  Esempio OL1000, F3 096013900, DDT2457: ID201 (167 pezzi) e ID202 (106 pezzi).
- OL1019 ha Raw 509001100 e lavorazioni ereditate 509001160/161/162 senza
  DDT: devono restare. OL1020 ha Raw 531000200 senza DDT e lavorazione
  531000230 con PDF: il Raw non va nascosto per il solo fatto che l'OL coincide.
- Cinque basi hanno già DDT salvati, ma nessun documento di quota preparato:
  OL1012 non ha Incoming pronto; OL977/1071/1128/1156 hanno snapshot materiale
  del Word non coincidente con l'attuale lista lotti. Il successivo audit A/B
  sotto distingue i quattro falsi blocchi dal nuovo materiale di OL1012.
  In quei casi "In attesa DDT" descrive male la situazione.
- OL1091: simulando un futuro DDT, il pianificatore segnala
  `different_word_sources` fra base originale e Word ricaricato sulla quota.
  Non prova da solo una differenza tecnica: il confronto comprende anche
  struttura interna DOCX, metadati, allegati e altri attributi. Piano sotto.

## Correzione realizzata

1. Solo proiezione registro: nascondere la base senza DDT quando esiste una
   quota con stesso OL, F3, numero e snapshot materiale completo coincidente,
   e almeno un Word esistente o PDF finale esistente. Nessuna cancellazione.
2. Non nascondere documenti con PDF o identità eSolver parziale, prove materiali
   incomplete, numero/materiale/F3 diverso, o quota priva di file disponibili.
   Restano tutte le singole quote anche con uguale numero certificato/DDT.
3. Il refresh del registro sostituisce la base con le quote corrispondenti:
   non deve reinserirla né accorpare documenti con lo stesso numero.
4. Quando un DDT è già noto per esatto OL/F3 ma la base non ha una quota
   associata, mostrare **DDT presente — verifica richiesta**. È un'informazione
   sul DDT conosciuto, NON un abbinamento manuale richiesto né una previsione
   del lavoro che il motore farà. Le priorità PDF chiuso/Word da aggiornare/
   Word mancante restano invariate.
5. Fonti dell'informazione: certificati DDT già registrati, snapshot persistenti
   e cache locale eSolver. Nessuna interrogazione remota aggiuntiva; lo storico
   continua a contare anche fuori dalla finestra eSolver.

Con la sola correzione di presentazione non cambiano ereditarietà, scelta della sorgente Word, standard/conformità,
numerazione, permessi, generazione PDF, export eSolver o raccolta DDT.
La vecchia esclusione generica dei record senza unit_key per intero OL è
sostituita dalla regola precisa, per non nascondere una lavorazione diversa.

## Verifiche locali

- Suite nuova registro: 13 test, inclusi assenza scritture/SQL remota,
  conservazione file, Raw/lavorazioni, materiali incompleti/diversi, file
  mancanti, quote multiple, riapertura PDF, refresh e sorgente di ereditarietà.
- Riuso Word: 43 test superati, SQLite e PostgreSQL isolato, inclusa la sequenza base
  nascosta -> ulteriore DDT -> riuso riuscito senza cambiare il file base.
  Verificati anche concorrenza, conflitti manuali, quantità, allegati e export
  limitato alla quota. Nessuna esecuzione sul database applicativo.
- Suite storici DDT (30 test), quantità registro (10), filtri Word (15), coda
  DDT (46), standard/rigenerazione (48); connessioni aziendali simulate.
- Frontend: tutti i 34 test Node superati. Build production riuscita;
  avvisi preesistenti Browserslist datato e bundle grande, nessun upgrade.
- Browser Playwright sulla pagina reale React, TUTTE le API simulate:
  sostituzione della base durante refresh, due quote con uguale numero/DDT,
  Raw e lavorazione ereditata distinti, avviso DDT, azioni PDF e ordinamento.
  Nessun errore JavaScript, nessuna chiamata ad API reali. Screenshot 1920/1440
  ispezionati; tabella con scroll interno come prima.
  Artefatti temporanei: `tmp_eval/packages_qa/register_projection_check.mjs`,
  `tmp_eval/register-projection-1920.png`, `tmp_eval/register-projection-1440.png`.
- Frontend abituale 5173 non riavviato: rinvio dell'utente rispettato.
  Collaudo con Vite separato 5174. Non è una prova di deploy Alpha.

## Punto 4 — piano iniziale, superato dall'implementazione C/D del 18/10

Problema distinto dalla riga doppia: per un futuro DDT il motore potrebbe
trovare due Word candidati diversi e non sapere quale riutilizzare.

1. Confrontare in lettura base e Word ricaricato di OL1091: dati tecnici,
   testo manuale, tabelle, firme, seconda pagina, allegati, controlli documento.
   Separare le differenze reali dalle sole informazioni interne di salvataggio.
2. Se il documento è equivalente, proporre una normalizzazione circoscritta
   del confronto: mai ignorare testo tecnico, immagini, firme o allegati.
   Una semplice uguaglianza del testo non è prova sufficiente.
3. Se la differenza è reale, chiarire quale Word l'utente intenda usare per
   i DDT futuri; poi progettare una scelta esplicita e tracciata della fonte.
   Non scegliere automaticamente l'ultimo file solo perché è più recente.
4. Provare DDT successivi anche lontani nel tempo, modifiche manuali,
   seconde pagine/allegati, F3 diversi e PDF già chiusi. I documenti già
   emessi restano immutati; nessuna rigenerazione massiva o riscrittura storica.

I quattro casi di lotti ampliati sono trattati separatamente nella correzione A
sotto: non sono risolti eliminando il confronto delle versioni Word e non
autorizzano match permissivi.

## Audit e correzioni A/B approvate — 17/10/2026

### A — nuovi prelievi, stesso materiale

Audit Alpha in transazione READ ONLY: quote 684/711/767/800, rispettivamente
OL977/1128/1071/1156, hanno Incoming pronto e lo stesso CDQ, colata e articolo
del Word. Quarta ha aggiunto lotti di prelievo, non un nuovo certificato fornitore.
I quattro Word non riportano quei numeri di lotto. Il confronto precedente
richiedeva l'uguaglianza dell'intera lista e bloccava quindi il riuso.

La compatibilità ora permette l'aggiunta di lotti SOLO per un unico materiale
identificato completamente. Restano bloccati rimozione/sostituzione dei lotti,
materiale nuovo, identità incompleta o ambigua. Ordine e ripetizioni della stessa
lista non creano differenze. Nessuna correzione degli snapshot/file già salvati.

**Protezione materiali multipli:** non estendere questa eccezione a più CDQ/
colate/articoli. La chimica può essere una media pesata: nuovi prelievi possono
alterarla anche senza nuovi CDQ. Con più materiali rimane richiesto lo stesso
insieme di lotti per ciascun materiale; una diversa regola richiede altro audit.

OL1012/quota660 rimane fermo correttamente: oltre a 26-1909/26139E è presente
il nuovo CDQ 26-0969/26016A (211 kg), non pronto in Incoming. Non è un semplice
lotto aggiuntivo e non va sbloccato eliminando i controlli.

### B — riferimenti legacy dell'operatore / Quality Manager

OL1139, F3 1140000100, certificato 7029_02_00/26: Word dei record 95/135/136
identici salvo campi spedizione gestiti; compresi footer, immagini e firme.
ID135 non ha i riferimenti interni alle persone, mentre 95/136 hanno (4,3).
Il Word riporta Operator Marco Gorza. Il NULL storico non dimostra un documento
diverso e provocava un falso conflitto per un futuro DDT.

Solo dopo il confronto completo dei file e degli altri dati il pianificatore
sceglie una sorgente con tutti i riferimenti noti coerenti (ID95 nel caso).
Due persone note diverse restano un conflitto. Non si combinano due record
incompleti, non si deducono persone dal PDF e non si riscrivono i record legacy.
Testo, footer, immagini, firme, allegati e conformità non vengono ignorati.

**Decisione utente confermata:** Operator resta chi ha preparato il Word,
NON chi preme Genera PDF. Il generatore del PDF è registrato separatamente
in `QuartaTaglioCertificatePdfVersion.generated_by_user_id`. Nessuna modifica
alla firma Quality Manager o ai PDF già chiusi. La dicitura precedente
"firmatari" era imprecisa: distinguere operatore e firma Quality Manager.

### C / punto 4 — riscontri precedenti alla decisione finale

Le differenze sono reali, non semplice metadata:

- OL1091: la quota ha pagine manuali con prove/trattamento 919/26 e numerazione
  pezzi 1–86. La successiva decisione sul Word completo di riferimento è
  registrata nel piano C/D; non dedurre da questo testo chi lo abbia scritto.
- OL1095: le quote hanno pagine manuali (trattamento 927/26) diverse dalla base.
- OL972: documenti con riferimenti normativi/limiti diversi (603-2 contro
  EN AW 755-2). Non scegliere in base alla sola data o al baseline legacy.

Le regole Raw/lavorazioni e seconda pagina restano quelle di
`docs/modules/quarta_taglio_word_inheritance_rules.md`. Nessuna nuova priorità
o catena di ereditarietà implementata. I tre conflitti restano protetti.

### Verifiche A/B

- 14 test puri di compatibilità: lotti aggiunti/rimossi/sostituiti, identità
  incomplete, materiali multipli, riferimenti persone mancanti/coerenti/diversi.
- Suite riuso estesa a 47 test SQLite/PostgreSQL isolato: copia per nuovo DDT,
  sorgenti e PDF precedenti invariati, riferimenti legacy non riscritti,
  concorrenza/rollback/allegati/export e altre protezioni già esistenti.
- Simulazione del codice locale solo in memoria su Alpha, transazione READ ONLY:
  quattro quote sopra -> `reuse`; futuro DDT OL1139 -> `reuse` da ID95;
  OL1012 -> `incoming_not_ready`; OL1091/1095/972 -> `different_word_sources`.
  Nessun flush/commit, record inserito, file scritto o servizio cambiato su Alpha.
- I conteggi sono una fotografia, non una lista autorizzata per un recupero.

## Futuro deploy

Backend/frontend insieme, senza migrazioni DB o bonifiche. Le basi restano
nel DB/storage. La sola proiezione registro non modifica dati; A/B invece
consentono al normale worker di creare nuove quote Word ammissibili dopo il
deploy. Il rollback NON deve cancellare automaticamente tali nuove quote:
verificare eventuali lavorazioni intervenute. Applicare tutte le cautele del
runbook, incluse spazio, backup e attività utenti.
Non ripetere recuperi storici né cambiare i flag di riuso/raccolta DDT.
