# Verifica visiva locale Windows: soluzione verificata

Ultima verifica: **30/09/2026**. Nessun intervento su Alpha.

## Cosa aveva funzionato

Il collaudo DDT del 29/09 è registrato in
`docs/tasks/ddt_certification_alert_queue_plan.md`, sezione «Collaudo visivo
locale completato»: Chromium tramite Playwright già installato, non Computer
Use. Verificati allora dati reali locali, filtri e collegamento alla quota #393.

Il 30/09 il percorso Playwright è stato provato nuovamente con esito positivo:
pagina React reale, API simulate, nessuna scrittura DB, screenshot a 1920 e
1440 px, nessun errore JavaScript. Non è una prova dell'integrazione eSolver.

## Procedura da riutilizzare

1. Verificare gli strumenti browser disponibili e seguire le loro istruzioni.
   Se Computer Use fallisce all'avvio, non confonderlo con un errore di CERTI.
2. Riutilizzare Playwright esistente. Al 30/09/2026:
   - Node: `C:\Program Files\nodejs\node.exe`;
   - import `playwright` risolvibile dagli script in `tmp_eval/packages_qa/`;
   - Chromium:
     `C:/Users/sireb/AppData/Local/ms-playwright/chromium-1194/chrome-win/chrome.exe`.
   Verificare che i percorsi esistano: versioni e cartelle possono cambiare.
   Non reinstallare browser o dipendenze come primo tentativo.
3. Avviare il browser con `chromium.launch({headless: true, executablePath: ...})`,
   creare una pagina, aprire l'URL locale, controllare DOM/errori e salvare
   screenshot da ispezionare. Chiudere il browser in `finally`.
   Questo è un browser di collaudo separato, non il profilo Chrome/Edge
   dell'utente; non eredita la sua sessione autenticata.
4. Per sole prove UI, intercettare **tutte** le API con dati fittizi, senza
   credenziali reali. Per prove integrate usare un ambiente isolato o letture
   autorizzate. Non compiere azioni mutanti sui dati reali per provare il browser.
5. Se il terminale fallisce prima dell'avvio con `helper_unknown_error`,
   registrare che è un problema di avvio del processo protetto. Richiedere
   l'esecuzione autorizzata attraverso il normale meccanismo di approvazione,
   se consentito; non disattivare protezioni né ignorare un rifiuto.

## Problema diverso: Vite serve codice vecchio

Il 30/09 il file locale `DdtWorkQueuePage.jsx` conteneva `ddtDeadline`, ma la
risposta HTTP di `http://localhost:5173/src/pages/quartaTaglio/DdtWorkQueuePage.jsx`
non lo conteneva. Il browser funzionava: era il codice servito a non essere
aggiornato. La causa precisa del mancato aggiornamento automatico non è accertata.
Un caso analogo e il successivo riavvio autorizzato sono documentati in
`docs/tasks/certificate_first_merge_manual_quality.md`.

Per il collaudo senza riavviare il servizio abituale:

```powershell
cd C:\Users\sireb\VScodeProjects\certi_nt\frontend
node node_modules/vite/bin/vite.js --host 127.0.0.1 --port 5174 --strictPort
```

Attendere il messaggio `ready`, poi aprire il percorso della pagina su
`http://127.0.0.1:5174`. `--strictPort` impedisce di scegliere un'altra porta
silenziosamente. Interrompere solo questo processo temporaneo al termine.
Non lasciare due frontend aperti inutilmente e non terminare tutti i processi Node.
Un riavvio del frontend abituale va concordato se può interrompere l'utente.

## Evidenze del 30/09

- Script temporaneo: `tmp_eval/packages_qa/ddt_deadline_check.mjs`.
- Screenshot: `tmp_eval/ddt-deadline-1920.png`, `tmp_eval/ddt-deadline-1440.png`.
- Verificati avvisi normale/giallo/arancione/rosso, data mancante, completati
  senza avviso, campi lunghi e cambio giorno italiano con browser in altro fuso.
- 13 colonne come prima, nessun debordo della pagina; scroll interno tabella.
- Il frontend abituale 5173 **non è stato riavviato** in questa verifica.

Gli artefatti sotto `tmp_eval` sono temporanei, non necessariamente presenti
in Git o su altri PC. Questa procedura e il richiamo in `AGENTS.md` costituiscono
la memoria persistente del progetto, non una garanzia che Computer Use sia riparato.
