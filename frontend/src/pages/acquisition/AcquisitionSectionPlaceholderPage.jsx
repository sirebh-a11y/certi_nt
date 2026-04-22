import { useEffect, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";

import { apiRequest } from "../../app/api";
import { useAuth } from "../../app/auth";
import AcquisitionChemistrySectionPage from "./AcquisitionChemistrySectionPage";
import AcquisitionPropertiesSectionPage from "./AcquisitionPropertiesSectionPage";
import AcquisitionRowSummaryCard from "./AcquisitionRowSummaryCard";

const SECTION_TITLES = {
  "document-matching": "Matching documentale",
  chemistry: "Chimica",
  properties: "Proprietà",
  notes: "Note",
};

export default function AcquisitionSectionPlaceholderPage() {
  const { token } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const { rowId, sectionKey } = useParams();
  const title = SECTION_TITLES[sectionKey] || "Sezione";
  const [row, setRow] = useState(null);
  const [certificateDocument, setCertificateDocument] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [sectionDirty, setSectionDirty] = useState(false);
  const [exitDialogOpen, setExitDialogOpen] = useState(false);
  const [pendingPath, setPendingPath] = useState("");

  async function loadRow() {
    setLoading(true);
    setError("");
    try {
      const rowData = await apiRequest(`/acquisition/rows/${rowId}`, {}, token);
      setRow(rowData);
      if (rowData.certificate_document?.id) {
        const certificateData = await apiRequest(`/acquisition/documents/${rowData.certificate_document.id}`, {}, token);
        setCertificateDocument(certificateData);
      } else {
        setCertificateDocument(null);
      }
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    let ignore = false;

    async function load() {
      try {
        const rowData = await apiRequest(`/acquisition/rows/${rowId}`, {}, token);
        if (!ignore) {
          setRow(rowData);
        }
        if (rowData.certificate_document?.id) {
          const certificateData = await apiRequest(`/acquisition/documents/${rowData.certificate_document.id}`, {}, token);
          if (!ignore) {
            setCertificateDocument(certificateData);
          }
        } else if (!ignore) {
          setCertificateDocument(null);
        }
      } catch (requestError) {
        if (!ignore) {
          setError(requestError.message);
        }
      } finally {
        if (!ignore) {
          setLoading(false);
        }
      }
    }

    load();

    return () => {
      ignore = true;
    };
  }, [rowId, token]);

  useEffect(() => {
    if (!["chemistry", "properties"].includes(sectionKey)) {
      return undefined;
    }

    function handleDocumentClick(event) {
      if (!sectionDirty) {
        return;
      }
      const target = event.target instanceof Element ? event.target.closest("a[href]") : null;
      if (!(target instanceof HTMLAnchorElement)) {
        return;
      }
      const href = target.getAttribute("href");
      if (!href || href.startsWith("#") || href.startsWith("mailto:") || href.startsWith("tel:")) {
        return;
      }

      const url = new URL(target.href, window.location.origin);
      const nextPath = `${url.pathname}${url.search}${url.hash}`;
      const currentPath = `${location.pathname}${location.search}${location.hash}`;
      if (url.origin !== window.location.origin || nextPath === currentPath) {
        return;
      }

      event.preventDefault();
      setPendingPath(nextPath);
      setExitDialogOpen(true);
    }

    document.addEventListener("click", handleDocumentClick, true);
    return () => document.removeEventListener("click", handleDocumentClick, true);
  }, [location.hash, location.pathname, location.search, sectionDirty, sectionKey]);

  function handleBackToList() {
    if (["chemistry", "properties"].includes(sectionKey) && sectionDirty) {
      setPendingPath("/acquisition");
      setExitDialogOpen(true);
      return;
    }
    navigate("/acquisition");
  }

  function handleLeaveWithoutConfirm() {
    setExitDialogOpen(false);
    setSectionDirty(false);
    navigate(pendingPath || "/acquisition");
  }

  return (
    <section className="space-y-4">
      {loading ? <p className="text-sm text-slate-500">Caricamento riga...</p> : null}
      {error ? <p className="text-sm text-rose-600">{error}</p> : null}
      {row ? (
        <div className="rounded-2xl border border-slate-600 bg-slate-700 p-3">
          <div className="flex flex-col gap-4 xl:flex-row xl:items-stretch">
            <div className="flex min-h-[92px] w-full shrink-0 flex-col justify-center rounded-2xl border border-slate-600 bg-slate-700 px-5 py-3 xl:w-[230px]">
              <p className="text-[17px] font-semibold leading-none text-slate-200">Riga #{rowId}</p>
              <h1 className="mt-1.5 text-[31px] font-semibold leading-none text-white">{title}</h1>
            </div>
            <div className="min-w-0 flex-1">
              <AcquisitionRowSummaryCard
                compact
                containerClassName="min-h-[92px]"
                row={row}
                rowId={rowId}
                showTitle={false}
              />
            </div>
          </div>
        </div>
      ) : null}
      {row && sectionKey === "chemistry" ? (
        <AcquisitionChemistrySectionPage
          certificateDocument={certificateDocument}
          onDirtyChange={setSectionDirty}
          onRefreshRow={loadRow}
          row={row}
          rowId={rowId}
          token={token}
        />
      ) : null}
      {row && sectionKey === "properties" ? (
        <AcquisitionPropertiesSectionPage
          certificateDocument={certificateDocument}
          onDirtyChange={setSectionDirty}
          onRefreshRow={loadRow}
          row={row}
          rowId={rowId}
          token={token}
        />
      ) : null}

      {exitDialogOpen ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/45 px-4">
          <div className="w-full max-w-lg rounded-2xl border border-slate-200 bg-white p-5 shadow-2xl">
            <p className="text-lg font-semibold text-slate-900">Hai modifiche non confermate</p>
            <p className="mt-2 text-sm leading-6 text-slate-600">
              Se esci adesso perderai i dati non confermati della sessione {title}. Vuoi davvero tornare alla lista?
            </p>
            <div className="mt-5 flex flex-wrap justify-end gap-2">
              <button
                className="rounded-xl border border-border px-4 py-2.5 text-sm font-semibold text-slate-700 hover:bg-slate-50"
                onClick={() => {
                  setExitDialogOpen(false);
                  setPendingPath("");
                }}
                type="button"
              >
                Continua a modificare
              </button>
              <button
                className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-2.5 text-sm font-semibold text-rose-700 hover:bg-rose-100"
                onClick={handleLeaveWithoutConfirm}
                type="button"
              >
                Esci senza confermare
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </section>
  );
}
