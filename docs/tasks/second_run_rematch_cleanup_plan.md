# Procedura pulizia parziale e test second run rematch

Scopo: preparare un test pulito del rematch automatico cross-run. Il test deve verificare che un DDT caricato in un primo run venga agganciato automaticamente a un certificato arrivato in un secondo run, senza intervento utente, quando i campi ponte coincidono.

Regola operativa: non avviare AI/Vision senza consenso esplicito dell'utente, dopo stima costo e lista PDF.

## Stato contaminato da pulire

Il DB attuale contiene test gia eseguiti che falserebbero il second run:

- Run contaminanti: `71`, `72`.
- Documenti contaminanti: `1029`-`1050`.
- Righe contaminanti: `864`-`883`.
- Caso specifico gia falsato: Bozen `147344` e gia stato agganciato dal run `72`, quindi non puo piu provare "certificato arrivato dopo" finche non si pulisce.

Prima di cancellare, verificare sempre che questi ID corrispondano ancora ai file attesi. Se nel frattempo sono stati fatti altri run, non usare questa procedura alla cieca.

## Backup obbligatorio

Prima della pulizia:

```powershell
New-Item -ItemType Directory -Force backups
docker compose exec -T postgres pg_dump -U certi_nt -d certi_nt > backups\certi_nt_before_second_run_rematch.dump
git status --short
git rev-parse HEAD
```

Non procedere se ci sono run attivi:

```sql
SELECT id, stato, fase_corrente, current_row_id, current_document_name
FROM acquisition_processing_runs
WHERE stato IN ('in_coda', 'in_esecuzione');
```

## Dry-run pulizia

Eseguire prima questi controlli. Se escono riferimenti esterni ai set da pulire, fermarsi.

```sql
WITH cleanup_rows AS (
  SELECT generate_series(864, 883) AS id
),
cleanup_docs AS (
  SELECT generate_series(1029, 1050) AS id
)
SELECT 'rows' AS scope, count(*) FROM datimaterialeincoming WHERE id IN (SELECT id FROM cleanup_rows)
UNION ALL
SELECT 'docs', count(*) FROM documenti_fornitore WHERE id IN (SELECT id FROM cleanup_docs)
UNION ALL
SELECT 'runs', count(*) FROM acquisition_processing_runs WHERE id IN (71, 72)
UNION ALL
SELECT 'read_values', count(*) FROM valori_letti_acquisition WHERE acquisition_row_id IN (SELECT id FROM cleanup_rows)
UNION ALL
SELECT 'evidences', count(*) FROM documenti_evidenze
WHERE acquisition_row_id IN (SELECT id FROM cleanup_rows) OR document_id IN (SELECT id FROM cleanup_docs)
UNION ALL
SELECT 'matches', count(*) FROM match_certificato
WHERE acquisition_row_id IN (SELECT id FROM cleanup_rows) OR document_certificato_id IN (SELECT id FROM cleanup_docs);
```

Controllo anti-danno:

```sql
WITH cleanup_rows AS (
  SELECT generate_series(864, 883) AS id
),
cleanup_docs AS (
  SELECT generate_series(1029, 1050) AS id
)
SELECT 'row_outside_refs_doc' AS risk, id, document_ddt_id, document_certificato_id
FROM datimaterialeincoming
WHERE id NOT IN (SELECT id FROM cleanup_rows)
  AND (document_ddt_id IN (SELECT id FROM cleanup_docs)
       OR document_certificato_id IN (SELECT id FROM cleanup_docs))
UNION ALL
SELECT 'match_outside_refs_doc', acquisition_row_id, NULL, document_certificato_id
FROM match_certificato
WHERE acquisition_row_id NOT IN (SELECT id FROM cleanup_rows)
  AND document_certificato_id IN (SELECT id FROM cleanup_docs);
```

Atteso: il controllo anti-danno deve restituire zero righe.

## Pulizia parziale

Eseguire solo dopo backup e dry-run positivo.

```sql
BEGIN;

CREATE TEMP TABLE cleanup_rows AS
SELECT generate_series(864, 883)::int AS id;

CREATE TEMP TABLE cleanup_docs AS
SELECT generate_series(1029, 1050)::int AS id;

CREATE TEMP TABLE cleanup_matches AS
SELECT id
FROM match_certificato
WHERE acquisition_row_id IN (SELECT id FROM cleanup_rows)
   OR document_certificato_id IN (SELECT id FROM cleanup_docs);

CREATE TEMP TABLE cleanup_values AS
SELECT id
FROM valori_letti_acquisition
WHERE acquisition_row_id IN (SELECT id FROM cleanup_rows);

UPDATE acquisition_processing_runs
SET current_row_id = NULL
WHERE current_row_id IN (SELECT id FROM cleanup_rows);

DELETE FROM match_certificato_candidati
WHERE match_certificato_id IN (SELECT id FROM cleanup_matches)
   OR document_certificato_id IN (SELECT id FROM cleanup_docs);

DELETE FROM match_certificato
WHERE id IN (SELECT id FROM cleanup_matches);

DELETE FROM acquisition_row_note_templates
WHERE acquisition_row_id IN (SELECT id FROM cleanup_rows);

DELETE FROM storico_valori_acquisition
WHERE acquisition_row_id IN (SELECT id FROM cleanup_rows)
   OR value_id IN (SELECT id FROM cleanup_values);

DELETE FROM valori_letti_acquisition
WHERE id IN (SELECT id FROM cleanup_values);

DELETE FROM storico_eventi_acquisition
WHERE acquisition_row_id IN (SELECT id FROM cleanup_rows);

DELETE FROM documenti_evidenze
WHERE acquisition_row_id IN (SELECT id FROM cleanup_rows)
   OR document_id IN (SELECT id FROM cleanup_docs);

DELETE FROM datimaterialeincoming
WHERE id IN (SELECT id FROM cleanup_rows);

DELETE FROM documenti_fornitore_pagine
WHERE document_id IN (SELECT id FROM cleanup_docs);

DELETE FROM documenti_fornitore
WHERE documento_padre_id IN (SELECT id FROM cleanup_docs);

DELETE FROM documenti_fornitore
WHERE id IN (SELECT id FROM cleanup_docs);

DELETE FROM acquisition_processing_runs
WHERE id IN (71, 72);

COMMIT;
```

Verifica post-pulizia:

```sql
SELECT count(*) AS rows_left
FROM datimaterialeincoming
WHERE id BETWEEN 864 AND 883;

SELECT count(*) AS docs_left
FROM documenti_fornitore
WHERE id BETWEEN 1029 AND 1050;

SELECT count(*) AS runs_left
FROM acquisition_processing_runs
WHERE id IN (71, 72);
```

Atteso: tutti e tre i conteggi devono essere `0`.

## Set selezionato per test second run

Primo run: caricare solo DDT.  
Secondo run: caricare solo certificati.  
Non mischiare DDT e certificati nello stesso run, altrimenti non stiamo testando il cross-run.

| Fornitore | Run 1 DDT | Pagine | Run 2 certificato | Pagine | Atteso |
| --- | --- | ---: | --- | ---: | --- |
| Aluminium Bozen | `esempi_locali/4-ddt/Aluminium Bz/1267.pdf` | 4 | `esempi_locali/3-certificati/Aluminium Bz - Sapa Bz/CQF_147344_6082H48_2025.pdf` | 2 | Solo la riga `147344` si aggancia; le altre righe senza certificato restano libere. |
| AWW | `esempi_locali/4-ddt/AWW/14142236.pdf` | 2 | `esempi_locali/3-certificati/AWW/CQF_Z25-02034_6082L35_2025.pdf` | 1 | Si aggancia la riga `Z25-02034`; eventuali righe DDT senza CDQ/certificato restano libere. |
| Impol | `esempi_locali/4-ddt/Impol/1505-11.pdf` | 1 | `esempi_locali/3-certificati/Impol/CQF_1505_a_608232_2026.pdf` | 2 | Si aggancia solo `1505/A`; `1505/B` e `1505/C` restano libere se i certificati non sono caricati. |
| Leichtmetall | `esempi_locali/4-ddt/Leichtmetall/80008535.pdf` | 2 | `esempi_locali/3-certificati/Leichtmetall A/Certificati Origine/CdQ_94668_6082_Ø228.pdf` | 1 | Si aggancia `94668`; il peso diverso non deve bloccare se `cdq/colata/diametro/lega` coincidono. |
| Metalba | `esempi_locali/4-ddt/Metalba/26-00960.pdf` | 2 | `esempi_locali/3-certificati/Metalba Aluminium/CQF_26-0746_608248_2026.pdf` | 1 | Si aggancia `26-0746`; controllare materiale, ordine e overlay proprieta. |
| Neuman | `esempi_locali/4-ddt/Neuman/75724077.pdf` | 2 | `esempi_locali/3-certificati/Vari/Neuman Aluminium Austria/CQF_26088_6082190_2026.pdf` | 1 | Si aggancia `26088`; controllare chimica e overlay elementi. |

Totale set: `12 PDF`, `21 pagine`.

## Stima costo AI

Stima prudente per il set selezionato: circa `0,10 - 0,40 USD`.

Motivo: la costante app per crop low-detail e bassa, ma il costo reale include prompt, output JSON e possibili chiamate multiple per DDT/certificato. La stima va ripetuta prima del lancio se cambia il set.

Prima di usare AI scrivere all'utente:

- numero PDF e pagine;
- modello configurato;
- costo stimato;
- scopo del run;
- richiesta esplicita: "Confermi l'uso AI per questo test?"

## Procedura test

1. Eseguire backup.
2. Eseguire dry-run pulizia.
3. Eseguire pulizia parziale.
4. Verificare che righe/documenti/run contaminanti siano a zero.
5. Caricare i 6 DDT del Run 1.
6. Avviare Run 1 con AI solo dopo consenso esplicito.
7. Verificare che esistano righe DDT-only e che non ci siano certificati agganciati per i casi del secondo run.
8. Caricare i 6 certificati del Run 2.
9. Avviare Run 2 con AI solo dopo consenso esplicito.
10. Verificare rematch automatico cross-run.
11. Audit finale per fornitore su righe alte, valori letti, match, chimica, proprieta, note e overlay.

## Query controllo dopo Run 1

```sql
SELECT r.id, s.ragione_sociale, d.nome_file_originale AS ddt,
       c.nome_file_originale AS certificato, r.cdq, r.colata, r.diametro, r.peso
FROM datimaterialeincoming r
LEFT JOIN fornitori s ON s.id = r.fornitore_id
LEFT JOIN documenti_fornitore d ON d.id = r.document_ddt_id
LEFT JOIN documenti_fornitore c ON c.id = r.document_certificato_id
WHERE d.nome_file_originale IN (
  '1267.pdf', '14142236.pdf', '1505-11.pdf',
  '80008535.pdf', '26-00960.pdf', '75724077.pdf'
)
ORDER BY s.ragione_sociale, r.id;
```

Atteso dopo Run 1: righe con DDT valorizzato e certificato `NULL`.

## Query controllo dopo Run 2

```sql
SELECT r.id, s.ragione_sociale, d.nome_file_originale AS ddt,
       c.nome_file_originale AS certificato, r.cdq, r.colata, r.diametro, r.peso,
       m.stato AS match_stato, m.fonte_proposta, m.motivo_breve
FROM datimaterialeincoming r
LEFT JOIN fornitori s ON s.id = r.fornitore_id
LEFT JOIN documenti_fornitore d ON d.id = r.document_ddt_id
LEFT JOIN documenti_fornitore c ON c.id = r.document_certificato_id
LEFT JOIN match_certificato m ON m.acquisition_row_id = r.id
WHERE d.nome_file_originale IN (
  '1267.pdf', '14142236.pdf', '1505-11.pdf',
  '80008535.pdf', '26-00960.pdf', '75724077.pdf'
)
ORDER BY s.ragione_sociale, r.id;
```

Atteso dopo Run 2:

- I 6 certificati selezionati devono risultare agganciati alle righe DDT corrette.
- Nessun certificato deve creare duplicato certificate-first se esiste gia la riga DDT corretta.
- Le righe DDT non coperte dai certificati caricati devono restare libere.
- Il match deve essere `fonte_proposta = sistema` e `stato = proposto`, salvo diversa regola attuale.

## Suggerimenti per i test second run successivi

Dopo il test base, aggiungere questi casi uno per volta:

- Certificato-first: caricare prima certificato, poi DDT in secondo run. Serve a verificare il verso inverso.
- DDT multiriga con piu certificati caricati in run diversi: esempio Leichtmetall `80008535.pdf` con `94668` e poi `94752`.
- Certificato non matchabile: caricare un certificato dello stesso fornitore ma con `cdq/colata/diametro` diversi; deve restare libero.
- Certificato gia accoppiato rilevante per altra riga: verificare che il motore lo consideri senza rompere il match esistente.
- Modifica utente sui campi ponte: se l'utente corregge i campi Excel, il rematch futuro deve usare i valori finali confermati dall'utente.
- Overlay dopo rematch: dopo aggancio cross-run, aprire pagina match/chimica/proprieta/note e verificare che overlay blu punti al documento corretto.

## Criteri di stop

Fermarsi se:

- Un rematch collega un certificato al DDT sbagliato.
- Un certificato caricato nel secondo run resta certificate-first pur avendo DDT gia presente con campi ponte coincidenti.
- Il peso blocca Leichtmetall `94668` nonostante `cdq/colata/diametro/lega` coincidano.
- AWW perde la lega corretta e torna a usare solo `T1`.
- Un overlay guida l'utente su un campo sbagliato.
- Viene proposta una nuova chiamata AI senza stima costo e consenso.

