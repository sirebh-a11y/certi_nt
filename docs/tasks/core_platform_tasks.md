# Core Platform Tasks

Implementare il core platform seguendo i file docs.

---

## Step 1 — Database

Creare le tabelle definite in:

docs/database/schema_core.md

---

## Step 2 — Authentication

Implementare:

- login (email + password)  
- JWT token  
- protezione endpoint  

Gestione password:

- supportare password = NULL  
- implementare flusso "Set Password"  
- implementare cambio password  
- NON usare email per password  

---

## Step 3 — Initial Admin

Implementare:

- creazione automatica admin al primo avvio  
- verificare se esiste già  
- NON creare duplicati  

---

## Step 4 — Users Management

Implementare:

- lista utenti  
- creazione utente  
- modifica utente (admin)  
- disattivazione utente  
- reset password (admin)  
- gestione OpenAI API key personale utente  

Gestione password:

- password NON impostata alla creazione  
- password = NULL  
- force_password_change = true  

Gestione OpenAI API key:

- campo opzionale per utente  
- inserimento / aggiornamento / rimozione da parte di admin  
- l'utente proprietario vede solo stato configurata / non configurata  
- salvataggio sicuro nel database  

---

## Step 5 — Roles and Permissions

Implementare:

- ruoli: user, manager, admin  
- controllo accesso alle funzionalità  
- protezione endpoint backend  

---

## Step 6 — Departments

Implementare:

- lista reparti predefiniti  
- validazione department  
- nessuna gestione CRUD  

---

## Step 7 — Email System

Implementare:

- configurazione tramite variabili ambiente  
- supporto development (MailHog)  
- supporto production (SMTP)  
- utilizzo SOLO per notifiche  

---

## Step 8 — Frontend

Implementare:

- layout principale (Header, Sidebar, Content, Footer)  
- pagine core (vedi docs/ui/pages.md)  
- gestione login  
- gestione set password  
- gestione utenti  
- gestione stato OpenAI API key nella scheda utente  
- User Detail admin con azioni amministrative  
- User Detail manager in sola lettura  

---

## Regole

- seguire docs/architecture  
- seguire docs/development_rules  
- NON implementare moduli  
