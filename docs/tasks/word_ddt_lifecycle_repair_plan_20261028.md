# Piano — integrità Word, righe DDT e chiusura PDF

## Stato e limiti di autorizzazione

28/10/2026: piano richiesto dopo audit locale e Alpha read-only; successivo
`procedi` per implementare e collaudare in locale. **Correzioni locali presenti;
nessun dato/documento Alpha modificato, nessun commit/push o deploy eseguito.**
L'implementazione locale, commit/push, deploy e recupero Alpha sono fasi distinte.
Questo documento non autorizza scritture sul server, adozioni massive o nuovi PDF.
Il deploy seguirà `../deploy/alpha_soft_update_server.md`, da integrare dopo il
collaudo con la procedura effettivamente implementata e verificata.

**Stato aggiornato dopo correzione R1–R3 e richiesta di preparazione deploy:**
correzioni software collaudate in locale. La revisione intermedia sotto descrive
problemi poi risolti, non difetti ancora aperti. Preparata anche la procedura
separata di recupero metadati, senza applicarla su Alpha. Nuovo inventario,
perimetro dei quattro riferimenti e sequenza operativa nel
[preflight 28/10](../deploy/alpha_word_preflight_20261028.md).
Restano necessari commit/push, approvazioni e nuova preview in manutenzione
prima del deploy/recupero; nessuna scrittura Alpha autorizzata dalla preparazione.

Prevalgono le regole concordate in
`word_reference_and_material_changes_resume_20261017.md` e
`../modules/quarta_taglio_word_inheritance_rules.md` (regola attuale Raw-first;
NON la catena alternativa proposta in quel documento).

**Estensione successiva richiesta dall'utente:** il recupero deve coprire l'intera
catena di identificativi, riferimenti e file generati, non il solo Word fonte.
I difetti creati dall'app devono essere prevenuti e recuperati dal software:
non demandare all'operatore ricaricamenti, adozioni o aggiustamenti manuali per
sanare metadati tecnici incoerenti prodotti da CERTI. Restano possibili messaggi
bloccanti per problemi reali non risolvibili con i dati disponibili (esempio:
certificato fornitore mancante), senza inventare dati o scegliere alla cieca.

## Evidenze e cause

1. Caricamento Word: il file principale viene pubblicato come riferimento,
   mentre la copia manuale separata viene già normalizzata. Il download del
   principale può normalizzarlo/aggiornare la struttura senza mantenere coerenti
   i metadati del riferimento. `choose()` segnala quindi `reference_file_changed`.
   Lo stesso rischio esiste nelle riscritture da Registro e nei download con
   ricostruzione degli allegati. Non è il semplice cambiamento DDT a provocarlo:
   i valori spedizione sono già esclusi dall'impronta tecnica.
2. Il selettore del dettaglio considera ambiguo il Word anticipato quando
   trova più righe per OL/F3, ma il worker può correttamente riutilizzarlo su
   ciascuna riga. Conta anche righe storiche/archiviate/escluse/completate.
3. Il Word fonte viene trovato senza essere rappresentato separatamente dal
   certificato della quota: il dettaglio mostra Nessun Word, ma ne impedisce la
   creazione perché il Word esiste. Le diagnosi d'integrità precise si perdono.
4. Nella conversione PDF i controlli successivi non provano sempre che il file
   convertito sia ancora quello selezionato: la modifica dello STESSO certificato
   di riferimento può passare, mentre quella di una fonte distinta è già coperta.

Audit Alpha del 28/10, fotografia da ricalcolare prima del deploy:

- OL2026001087/F3 449000700, fonte ID62, numero 7044_00_00/26, quota894,
  DDT2626-27/10/2026: `reference_file_changed`; Incoming pronto e dati DDT
  coerenti. Unico disallineamento d'impronta tra 50 riferimenti esaminati.
  File principale e manual base hanno gli stessi membri/contenuti DOCX; il
  principale è invariato rispetto al backup del 24/10. Non si dispone, da questo
  solo confronto, della prova della singola richiesta storica che cambiò il file.
- OL2026000986/F3 471000500, quote898/899 DDT2630-28/10/2026: errore di apertura
  per più quote. Il blocco materiale è invece reale: sono stati aggiunti CDQ e
  24-0985 manca in Incoming. Non autorizzare il riuso/PDF del vecchio contenuto.
- OL2026001148, quote895/896, certificati296/297: PDF chiusi, riferiti al proprio
  OL, 670 of 2257 e 1587 of 2257; nessun errore riscontrato nei riferimenti
  esaminati. Nessuna riscrittura o rinumerazione proposta.
- La criticità di conversione concorrente è riprodotta in locale; non è stato
  accertato che abbia prodotto PDF errati su Alpha.

### Estensione audit identificativi e documenti generati

Nuova fotografia Alpha READ ONLY: 304 record certificato (211 draft e 93 chiusi),
93 righe export. Esaminati collegamenti delle copie alla fonte/famiglia/revisione,
percorsi correnti e metadati, impronte delle copie, numero e DDT nei Word riusati,
identità/quantità delle quote con snapshot corrispondente, versioni PDF attive,
file presenti e identità esposte in export. Nei controlli svolti non sono emersi
ID fonte mancanti/scambiati tra OL/F3, numeri Word difformi dal record o identità
export difformi dal record. Non significa aver provato ogni dato tecnico dei file.

Riscontri aggiuntivi:

- ID268, OL1058/F3 520002360, e ID285, OL1025/F3 913001760: il metadato del
  riferimento conserva il percorso precedente, mentre il record punta al Word
  successivo. Sono PDF chiusi; numero e DDT stampati nei Word sono coerenti,
  vecchio/nuovo file hanno la stessa impronta tecnica e il riferimento è valido.
  È una mancata manutenzione del collegamento, non una prova di ID/Word scambiati.
- L'audit dei testi dei 93 PDF chiusi trova numero certificato, OL, F3 e DDT
  coerenti con i rispettivi record. Non è una verifica di tutta la chimica,
  meccanica, testo libero o impaginazione, né prova l'assenza di ogni errore storico.
- Nessun percorso Word principale attualmente condiviso da più record.
- Quattro gruppi condividono invece una base manuale, perché il nome della base
  è costruito sul solo numero certificato. Condivisioni censite:
  ID137/177/71; ID189/99; ID194/74; ID208/88/225. Non sono liste da bonificare
  automaticamente né prova che i PDF corrispondenti siano sbagliati.
- **Difetto ulteriore riprodotto localmente:** due documenti distinti con numero
  certificato uguale possono scrivere la stessa base manuale. Ricostruendo poi
  il primo Word per gestire allegati, la funzione usa la base scritta dal secondo:
  il contenuto manuale A è sostituito da B. La regola del numero condiviso tra
  righe dello stesso DDT è corretta; è errata la deduzione che ciò identifichi
  anche un'unica versione fisica di ogni Word. Riproduzione temporanea:
  `.tmp_server_audit/anomalia_20261028/manual_base_reproduction.py`.

### Contratto degli identificativi da preservare

- ID interno del certificato: stabile; non rinumerare chiavi primarie per
  riparare un'impronta o un percorso. È usato da PDF/versioni/allegati/export/link.
- ID fonte e revisione: devono descrivere la provenienza reale della copia;
  non sostituirli indiscriminatamente con il riferimento più recente. Un PDF
  chiuso può legittimamente conservare una revisione storica.
- Identità quota: OL/F3/documento eSolver/riga/lotto/ordine, con quantità distinta;
  non ricostruirla dal solo numero certificato o dal solo DDT.
- Numero certificato: distinto dall'ID interno. Progressivo per nuovo DDT;
  numero condiviso fra righe dello stesso OL/F3/DDT, senza fondere i documenti.
- File principale, base manuale, seconde pagine e allegati: identificarne
  proprietà/versione. Distinguere componenti volutamente comuni dal contenuto
  lavorato separatamente, senza cambiare la regola del Word completo riferimento.
- Dentro DOCX: preservare controlli automatici, relazioni di immagini/allegati e
  numeri sulle varie pagine. Gli identificativi interni XML sono locali al file:
  non rinumerarli globalmente o confonderli con ID database/numero certificato.

Riproduzioni locali, SQLite/file temporanei, nessuna conversione aziendale:
`.tmp_server_audit/anomalia_20261028/lifecycle_reproductions.py`.
Tre difetti confermati: vero upload seguito da download, apertura contro worker
discordante, chiusura dello stesso riferimento cambiato durante conversione.
Il convertitore nell'ultima prova è simulato: prova la guardia di pubblicazione,
non il rendering. Rendering/concorrenza PostgreSQL rientrano nel collaudo futuro.

Riesecuzione di baseline locale su `test_quarta_taglio_word_reference.py` e
`test_quarta_taglio_ddt_shipments.py`: 41 superati, 34 saltati (inclusi test
ereditati intenzionalmente esclusi e quelli con prerequisiti specifici). Questo
non dimostra la correzione: le tre riproduzioni sopra confermano che i difetti
sono ancora presenti. Rieseguire i casi PostgreSQL pertinenti prima di consegnare
l'implementazione, dichiarando separatamente quelli non eseguiti.

## Interventi software proposti, in ordine

### A — Un ciclo coerente di scrittura e integrità

- Censire e instradare tutte le scritture: generazione, upload, download,
  rigenerazione, seconde pagine, allegati/rimozione, aggiornamento Registro,
  riuso DDT, ereditarietà e aggiornamento materiali.
- Completare la normalizzazione prima di pubblicare un nuovo riferimento.
- Per una trasformazione automatica: verificare prima sorgente/metadati attesi,
  produrre un file nuovo, conservare il precedente e aggiornare coerentemente
  percorso/impronte solo dopo successo. Gestire rollback e file temporanei.
- La sola manutenzione di campi/impaginazione non crea una nuova pubblicazione
  utente e non promuove una copia DDT a riferimento. Le revisioni esplicite
  tecniche continuano invece ad aggiornare le copie ammissibili.
- Non azzerare le impronte né accettare qualsiasi mismatch. Un riferimento
  già discordante richiede diagnosi/recupero verificato, non riparazione nascosta
  al download. Non indebolire confronti di testi, firme, immagini e allegati.
- Evitare mutazioni in-place di documenti condivisi e preservare PDF chiusi.
- Isolare le basi manuali per documento/versione, senza usare il solo numero
  certificato come chiave fisica. Per i documenti legacy verificare la propria
  base dal proprio Word, rimuovendo solo le pagine PDF gestite e riconosciute;
  non fidarsi ciecamente di una base condivisa che potrebbe appartenere a un'altra
  copia. Conservare le basi precedenti e fermarsi se la ricostruzione non è certa.
- Verificare allo stesso modo i riferimenti di seconde pagine/allegati e tutte
  le copie discendenti: non considerare conclusa la correzione appena passa choose().

### B — Separare fonte OL/lavorazione e certificato della quota

- Distinguere nella risoluzione e nella risposta API il certificato ESATTO della
  riga DDT dal Word riutilizzabile come fonte, anche se non associato a un DDT.
- Una pluralità di righe DDT non è da sola una causa di ambiguità della fonte.
  La selezione usa le stesse regole di riferimento del worker/ereditarietà.
- Non limitarsi a cancellare il controllo o a restituire la fonte come
  certificato attivo: la funzione attuale serve anche alla creazione, che
  potrebbe riassegnare la base al DDT. La fonte deve restare indipendente.
- Conservare gli errori veri: identità/quantità cambiate, due certificati esatti,
  file mancanti, materiale/standard non coerenti, fonti tecniche discordanti.
- Aprire il dettaglio per diagnosi senza avviare scritture di recupero nella GET.

### C — Diagnosi e percorso utente raggiungibili

- Condividere codici causa tra coda, dettaglio e controlli PDF; tradurli in
  messaggi specifici, non nel solo elenco generico compatibilità/file/campi.
- Mostrare il Word fonte e l'accesso alla sua verifica senza presentarlo come
  documento già pronto della nuova quota; evitare doppioni e nuova creazione Raw.
- Per i casi validi l'app completa il riuso automaticamente: l'operatore non
  deve sistemare ID, impronte, percorsi, ricaricare lo stesso Word o adottarlo
  nuovamente per aggirare un difetto dell'app. I messaggi spiegano l'eventuale
  attesa automatica o il vero requisito mancante; non sostituiscono la correzione.
- Rendere raggiungibili Incoming e aggiornamento del Word/materiali, con i
  permessi e le conferme già concordati. Nessuna scelta ordinaria obbligatoria
  dell'utente a ogni nuovo DDT quando il riuso è ammissibile.
- Se fonte chiusa: mantenere il percorso già previsto che crea un riferimento
  aperto separato senza riaprire o riscrivere il PDF precedente.

### D — Fissare il documento effettivamente convertito

- Identificare il file preciso e lo stato atteso prima della conversione:
  certificato/quota, percorso, impronta, revisione e controlli già presenti su
  standard/materiali/DDT. Usare un input stabile per la conversione.
- Dopo la conversione, ricaricare lo stato e verificare sotto lock che sia
  ancora quello autorizzato. Coprire sia fonte distinta sia stesso riferimento.
- Se cambia qualcosa: non pubblicare il nuovo PDF in Registro/export, spiegare
  che il Word è cambiato e consentire di ripetere. Gestire i file temporanei
  creati da questa operazione, senza eliminare documenti aziendali precedenti.
- Considerare doppio clic/due conversioni concorrenti, riapertura/chiusura e
  rollback: non duplicare versioni attive o sovrascrivere esiti concorrenti.

## Regole da preservare e collaudo richiesto

Per ciascun blocco prima riprodurre il difetto, poi correggere, rieseguire il
caso completo e le regressioni. Se emergono ricadute, correggere in locale e
ripetere; non trasformare test verdi isolati in una garanzia sull'intero flusso.

- Upload di Word con formati reali/non già normalizzati → più download → PDF
  → DDT successivo → ereditarietà. Nessun falso cambio d'integrità.
- Stesso OL/F3: più righe dello stesso DDT e DDT diversi anche oltre 60 giorni;
  apertura prima del worker e con worker fermo per Incoming/materiali.
- Uno/due Word fonti, fonti equivalenti/discordanti, PDF chiusi, righe
  archiviate/escluse, identità/quantità cambiate e correzioni eSolver.
- Materiale nuovo, colata diversa, singolo materiale con lotti aggiunti e
  materiali multipli con pesi diversi: nessun allargamento dei controlli.
- Standard scelto/cambiato, conferme non conformità, chimica/meccanica/A50mm:
  nessun aggiornamento tecnico implicito o modifica delle regole normative.
- Raw prioritario; nessuna propagazione arbitraria da lavorazione40 a50;
  nuove lavorazioni ereditano seconde pagine, immagini e allegati validi.
- Copie automatiche aperte aggiornate quando previsto; modifiche manuali
  protette; operatore del Word e Quality Manager preservati.
- Due Word manuali diversi con uguale numero certificato: upload A/B, aggiunta
  e rimozione allegati, download e riuso non devono scambiare le basi. Controllare
  ID fonte, revisione, percorsi, allegati/versioni e collegamenti export dopo
  ogni passaggio, non soltanto il testo visibile o lo stato della coda.
- Numero dentro Word/PDF, nomi file standard/personalizzati e vista export
  coerenti: progressivo per nuovo DDT, stesso numero per le righe dello stesso
  DDT, quantità parte/totale limitata all'esatto OL/F3/documento.
- Concorrenza su PostgreSQL temporaneo: worker, upload, aggiornamento materiale,
  download, chiusura PDF. Errore/timeout conversione e rollback senza perdite.
- UI reale locale: coda, dettaglio, Registro, link fonte, messaggi, azioni e
  permessi. Rendering Word/PDF sintetico anche con seconde pagine/allegati.
- Suite backend/frontend pertinente e controllo del diff finale; verificare
  che acquisizione/matching Arconic/Metalba, sync eSolver/Quarta e contatori non
  siano cambiati. Dichiarare separatamente test passati, saltati e limiti.

## Piano separato e prudenziale per Alpha

1. **Nuova preview READ ONLY:** versione, stato/file/impronte e riferimenti,
   quote e PDF/versioni/export, materiali/standard, attività utenti/job, spazio.
   Non usare GET mutanti o generare PDF come prova. Le vecchie liste non sono
   autorizzazioni su dati che gli utenti potrebbero aver già corretto.
2. Preparare proposta con allowlist di ID/OL/F3, valori e hash prima/dopo e
   ragione di ogni scrittura. Distinguere metadato disallineato, Word tecnico
   superato e PDF realmente errato; nessun PDF è oggi accertato errato.
   La preview deve comprendere l'intera catena di fonti/copiedocumenti aperti e
   chiusi, identificativi quote, basi manuali, seconde pagine, allegati, versioni
   PDF e IdCerti export. Per ciascun elemento specificare: conservare, correggere
   il solo collegamento, creare/ripristinare la propria base, ricreare una copia
   automatica aperta o fermarsi per dati tecnici insufficienti.
3. Autorizzazione esplicita per deploy e interventi dati esatti. Finestra senza
   attività e writer/worker fermi; backup coerenti DB/storage/app, verificati.
   Non copiare il DB locale e non eseguire vecchie bonifiche del runbook.
4. Pubblicare la correzione collaudata. Al momento non è prevista una nuova
   colonna: riconfermare schema/metadati dopo l'implementazione. Nessun recupero
   generico nel bootstrap o a ogni avvio.
5. **OL1087/ID62:** ricontrollare Word completo, seconde pagine/allegati, standard,
   materiale, numero, origine e backup. Proporre solo il riallineamento tracciato
   del riferimento verificato, conservando file/metadati precedenti. Fermarsi
   se cambiano gli hash o non si dimostra quale documento conservare. Nessuna
   rigenerazione tecnica o PDF automatica per rimediare all'impronta.
   Dopo il recupero verificare e predisporre automaticamente la copia esatta
   della quota894 se ancora mancante e ammissibile. Conservare ID62 come fonte;
   l'eventuale nuovo ID della copia viene assegnato normalmente, non sostituito
   a quello della fonte. Verificare tutti i metadati del Word appena generato.
6. **OL986:** correggere l'accessibilità e la diagnosi, non forzare il materiale.
   Il certificato mancante/conferme devono essere risolti nel normale flusso
   utente. Solo dopo il Word va aggiornato con le conferme previste; nessuna
   creazione di contenuti tecnici inventati o adozione del vecchio materiale.
7. **OL1148 e PDF chiusi:** nessuna modifica proposta; confrontare record/file/
   versioni/export prima/dopo. Se in futuro si dimostra un PDF errato, predisporre
   una gestione separata con l'utente: mai sostituirlo silenziosamente.
   **ID268/285:** proporre nella preview soltanto l'eventuale allineamento del
   metadato percorso, con prove di equivalenza e conservazione di ID/numero/file/
   PDF/versioni/link export. Non farli sembrare nuovi PDF emessi né promuovere una
   nuova revisione tecnica. **Basi condivise:** valutarle per singolo documento;
   preparare basi indipendenti dai propri Word validati, non copiare l'ultima
   base comune su tutti e non rigenerare PDF già chiusi.
8. Eseguire soltanto gli interventi allowlist nella stessa manutenzione,
   verificando immediatamente precondizioni/hash sotto lock e idempotenza.
   Riattivare i normali automatismi approvati solo dopo controllo: il worker può
   predisporre nuove copie Word valide, non chiudere PDF per collaudo.
9. Confrontare dati/file protetti e quelli effettivamente autorizzati, export,
   servizi, contatori/diagnosi e sync. Segnalare differenze inattese e fermarsi
   prima di allargare l'intervento.
10. Recupero in caso di errore: file originali e metadati precedenti conservati;
    usare il perimetro minimo verificato. Non ripristinare un vecchio DB globale
    perdendo il lavoro successivo, né cancellare copie/DDT comparsi nel frattempo.

## Criterio di consegna

Non dichiarare concluso il lavoro prima di aver verificato il percorso utente
completo e le regole sopra. Prima consegnare esito locale, limiti residui e piano
Alpha aggiornato; attendere l'indicazione esplicita per commit/push/deploy e per
il recupero dati Alpha con la sua preview aggiornata.

## Implementazione locale del 28/10

- Normalizzazione upload prima della pubblicazione; guardia del file originario
  e manutenzione delle impronte/percorso per trasformazioni automatiche, senza
  promozioni delle copie o revisioni utente inventate. Cronologia dei precedenti
  percorsi automatici conservata nel JSON esistente.
- Download con aggiornamento dei soli controlli del Word completo: non rigenera
  pagina tecnica, firme, immagini e allegati. Copia su nuovo file solo quando
  cambiano davvero i campi, confrontati per tag (compresi valori da svuotare),
  non cercando un numero qualsiasi nel testo XML. File precedenti conservati.
- Basi manuali nominate con ID documento e versione del percorso Word. Nessuna
  modifica/cancellazione dei vecchi file condivisi: ricostruzione dal proprio
  Word quando serve una base indipendente, non riuso della base di un'altra quota.
- `certificate_for_saved_ddt` restituisce solo il documento esatto della quota.
  Fonte distinta nei campi API/link di diagnosi. Eliminato il falso conflitto per
  il solo numero delle righe DDT; protetti identità/quantità/duplicati reali.
  La ripetizione della POST di preparazione usa l'algoritmo del worker, non
  riassegna la fonte e non rigenera un nuovo Raw.
- PDF convertito da copia privata stabile; ricontrollo file/record/revisione
  sotto lock prima della pubblicazione. Cambiamenti concorrenti non pubblicano
  il PDF dell'operazione superata. I file temporanei non pubblicati vengono
  rimossi; un errore incerto durante commit richiede verifica, non cancellazioni.
  Lock OL → quota uniforme con il worker; modifiche esplicite rileggono il
  documento sotto lock prima di agire e non toccano PDF chiusi.
- Coda/dettaglio riportano cause specifiche; la fonte disponibile non è di per
  sé un errore e non viene descritta come Nessun Word. Nessuna riadozione
  obbligatoria per i normali DDT o per problemi di metadati creati dall'app.
- Aggiunti helper e CLI `audit_word_lifecycle` SOLO preview, testati su fixture
  isolate. Distinguono percorso obsoleto equivalente da impronta discordante e
  fonte mancante/di altra famiglia; censiscono le basi e i piani DDT. Non accettano
  automaticamente il contenuto di un file discordante. Nessuna modalità apply.
- Nessuna colonna aggiunta, aggiornamento dipendenze, modifica acquisizione AI,
  matching, filtri Incoming, norme, calendario, numerazione o export.

### Collaudo

Registrare sotto gli esiti finali dei sorgenti stabilizzati (non sommare le
riesecuzioni come test diversi). Nuovi casi reali di upload/download, più DDT
prima del worker, materiale mancante, due Word con stesso numero e basi diverse,
download ripetuti, preservazione corpo completo/firme, fonte non pubblicata,
preview senza scritture e vera sovrapposizione upload/conversione su PostgreSQL.

Le due fixture del convertitore sono state rese portabili Windows/Linux:
continuano a eseguire un processo Python reale con gli argomenti del convertitore;
non è stata modificata la configurazione LibreOffice del prodotto.

Browser locale React con API tutte simulate: fonte distinta da quota, link al
documento corretto senza parametro DDT, veri blocchi e azioni C/D preesistenti,
1440/1920px, nessun POST implicito o errore JavaScript. Frontend di collaudo 5174
separato; non è un test su Alpha e non richiede riavviare il frontend abituale.

Rendering sintetico con il convertitore dell'app in container Linux senza rete:
Word prima/dopo aggiornamento materiali, due pagine, tabelle popolate, immagine
incorporata e firme; entrambe le coppie di pagine ispezionate. Non sono stati
convertiti o chiusi documenti aziendali per collaudo. Artefatti privati temporanei
in `tmp_eval/word_lifecycle_render_20261028/`.

Prima del passaggio su Alpha: revisione Astra concordata, nuova preview sui
suoi dati e autorizzazione distinta. La correzione locale non equivale al recupero
di ID62 o delle basi/metadati storici: quelle scritture sono ancora da concordare.

### Esito finale locale

- Suite backend completa nel runtime Linux locale, rete disabilitata e sorgenti
  montati read-only: **720 superati, 111 saltati per prerequisito PostgreSQL**.
  Questi 111 casi sono stati eseguiti separatamente: **111 superati** su un
  PostgreSQL temporaneo dedicato in RAM, porta solo localhost, nessun DB CERTI.
- Dopo l'ultima rifinitura della guardia (fonte separata confrontata per contenuto
  tecnico/revisione, non per soli campi spedizione/percorso amministrativo) sono
  stati ripetuti i **13 casi PostgreSQL del nuovo ciclo**, tutti superati, oltre
  alla suite Linux completa. Nessun test PostgreSQL richiesto rimasto ineseguito.
- Concorrenza realmente esercitata con sessioni PostgreSQL distinte: upload
  durante conversione non chiude il vecchio PDF; worker concorrenti, numerazione,
  identità/quantità, snapshot e modifiche di riferimento restano protetti.
- **34 test frontend superati**, build riuscita. Avvisi preesistenti su
  Browserslist e bundle grande; nessun aggiornamento di dipendenze.
- Due collaudi browser React: nuova distinzione fonte/quota e azioni C/D già
  esistenti, API simulate, nessuna scrittura implicita/errore JS, 1440/1920px.
- Ulteriore prova sintetica end-to-end con convertitore LibreOffice reale
  dell'app: Word completo → nuovo DDT → PDF a due pagine → export. Numero
  `7013_00_00_01/26` e DDT corretti su entrambe le pagine, nome PDF personalizzato
  conservato, un solo record export per l'ID della copia, fonte originale invariata.
  In questa fixture il risultato del controllo conformità è controllato; non
  sostituisce le suite normative/meccaniche/chimiche eseguite separatamente.
- Tutte le immagini delle prove PDF prima/dopo e del ciclo completo ispezionate;
  nessun Word/PDF aziendale generato o modificato. Artefatti temporanei sotto
  `tmp_eval/word_lifecycle_render_20261028/` e `tmp_eval/word-lifecycle-*.png`.
- `git diff --check` senza errori. Nessuna modifica a requisiti/Dockerfile o
  configurazione operativa, nessun commit/push, nessun deploy e nessuna scrittura
  Alpha. Container temporanei rimossi automaticamente; frontend QA5174 fermato,
  servizi locali ordinari lasciati attivi.

**Passo successivo (aggiornato dalla chiusura R1–R3 sotto):** il recupero Alpha
resta separato dalle correzioni locali. La CLI consegnata è
intenzionalmente soltanto preview: l'apply
dei record/file storici selezionati richiede nuova preview Alpha, decisione e
collaudo della procedura puntuale prima di essere autorizzato/eseguito.

## Revisione finale Astra — 28/10/2026

Perimetro: diff locale, chiamanti e regole C/D, Raw-first, allegati, numerazione,
chiusura PDF e preparazione recupero. Solo fixture/documenti sintetici e DB
isolati; nessun accesso in scrittura a database/file aziendali. Riproduzioni
private in `.tmp_server_audit/anomalia_20261028/astra_review_repro.py`.

Rieseguite le quattro suite mirate (lifecycle, reference, reuse, shipments):
**75 casi SQLite e 72 PostgreSQL superati**. Il primo lancio PostgreSQL aveva
indicato `psycopg2`, non installato nel venv di collaudo; i 72 setup non erano
partiti. Rieseguiti tutti con `postgresql+psycopg` già installato, senza cambiare
dipendenze o codice. Le tre nuove riproduzioni sotto dimostrano percorsi mancanti
nelle suite, non vengono conteggiate tra quei test verdi. Il caso R1 è confermato
anche separatamente con due sessioni PostgreSQL reali. Container QA dedicato
usa-e-getta, in RAM e solo localhost; nessun servizio ordinario CERTI riavviato.

### R1 — PDF vecchio pubblicabile dopo un upload nuovo (priorità alta)

- La sincronizzazione Word fa commit e restituisce un percorso. Prima che
  `generate_quarta_taglio_certificate_pdf` rilegga il record e calcoli
  `conversion_state`, un altro upload può sostituire il Word del certificato.
- Il controllo fotografa il record/file NUOVO, ma il convertitore riceve il
  percorso VECCHIO restituito dalla sincronizzazione. L'hash dell'input congelato
  viene confrontato solo con quel vecchio file, non con il Word della fotografia.
  Il confronto finale passa perché il record nuovo non è più cambiato.
- Riprodotto prima in SQLite con vero upload e poi con **due sessioni PostgreSQL
  distinte**, upload reale tra commit della sincronizzazione e fotografia PDF.
  Esito: una versione PDF attiva, stato `pdf_final`, contenuto inviato al
  convertitore vecchio, Word corrente con il nuovo testo. Convertitore simulato:
  dimostra il difetto di selezione/pubblicazione, non l'impaginazione LibreOffice.
- Correzione proposta: acquisire sotto lock un'unica fotografia coerente di
  record, percorso, revisione e hash, congelando esattamente quel file. Se il
  percorso/versione restituito dal refresh non coincide, ripartire dai controlli
  sul nuovo documento o interrompere prima di pubblicare. Non accoppiare lo
  stato nuovo con il vecchio input. Mantenere controlli finali, doppio clic,
  snapshot, materiali e standard, senza tenere lock durante tutta la conversione.
- Nuovo test obbligatorio: la finestra PRIMA della conversione oltre a quella
  DURANTE già coperta; zero versioni/PDF/export del documento superato.

### R2 — Allegato PDF può eliminare pagine manuali ereditate (priorità alta)

- Raw completo con una pagina manuale incorporata; prima generazione della
  lavorazione successiva conserva correttamente la pagina e marca il Word
  `inherited`.
- Aggiungendo un PDF alla lavorazione con la vera funzione di upload allegato,
  `_rebuild_certificate_word_after_pdf_attachment` tratta `inherited` come un
  Word ricostruibile da zero. Il builder usa le pagine registrate separatamente,
  non la pagina manuale presente soltanto nel Word completo ereditato.
- Prova: il marcatore della pagina laboratorio è presente prima e assente dopo
  l'aggiunta dell'allegato; il Word diventa `generated`. Originale Raw e vecchi
  file restano conservati, ma il nuovo Word pubblicato è incompleto.
- Questo ramo era già presente prima del diff corrente: non è una regressione
  introdotta dalle nuove basi manuali, ma è una lacuna pertinente al ciclo che
  la prima consegna dichiarava coperto.
- Correzione proposta: per aggiunta/rimozione allegati preservare il documento
  completo ereditato, usando la propria base verificata e sostituendo soltanto
  le pagine PDF gestite. Non cambiare globalmente tutte le regole di `inherited`
  senza riesaminare rigenerazione e UI. Raw-first rimane invariato.
- Nuovi test: Raw con pagine incorporate e immagini → lavorazione → aggiunta e
  rimozione PDF → download → nuovo DDT → PDF; verificare contenuti, firme,
  relazioni immagini e impaginazione. Nessuna riscrittura dei PDF già chiusi.

### R3 — Copia completata con allegato non aggiorna più il totale DDT

- Una copia automatica (`ddt_reused`) viene completata aggiungendo un PDF:
  correttamente diventa riferimento esplicito (`word_reference.kind=reference`),
  ma conserva `word_source=ddt_reused`.
- Arriva un'altra riga dello stesso DDT/OL/F3. La quantità della quota non cambia,
  cambia solo il totale da stampare: nella prova, da `1398` a `1398 of 1698`.
- Il download entra nel ramo delle copie che ammette soltanto `kind=copy` e
  risponde 409 `Dati DDT diversi dal Word predisposto: verifica richiesta`.
  Nessun conflitto reale di identità/materiale è stato introdotto nella prova.
  Anche questo incrocio di classificazioni era già presente prima del diff.
- Correzione proposta: distinguere la provenienza iniziale dal ruolo attuale.
  Un documento completato/pubblicato può aggiornare i soli campi spedizione
  verificati mantenendo corpo, allegati, numero e revisione tecnica. Non togliere
  le protezioni delle copie lavorate separatamente o dei file non pubblicati.
- Nuovi test: aggiunta/rimozione allegati, nuova quota stesso DDT, download/PDF
  con totale aggiornato; stesso numero sulle quote, progressivo solo per nuovo
  DDT, documenti chiusi invariati. Verificare il ruolo dopo ogni azione esplicita.

### Effetto sul piano Alpha

Non risulta da queste prove che i tre percorsi abbiano già prodotto documenti
sbagliati su Alpha. **Non interpretare il precedente controllo numero/OL/F3/DDT
dei 93 PDF come verifica delle seconde pagine.** Prima di applicare recuperi:

- aggiungere alla preview la storia di origine/revisioni e i passaggi da Word
  ereditato a ricostruito dopo allegati; confrontare contenuti e pagine disponibili
  nei file conservati, senza attribuire a tutti i documenti un difetto ipotetico;
- cercare i riferimenti ancora etichettati `ddt_reused` con totale DDT cambiato;
  prevedere manutenzione dei campi, non rigenerazione tecnica o rinumerazione;
- per R1 non è sufficiente l'identità del numero: confrontare il contenuto del
  PDF con la versione Word pertinente dove le evidenze indicano sovrapposizioni;
- mantenere recupero puntuale, hash, backup, autorizzazione e protezione di tutti
  i PDF chiusi. Nessun nuovo apply, bonifica o deploy autorizzato dalla revisione.

## Chiusura locale R1–R3 — 28/10/2026, dopo il «procedi»

Le tre riproduzioni sono state prima trasformate in test fallenti sul codice
precedente, poi corrette. Questa sezione aggiorna lo stato della revisione sopra;
non cancella le cause e non dichiara riparato alcun documento Alpha.

- **R1:** dopo il commit della sincronizzazione si riacquisisce il lock OL e si
  verificano insieme record, percorso, revisione e impronta del Word. L'input
  privato passato al convertitore deve avere esattamente l'impronta di quella
  fotografia. Un upload nella finestra precedente non può autorizzare il vecchio
  input con lo stato nuovo. Il lock viene rilasciato prima di LibreOffice;
  ricontrollo finale e doppio clic restano protetti. Il conflitto reale richiede
  di riprovare la generazione, non di ricaricare o correggere documenti a mano.
- **R2:** aggiungere/togliere PDF su un Word `inherited` mantiene il corpo
  completo, immagini, pagine incorporate e firmatari originari. Non si cambia
  globalmente la classificazione dei Word ereditati né la priorità Raw.
  La prova visiva ha inoltre scoperto la sezione vuota residua dopo la rimozione:
  ora si ripristina la sezione precedente quando viene tolta la coda PDF.
  La rimozione riconosce le coppie marcatore/immagine gestite dall'app, non taglia
  indiscriminatamente tutto ciò che segue: eventuali pagine manuali successive
  vengono conservate. Coperti anche i titoli allegato legacy e la ripetizione.
- **R3:** un documento nato `ddt_reused` ma pubblicato come riferimento non viene
  scambiato per una copia automatica ancora sostituibile. Può aggiornare i soli
  campi spedizione verificati senza perdere allegati o cambiare revisione tecnica.
  Esempio collaudato: quota 91, arriva quota 29 dello stesso DDT → `91 of 120` e
  `29 of 120`, stesso numero; un DDT diverso conserva la regola del progressivo.
  Restano i controlli di impronta, identità, standard, materiale e PDF già chiusi.

### Evidenze aggiuntive e limiti

- Suite backend completa ripetuta sul codice corretto nel runtime Linux isolato:
  **725 superati, 116 saltati perché richiedono PostgreSQL**. Eseguiti tutti i
  116 separatamente sul database temporaneo dedicato: **116 superati**, nessun
  caso PostgreSQL richiesto lasciato ineseguito. **34 test frontend superati**
  e build riuscita in cartella QA, senza riavviare il frontend ordinario.
  Restano solo warning preesistenti di deprecazione, Browserslist e bundle grande.
- Sessioni PostgreSQL reali e separate: upload sia dopo il sync/prima del pin
  sia durante conversione; nessuna versione obsoleta pubblicata. Due PDF
  contemporanei sullo stesso Word: una sola versione finale, output concorrente
  non utilizzato rimosso. Il convertitore è simulato in queste prove di gara.
- Rendering LibreOffice reale separato, nel runtime dell'app senza rete:
  documento ereditato di 2 pagine → 3 con PDF → 2 dopo rimozione → 2 sul nuovo
  DDT. Il riferimento riutilizzato con totale `91 of 120` resta a 3 pagine con
  laboratorio e PDF allegato. Controllati contenuto, immagini, firme, numero,
  nome personalizzato e righe export delle sole copie; Raw originale invariato.
  Le fixture hanno conformità controllata e non sostituiscono le suite normative.
- Verificata anche una pagina manuale aggiunta DOPO il PDF: eliminando l'allegato
  restano le due pagine originali e quella manuale, senza pagina vuota intermedia.
  Il test delle azioni reali copre inoltre due PDF aggiunti e rimossi uno alla
  volta: l'allegato ancora presente e le immagini manuali non vengono persi.
- Verifica visiva eseguita sulle immagini dei PDF, non soltanto sul testo estratto.
  Artefatti sintetici privati: `tmp_eval/r123_render_20261028/`.
- Il primo test della sezione confrontava anche gli ID amministrativi `rsid`
  che python-docx rimuove nella clonazione: corretto il test per confrontare
  impostazioni, margini e relazioni header/footer, non quegli ID di sessione.
  Il primo setup del doppio PDF ricalcolava la conformità fittizia fuori dal mock:
  stabilizzata la fixture, senza indebolire le guardie di prodotto.
- Nessun documento aziendale, database locale CERTI o file Alpha usato in
  scrittura. Nessuna nuova dipendenza, migrazione, modifica ai servizi operativi,
  commit/push o deploy. La CLI rimane soltanto preview: l'apply storico non è
  implicitamente autorizzato e non è incluso in questa chiusura locale.

## Preparazione successiva del deploy — 28/10/2026

Su richiesta successiva dell'utente è stata preparata la CLI separata
`recover_word_lifecycle_alpha`: non cambia la natura preview-only del comando
di audit e non viene chiamata dall'app. Perimetro proposto: soli metadati dei
record 62/268/285/308, senza riscrivere Word/PDF o cambiare ID e numeri.
Dopo l'eventuale recupero metadati, una nuova preview deve confermare il solo
riuso della quota894; nessuna creazione della copia eseguita ora su Alpha.

Preparazione verificata con 732 test generali backend, 126 PostgreSQL dedicati,
34 frontend e build riuscita. I 7 nuovi casi SQLite del recupero, già inclusi
nei 732, sono stati ripetuti insieme ai 126 PostgreSQL (133 successi).
L'audit Alpha aggiornato ha trovato 312 certificati/98 PDF, tre vecchi percorsi
equivalenti invece di due. Identità testuali dei 98 PDF coerenti; non è una
certificazione integrale dei contenuti storici. Nessuna nuova evidenza di
pagine errate che autorizzi una rigenerazione retroattiva.

Sequenza, spazio, allowlist, limiti e comandi nel
[preflight 28/10](../deploy/alpha_word_preflight_20261028.md).
Nessuna scrittura su Alpha, nessun commit/push o deploy eseguito nella preparazione.
