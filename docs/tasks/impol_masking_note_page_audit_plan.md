# Impol — piano correzioni mascheramento e pagina delle note

Data: 18 settembre 2026. **Implementazione locale autorizzata e completata; deploy Alpha non richiesto.** Il piano iniziale resta sotto come traccia, seguito dall'esito dei lavori.

## Cosa è emerso

Nel test locale del certificato Impol 1505/a, 6082, Ø32, due pagine:

- La maschera rettangolare del logo copre anche `Supplier Order No.`. L'AI riceve il campo già oscurato: cambiarle modello non recupera il dato.
- Alcuni frammenti di nomi, recapiti e loghi restano visibili nelle copie prodotte dalle maschere attuali. Le prove AI precedenti hanno usato copie con protezioni privacy aggiuntive, non modifiche all'app.
- Il normalizzatore assegna note e richiamo requisiti alla pagina finale, anche quando la frase si trova sulla prima. È un problema di provenienza dell'evidenza, non una prova che il valore tecnico sia errato.
- Sul campione sono rimasti corretti gli undici valori chimici, le tre righe meccaniche, CDQ `1505/a`, US classe B, esclusione classe A sulle sole estremità, RoHS e LST00. Non risultano da correggere queste regole.

Riferimenti in `backend/app/modules/acquisition/service.py`: `_mask_impol_visual_logo_regions`, `_build_impol_certificate_masked_page`, `_normalize_impol_certificate_ai_payload`. La maschera certificato usa il rettangolo relativo `(0.70, 0.07, 0.98, 0.24)`; note e requisiti vengono costruiti usando la pagina/ritaglio finale.

## Piano proposto, in due correzioni distinte

### 1. Mascherare solo le zone riservate, senza perdere l'ordine

Individuare inizio e fine dei nomi con le coordinate OCR e i confini visivi di loghi/timbri. Unire le parole dello stesso campo e coprire tutto il campo, con un piccolo margine controllato; non un grande rettangolo che comprende dati tecnici.

Proteggere dalla copertura CDQ, Supplier Order No., Customer Order No., Packing List No., colata, lega, dimensioni, chimica, proprietà e note. Esaminare ogni pagina, comprese firme e timbri. Nei casi in cui i confini non sono affidabili, prevedere verifica della maschera prima dell'invio, non inviare una pagina non protetta. L'eventuale interazione UI va concordata prima di implementarla.

### 2. Collegare ogni nota alla pagina effettiva

Conservare per ogni nota/richiamo la citazione e la pagina sorgente, poi verificare la corrispondenza con il testo disponibile. Usare una pagina solo quando identificabile; se la stessa frase compare più volte o l'OCR non permette verifica, segnalare la provenienza da verificare, senza scegliere automaticamente l'ultima pagina.

Non cambiare gli esiti tecnici delle note, la distinzione ultrasuoni sull'intero materiale/sole estremità o la logica di match. Prima del codice verificare tutti i consumatori di `page_id` e dei ritagli, per non mostrare evidenze incoerenti nelle finestre di conferma.

## Rischi e prove prima dell'approvazione al rilascio

| Rischio | Verifica richiesta |
|---|---|
| Maschera troppo piccola: dati riservati esposti | Controllo visivo di tutte le pagine, nomi, loghi, recapiti e timbri |
| Maschera troppo grande: ordine/valori nascosti | Confronto originale/copia e leggibilità di tutti i campi identificativi e tecnici |
| Scansione spostata, ruotata o con risoluzione diversa | Campioni con più layout, dimensioni e qualità OCR; non solo 1505/a |
| Nota nella pagina errata | Frase in pagina 1, pagina 2, ripetuta, assente o OCR incompleto |
| Regressioni nell'estrazione e nel match | Confrontare CDQ minuscolo, ordini, chimica, tutte le righe meccaniche, note e richiami |
| Cambiamenti involontari allo storico | Nessuna rilettura massiva o modifica delle conferme già salvate |

Usare prima test locali senza chiamate AI; eventuali nuove prove a pagamento rispettano il budget residuo già autorizzato, da verificare nel ledger. Le anomalie privacy analoghe osservate su Leichtmetall vanno tracciate nello stesso audit trasversale, ma non si dichiarano risolte con il controllo del tipo documento.

## Confini e stato

- [x] Audit del campione e dei punti del codice.
- [x] Piano scritto.
- [x] OK di Silvano per implementare Impol: «commitpush e poi procedi con impol».
- [x] Correzioni locali e campioni aggiuntivi.
- [x] Test automatici di normalizzazione, evidenze e regressioni; controlli visivi dei campioni.
- [x] Commit/push richiesto anche per Impol durante la lavorazione.
- [ ] Prova AI reale con le nuove immagini e caricamento completo su dati di test.
- [ ] Deploy Alpha, solo dopo richiesta separata e secondo MD.

Il controllo AI DDT/certificato rimane per ora limitato a Leichtmetall. Nessuna estensione automatica a Impol o agli altri fornitori. Nessuna modifica Alpha, agli originali, allo storico, ai match confermati, a KPI o Registro.

## Esito implementazione locale

### Maschere certificati

`impol_masking.py` sostituisce il rettangolo fisso del percorso certificato. Riconosce intestazione e confine dei campi ordine via OCR; dentro le aree del layout conosciuto usa i confini effettivi dell'inchiostro, con margine limitato. Copre indirizzo cliente, logo/recapiti fornitore, nomi dei timbri, pannelli firme e dati societari a piè pagina. Conserva titolo, numero certificato, campi ordine, dati tecnici e dichiarazioni ISO/conformità all'ordine.

Nel layout 17126/a il controllo visivo ha rilevato intestazione spostata e firme vicine alla dichiarazione: corretti i limiti superiore/inferiore e aggiunto un test di regressione. Si tratta di un profilo Impol ancorato, non di un riconoscitore universale per qualsiasi impaginazione. Se mancano gli ancoraggi o un'area da oscurare si sovrappone a un campo tecnico riconosciuto, errore esplicito prima della chiamata AI. Nessun retry automatico per questo errore. Nessuna nuova finestra di approvazione maschere introdotta.

DDT Impol e maschere degli altri fornitori non modificati. Nessuna bonifica automatica delle vecchie immagini derivate; i nuovi ritagli vengono rigenerati nel percorso di lettura certificato.

### Provenienza note e richiamo requisiti

`impol_evidence.py` confronta le citazioni già estratte dall'AI con testo PDF/OCR delle pagine. Nessuna modifica al prompt, al modello o alle regole di estrazione. L'OCR serve soltanto per localizzare la frase, non per sostituire il valore letto dall'AI.

- Associazione solo se la citazione è individuata su un'unica pagina; citazioni unite da `|` devono risultare tutte sulla stessa pagina.
- Tolleranza di una sola sostituzione OCR in frasi lunghe almeno 40 caratteri; numeri e classe A/B devono coincidere. Esempio reale: `STD` letto dall'OCR come `STO`.
- Se assente, ripetuta, troppo breve o non verificabile: pagina nulla, testo ed esito tecnico invariati. Non si assegna più l'ultima pagina per ipotesi.
- Implicazione LST00 → classe B invariata, ma localizzata prima che un consumatore possa riattribuirla per fallback alla prima pagina.
- Persistenza nello schema esistente: `document_page_id = NULL`, tipo evidenza `testo_pagina_da_verificare`. Nessuna migrazione DB.
- Avviso giallo tenue in Note e sul richiamo requisiti quando il valore corrente non confermato ha provenienza incerta. Evidenze vecchie non più referenziate non mantengono avvisi; le evidenze senza pagina non generano sovrapposizioni grafiche su una pagina inventata.

### Verifiche

- Quattro PDF locali: 1505/a (2 pagine), 10341 (2), 1505/c (2), 17126/a (1). Rendering e verifica visiva di tutte le sette pagine; ordine fornitore e contenuto tecnico leggibili nelle copie mascherate.
- Test maschere su scale differenti, traslazione, ancoraggi mancanti, layout alto e firme basse; originali non modificati.
- Test note su pagina 1/2, citazioni ripetute, mancanti, aggregate, OCR incompleto, classe/numero diverso, implicazione LST00 e salvataggio con pagina nulla; note confermate protette.
- Rielaborate localmente le quattro risposte AI Impol già salvate nella valutazione precedente: mantenuti CDQ `1505/a`, undici valori chimici, tre righe meccaniche, classe B presente e A sulle estremità esclusa, RoHS presente. Classe B e richiamo LST00 localizzati alla pagina 1 in tutte. RoHS localizzato alla pagina 1 in due risposte; nelle altre due citazione/OCR non concordano abbastanza e viene correttamente richiesto il controllo della pagina, senza cambiare l'esito RoHS.
- Test frontend della visibilità dell'avviso e build Vite. Avvisi non bloccanti: database Browserslist datato e dimensione bundle; nessun aggiornamento dipendenze fuori ambito.
- Suite backend completa: **296 test superati**, 7 avvisi di deprecazione; 2 test frontend superati; build Vite completata. `git diff --check` senza errori di whitespace.

### Limiti prima del rilascio

Nessuna nuova chiamata AI a pagamento: budget invariato. La leggibilità visiva dell'ordine ora scoperto non equivale a una nuova prova di estrazione AI di quel valore. Non eseguito ciclo completo upload → conferme → Word/PDF su database aziendale né collaudo UI interattivo. Layout ruotati/degradati o diversi dai campioni richiedono ulteriori prove; gli errori espliciti vanno gestiti mediante verifica del documento, senza allargare automaticamente le maschere. Nessun deploy Alpha eseguito.
