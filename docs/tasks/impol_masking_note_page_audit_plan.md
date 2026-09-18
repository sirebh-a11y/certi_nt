# Impol — piano correzioni mascheramento e pagina delle note

Data: 18 settembre 2026. **Solo audit e proposta: implementazione da autorizzare.**

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
- [ ] OK di Silvano per implementare Impol.
- [ ] Correzioni locali e campioni aggiuntivi.
- [ ] Test di estrazione, evidenze e regressioni del percorso applicativo.
- [ ] Approvazione, commit/push e deploy separatamente richiesti.

Il controllo AI DDT/certificato rimane per ora limitato a Leichtmetall. Nessuna estensione automatica a Impol o agli altri fornitori. Nessuna modifica Alpha, agli originali, allo storico, ai match confermati, a KPI o Registro.
