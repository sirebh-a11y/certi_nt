# Nuovo set test flusso fornitori - 2026-05-11

Cartella preparata:

`C:\Users\sireb\OneDrive\Desktop\Sire activity\ArInt\Case Forgital\Cerificati Training\test_flusso_fornitori\NUOVO_SET_2026-05-11`

Questo set e' nuovo rispetto al set storico gia' presente in `test_flusso_fornitori`.

## Scenari

Ogni fornitore contiene, dove applicabile:

- `01_match_stesso_run`: DDT e certificati insieme.
- `02_second_run_ddt_prima`: DDT nel primo run.
- `03_second_run_cert_dopo`: certificato nel secondo run/rematch.
- `04_certificate_first_cert_prima`: certificato nel primo run.
- `05_certificate_first_ddt_dopo`: DDT nel secondo run/rematch.

## Fornitori e casi

- Aluminium Bozen: `176.pdf`, `261.pdf`, `419.pdf` con certificati `151238`, `151675`, `151323`.
- Arconic: `27697432.pdf` con `EEP66506`.
- Grupa Kety: `201138817.pdf`, `201144562.pdf`, `201149900.pdf`, `201177772.pdf` con certificati lotto collegati.
- Impol: `5445-11.pdf` con certificati `5445/a`, `5445/b`, `5445/c`, `5445/d`.
- Leichtmetall: `80008518.pdf`, `80008519.pdf`, `80008577.pdf`, `80008578.pdf` con certificati `94683`, `94668`, `94775`.
- Metalba: `26-00957.pdf`, `26-00958.pdf`, `26-00959.pdf`, `26-00961.pdf` con certificati `26-0743`, `26-0744`, `26-0745`, `26-0747`.
- Neuman: `75706589.pdf`, `75716074.pdf` con certificati `25450`, `25537`.
- Zalco: `20858.pdf` con `CdQ_20858`.

## No match controllato

La cartella `_no_match_controllato` contiene:

- `CQF_100037_201452_2023.pdf`
- `CQF_14-0961_2014.pdf`

Questi certificati vanno usati come disturbo controllato: non devono agganciarsi se manca il DDT corretto.
