# Modules

I moduli rappresentano le funzionalità applicative del sistema.

---

## Stato attuale

I moduli sono documentati come blueprint funzionali.

In generale NON sono ancora implementati in questa fase, ma il modulo `fornitori` e' il primo modulo applicativo entrato in implementazione dopo la stabilizzazione del core.

---

## Regole

- NON implementare nuovi moduli senza prompt dedicato  
- NON anticipare codice o architetture runtime dei moduli senza prompt dedicato  
- usare questi file come base analitica per sviluppi futuri  

---

## Architettura

I moduli:

- utilizzano la core platform  
- NON modificano il core  
- sono indipendenti tra loro  

---

## Integrazione con core

I moduli utilizzano:

- autenticazione  
- utenti  
- ruoli  
- reparti  
- servizi comuni (email, log)  

---

## Obiettivo

Preparare il sistema per supportare moduli futuri gia' documentati, mantenendo il focus implementativo su core e sui singoli moduli avviati in modo esplicito.
