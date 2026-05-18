# Placeholder audit overlay e cattura tabella fornitori

Scopo: verificare in modo sistematico overlay e cattura tabella su chimica/proprieta per tutti i fornitori, senza introdurre patch puntuali che rompano logiche gia funzionanti.

## Da auditare

- Overlay chimica: pagina corretta, riga corretta, valori associati all'elemento corretto, esclusione di min/max/spec.
- Cattura tabella chimica: tabella orizzontale, verticale, compatta, righe multilinea, valori con virgola/punto e campi non gestiti.
- Overlay proprieta: valori minimi gia calcolati in UI, ricerca nei dintorni della riga/colonna quando il valore deriva da piu misure.
- Fornitori gia presenti: Aluminium Bozen, AWW, Impol, Leichtmetall, Metalba, Neuman, Zalco, Arconic, Grupa Kety.

## Regole da preservare

- Ogni fornitore puo avere parser dedicato se la struttura documento lo richiede.
- Il generico resta fallback, non deve prevalere su una geometria fornitore piu sicura.
- Le righe `min`, `max`, `norm`, `spec limits`, `test limits` non devono essere lette come valori misurati.
- Il box deve puntare al valore dell'elemento, non solo alla riga o alla tabella intera.

## Test attesi

- Almeno un certificato per fornitore con overlay chimica.
- Almeno un test cattura tabella per fornitore dove applicabile.
- Verifica regressione sui casi gia corretti: AWW, Neuman, Metalba, Zalco, Arconic.
