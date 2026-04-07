# DDT / Certificates Normative Standards Module
## Posizionamento
Questo modulo **NON** fa parte del core. Deve essere implementato **dopo** la stabilizzazione del core, con un prompt Codex dedicato.
Questo file definisce il motore normativo e il contenuto iniziale delle regole estratto dal file `_Prova Analisi_.xlsx`.

## Obiettivo
Costruire un database di standard normativi da usare per confrontare i dati acquisiti da DDT e certificati fornitore.
Ogni foglio Excel corrisponde a **una singola lega_designazione** e contiene le regole di quella designazione.

La `lega_designazione` può coincidere con la lega standard oppure rappresentare una variante specifica della lega base.

## Logica del motore normativo
- Primo filtro obbligatorio: **lega_base**.
- Se presente, la `variante_lega` raffina la selezione e ha precedenza sulla regola generale della lega base.
- Dentro la lega, la regola corretta si seleziona in base a una o più dimensioni: `norma`, `trattamento_termico`, `tipo_prodotto`, `misura_tipo` (`diametro` o `spessore`) e relativo range.
- Se una dimensione non compare per una regola, quella dimensione è **ininfluente** per quella regola.
- Le formule Excel usano il diametro o lo spessore per scegliere il blocco meccanico corretto. Questa logica deve essere ricostruita in database.
- Le medie chimiche e i controlli di conformità presenti in Excel **non sono standard**: sono logica applicativa successiva.

## Modello dati proposto
### 1. `normative_standards`
- `id`
- `lega_base` (obbligatorio)
- `lega_designazione` (obbligatorio)
- `variante_lega` (nullable)
- `regola_tipo` (`generale` / `variante`)
- `norma` (nullable)
- `trattamento_termico` (nullable)
- `tipo_prodotto` (nullable)
- `misura_tipo` (nullable: `diametro` / `spessore`)
- `misura_min` (nullable)
- `misura_max` (nullable)
- `fonte_excel_foglio`
- `fonte_excel_blocco`

### 2. `normative_standard_chemistry`
- `id`
- `standard_id`
- `elemento`
- `min_value` (nullable)
- `max_value` (nullable)

### 3. `normative_standard_properties`
- `id`
- `standard_id`
- `categoria` (esempio: `meccanica`, `elettrica`)
- `proprieta`
- `min_value` (nullable)
- `max_value` (nullable)

### Nota futura
Il modello deve restare modificabile da GUI in futuro. Non hardcodare enum o regole nel codice: il database dovrà poter essere esteso con nuove leghe, nuove norme e nuove varianti.

## Regole generali vs regole speciali di variante

Una regola normativa può essere:

* **generale**: valida per la `lega_base`, senza variante specifica
* **speciale di variante**: valida solo per una `variante_lega` o `lega_designazione` specifica

Esempi:

* `2024` → regola generale della lega base
* `2024 Sigma` → regola speciale di variante della lega base `2024`
* `7075 Eppendorf` → regola speciale di variante della lega base `7075`

Quando una regola speciale di variante matcha, prevale sulla regola generale della stessa lega base.

## Regole iniziali estratte da `_Prova Analisi_.xlsx`

Nota di lettura:

* il titolo del foglio Excel corrisponde alla `lega_designazione`
* da quel titolo si ricavano `lega_base` e, se presente, `variante_lega`
* i fogli che coincidono con la sola lega standard rappresentano regole generali
* i fogli con suffissi o nomi aggiuntivi rappresentano regole speciali di variante

### Lega `2014`

**Standard chimico**

| Elemento | Min | Max |
|---|---:|---:|
| Si | 0.5 | 1.2 |
| Fe | NULL | 0.7 |
| Cu | 3.9 | 5 |
| Mn | 0.4 | 1.2 |
| Mg | 0.2 | 0.8 |
| Cr | NULL | 0.1 |
| Ni | NULL | 0.05 |
| Zn | NULL | 0.25 |
| Ti | NULL | 0.15 |
| Pb | NULL | 0.05 |
| V | NULL | 0.05 |
| Bi | NULL | 0.05 |
| Sn | NULL | 0.05 |
| Zr | NULL | 0.2 |
| Be | NULL | 0.05 |
| Zr+Ti | NULL | 0.2 |

**Standard meccanici**

- **Blocco:** EN AW 755-2, T6 — misura: `diametro`
| Range | Rp0.2 | Rm | A% |
|---|---:|---:|---:|
| <= 25 | 370 | 415 | 6 |
| 25 – 75 | 415 | 460 | 7 |
| 75 – 150 | 420 | 465 | 7 |
| 150 – 200 | 350 | 430 | 6 |
| 200 – 250 | 320 | 420 | 5 |

- **Blocco:** EN AW 603-2, T62 — misura: `diametro`
| Range | Rp0.2 | Rm | A% |
|---|---:|---:|---:|
| <= 180 | 440 | 380 | 6 |


### Lega `2017A`

**Standard chimico**

| Elemento | Min | Max |
|---|---:|---:|
| Si | 0.2 | 0.8 |
| Fe | NULL | 0.7 |
| Cu | 3.5 | 4.5 |
| Mn | 0.4 | 1 |
| Mg | 0.4 | 1 |
| Cr | NULL | 0.1 |
| Ni | NULL | 0.05 |
| Zn | NULL | 0.25 |
| Ti | NULL | 0.25 |
| Pb | NULL | 0.05 |
| V | NULL | 0.05 |
| Bi | NULL | 0.05 |
| Sn | NULL | 0.05 |
| Zr | NULL | 0.25 |
| Be | NULL | 0.05 |
| Zr+Ti | NULL | 0.25 |

**Standard meccanici**

- **Blocco:** EN AW 755-2, T4 — misura: `diametro`
| Range | Rp0.2 | Rm | A% |
|---|---:|---:|---:|
| <= 25 | 260 | 380 | 12 |
| 25 – 75 | 270 | 400 | 10 |
| 75 – 150 | 260 | 390 | 9 |
| 150 – 200 | 240 | 370 | 8 |
| 200 – 250 | 220 | 360 | 7 |


### Lega `2024`

**Standard chimico**

| Elemento | Min | Max |
|---|---:|---:|
| Si | NULL | 0.5 |
| Fe | NULL | 0.5 |
| Cu | 3.8 | 4.9 |
| Mn | 0.3 | 0.9 |
| Mg | 1.2 | 1.8 |
| Cr | NULL | 0.1 |
| Ni | NULL | 0.05 |
| Zn | NULL | 0.25 |
| Ti | NULL | 0.15 |
| Pb | NULL | 0.05 |
| V | NULL | 0.05 |
| Bi | NULL | 0.05 |
| Sn | NULL | 0.05 |
| Zr | NULL | 0.2 |
| Be | NULL | 0.05 |
| Zr+Ti | NULL | 0.2 |

**Standard meccanici**

- **Blocco:** EN AW 603-2, T4 — misura: `diametro`
| Range | Rp0.2 | Rm | A% |
|---|---:|---:|---:|
| <= 150 | 260 | 420 | 8 |


### Lega `2024 Sigma`

**Standard chimico**

| Elemento | Min | Max |
|---|---:|---:|
| Si | NULL | 0.12 |
| Fe | NULL | 0.2 |
| Cu | 3.8 | 4.9 |
| Mn | 0.3 | 0.9 |
| Mg | 1.2 | 1.8 |
| Cr | 0.03 | 0.1 |
| Ni | NULL | 0.05 |
| Zn | NULL | 0.25 |
| Ti | NULL | 0.15 |
| Pb | NULL | 0.05 |
| V | NULL | 0.05 |
| Bi | NULL | 0.05 |
| Sn | NULL | 0.05 |
| Zr | NULL | 0.2 |
| Be | NULL | 0.05 |
| Zr+Ti | NULL | 0.2 |

**Standard meccanici**

- **Blocco:** LST 05, T4 — misura: `diametro`
| Range | Rp0.2 | Rm | A% |
|---|---:|---:|---:|
| non esplicitato nel blocco | 260 | 420 | 10 |

- **Blocco:** LST 05, T6
| Range | Rp0.2 | Rm | A% |
|---|---:|---:|---:|
| non esplicitato nel blocco | 300 | 450 | 10 |


### Lega `2618A`

**Standard chimico**

| Elemento | Min | Max |
|---|---:|---:|
| Si | 0.15 | 0.25 |
| Fe | 0.9 | 1.4 |
| Cu | 1.8 | 2.7 |
| Mn | NULL | 0.25 |
| Mg | 1.2 | 1.8 |
| Cr | NULL | 0.05 |
| Ni | 0.8 | 1.4 |
| Zn | NULL | 0.15 |
| Ti | NULL | 0.2 |
| Pb | NULL | 0.05 |
| V | NULL | 0.05 |
| Bi | NULL | 0.05 |
| Sn | NULL | 0.05 |
| Zr | NULL | 0.25 |
| Be | NULL | 0.05 |
| Zr+Ti | NULL | 0.25 |

**Standard meccanici**

- **Blocco:** EN AW 755-2, T6 — misura: `diametro`
| Range | Rp0.2 | Rm | A% |
|---|---:|---:|---:|
| <= 10 | 330 | 410 | 6 |
| 10 – 100 | 360 | 420 | 7 |


### Lega `2618A Adixen`

**Standard chimico**

| Elemento | Min | Max |
|---|---:|---:|
| Si | 0.15 | 0.25 |
| Fe | 0.9 | 1.4 |
| Cu | 1.8 | 2.7 |
| Mn | NULL | 0.25 |
| Mg | 1.2 | 1.8 |
| Cr | NULL | 0.05 |
| Ni | 0.8 | 1.4 |
| Zn | NULL | 0.15 |
| Ti | NULL | 0.2 |
| Pb | NULL | 0.005 |
| V | NULL | 0.05 |
| Bi | NULL | 0.005 |
| Sn | NULL | 0.05 |
| Zr | NULL | 0.25 |
| Be | NULL | 0.05 |
| Zr+Ti | NULL | 0.25 |
| Bi+Pb | NULL | 0.008 |

**Standard meccanici**

- **Blocco:** EN AW 755-2, T6 — misura: `diametro`
| Range | Rp0.2 | Rm | A% |
|---|---:|---:|---:|
| <= 10 | 330 | 410 | 6 |
| 10 – 100 | 360 | 420 | 7 |


### Lega `5754`

**Standard chimico**

| Elemento | Min | Max |
|---|---:|---:|
| Si | NULL | 0.4 |
| Fe | NULL | 0.4 |
| Cu | NULL | 0.1 |
| Mn | NULL | 0.5 |
| Mg | 2.6 | 3.6 |
| Cr | NULL | 0.3 |
| Ni | NULL | 0.05 |
| Zn | NULL | 0.2 |
| Ti | NULL | 0.15 |
| Pb | NULL | 0.05 |
| V | NULL | 0.05 |
| Bi | NULL | 0.05 |
| Sn | NULL | 0.05 |
| Zr | NULL | 0.25 |
| Be | NULL | 0.05 |
| Mn+Cr | 0.1 | 0.6 |

**Standard meccanici**

- **Blocco:** EN AW 755-2, H112 — misura: `diametro`
| Range | Rp0.2 | Rm | A% |
|---|---:|---:|---:|
| <= 150 | 80 | 180 | 14 |
| 150 – 250 | 70 | 180 | 13 |


### Lega `6005A`

**Standard chimico**

| Elemento | Min | Max |
|---|---:|---:|
| Si | 0.5 | 0.9 |
| Fe | NULL | 0.35 |
| Cu | NULL | 0.3 |
| Mn | NULL | 0.5 |
| Mg | 0.4 | 0.7 |
| Cr | NULL | 0.3 |
| Ni | NULL | 0.05 |
| Zn | NULL | 0.2 |
| Ti | NULL | 0.1 |
| Pb | NULL | 0.05 |
| V | NULL | 0.05 |
| Bi | NULL | 0.05 |
| Sn | NULL | 0.05 |
| Zr | NULL | 0.05 |
| Be | NULL | 0.05 |
| Mn+Cr | 0.12 | 0.5 |

**Standard meccanici**

- **Blocco:** EN AW 755-2, T6 — misura: `diametro`
| Range | Rp0.2 | Rm | A% |
|---|---:|---:|---:|
| <= 25 | 225 | 270 | 10 |
| 25 – 50 | 225 | 270 | 8 |
| 50 – 100 | 215 | 260 | 8 |


### Lega `6060`

**Standard chimico**

| Elemento | Min | Max |
|---|---:|---:|
| Si | 0.3 | 0.6 |
| Fe | 0.1 | 0.3 |
| Cu | NULL | 0.1 |
| Mn | NULL | 0.1 |
| Mg | 0.35 | 0.6 |
| Cr | NULL | 0.05 |
| Ni | NULL | 0.05 |
| Zn | NULL | 0.15 |
| Ti | NULL | 0.1 |
| Pb | NULL | 0.05 |
| V | NULL | 0.05 |
| Bi | NULL | 0.05 |
| Sn | NULL | 0.05 |
| Zr | NULL | 0.05 |
| Be | NULL | 0.05 |

**Standard meccanici**

- **Blocco:** EN AW 755-2, T6 — misura: `diametro`
| Range | Rp0.2 | Rm | A% |
|---|---:|---:|---:|
| <= 150 | 150 | 190 | 8 |


### Lega `6082`

**Standard chimico**

| Elemento | Min | Max |
|---|---:|---:|
| Si | 0.7 | 1.3 |
| Fe | NULL | 0.5 |
| Cu | NULL | 0.1 |
| Mn | 0.4 | 1 |
| Mg | 0.6 | 1.2 |
| Cr | NULL | 0.25 |
| Ni | NULL | 0.05 |
| Zn | NULL | 0.2 |
| Ti | NULL | 0.1 |
| Pb | NULL | 0.05 |
| V | NULL | 0.05 |
| Bi | NULL | 0.05 |
| Sn | NULL | 0.05 |
| Zr | NULL | 0.05 |
| Be | NULL | 0.05 |

**Standard meccanici**

- **Blocco:** EN AW 755-2, T6 BARRE — misura: `diametro`
| Range | Rp0.2 | Rm | A% |
|---|---:|---:|---:|
| <= 20 | 250 | 295 | 8 |
| 20 – 150 | 260 | 310 | 8 |
| 150 – 200 | 240 | 280 | 6 |
| 200 – 250 | 200 | 270 | 6 |

- **Blocco:** EN AW 755-2, T6 PROFILI — misura: `spessore`
| Range | Rp0.2 | Rm | A% |
|---|---:|---:|---:|
| <= 5 | 250 | 290 | 8 |
| 5 – 25 | 260 | 310 | 10 |


### Lega `6082H`

**Standard chimico**

| Elemento | Min | Max |
|---|---:|---:|
| Si | 1.1 | 1.25 |
| Fe | NULL | 0.4 |
| Cu | 0.04 | 0.08 |
| Mn | 0.6 | 0.8 |
| Mg | 0.75 | 0.95 |
| Cr | NULL | 0.25 |
| Ni | NULL | 0.05 |
| Zn | NULL | 0.15 |
| Ti | 0.03 | 0.1 |
| Pb | NULL | 0.05 |
| V | NULL | 0.05 |
| Bi | NULL | 0.03 |
| Sn | NULL | 0.05 |
| Zr | NULL | 0.05 |
| Be | NULL | 0.05 |

**Standard meccanici**

- **Blocco:** EN AW 755-2, T6 — misura: `diametro`
| Range | Rp0.2 | Rm | A% |
|---|---:|---:|---:|
| <= 1000 | 340 | 380 | 10 |


### Lega `6082L`

**Standard chimico**

| Elemento | Min | Max |
|---|---:|---:|
| Si | 0.7 | 1.3 |
| Fe | NULL | 0.5 |
| Cu | NULL | 0.05 |
| Mn | 0.4 | 1 |
| Mg | 0.6 | 1.2 |
| Cr | NULL | 0.25 |
| Ni | NULL | 0.05 |
| Zn | NULL | 0.2 |
| Ti | NULL | 0.1 |
| Pb | NULL | 0.005 |
| V | NULL | 0.05 |
| Bi | NULL | 0.05 |
| Sn | NULL | 0.05 |
| Zr | NULL | 0.05 |
| Be | NULL | 0.05 |

**Standard meccanici**

- **Blocco:** EN AW 755-2, T6 — misura: `diametro`
| Range | Rp0.2 | Rm | A% |
|---|---:|---:|---:|
| <= 20 | 250 | 295 | 8 |
| 20 – 150 | 260 | 310 | 8 |
| 150 – 200 | 240 | 280 | 6 |
| 200 – 250 | 200 | 270 | 6 |


### Lega `6110A`

**Standard chimico**

| Elemento | Min | Max |
|---|---:|---:|
| Si | 0.8 | 1 |
| Fe | NULL | 0.2 |
| Cu | 0.4 | 0.5 |
| Mn | 0.4 | 0.5 |
| Mg | 0.7 | 0.9 |
| Cr | 0.05 | 0.25 |
| Ni | NULL | 0.05 |
| Zn | NULL | 0.05 |
| Ti | NULL | 0.05 |
| Pb | NULL | 0.05 |
| V | NULL | 0.05 |
| Bi | NULL | 0.05 |
| Sn | NULL | 0.05 |
| Zr | 0.08 | 0.14 |
| Be | 0.005 | 0.006 |
| Zr+Ti | NULL | 0.2 |

**Standard meccanici**

- **Blocco:** EN AW 755-2, T6 — misura: `diametro`
| Range | Rp0.2 | Rm | A% |
|---|---:|---:|---:|
| <= 120 | 380 | 410 | 10 |


### Lega `6182`

**Standard chimico**

| Elemento | Min | Max |
|---|---:|---:|
| Si | 0.9 | 1.3 |
| Fe | NULL | 0.5 |
| Cu | NULL | 0.1 |
| Mn | 0.5 | 1 |
| Mg | 0.7 | 1.2 |
| Cr | NULL | 0.25 |
| Ni | NULL | 0.05 |
| Zn | NULL | 0.2 |
| Ti | NULL | 0.1 |
| Pb | NULL | 0.05 |
| V | NULL | 0.05 |
| Bi | NULL | 0.05 |
| Sn | NULL | 0.05 |
| Zr | 0.05 | 0.2 |
| Be | NULL | 0.05 |

**Standard meccanici**

- **Blocco:** EN AW 755-2, T6 — misura: `diametro`
| Range | Rp0.2 | Rm | A% |
|---|---:|---:|---:|
| 9 – 100 | 330 | 360 | 9 |
| 100 – 150 | 300 | 330 | 8 |
| 150 – 220 | 240 | 280 | 6 |


### Lega `6182 LST07`

**Standard chimico**

| Elemento | Min | Max |
|---|---:|---:|
| Si | 1.2 | 1.3 |
| Fe | NULL | 0.3 |
| Cu | 0.04 | 0.08 |
| Mn | 0.5 | 0.65 |
| Mg | 0.75 | 0.95 |
| Cr | NULL | 0.25 |
| Ni | NULL | 0.05 |
| Zn | NULL | 0.2 |
| Ti | NULL | 0.1 |
| Pb | NULL | 0.01 |
| V | NULL | 0.05 |
| Bi | NULL | 0.01 |
| Sn | NULL | 0.03 |
| Zr | 0.05 | 0.2 |
| Be | 0.005 | 0.008 |

**Standard meccanici**

- **Blocco:** EN AW 755-2, T6 — misura: `diametro`
| Range | Rp0.2 | Rm | A% |
|---|---:|---:|---:|
| <= 1000 | 340 | 380 | 10 |


### Lega `7003`

**Standard chimico**

| Elemento | Min | Max |
|---|---:|---:|
| Si | NULL | 0.3 |
| Fe | NULL | 0.35 |
| Cu | NULL | 0.2 |
| Mn | NULL | 0.3 |
| Mg | 0.5 | 1 |
| Cr | NULL | 0.2 |
| Ni | NULL | 0.05 |
| Zn | 5 | 6.5 |
| Ti | NULL | 0.2 |
| Pb | NULL | 0.05 |
| V | NULL | 0.05 |
| Bi | NULL | 0.05 |
| Sn | NULL | 0.05 |
| Zr | 0.05 | 0.25 |
| Be | NULL | 0.05 |

**Standard meccanici**

- **Blocco:** EN AW 755-2, T6 — misura: `diametro`
| Range | Rp0.2 | Rm | A% |
|---|---:|---:|---:|
| <= 50 | 290 | 350 | 8 |
| 50 – 150 | 280 | 340 | 8 |


### Lega `7055`

**Standard chimico**

| Elemento | Min | Max |
|---|---:|---:|
| Si | NULL | 0.1 |
| Fe | NULL | 0.15 |
| Cu | 2 | 2.6 |
| Mn | NULL | 0.05 |
| Mg | 1.8 | 2.3 |
| Cr | NULL | 0.04 |
| Ni | NULL | 0.05 |
| Zn | 7.6 | 8.4 |
| Ti | NULL | 0.06 |
| Pb | NULL | 0.05 |
| V | NULL | 0.05 |
| Bi | NULL | 0.05 |
| Sn | NULL | 0.05 |
| Zr | 0.08 | 0.25 |
| Be | NULL | 0.05 |

**Standard meccanici**

- **Blocco:** EN AW 755-2, T76 — misura: `diametro`
| Range | Rp0.2 | Rm | A% |
|---|---:|---:|---:|
| <= 1000 | 550 | 600 | 8 |


### Lega `7075`

**Standard chimico**

| Elemento | Min | Max |
|---|---:|---:|
| Si | NULL | 0.4 |
| Fe | NULL | 0.5 |
| Cu | 1.2 | 2 |
| Mn | NULL | 0.3 |
| Mg | 2.1 | 2.9 |
| Cr | 0.18 | 0.28 |
| Ni | NULL | 0.05 |
| Zn | 5.1 | 6.1 |
| Ti | NULL | 0.2 |
| Pb | NULL | 0.05 |
| V | NULL | 0.05 |
| Bi | NULL | 0.05 |
| Sn | NULL | 0.05 |
| Zr | NULL | 0.25 |
| Be | NULL | 0.05 |
| Zr+Ti | NULL | 0.25 |

**Standard meccanici**

- **Blocco:** EN AW 755-2, T6 — misura: `diametro`
| Range | Rp0.2 | Rm | A% |
|---|---:|---:|---:|
| <= 25 | 480 | 540 | 7 |
| 25 – 100 | 500 | 560 | 7 |
| 100 – 150 | 440 | 550 | 5 |
| 150 – 200 | 400 | 440 | 5 |

- **Blocco:** EN AW 755-2, T73 — misura: `diametro`
| Range | Rp0.2 | Rm | A% |
|---|---:|---:|---:|
| <= 25 | 420 | 485 | 7 |
| 25 – 75 | 405 | 475 | 7 |
| 75 – 100 | 390 | 470 | 6 |
| 100 – 150 | 360 | 440 | 6 |


### Lega `7075 Eppendorf`

**Standard chimico**

| Elemento | Min | Max |
|---|---:|---:|
| Si | NULL | 0.4 |
| Fe | NULL | 0.5 |
| Cu | 1.2 | 2 |
| Mn | NULL | 0.3 |
| Mg | 2.1 | 2.9 |
| Cr | 0.18 | 0.28 |
| Ni | NULL | 0.05 |
| Zn | 5.1 | 6.1 |
| Ti | NULL | 0.2 |
| Pb | NULL | 0.05 |
| V | NULL | 0.05 |
| Bi | NULL | 0.05 |
| Sn | NULL | 0.05 |
| Zr | NULL | 0.25 |
| Be | NULL | 0.05 |
| Zr+Ti | NULL | 0.25 |

**Standard meccanici**

- **Blocco:** EN AW 755-2, T6 — misura: `diametro`
| Range | Rp0.2 | Rm | A% |
|---|---:|---:|---:|
| <= 25 | 480 | 540 | 7 |
| 25 – 100 | 500 | 560 | 7 |
| 100 – 150 | 440 | 550 | 5 |
| 150 – 200 | 400 | 440 | 5 |

- **Blocco:** EN AW 755-2, T73 — misura: `diametro`
| Range | Rp0.2 | Rm | A% |
|---|---:|---:|---:|
| <= 25 | 420 | 485 | 7 |
| 25 – 75 | 405 | 475 | 7 |
| 75 – 100 | 390 | 470 | 6 |
| 100 – 150 | 360 | 440 | 6 |


### Lega `7150`

**Standard chimico**

| Elemento | Min | Max |
|---|---:|---:|
| Si | NULL | 0.12 |
| Fe | NULL | 0.15 |
| Cu | 1.9 | 2.5 |
| Mn | NULL | 0.1 |
| Mg | 2 | 2.7 |
| Cr | NULL | 0.04 |
| Ni | NULL | 0.05 |
| Zn | 5.9 | 6.9 |
| Ti | NULL | 0.06 |
| Pb | NULL | 0.05 |
| V | NULL | 0.05 |
| Bi | NULL | 0.05 |
| Sn | NULL | 0.05 |
| Zr | 0.08 | 0.15 |
| Be | NULL | 0.05 |

**Standard meccanici**

- **Blocco:** EN AW 755-2, T76 — misura: `diametro`
| Range | Rp0.2 | Rm | A% | IACS% |
|---|---:|---:|---:|---:|
| <= 1000 | 525 | 580 | 8 | 33 |


### Lega `7175`

**Standard chimico**

| Elemento | Min | Max |
|---|---:|---:|
| Si | NULL | 0.15 |
| Fe | NULL | 0.2 |
| Cu | 1.2 | 2 |
| Mn | NULL | 0.1 |
| Mg | 2.1 | 2.9 |
| Cr | NULL | 0.28 |
| Ni | NULL | 0.05 |
| Zn | 5.1 | 6.1 |
| Ti | NULL | 0.1 |
| Pb | NULL | 0.05 |
| V | NULL | 0.05 |
| Bi | NULL | 0.05 |
| Sn | NULL | 0.05 |
| Zr | NULL | 0.05 |
| Be | NULL | 0.05 |

**Standard meccanici**

- **Blocco:** EN AW 755-2, T6 — misura: `diametro`
| Range | Rp0.2 | Rm | A% |
|---|---:|---:|---:|
| <= 1000 | 0 | 0 | 0 |

## Regola di selezione (CRITICA)

Quando più standard matchano:

1. considerare solo quelli della `lega_base`
2. se il caso ha una `variante_lega`, cercare prima le regole speciali compatibili
3. se nessuna regola speciale matcha, usare le regole generali della `lega_base`
4. applicare i filtri (`norma`, `trattamento_termico`, `tipo_prodotto` se presenti)
5. verificare il range (`diametro` / `spessore`)
6. tra le regole valide, selezionare quella più specifica:

- più campi valorizzati (norma, trattamento, tipo)
- range più stretto

Se più regole risultano equivalenti:
→ errore o warning (non scegliere arbitrariamente)
