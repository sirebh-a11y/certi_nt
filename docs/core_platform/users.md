# Users Management

Gestione utenti del sistema.

---

## Funzioni

lista utenti  
scheda utente  
creazione utente  
disattivazione utente  
reset password  

---

## Campi utente

name  
email  
department  
role  
api_key  
active  

---

## Departments

I reparti disponibili sono:

quality  
administration  
production  
managing  
incoming  
laboratory  

Ogni utente deve appartenere a uno di questi reparti.

---

## Creazione utente

Quando un admin crea un utente:

- vengono salvati:
  - name  
  - email  
  - department  
  - role  
- la password NON viene impostata  
- password = NULL  
- force_password_change = true  

---

## Gestione password

La password NON è gestita tramite email.

---

### Primo accesso (Set Password)

- utente senza password (NULL)  
- il sistema rileva la condizione  
- viene mostrata schermata per creare password  
- dopo la creazione:
  - accesso completato  

---

### Login normale

- utente inserisce email e password  
- il sistema valida le credenziali  
- accesso consentito  

---

### Cambio password

- utente autenticato  
- inserisce:
  - password attuale  
  - nuova password  
- il sistema valida e aggiorna  

---

### Reset password (Smarrimento)

- solo admin può resettare la password  
- il reset imposta:
  - password = NULL  
  - force_password_change = true  

Al successivo accesso:

- utente deve creare una nuova password  

---

## Regole

- solo admin può creare utenti  
- solo admin può resettare password  
- ogni utente deve avere un ruolo valido  
- ogni utente deve appartenere a un department  
