# Departments

Il sistema utilizza reparti aziendali per classificare gli utenti.

---

## Lista reparti

I reparti disponibili sono predefiniti e NON modificabili:

quality  
administration  
production  
managing  
incoming  
laboratory  

---

## Utilizzo

- ogni utente deve appartenere a un solo reparto  
- il reparto è assegnato in fase di creazione utente  
- il reparto può essere modificato solo da admin  

---

## Database

È presente una tabella `departments` con i seguenti campi:

id  
name  
description  

---

## Regole

- i reparti sono statici (non CRUD)  
- NON implementare creazione/modifica/eliminazione reparti  
- il sistema deve validare che il valore appartenga alla lista definita  
