# Piano Accessi Per Reparto

## Obiettivo

Separare gli accessi per reparto senza creare una struttura fragile di ruoli duplicati.

L'app oggi ha gia:

- ruoli: `user`, `manager`, `admin`
- reparti: `IT`, `Qualita`, `Amministrazione`, `Direzione`, `Incoming`, `Laboratorio`, `Produzione`

La modifica proposta usa insieme `role` e `department`.

## Situazione Attuale

Oggi il reparto e quasi solo informativo.

La maggior parte della UI e delle API guarda solo il ruolo:

- `admin`
- `manager`
- `user`

Problema: un `admin` di Qualita vede anche pagine tecniche IT come Database, Email e Assistente AI.

Altro problema: molte pagine sono nascoste in sidebar, ma alcune API backend restano aperte a qualunque utente autenticato. Quindi non basta nascondere il menu.

## Regola Proposta

Non aggiungere ruoli come `admin_it`, `admin_qualita`, `admin_amministrazione`.

Usare:

- `role` per il livello di potere
- `department` per l'area aziendale

Esempi:

- `admin + IT`: amministratore tecnico completo
- `admin + Qualita`: amministratore qualita, non tecnico IT
- `user/manager + Amministrazione`: accesso amministrativo limitato
- `user/manager + Direzione`: accesso consultivo

## Matrice Accessi Proposta

### IT Admin

Accesso completo:

- Dashboard
- Carica Documenti
- Incoming materiale
- Certificazione
- Registro certificazione
- Valutazione
- KPI
- Standards
- Requisiti Cliente
- Note
- Codici fornitori
- Fornitori
- Clienti
- Utenti
- Reparti
- Log
- Database
- Assistente AI
- Email

### Qualita

Accesso operativo qualita:

- Dashboard
- Carica Documenti
- Incoming materiale
- Certificazione
- Registro certificazione
- Valutazione
- KPI
- Standards
- Requisiti Cliente
- Note
- Codici fornitori
- Fornitori
- Clienti

Non vede:

- Database
- Email
- Assistente AI
- Reparti
- Log tecnici, salvo diversa decisione

Pagina utenti:

- per alpha: non visibile
- futura opzione: visibile solo per utenti di reparti qualita, senza poter toccare IT

### Amministrazione

Accesso non operativo:

- Dashboard
- Registro certificazione

Non vede:

- Carica Documenti
- Incoming materiale
- Certificazione operativa
- Valutazione
- Standards
- Requisiti Cliente
- Note
- Codici fornitori
- Fornitori
- Database
- Email
- Assistente AI
- Utenti
- Reparti
- Log

Nota: amministrazione deve scaricare o consultare certificati dal Registro, non creare o modificare il processo.

### Direzione

Accesso consultivo:

- Dashboard
- Registro certificazione
- KPI
- Valutazione fornitori, se confermato

Non modifica il processo.

### Incoming

Per ora trattato come Amministrazione.

Decisione futura: separare Incoming se dovra caricare documenti o lavorare sulle righe di ingresso.

## Implementazione Tecnica Proposta

### 1. Funzione centrale permessi

Creare una funzione condivisa lato frontend:

```text
canAccessPage(user, pageKey)
```

Questa funzione deve leggere:

- `user.role`
- `user.department`

La sidebar e il router devono usare la stessa funzione.

### 2. Protezione frontend

Adeguare:

- `frontend/src/components/layout/Sidebar.jsx`
- `frontend/src/app/router.jsx`
- eventuali pulsanti interni gia condizionati solo da `role`

Obiettivo:

- l'utente non vede pagine non sue
- l'utente non entra digitando l'URL

### 3. Protezione backend

Creare una funzione backend analoga:

```text
require_access(area)
```

Oppure una funzione di controllo:

```text
can_access(user, area)
```

Da applicare alle API sensibili.

Priorita backend:

- `/api/integrations`
- `/api/email-settings`
- `/api/ai`
- `/api/users`
- `/api/departments`
- `/api/logs`
- rotte operative di certificazione e incoming

### 4. Pagina Utenti

Per alpha:

- visibile solo a `admin + IT`
- backend `/api/users` accessibile solo a `admin + IT`

Motivo:

- reset password, cambio ruolo e cambio reparto sono azioni ad alto rischio
- un admin qualita non deve poter modificare utenti IT

### 5. Bottoni e azioni interne

Verificare i pulsanti che oggi usano solo:

```text
user.role === "admin"
```

Esempi:

- elimina riga Incoming
- riapri PDF
- modifica fornitori
- codici fornitori
- configurazioni AI/email/database

Non tutti gli admin devono poter fare tutto.

## Rischi

### Rischio 1: nascondere solo la UI

Se si modifica solo la sidebar, un utente puo ancora chiamare API dirette.

Mitigazione:

- protezione anche backend.

### Rischio 2: bloccare funzioni usate dal flusso

Alcune pagine chiamano API comuni.

Mitigazione:

- prima limitare le pagine intere
- poi restringere le azioni specifiche una per una
- testare con utenti reali per reparto

### Rischio 3: nomi reparto

Nel codice attuale i reparti canonici sono in italiano, ma alcuni documenti vecchi riportano nomi inglesi legacy.

Mitigazione:

- usare solo i nomi reali del database:
  - `IT`
  - `Qualita`
  - `Amministrazione`
  - `Direzione`
  - `Incoming`
  - `Laboratorio`
  - `Produzione`

### Rischio 4: manager

Oggi `manager` vede utenti e log.

Decisione proposta:

- in alpha non usare `manager` come ruolo operativo privilegiato
- preferire reparto + admin IT per funzioni tecniche

## Test Minimi

Creare o usare 4 utenti:

- Admin IT
- Admin Qualita
- Utente Amministrazione
- Utente Direzione

Verifiche:

- sidebar corretta
- URL diretto bloccato
- API diretta bloccata
- Registro certificazione accessibile ad Amministrazione
- Certificazione operativa non accessibile ad Amministrazione
- Database/Email/AI accessibili solo a IT admin
- Utenti accessibile solo a IT admin

## Decisioni Ancora Da Confermare

1. Direzione vede solo KPI e Registro, o anche Valutazione?
2. Qualita deve vedere Log in sola lettura?
3. Qualita deve vedere Utenti in sola lettura o niente per alpha?
4. Incoming resta come Amministrazione per alpha?
5. Fornitori e Clienti devono essere visibili a Qualita, Amministrazione o solo Qualita?

## Piano Di Implementazione

1. Creare mappa permessi centralizzata frontend.
2. Applicarla a Sidebar e Router.
3. Creare mappa permessi backend.
4. Proteggere API tecniche IT.
5. Proteggere API utenti/reparti/log.
6. Proteggere API operative Incoming/Certificazione dove serve.
7. Testare con 4 utenti tipo.
8. Solo dopo, valutare permessi piu fini su singoli pulsanti.

