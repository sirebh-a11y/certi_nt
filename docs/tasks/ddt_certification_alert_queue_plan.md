# DDT da certificare - audit Alpha e piano di implementazione

**Stato:** fase 1 backend realizzata in locale; attivazione, API/UI e recupero storico ancora da completare

**Data audit:** 29/09/2026

**Ambiente verificato:** Alpha `certi-test.forgialluminio.it`

**Scopo del documento:** consegna operativa per proseguire il lavoro con Codex in VS Code.

## Avanzamento locale dopo il procedi

L'utente ha autorizzato lo sviluppo locale. È stata realizzata la fase 1:

- `QuartaTaglioDdtWorkItem` conserva i fatti sorgente anche oltre la finestra eSolver;
- `QuartaTaglioDdtSyncRun` conserva esiti/timestamp e contatori, separando ultimo tentativo e ultimo successo;
- `ddt_snapshot.py` legge la vista completa e applica il batch in transazione;
- nuove tabelle create dal bootstrap `Base.metadata.create_all`, secondo la convenzione esistente, senza ALTER distruttivi;
- lock transazionale PostgreSQL contro esecuzioni concorrenti, più lock locale di processo;
- errori di lettura, righe non valide e conflitti di identità lasciano intatto lo snapshot;
- OL mancante promosso a OL noto solo quando l'abbinamento è unico;
- errori persistiti tramite codici fissi, senza testo del driver o credenziali;
- scheduler predisposto con `DDT_SNAPSHOT_ENABLED=false` di default.

La nuova sincronizzazione **non è stata attivata** sul database applicativo. I test usano dati simulati, SQLite e PostgreSQL temporaneo isolato. Nessun collegamento ad Alpha/eSolver è stato effettuato durante questa implementazione.

Le aggiunte qui descritte sono autorizzate dal procedi per la fase 1. Il vecchio documento `docs/development_rules.md` contiene vincoli del progetto inizialmente limitato al core: l'eccezione riguarda soltanto questa funzionalità approvata, non modifiche generali all'architettura.

Mancano ancora: API, pagina, badge, stati derivati da Incoming/PDF, esclusione manuale, importazione storica, scelta delle soglie e avviso visivo. Non considerare la coda operativa finché queste fasi non sono complete e verificate. Nessun commit, push o deploy eseguito.

### Precisazione emersa nell'implementazione

Le quattro righe senza OL che condividono documento/riga con quote aventi OL **non sono duplicati dimostrati**. L'audit mostra lotti/quantità distinti: vanno conservate finché un controllo specifico non prova il contrario. La condivisione di `IdDocumento + IdRigaDoc` da sola non autorizza l'esclusione.

### Verifiche fase 1

- suite offline dedicata a identità, persistenza, riconciliazione, errori, rollback e scheduler;
- verifica PostgreSQL locale con lock detenuto da un'altra connessione, rilascio del lock e violazione reale NOT NULL per verificare il rollback;
- regressioni su eSolver, filtri Word, quantità registro, riserva qualità ed export PDF;
- risultati e comando finale annotati a fine documento.

## Istruzioni obbligatorie per Codex

Prima di modificare il codice:

1. leggere completamente questo documento;
2. rileggere `docs/development_rules.md` e i documenti eSolver richiamati più avanti;
3. controllare il codice attuale e verificare che i riferimenti indicati non siano cambiati;
4. presentare al proprietario un audit aggiornato, il piano dei file da modificare, i rischi e i test;
5. attendere un suo esplicito **OK** o **procedi** prima di scrivere codice;
6. lavorare prima e solamente in locale;
7. non fare deploy Alpha finché non viene richiesto esplicitamente;
8. per un eventuale deploy Alpha seguire integralmente `docs/deploy/alpha_soft_update_server.md`;
9. non modificare dati Alpha durante l'audit e non inserire credenziali o password in codice, documentazione, test o log;
10. non alterare le logiche esistenti di Incoming, standard, certificazione, registro o PDF salvo quanto definito qui.

## Obiettivo funzionale

Creare una nuova pagina che avvisi l'utente quando eSolver espone un nuovo DDT collegato a un OL e mostri il lavoro di certificazione ancora da completare.

Nome proposto nella sidebar:

> **DDT da certificare**

Posizione proposta:

- prima voce della sezione `Flusso certificazione`;
- prima di `Carica Documenti`;
- accessibile con lo stesso permesso già usato per `Certificazione`, senza introdurre un nuovo ruolo se non necessario;
- badge con il numero delle unità ancora attive.

Una riga deve lasciare la vista attiva solamente quando il PDF definitivo della sua specifica unità DDT/OL è stato chiuso. L'apertura della pagina o della riga non equivale al completamento.

## Cosa non deve fare

- Non deve sostituire la pagina `Certificazione`.
- Non deve cambiare automaticamente lo stato di Incoming.
- Non deve confermare chimica, proprietà, note, qualità o standard.
- Non deve considerare il solo Word come lavoro concluso.
- Non deve unire righe basandosi soltanto sul numero DDT o soltanto sull'OL.
- Non deve cancellare una segnalazione solo perché la vista eSolver non restituisce più un DDT vecchio.
- Non deve usare `CertificatoPresente` come fonte di verità per il PDF CERTI.
- Non deve inventare un OL quando eSolver non lo fornisce.

## Risultato dell'audit Alpha

### Finestra temporale eSolver

Il 29/09/2026 la vista `dbo.CertiRigheDDT` ha restituito:

- 392 righe;
- 154 DDT distinti;
- 190 valori OL distinti contando anche il valore vuoto;
- 189 OL non vuoti;
- date comprese tra 03/08/2026 e 29/09/2026;
- età massima osservata: 57 giorni;
- nessuna data non interpretabile;
- nessuna riga oltre 60 giorni.

La cache locale Alpha conserva righe del 30/07/2026, oggi vecchie di 61 giorni, che non sono più restituite dalla vista. Le righe del 03/08/2026, vecchie di 57 giorni, sono ancora restituite.

Il comportamento è quindi coerente con un limite di circa 60 giorni. Non è possibile certificare dal solo campione se il limite esatto sia 58, 59 o 60 giorni, perché non risultano DDT dal 31/07 al 02/08. L'utente SQL configurato in CERTI possiede `SELECT`, ma non `VIEW DEFINITION`, sulla vista. Per confermare il valore SQL esatto occorre una delle seguenti informazioni da Matteo/eSolver:

- definizione della vista `dbo.CertiRigheDDT`; oppure
- permesso temporaneo o permanente `VIEW DEFINITION` sulla vista.

Questo dettaglio non cambia l'architettura necessaria: CERTI deve conservare localmente le righe già viste.

### Completezza dei collegamenti correnti

Sulle 392 righe correnti:

- 343 hanno un OL e formano 343 unità eSolver distinguibili;
- tutte le 343 righe con OL appartengono a uno dei 189 OL presenti anche nei dati Quarta correnti;
- non sono stati trovati OL valorizzati in eSolver ma assenti da Quarta;
- 49 righe hanno OL vuoto;
- 4 delle 49 righe vuote condividono documento/riga con quote collegate a uno o più OL, ma non sono duplicati dimostrati;
- 45 righe, relative a 44 righe documento, restano realmente senza OL utilizzabile.

Non emerge una perdita corrente degli OL valorizzati tra eSolver e Quarta. Le righe senza OL, invece, oggi non possono essere aperte correttamente in Certificazione.

### Stato del lavoro corrente

Tra le 343 unità correnti con OL:

- 8 hanno già un PDF finale esattamente collegato e non dovrebbero comparire nella vista attiva;
- 3 sono pronte lato Incoming e non hanno ancora il PDF finale;
- 332 non sono ancora complete lato Incoming;
- non sono state trovate unità correnti classificate come sola qualità respinta nel campione del giorno.

Conservando tutte le quote distinte, l'avvio della nuova funzione produrrebbe indicativamente:

- 335 unità con OL ancora attive;
- 49 righe senza OL da verificare;
- totale iniziale: circa 384 segnalazioni attive.

Questi numeri sono una fotografia dell'audit e non devono diventare valori fissi nei test o nel codice.

### Limite della cache attuale

Il sincronizzatore Quarta viene eseguito ogni 15 minuti, ma `sync_and_list_quarta_taglio()` aggiorna i collegamenti eSolver soltanto per gli OL della pagina restituita, normalmente 25 gruppi.

Al momento dell'audit:

- la cache locale conteneva 413 identità eSolver;
- soltanto 231 delle 392 identità correnti erano già in cache;
- 161 identità correnti non erano ancora state memorizzate dalla navigazione/paginazione;
- la cache conservava 182 unità uniche più vecchie di 60 giorni;
- queste 182 unità appartenevano a 90 OL;
- nessuna delle 182 risultava chiusa con PDF finale secondo la chiave esatta disponibile.

Quando un OL vecchio viene riletto dopo che il DDT è uscito dalla finestra eSolver, il collegamento corrente può essere sovrascritto con `DDT mancante`. Per questo la nuova pagina non deve appoggiarsi soltanto a `quarta_taglio_esolver_links`.

### Campo eSolver `CertificatoPresente`

Nell'audit tutte le 392 righe riportavano `CertificatoPresente = 0`, comprese otto unità per le quali CERTI possiede già il PDF finale.

Conclusione:

- il campo può essere conservato come informazione proveniente da eSolver;
- non deve determinare la scomparsa della riga;
- la fonte di verità deve restare `quarta_taglio_final_certificates` con PDF finale valido.

## Identità corretta di una segnalazione

L'audit ha confrontato più chiavi:

| Chiave | Unicità sulle 392 righe | Esito |
| --- | ---: | --- |
| `IdDocumento + IdRigaDoc` | 359 | insufficiente: una riga documento può appartenere a più OL |
| `IdDocumento + IdRigaDoc + ORP` | 390 | insufficiente per due casi senza OL |
| `IdDocumento + IdRigaDoc + ORP + RifLottoAlfanum` | 392 | univoca nel campione corrente |
| chiave unità CERTI completa | 392 | univoca nel campione corrente |

Chiave sorgente proposta per lo storico:

```text
IdDocumento + IdRigaDoc + ORP normalizzato + RifLottoAlfanum normalizzato
```

La chiave completa già prodotta da `_certifiable_unit_key()` deve restare la chiave di lavoro verso la certificazione e il PDF. Contiene anche CodF3, DDT, ordine cliente e conferma ordine.

Regola per una correzione eSolver:

- se cambiano DDT, CodF3, quantità o ordini ma la chiave sorgente resta uguale, aggiornare la stessa segnalazione mantenendo `first_seen_at`;
- se un ORP inizialmente vuoto viene successivamente valorizzato, riconciliare la riga tramite `IdDocumento + IdRigaDoc + RifLottoAlfanum` e trasformarla da `Da collegare` a riga collegata, senza lasciare un duplicato;
- se anche il lotto cambia e la riconciliazione è ambigua, non unire automaticamente: evidenziare `Dati eSolver modificati - verifica richiesta`.

## Casistiche obbligatorie

### Un DDT e un OL

Esempio:

```text
DDT 2349 -> OL2026001004
```

Mostrare una riga. Se Incoming è pronto, l'azione apre direttamente il dettaglio di Certificazione dell'OL e della specifica unità.

### Stesso DDT con più OL

Nell'audit sono stati trovati 59 DDT associati a più OL.

Esempio:

```text
DDT 2071 -> OL2026000499
DDT 2071 -> OL2026000657
```

Mostrare due lavori separati. Il PDF chiuso per un OL non deve chiudere l'altro.

### Stessa riga documento divisa tra più OL

Sono state trovate 24 righe documento con più collegamenti OL. Distinguere sempre tramite ORP e lotto, non solo tramite `IdDocumento + IdRigaDoc`.

### Stesso OL con più DDT

Sono stati trovati 40 OL associati a più DDT. Ogni unità resta indipendente. Se un PDF è pronto solo per un DDT, gli altri restano visibili.

### DDT senza OL

Le righe realmente senza OL vanno mostrate nella categoria `Da collegare` con:

- DDT e data;
- IdDocumento e IdRigaDoc;
- CodF3;
- cliente;
- quantità;
- motivo `OL non fornito da eSolver`.

Non consentire l'apertura diretta della certificazione finché manca l'OL e non tentare collegamenti automatici non certi.

### Word preparato prima del DDT

Quando esiste già un Word/raw senza DDT e successivamente arriva l'unità eSolver:

- non creare automaticamente un secondo lavoro Word;
- mostrare `Word già preparato - DDT arrivato, completare il PDF`;
- usare le regole già presenti per associare il draft all'unità;
- se l'associazione è ambigua, chiedere scelta manuale senza sovrascrivere dati.

### Incoming non completo

La riga deve essere visibile, con stato `In attesa Incoming` e azione per aprire le righe Incoming collegate. Non deve risultare pronta per la creazione del certificato.

### Qualità respinta

La riga deve restare visibile. Mostrare `Qualità respinta` e lasciare che siano le regole esistenti di Certificazione a bloccare o guidare il seguito. Non nasconderla dal promemoria.

### Accettato con riserva

La riga deve essere trattata secondo la logica esistente: visibile e lavorabile quando gli altri requisiti lo consentono. Non cambiare la valutazione.

### Nuovo DDT dopo un PDF già chiuso

Il nuovo DDT crea una nuova segnalazione anche se lo stesso OL possiede già un altro PDF finale.

### PDF annullato o riaperto

La relativa segnalazione deve tornare nella vista attiva. Un PDF annullato non è un completamento valido.

### Uscita dalla finestra eSolver

Quando una riga non è più restituita dalla vista per anzianità:

- mantenere lo storico locale;
- segnare `non più presente nella finestra eSolver`;
- continuare a mostrarla se non è completata o esclusa manualmente;
- non cancellare dati e non trasformarla automaticamente in completata.

### Errore di collegamento eSolver

Se la lettura fallisce:

- conservare l'ultimo snapshot valido;
- mostrare data e risultato dell'ultimo aggiornamento riuscito;
- non segnare tutte le righe come scomparse;
- registrare l'errore senza password o dati sensibili.

### Avviso di sincronizzazione eSolver ferma

L'app deve controllare quando è terminata con successo l'ultima lettura completa di `CertiRigheDDT`.

Comportamento proposto:

- sincronizzazione recente e riuscita: nessun avviso, mostrare soltanto `Ultimo aggiornamento: data e ora`;
- uno o più tentativi falliti per alcune ore: avviso giallo `Aggiornamento DDT eSolver non riuscito dalle HH:MM`;
- collegamento fermo da più giorni: avviso rosso, ben visibile agli amministratori, con data e ora dell'ultimo aggiornamento riuscito;
- al ripristino del collegamento: recuperare automaticamente tutte le righe ancora presenti nella finestra eSolver e rimuovere l'avviso dopo una lettura completa riuscita.

L'avviso non deve:

- cancellare o modificare i DDT già memorizzati;
- trasformare righe attive in completate o scomparse;
- mostrare password, stringhe di connessione o dettagli tecnici sensibili;
- dichiarare che i dati sono aggiornati quando l'ultima lettura completa è fallita.

Scopo dell'avviso: rendere evidente un'interruzione prima che duri abbastanza da creare una possibile lacuna rispetto alla finestra temporale eSolver. Le soglie precise per giallo e rosso devono essere confermate prima dell'implementazione; non devono essere valori nascosti o duplicati nel frontend.

## Regole di comparsa e scomparsa

### Una riga compare quando

- viene rilevata per la prima volta in `CertiRigheDDT`; oppure
- esiste nello storico locale ma è ancora incompleta; oppure
- il suo PDF definitivo è stato annullato o riaperto.

### Una riga lascia la vista attiva quando

- esiste un `quarta_taglio_final_certificates` della stessa unità;
- il certificato è realmente `pdf_final`;
- `storage_key_pdf` è presente e valido;
- il PDF non è stato annullato.

La riga deve restare consultabile nello storico `Completati`.

### Condizioni che non chiudono la segnalazione

- Word caricato o generato;
- draft creato;
- utente che apre la pagina;
- spunta di lettura dell'avviso;
- `CertificatoPresente = 1` senza un PDF finale CERTI verificabile;
- PDF di un altro DDT o di un altro OL.

### Esclusione manuale

Non aggiungere un generico `Nascondi`.

Se necessario, prevedere:

> **Non richiede certificazione**

con motivazione obbligatoria, utente, data e possibilità di ripristino. Questa azione deve essere limitata ai ruoli già autorizzati alla certificazione e tracciata nei log.

## UI proposta

### Sidebar

```text
Flusso certificazione
  DDT da certificare        [numero attivi]
  Carica Documenti
  Incoming materiale
  Certificazione
  Registro certificazione
```

Il badge conta le righe attive, non soltanto quelle appena visualizzate. Le righe rilevate di recente possono avere anche l'etichetta `Nuovo`, ma aprire la pagina non le elimina.

### Contatori pagina

- `Attivi`
- `Nuovi`
- `Pronti`
- `In attesa Incoming`
- `Da collegare`
- `Completati`

Vicino ai contatori mostrare sempre:

- data e ora dell'ultima sincronizzazione completa riuscita;
- eventuale avviso giallo o rosso di sincronizzazione ferma;
- pulsante di aggiornamento manuale, senza cancellare lo snapshot in caso di errore.

### Filtri

- stato operativo;
- DDT;
- OL;
- CodF3;
- cliente;
- intervallo data DDT;
- nuovi/non letti;
- solo elementi non più presenti nella finestra eSolver;
- storico completati/esclusi.

### Colonne minime

| Colonna | Origine/nota |
| --- | --- |
| Nuovo | calcolato da `first_seen_at` |
| Data DDT | estratta dal campo DDT, mantenendo anche il valore raw |
| DDT | eSolver |
| OL | eSolver; se vuoto mostra `Da collegare` |
| CodF3 | eSolver |
| Cliente | eSolver `RagSoc` |
| Quantità | eSolver `QtaUmMag` |
| Ordine cliente | eSolver `ODVCli` |
| Conferma F3 | eSolver `ODVF3` |
| Incoming | stato derivato dalle righe Quarta/Incoming |
| Certificazione | nessuna, Word, bozza, PDF finale, PDF annullato |
| Azione | apri Certificazione, apri Incoming, verifica collegamento |

Mostrare sempre anche `Ultimo aggiornamento eSolver` e un pulsante di aggiornamento manuale protetto contro richieste ripetute.

## Architettura proposta

### Nuova tabella persistente

Nome proposto:

```text
quarta_taglio_ddt_work_items
```

Campi da confermare durante l'audit pre-codice:

- `id`;
- `source_key`, univoca;
- `id_documento`;
- `id_riga_doc`;
- `rif_lotto_alfanum`;
- `cod_odp` nullable;
- `cod_f3`;
- `ddt_raw`;
- `ddt_date` nullable;
- `cliente`;
- `ordine_cliente`;
- `conferma_ordine`;
- `quantita`;
- `certificato_presente_esolver` solo informativo;
- `certification_unit_key`;
- `first_seen_at`;
- `last_seen_at`;
- `source_present`;
- `source_disappeared_at` nullable;
- `manual_disposition` nullable;
- `manual_reason` nullable;
- `manual_actor_id` nullable;
- `manual_at` nullable;
- `created_at` e `updated_at`.

Non salvare come verità definitiva lo stato Incoming o lo stato del PDF: devono essere ricalcolati dai dati correnti per non diventare obsoleti.

### Sincronizzazione

Creare una sincronizzazione dedicata che:

1. legge integralmente `CertiRigheDDT`, non per pagina e non per lista OL;
2. lavora in batch/upsert tramite chiave sorgente;
3. aggiorna `last_seen_at` e i campi modificabili;
4. non elimina righe assenti dal nuovo snapshot;
5. imposta `source_present = false` solamente dopo una lettura completa riuscita;
6. non altera lo snapshot in caso di errore di connessione o query parziale;
7. gira ogni 15 minuti insieme al ciclo Quarta, ma come operazione separata;
8. può essere richiamata manualmente dalla nuova pagina;
9. impedisce due esecuzioni contemporanee;
10. registra contatori sintetici nei log, senza credenziali;
11. conserva separatamente l'esito dell'ultimo tentativo e la data dell'ultima lettura completa riuscita;
12. alimenta l'avviso giallo/rosso quando la sincronizzazione resta ferma.

Lettura completa attuale: circa 392 righe. È sufficientemente piccola per un caricamento periodico, ma usare comunque query e transazioni controllate.

### Stato derivato di ogni riga

Ordine proposto:

1. `Completato` se il PDF finale esatto è valido;
2. `Escluso manualmente` se esiste una disposizione valida;
3. `Da collegare` se manca l'OL;
4. `Qualità respinta` se la riga Incoming collegata è respinta;
5. `In attesa Incoming` se Incoming non è completo;
6. `Word pronto - chiudere PDF` se esiste Word/draft associabile;
7. `Pronto da certificare` negli altri casi lavorabili;
8. `Verifica richiesta` in presenza di identità o associazioni ambigue.

Non duplicare le regole: riusare, estraendo dove opportuno, le funzioni già presenti in `backend/app/modules/quarta_taglio/service.py`.

### Endpoint proposti

Confermare nomi e convenzioni durante l'audit:

```text
GET  /quarta-taglio/ddt-work-items
GET  /quarta-taglio/ddt-work-items/counters
POST /quarta-taglio/ddt-work-items/sync
PATCH /quarta-taglio/ddt-work-items/{id}/disposition
```

Il listing deve supportare paginazione, filtri e ordinamento lato server. Il contatore sidebar non deve scaricare l'intera tabella.

### Frontend proposto

- nuova rotta: `/quarta-taglio/ddt-da-certificare`;
- nuova pagina nel modulo `frontend/src/pages/quartaTaglio/`;
- voce e badge in `frontend/src/components/layout/Sidebar.jsx`;
- API in `frontend/src/app/api.js` seguendo le convenzioni esistenti;
- stesso `AccessGuard` della pagina Certificazione;
- navigazione alla specifica unità, non soltanto all'OL, tramite query o stato già supportato dal dettaglio.

## Avvio iniziale e recupero storico

La prima esecuzione non deve limitarsi alla vista corrente, altrimenti si perderebbero le unità più vecchie già note ad Alpha.

Procedura proposta:

1. importare lo snapshot corrente completo di `CertiRigheDDT`;
2. importare da `quarta_taglio_esolver_links.rows` le unità storiche non più presenti nella vista;
3. deduplicare usando la chiave sorgente;
4. marcarle `Storico recuperato - da verificare`, non `Nuovo`;
5. confrontarle con tutti i certificati finali già esistenti;
6. lasciare attive solamente quelle non completate;
7. produrre prima un report dry-run con conteggi e conflitti;
8. richiedere conferma del proprietario prima di eseguire l'importazione reale su Alpha.

Non usare numeri dell'audit come condizione applicativa. I 182 elementi storici e i 90 OL servono solo per controllare il risultato del dry-run.

Il recupero della cache non garantisce lo storico completo: i DDT usciti dalla vista e mai memorizzati da CERTI richiedono un'estrazione storica aggiuntiva da eSolver. Anche dopo l'attivazione, DDT mai esposti dalla vista, rimossi prima della lettura o non letti per un'interruzione superiore alla finestra disponibile non sono recuperabili dal solo snapshot. L'avviso di sincronizzazione riduce il rischio, ma non costituisce una garanzia assoluta di assenza di lacune.

## File e logiche da riesaminare prima dell'implementazione

### Backend

- `backend/app/modules/quarta_taglio/models.py`
- `backend/app/modules/quarta_taglio/schemas.py`
- `backend/app/modules/quarta_taglio/router.py`
- `backend/app/modules/quarta_taglio/service.py`
- `backend/app/modules/quarta_taglio/scheduler.py`
- migrazioni/database bootstrap secondo la convenzione reale del repository
- `backend/tests/test_quarta_taglio_esolver.py`
- test specifici nuovi per la coda DDT

Funzioni esistenti da preservare o riusare:

- `_fetch_esolver_ddt_rows_batch()`;
- `_refresh_esolver_links_for_rows()`;
- `_build_certifiable_units()`;
- `_certifiable_unit_key()`;
- `_certification_progress_for_group()`;
- `_incoming_rows_ready_for_certification()`;
- `_incoming_rows_complete_for_word_queue()`;
- `_certificate_is_pdf_final()` e relative regole di annullamento.

### Frontend

- `frontend/src/components/layout/Sidebar.jsx`
- `frontend/src/app/router.jsx`
- `frontend/src/app/api.js`
- `frontend/src/app/access.js`
- `frontend/src/pages/quartaTaglio/QuartaTaglioPage.jsx`
- `frontend/src/pages/quartaTaglio/QuartaTaglioDetailPage.jsx`
- eventuali helper e test `.mjs` dedicati.

### Documentazione collegata

- `docs/development_rules.md`
- `docs/modules/esolver_sql_view_implementation_plan.md`
- `docs/modules/esolver_sql_view_export_plan.md`
- `docs/modules/quarta_taglio_final_certificate_flow_placeholder.md`
- `docs/modules/quarta_taglio_word_inheritance_rules.md`
- `docs/deploy/alpha_soft_update_server.md`

## Piano di sviluppo per fasi

### Fase 0 - audit aggiornato e approvazione

- verificare lo stato Git e preservare modifiche estranee;
- controllare modelli, migrazioni, API e test attuali;
- confermare la chiave e la semantica del PDF finale;
- presentare file, rischi e test;
- attendere `procedi`.

### Fase 1 - snapshot persistente backend

- modello e migrazione;
- lettura completa eSolver;
- upsert non distruttivo;
- gestione finestra scaduta ed errori;
- test unitari della chiave e della sincronizzazione;
- nessuna UI.

### Fase 2 - stato operativo e API

- correlazione con Quarta, Incoming, Word, draft e PDF;
- contatori e filtri;
- esclusione manuale tracciata;
- test delle casistiche e delle autorizzazioni.

### Fase 3 - UI

- pagina, contatori e filtri;
- voce sidebar e badge;
- navigazioni verso Incoming e Certificazione;
- controllo responsive e testi chiari.

### Fase 4 - recupero storico locale

- dry-run dell'importazione della cache;
- report conteggi, duplicati e ambiguità;
- importazione locale dopo conferma;
- test con righe oltre 60 giorni.

### Fase 5 - verifica complessiva

- test backend mirati e suite Quarta/eSolver;
- test frontend/helper;
- build frontend;
- controllo manuale con dati simulati;
- verifica che filtri, registro e generazione PDF esistenti non cambino.

### Fase 6 - commit/push e Alpha

Solo su richiesta esplicita e in passaggi separati:

1. mostrare diff e risultati dei test;
2. attendere conferma per commit/push;
3. attendere conferma separata per deploy;
4. seguire `docs/deploy/alpha_soft_update_server.md`;
5. eseguire prima il dry-run storico;
6. verificare applicazione e database senza interrompere il lavoro utente.

## Test obbligatori

### Sincronizzazione

- vista vuota per errore: nessuna cancellazione;
- errore connessione: snapshot invariato;
- stessa lettura ripetuta: nessun duplicato;
- modifica quantità/DDT/CodF3 con stessa chiave: stessa riga aggiornata;
- DDT non più restituito oltre finestra: riga conservata;
- OL inizialmente vuoto e poi valorizzato: una sola segnalazione riconciliata;
- due job contemporanei: nessuna doppia importazione.
- ultimo tentativo fallito ma snapshot precedente valido: dati invariati e avviso visibile;
- ripristino eSolver: recupero automatico delle righe ancora disponibili e rimozione dell'avviso;
- stato giallo/rosso calcolato dalla data dell'ultima lettura completa riuscita, non dalla semplice apertura della pagina.

### Identità

- stesso DDT, più OL;
- stesso OL, più DDT;
- stessa riga documento, più OL;
- stesso documento/riga/OL ma lotti differenti;
- DDT senza OL;
- correzione eSolver ambigua: nessuna unione automatica.

### Stato Incoming

- Incoming completo;
- Incoming incompleto;
- accettato con riserva;
- respinto;
- CDQ mancante;
- più righe Incoming collegate allo stesso OL.

### Certificazione

- nessun Word;
- Word preparato prima del DDT;
- draft con DDT;
- PDF finale esatto;
- PDF finale di un altro DDT dello stesso OL;
- PDF finale di un altro OL dello stesso DDT;
- PDF annullato o riaperto;
- nuovo DDT dopo PDF precedente;
- record finale legacy senza identità precisa: non chiudere automaticamente una riga ambigua.

### UI

- badge uguale ai contatori API;
- apertura pagina non chiude le righe;
- filtri combinati e paginazione;
- navigazione alla specifica unità;
- righe senza OL non aprono un OL inventato;
- storico completati ed esclusi;
- layout con dati lunghi e quantità grandi;
- messaggio e timestamp in caso di eSolver non aggiornato.

### Regressioni

- filtri attuali di Certificazione;
- `Nascondi completati`;
- `Solo certificati da fare`;
- `Altri Word da preparare`;
- selezione standard;
- generazione Word;
- chiusura e riapertura PDF;
- Registro certificazione;
- flusso Incoming e valutazione qualità.

## Criteri di accettazione

La funzione è accettabile quando:

1. ogni nuova unità eSolver con OL compare entro il ciclo di sincronizzazione previsto;
2. una riga non scompare attraversando il limite temporale eSolver;
3. stessa DDT con OL differenti produce lavori indipendenti;
4. stesso OL con DDT differenti produce lavori indipendenti;
5. il PDF finale chiude esclusivamente la propria unità;
6. annullare il PDF fa ricomparire la segnalazione;
7. draft e Word non chiudono la segnalazione;
8. le righe senza OL sono visibili e non collegate automaticamente;
9. errori eSolver non cancellano né completano elementi;
10. nessuna logica esistente di Incoming, standard, Word, PDF o registro cambia senza richiesta esplicita.

## Decisioni ancora da confermare con il proprietario

Prima dell'implementazione finale chiedere conferma solamente sui punti che incidono sul comportamento:

1. importare in Alpha anche tutto lo storico recuperabile oltre la finestra eSolver oppure partire solo dai DDT correnti;
2. consentire `Non richiede certificazione` e a quali ruoli;
3. mostrare nel badge tutte le righe attive oppure solamente quelle pronte;
4. periodo visivo dell'etichetta `Nuovo`;
5. conferma da Matteo/eSolver del limite SQL esatto della vista, informazione utile ma non bloccante.
6. soglie temporali dell'avviso: dopo quante ore mostrare il giallo e dopo quanti giorni mostrare il rosso.

## Nota finale

Il punto architetturale non negoziabile è lo snapshot persistente e indipendente dalla paginazione. Limitarsi ad aggiungere una nuova pagina sopra `quarta_taglio_esolver_links` manterrebbe il rischio attuale: righe non ancora visitate non memorizzate e DDT incompleti che possono sparire quando escono dalla finestra eSolver.

## Esito test locali della fase 1

Verifica finale: **76 test superati** e **2 test PostgreSQL saltati nella suite offline**, già eseguiti separatamente e superati su PostgreSQL 16 locale temporaneo. Totale: 78 casi distinti verificati. Rimangono solo avvisi di deprecazione delle dipendenze SWIG già utilizzate dal progetto.

Comando offline dalla radice del repository (usare l'interprete locale con le dipendenze backend installate):

```powershell
$env:PYTHONPATH = 'backend'
python -m pytest backend/tests/test_quarta_taglio_ddt_snapshot.py backend/tests/test_quarta_taglio_esolver.py backend/tests/test_quarta_taglio_word_filters.py backend/tests/test_quarta_taglio_register_quantity.py backend/tests/test_quarta_taglio_quality_reservation.py backend/tests/test_esolver_export.py -q
```

I due test di integrazione si abilitano con `DDT_TEST_POSTGRES_URL`. Accettano esclusivamente host `localhost`/`127.0.0.1` e un database dedicato il cui nome inizia con `certi_ddt_test`; creano e rimuovono soltanto uno schema temporaneo proprio. Non usare il database applicativo. Il contenitore usa-e-getta utilizzato per il collaudo è stato arrestato e rimosso, senza volumi dell'app.

`git diff --check` superato. Nessun frontend modificato: build/UI da verificare nelle fasi successive.

### Attivazione ancora da fare

`DDT_SNAPSHOT_ENABLED` è disattivo per impostazione predefinita. Non è stato aggiunto alle configurazioni di deploy né impostato nei file `.env`. Prima dell'attivazione reale completare le fasi successive e predisporre esplicitamente il passaggio della variabile nel Compose dell'ambiente scelto; non basta aggiungerla al `.env` radice se Compose non la inoltra al backend.

La conservazione persistente riguarda i nuovi work item. Le pagine esistenti continuano a usare la cache precedente: il collegamento operativo allo storico, specialmente per certificare un DDT ormai uscito dalla vista eSolver, è ancora da implementare e testare. Salvare il DDT è il primo passo, non rende già disponibile il flusso completo.
