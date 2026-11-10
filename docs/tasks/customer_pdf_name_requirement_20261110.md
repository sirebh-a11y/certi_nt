# Requisito nome PDF particolare — 10/11/2026

## Decisione approvata

Spunta **Nome PDF particolare** nella pagina Requisiti cliente, modificabile
con i permessi Qualità/IT admin già esistenti. Non si compilano formati o nomi
automatici: chi genera il PDF sceglie il nome nel campo già disponibile.

Distinzione soltanto visiva sotto Cliente, nelle liste Certificazione e DDT:

- Solo il nuovo requisito -> `Nome PDF particolare` (ambra).
- Altri requisiti -> `Requisiti cliente` (rosso, esistente).
- Entrambi -> entrambi, compatti e a capo secondo lo spazio disponibile.

**Nessuna nuova distinzione nei filtri.** Il filtro esistente resta
Tutte/Con requisiti cliente/Senza requisiti cliente. Il solo nome particolare
è un requisito a tutti gli effetti. Stati, contatori, scadenze e sidebar invariati.
Il tag indica una richiesta, non il completamento della modifica del nome.

## Audit e connessioni

- Il nome esterno è già gestito da `ConfirmPdfDialog`, `pdf_file_name`, versione
  PDF, download ed export eSolver SQL/JSON. Non cambiare questa catena, né
  collegare il nome esterno al numero stampato dentro il certificato.
- Le schede sono per F3, con priorità esatta e poi famiglia senza ultime due
  cifre: conservati codici completi/zeri iniziali e schede inattive escluse.
  Nessun abbinamento per nome cliente, OL generico o Word Raw di altra lavorazione.
- Il tag generico attuale indica anche una scheda con sole note o vuota. Le
  vecchie schede conservano tale tag. Per una scheda con il nuovo flag attivo,
  le altre checkbox, i requisiti specifici o le note mantengono anche il tag
  generale. Le note non sono analizzate per dedurre automaticamente il nuovo flag.
- Più schede di famiglia restano alternative: etichette e dialogo non ne
  selezionano una arbitrariamente. Il dialogo PDF segnala il possibile requisito
  sul nome se presente tra le alternative, chiedendo di verificarne l'applicabilità.
- `CUSTOMER_REQUIREMENT_FIELDS` include il flag: compare anche nel dettaglio
  dei requisiti e nel riepilogo rosso già esistente nel dettaglio OL. Non attiva
  seconde pagine, non altera Word manuali o regole di ereditarietà.
- Il componente badge è condiviso tra le due liste, senza duplicare condizioni.
  Il filtro backend non è modificato: la presenza della scheda comprende già
  entrambi i tipi. Contratto test condiviso backend/frontend esteso ai casi solo nome.

## Finestra Genera PDF

La finestra condivisa dai DDT e dal Registro interroga `/customer-requirements`
in sola lettura ad ogni apertura usando il **F3 del certificato selezionato**.
Non si affida alla scheda rimasta in memoria nella lista; non cambia dati lato
server e non effettua chiamate AI o eSolver.

Sopra al nome, se richiesto:

> **Nome PDF particolare**
> Questo cliente richiede un nome PDF particolare. Verifica e modifica il nome prima di generare il PDF.

Il nome già scelto resta precompilato. Nessun obbligo di cambiarlo, nessuna
ulteriore spunta di conferma o finestra. Estensione, validazione nomi, annulla,
riprova dopo errore PDF e ripristino standard restano come prima.
Durante la breve lettura iniziale si attende prima di generare; timeout 10 s,
annullamento della richiesta alla chiusura, errore evidente/Riprova senza
blocco permanente. Un errore non viene presentato come assenza di requisiti.
Un retry dei requisiti non cancella il nome che l'utente sta scrivendo.

## Database e compatibilità

Nuovo booleano `customer_requirements.requires_custom_pdf_name`, non nullo,
default false nel modello e nello schema esistente via bootstrap ripetibile.
Nessuna attribuzione automatica a clienti o ricerca di parole nelle note/seed.
Schema API e CRUD aggiornati; le vecchie chiamate di aggiornamento che omettono
il nuovo campo **conservano** una scelta già salvata, anziché azzerarla.
Nuove creazioni senza campo -> false; checkbox inviata false -> viene rimossa.

Non modificare documenti, numerazione, file già chiusi, storage/UUID, token,
URL o vista export. Un normale rollback del codice non richiede di eliminare
la colonna o ripristinare i dati.

## Collaudo locale

- Unitari frontend: 56 passati, incluso contratto filtro condiviso, schede
  solo nome/altri/entrambe, note, vuote, inattive, F3 esatto e famiglia ambigua.
- Suite backend generale: 980 passati, 184 saltati per prerequisiti opzionali
  (PostgreSQL e rendering reale). Nessun errore. Le prove opzionali rilevanti
  sono eseguite a parte, su ambienti isolati.
- Suite mirata con PostgreSQL usa-e-getta: 43 passati, nessuno saltato.
  Include migrazione PostgreSQL/SQLite ripetuta, default e conservazione vecchie
  schede/spunte, compatibilità vecchio client, CRUD/permessi, filtro unico e
  azione PDF dalla quota corretta con nome personalizzato.
- Ripetizione finale con rendering LibreOffice reale attivo: 46 passati,
  1 saltato (la prova PostgreSQL, già superata nella suite dedicata). Incluse
  seconde pagine, allegati PDF, migrazione SQLite e filtro requisiti.
- Browser React reale con tutte le API simulate: tre casi visivi, note/vuote,
  inattive/ambigue, famiglia e zeri iniziali, filtro unico a tre scelte, clic
  senza navigazione, entrambe le finestre PDF, nome già personalizzato accettato
  senza modificarlo, lettura aggiornata ad ogni apertura, errore/Riprova senza
  perdere il nome, payload PDF esatto per quota, create/update e sola lettura.
- Riaperti e superati anche i tre collaudi browser preesistenti: requisiti OL,
  azioni requisiti/PDF DDT e dialogo nome PDF. Nessun errore JavaScript.
- Layout ispezionato su screenshot 1440/1920, finestra anche 600 px; tabella
  mantiene scroll interno, nessuna nuova colonna nelle due liste operative.
  Build production riuscita; restano solo gli avvisi preesistenti bundle e
  Browserslist, nessun aggiornamento dipendenze.
- Artefatti temporanei esclusi dal pacchetto: script
  `tmp_eval/packages_qa/custom_pdf_requirement_check.mjs` e screenshot
  `tmp_eval/custom-pdf-*.png`. Nessuna credenziale o documento reale usato.
- Vite temporaneo fermato al termine; PostgreSQL di collaudo e suo volume
  rimossi dopo averne verificato nome/etichetta/database/rete. Nessuna pulizia
  di container, documenti o cartelle appartenenti all'utente.

Solo sviluppo locale. Alpha e database operativo non modificati. Il collaudo
usa Vite temporaneo 5174: non riavvia i servizi abituali dell'utente. Commit,
push, aggiornamento dei servizi locali abituali e deploy seguono indicazioni
separate. Per Alpha vedere la nuova sezione del runbook di deploy, mantenendo
backup/restore, manutenzione, spazio e tutte le altre cautele già presenti.
