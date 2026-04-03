# Core Database Schema

Il database definisce le tabelle principali del core platform.

---

## Tabelle

users  
departments  

---

## Tabella: users

Campi:

id → integer (primary key)  
name → string  
email → string (unique)  
password_hash → string (nullable)  
department_id → integer (foreign key → departments.id)  
role → string  
openai_api_key_encrypted → string (nullable)  
active → boolean  
force_password_change → boolean  
created_at → datetime  
last_login → datetime (nullable)  

---

## Regole users

- email deve essere unica  
- password_hash può essere NULL (utente non ha ancora impostato password)  
- force_password_change indica obbligo cambio password  
- ogni utente deve avere un solo ruolo  
- ruolo deve essere uno tra:
  - user  
  - manager  
  - admin  
- ogni utente deve appartenere a un department  
- openai_api_key_encrypted contiene la OpenAI API key cifrata dell'utente  
- la OpenAI API key non deve essere salvata in chiaro  
- la OpenAI API key non deve essere restituita in chiaro dalle API  

---

## Tabella: departments

Campi:

id → integer (primary key)  
name → string  
description → string  

---

## Regole departments

- i valori devono essere predefiniti  
- NON implementare CRUD per departments  
- valori ammessi:
  - quality  
  - administration  
  - production  
  - managing  
  - incoming  
  - laboratory  

---

## Regole generali

- utilizzare foreign key  
- utilizzare nomi in inglese  
- mantenere schema semplice e coerente con il core platform  
