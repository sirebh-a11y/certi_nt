# System Architecture

CERTI_nt è un software aziendale interno.

Architettura

browser
   │
frontend
   │
backend API
   │
database

Backend diviso in due parti:

core
modules

Core contiene la piattaforma del sistema.

Core comprende:

auth
users
roles
departments
email
logs

UI comprende:

header
sidebar
content
footer

Modules contiene le funzionalità applicative.

Stack tecnologico

Frontend
React + Tailwind

Backend
FastAPI (Python)

Database
PostgreSQL

Container
Docker
