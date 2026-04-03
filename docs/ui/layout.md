# UI Layout

Il sistema utilizza un layout unico per tutte le pagine autenticato.

---

## Struttura layout

Il layout è composto da:

Header  
Sidebar  
Content  
Footer  

---

## Header

Contiene:

- nome applicazione (CERTI_nt)  
- nome utente  
- ruolo utente  
- pulsante logout  

---

## Sidebar

La sidebar è fissa sul lato sinistro.

Caratteristiche:

- larghezza 220px  
- scroll indipendente  
- icone + testo  

---

## Menu

Dashboard  
Prima applicazione  
---------  
Utenti  
Reparti  
Log  

---

## Content

- area principale della pagina  
- mostra il contenuto dinamico  
- cambia in base alla pagina selezionata  

---

## Footer

Contiene:

- versione sistema  
- stato servizio  

---

## Comportamento

- il layout è unico e riutilizzato in tutte le pagine  
- le pagine vengono renderizzate nella Content area  
- la sidebar cambia contenuto in base al ruolo utente  
- il menu deve essere coerente con i permessi  

---

## Regole

- NON creare layout multipli  
- utilizzare un unico AppShell  
- separare layout e pagine  