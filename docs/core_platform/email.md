# Email System

Il sistema email è utilizzato per notifiche e comunicazioni interne del sistema.

---

## Utilizzo

Il sistema email NON deve essere utilizzato per:

- reset password  
- gestione credenziali utenti  

La gestione password è interna al sistema (vedi auth.md).

---

## Modalità di utilizzo

Il sistema deve supportare due modalità:

### Development

Provider: MailHog

Configurazione:

host: mailhog  
port: 1025  
nessuna autenticazione  
nessun TLS  

Uso:

- sviluppo locale  
- le email non vengono inviate realmente  

---

### Production

Provider: SMTP aziendale

Configurazione tramite variabili ambiente:

SMTP_HOST  
SMTP_PORT  
SMTP_USER  
SMTP_PASSWORD  
MAIL_ALWAYS_CC_EMAIL (opzionale)

TLS: abilitato  

Uso:

- ambiente reale  
- invio email per notifiche sistema  

---

## Configurazione (.env)

Il sistema deve utilizzare un file `.env` nella root del progetto.

Esempio:

ENV=development  

SMTP_HOST=smtp.azienda.it  
SMTP_PORT=587  
SMTP_USER=noreply@azienda.it  
SMTP_PASSWORD=CHANGE_ME  
SMTP_TLS=true  
MAIL_ALWAYS_CC_EMAIL=archivio@azienda.it

Regole:

- il file `.env` contiene la configurazione reale  
- NON salvare password reali nel repository  
- utilizzare `.env` per differenziare development e production  

---

## Comportamento

- la modalità (development / production) deve essere configurata tramite variabile ENV  
- il sistema deve selezionare automaticamente il provider corretto  
- il servizio email deve essere separato dalla logica utenti  
- se `MAIL_ALWAYS_CC_EMAIL` è valorizzato, tutte le email inviate dal servizio comune devono includerlo in `Cc`
- se il destinatario principale coincide con il CC globale, deve essere inviata una sola copia

---

## Funzioni richieste

Il sistema deve implementare:

- invio email per notifiche sistema  
- invio email per eventi applicativi  

---

## Dati email

from_email: noreply@certi.local  
from_name: CERTI_nt System
