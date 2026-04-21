import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { apiRequest } from "../../app/api";
import { useAuth } from "../../app/auth";
import AcquisitionChemistrySectionPage from "./AcquisitionChemistrySectionPage";
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
  const { rowId, sectionKey } = useParams();
  const title = SECTION_TITLES[sectionKey] || "Sezione";
  const [row, setRow] = useState(null);
  const [certificateDocument, setCertificateDocument] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

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

  return (
    <section className="space-y-4">
      <div>
        <button className="text-sm font-medium text-accent hover:underline" onClick={() => navigate("/acquisition")} type="button">
          Torna alla lista
        </button>
        <p className="mt-3 text-sm uppercase tracking-[0.3em] text-slate-500">Incoming Quality</p>
        <h1 className="mt-1 text-3xl font-semibold text-slate-900">{title}</h1>
      </div>

      {loading ? <p className="text-sm text-slate-500">Caricamento riga...</p> : null}
      {error ? <p className="text-sm text-rose-600">{error}</p> : null}
      {row ? <AcquisitionRowSummaryCard row={row} rowId={rowId} /> : null}
      {row && sectionKey === "chemistry" ? (
        <AcquisitionChemistrySectionPage certificateDocument={certificateDocument} onRefreshRow={loadRow} row={row} rowId={rowId} token={token} />
      ) : null}
    </section>
  );
}
