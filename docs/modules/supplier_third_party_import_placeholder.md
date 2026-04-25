# Supplier Third-Party Import Placeholder

## Stato
- Placeholder creato il 25/04/2026.
- Tema aperto: importare o riallineare la tabella `fornitori` partendo da un DB terzo o da una nuova rigenerazione seed.

## Problema reale
Oggi il sistema usa due livelli diversi:

1. **relazioni DB**
- `documenti`
- `righe acquisition`
- `match`
- collegati tramite `fornitore_id`

2. **logica supplier-specific**
- parser
- split righe
- AI
- masking
- overlay
- match fields

Questa seconda parte oggi si attiva soprattutto tramite:
- `ragione_sociale`
- alias
- `resolve_supplier_template(...)`

Quindi il rischio vero non e solo cambiare un `id`.
Il rischio vero e anche cambiare nome/alias in modo che il supplier-specific non venga piu risolto correttamente.

## Situazioni a rischio

### 1. Rinominare un fornitore gia esistente
Esempio:
- `Impol d.o.o.` -> altro nome piu commerciale

Effetto:
- i legami DB possono restare validi
- ma il flusso supplier-specific puo degradare se nome e alias non matchano piu il template

### 2. Rigenerare la lista fornitori su una nuova installazione
Oggi il bootstrap:
- semina i fornitori da CSV solo se la tabella e vuota
- semina gli alias solo se la tabella alias e vuota

Effetto:
- installazioni diverse possono avere nomi leggermente diversi
- se i nomi seeded non restano coerenti con i template, alcuni flussi fornitore possono non attivarsi

### 3. Importare da un DB terzo con `id` diversi
Questo e il caso piu pericoloso.

Effetto:
- `fornitore_id` su documenti e righe puo puntare al fornitore sbagliato
- quindi si puo attivare il parser sbagliato, oppure fallire il match

### 4. Importare una tabella fornitori con struttura diversa
Se arrivano:
- colonne diverse
- nomi diversi
- alias assenti

allora il bootstrap o il mapping attuale non bastano da soli.

## Cosa tenere fermo
- non fidarsi mai degli `id` di un DB terzo
- non rinominare i fornitori supplier-specific senza alias equivalenti
- non trattare `ragione_sociale` come chiave tecnica stabile

## Prevenzione minima
Quando si affronta questo tema:

1. fare mapping per:
- nome canonico
- alias

2. verificare per ogni fornitore supplier-specific:
- nome attuale
- alias attivi
- template risolto

3. testare almeno:
- `Impol`
- `Neumann`
- `AWW`
- `Aluminium Bozen`
- `Metalba`
- `Leichtmetall`

## Hardening consigliato
La soluzione robusta da valutare e introdurre nel DB un campo stabile tipo:
- `supplier_key`

Esempi:
- `impol`
- `neuman`
- `aww`
- `aluminium_bozen`

Obiettivo:
- separare il nome utente dalla chiave tecnica del flusso supplier-specific

## Domande da riaprire quando affronteremo il tema
1. L'import da DB terzo deve:
- sostituire
- fondere
- oppure solo mappare i fornitori esistenti?

2. Il bootstrap CSV deve diventare:
- seed una tantum
- oppure upsert controllato?

3. Introduciamo `supplier_key` nel DB prima dell'import, oppure gestiamo prima solo mapping nome/alias?

## Riferimento operativo
Quando riapriamo questo tema, partire da qui:

`docs/modules/supplier_third_party_import_placeholder.md`

