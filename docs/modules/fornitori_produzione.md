# Fornitori - passaggio in produzione

## Regola

Il DB locale deve contenere solo i fornitori gestiti da Certi.

I 9 fornitori speciali sono locali e hanno:

- dati anagrafici locali usati dall'app;
- alias usati per riconoscimento documenti;
- `reader_template_key` stabile;
- collegamento eSolver in `fornitori_esolver_link`.

eSolver arricchisce i dati, ma non sostituisce le regole locali di lettura.

## Fornitori speciali iniziali

- Aluminium Bozen S.r.l. -> `aluminium_bozen`
- Aluminium-Werke Wutöschingen AG & Co. KG -> `aww`
- Arconic Extrusions Hannover GmbH -> `arconic_hannover`
- Grupa Kety S.A. -> `grupa_kety`
- Impol d.o.o. -> `impol`
- Leichtmetall Aluminium Giesserei Hannover GmbH -> `leichtmetall`
- Metalba S.p.A. -> `metalba`
- Neuman Aluminium Austria GmbH -> `neuman`
- Zeeland Aluminium Company -> `zalco`

## Nuovo DB produzione

All'avvio, il seed crea questi 9 fornitori e collega i dati eSolver noti.

Non devono essere importati fornitori generici nel DB locale.

## DB gia popolato

Prima del passaggio in produzione:

1. fare backup DB;
2. verificare documenti, righe incoming e storico collegati ai fornitori extra;
3. mantenere i 9 speciali;
4. rimuovere solo fornitori extra senza dipendenze operative;
5. se un fornitore extra ha dipendenze operative, decidere manualmente se archiviarlo o mantenerlo come standard.

Non fare cancellazioni automatiche all'avvio.

Audit non distruttivo:

```bash
docker compose exec -T backend python scripts/audit_suppliers_production.py
```

Il report indica per ogni fornitore se e core, quanti documenti/righe incoming sono collegati e se e rimovibile o da valutare manualmente.

## Aggiornamento dati eSolver

La pagina fornitori espone un'azione admin per aggiornare i fornitori gia collegati a eSolver.

L'aggiornamento modifica solo `fornitori_esolver_link`:

- nome eSolver;
- codice alternativo;
- P.IVA/codice fiscale eSolver;
- indirizzo, citta, nazione, email, telefono eSolver;
- data ultimo sync.

Non modifica:

- ragione sociale locale;
- alias;
- `reader_template_key`;
- regole di lettura, mascheramento e match.

## Nuovi fornitori da eSolver

Un admin puo aggiungere in app un fornitore presente in eSolver.

Il fornitore entra come standard:

- visibile nella lista locale;
- collegato a eSolver;
- senza `reader_template_key`;
- senza parser speciale.

Diventa speciale solo quando vengono sviluppate e assegnate regole dedicate di lettura, mascheramento e match.

## Controlli prima di go-live

- i 9 fornitori hanno `reader_template_key`;
- i 9 fornitori hanno link eSolver;
- il riconoscimento documenti usa prima `reader_template_key`;
- caricamento DDT/certificati funziona sui 9 fornitori;
- mascheramento/crop AI funziona sui 9 fornitori;
- nessun fornitore extra rimane nel DB locale senza decisione esplicita.
