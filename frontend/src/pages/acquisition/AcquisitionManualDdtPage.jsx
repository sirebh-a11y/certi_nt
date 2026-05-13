import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";

import { apiRequest, fetchApiBlob } from "../../app/api";
import { useAuth } from "../../app/auth";

const FIELD_DEFS = [
  { key: "lega_base", label: "lega" },
  { key: "diametro", label: "Ø" },
  { key: "cdq", label: "Cdq" },
  { key: "colata", label: "Colata" },
  { key: "ddt", label: "Ddt" },
  { key: "peso", label: "peso" },
  { key: "ordine", label: "ordine" },
];

const EMPTY_FIELDS = Object.fromEntries(FIELD_DEFS.map((field) => [field.key, ""]));

const PAGE_CONFIGS = {
  ddt: {
    side: "ddt",
    documentLabel: "DDT",
    documentLabelPlural: "DDT",
    sourceLabel: "ddt",
    uploadEndpoint: "/acquisition/documents/manual-ddt-upload",
    title: "Fallback manuale DDT",
    intro:
      "Usa questa pagina quando il flusso automatico non e disponibile o quando un DDT gia caricato richiede una riga aggiuntiva. Carica il PDF: se era gia presente, il sistema lo riconosce e mostra le righe gia create.",
    rule:
      "Ogni conferma crea una riga Solo DDT. Per DDT multiriga compila i campi della prima riga, crea, poi compila la riga successiva.",
    linkedTitle: "Righe gia create da questo DDT",
    linkedHelper: "Solo guida: qui non modifichi righe esistenti, puoi solo aggiungerne una nuova sotto.",
    emptyRows: "Nessuna riga ancora creata da questo DDT.",
    formTitle: "DDT",
    formHelper: "Compila i campi che l'utente usa per lista e match. I valori saranno salvati come provenienza utente.",
    readyMessage: "PDF DDT pronto. Ora puoi creare una o piu righe da questo documento.",
    createdMessage: "Puoi aggiungere un'altra riga dallo stesso DDT.",
    createButton: "Crea riga DDT",
    creatingButton: "Creo...",
    rowStateLinked: "con certificato",
    rowStateSingle: "solo DDT",
  },
  certificato: {
    side: "certificato",
    documentLabel: "certificato",
    documentLabelPlural: "certificati",
    sourceLabel: "certificato",
    uploadEndpoint: "/acquisition/documents/manual-certificate-upload",
    title: "Fallback manuale certificato",
    intro:
      "Usa questa pagina quando il flusso automatico non e disponibile o quando un certificato gia caricato richiede una riga aggiuntiva. Carica il PDF: se era gia presente, il sistema lo riconosce e mostra le righe gia create.",
    rule:
      "Ogni conferma crea una riga Solo Certificato. Compila i campi ponte del certificato come certificate first, cosi potranno agganciarsi ai DDT coerenti.",
    linkedTitle: "Righe gia create da questo certificato",
    linkedHelper: "Solo guida: qui non modifichi righe esistenti, puoi solo aggiungerne una nuova sotto.",
    emptyRows: "Nessuna riga ancora creata da questo certificato.",
    formTitle: "Certificato",
    formHelper: "Compila i campi ponte letti dal certificato. I valori saranno salvati come provenienza utente.",
    readyMessage: "PDF certificato pronto. Ora puoi creare una o piu righe da questo documento.",
    createdMessage: "Puoi aggiungere un'altra riga dallo stesso certificato.",
    createButton: "Crea riga certificato",
    creatingButton: "Creo...",
    rowStateLinked: "con DDT",
    rowStateSingle: "solo certificato",
  },
};

export function AcquisitionManualCertificatePage() {
  return <AcquisitionManualDocumentPage config={PAGE_CONFIGS.certificato} />;
}

export default function AcquisitionManualDdtPage() {
  return <AcquisitionManualDocumentPage config={PAGE_CONFIGS.ddt} />;
}

function AcquisitionManualDocumentPage({ config }) {
  const { token } = useAuth();
  const [suppliers, setSuppliers] = useState([]);
  const [selectedSupplierId, setSelectedSupplierId] = useState("");
  const [selectedDocumentId, setSelectedDocumentId] = useState("");
  const [selectedDocument, setSelectedDocument] = useState(null);
  const [linkedRows, setLinkedRows] = useState([]);
  const [fields, setFields] = useState(EMPTY_FIELDS);
  const [uploading, setUploading] = useState(false);
  const [creating, setCreating] = useState(false);
  const [loadingDocument, setLoadingDocument] = useState(false);
  const [createdRows, setCreatedRows] = useState([]);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  async function loadInitialData() {
    setError("");
    try {
      const supplierResponse = await apiRequest("/suppliers", {}, token);
      setSuppliers((supplierResponse.items || []).filter((supplier) => supplier.attivo));
    } catch (requestError) {
      setError(requestError.message);
    }
  }

  async function loadDocument(documentId) {
    if (!documentId) {
      setSelectedDocument(null);
      return;
    }
    setLoadingDocument(true);
    setError("");
    try {
      const detail = await apiRequest(`/acquisition/documents/${documentId}`, {}, token);
      setSelectedDocument(detail);
    } catch (requestError) {
      setError(requestError.message);
      setSelectedDocument(null);
    } finally {
      setLoadingDocument(false);
    }
  }

  useEffect(() => {
    void loadInitialData();
  }, [token]);

  function updateField(field, value) {
    setFields((current) => ({ ...current, [field]: value }));
  }

  function clearDocument() {
    setSelectedDocumentId("");
    setSelectedDocument(null);
    setLinkedRows([]);
    setCreatedRows([]);
    setFields(EMPTY_FIELDS);
    setNotice("");
    setError("");
  }

  async function handleUpload(event) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) {
      return;
    }
    if (!selectedSupplierId) {
      setError("Seleziona prima il fornitore.");
      return;
    }

    const formData = new FormData();
    formData.append("tipo_documento", config.side);
    formData.append("fornitore_id", selectedSupplierId);
    formData.append("file", file);
    formData.append("origine_upload", "utente");

    setUploading(true);
    setError("");
    setNotice("");
    try {
      const uploaded = await apiRequest(
        config.uploadEndpoint,
        {
          method: "POST",
          body: formData,
        },
        token,
      );
      setSelectedDocument(uploaded.document);
      setSelectedDocumentId(String(uploaded.document.id));
      setLinkedRows(uploaded.rows || []);
      if (uploaded.document.fornitore_id) {
        setSelectedSupplierId(String(uploaded.document.fornitore_id));
      }
      setNotice(uploaded.message || config.readyMessage);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setUploading(false);
    }
  }

  async function handleCreateRow() {
    if (!selectedSupplierId) {
      setError("Seleziona il fornitore.");
      return;
    }
    if (!selectedDocumentId) {
      setError(`Seleziona o carica un PDF ${config.documentLabel}.`);
      return;
    }
    const hasAnyField = FIELD_DEFS.some((field) => fields[field.key]?.trim());
    if (!hasAnyField) {
      setError("Compila almeno un campo prima di creare la riga.");
      return;
    }

    setCreating(true);
    setError("");
    setNotice("");
    try {
      const created = await apiRequest(
        `/acquisition/documents/${selectedDocumentId}/manual-row`,
        {
          method: "POST",
          body: JSON.stringify({
            side: config.side,
            fornitore_id: Number(selectedSupplierId),
            fields,
          }),
        },
        token,
      );
      setCreatedRows((current) => [created, ...current]);
      setLinkedRows((current) => [...current, created]);
      setFields(EMPTY_FIELDS);
      setNotice(`Riga #${created.id} creata. ${config.createdMessage}`);
      await loadDocument(selectedDocumentId);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setCreating(false);
    }
  }

  return (
    <section className="space-y-4">
      <div className="rounded-3xl border border-border bg-panel p-6 shadow-lg shadow-slate-200/40">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
          <div>
            <p className="text-sm uppercase tracking-[0.3em] text-slate-500">Incoming materiale</p>
            <h2 className="mt-2 text-2xl font-semibold text-ink">{config.title}</h2>
            <p className="mt-2 max-w-4xl text-sm leading-6 text-slate-500">
              {config.intro}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Link className="rounded-xl border border-border bg-white px-4 py-2.5 text-sm font-medium text-slate-700 hover:bg-slate-100" to="/acquisition/upload">
              Torna al caricamento
            </Link>
            <Link className="rounded-xl border border-border bg-white px-4 py-2.5 text-sm font-medium text-slate-700 hover:bg-slate-100" to="/acquisition">
              Torna alla griglia
            </Link>
          </div>
        </div>

        {error ? <p className="mt-4 text-sm text-rose-600">{error}</p> : null}
        {notice ? <p className="mt-4 text-sm text-emerald-700">{notice}</p> : null}

        <div className="mt-5 grid gap-4 xl:grid-cols-[320px,1fr]">
          <aside className="space-y-4">
            <div className="rounded-2xl border border-border bg-white p-4">
              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">1. Documento</p>
              <label className="mt-3 block text-sm font-medium text-slate-700" htmlFor={`manual-${config.side}-supplier`}>
                Fornitore
              </label>
              <select
                className="mt-1 w-full rounded-xl border border-border bg-white px-3 py-2 text-sm text-slate-800 outline-none focus:border-accent"
                id={`manual-${config.side}-supplier`}
                onChange={(event) => setSelectedSupplierId(event.target.value)}
                disabled={Boolean(selectedDocument)}
                value={selectedSupplierId}
              >
                <option value="">Seleziona fornitore</option>
                {suppliers.map((supplier) => (
                  <option key={supplier.id} value={supplier.id}>
                    {supplier.ragione_sociale}
                  </option>
                ))}
              </select>

              <div className="mt-4 rounded-2xl border border-dashed border-slate-300 bg-slate-50 p-4">
                <p className="text-sm font-medium text-slate-700">Carica PDF {config.documentLabel}</p>
                <input
                  accept=".pdf,application/pdf"
                  className="mt-3 block w-full text-sm text-slate-600 file:mr-3 file:rounded-lg file:border file:border-border file:bg-white file:px-3 file:py-2 file:text-sm file:font-medium file:text-slate-700 hover:file:bg-slate-100"
                  disabled={uploading || !selectedSupplierId || Boolean(selectedDocument)}
                  onChange={handleUpload}
                  type="file"
                />
                <p className="mt-2 text-xs leading-5 text-slate-500">Se il PDF era gia caricato, viene riusato e qui sotto vedrai le righe gia create.</p>
                {selectedDocument ? (
                  <button
                    className="mt-3 rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-100"
                    onClick={clearDocument}
                    type="button"
                  >
                    Cambia PDF
                  </button>
                ) : null}
              </div>
            </div>

            <div className="rounded-2xl border border-sky-200 bg-sky-50 p-4">
              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-sky-700">Regola</p>
              <p className="mt-2 text-sm leading-6 text-slate-600">
                {config.rule}
              </p>
            </div>
          </aside>

          <div className="space-y-4">
            <ManualPdfPanel config={config} document={selectedDocument} loading={loadingDocument} token={token} />

            {selectedDocument ? (
              <LinkedRowsGuide config={config} rows={linkedRows} />
            ) : null}

            <div className="rounded-2xl border border-slate-300/80 bg-slate-100/95 p-3">
              <div className="flex flex-col gap-3 xl:flex-row xl:items-stretch xl:justify-between">
                <div className="flex w-full shrink-0 flex-col justify-center rounded-xl border border-sky-200 bg-sky-50 px-3 py-2 xl:w-[230px]">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-sky-700">{config.formTitle}</p>
                  <p className="mt-1.5 text-[11px] leading-tight text-slate-600">
                    {config.formHelper}
                  </p>
                </div>
                <div className="min-w-0 flex-1 overflow-hidden rounded-2xl border border-slate-400 bg-slate-50">
                  <div className="overflow-x-auto">
                    <div className="grid auto-cols-[108px] grid-flow-col gap-0 border-b border-slate-200">
                      {FIELD_DEFS.map((field) => (
                        <div className="border-r border-slate-200 px-1.5 py-1" key={field.key}>
                          <p className="text-center text-[11px] font-semibold leading-none text-slate-600">{field.label}</p>
                          <input
                            className="mt-1 w-full rounded-md border border-slate-200 bg-white px-1 py-1 text-center text-[13px] text-slate-800 outline-none transition focus:border-accent"
                            onChange={(event) => updateField(field.key, event.target.value)}
                            placeholder="Valore"
                            value={fields[field.key] || ""}
                          />
                          <p className="mt-1 text-center text-[8px] font-semibold uppercase tracking-[0.03em] text-amber-600">Origine</p>
                          <p className="min-h-[20px] text-center text-[10px] font-medium leading-tight text-slate-600">{config.sourceLabel} - utente</p>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
                <div className="flex w-full shrink-0 flex-col gap-3 xl:w-[230px] xl:self-start">
                  <button
                    className="rounded-xl border border-slate-300 bg-white px-4 py-2.5 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-60"
                    disabled={creating}
                    onClick={() => setFields(EMPTY_FIELDS)}
                    type="button"
                  >
                    Pulisci campi
                  </button>
                  <button
                    className="rounded-xl bg-accent px-4 py-2.5 text-sm font-semibold text-white hover:bg-teal-700 disabled:opacity-60"
                    disabled={creating || !selectedDocumentId || !selectedSupplierId}
                    onClick={handleCreateRow}
                    type="button"
                  >
                    {creating ? config.creatingButton : config.createButton}
                  </button>
                </div>
              </div>
            </div>

            {createdRows.length ? (
              <div className="rounded-2xl border border-border bg-white p-4">
                <p className="text-sm font-semibold text-slate-900">Righe create in questa sessione</p>
                <div className="mt-3 space-y-2">
                  {createdRows.map((row) => (
                    <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2" key={row.id}>
                      <span className="text-sm text-slate-700">
                        Riga #{row.id} · {row.cdq || "-"} · {row.colata || "-"} · {row.peso || "-"}
                      </span>
                      <Link className="text-sm font-semibold text-accent hover:underline" to={`/acquisition/${row.id}/document-matching`}>
                        Apri riga
                      </Link>
                    </div>
                  ))}
                </div>
              </div>
            ) : null}
          </div>
        </div>
      </div>
    </section>
  );
}

function LinkedRowsGuide({ config, rows }) {
  return (
    <div className="rounded-2xl border border-border bg-white p-4">
      <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
        <div>
          <p className="text-sm font-semibold text-slate-900">{config.linkedTitle}</p>
          <p className="mt-1 text-xs leading-5 text-slate-500">{config.linkedHelper}</p>
        </div>
        <span className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs font-semibold text-slate-600">
          {rows.length} righe
        </span>
      </div>
      {rows.length ? (
        <div className="mt-3 overflow-x-auto rounded-2xl border border-slate-200">
          <table className="min-w-full divide-y divide-slate-200 text-sm">
            <thead className="bg-slate-50">
              <tr className="text-left text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">
                <th className="px-3 py-2">Riga</th>
                <th className="px-3 py-2">lega</th>
                <th className="px-3 py-2">Ø</th>
                <th className="px-3 py-2">Cdq</th>
                <th className="px-3 py-2">Colata</th>
                <th className="px-3 py-2">Ddt</th>
                <th className="px-3 py-2">Peso</th>
                <th className="px-3 py-2">Ordine</th>
                <th className="px-3 py-2">Stato</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 bg-white">
              {rows.map((row) => (
                <tr key={row.id}>
                  <td className="whitespace-nowrap px-3 py-2">
                    <Link className="font-semibold text-accent hover:underline" to={`/acquisition/${row.id}/document-matching`}>
                      #{row.id}
                    </Link>
                  </td>
                  <td className="whitespace-nowrap px-3 py-2 text-slate-700">{row.lega_designazione || row.lega_base || row.variante_lega || "-"}</td>
                  <td className="whitespace-nowrap px-3 py-2 text-slate-700">{row.diametro || "-"}</td>
                  <td className="whitespace-nowrap px-3 py-2 text-slate-700">{row.cdq || "-"}</td>
                  <td className="whitespace-nowrap px-3 py-2 text-slate-700">{row.colata || "-"}</td>
                  <td className="whitespace-nowrap px-3 py-2 text-slate-700">{row.ddt || "-"}</td>
                  <td className="whitespace-nowrap px-3 py-2 text-slate-700">{row.peso || "-"}</td>
                  <td className="whitespace-nowrap px-3 py-2 text-slate-700">{row.ordine || "-"}</td>
                  <td className="whitespace-nowrap px-3 py-2 text-slate-600">
                    {(config.side === "ddt" ? row.document_certificato_id : row.document_ddt_id) ? config.rowStateLinked : config.rowStateSingle}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="mt-3 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-500">
          {config.emptyRows}
        </p>
      )}
    </div>
  );
}

function ManualPdfPanel({ config, document, loading, token }) {
  const [pageImages, setPageImages] = useState([]);
  const [zoom, setZoom] = useState(100);
  const [error, setError] = useState("");
  const viewportRef = useRef(null);
  const [viewportWidth, setViewportWidth] = useState(0);

  useEffect(() => {
    let ignore = false;
    const objectUrls = [];

    async function loadImages() {
      const pages = (document?.pages || []).filter((page) => page.image_url);
      if (!pages.length) {
        setPageImages([]);
        return;
      }
      try {
        const loaded = await Promise.all(
          pages.map(async (page) => {
            const blob = await fetchApiBlob(page.image_url, token);
            const objectUrl = URL.createObjectURL(blob);
            objectUrls.push(objectUrl);
            return { id: page.id, numero_pagina: page.numero_pagina, src: objectUrl };
          }),
        );
        if (!ignore) {
          setPageImages(loaded);
          setError("");
        }
      } catch (requestError) {
        if (!ignore) {
          setPageImages([]);
          setError(requestError.message);
        }
      }
    }

    void loadImages();
    return () => {
      ignore = true;
      objectUrls.forEach((url) => URL.revokeObjectURL(url));
    };
  }, [document, token]);

  useEffect(() => {
    const node = viewportRef.current;
    if (!node) {
      return undefined;
    }
    function updateViewportWidth() {
      setViewportWidth(Math.max(node.clientWidth - 24, 0));
    }
    updateViewportWidth();
    const observer = new ResizeObserver(updateViewportWidth);
    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  return (
    <div className="rounded-2xl border border-slate-600 bg-slate-700 p-4">
      <div className="mb-3 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-300">PDF {config.documentLabel}</p>
          <p className="mt-1 text-sm text-white">{document?.nome_file_originale || "Seleziona o carica un documento"}</p>
        </div>
        <div className="flex items-center gap-2">
          <button className="rounded-lg border border-slate-500 bg-slate-700 px-3 py-2 text-sm font-semibold text-white hover:bg-slate-600" onClick={() => setZoom((current) => Math.max(50, current - 10))} type="button">
            -
          </button>
          <span className="min-w-[64px] text-center text-sm font-semibold text-white">{zoom}%</span>
          <button className="rounded-lg border border-slate-500 bg-slate-700 px-3 py-2 text-sm font-semibold text-white hover:bg-slate-600" onClick={() => setZoom((current) => Math.min(250, current + 10))} type="button">
            +
          </button>
        </div>
      </div>

      <div className="h-[46vh] overflow-auto rounded-2xl border border-slate-600 bg-slate-700 p-3" ref={viewportRef}>
        {loading ? (
          <div className="flex h-full items-center justify-center px-6 text-sm text-slate-200">Caricamento PDF...</div>
        ) : pageImages.length ? (
          <div className="space-y-4">
            {pageImages.map((page) => (
              <div className="w-full" key={page.id}>
                <p className="mb-2 text-center text-xs font-semibold uppercase tracking-[0.14em] text-slate-300">Pagina {page.numero_pagina}</p>
                <div className="relative" style={{ width: viewportWidth > 0 ? `${(viewportWidth * zoom) / 100}px` : "100%" }}>
                  <img alt={`${config.documentLabel} pagina ${page.numero_pagina}`} className="block w-full rounded-xl border border-slate-200 bg-white shadow-sm" draggable={false} src={page.src} />
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="flex h-full items-center justify-center px-6 text-sm text-slate-200">
            {error || "Nessun PDF selezionato o immagini pagina non disponibili."}
          </div>
        )}
      </div>
    </div>
  );
}
