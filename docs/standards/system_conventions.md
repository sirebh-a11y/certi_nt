# System Conventions

## ⚠️ IMPORTANTE

Questo file definisce le convenzioni globali del sistema.

Queste regole devono essere rispettate da tutti i moduli:

* data acquisition
* normative engine
* fornitori
* moduli futuri

---

## 1. Convenzioni numeriche

### 1.1 Formato europeo (input / output)

Il sistema utilizza il formato europeo per la rappresentazione dei numeri lato utente.

Separatore decimale:

```plaintext id="bq3k7n"
,
```

Esempi:

```plaintext id="fzt6r1"
12,5
0,25
3,80
```

---

### 1.2 Formato interno (database)

Nel database i numeri devono essere salvati utilizzando:

```plaintext id="kz0y6m"
.
```

Esempi:

```plaintext id="7c0i3q"
12.5
0.25
3.80
```

---

### 1.3 Regole di normalizzazione

* input può contenere:

  * `,` (formato europeo)
  * `.` (formato OCR o varianti)

* il sistema deve:

```plaintext id="n3u8ps"
convertire sempre a "." prima del salvataggio
```

---

### 1.4 Separatore delle migliaia

Formato europeo:

```plaintext id="4b4qgk"
1.000
10.000
```

Regola:

* il separatore delle migliaia NON deve essere salvato nel database
* deve essere rimosso in fase di normalizzazione

---

## 2. Unità di misura

### 2.1 Chimica

Unità:

```plaintext id="3c4u0p"
percentuale (%)
```

Esempio input:

```plaintext id="xt3w9k"
Mg = 0,8 %
```

Valore salvato:

```plaintext id="f4xw2k"
0.8
```

---

### Regole

* NON salvare il simbolo `%`
* salvare solo il valore numerico
* formato DB sempre con `.`

---

### 2.2 Proprietà certificate

Unità standard:

| Proprietà  | Unità                  |
| ---------- | ---------------------- |
| Rp0.2      | MPa                    |
| Rm         | MPa                    |
| HB         | HB                     |
| A%         | %                      |
| Rp0.2 / Rm | rapporto (senza unità) |
| IACS%      | % IACS                 |

Le proprietà certificate possono appartenere a categorie diverse, per esempio:

* meccanica
* elettrica

---

### Regole

* NON salvare unità nel database
* le unità sono definite a livello di sistema
* input può contenere unità → ignorare in fase di salvataggio

---

### 2.3 Peso

Unità standard:

| Campo | Unità |
| ----- | ----- |
| peso  | kg    |

Esempio input:

```plaintext
2120 Kg
```

Valore salvato:

```plaintext
2120
```

### Regole

* NON salvare l'unità nel database
* accettare varianti come `kg`, `Kg`, `KG`
* salvare solo il valore numerico
* applicare le convenzioni numeriche globali del sistema

---

## 3. Range e valori

### 3.1 Range

```plaintext id="tf8e5s"
min_value ≤ valore ≤ max_value
```

---

### 3.2 Valori NULL

```plaintext id="kq8f0a"
NULL = valore non presente nel documento
```

NON significa:

* 0
* errore
* non conforme

---

## 4. Date

### 4.1 Formato europeo (input)

Formato accettato:

```plaintext id="h3g8rp"
DD/MM/YYYY
DD/MM/YY
```

Esempi:

```plaintext id="3r9p7c"
02/04/2026
15/12/2025
```

---

### 4.2 Formato interno (database)

Nel database le date devono essere salvate come:

```plaintext id="4l0z7m"
YYYY-MM-DD
```

Esempi:

```plaintext id="7p8v2x"
2026-04-02
2025-12-15
```

---

### 4.3 Regole

* input può contenere formati diversi (OCR)
* il sistema deve normalizzare prima del salvataggio
* NON salvare formati ambigui

---

## 5. Stringhe

### 5.1 Normalizzazione

* rimuovere spazi iniziali e finali
* evitare doppi spazi
* mantenere il contenuto originale per tracciabilità

---

## 6. Identificativi

### 6.1 CDQ

* NON modificare
* NON normalizzare
* salvare esattamente come nei documenti

---

## 7. OCR / Input

Regole:

* accettare vari formati in input
* normalizzare solo in fase di salvataggio
* mantenere il dato originale quando necessario (es. `fornitore_raw`)

---

## 8. Derivati

Nel livello documentale / `acquisition`:

* NON salvare valori derivati
* calcolare solo runtime o in livelli separati
* salvare solo dati presenti nei documenti

Livelli futuri del sistema, come KPI o processi interni, possono invece gestire valori derivati in modo esplicito e separato.

---

## 9. Obiettivo

Garantire:

* coerenza globale del sistema
* compatibilità tra moduli
* robustezza rispetto a input reali (OCR, documenti)
* allineamento con formato europeo lato utente
