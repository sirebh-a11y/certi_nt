# Ereditarieta Word per lavorazioni CodF3

Questo documento confronta la regola attuale con la regola proposta per il Word del certificato materiale, seconde pagine e PDF allegati.

## Regola attuale

Oggi il raw resta la fonte principale.

Quando una lavorazione nuova deve creare o scaricare il Word, l'app cerca prima il Word del raw. Se il raw esiste ed e valido, la lavorazione eredita da lui, anche se una lavorazione intermedia e stata modificata.

Schema:

```text
Raw
 |
 +--> 30
 |
 +--> 40
 |
 +--> 50
 |
 +--> 60
```

Esempio:

```text
Raw = seconda pagina + allegati A + B
30  = eredita Raw: A + B
40  = eredita Raw, poi utente modifica: A + C
50  = eredita ancora Raw: A + B
60  = eredita ancora Raw: A + B
```

Quindi la modifica fatta su 40 non passa automaticamente a 50 e 60.

Caso sporco:

```text
Raw senza Word valido
30 con Word
40 con Word manuale
50 nuova
```

In questo caso 50 puo ereditare da 40, perche il raw non e disponibile. Questo non dovrebbe essere il flusso normale.

Punti positivi:

- Il raw resta una base stabile.
- Una modifica errata su una lavorazione non si propaga facilmente.

Punti deboli:

- Se l'utente modifica 40 pensando che 50 segua quella modifica, oggi non succede.
- L'ereditarieta non segue la sequenza naturale delle lavorazioni.
- Serve guardare bene la fonte mostrata in UI per capire da dove arriva il Word.

## Regola proposta

Ogni nuova lavorazione eredita dalla lavorazione precedente piu vicina gia esistente e valida.

Il raw e la base iniziale, ma non resta sempre la fonte principale.

Schema:

```text
Raw -> 30 -> 40 -> 50 -> 60 -> 70
```

Esempio 1:

```text
Raw = seconda pagina + allegati A + B
30  = eredita Raw: A + B
40  = eredita 30, poi utente modifica: A + C
50  = nuova, eredita 40: A + C
```

Esempio 2:

```text
Raw = A + B
30  = A + B
40  = A + C
50  = A + C
60  = gia generata prima, resta A + B
70  = nuova, eredita 60: A + B
```

La regola importante e: una lavorazione gia generata non viene riscritta.

Quindi se 60 esiste gia, 70 eredita da 60, anche se 40 era stata modificata.

## Casi pratici

### Caso A: modifica su lavorazione intermedia

```text
Raw: A + B
30: eredita Raw
40: utente rimuove B e aggiunge C
50: non ancora generata
```

Regola attuale:

```text
50 = A + B
```

Regola proposta:

```text
50 = A + C
```

### Caso B: lavorazione gia generata

```text
Raw: A + B
30: A + B
40: A + C
50: A + C
60: gia generata con A + B
70: nuova
```

Regola proposta:

```text
60 resta A + B
70 eredita 60, quindi A + B
```

### Caso C: utente vuole tornare al raw

Con la regola proposta, se una lavorazione precedente ha modifiche, le successive ereditano da quella.

Per tornare al raw servirebbe una scelta esplicita futura, per esempio:

```text
Ripristina da raw
```

Oppure l'utente modifica manualmente il Word e lo ricarica.

### Caso D: PDF allegati

Gli allegati seguono la stessa logica della fonte Word.

Regola attuale:

```text
Nuova lavorazione -> allegati del raw, se raw disponibile
```

Regola proposta:

```text
Nuova lavorazione -> allegati della lavorazione precedente valida
```

## Messaggio utile in UI

Per evitare confusione, la pagina dovrebbe sempre mostrare la fonte:

```text
Word ereditato da 7000_00_40/26
Allegati ereditati da 7000_00_40/26
```

Oppure:

```text
Word generato sul raw
Allegati specifici di questa lavorazione
```

## Decisione da prendere

La regola attuale e piu prudente ma meno naturale.

La regola proposta e piu coerente con il lavoro dell'utente:

```text
una nuova lavorazione eredita dalla precedente gia esistente
```

Prima di implementarla bisogna decidere se aggiungere anche un comando esplicito:

```text
Ripristina da raw
```

Questo servirebbe nei casi in cui una lavorazione successiva non deve seguire le modifiche della precedente.
