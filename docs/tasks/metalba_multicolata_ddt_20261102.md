# Metalba: DDT multipagina e multicolata – 02/11/2026

## Perimetro

Implementazione autorizzata **in locale**, con audit prima/dopo e prove estese.
Nessun commit/push/deploy autorizzato da questa attività. Alpha e il database
dell'app locale non sono stati modificati. Nessuna nuova colonna o migrazione DB.
Implementazione locale completata e verificata; Alpha resta invariata.

## Caso e causa

DDT `26-03514`, tre pagine: una posizione commerciale da 22.075 kg e una lista
imballi sulle pagine 2/3, con 28 colli, 524 pezzi e tre colate:

| Colata | Certificato fornitore | Netto kg |
| --- | --- | ---: |
| 26246A | 26-2727 | 2.143 |
| 26257A | 26-2728 | 9.954 |
| 26258A | 26-2729 | 9.978 |

Su Alpha il PDF è completo e tutte le immagini erano state preparate; il codice
invia tutte le pagine. Non è conservata la richiesta HTTP storica integrale.
L'evidenza AI registrata sulla riga originaria contiene solo il totale di testata
e non le tre colate. Prompt e ricostruzione Metalba non contemplavano
esplicitamente questo formato; inoltre la colata raw non arrivava al candidato
normalizzato né a tutti i controlli di abbinamento.

Il cliente ha già sistemato e validato le righe Alpha 290/295/296, collegate allo
stesso DDT401 e ai certificati407/408/409. **Non correggerle, duplicarle o rileggerle
automaticamente.** Il DDT401 è protetto come documento con intervento manuale.

## Soluzione locale

- AI: trascrizione distinta di posizioni commerciali, colli stampati e totali;
  tutte le pagine, anche continuazioni; annotazioni a penna escluse come prima.
  Una sola immagine per pagina, non due invii sotto ruoli diversi.
- App (`metalba_packing.py`): raggruppamento per posizione e colata, somme
  Decimal, controllo di netto/pezzi/numero colli disponibili e copertura delle
  posizioni. Dedup per ID collo o posizione nella pagina; ID discordanti fermano
  il documento. Colli distinti di peso uguale non sono eliminati.
- Nessuna somma di riepiloghi, attribuzione di residui a una colata, distribuzione
  proporzionale o creazione di righe dal solo totale quando il packing è incompleto.
- Contraddizioni stampate tra collo e posizione (articolo, ordine, lega,
  diametro, lunghezza) escluse, senza esigere campi assenti nel documento.
- Completezza immagini prima dell'AI; manifest delle pagine nella risposta.
  Una sola rilettura semantica del DDT corrente se il controllo fallisce; dopo
  due risposte incoerenti errore specifico, non retry generico del worker.
  Gli altri documenti del batch continuano sul percorso esistente.
- Risultati verificati riusati nella sessione per le righe dello stesso DDT,
  invalidabili al cambio di hash/pagine. Inoltre, solo per i nuovi DDT automatici,
  lettura verificata salvata prima della prima riga come evidenza documentale
  `metalba_ddt_groups_v1` nella tabella già esistente. Un salvataggio interrotto
  riparte dai gruppi salvati, anche in una nuova sessione, creando solo le righe
  mancanti e recuperando quelle parziali identificabili senza ambiguità.
  Nessuna scansione AI dello storico o promozione dei manuali a lettura globale.
- Colata conservata con evidenza di origine DDT fino a salvataggio, identità
  riga, associazione nei due ordini di arrivo, scoring/riletture e preview.
  Non trattare la colata copiata dal certificato come evidenza indipendente DDT.
- Contraddizioni di colata escludono candidati anche con pesi simili. Il bonus
  colata discrimina **solo candidati già idonei con le soglie materiali precedenti**.
  Sui nuovi gruppi multicolata non accettare un certificato senza la colata necessaria
  a distinguerlo. DDT ordinari senza colata conservano i requisiti precedenti.
- Identità dei nuovi gruppi comprende posizione/articolo/lunghezza per non
  sopprimere materiali diversi con stesso peso e colata. Riassegnazioni tra
  gruppi e righe esistenti soltanto con miglior candidato univoco in entrambi i sensi.
- Lettura e creazione di tutti i gruppi Metalba serializzate per documento,
  riusando il lock multiprocesso già presente per le letture: due worker non
  devono leggere e creare due volte lo stesso DDT. Nessuna modifica ai lock
  degli altri fornitori o allo schema.
- Manuali/confermati/validati, sganci, campi interni, alias `6082F`/`6082F F`/
  `6082FF` e LST03 restano protetti. Nessun cambiamento ai prompt certificato,
  chimica, meccanica, Word/PDF, dati eSolver o numerazioni certificati.
  Più righe di prove meccaniche dello stesso certificato NON sono nuovi documenti.

## Prove

Esito conclusivo: **838 test superati, 127 opt-in non eseguiti**, 965 totali,
zero fallimenti/errori. Inclusi 48 test Metalba dedicati e 28 PostgreSQL
(17 Metalba e 11 riuso/concorrenza esistenti) nei soli database temporanei.
I messaggi di errore/retry nei log della suite sono scenari simulati attesi.
Nessuna regressione rilevata nei percorsi coperti; non è una garanzia su qualsiasi
formato futuro o una verifica operativa su Alpha.

`backend/tests/test_metalba_packing.py`: aritmetica del caso reale, ultima pagina
mancante, colli duplicati/conflittuali, pesi uguali, quantità mancanti, materiali
diversi con stessa colata, formati numerici, DDT senza packing, retry limitato,
cache di sessione, provenienza, soglie precedenti, protezioni e flussi di
creazione/riavvio/DDT-prima/certificati-prima. PostgreSQL opt-in limitato a
`127.0.0.1:55439/certi_ai_reuse`, schemi UUID; nessun DB applicativo ammesso.

Test AI autorizzati entro 1 EUR, effettuati solo da QA locale con immagini
mascherate e DB SQLite isolato: tre chiamate, tutte completate al primo tentativo
per ciascuna prova. Caso 3 pagine ripetuto anche con il prompt finale: 28 colli,
tre pesi corretti e matrice 3x3 con soli tre abbinamenti corretti. Altro caso
reale `26-00960`, due pagine e una colata: 1.334 kg, 26052B, ordine45/26,
diametro48, lega6082F F conservata. I certificati del primo caso sono stati
confrontati usando JSON già letti, non rimandati all'AI.

La risposta reale del prompt finale è stata inoltre riapplicata, senza rete,
alla revisione conclusiva del codice: cinque flussi integrazione superati
(creazione, certificati-prima, DDT-prima, interruzione parziale e nuova sessione).
Il riuso dei manifest/evidenze prima della creazione è stato collaudato sia su
SQLite sia su PostgreSQL, senza abbassare le soglie materiali preesistenti.

Consumo totale 27.025 token input e 8.674 output; stima 0,395345 USD ai prezzi
del [modello GPT-5.5](https://developers.openai.com/api/docs/models/gpt-5.5).
Contabilizzazione prudenziale 0,632552 EUR, includendo un margine di conversione,
imposte e pagamento: non è una fattura né un cambio valutario aggiornato.
Nessun altro test pagato implicito. Chiavi solo in memoria, mai nei report.

Build frontend riuscita, senza modifiche UI; warning Browserslist obsoleto e
dimensione bundle preesistenti, nessun aggiornamento dipendenze automatico.
Backend locale con bind mount/ricaricamento automatico verificato: startup
completato senza errori e `GET /api/health` restituisce `{"status":"ok"}`.
Nessun riavvio manuale dei quattro container applicativi effettuato.

Report JSON/immagini e risposte AI sono sotto `tmp_eval/incoming_anomaly_20261102`
con ACL riservate, **da non committare/distribuire**. Script QA sotto
`.tmp_server_audit`, non necessari all'app. Preservare i documenti originali.
PostgreSQL temporaneo `certi-metalba-packing-qa-20261102` rimosso dopo i controlli,
verificando ID/etichetta e assenza di volumi persistenti. Eliminati solo i dati
usa-e-getta dei test, ricreabili dalle fixture; quattro container locali dell'app
e relativi dati lasciati attivi e intatti.

## Futuro Alpha

Seguire [runbook Alpha](../deploy/alpha_soft_update_server.md). Distribuire
insieme `service.py` e **il nuovo modulo `metalba_packing.py`**, non un overlay
del solo service. Nessuna preparazione schema, reset cache, backfill, copia del
DB locale o bonifica dei DDT vecchi. Nessuna modifica dei documenti401/407/408/409.
Eventuali altri storici incompleti richiedono inventario e approvazione separati.
Rollback del codice senza cancellare righe nuove o evidenze; il codice vecchio
resta affetto dai limiti documentati. Aggiornare commit/pacchetto ed esiti solo
quando l'utente autorizzerà commit/push e successivamente il deploy.
