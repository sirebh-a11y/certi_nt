# Authentication

Sistema di autenticazione basato su email e password.

Funzioni

login
logout
reset password
change password

Autenticazione tramite token.

Gli endpoint protetti richiedono autenticazione.

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

Questo comportamento è obbligatorio per permettere il primo accesso al sistema.