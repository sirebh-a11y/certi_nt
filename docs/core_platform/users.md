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
openai_api_key  
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
- openai_api_key NON viene impostata in creazione utente  

---

## Modifica utente

Admin può modificare un utente esistente.

Campi modificabili:

- name  
- department  
- role  
- active  

Regole:

- email NON viene modificata nella fase iniziale  
- department può essere modificato solo da admin  
- role può essere modificato solo da admin  
- active può essere modificato solo da admin  

---

## OpenAI API Key utente

Ogni utente può avere una OpenAI API key personale opzionale.

Regole:

- il campo è opzionale  
- la chiave appartiene al singolo utente  
- NON deve essere mostrata in chiaro dopo il salvataggio  
- il sistema deve mostrare solo stato configurata / non configurata  
- admin può inserire, aggiornare o rimuovere la chiave nella scheda utente  
- l'utente proprietario può vedere solo lo stato della chiave, NON il valore  
- la chiave deve essere salvata in modo sicuro nel database  
- l'utilizzo applicativo della chiave è demandato ai moduli futuri, NON al core  

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
- solo admin può modificare utenti  
- solo admin può resettare password  
- solo admin può disattivare utenti  
- ogni utente deve avere un ruolo valido  
- ogni utente deve appartenere a un department  
- la OpenAI API key è opzionale e personale  
- la OpenAI API key non deve mai essere restituita in chiaro dalle API  
