export default function AlloyMatchNotice({ row, alloyEdited = false }) {
  const values = Array.isArray(row?.values) ? row.values : [];
  const alloyValues = [
    values.find(value => value.blocco === "ddt" && value.campo === "lega"),
    values.find(value => value.blocco === "match" && value.campo === "lega_certificato"),
  ];
  const lst03Applied = Boolean(
    row?.document_ddt_id && row?.document_certificato_id && !alloyEdited &&
    alloyValues.every(value => value?.metodo_lettura === "metalba_lst03"),
  );
  const isMetalba = lst03Applied || /\bmetalba\b/i.test(row?.fornitore_nome || row?.fornitore_raw || "");

  return (
    <div role="note" aria-label="Informazioni sulla lega" className="rounded-lg border border-sky-100 bg-sky-50/70 px-3 py-2 text-lg leading-relaxed text-slate-600">
      <p><span className="font-semibold text-slate-800">Lega:</span> qui trovi il valore completo; in Incoming è mostrato senza lo stato fisico. Modificalo solo per correggere un errore di lettura.</p>
      {isMetalba ? (
        <p className="mt-1">
          {lst03Applied
            ? "6082H proposta dalla specifica LST03. I valori originali sono conservati per il confronto."
            : "Metalba: finché è presente un solo documento, vedi la lega letta. Quando DDT e certificato sono collegati e la lettura è completa, CERTI verifica la specifica LST03 e i dati del materiale. Se concordano, propone 6082H su entrambi i lati. Non occorre cambiarla a mano; le leghe già confermate o modificate manualmente restano protette."}
        </p>
      ) : null}
    </div>
  );
}
