# Backend Architecture

Backend sviluppato con FastAPI.

---

## Struttura generale

Il backend è diviso in due parti:

core  
modules  

---

## Core Platform

Il core contiene la logica principale del sistema.

Struttura:

auth  
users  
roles  
departments  
email  
logs  

Ogni componente del core deve essere organizzato in:

router → API endpoints  
service → logica applicativa  
models → modello database  
schemas → validazione dati  

---

## Modules

I moduli contengono funzionalità applicative.

IMPORTANTE:

- i moduli NON sono definiti in questa fase
- NON implementare moduli ora
- i moduli saranno aggiunti successivamente

---

## Regole fondamentali

- il core è indipendente
- i moduli utilizzano il core
- i moduli NON devono modificare il core
- ogni componente deve essere separato (no logica duplicata)

---

## API Design

Le API devono seguire struttura REST:

GET /users  
POST /users  
GET /users/{id}  
PUT /users/{id}  

Utilizzare nomi in inglese per endpoint e codice.
