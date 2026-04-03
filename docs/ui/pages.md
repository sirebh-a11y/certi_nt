# Pages

---

## Pagine core

Login  
Set Password  
Dashboard  
Users List  
User Detail  
New User  
Change Password  

---

## Login

- utente inserisce email e password  
- il sistema verifica credenziali  

Comportamento:

- se password valida → accesso  
- se password = NULL → reindirizza a "Set Password"  

---

## Set Password (Primo accesso)

Pagina utilizzata quando l'utente non ha ancora una password.

- utente inserisce nuova password  
- conferma password  
- il sistema salva la password  

Dopo il salvataggio:

- accesso completato  

---

## Dashboard

- pagina principale dopo login  
- mostra informazioni utente  
- contenuto placeholder  

---

## Users List

- lista utenti  
- visibile in base ai permessi  

---

## User Detail

- dettaglio utente  
- mostra dati utente  

---

## New User

- creazione nuovo utente  
- campi:
  - name  
  - email  
  - department  
  - role  

---

## Change Password

- utente autenticato  
- inserisce:
  - password attuale  
  - nuova password  

---

## Regole

- NON creare pagine per moduli  
- tutte le pagine utilizzano il layout principale  
- il contenuto è mostrato nella Content area  