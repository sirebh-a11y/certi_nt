# Roles and Permissions

Il sistema utilizza ruoli per controllare l'accesso alle funzionalità.

Ogni utente ha un solo ruolo.

---

## Ruoli disponibili

user  
manager  
admin  

---

## Comportamento per ruolo

### user

- accesso dashboard  
- accesso applicazione  

---

### manager

- accesso dashboard  
- accesso applicazione  
- visualizzazione utenti  
- visualizzazione dettaglio utente  
- visualizzazione log  

---

### admin

- accesso completo  
- creazione utenti  
- modifica utenti  
- reset password  
- gestione reparti (assegnazione)  

---

## Regole

- ogni utente deve avere un solo ruolo  
- il ruolo determina direttamente le funzionalità disponibili  
- NON implementare sistema di permessi separato  
- il backend deve controllare l’accesso in base al ruolo  
- il frontend deve adattare la UI in base al ruolo  

---

## Accesso funzionalità

### Users Management

- admin → accesso completo  
- manager → sola visualizzazione (lista + dettaglio)  
- user → nessun accesso  

---

### Logs

- admin → accesso completo  
- manager → accesso in lettura  
- user → nessun accesso  

---

### Application

- user → accesso  
- manager → accesso  
- admin → accesso   
