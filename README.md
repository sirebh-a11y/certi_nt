# CERTI_nt

Prima definizione del progetto.

## Core

Il core e la piattaforma base del sistema.

Comprende:

- autenticazione
- utenti
- ruoli e permessi
- reparti
- email
- log

## UI

La UI e l'interfaccia usata dagli utenti interni.

Comprende:

- header
- sidebar
- content area
- footer
- pagine core
- pagine dei moduli

## Modules

I moduli implementano le funzioni applicative e usano il core senza modificarlo.

Esempi:

- AI
- documents
- certificates

## Stack

- frontend: React + Tailwind
- backend: FastAPI
- database: PostgreSQL
- container: Docker
