# Ripresa lavori C e D — Word di riferimento e variazione materiale OL

## Stato e perimetro

Decisioni concordate con l'utente il 17–18/10/2026. **C e D implementati nei
sorgenti locali il 18/10**, con il collaudo registrato sotto. Le sezioni del
piano iniziale restano per conservare motivazioni e vincoli. Alpha rimane
invariata; il futuro deploy richiede schema additivo e verifiche dedicate.
Commit/push, riavvii e deploy richiedono le rispettive indicazioni dell'utente.

Le correzioni A/B e la proiezione registro sono già presenti nella working
tree e testate: preservarle, insieme alle modifiche estranee. Non assumere
che siano già committate o pubblicate. Rileggere git status/diff alla ripresa.
Audit precedente: [registro e riuso](register_early_word_visibility_20261017.md).

## C — Regola funzionale concordata

**Il Word completato è il riferimento per quell'OL e quella lavorazione,
comprese seconde pagine e allegati. All'arrivo dei nuovi DDT CERTI riutilizza
quel lavoro e aggiorna automaticamente i dati della spedizione.**

Esempio del flusso voluto:

1. CERTI prepara il Word; l'utente lo completa, se necessario, e lo ricarica.
2. L'utente genera il PDF della prima quota DDT.
3. Arriva un altro DDT della stessa lavorazione, anche molto tempo dopo.
4. CERTI prepara automaticamente la copia con i dati del nuovo DDT, partendo
   dal Word completo: l'utente non deve ricreare il Word o scegliere ogni volta.
5. I PDF già chiusi rimangono invariati.

L'ereditarietà tra lavorazioni mantiene la priorità attuale del Raw, con
seconde pagine e allegati. NON implementare la catena proposta
Raw -> 30 -> 40 -> 50 descritta come alternativa nel
[documento ereditarietà](../modules/quarta_taglio_word_inheritance_rules.md).
Le lavorazioni già preparate non vengono riscritte retroattivamente.

Non introdurre come requisito una scelta ordinaria «solo questo DDT / tutti
i futuri»: era una proposta dell'assistente, NON il flusso richiesto.
Il dubbio ipotetico sulle modifiche limitate a una spedizione non autorizza
a rimettere in discussione la regola concordata o aggiungere blocchi generici.

## C — Evidenze e difetto da correggere

Audit Alpha read-only, transazioni READ ONLY e simulazioni senza apply/sync:

- OL1091/F3 531000300: ID99 Word iniziale; ID189 Word ricaricato con pagine
  aggiuntive, PDF chiuso per DDT2418. Nuovo DDT dello stesso F3 simulato:
  `different_word_sources`. Nuova lavorazione ipotetica 531000330: il selettore
  di ereditarietà sceglierebbe invece ID189. Due percorsi incoerenti.
- OL1095/F3 096015000: base ID88, copie completate ID208/225 con pagine di
  trattamento 927/26. Il nuovo DDT simulato si blocca; la nuova lavorazione
  ipotetica 096015030 sceglierebbe ID225.
- OL972/F3 413001200: ID3 riporta 603-2, ID133/134 EN AW 755-2. Differenza
  tecnica reale; non dedurre la correttezza dal solo timestamp o da un
  baseline legacy. Verificare la versione valida per il riuso futuro senza
  riscrivere i documenti emessi.
- I DDT reali censiti per questi tre OL hanno documenti già presenti; i blocchi
  citati riguardano simulazioni di un DDT futuro, non nuovi DDT realmente creati.

Precisazione sulla frase «Progressive numbering ... 1 ... 86» di OL1091:
è stata trovata nel Word ID189 come testo fuori dai campi automatici, non nel
Word ID99. `word_source=user_uploaded` prova il ricaricamento del file, NON chi
abbia scritto la frase o da quale sistema provenga. La quantità DDT è invece
un dato noto all'app. Non confondere quantità automatica e testo libero;
non sostenere che l'utente debba riscrivere quantità/DDT. Non inventare un
parser che modifichi qualsiasi numero nei testi delle seconde pagine.

## C — Piano software alla ripresa

1. Tracciare generazione, ricaricamento, rigenerazione, seconde pagine,
   allegati, riuso DDT, ereditarietà e chiusura/riapertura PDF. Individuare
   come riconoscere in modo persistente il Word di riferimento valido.
2. Distinguere il riferimento dalle copie prodotte automaticamente per i DDT:
   una copia appena creata non deve scalzare il riferimento soltanto perché
   ha una data più recente. Una modifica esplicita al Word deve poter aggiornare
   il riferimento secondo la regola concordata, con provenienza tracciabile.
3. Usare una scelta della versione coerente nei due percorsi: nuovo DDT dello
   stesso F3 e nuova lavorazione che eredita dal Raw. Non ignorare indiscriminatamente
   le differenze tra file e non scegliere il massimo ID/updated_at come soluzione.
4. Conservare controlli di materiale, standard, identità OL/F3/quota, allegati
   e file presenti. Operator resta chi ha preparato il Word; chi genera il PDF
   è registrato separatamente. Preservare la firma Quality Manager.
5. Per i record storici ricostruire la provenienza con una preview. Se la
   versione valida non è dimostrabile, riportare il singolo caso all'utente:
   non trasformare un dubbio storico in una domanda a ogni nuovo DDT.
6. Non riscrivere PDF chiusi né copie di altre quote già lavorate. Definire
   esplicitamente gli effetti sulle quote aperte prima di implementare.

## D — Avviso chiaro e percorso per risolvere

Approvato: avvisare che il materiale/certificato fornitore dell'OL è cambiato
rispetto al Word e permettere all'utente di sistemarlo, senza restare in un
blocco senza uscita. Non eliminare il controllo di compatibilità.

Caso verificato OL1012:

- Word ID24: CDQ 26-1909, colata 26139E, 721 kg nello snapshot iniziale.
- OL attuale: stesso CDQ con 1358 kg, più CDQ 26-0969/26016A con 211 kg.
- Quota660, DDT2410-06/10/2026: manca in Incoming il CDQ 26-0969.
- Simulando SOLO Incoming completato, il piano passa da `incoming_not_ready`
  a `no_compatible_word`: il vecchio Word non copre il materiale attuale.
- La presenza del nuovo materiale sull'OL non prova da sola quale colata sia
  stata spedita su quel DDT. Verificare il perimetro dei dati prima di imporre
  un aggiornamento tecnico del documento.

Messaggio concordato come direzione, da adattare ai dati reali:

> Il materiale dell'OL è cambiato rispetto al Word preparato. È presente anche
> il certificato fornitore 26-0969. Verifica il materiale in Incoming, poi
> aggiorna il Word prima di preparare il PDF.

Piano:

1. Mostrare la causa precisa e i CDQ coinvolti, non il generico «file non
   collegabile». Distinguere certificato mancante in Incoming da Word da aggiornare.
2. Rendere raggiungibile «Apri Incoming» e il percorso per aggiornare il Word
   interessato, rispettando ruoli e permessi esistenti.
3. Verificare che il blocco «Word già preparato» non impedisca questa correzione:
   niente nuovo Word Raw duplicato e niente necessità di riaprire un vecchio
   PDF chiuso solo per correggere il riferimento destinato ai futuri DDT.
4. Rivalutare materiale/standard/conformità dopo la correzione, conservando
   le conferme necessarie; riprendere il riuso solo quando i requisiti sono soddisfatti.
5. Non cancellare dati né modificare automaticamente il materiale per far
   passare il controllo. Non promettere che il solo caricamento Incoming risolva tutto.

## Verifiche richieste e successivo deploy

- Word iniziale -> completamento -> primo PDF -> successivi DDT, anche oltre
  60 giorni: contenuti completi conservati, dati spedizione corretti.
- Seconda pagina incorporata nel Word, caricamento dedicato e allegati PDF;
  più quote nello stesso DDT; nuovo F3; Raw e lavorazioni già esistenti.
- Ricaricamento/rigenerazione e concorrenza con worker; nessun rimbalzo della
  fonte verso una vecchia copia. Standard cambiato, file mancante, materiale
  aggiunto e Incoming incompleto non devono essere aggirati.
- D: completare tutto il percorso utente fino alla disponibilità del Word
  corretto per la quota, non collaudare soltanto il messaggio.
- Hash dei Word sorgenti e PDF emessi, numerazione/export, quantità, firme,
  esclusioni, registro e protezioni A/B: assenza di regressioni.
- Verifica visiva locale dei messaggi/azioni seguendo le istruzioni browser;
  non riavviare implicitamente frontend o servizi Alpha.
- Dopo l'implementazione aggiornare il runbook con migrazioni eventualmente
  necessarie, preview Alpha, backup, rollback e verifiche dei dati specifici
  Alpha. Mai copia del DB locale, scelta massiva non verificata o rigenerazione PDF.

## Implementazione locale del 18/10/2026

Conferme ricevute: aggiornare anche le copie automatiche senza PDF; segnalare
quelle modificate manualmente prima di sostituirle. Ogni certificato considera
tutti i materiali attuali dell'OL, anche quando ci sono più DDT. Non viene
introdotta una scelta arbitraria della colata per una singola spedizione.

### Riferimento e copie

- Una colonna JSON nullable `quarta_taglio_final_certificates.word_reference`
  distingue pubblicazioni esplicite e copie automatiche, con revisione, origine,
  data dell'azione e impronte del documento. I timestamp amministrativi dei
  record non scelgono più la versione. Le revisioni precedenti della stessa
  fonte restano descritte nella cronologia; i vecchi file non vengono eliminati.
- Generazione, ricaricamento, aggiunta/rimozione allegati e seconde pagine
  pubblicano il Word completato. Le copie DDT registrano la revisione ricevuta,
  senza diventare nuove pubblicazioni soltanto perché appena create.
- Dopo un completamento, il worker ricontrolla solo OL/F3 interessati usando
  lo stesso database della richiesta. Aggiorna copie automatiche ancora aperte
  e fisicamente integre. Nessun aggiornamento automatico di PDF chiusi, copie
  modificate o documenti con versioni PDF precedenti. Restano identità DDT,
  quantità, esclusioni, standard e Incoming come condizioni obbligatorie.
- Copie lavorate separatamente: avviso «Il Word di riferimento è stato aggiornato»
  e comando «Aggiorna questa copia dal riferimento», con conferma prima della
  sostituzione e conservazione del vecchio file/impronta.
- Storico con Word realmente diversi: una conferma esplicita «Usa questo Word
  come riferimento» permette di adottare la versione verificata, anche da un
  PDF già chiuso, senza riaprirlo o riscriverlo. Non è una domanda a ogni DDT.
- La nuova lavorazione usa la stessa risoluzione della versione Raw. Corretto
  anche l'ingresso dal primo DDT della lavorazione: copia il Word completo,
  incluse pagine incorporate, e aggiorna i campi di testata. Operator/Quality
  Manager vengono conservati durante l'eredità automatica. La priorità Raw
  rispetto alle lavorazioni intermedie non cambia.
- Ricaricamento e rigenerazione con ID esplicito operano sul documento scelto,
  anche se lo stesso OL ha altre lavorazioni aperte o basi senza unità DDT.
  Non cercano l'ultimo Word aperto dell'OL ignorando la selezione dell'utente.

### Variazione materiale e correzione praticabile

- Avviso con i CDQ aggiunti o con colata diversa, accesso Incoming e «Aggiorna
  Word». Finché mancano certificati/validazioni o standard, il percorso indica
  la causa. La sola ricarica di un file non vale come bonifica del materiale.
- L'azione esplicita rivaluta tutti i materiali e aggiorna sia la pagina tecnica
  sia lo snapshot dei materiali e dello standard; fuori norma richiede consenso.
  Le seconde pagine, immagini e allegati incorporati sono conservati tramite
  `docxcompose`, importando anche le relazioni del documento.
- La conferma avverte che le modifiche manuali nella pagina tecnica verranno
  sostituite. Per riconoscere il confine usa la tabella meccanica generata o
  il messaggio applicativo di assenza proprietà; con struttura personalizzata
  non riconoscibile si ferma conservando file e dati originali, senza tagliare
  contenuti alla cieca. Il caso deve essere verificato prima di riprovare.
- Se la fonte appartiene a un PDF chiuso, crea un riferimento aperto separato
  per i riusi futuri, con lo stesso numero OL/lavorazione. Non riapre né cambia
  la vecchia spedizione. Restano distinte le copie dei singoli DDT.
- Con più materiali controlla anche le proporzioni note dei pesi: una diversa
  media chimica non deve passare perché CDQ e lotti sono rimasti uguali.
- La protezione vale anche prima della generazione PDF, dopo l'aggiornamento
  campi e dopo la conversione, comprese le chiamate dal Registro: un aggiornamento
  del riferimento durante la conversione non chiude un PDF ormai superato.

### Verifiche e limiti della consegna

Esito finale 18/10: **279 test backend distinti superati**: 106 fra nuovi C/D,
riuso A/B e compatibilità; 171 regressioni SQLite più i due controlli dello
storico eseguiti separatamente su PostgreSQL. **25 test Node superati**, build
frontend riuscita. Restano gli avvisi build già presenti su Browserslist e
dimensione bundle; nessun aggiornamento dipendenze applicative introdotto.

- Test SQLite e PostgreSQL temporaneo (senza rete aziendale): riferimenti,
  successivi DDT, prima lavorazione derivata, sostituzione copie con conferma,
  conservazione Word/PDF, metadati, file alterati, migrazione idempotente,
  permessi, hash richiesta superato, rollback e due worker concorrenti.
- Regressioni su riuso precedente, registro, storico DDT, coda, filtri,
  rigenerazione e standard. Test Node e build frontend.
- Browser React reale con tutte le API simulate: conflitto storico, copia
  manuale, materiale mancante/pronto, conferme e richieste corrette; nessun
  errore JavaScript e layout verificato a 1440 e 1920 px.
- Rendering con il convertitore applicativo di Word sintetici: tabelle chimiche
  e meccaniche popolate, seconda pagina con immagine. Verificati entrambi i PDF
  a due pagine e immagini prima/dopo; documenti sorgenti conservati.
- Artefatti temporanei: `tmp_eval/word_reference_qa/` e
  `tmp_eval/word-reference-*.png`. Frontend di collaudo 5174 separato; quello
  abituale 5173 non riavviato. Nessun documento aziendale creato per collaudo.
- Verifica dell'ambiente locale effettivo: progetto Docker della workspace,
  DB host `postgres`/database `certi_nt`, colonna `word_reference` presente
  tramite bootstrap di sviluppo. La porta 5173 serve le nuove azioni C/D
  (controllato il modulo React via HTTP). Non equivale a un deploy Alpha.
- Resta da pubblicare su Alpha e da adottare la fonte valida dei tre casi
  storici OL1091/1095/972 dopo verifica umana. Nessuna scelta massiva implicita.

Al futuro deploy seguire la sezione C/D del runbook: preparare la colonna
prima delle query ORM e non copiare il DB locale. Questa consegna non autorizza
commit/push o deploy e non afferma che i servizi Alpha eseguano già il codice.
