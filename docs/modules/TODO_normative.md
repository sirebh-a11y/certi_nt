# TODO Normative Standards

## Scopo

Tracciare eccezioni e anomalie nei dati normativi estratti da Excel (`_Prova Analisi_.xlsx`) da correggere in una fase successiva.

---

## 🔴 Lega 7175

**Problema**

* Valori meccanici impostati a 0:

  * Rp0.2 = 0
  * Rm = 0
  * A% = 0

**Interpretazione**

* Probabile placeholder o dati non validi

**Azione**

* NON usare per validazione
* Verificare con fonte tecnica / Excel aggiornato

---

## 🟡 Lega 2024 Sigma

**Problema**

* Blocchi meccanici senza range esplicito (diametro non definito)

**Interpretazione**

* Standard probabilmente valido per tutti i diametri

**Azione**

* Confermare se esistono range reali
* In assenza, trattare come:

  * misura_min = NULL
  * misura_max = NULL

---

## 🟢 Lega 7150

**Problema**

* Presenza proprietà certificata non meccanica:

  * IACS%

**Interpretazione**

* Proprietà elettrica / conducibilità
* il modello normativo deve supportare proprietà certificate categorizzate, non solo meccaniche

**Azione**

* classificare `IACS%` nella categoria corretta
* verificare se esistono altre proprietà certificate non meccaniche da supportare allo stesso modo

---

## 📌 Nota generale

* Queste eccezioni NON bloccano il sistema
* Il modello aggiornato deve supportarle senza forzature concettuali
* Correzioni da fare in fase di:

  * validazione dati
  * evoluzione GUI

---
