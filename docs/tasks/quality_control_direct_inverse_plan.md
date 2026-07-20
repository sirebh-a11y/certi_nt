# Indicatore controllo Diretta / Inversa

## Stato

Requisiti funzionali confermati e implementazione locale completata. In attesa di eventuale commit, push e aggiornamento esplicitamente richiesti dall'utente.

Questo documento descrive il piano e i test. Non rappresenta un'implementazione approvata e non autorizza modifiche al codice applicativo.

## Richiesta

Aggiungere a ogni riga materiale un indicatore esclusivo:

- `Diretta`
- `Inversa`

L'indicatore deve poter essere scelto durante il controllo del materiale e deve essere disponibile anche nell'Excel esportato dalla pagina KPI fornitori.

## Audit dell'applicazione attuale

La decisione finale sul materiale viene presa nella pagina Incoming, nel riquadro **Valutazione qualità**, insieme alla nota valutazione e ai pulsanti:

- Accettato
- Accettato con riserva
- Respinto

La pagina **Conformità e valutazione fornitori** mostra le righe con match confermato e consente attualmente di gestire le date. Valutazione e nota sono visualizzate ma derivano dal flusso Incoming.

L'Excel KPI contiene fogli di sintesi e un foglio di dettaglio per ciascun fornitore. Nei fogli di dettaglio sono già presenti `Data richiesta`, `Valutazione` e `Note`.

## Proposta per il video

### Punto principale di scelta

Inserire la scelta nel riquadro **Valutazione qualità** della riga Incoming, vicino alla nota valutazione e prima dei pulsanti finali.

Visualizzazione proposta:

```text
Tipo controllo
[ Diretta ] [ Inversa ]
```

Si propone un unico controllo a scelta esclusiva, non due checkbox indipendenti, per impedire che Diretta e Inversa risultino selezionate contemporaneamente.

### Comportamento proposto

- Selezionare Diretta/Inversa non deve cambiare lo stato qualità della riga.
- La scelta deve essere persistente e ritrovata dopo uscita o aggiornamento della pagina.
- Se l'utente seleziona un valore e preme immediatamente Accettato/Riserva/Respinto, deve essere usata l'ultima scelta.
- La scelta è obbligatoria prima di Accettato, Accettato con riserva o Respinto.
- Dopo la valutazione finale il valore è bloccato.
- In caso di riapertura forzata della valutazione, il valore torna modificabile.

### Pagina Conformità e valutazione fornitori

Aggiungere una colonna **Tipo controllo** nella posizione:

```text
Data richiesta | Tipo controllo | Valutazione | Note
```

Valori visualizzati:

- `Diretta`
- `Inversa`
- `Da indicare` per una riga senza valore

Il campo dovrebbe essere incluso nella ricerca libera e nell'ordinamento della griglia.

In questa pagina il campo è soltanto visualizzato e non è modificabile. La fonte della scelta rimane la valutazione della riga Incoming.

## Proposta per l'Excel

In ogni foglio di dettaglio fornitore aggiungere la colonna **Tipo controllo** dopo `Data richiesta` e prima di `Valutazione`:

```text
Data richiesta | Tipo controllo | Valutazione | Note
```

Contenuto della cella:

- `Diretta`
- `Inversa`
- cella vuota per le righe storiche senza classificazione

La proposta non modifica:

- foglio `Sintesi periodo`;
- foglio `Fornitori`;
- foglio `Mesi`;
- calcoli KPI;
- conteggi Accettati/Riserva/Respinti;
- ritardo medio;
- tempo medio di controllo.

Non sono richiesti conteggi separati Diretta/Inversa nei fogli riepilogativi.

## Proposta dati e API

Campo applicativo proposto:

```text
qualita_tipo_controllo
```

Caratteristiche:

- tipo database testuale breve e nullable;
- valori ammessi: `diretta`, `inversa`;
- `null` per righe storiche o non ancora classificate;
- validazione API per rifiutare valori diversi;
- esposizione nella risposta della riga Incoming e della riga qualità;
- possibilità di includerlo nella richiesta di valutazione finale, per non perdere una scelta effettuata immediatamente prima del pulsante.

Si propone un campo enumerato anziché un booleano, perché rende espliciti i valori e gestisce correttamente lo stato iniziale non ancora indicato.

## Piano di implementazione

1. Aggiungere `qualita_tipo_controllo` al modello della riga Incoming.
2. Aggiungere l'aggiornamento compatibile della struttura database.
3. Esporre e validare il campo negli schemi API.
4. Gestire salvataggio e storico della modifica nel servizio qualità.
5. Inserire il selettore nella valutazione Incoming.
6. Rendere la scelta obbligatoria e includere l'ultima selezione nella valutazione finale.
7. Mostrare la colonna nella pagina Conformità e valutazione fornitori.
8. Mantenere il campo in sola lettura nella pagina Conformità e includerlo in ricerca e ordinamento.
9. Aggiungere la colonna a ogni foglio Excel di dettaglio fornitore.
10. Verificare che sintesi e KPI non cambino.

## Regole che non devono cambiare

- Selezionare Diretta/Inversa non accetta né respinge automaticamente la riga.
- Accettato con riserva e Respinto continuano a richiedere la nota.
- Accettato continua a seguire la regola attuale sulla nota facoltativa.
- La data di accettazione continua a essere valorizzata secondo la logica attuale.
- Nessuna modifica a chimica, proprietà, note tecniche, match o registro certificazione.
- Nessuna modifica ai conteggi e alle formule KPI, salvo futura richiesta esplicita.

## Test previsti

### Persistenza e flusso

- Seleziono Diretta, esco e rientro: Diretta è presente.
- Seleziono Inversa, aggiorno la pagina: Inversa è presente.
- Seleziono Diretta e premo subito Accettato: viene salvata Diretta.
- Seleziono Inversa e premo subito Riserva/Respinto: viene salvata Inversa.
- Accettato/Riserva/Respinto senza Diretta/Inversa restano bloccati.
- La sola selezione non modifica lo stato qualità.
- Un valore API diverso da Diretta/Inversa viene rifiutato.

### Chiusura e riapertura

- Dopo la valutazione finale il campo è visibile ma non modificabile.
- Dopo la riapertura forzata il campo torna modificabile.
- Riserva/Respinto senza nota restano bloccati.

### Pagina Conformità

- La colonna visualizza Diretta/Inversa correttamente.
- Le righe storiche senza valore mostrano `Da indicare`.
- Ricerca e ordinamento includono il nuovo campo.
- Il campo non è modificabile dalla griglia Conformità.

### Excel

- La colonna `Tipo controllo` è nella posizione prevista in ogni foglio di dettaglio fornitore.
- Diretta e Inversa vengono esportate con etichetta leggibile.
- Le righe storiche producono una cella vuota.
- Chimica e proprietà restano allineate alle intestazioni successive.
- I fogli di sintesi e i calcoli KPI restano invariati.

### Regressione

- Suite backend completa.
- Build frontend.
- Nessuna modifica agli stati Incoming.
- Nessuna modifica ai KPI o al registro certificazione.

## Decisioni confermate

1. **Obbligatorietà**: Diretta/Inversa è obbligatorio prima di Accettato/Riserva/Respinto.
2. **Blocco dopo chiusura**: dopo la valutazione finale il campo è bloccato; torna modificabile soltanto tramite Forza riapertura.
3. **Pagina Conformità**: il campo è soltanto visualizzato e non è modificabile dalla griglia.
4. **Excel**: la colonna è presente in ogni foglio di dettaglio fornitore; non vengono aggiunti conteggi Diretta/Inversa nei fogli di sintesi.

## Esito implementazione locale

- Campo, API, selettore Incoming, blocco dopo valutazione e riapertura implementati.
- Colonna in sola lettura nella pagina Conformità implementata con ricerca e ordinamento.
- Colonna aggiunta a ogni foglio Excel di dettaglio fornitore.
- Test backend mirati superati: 28.
- Build frontend superata.
- Nessun aggiornamento dell'ambiente, commit o push eseguito senza richiesta esplicita.
