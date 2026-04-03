# Authentication

Sistema di autenticazione basato su email e password.

---

## Funzioni

login  
logout  
change password  

---

## Autenticazione

- autenticazione tramite email e password  
- utilizzo di token (JWT)  
- gli endpoint protetti richiedono autenticazione  

---

## Gestione Password

Il sistema NON utilizza email per il reset password.

La gestione password è interna.

---

## Creazione Utente

Quando un admin crea un utente:

- la password NON viene impostata
- password = NULL
- force_password_change = true

---

## Primo accesso (Set Password)

Flusso:

- utente inserisce email  
- il sistema rileva che password è NULL  
- NON esegue login normale  
- mostra schermata "crea password"  
- utente imposta la password  
- accesso completato  

---

## Login normale

Flusso:

- utente inserisce email e password  
- il sistema valida le credenziali  
- accesso consentito  

---

## Cambio password

Flusso:

- utente autenticato  
- inserisce:
  - password attuale  
  - nuova password  
- il sistema valida e aggiorna  

---

## Reset password (Smarrimento)

Il reset password NON avviene via email.

Flusso:

- utente contatta admin  
- admin esegue "reset password"  
- il sistema imposta:
  - password = NULL  
  - force_password_change = true  

Al successivo accesso:

- utente deve creare una nuova password  

---

## Initial Admin User (IMPORTANT)

Il sistema deve creare automaticamente un utente admin al primo avvio.

Logica:

- all'avvio del backend  
- controllare se esiste un utente con ruolo "admin"  
- se NON esiste → creare utente admin  

Dati admin iniziale:

email: admin@certi.local  
password: admin123  
name: System Admin  

Regole:

- password deve essere hashata  
- role = admin  
- active = true  
- force_password_change = true  
- NON creare duplicati se admin esiste  

Questo comportamento è obbligatorio per permettere il primo accesso al sistema