# Controllo AI del tipo documento — prove e proposta

Data: 18 settembre 2026. **Rapporto dei test iniziali**, seguito dall'aggiornamento di implementazione locale in fondo. Il successivo «procedi con Leichtmetall» autorizza solo quel fornitore; Impol resta una proposta.

## Decisione proposta

Introdurre inizialmente il controllo solo per Leichtmetall, mantenendo GPT-5.5.
L'idea funziona sui campioni provati. Non cambiare contemporaneamente il modello globale e tutti i fornitori.
Sol è un candidato economico per una successiva migrazione separata; Astra non ha dimostrato, in questo piccolo campione, un vantaggio di accuratezza che giustifichi il maggior costo.

Nella fase di valutazione descritta sotto: nessuna modifica a codice applicativo, configurazione modello, dati locali/Alpha, stati, match, conferme o documenti originali. Nessun commit/push/deploy eseguito. Creati soltanto harness, copie mascherate, risultati temporanei e questo rapporto. Per la fase successiva leggere l'aggiornamento in fondo.

## Perché il problema non si risolve soltanto cambiando modello

La classificazione iniziale avviene prima dell'AI: `_apply_document_identity_detection`, `_detect_document_type`, `_detect_leichtmetall_document_type` in `backend/app/modules/acquisition/service.py`.
Il DDT Leichtmetall può contenere la richiesta «Inspection Certificate 3.1 according to EN 10204»: non è per questo un certificato.
La scritta Delivery Note è importante per il riconoscimento attuale; un OCR danneggiato può indebolire il riconoscimento del DDT.
Il precedente audit aveva riprodotto la fragilità alterando soltanto copie del testo in memoria. Non è stato identificato con certezza il PDF originale del problema segnalato dal cliente: non attribuire definitivamente quel singolo incidente all'OCR.

La classificazione iniziale determina anche percorso, maschere e prompt. L'AI deve poter contestare tale ipotesi PRIMA che il risultato venga usato per creare/collegare righe. Il semplice cambio di prompt, senza gestione della risposta, non basta.

## Campione e metodo

| Campione locale | Pagine | Verifiche principali |
|---|---:|---|
| Leichtmetall DDT 80008535 | 2 | Due batch 94668/94752; pesi 5014/12211 kg; totale 17225; ordine 19.2 + 4 + 5; lega 6082; diametro 228 |
| Leichtmetall CdQ 94668, 6082, Ø228 | 1 | Identità, selezione billetta, otto valori chimici, note; assenza di prove meccaniche da non inventare |
| Impol CdQ 1505/a, 6082, Ø32 | 2 | Undici valori chimici, tre righe meccaniche, CDQ minuscolo, US B vs A sulle sole estremità, RoHS e LST00 |

Leichtmetall è il pilota proposto; Impol è un controllo aggiuntivo delle regressioni, NON un'autorizzazione a estendere la modifica.

Per ogni campione: GPT-5.5 con prompt attuale; GPT-5.5, Sol e Astra con lo stesso prefisso di controllo più il prompt di estrazione originale. Totale 12 chiamate.
Altre 6 chiamate: DDT con prompt/tipo certificato e viceversa su GPT-5.5 e Sol; immagini vuote e gruppo DDT+certificato su GPT-5.5. Totale **18 generazioni**, tutte completate, nessun retry.

Le immagini sono state renderizzate a scala 2, mascherate con le funzioni esistenti, poi controllate a vista. Ulteriori maschere privacy sono state applicate SOLO alle copie di test. Ogni confronto sullo stesso campione usa immagini identiche.
I prompt di estrazione sono catturati dalle funzioni effettive, non riscritti a mano. Le immagini vengono ripetute per ruolo come nei percorsi esaminati; per il controllo Impol il test usa quattro riferimenti per pagina, anche sulla seconda pagina: i costi misurati non sono quindi una previsione esatta del costo di un caricamento reale.

API Responses, `store=false`, tier standard, massimo 7000 token di output, nessun parametro reasoning aggiunto (default del modello). SDK app rilevato 1.79.0; harness HTTP isolato, nessun aggiornamento SDK. Accessibilità dei tre modelli verificata via API. Chiave letta privatamente dal DB locale con transazione READ ONLY, senza stamparla o salvarla.

## Risultati

| Verifica | Esito |
|---|---|
| Nuovo controllo sui tre documenti correttamente attribuiti | Tipo corretto con tutti e tre i modelli |
| DDT attribuito a certificato, e viceversa | Correzione riconosciuta da GPT-5.5 e Sol; nessuna estrazione nello schema errato |
| Pagine bianche | `incerto`, nessun dato inventato |
| Gruppo DDT + certificato | `misto`, nessuna estrazione forzata |
| DDT multipagina | Entrambi i batch, ordini, lega, diametro e pesi corretti dopo parser esistente |
| Chimica | Tutti gli 8 valori Leichtmetall e gli 11 Impol corrispondono al PDF; assenti non inventati |
| Meccanica Impol | Conservate tutte e tre le righe reali, senza usare i minimi |
| US Impol | B presente; A sulle sole estremità esclusa; A estesa BSH assente |
| Altre note | RoHS Impol e radioattività Leichtmetall conservate |
| CDQ case-sensitive | `1505/a`, non `1505/A`, in tutte le prove Impol |
| Parser/normalizzatori esistenti | Risposte corrette compatibili; match_values, chemistry e properties normalizzati identici alla baseline per tutti i confronti certificato |
| Test automatici locali preesistenti | 16 passati: `test_document_type_detection.py`, `test_material_form_standard_matching.py` |

Meccanica Impol, ordine colonne Rm / Rp0.2 / A% / HB:

1. 396 / 380 / 12,5 / 111,8
2. 404 / 389 / 13,5 / 112,3
3. 396 / 380 / 12,5 / 111,8

### Differenze e anomalie: non dichiarare «tutto identico»

- I numeri e gli esiti delle note controllati restano corretti, ma i testi raw non sono sempre identici.
- Sol restituisce solo la parte inglese della descrizione bilingue Leichtmetall; il significato billetta resta corretto, ma non conserva la descrizione completa come GPT-5.5. Su Impol Sol e Astra accorciano il blocco descrittivo, mantenendo i campi identificativi separati.
- Astra include «only single discontinuities» nella nota US Leichtmetall; è testo realmente visibile. Sul richiamo Impol mantiene LST00 ma omette la dichiarazione generale sull'ordine riportata dalla baseline.
- Il richiamo Leichtmetall perde la sola intestazione «Customer Special Requirements», mantenendo la frase relativa agli accordi d'ordine. Impol: `DIA 32` anziché `DIA 32 x 5000mm`; diametro normalizzato sempre 32, lunghezza ancora nel testo prodotto.
- Le evidenze del nuovo `document_check` alternano chiavi `text` e `quote`; una risposta GPT-5.5 assegna alla pagina 2 un'intestazione presente sulla pagina 1. Il riconoscimento resta giusto, ma la provenienza non è ancora un contratto affidabile. Definire schema rigoroso e validare le pagine nell'implementazione; non usare una citazione AI come prova infallibile.
- Le maschere esistenti, su questi rendering, lasciano recapiti/loghi parziali. Quella Impol copre anche l'area Supplier Order No.: il campo risulta null in tutte le prove e NON si può dichiarare verificata la sua corretta lettura. Le aggiunte privacy di test non hanno corretto questa perdita preesistente.
- Il normalizzatore Impol associa note/requisiti alla pagina finale (2) anche quando il testo tecnico è nella pagina 1: comportamento preesistente e uguale nella baseline. Non corretto in questa attività; separare dall'aggiunta del controllo tipo.

## Costi, modelli e deprecazione

Prezzi standard verificati nella documentazione OpenAI il 18/09/2026, USD per milione di token input/output:

| Modello | Listino input / output | Costo nominale dei 3 documenti con nuovo prompt | Tempo medio osservato |
|---|---:|---:|---:|
| GPT-5.5 | 5 / 30 | circa $0,37 | 22,6 s |
| GPT-5.6 Sol | 4 / 20 | circa $0,25 | 27,9 s |
| GPT-6 Astra | 10 / 50 | circa $0,55 | 12,1 s |

Tempi su una sola esecuzione per caso: NON costituiscono una garanzia o benchmark statistico. Sol costa circa un terzo meno sul campione, ma qui non è più veloce. Astra è più veloce su queste prove, senza vantaggio dimostrato sui valori.

Totale nominale, calcolato dai token delle 18 risposte: **$1,924687**. Non è una lettura della fattura del provider.
Conteggio prudenziale (input maggiorato del 25% per eventuali cache writes e ulteriore margine 10%): **$2,501751**.
Con cambio BCE 17/09/2026 di 1 EUR = 1,1481 USD e IVA ipotetica 22%, il conteggio prudenziale è circa **€2,66**, sotto i **€4 autorizzati**. Trattamento fiscale/addebito effettivo non verificati.
Prima di ogni generazione: conteggio input tramite `/responses/input_tokens`, prenotazione del costo massimo di output nel ledger, stop prima di superare $3 cumulativi prudenziali, nessun retry automatico; richieste incerte avrebbero conservato l'intera prenotazione.

GPT-5.5 è accessibile e non risulta con una data di ritiro annunciata nella pagina deprecations verificata oggi. Non è una promessa di disponibilità perpetua.
Sol: prezzi promozionali garantiti dalla documentazione almeno fino al 21/11/2026; ricontrollarli prima di una migrazione futura.

Fonti ufficiali:

- [GPT-5.5](https://developers.openai.com/api/docs/models/gpt-5.5)
- [GPT-5.6 Sol](https://developers.openai.com/api/docs/models/gpt-5.6-sol)
- [GPT-6 Astra](https://developers.openai.com/api/docs/models/gpt-6-astra)
- [Deprecazioni API](https://developers.openai.com/api/docs/deprecations)
- [Conteggio preventivo token](https://developers.openai.com/api/docs/guides/token-counting)
- [Cambio BCE](https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/index.pt.html)

## Piano inizialmente proposto (stato successivo in fondo)

1. **Solo Leichtmetall:** rendere più robusta la classificazione OCR alle varianti/danni di Delivery Note, senza scambiare un vero certificato senza prove meccaniche per un DDT.
2. **Immagini adatte a entrambi i tipi:** conservare titolo e contenuto tecnico, proteggere dati riservati; verificare anche le maschere del percorso sbagliato. Il test attuale inverte il prompt/tipo, ma usa immagini già preparate correttamente: NON certifica questo tratto end-to-end.
3. **Controllo nella chiamata già prevista:** l'AI valuta prima DDT/certificato/misto/incerto; se concorda continua con lo schema attuale. Nessuna chiamata classificatrice aggiuntiva per il caso normale.
4. **Se discorda:** validare un `document_check` con schema definito; non passare la risposta al vecchio parser come se fosse un'estrazione. Per un documento nuovo e non ancora utilizzato, ripartire una sola volta col percorso corretto. Nessun ciclo DDT→certificato→DDT. Costo della seconda lettura esplicito.
5. **Se incerto, misto, errore o documento già usato:** fermare quel documento e chiedere verifica, senza cancellare righe o toccare match, conferme, valutazioni, KPI e registro. Gli altri documenti non devono essere bloccati inutilmente.
6. **Traccia e test locali:** registrare tipo iniziale/rilevato, motivo, modello e decisione senza segreti. Testare upload automatico/manuale, pagine mancanti, timeout, retry, documenti condivisi e già collegati, certificate-first/DDT dopo, match, chimica/proprietà/note e percorso fino a Word/PDF. Nessuna prova end-to-end con scritture è stata eseguita oggi.
7. **Modello:** tenere GPT-5.5 per il pilota, così si cambia una variabile alla volta. Separare un eventuale passaggio a Sol dal rilascio della correzione; non toccare l'impostazione globale che influenza gli altri fornitori.

### Limiti residui prima dell'estensione a tutti i fornitori

Tre PDF reali non coprono tutti i formati, lingue, fornitori né il documento originale problematico. IACS e rapporto Rp0.2/Rm sono assenti nei campioni: verificata l'assenza di invenzioni, non la lettura di valori reali. Nessuna validazione di produzione, carichi concorrenti, riclassificazione DB o generazione finale Word/PDF. La nuova protezione deve essere progettata riutilizzabile, ma attivata per altri fornitori solo dopo prove dedicate delle rispettive immagini, maschere e parser.

## Evidenze locali (non da mettere in Git con documenti aziendali)

- `backend/tmp_eval/doc_type_eval_20260918.py`: preparazione e chiamate con tetto preventivo.
- `backend/tmp_eval/analyze_doc_type_eval_20260918.py`: confronto con valori PDF e parser puri.
- `backend/tmp_eval/doc_type_eval_20260918/manifest.json`: campioni e hash.
- Nella stessa cartella: `ledger.json`, `analysis.json`, prompt originale/prefisso, risposte complete e immagini controllate.
- Le cartelle di prova sono temporanee/ignorate; nessuna chiave salvata. Questo MD è il riepilogo versionabile, in attesa di eventuale richiesta commit.

## Aggiornamento — implementazione locale autorizzata Leichtmetall

Richiesta: «fammi piano per correzioni anche Impol e procedi con Leichtmetall».

Implementato, senza cambio del modello e senza migrazioni database:

1. Riconoscimento OCR più robusto di Delivery Note e dei segnali logistici, mantenendo la precedenza dei risultati chimici su un vero certificato.
2. Preparazione immagini Leichtmetall comune ai due tipi, conservando il titolo anche quando il tipo iniziale è sbagliato. Controllo di disponibilità di tutte le pagine.
3. Prefisso al prompt già usato e validazione locale rigorosa di `document_check`, prima del parser di estrazione. Non è un vincolo Structured Outputs imposto via API: risposte non conformi vengono rifiutate localmente.
4. Verifica prima della creazione delle righe. Se il tipo coincide, la stessa lettura alimenta la cache e non richiede una seconda chiamata ordinaria. Se diverso, una sola rilettura nel percorso corretto, solo per documenti temporanei esplicitamente caricati nel run e privi di riferimenti. Il tipo viene salvato solo dopo il successo della rilettura e un nuovo controllo dei riferimenti.
5. Documenti misti/incerti, risposte incomplete, timeout o documenti già usati: esclusi dall'elaborazione di quel run e segnalati nel riepilogo errori. Protezione anche dei percorsi certificate-first, collegamento nelle due direzioni e rematch; nessuna correzione automatica dei documenti storici.
6. Traccia nelle evidenze documento già esistenti: tipo iniziale/finale, decisione, motivi, modello configurato. Un successivo riconoscimento OCR non annulla un tipo già controllato.

File: `document_type_guard.py`, `leichtmetall_type_workflow.py`, integrazioni mirate in `service.py`, test `test_leichtmetall_document_type_guard.py`.

### Verifiche e limiti

- Suite backend completa eseguita nel Docker locale: **284 test superati**, 7 avvisi di deprecazione delle dipendenze, nessun fallimento (`python -m pytest tests -q`). `git diff --check` senza errori di whitespace.
- Test con DB SQLite isolato e risposte simulate: contratto valido/errato, tipi scambiati, misto/incerto, timeout, una sola rilettura, documento usato, pagine mancanti, cache, isolamento altri fornitori, esclusione dal match e instradamento del run.
- Controllo visivo dei rendering di DDT 80008535 e 80008518 e certificato 94668: titoli e dati tecnici leggibili. Le maschere privacy complete **non sono risolte**: restano frammenti preesistenti di loghi/recapiti, da trattare nell'audit separato.
- Nessuna nuova chiamata AI a pagamento in questa fase. I risultati delle 18 chiamate sopra si riferiscono al prefisso sperimentale; il contratto definitivo più rigoroso è verificato automaticamente con risposte simulate, non ancora con una nuova campagna AI reale.
- Non eseguiti upload reali con scritture nel DB aziendale, prova concorrente di produzione o ciclo completo Word/PDF. La suite superata non sostituisce questi controlli prima di un rilascio Alpha.
- Nessun commit, push, deploy Alpha o modifica delle impostazioni AI effettuati.

Piano Impol separato: [audit, piano ed esito successivo](impol_masking_note_page_audit_plan.md). Dopo questo rapporto Silvano ha autorizzato l'implementazione locale, documentata nel file collegato. L'eventuale bonifica di documenti già caricati richiede una decisione separata, non avviene automaticamente.
