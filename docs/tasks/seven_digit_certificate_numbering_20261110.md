# Numero certificato con F3 a sette cifre — 10/11/2026

## Decisione approvata

- Solo **nuove numerazioni** con F3 esattamente di sette cifre: segmento
  lavorazione `00`, contando gli zeri iniziali. `0600023` -> `7100_00_00/26`.
- Altre lunghezze restano come prima: `060002330` -> `..._30/26`,
  `060002340` -> `..._40/26`; un F3 a sei cifre non riceve la nuova eccezione.
  Il F3 completo, gli abbinamenti e l'identità della lavorazione non cambiano.
- **Vecchi numeri assegnati invariati**, anche Word aperti, rigenerazione
  esplicita, riapertura PDF o altra quota dello stesso DDT già numerato.
  Nessuna bonifica o rinomina dello storico.
- Un DDT realmente nuovo applica la nuova regola anche riusando un vecchio Word.
  Si conserva il progressivo DDT già raggiunto, senza ripartire da `_01`.
- Resta la numerazione per OL/CDQ e il progressivo delle spedizioni:
  stesso OL/F3/IdDocumento -> stesso numero, documenti distinti per quota;
  DDT successivo -> `_01`, `_02` ecc. La priorità resta al numero già assegnato.

## Audit e perimetro

La precedente funzione `_cod_f3_certificate_suffix` prendeva sempre le ultime
due cifre. Correggerla da sola non bastava: `ddt_shipments.number_plan` riprende
la base dal Word già presente; confronti di riuso/Registro avrebbero distinto
erroneamente una base storica `..._23/26` dalla nuova `..._00/26`.

Nel riscontro locale storico Alpha del **28/10**, 312 record con numero/F3,
11 con F3 a sette cifre (8 draft, 3 PDF chiusi), nessuna collisione apparente
dopo la sola sostituzione del segmento. OL1196/ID170 risultava draft, F3
0600023, numero e controllo Word `7100_00_23/26`. Non è un audit corrente
del server e **non è una lista di documenti da correggere**.

Nuovo modulo puro `certificate_numbering.py`: regola di assegnazione e chiave
di confronto tra le sole due forme note della medesima serie. Ammesso anche
lo zero di padding dei vecchi formati (`023` rispetto a `23`); un suffisso
arbitrario diverso non viene sanato silenziosamente.

- `base_number` continua a restituire la base letterale storica. Solo
  `series_base_number` confronta la forma vecchia/nuova per il F3 a sette cifre.
- `number_plan` controlla prima target e quote DDT già numerate, conservandole.
  Solo se serve un numero nuovo usa `00`, contando i progressivi sia della
  vecchia sia della nuova forma. Per esempio `_23_03/26` -> `_00_04/26`.
- Riuso Word, confronto versioni e Registro usano la chiave equivalente ma
  mantengono **OL e F3 completo identici** e il confronto materiale/contenuto.
  Il Raw senza DDT non ricompare come riga duplicata. Nessuna unione tra
  lavorazioni differenti solo perché entrambe finiscono visivamente con `00`.
- Integrità reale invariata: controllo CERT_NUMBER deve corrispondere al
  numero effettivamente salvato, hash storici non ricalcolati o accettati a
  posteriori. Differenze tecniche/manuali restano conflitti; si ignora soltanto
  il numero nel confronto di copie altrimenti equivalenti, come già previsto.
- Conflitti di assegnazione mantengono il blocco di unicità. Il piano di riuso
  restituisce ora una diagnostica di **numerazione**, con dettaglio preciso,
  non un falso errore di Word corrotto. Nessuna rinumerazione automatica di un
  altro OL/lavorazione per aggirare un conflitto, né modifica dei vecchi file.

## Nome file, archiviazione e documenti

Numero assegnato/draft, controllo CERT_NUMBER in tutte le intestazioni,
download Word/PDF, Registro e `NumeroCertificato`/`NomeFilePdf` export derivano
dal medesimo numero. Nome standard `7100_00_00_01_26.docx`/`.pdf`.
Il nome PDF personalizzato continua a seguire la scelta esplicita dell'utente.

I **percorsi fisici interni restano con UUID univoco**: il nome pubblico di
download/export è distinto dalla chiave di storage. Non rinominare i percorsi
storici, token o URL, né usare il nome visibile come identità di una quota.
L'export e il download restituiscono il nome corretto anche se il file è
conservato sotto UUID. Due quote dello stesso DDT possono avere lo stesso nome
standard senza sovrascriversi.

Seconde pagine associate al vecchio numero, contenuti incorporati e allegati
PDF restano reperibili tramite la fonte della medesima lavorazione. Non spostare
né rinumerare i loro record storici. La nuova copia conserva pagine/allegati;
i suoi riferimenti riportano il nuovo numero. Font, colori, altezze header,
quantità parte/totale, firme e impaginazione non sono modificati.

## Verifiche e limiti

- Suite generale con rendering reale abilitato: **980 superati, 178 saltati**
  per prerequisiti PostgreSQL opzionali della suite completa non attivati.
  Nessun errore. Regressione PostgreSQL dedicata a numerazione, riuso,
  riferimento Word, Registro ed export: **164 superati, nessuno saltato**.
  Ultima ripetizione del nuovo file (incluso padding storico e contenuti manuali)
  su SQLite/PostgreSQL: **28 superati, nessuno saltato**. Anche i 51 test
  frontend restano verdi; nessuna modifica frontend necessaria, il dialogo PDF
  usa nome e numero restituiti dal backend senza ricalcolarli.
- Test unitari su 7 cifre/zeri iniziali, 6/8/9 cifre, valori vuoti/brevi,
  padding storico, serie non coerenti e conflitti tra F3 differenti.
- DB temporanei: vecchio aperto e PDF chiuso invariati; quota aggiunta a DDT
  già numerato, nuovo DDT da vecchia base, continuazione `_03 -> _04 -> _05`,
  prima spedizione da base anticipata senza consumare sequenza; altre
  lavorazioni 30/40 con numeri e campi F3 corretti nel Word reale.
- Riuso reale/Registro: copie con nuovo numero non creano falsi conflitti;
  modifiche manuali al contenuto continuano a essere distinte. Vecchia base
  anticipata nascosta dopo la quota senza essere cancellata o riscritta.
- Collaudo sintetico con catena CERTI **Word -> PDF reale -> export/download**:
  vecchio Word/PDF di tre pagine, nuova copia con numero `7100_00_00_01/26`,
  `200 of 23000`, seconda pagina e un allegato. Verificati nomi `.docx`/`.pdf`,
  export, numero nelle intestazioni e tutte le sei PNG vecchio/nuovo. Stesso
  numero di pagine; vecchi file byte-identici, nuovi percorsi UUID distinti.
  Script/immagini temporanei in `tmp_eval/number7_render_qa.py` e
  `tmp_eval/number7_render/`, esclusi dal pacchetto applicativo.
- Il runtime artifact dedicato delle skill non è collegato a questo workspace;
  la verifica usa il convertitore dell'app in Docker (non LibreOffice desktop),
  seguito da rendering e ispezione PNG secondo la verifica Word/PDF.

Solo sviluppo locale. Nessun accesso o modifica ad Alpha, dati locali operativi,
chiamata AI/eSolver o importazione documenti reali. Commit/push e deploy richiedono
istruzione separata. Nessuna nuova colonna o migrazione DB; **nessun backfill**.
PostgreSQL e volume anonimo di collaudo rimossi dopo i test, con verifica di nome,
etichetta, database e rete isolata. Nessun servizio abituale riavviato.
