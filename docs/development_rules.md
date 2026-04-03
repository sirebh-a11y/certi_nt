# Development Rules

Queste regole sono obbligatorie.

---

## Architettura

- NON modificare l'architettura del progetto  
- mantenere separazione tra core e modules  
- il core platform è stabile  

---

## Core Platform

- implementare SOLO il core platform  
- NON aggiungere funzionalità non richieste  
- NON modificare comportamento definito nei file docs  

---

## Modules

- NON implementare moduli  
- NON creare esempi di moduli  
- NON aggiungere codice relativo a moduli  

---

## Database

- creare SOLO le tabelle definite in schema_core.md  
- NON aggiungere tabelle extra  
- NON anticipare schema moduli  

---

## Backend

- seguire struttura:
  router  
  service  
  models  
  schemas  

- NON mescolare responsabilità  
- NON duplicare logica  

---

## Frontend

- utilizzare layout unico  
- NON creare layout multipli  
- rispettare struttura sidebar e pagine  

---

## Password e autenticazione

- NON utilizzare email per gestione password  
- seguire flusso definito in auth.md  
- supportare password NULL  
- implementare Set Password flow  

---

## Email

- utilizzare email SOLO per notifiche sistema  
- NON usare email per reset password  

---

## Generazione codice

- modificare SOLO i file necessari  
- NON creare codice inutile  
- mantenere codice semplice e leggibile  

---

## Regola generale

Se una funzionalità NON è definita nei file docs:

→ NON implementarla  