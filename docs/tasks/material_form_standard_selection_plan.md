# Forma materiale e proposta standard

## Stato

- Audit completato in locale il 30/07/2026.
- Catalogo standard verificato anche su Alpha il 30/07/2026.
- Implementazione eseguita in locale dopo conferma esplicita dell'utente.
- Test backend, build frontend e prove AI completati.
- Nessun deploy Alpha eseguito per questa modifica.

## Obiettivo

Usare la forma reale del materiale per migliorare:

- l'avviso nella Valutazione qualità;
- la proposta standard durante la conferma di Chimica;
- la proposta standard durante la conferma delle Proprietà;
- la proposta standard nella pagina Certificazione.

La proposta non sostituisce la decisione dell'utente: lo standard deve sempre essere scelto e confermato dall'utente.

## Decisioni confermate

1. `Billets casted` indica billetta.
2. `Casted logs`, senza un riferimento esplicito a billet/billetta, resta `Materiale da verificare`.
3. Le note relative agli ultrasuoni non devono determinare la forma del materiale.
4. Per la billetta l'app non crea e non assegna automaticamente uno standard dedicato: propone gli standard più verosimili e decide l'utente.
5. Se la forma è da verificare, la scelta manuale dello standard deve restare possibile.
6. Se un OL contiene indicazioni diverse, l'app propone lo standard più verosimile, mostra le differenze e lascia la scelta all'utente.
7. Non devono essere eseguiti ricalcoli o correzioni automatiche sui dati storici.

## Audit sintetico

Oggi esistono logiche separate per:

- avviso barra/billetta in Incoming;
- controllo visivo dello standard in Chimica e Proprietà;
- proposta standard in Certificazione.

Le due logiche standard non usano in modo completo la descrizione prodotto letta dall'AI e non riconoscono la billetta. Quando la forma non viene individuata, possono comunque proporre uno standard `BARRE` usando lega e diametro.

Il catalogo locale non è allineato al catalogo Alpha. Nel database locale risultano:

- 25 senza tipo prodotto, considerando anche standard non attivi;
- 1 `BARRE`;
- 1 `PROFILI`;
- nessuno `BILLETTE`.

Su Alpha risultano invece:

- 25 standard attivi `BARRE`;
- 1 standard attivo scritto `BILLETTA`;
- 5 standard attivi scritti `BILLETTE`;
- 1 ulteriore standard `BILLETTE` in bozza;
- 1 standard attivo `PROFILI`;
- 2 standard attivi senza tipo prodotto.

`BILLETTA` e `BILLETTE` devono essere considerati lo stesso tipo. Non esiste su Alpha un tipo standard `ESTRUSO`: estruso descrive una lavorazione e, senza un nome prodotto, non permette di distinguere una barra da un profilo.

Sono stati inoltre trovati due OL locali Zalco, collegati a documenti che riportano `billets`, con standard `6082 - BARRE` già confermato. Sono bozze e non PDF finali.

## Classificazione comune da introdurre

Tutte le pagine dovranno usare lo stesso risultato:

- `BILLETTE`
- `BARRE`
- `PROFILI`
- `ESTRUSO_GENERICO`
- `DA_VERIFICARE`
- `DATI_DISCORDANTI`

Esempi:

| Testo prodotto | Risultato |
|---|---|
| `Billets casted, homogenized and turned` | `BILLETTE` |
| `Aluminium roundbars (billets), cast, homogenized and scalped` | `BILLETTE` |
| `Extruded round bar produced from aluminium billet` | `BARRE` |
| `Casted logs, rough surface` | `DA_VERIFICARE` |
| `Rundstange 35,00` | `BARRE` |
| `Round bar` / `Barra tonda` | `BARRE` |
| `Profile` / `Profilo` | `PROFILI` |
| solo nota `US-Inspection on billets` | `DA_VERIFICARE` |

`Diretta` e `Inversa` indicano il metodo di estrusione ma non distinguono, da sole, barra da profilo. La scelta manuale `Non applicabile - billetta` è invece un'indicazione esplicita dell'utente.

Quando nella stessa descrizione compaiono sia `roundbar` sia `billet`, conta il processo:

- materiale `cast`, `homogenized`, `scalped` o esplicitamente definito `roundbars (billets)` è billetta cilindrica;
- una `extruded round bar` prodotta a partire da una billetta è invece una barra finita;
- senza un contesto sufficiente il dato resta discordante, non viene deciso automaticamente.

Nel confronto con gli standard:

- la classificazione interna `BILLETTE` deve trovare sia gli standard scritti `BILLETTA` sia quelli scritti `BILLETTE`;
- `ESTRUSO_GENERICO` non deve essere trasformato automaticamente in `BARRE` o `PROFILI`;
- `DA_VERIFICARE` e `DATI_DISCORDANTI` non impediscono la scelta manuale dello standard.

## Piano di implementazione attuale

Le fasi seguenti sono state implementate in locale il 30/07/2026.

### Fase 1 - Descrizione prodotto AI

Estendere prompt, JSON e normalizzazione dei fornitori interessati affinché venga conservata la descrizione prodotto reale:

- Aluminium Bozen, percorso DDT;
- Leichtmetall, DDT e certificato;
- AWW, percorso DDT;
- Grupa Kety, DDT e certificato;
- Zalco, DDT e certificato.

Per Arconic utilizzare anche `item_description_raw`.

Impol, Metalba e Neuman devono restare invariati salvo test di regressione.

### Fase 2 - Classificazione condivisa

Creare un solo classificatore della forma materiale e utilizzarlo sia nell'avviso della Valutazione sia nei due percorsi standard.

Il classificatore deve:

- conservare testo, fonte ed evidenza;
- ignorare le note UT;
- non dedurre billetta dal solo fornitore, dalla lega o dal diametro;
- distinguere barra, profilo ed estruso generico;
- segnalare descrizioni realmente discordanti.

### Fase 3 - Proposta standard in Chimica e Proprietà

Sostituire la selezione attuale con una proposta ordinata considerando:

1. lega;
2. variante;
3. forma materiale;
4. trattamento;
5. diametro o spessore.

La forma materiale deve essere confrontata così:

- `BARRE` con standard `BARRE`;
- `BILLETTE` con standard `BILLETTA` o `BILLETTE`;
- `PROFILI` con standard `PROFILI`;
- `ESTRUSO_GENERICO`, `DA_VERIFICARE` e `DATI_DISCORDANTI` senza assegnare automaticamente un tipo standard.

Gli standard senza tipo prodotto restano candidati in base a lega, variante, trattamento e misura.

La finestra deve mostrare:

- standard più probabile;
- attendibilità;
- motivi;
- eventuali incertezze.

La conferma manuale deve restare possibile anche per billetta, forma incerta o dati discordanti.

### Fase 4 - Proposta standard in Certificazione

Usare lo stesso motore della Fase 3.

Per OL con più righe:

- calcolare la compatibilità complessiva;
- proporre lo standard più verosimile;
- indicare quante righe sono coerenti, incerte o discordanti;
- mostrare alternative;
- richiedere sempre la conferma dell'utente.

La selezione manuale completa degli standard deve restare disponibile.

### Fase 5 - Coerenza del flusso corrente

Dopo la conferma dell'utente, lo standard scelto continua a governare:

- confronto di Chimica e Proprietà;
- conformità;
- conferma rapida da Certificazione;
- contenuto di Word e PDF.

Non vengono introdotti nuovi controlli successivi, riconferme automatiche o blocchi aggiuntivi.

## Sviluppo futuro escluso

Non implementare ora il controllo dello standard dopo modifiche successive dei dati.

L'idea resta documentata per una valutazione futura:

- memorizzare la forma materiale presente al momento della conferma dello standard;
- rilevare eventuali cambi successivi;
- chiedere una riconferma prima di conferma rapida, nuovo Word o PDF.

Questa funzione è rinviata perché introdurrebbe nuove dipendenze e blocchi nel flusso attuale.

## Rischi da evitare

- classificare come billetta una semplice nota UT;
- classificare `Casted logs` automaticamente come billetta o barra;
- usare uno standard `BARRE` come scelta automatica certa quando la forma è incerta;
- confondere Diretta/Inversa con Barra/Profilo;
- cambiare automaticamente uno standard già confermato;
- modificare stati, match, chimica, proprietà, note o valutazioni esistenti;
- modificare Word o PDF già creati;
- creare nuovi standard billetta quando quelli necessari sono già presenti su Alpha;
- trattare `BILLETTA` e `BILLETTE` come tipi diversi;
- trattare `ESTRUSO_GENERICO` come sinonimo automatico di `BARRE`;
- proporre una variante lega senza evidenza reale;
- usare standard diversi tra Incoming e Certificazione per gli stessi dati.

## Test obbligatori

1. Matrice testi: billet, casted logs, barra, Rundstange, profilo, estruso generico e note UT.
2. Verifica dedicata per ogni fornitore interessato.
3. Stessa proposta standard in Chimica, Proprietà e Certificazione.
4. Billetta senza standard dedicato: proposta possibile, nessuna scelta automatica, decisione utente.
5. Billetta con standard Alpha scritto `BILLETTA`: candidato riconosciuto.
6. Billetta con standard Alpha scritto `BILLETTE`: candidato riconosciuto.
7. Estruso generico: nessuna conversione automatica in barra o profilo.
8. `Casted logs`: materiale da verificare e scelta manuale consentita.
9. OL con righe diverse: proposta ordinata e differenze visibili.
10. Standard discordante scelto manualmente: scelta consentita e chiaramente presentata.
11. Standard senza tipo prodotto: candidato valutato con gli altri criteri.
12. Nessuna regressione per Impol, Metalba e Neuman.
13. Nessuna modifica automatica allo storico e ai PDF finali.
14. Test completi su conformità, conferma rapida, Word e PDF dopo la scelta dello standard.

## Esito verifiche del 30/07/2026

- Test automatici backend: `244 passed`.
- Test specifici nuovi su forme, alias `BILLETTA/BILLETTE`, ranking, casi misti, OCR e parser: `12 passed`.
- Build frontend: completata.
- `git diff --check`: completato senza errori.

Sono state eseguite 7 chiamate AI riuscite e 1 tentativo fallito per errore temporaneo HTTP 520 del servizio, quindi 8 tentativi totali sui 10 autorizzati.

Costo conservativo stimato delle 7 chiamate riuscite: circa 0,43 USD, sotto il limite di 2 USD.

Documenti provati:

| Fornitore e percorso | Descrizione restituita | Forma |
|---|---|---|
| Leichtmetall DDT | `Aluminium roundbars (billets) ... cast, homogenized and scalped` | `BILLETTE` |
| Leichtmetall certificato | `Billets casted, homogenized and turned` | `BILLETTE` |
| Grupa Kety DDT | `Extruded Round Bar 44.00 ...` | `BARRE` |
| Grupa Kety certificato | `Extruded bar` | `BARRE` |
| Zalco DDT | `billets` | `BILLETTE` |
| Zalco certificato | `billets` | `BILLETTE` |
| AWW DDT | `Rundstange 35,00` / `Rundstange 43,00` | `BARRE` |

Il confronto con le righe locali già salvate ha confermato che CDQ, lega, diametro, colata, DDT, peso e ordine sono rimasti coerenti. Per i certificati verificati sono rimaste coerenti anche chimica, proprietà e note.

Verifica aggiuntiva sulla riga locale 91:

- il vecchio payload AI non conteneva la descrizione prodotto;
- il PDF/OCR riporta `Aluminium roundbars (billets) in alloy 2024, cast, homogenized and scalped`;
- il fallback OCR limitato alla frase prodotto la classifica `BILLETTE`;
- semplici note `US inspection on billets`, `ends of bars` o l'intestazione `No. of Billets` non attivano il fallback.
