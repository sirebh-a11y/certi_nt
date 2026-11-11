# Leichtmetall Piano per certificati con più lotti

## Stato e obiettivo

Implementazione in sviluppo locale autorizzata dall'utente l'11 novembre 2026,
con verifica dei casi DDT prima, certificato prima e insieme. Implementazione
locale completata e collaudata; non pubblicata su Alpha. Le sezioni di proposta
e audit iniziale restano come traccia delle decisioni, non come lavoro pendente.
Nessun deploy o recupero storico autorizzato implicitamente.

Un certificato Leichtmetall può coprire più lotti del DDT. Il documento resta
uno; Incoming deve conservare una riga per ogni gruppo materiale effettivo del
DDT, con il peso di quel gruppo, collegandola allo stesso certificato quando
la copertura è dimostrata. Non basta correggere il numero: vanno allineati
abbinamento, conferme, rematch e collegamento con Quarta.

## Evidenze confermate su Alpha

Audit del 10 novembre con transazioni PostgreSQL READ ONLY, timeout e nessun
endpoint applicativo mutante. Verificati 46 documenti, 23 righe Incoming,
5 casi con identificativo composto. All'audit, il codice dei cinque moduli
pertinenti installati su Alpha aveva lo stesso AST della baseline locale,
prima di questa implementazione; i file differivano nella rappresentazione
testuale, non nella logica Python confrontata.

Caso principale, DDT 80011293, documento 432, certificato 437:

- Certificato stampato `95131.33`, peso totale 5.047 kg, diametro 150 mm.
- Packing list: lotto 95131, 3.962 kg; lotto 95133, 1.085 kg. Totale 5.047 kg.
- La lettura AI salvata contiene entrambi i lotti/pesi e il nome completo.
- Nella baseline, parser AI e parser locale conservavano solo 95131. Il confronto ordinario,
  l'arrivo prima del certificato e il rematch rifiutano correttamente il peso
  del singolo lotto contro il totale, ma non riconoscono la relazione di gruppo.
- La riga 310 è stata poi corretta manualmente a `95131.33` e 5.047 kg;
  i log mostrano DELETE della riga 311. La situazione attuale non dimostra
  una perdita di lettura AI del secondo lotto.

Altro caso verificato visivamente: DDT 80011124 e certificato `95131.32`,
5.361 kg. Il packing distingue 95131 per 2.550 kg e 95132 per 2.811 kg.
Le altre identità composte osservate sono `95088.90`, `95089.90`, `94967.68`.
Quattro letture AI conservano il composto nel JSON originale ma lo troncano
nel risultato normalizzato; `94967.68` comprende dati manuali protetti.

Quarta usa già CDQ e colata composti: OL1121 `95088.90`, OL1150/1152
`95089.90`, OL1243/1356 `94967.68`, OL1353 `95131.32`.
Esistono Word e un PDF chiuso collegati a questi riferimenti. Nessuna correzione
automatica dello storico deve essere dedotta da questo elenco.

Nei PDF controllati la chimica riporta «Average of 2 batches»: è un dato comune
del certificato, non due misurazioni individuali da inventare.

Le evidenze locali sono in `tmp_eval/leichtmetall_audit_20261110/`: snapshot,
relazioni, sei originali con SHA256 verificato, PNG e riproduzione offline.
Sono file privati di collaudo, non un database da copiare su Alpha.

## Regola proposta per identità e pesi

Separare tre concetti senza aggiungere colonne alla lista Incoming:

1. Numero originale del certificato, per esempio `95131.33`.
2. Lotti coperti, per esempio 95131 e 95133, con provenienza verificabile.
3. Lotto e peso della singola riga DDT, per esempio 95133 e 1.085 kg.

Regola precisata e approvata dall'utente l'11 novembre: sulle nuove righe
abbinate **CDQ e colata completi** del certificato, come Quarta (`95131.33`),
e peso specifico del lotto DDT. Il lotto specifico resta nei ReadValue originali
del lato DDT, non viene cancellato né sostituito dal riferimento comune.
Nel Match i due lati restano distinguibili: DDT 95133 / certificato 95131.33
non è una discordanza quando appartenenza e totale sono stati verificati.

Ripetizioni di colli dello stesso lotto si sommano soltanto se appartengono
allo stesso materiale e ordine. Stesso lotto con diverso diametro, lega,
ordine o prodotto resta distinto. Il numero delle righe non deriva dal
numero di punti nel certificato né dal numero dei colli.

Il totale del certificato non sostituisce il peso della riga, non si replica
su tutte le righe e non si divide in parti uguali o per differenza residua.

## Interventi software proposti

### Identità composta senza alterare gli altri fornitori

Creare una funzione Leichtmetall comune a parser AI, parser locale e confronti.
Conservare il testo integrale e ricavare una lista esplicita di lotti solo da
una scrittura riconoscibile e verificata nel contesto documentale.

`95131.33.35` indica come ipotesi di lettura i tre numeri 95131, 95133, 95135:
non include automaticamente 95132 e 95134. L'espansione richiede riscontro
nei lotti DDT. Numeri completi ripetuti, spazi e separatori OCR vanno provati;
slash, trattini e intervalli non diventano liste per semplice sostituzione.
Non usare nome file, sottostringhe, vicinanza numerica o primo numero come ripiego.

Il risultato deve distinguere internamente singolo, gruppo verificabile e
composto dubbio. Un composto dubbio non deve ricadere nel parser generico che
ne prenderebbe soltanto il primo lotto. Il caso singolo continua come prima.

### Un unico controllo del gruppo in tutti i percorsi

Prima di assegnare un certificato comune verificare stesso fornitore,
appartenenza esplicita dei lotti, compatibilità del materiale e unicità della
scelta nell'ambito del DDT. Ordini, diametri o leghe discordanti restano blocchi.
Mai scegliere il primo candidato in caso di parità.

Quando il certificato dichiara un totale, confrontarlo con la somma dei soli
gruppi coperti nel DDT, con unità esplicite e tolleranza documentata; non con
ogni singola riga. Il totale generale del camion può includere altri certificati.
Non confondere virgole delle migliaia con decimali o convertire due volte kg/tonnellate.
Non allargare le tolleranze globali per far tornare i conti.

Se il totale del certificato è assente, non inventarlo: permettere l'automatismo
solo con appartenenza, ordine, lega e diametro completi e univoci e dettaglio
DDT verificato. Se manca anche l'ordine, richiedere materiale completo e un
riscontro aggregato indipendente sul peso; altrimenti lasciare il caso da verificare.
Una contraddizione presente non diventa mai un dato «mancante» per aggirare il controllo.

La stessa decisione di gruppo deve essere usata da:

- scorer iniziale dei certificati e assegnazione dopo la lettura del DDT;
- ricerca con certificato arrivato prima o dopo, e split automatico DDT;
- anteprime di collegamento e azione manuale già esistente;
- bridge/rematch, controllo conflitti tra i due lati e conferma del match;
- verifica successiva di un collegamento già presente.

Non basta cambiare `score_bridge_match` o aumentare un punteggio. Non togliere
globalmente il controllo del peso o il vincolo sul multi-link già usato dal
collegamento manuale: la nuova eccezione automatica richiede la prova del gruppo.
L'aggancio deve concludersi anche nello stesso run, non attendere un caricamento
successivo né ampliare indiscriminatamente l'eccezione Arconic nei protetti del run.

### Righe e salvataggi coerenti

Il database ammette già lo stesso documento certificato in più righe. Salvare
il contesto del gruppo con provenienza e revisione, usando dove possibile le
evidenze versionate esistenti: documento/hash, DDT, membri, pesi, ordine e
materiale. Non usare il solo CDQ come identità o un nuovo campo visibile.

Vincoli da dimostrare nel prototipo locale prima di confermare l'assenza di
migrazioni DB: il contesto deve essere recuperabile, invalidabile e verificabile
dopo un riavvio. Se serve uno schema dedicato, aggiungerlo al piano per approvazione,
non introdurlo come dettaglio nascosto durante il deploy.

Unione della riga solo certificato una sola volta, mantenendo prima una fonte
comune valida per tutti i membri. Nessuna quarta riga superflua dopo un gruppo
di tre lotti completo. Lock ordinati sui documenti/righe interessati, controllo
delle revisioni prima della scrittura e operazione ripetibile: due worker,
doppio clic o ripartenza non duplicano righe, collegamenti, peso o documenti.

Non usare una firma basata solo su peso o nome; non ricreare automaticamente
una riga eliminata volontariamente dall'utente. Le letture DDT già salvate
conservano il proprio ruolo nel recupero da un salvataggio incompleto.

### Non riscrivere le fonti per farle coincidere

Oggi `_sync_row_from_match_values` può portare il CDQ completo sulla riga,
mentre `_sync_match_values_from_row_fields` può riportare campi della riga
nel lato certificato durante modifiche o refresh. Nel nuovo contesto di gruppo
evitare che il peso/lotto singolo sovrascriva totale/elenco del certificato,
o che il refresh del certificato riunisca i pesi separati del DDT.

Una correzione dell'utente che renda incompatibile il lotto deve invalidare
la prova del collegamento di quella riga. Lo sgancio esplicito e i blocchi
manuali restano efficaci: nessun riaggancio automatico, né modifiche alle altre
righe per rendere artificialmente coerente il dato corretto.

Dati tecnici del certificato condivisibili non significano validazione qualità
automatica di tutti i lotti. Non copiare indiscriminatamente accettazione,
date, riserve, respinti o numero colli da un membro agli altri.

### Quarta e certificazione senza cambiare lo storico

Mantenere i riferimenti originali ricevuti da Quarta, senza modificarne il DB
o fabbricare nuovi codici. Aggiungere una risoluzione applicativa del gruppo
solo per documenti Leichtmetall con copertura verificata; il percorso esatto
attuale resta per singoli e righe storiche senza nuovo contesto.

Se Quarta cerca `95131.32`, deve poter ricondurre il materiale al certificato
comune e alle righe dei lotti necessari, senza scegliere il primo membro.
La quantità usata dall'OL può essere una parte del materiale ricevuto: non
imporre che coincida col peso totale DDT. Soglie, qualità e distinzione per
articolo/diametro non vanno aggirate aggregando righe estranee.

Se la richiesta Quarta non identifica quale membro del gruppo sia stato usato,
non attribuirlo artificialmente. Si può validare la copertura comune soltanto
se tutti i membri possibili pertinenti sono coerenti e hanno superato i controlli
previsti; un membro respinto, mancante o ambiguo deve restare visibile e impedire
un falso verde. Richieste Quarta per lotto individuale usano soltanto quel membro.

Verificare riepiloghi, standard/chimica, apertura Incoming, generazione e riuso
Word, variazioni materiale OL, DDT da certificare, Registro ed export PDF.
Non moltiplicare nel Word l'analisi media come se fosse una prova separata.
PDF chiusi, numeri, nomi file e Word già approvati non si rigenerano per questa funzione.

## Fallback da preservare o rendere espliciti

- Solo certificato: una riga provvisoria del documento, totale dichiarato
  non suddiviso; al DDT completo si passa ai membri senza duplicare la fonte.
- Solo DDT: righe corrette per lotto e peso; attendono il certificato, non
  vengono accorpate per facilitare il match.
- Certificato arrivato dopo o storico già letto: usare la lettura salvata
  valida e ricavare il gruppo dal JSON originale, senza nuova AI per il solo
  cambio del parser e senza invalidare tutta la cache degli altri fornitori.
- Documento manuale: mai AI automatica. Può partecipare al confronto con
  dati manuali espliciti e confermati; non viene riclassificato o riscritto.
- Cache tronca senza originale affidabile o documento/hash cambiato: non
  inventare i membri da Incoming o dal nome file. Conservare il dato e segnalare
  la verifica del singolo documento, rispettando la politica di lettura già esistente.
- Pagine mancanti, pesi parziali/discordanti o separatore ambiguo: fermare
  l'automatismo del gruppo, non ripiegare su un solo lotto o su un totale copiato.
- Più certificati compatibili: nessuna scelta arbitraria. Numero uguale non
  supera differenze di ordine, diametro, materiale o documento.
- Certificato valido solo per parte dei lotti del DDT: non collegare quelli
  esclusi. Verificare separatamente ogni gruppo coperto.
- Copertura parziale su più DDT: non sommare consegne distinte per far tornare
  il peso. Senza un ambito documentale esplicito resta un caso da chiarire,
  non un'eccezione che disattiva i controlli.
- Dati manualmente corretti, validati o sganciati: niente bonifica automatica;
  invalidare solo eventuali prove derivate divenute incoerenti.
- Errore di un documento: il run deve continuare sugli altri senza doppie
  letture AI, cancellazione di righe sane o perdita di completamenti precedenti.

## Sequenza di implementazione proposta

1. Approvare comportamento e rappresentazione delle righe; partire soltanto
   in sviluppo locale con snapshot/copie e database temporanei.
2. Scrivere prima le prove dei due casi reali 95131.33 e 95131.32 e i casi
   negativi. Rendere esplicita la matrice dei fallback e il contratto del gruppo.
3. Implementare identità composta e recupero dalla lettura salvata, senza
   cambiare prompt generali o riaprire gli storici AI/manuali.
4. Integrare un'unica verifica nei percorsi di match e creazione/riuso righe,
   inclusi conferma, modifiche utente, sganci e ripartenze concorrenti.
5. Integrare Quarta e i consumatori della certificazione usando il contesto
   verificato, con regressione sugli OL citati e nessuna scrittura sul server.
6. Eseguire test trasversali, PostgreSQL isolato e prove visive con API simulate.
   Nuove prove AI a pagamento solo se necessarie e con budget autorizzato.
7. Solo dopo esito positivo aggiornare il runbook Alpha con codice/schema
   effettivi, preview storica e rollback. Presentare esito e anomalie all'utente.

La baseline esistente, non la correzione futura, è stata ricontrollata il
10 novembre: 123 test offline superati e 10 PostgreSQL opt-in saltati nelle
suite tipo Leichtmetall, bridge, cache, manuali e sicurezza packing. La
riproduzione offline precedente dimostra il difetto sui quattro JSON AI
composti e il rifiuto dei due pesi del DDT80011293 nei percorsi attuali.

## Criteri di chiusura

- Per il DDT80011293 restano due righe 3.962/1.085 kg, entrambe collegate al
  PDF95131.33; somma5.047, nessun raddoppio del file o del peso. Per un caso
  sintetico di tre lotti devono risultare esattamente tre gruppi coerenti.
- Stesso risultato in qualunque ordine di arrivo e dopo un riavvio, senza
  quarta riga residua, match oscillanti o necessità di correggere il nome a mano.
- Casi positivi e negativi su singoli, composti non consecutivi, numeri
  completi, zeri iniziali, separatori, quantità mancanti, pagine mancanti,
  duplicati HU, uguali pesi ma prodotti diversi e più certificati concorrenti.
- Per i dati storici le protezioni restano efficaci; una modifica manuale o
  uno sgancio non viene annullato dal primo caricamento successivo.
- Quarta, Word/PDF, codice e numeri certificati, nomi file, ereditarietà,
  export, Gemba, valutazione/KPI e quantità non subiscono duplicazioni o falsi verdi.
- Nessun cambiamento dei match per gli altri fornitori e nessuna rilettura AI
  massiva dovuta alla sola nuova versione dell'app.

## Alpha e recupero storico separati

Non dividere ora le cinque righe composte: alcune sono validate, modificate
manualmente o già collegate a Word/PDF. Al prossimo audit fare una preview
sul DB Alpha corrente distinguendo nuovi documenti, righe automatiche aperte,
righe manuali/validate e certificati emessi. Una correzione dati storica,
anche se fattibile, richiede un elenco preciso e autorizzazione separata.

Deploy solo su richiesta esplicita, secondo
[`alpha_soft_update_server.md`](../deploy/alpha_soft_update_server.md), con
verifica utenti attivi, backup DB/storage, spazio e rollback. Nessun ripristino
indiscriminato di DB o storage, nessuna copia del DB locale su Alpha.

## Decisioni confermate alla ripresa

Una riga per lotto, CDQ/colata comuni completi, pesi DDT individuali. L'utente
ha chiesto esplicitamente simulazioni anche per `95131.33.35` e per punteggiatura
OCR come ``95131.33`.35``. L'analisi del certificato resta comune; non viene
trasformata in analisi individuali. Separatore non dimostrabile o consegna
parziale non autorizzano inferenze sui pesi o sui lotti mancanti.

## Implementazione e collaudo 11 novembre — aggiornamento operativo

- Nuovo modulo puro `leichtmetall_groups.py`, usato dal parser locale/AI,
  recupero della lettura salvata e bridge comune di match/rematch.
- Contesto ricostruito dai dati correnti del DDT e dalla firma di completamento
  con identità documento; nessun motore AI decide l'abbinamento. Le correzioni
  esplicitamente confermate sul lato DDT possono essere rivalutate, senza
  cancellare gli sganci manuali o cambiare i dati del certificato per farli tornare.
- Evidenza `leichtmetall_group_link_v1` in `documenti_evidenze`, con documenti,
  hash e riferimento completo. **Nessuna nuova colonna/tabella o migrazione SQL**
  per questa funzione. Nessun backfill di Incoming o delle cache salvate.
- Il riferimento visibile non riscrive la colata originale DDT; il peso del
  lotto non riscrive quello totale del certificato, anche al refresh. La prova
  viene rivalutata sui dati vivi: membro eliminato, documento cambiato o
  incompatibilità non possono lasciare un falso verde.
- Creazione effettiva delle righe, fonte solo certificato assorbita una volta,
  recupero sullo stesso run, lock ordinati per tutto il gruppo e due worker.
  Sessioni normali e worker `autoflush=False`/`expire_on_commit=False` incluse.
- Quarta usa tutti i lotti pertinenti verificati: non sceglie un membro dal peso
  consumato dall'OL. Controlli e qualità di ogni membro restano necessari.
  L'analisi identica del documento comune viene conteggiata una sola volta
  nell'aggregazione chimica, per non sovrappesarla rispetto ad altri certificati.
- Se sui membri risultano dati tecnici diversi dopo modifiche manuali, non si
  inventa un'unica analisi comune né una ripartizione del consumo sconosciuta:
  la richiesta Quarta con colata composta richiede verifica. Una colata singola
  esplicitamente fornita da Quarta resta valutabile sul proprio membro.
- Restano distinte le consegne: nessuna somma fra DDT diversi, nessun accorpamento
  di materiali/ordini discordanti, nessuna scelta del primo certificato a parità.
- Se lo stesso PDF copre più consegne complete, ogni DDT deve superare la prova
  autonomamente. Quarta verifica tutti i membri pertinenti; una colata singola
  esplicita, con lo stesso CDQ completo, seleziona solo i relativi membri, senza
  inventare l'attribuzione dal peso consumato. Un override sceglie l'intero gruppo
  coerente, non permette di saltare i controlli di un membro.
- Le firme di completamento conservano anche i campi DDT canonici (es. 150.00
  diventa 150 nei ReadValue). Una lettura salvata precedente si verifica dal
  candidato originale e dall'identità del documento, non cancellando separatori
  o confrontando il peso della riga con il totale.
- Punto e virgola numerici nell'ordine (`332. 2 + 3` / `332, 2 + 3`, osservati
  nella prova AI) sono compatibili; il `+` non viene cancellato: `332.23` non è
  la stessa cosa. I riferimenti DDT canonici e i loro alias non possono
  nascondere una correzione intenzionale dell'utente.
- Per i futuri DDT Leichtmetall, una riga eliminata tramite il comando utente
  lascia una traccia documentale `leichtmetall_deleted_ddt_groups_v1`, se il
  PDF resta condiviso. Il recupero da salvataggio interrotto non la ricrea.
  Non si deducono nuove tracce dalle cancellazioni storiche e non si impedisce
  l'aggiunta manuale esplicita prevista dall'app. Nessun altro fornitore cambia
  le proprie regole di cancellazione/ricostruzione.
- Caricamento delle evidenze in blocco nelle liste interessate: prova SQL
  dedicata, per evitare una nuova query sulle evidenze per ogni riga ordinaria.
- Protezioni manuali, tipi documenti, altri fornitori, numerazioni, nomi file,
  modelli Word/PDF, PDF chiusi ed ereditarietà non vengono ridefiniti.

Prova AI reale locale autorizzata fino a 2 EUR: **due chiamate, entrambe riuscite**,
sui PDF già copiati dal precedente audit (DDT432 completo di due pagine e
certificato437). Prompt/modello applicativi invariati. Risultato `95131.33`,
95131/3962 kg e 95133/1085 kg, copertura verificata per entrambe le righe.
Stima **prudenziale** 0,491072 EUR (non consuntivo della fatturazione); riserva
massima prima delle chiamate 1,80 EUR. Nessuna ulteriore chiamata necessaria.
Artefatti/registro costi locali: `tmp_eval/leichtmetall_audit_20261110/live_20261111/`.
Chiave solo in memoria/stdin; su Alpha esclusivamente lettura credenziale in
transazione READ ONLY, nessuna chiamata a endpoint operativi, nessuna scrittura.

## Esito finale del collaudo locale — 11 novembre

- Suite mirata finale: **165 test superati, nessuno saltato o fallito**. Include
  41 casi puri, 26 prove del flusso su SQLite e 27 su PostgreSQL isolato,
  comprese concorrenza a due worker, rollback/retry, ripartenza, creazione reale
  delle righe con valori AI, correzioni/sganci e cancellazione volontaria.
  Comprende inoltre protezione manuali e sicurezza/recupero packing DDT.
- Regressione generale finale sul codice fermo: **1.112 superati, 147 saltati,
  zero errori/fallimenti**, 333,35 secondi. I 147 opt-in esclusi sono 141 prove
  PostgreSQL di altre suite prive del rispettivo URL dedicato e 6 rendering
  LibreOffice reali; non sono conteggiati come superati. Le prove PostgreSQL
  pertinenti al nuovo gruppo e al recupero DDT sono state eseguite.
- I 165 test mirati sono inclusi anche nella suite generale: non sommare
  i due conteggi come prove distinte. Restano soltanto avvisi di deprecazione
  delle dipendenze già presenti, nessun errore applicativo del collaudo finale.
- Verificati `95131.33`, `95131.32`, tre lotti non consecutivi e punteggiatura
  OCR. Sul caso reale 95131.33: due righe, 3.962/1.085 kg, stessa identità
  completa su CDQ/colata e totale certificato 5.047 kg conservato soltanto
  sul lato certificato. Nessuna riga provvisoria aggiuntiva dopo l'aggancio.
- Quarta non sceglie il lotto dal peso OL, non salta membri respinti/mancanti
  e non inventa una media di dati tecnici manualmente diversi. Restano distinti
  i casi con colata individuale esplicita e quelli con riferimento comune.
- Prova AI reale riuscita e rigiocata offline sul codice finale senza altre
  chiamate; originali PDF/packing controllati visivamente. Nessun modello,
  font, impaginazione o file Word/PDF emesso è stato modificato.
- Test eseguiti su DB temporanei, non sul DB dell'app locale o su Alpha.
  Evidenze XML: `final_target_20261111.xml` e
  `final_all_20261111_frozen.xml`, nella cartella locale dell'audit.
- A prove concluse è stato arrestato e rimosso soltanto il contenitore QA
  `certi-leichtmetall-qa-20261111`, verificato per ID, immagine, porta e assenza
  di volumi dell'app. Il DB sintetico era in tmpfs ed è ricreabile dai test;
  originali copiati, risultati e registro costi restano disponibili per l'audit.

Commit/push, deploy e qualsiasi recupero storico restano subordinati a nuova
indicazione esplicita. Il runbook Alpha è aggiornato con perimetro, controlli
e limiti di rollback; nessun intervento operativo sul server è stato eseguito.
