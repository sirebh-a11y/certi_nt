# Vista SQL Certi verso eSolver - piano di lavoro

Stato: piano/audit, non implementato.

Regola operativa: non applicare modifiche a codice, database o server senza conferma esplicita di Silvano.

## Obiettivo

Esporre a Nemesi/eSolver i certificati PDF chiusi prodotti da Certi tramite una vista SQL in sola lettura.

L'endpoint HTTP gia esistente resta utile per scaricare il PDF, ma Walter ha segnalato che l'integrazione inizialmente attesa era una vista database.

## Stato attuale

Oggi Certi espone i PDF chiusi tramite endpoint:

`GET /api/export/esolver/certificati-pdf`

Autenticazione:

- utente: `Certi`
- password: `Certi`

Campi esposti oggi dall'endpoint:

- `IdCerti`
- `OL`
- `DDT`
- `CodF3`
- `NumeroCertificato`
- `DataCertificato`
- `PdfUrl`
- `Stato`
- `UpdatedAt`

Il PDF non viene copiato nel database: viene esposto con un URL applicativo firmato tramite `download_token`.

## Audit tecnico

La tabella principale oggi e:

`quarta_taglio_final_certificates`

Campi gia presenti e utili:

- `id`
- `cod_odp`
- `cod_f3`
- `ddt`
- `ordine_cliente`
- `quantita`
- `cdq_key`
- `certificate_number`
- `draft_number`
- `cert_date`
- `fornitore_cliente`
- `conformity_status`
- `status`
- `storage_key_pdf`
- `download_token`
- `updated_at`

Filtro corretto per esportare solo certificati validi:

- `status = 'pdf_final'`
- PDF presente
- token download presente
- numero certificato presente
- data certificato presente
- DDT presente

Problema rilevante:

oggi la tabella salva un solo `cod_f3`. Il Word invece conosce la distinzione tra:

- CodF3 del certificato/lavorazione
- CodF3 raw
- CodF3 finished

Questa distinzione viene calcolata dal codice quando genera/aggiorna il Word, ma non e persistita in modo completo nella tabella export.

## Punto chiave sui CodF3

Per evitare ambiguita verso eSolver/Nemesi, la vista non dovrebbe esporre un solo campo generico se il significato non e chiaro.

Proposta campi:

- `CodF3Certificato`: codice della riga certificata, sempre valorizzato
- `CodF3Raw`: codice raw, valorizzato solo se utile per la riga
- `CodF3Finished`: codice finished, valorizzato solo se utile per la riga

Regola semplice:

- se il certificato riguarda il raw, `CodF3Certificato = CodF3Raw`
- se il certificato riguarda una lavorazione, `CodF3Certificato = CodF3Finished`
- non esporre due codici alternativi senza significato, perche chi legge non saprebbe quale usare

## Soluzione consigliata

### Fase 1 - Vista SQL semplice

Creare una vista PostgreSQL read-only che espone i PDF chiusi usando i campi gia presenti.

Nome proposto:

`certi_export_certificati_pdf`

Campi:

- `IdCerti`
- `OL`
- `DDT`
- `CodF3Certificato`
- `NumeroCertificato`
- `DataCertificato`
- `Quantita`
- `Cliente`
- `OrdineCliente`
- `Cdo`
- `PdfUrl`
- `Stato`
- `UpdatedAt`

Questa fase e la piu rapida e non richiede di cambiare la logica di certificazione.

Limite: raw/finished non sono ancora separati in modo esplicito.

### Fase 2 - Vista robusta raw/finished

Aggiungere colonne persistenti alla tabella certificati finali:

- `cod_f3_certificato`
- `cod_f3_raw`
- `cod_f3_finished`
- `ddt_raw`
- `ddt_finished`
- `quantita_raw`
- `quantita_finished`
- `descrizione_raw`
- `descrizione_finished`

Questi valori devono essere scritti dal codice nello stesso momento in cui viene aggiornato/generato il Word, usando la stessa logica gia esistente per l'header certificato.

La vista SQL poi legge solo campi gia salvati, senza rifare calcoli complessi.

Questa e la soluzione piu robusta per produzione.

## Accesso database

Oggi nel deploy alpha PostgreSQL e interno al compose.

Per una vista SQL vera serve intervento IT:

1. esporre PostgreSQL solo alla rete autorizzata, ad esempio classe `10.10.0.0/16` o host specifici Nemesi;
2. creare utente read-only dedicato;
3. concedere solo `SELECT` sulla vista;
4. non concedere accesso diretto alle tabelle applicative;
5. mantenere backup prima di ogni modifica schema.

Credenziali proposte per lettura:

- utente: da decidere con IT/Nemesi
- password: da comunicare fuori mail

Nota: l'utente `Certi / Certi` oggi riguarda l'endpoint HTTP, non necessariamente l'accesso PostgreSQL.

## PdfUrl nella vista

La vista puo esporre un campo `PdfUrl`.

Esempio:

`http://certi-test.forgialluminio.it/api/quarta-taglio/certificates/<IdCerti>/pdf-file?download_token=<token>`

La base URL deve essere stabile.

Se in futuro cambia dominio o ambiente, bisogna aggiornare la configurazione usata per costruire la vista o rigenerare il campo esposto.

## Rischi

- Esporre PostgreSQL apre un tema IT/rete/sicurezza che oggi non esiste con il solo endpoint HTTP.
- Se la vista legge direttamente tabelle interne, Nemesi potrebbe dipendere da dettagli applicativi non stabili.
- Senza campi raw/finished persistiti, il significato di `CodF3` puo essere ambiguo in alcuni casi.
- Se un PDF viene riaperto, non deve piu risultare valido in export.
- La vista non deve esporre PDF non chiusi o certificati ancora modificabili.

## Test prima di produzione

1. Chiudere almeno un PDF raw.
2. Chiudere almeno un PDF finished.
3. Verificare che entrambi compaiano nella vista.
4. Riaprire un PDF e verificare che sparisca dalla vista.
5. Scaricare il PDF tramite `PdfUrl`.
6. Verificare con Nemesi se `CodF3Certificato`, `CodF3Raw`, `CodF3Finished` sono sufficienti.
7. Verificare accesso read-only da host Nemesi.

## Proposta operativa

Per non bloccare i test Nemesi:

1. tenere attivo endpoint HTTP attuale;
2. preparare vista SQL semplice come prima risposta;
3. in parallelo preparare la fase robusta con campi raw/finished persistiti;
4. chiedere a Walter se per loro basta `PdfUrl` o se vogliono anche una cartella condivisa alternativa;
5. chiedere a Matteo se preferisce esporre PostgreSQL direttamente o passare da altra modalita controllata.

## Decisione da prendere

Prima di implementare serve scegliere:

1. vista semplice subito, con solo `CodF3Certificato`;
2. vista robusta subito, aggiungendo campi persistenti raw/finished;
3. mantenere solo endpoint HTTP se Nemesi lo accetta dopo test.

Scelta consigliata: fase 1 subito per test, fase 2 prima della produzione stabile.

---

# Audit 2026-07-02 - collegamento PDF Certi a righe DDT eSolver

Stato: audit/piano, non implementato.

Regola operativa: non modificare codice, database o server senza conferma esplicita di Silvano.

## Punto emerso da Walter/Nemesi

L'endpoint HTTP funziona e Nemesi ha scaricato i PDF tramite `PdfUrl`.

Il campo `DDT` esposto oggi da Certi contiene pero solo il numero documento con data, ad esempio:

`1413-22/05/2026`

Questo non basta a eSolver per agganciare il PDF alla riga corretta, perche nella vista `CertiRigheDDT` esistono almeno due identificativi piu precisi:

- `IDDocumento`
- `IDRiga`

Walter ha spiegato che:

- uno stesso DDT puo avere piu righe;
- una stessa riga DDT puo contenere piu lotti;
- lotti diversi possono derivare da OL diversi;
- quindi una riga DDT puo richiedere piu certificati;
- oppure uno stesso certificato puo dover essere collegato a piu righe DDT.

## Stato attuale Certi

Oggi Certi salva e usa principalmente:

- `OL`
- `CodF3`
- `DDT` testuale
- `Quantita`
- `Cliente`
- `Ordine cliente`
- `Numero certificato`
- `PdfUrl`

Oggi Certi non salva in modo strutturato:

- `IDDocumento`
- `IDRiga`
- elenco righe DDT eSolver collegate a un certificato

Questo significa che Certi puo produrre un PDF corretto, ma non sempre puo dire a eSolver su quale riga DDT precisa allegarlo.

## Caso limite spiegato da Walter

Esempio:

- `IDDocumento = 5163782`
- `IDRiga = 7`
- `IDRiga = 8`
- due OL coinvolti sulla riga 8

Scenari da rappresentare:

1. uno stesso OL puo comparire su piu righe DDT;
2. una stessa riga DDT puo contenere quote di OL diversi;
3. una stessa riga DDT puo quindi ricevere piu certificati, uno per quota/OL;
4. un DDT arrivato dopo deve creare un nuovo record, non modificare PDF gia chiusi.

Con il modello attuale, Certi non riesce a rappresentare in modo certo tutti questi casi.

## Rischio attuale

Non e detto che Certi perda il certificato.

Il rischio vero e che il PDF esista, ma venga esposto a eSolver con tracciabilita insufficiente.

Esempi:

- Certi espone un PDF con `DDT = 1413-22/05/2026`, ma eSolver non sa se allegarlo a `IDRiga 7` o `IDRiga 8`;
- Certi somma quantita di piu righe senza sapere che eSolver vuole allegati separati;
- Certi crea piu certificati, ma l'export non espone il legame corretto con le righe eSolver;
- se un certificato viene riaperto/modificato dopo esposizione, eSolver non riceve oggi un'informazione esplicita di revisione.

## Decisione funzionale

La soluzione scelta e una sola:

un certificato/record registro per ogni singola riga o quota eSolver arrivata.

Non si sommano automaticamente righe DDT diverse, anche se hanno stesso OL o stesso ordine cliente.

Motivo operativo:

- i DDT possono arrivare in momenti diversi;
- il PDF puo dover essere chiuso e spedito prima che arrivi un secondo DDT;
- quindi Certi non puo aspettare righe future per decidere una somma;
- ogni PDF chiuso deve restare riferito alla riga/quota eSolver disponibile in quel momento.

Esempio Walter:

- `IDDocumento 5163782`, `IDRiga 7`, OL `OL2026000271`, quantita 484;
- `IDDocumento 5163782`, `IDRiga 8`, OL `OL2026000271`, quantita 45;
- `IDDocumento 5163782`, `IDRiga 8`, OL `OL2026000455`, quantita 455.

Risultato Certi:

- un certificato/record per 484 pezzi, collegato a `IDDocumento 5163782` e `IDRiga 7`;
- un certificato/record per 45 pezzi, collegato a `IDDocumento 5163782` e `IDRiga 8`;
- un certificato/record per 455 pezzi, collegato a `IDDocumento 5163782` e `IDRiga 8`, ma con OL diverso.

Caso aggiuntivo non evidente nella mail di Walter:

se per lo stesso OL/CodF3 esistono anche DDT precedenti o successivi, ad esempio un DDT precedente gia visibile in Certi per lo stesso OL, anche quello deve generare il proprio record registro/export quando arriva da eSolver.

Quindi il registro non deve rappresentare solo "un OL + un CodF3", ma ogni destinazione reale eSolver:

`OL + CodF3 + IDDocumento + IDRiga + eventuale lotto/quota`.

La somma tra righe resta fuori dalla logica automatica Certi.
Se in futuro Qualita volesse unire manualmente piu righe in un unico PDF, servirebbe una funzione esplicita e tracciata, non implicita.

## Soluzione tecnica necessaria per la scelta fissata

Certi deve portare dentro i riferimenti eSolver precisi per ogni singola riga/quota.

Piano tecnico:

1. estendere la lettura della vista `CertiRigheDDT` includendo `IDDocumento` e `IDRiga`;
2. salvare questi valori nelle righe eSolver collegate all'OL;
3. creare un legame persistente tra certificato Certi e la riga/quota eSolver specifica;
4. esportare verso eSolver una riga per ogni collegamento certificato-riga DDT;
5. non fondere automaticamente piu righe eSolver nello stesso certificato;
6. se un PDF viene riaperto, non esporlo piu come valido oppure esporre uno stato chiaro da concordare.

Campi export consigliati:

- `IdCerti`
- `NumeroCertificato`
- `DataCertificato`
- `OL`
- `CodF3Certificato`
- `IDDocumento`
- `IDRiga`
- `DDT`
- `QuantitaCertificata`
- `PdfUrl`
- `Stato`
- `UpdatedAt`

## Nota su vista SQL o endpoint HTTP

Il problema non dipende dal fatto che l'export sia endpoint HTTP o vista SQL.

Il problema e il dato esposto.

Prima va salvato il legame corretto Certi -> righe eSolver.

Dopo si puo esporre lo stesso contenuto:

- via endpoint HTTP JSON;
- oppure via vista PostgreSQL read-only;
- oppure entrambi, se utile.

## Proposta operativa

1. Rispondere a Walter che il punto e chiaro: aggiungere solo `IDDocumento` e `IDRiga` all'output non basta se internamente Certi non salva il legame.
2. Confermare che Certi puo adeguarsi per esporre una riga per ogni collegamento certificato-riga DDT.
3. Comunicare a Nadia/Forgialluminio la decisione operativa: certificato per singola riga/quota eSolver arrivata.
4. Implementare evitando somme implicite non visibili all'utente.

---

# Piano aggiornato 2026-07-02 - righe eSolver/DDT progressive

Stato: piano/audit, non implementato.

Regola operativa: questa modifica e delicata. Prima di applicarla bisogna chiedere conferma esplicita a Silvano.

## Correzione importante del piano

La pagina `Certificazione / OL Quarta` deve restare una riga per OL.

Il `Registro certificazione`, invece, deve poter mostrare una riga per ogni destinazione eSolver reale:

- stesso OL;
- specifico CodF3;
- specifico DDT;
- specifico `IdDocumento`;
- specifico `IdRigaDoc`;
- eventuale lotto/ORP quando la stessa riga DDT contiene piu OL.

Questo serve per non perdere righe DDT e per permettere a eSolver di allegare il PDF alla riga giusta.

## Perche oggi non basta

Audit codice:

- le query verso `CertiRigheDDT` ordinano gia per `IdDocumento` e `IdRigaDoc`;
- pero oggi Certi non seleziona e non salva questi due campi;
- `QuartaTaglioEsolverLink` e unico per `cod_odp` e salva le righe eSolver dentro un JSON aggregato;
- `_build_certifiable_units` raggruppa per `CodF3 + DDT + ODVCli + ODVF3`;
- `_sync_certifiable_unit_register` crea/aggiorna certificati tramite `unit_key`;
- l'export legge solo `quarta_taglio_final_certificates` e quindi espone una riga per certificato, non una riga per collegamento eSolver.

Effetto:

se eSolver espone piu righe con stesso OL/CodF3/DDT, Certi puo fonderle in una sola unita.

Esempio Walter:

- `IdDocumento 5163782`, `IdRigaDoc 7`, OL `OL2026000271`, quantita 484;
- `IdDocumento 5163782`, `IdRigaDoc 8`, OL `OL2026000271`, quantita 45;
- `IdDocumento 5163782`, `IdRigaDoc 8`, OL `OL2026000455`, quantita 455.

La pagina OL puo restare una sola riga per `OL2026000271`.

Il registro/export pero deve sapere che esistono due destinazioni eSolver per `OL2026000271`:

- riga 7;
- riga 8.

## Vincolo operativo: arrivo progressivo

Le righe DDT/eSolver non arrivano tutte insieme.

Flusso reale:

1. Quarta espone l'OL e Certi puo gia preparare raw/lavorazioni.
2. Qualita puo generare Word prima che il DDT esista.
3. eSolver puo emettere un primo DDT dopo ore o giorni.
4. eSolver puo emettere un secondo DDT ancora dopo.
5. Ogni nuova riga eSolver deve creare o aggiornare il proprio collegamento nel registro.

Quindi la logica non puo essere "creo tutto una volta".

Deve essere una sincronizzazione incrementale:

- se una riga eSolver nuova arriva, Certi la aggiunge;
- se una riga eSolver gia nota resta uguale, Certi la mantiene;
- se una riga eSolver cambia dopo PDF chiuso, Certi non deve sovrascrivere in silenzio: deve segnalarlo.

## Modello dati proposto

Non cambiare il significato principale di `quarta_taglio_final_certificates`.

Aggiungere una tabella figlia dedicata ai collegamenti eSolver, nome proposto:

`quarta_taglio_certificate_esolver_links`

Campi minimi:

- `id`
- `certificate_id` nullable inizialmente, valorizzato quando il certificato esiste
- `cod_odp`
- `cod_f3`
- `id_documento`
- `id_riga_doc`
- `rif_lotto_alfanum` oppure campo equivalente se disponibile
- `ddt`
- `ordine_cliente`
- `conferma_ordine`
- `cliente`
- `quantita`
- `source_row_hash`
- `status`
- `message`
- `created_at`
- `updated_at`

Chiave naturale consigliata:

`id_documento + id_riga_doc + cod_odp + cod_f3 + rif_lotto_alfanum`

Motivo:

- `IdDocumento + IdRigaDoc` individua la riga DDT eSolver;
- `cod_odp` distingue i lotti/OL quando la stessa riga DDT contiene piu ORP;
- `cod_f3` evita ambiguita sulle lavorazioni;
- `rif_lotto_alfanum` rafforza il legame se disponibile.

Fallback solo per dati vecchi o incompleti:

`cod_odp + cod_f3 + ddt + ordine_cliente + conferma_ordine + quantita`

Il fallback va marcato come `legacy/da_verificare`, perche non e robusto come gli ID eSolver.

## Sincronizzazione proposta

### Quando sincronizzare

Usare gli stessi momenti gia previsti oggi:

- apertura pagina Certificazione;
- refresh righe visibili;
- apertura dettaglio OL;
- refresh Registro certificazione visibile.

Non serve caricare tutto eSolver sempre.

Si aggiorna quello che l'utente sta guardando o filtrando.

### Regola per ogni riga eSolver letta

1. Calcolare la chiave naturale eSolver.
2. Se il link esiste:
   - aggiornare campi amministrativi non critici;
   - mantenere il legame al certificato;
   - se il PDF e gia chiuso e cambiano DDT/quantita/ordine, segnare warning.
3. Se il link non esiste:
   - creare nuovo link;
   - cercare se esiste un certificato/Word compatibile per OL+CodF3;
   - se esiste, collegarlo o ereditarlo secondo le regole attuali;
   - se non esiste, lasciare riga in attesa/preparabile.
4. Non fondere mai due righe solo perche hanno stesso `DDT` testuale.

## Registro certificazione

Il registro deve visualizzare una riga per ogni link eSolver quando il DDT e arrivato.

Esempi:

### Caso semplice

Un OL, un CodF3, un DDT, una riga eSolver:

- una riga nel registro;
- un PDF;
- una riga export.

### Stesso OL su due righe DDT

Un OL, stesso CodF3, stesso DDT, ma `IdRigaDoc 7` e `IdRigaDoc 8`:

- due righe nel registro;
- due certificati/PDF separati se entrambe devono essere chiuse;
- export espone due righe.

### Stessa riga DDT con due OL

Stesso `IdDocumento`, stesso `IdRigaDoc`, due OL diversi:

- una riga registro per il primo OL;
- una riga registro per il secondo OL;
- eSolver riceve due righe export, entrambe sulla stessa riga DDT ma con OL diversi.

### DDT arrivato dopo il Word

Prima:

- registro mostra Word in attesa DDT.

Dopo arrivo eSolver:

- nasce/si aggiorna il link eSolver;
- il Word scaricato o il PDF generato deve aggiornare DDT/data/quantita prima dell'output;
- se servono piu righe eSolver, nascono piu righe registro.

## Export verso eSolver

L'export non deve piu essere solo "una riga per certificato".

Deve essere:

una riga per ogni collegamento certificato-riga eSolver.

Campi consigliati:

- `IdCerti`
- `NumeroCertificato`
- `DataCertificato`
- `OL`
- `CodF3`
- `IdDocumento`
- `IdRigaDoc`
- `RifLottoAlfanum`
- `DDT`
- `Quantita`
- `PdfUrl`
- `Stato`
- `UpdatedAt`

Regole:

- esporre solo PDF chiusi;
- ogni riga export punta al PDF chiuso della propria riga/quota eSolver;
- se il PDF viene riaperto, non esporre piu il link come valido;
- se un PDF gia consegnato viene modificato dopo, serve stato/flag da concordare con eSolver.

## Scelta funzionale fissata

La scelta funzionale fissata e:

certificato separato per ogni riga/quota eSolver.

Esempio:

- riga 7, OL 271, 484 pezzi -> un certificato;
- riga 8, OL 271, 45 pezzi -> un certificato;
- riga 8, OL 455, 455 pezzi -> un certificato.

Se un altro DDT per lo stesso OL arriva dopo, nasce un nuovo record registro/export per quel DDT.

Non si aggiorna un PDF gia chiuso per inglobare righe arrivate dopo.

Conseguenza:

- tracciabilita piu semplice;
- nessuna attesa di DDT futuri;
- eSolver puo allegare il PDF alla riga precisa;
- qualita puo chiudere e amministrazione puo spedire senza aspettare eventuali spedizioni successive.

## Piano di implementazione

### Fase 1 - Audit tecnico puntuale

1. Verificare nomi esatti dei campi eSolver:
   - `IdDocumento`;
   - `IdRigaDoc`;
   - `RifLottoAlfanum`;
   - `ORP`;
   - `QtaUmMag`.
2. Verificare tutti i punti dove oggi si usa `unit_key`.
3. Verificare casi gia gestiti:
   - raw/lavorazioni;
   - ereditarieta Word;
   - DDT arrivato dopo;
   - PDF chiuso;
   - PDF riaperto.

### Fase 2 - Database

1. Aggiungere nuova tabella link eSolver.
2. Aggiungere indici su:
   - `certificate_id`;
   - `cod_odp`;
   - `cod_f3`;
   - `id_documento`;
   - `id_riga_doc`;
   - chiave naturale.
3. Preparare migrazione sicura.
4. Backfill prudente dei certificati esistenti:
   - automatico solo se non ambiguo;
   - warning/manuale se ambiguo.

### Fase 3 - Lettura eSolver

1. Estendere query `CertiRigheDDT` per selezionare `IdDocumento`, `IdRigaDoc`, `RifLottoAlfanum`.
2. Estendere schema `QuartaTaglioEsolverDdtRowResponse`.
3. Non usare piu solo il raggruppamento `CodF3 + DDT + ordine`.
4. Creare/aggiornare link in modo incrementale.

### Fase 4 - Registro certificazione

1. Mostrare le righe registro in base ai link eSolver quando disponibili.
2. Mantenere righe "in attesa DDT" per Word/certificati preparati prima del DDT.
3. Mostrare stato chiaro:
   - `In attesa DDT`;
   - `DDT arrivato`;
   - `Word aperto`;
   - `PDF da generare`;
   - `PDF chiuso`;
   - `eSolver variato dopo PDF`.
4. Evitare duplicati visivi non spiegati.

### Fase 5 - Word/PDF

1. Prima di scaricare Word o generare PDF, aggiornare campi da link eSolver attivo.
2. Generare numero/Word/PDF separato per ogni riga/quota eSolver da chiudere.
3. Non sovrascrivere PDF chiuso senza riapertura esplicita.

### Fase 6 - Export endpoint/vista

1. Cambiare endpoint per leggere dalla tabella link.
2. Aggiungere `IdDocumento` e `IdRigaDoc`.
3. Esporre un record per ogni riga/quota eSolver con il proprio `PdfUrl`.
4. Preparare eventuale vista SQL PostgreSQL con gli stessi campi.

### Fase 7 - Test obbligatori

1. Caso Walter `5163782` riga 7/8.
2. DDT arrivato in due momenti diversi sullo stesso OL.
3. Stesso DDT, stesso CodF3, righe diverse.
4. Stessa riga DDT con due OL diversi.
5. PDF chiuso e poi nuova riga eSolver arrivata.
6. PDF riaperto.
7. Export con una riga per ogni riga/quota eSolver.
8. Registro senza duplicati falsi.

## Rischi principali

- Sommare quantita quando invece eSolver vuole allegati separati.
- Perdere una riga DDT perche ha stesso DDT testuale di un'altra.
- Cambiare PDF gia chiusi senza traccia.
- Rompere l'ereditarieta Word se si lega tutto troppo presto al DDT.

## Decisione consigliata

Prima implementazione consigliata:

1. salvare sempre tutte le righe eSolver con `IdDocumento` e `IdRigaDoc`;
2. non sommare automaticamente righe diverse;
3. esporre in registro una riga per ogni link eSolver;
4. generare/chiudere PDF per la singola riga/quota disponibile;
5. se arriva un nuovo DDT dopo, creare un nuovo record registro/export;
6. in caso ambiguo mostrare warning e non esportare come definitivo.

Questa e la soluzione piu sicura per non perdere righe DDT, non aspettare DDT futuri e permettere a eSolver di allegare il PDF alla riga corretta.
