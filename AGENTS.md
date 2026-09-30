# Istruzioni operative CERTI

- Prima di modificare codice: audit e proposta; implementare soltanto dopo
  l'approvazione dell'utente. Commit/push e deploy Alpha richiedono indicazione
  esplicita. Per Alpha seguire `docs/deploy/alpha_soft_update_server.md`.
- Per i controlli visivi locali su Windows leggere
  `docs/development/browser_verification_windows.md`: Playwright/Chromium già
  installati hanno funzionato anche quando Computer Use non si avviava.
  Distinguere errore del browser, errore di avvio del processo protetto e codice
  Vite non aggiornato; non dichiarare impossibile il controllo visivo senza
  verificare il percorso documentato. Rispettare sempre permessi e autorizzazioni.
