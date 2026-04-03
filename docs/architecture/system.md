# System Architecture

CERTI_nt è un software aziendale interno.

---

## Stack tecnologico

Frontend  
React + Tailwind  

Backend  
FastAPI (Python)  

Database  
PostgreSQL  

Container  
Docker  

---

## Architettura

browser  
   │  
frontend  
   │  
backend API  
   │  
database  

---

## Struttura backend

Il backend è diviso in due parti:

core  
modules  

---

## Core Platform

Il core contiene la piattaforma stabile del sistema.

Include:

auth  
users  
roles  
departments  
email  
logs  

Il core è stabile e deve essere implementato completamente nella prima fase.

---

## Modules

I moduli rappresentano le funzionalità applicative.

IMPORTANTE:

- i moduli NON sono definiti in questa fase
- NON creare moduli specifici (es. AI, documents, ecc.)
- i moduli saranno progettati successivamente

---

## Regole architetturali

- i moduli utilizzano il core
- i moduli NON devono modificare il core
- il core deve essere indipendente dai moduli.
