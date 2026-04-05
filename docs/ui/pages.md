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

Comportamento:

- admin → accesso completo alla lista  
- manager → accesso in sola lettura  
- user → nessun accesso  

---

## User Detail

- dettaglio utente  
- mostra dati utente  
- mostra stato OpenAI API key: configurata / non configurata  

Comportamento:

- admin può:
  - modificare name  
  - modificare department  
  - modificare role  
  - modificare active  
  - eseguire reset password  
  - disattivare utente  
  - inserire, aggiornare o rimuovere la OpenAI API key  
- manager può visualizzare il dettaglio in sola lettura  
- l'utente proprietario può vedere solo lo stato della propria OpenAI API key  
- il valore della chiave NON deve essere mostrato in chiaro  

---

## New User

- creazione nuovo utente  
- campi:
  - name  
  - email  
  - department  
  - role  

Regola:

- la OpenAI API key NON viene inserita in fase di creazione utente  
- la password NON viene inserita in fase di creazione utente  

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
