import { useEffect, useMemo, useState } from "react";

import { apiRequest } from "../../app/api";
import { useAuth } from "../../app/auth";

const EMPTY_STANDARD = {
  id: null,
  code: "",
  lega_base: "",
  lega_designazione: "",
  variante_lega: "",
  norma: "",
  trattamento_termico: "",
  tipo_prodotto: "",
  misura_tipo: "diametro",
  fonte_excel_foglio: "",
  fonte_excel_blocco: "",
  stato_validazione: "bozza",
  note: "",
  chemistry: [],
  properties: [],
};

const CHEMISTRY_ELEMENTS = [
  "Si",
  "Fe",
  "Cu",
  "Mn",
  "Mg",
  "Cr",
  "Ni",
  "Zn",
  "Ti",
  "Cd",
  "Hg",
  "Pb",
  "V",
  "Bi",
  "Sn",
  "Zr",
  "Be",
  "Zr+Ti",
  "Mn+Cr",
  "Bi+Pb",
];
const PROPERTY_FIELDS = ["Rp0.2", "Rm", "A%", "HB", "IACS%"];

function textValue(value) {
  return value === null || value === undefined ? "" : String(value);
}

function numberText(value) {
  return value === null || value === undefined ? "" : String(value).replace(".", ",");
}

function parseOptionalNumber(value) {
  const cleaned = String(value ?? "").trim().replace(",", ".");
  if (!cleaned) {
    return null;
  }
  const parsed = Number(cleaned);
  return Number.isFinite(parsed) ? parsed : null;
}

function cloneEmptyStandard() {
  return {
    ...EMPTY_STANDARD,
    chemistry: [],
    properties: [],
  };
}

function normalizeDecimalText(value) {
  return String(value ?? "").trim().replace(".", ",");
}

function buildRangeLabel(minValue, maxValue) {
  const minText = normalizeDecimalText(minValue);
  const maxText = normalizeDecimalText(maxValue);
  if (minText && maxText) {
    return `${minText} - ${maxText}`;
  }
  if (maxText) {
    return `<= ${maxText}`;
  }
  if (minText) {
    return `> ${minText}`;
  }
  return null;
}

function isOptionalNumberText(value) {
  const cleaned = String(value ?? "").trim();
  return !cleaned || /^-?\d+(?:[,.]\d+)?$/.test(cleaned);
}

function isChanged(currentValue, savedValue) {
  return textValue(currentValue) !== textValue(savedValue);
}

function inputStateClass({ changed = false, invalid = false } = {}) {
  if (invalid) {
    return "border-rose-300 bg-rose-50 text-rose-900";
  }
  if (changed) {
    return "border-amber-300 bg-amber-50 text-ink";
  }
  return "border-slate-200 bg-slate-50 text-ink";
}

function validateDraft(draft) {
  const errors = [];
  const seenElements = new Map();

  draft.chemistry.forEach((entry, index) => {
    const element = entry.elemento.trim();
    if (!element) {
      errors.push(`Chimica riga ${index + 1}: seleziona un elemento.`);
      return;
    }
    seenElements.set(element, [...(seenElements.get(element) || []), index + 1]);

    if (!isOptionalNumberText(entry.min_value) || !isOptionalNumberText(entry.max_value)) {
      errors.push(`Chimica ${element}: usa numeri con virgola, esempio 0,25.`);
      return;
    }

    const minValue = parseOptionalNumber(entry.min_value);
    const maxValue = parseOptionalNumber(entry.max_value);
    if (minValue !== null && maxValue !== null && minValue > maxValue) {
      errors.push(`Chimica ${element}: il minimo non può essere maggiore del massimo.`);
    }
  });

  seenElements.forEach((rows, element) => {
    if (rows.length > 1) {
      errors.push(`Chimica ${element}: elemento duplicato nelle righe ${rows.join(", ")}.`);
    }
  });

  const seenProperties = new Map();
  draft.properties.forEach((entry, index) => {
    const field = entry.proprieta.trim();
    if (!field) {
      errors.push(`Proprieta riga ${index + 1}: seleziona un campo.`);
      return;
    }

    const numericFields = [
      ["Da", entry.misura_min],
      ["A", entry.misura_max],
      ["Min", entry.min_value],
      ["Max", entry.max_value],
    ];
    const invalidNumber = numericFields.find(([, value]) => !isOptionalNumberText(value));
    if (invalidNumber) {
      errors.push(`Proprieta ${field}: il campo ${invalidNumber[0]} deve essere un numero con virgola, esempio 260,5.`);
      return;
    }

    const measureMin = parseOptionalNumber(entry.misura_min);
    const measureMax = parseOptionalNumber(entry.misura_max);
    if (measureMin !== null && measureMax !== null && measureMin > measureMax) {
      errors.push(`Proprieta ${field}: il campo Da non puo essere maggiore del campo A.`);
    }

    const minValue = parseOptionalNumber(entry.min_value);
    const maxValue = parseOptionalNumber(entry.max_value);
    if (minValue !== null && maxValue !== null && minValue > maxValue) {
      errors.push(`Proprieta ${field}: il minimo non puo essere maggiore del massimo.`);
    }

    const duplicateKey = [field, normalizeDecimalText(entry.misura_min), normalizeDecimalText(entry.misura_max)].join("|");
    seenProperties.set(duplicateKey, [...(seenProperties.get(duplicateKey) || []), index + 1]);
  });

  seenProperties.forEach((rows, key) => {
    const [field] = key.split("|");
    if (rows.length > 1) {
      errors.push(`Proprieta ${field}: riga duplicata nelle righe ${rows.join(", ")}.`);
    }
  });

  return errors;
}

function hydrateDraft(item) {
  return {
    ...EMPTY_STANDARD,
    ...item,
    variante_lega: textValue(item.variante_lega),
    norma: textValue(item.norma),
    trattamento_termico: textValue(item.trattamento_termico),
    tipo_prodotto: textValue(item.tipo_prodotto),
    misura_tipo: textValue(item.misura_tipo),
    fonte_excel_foglio: textValue(item.fonte_excel_foglio),
    fonte_excel_blocco: textValue(item.fonte_excel_blocco),
    note: textValue(item.note),
    chemistry: (item.chemistry || []).map((entry) => ({
      elemento: entry.elemento,
      min_value: numberText(entry.min_value),
      max_value: numberText(entry.max_value),
    })),
    properties: (item.properties || []).map((entry) => ({
      proprieta: entry.proprieta,
      misura_min: numberText(entry.misura_min),
      misura_max: numberText(entry.misura_max),
      range_label: textValue(entry.range_label),
      min_value: numberText(entry.min_value),
      max_value: numberText(entry.max_value),
    })),
  };
}

function serializeDraft(draft) {
  const legaBase = draft.lega_base.trim();
  const variante = draft.variante_lega.trim();
  const legaDesignazione = variante ? `${legaBase} ${variante}` : legaBase;
  const generatedCode = slugify(
    [legaDesignazione, draft.norma, draft.trattamento_termico, draft.tipo_prodotto, draft.misura_tipo]
      .filter((value) => String(value || "").trim())
      .join(" "),
  );
  return {
    code: draft.code.trim() || generatedCode,
    lega_base: legaBase,
    lega_designazione: legaDesignazione,
    variante_lega: draft.variante_lega.trim() || null,
    norma: draft.norma.trim() || null,
    trattamento_termico: draft.trattamento_termico.trim() || null,
    tipo_prodotto: draft.tipo_prodotto.trim() || null,
    misura_tipo: draft.misura_tipo.trim() || null,
    fonte_excel_foglio: draft.fonte_excel_foglio.trim() || null,
    fonte_excel_blocco: draft.fonte_excel_blocco.trim() || null,
    stato_validazione: draft.stato_validazione,
    note: draft.note.trim() || null,
    chemistry: draft.chemistry
      .filter((entry) => entry.elemento.trim())
      .map((entry) => ({
        elemento: entry.elemento.trim(),
        min_value: parseOptionalNumber(entry.min_value),
        max_value: parseOptionalNumber(entry.max_value),
      })),
    properties: draft.properties
      .filter((entry) => entry.proprieta.trim())
      .map((entry) => ({
        proprieta: entry.proprieta.trim(),
        misura_min: parseOptionalNumber(entry.misura_min),
        misura_max: parseOptionalNumber(entry.misura_max),
        range_label: buildRangeLabel(entry.misura_min, entry.misura_max),
        min_value: parseOptionalNumber(entry.min_value),
        max_value: parseOptionalNumber(entry.max_value),
      })),
  };
}

function slugify(value) {
  return (
    String(value || "")
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "_")
      .replace(/^_+|_+$/g, "") || "standard"
  );
}

function buildDuplicate(item) {
  const suffix = new Date().toISOString().slice(0, 19).replace(/[-:T]/g, "");
  return {
    ...hydrateDraft(item),
    id: null,
    code: `${item.code}_copy_${suffix}`,
    stato_validazione: "bozza",
    note: "Duplicato da standard esistente: verificare prima dell'uso operativo.",
  };
}

export default function StandardsPage() {
  const { token } = useAuth();
  const [items, setItems] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [draft, setDraft] = useState(cloneEmptyStandard);
  const [savedDraft, setSavedDraft] = useState(cloneEmptyStandard);
  const [filter, setFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [statusMessage, setStatusMessage] = useState("");

  useEffect(() => {
    refresh();
  }, []);

  async function refresh(nextSelectedId = selectedId) {
    setLoading(true);
    setError("");
    try {
      const data = await apiRequest("/standards", {}, token);
      setItems(data.items || []);
      const resolvedId = nextSelectedId || data.items?.[0]?.id || null;
      setSelectedId(resolvedId);
      const selected = data.items?.find((item) => item.id === resolvedId);
      if (selected) {
        const hydrated = hydrateDraft(selected);
        setDraft(hydrated);
        setSavedDraft(hydrated);
      }
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setLoading(false);
    }
  }

  const visibleItems = useMemo(() => {
    const needle = filter.trim().toLowerCase();
    if (!needle) {
      return items;
    }
    return items.filter((item) =>
      [item.lega_base, item.lega_designazione, item.norma, item.trattamento_termico, item.tipo_prodotto, item.stato_validazione]
        .filter(Boolean)
        .join(" ")
        .toLowerCase()
        .includes(needle),
    );
  }, [filter, items]);

  const duplicatePropertyRows = useMemo(() => {
    const rowsByKey = new Map();
    draft.properties.forEach((entry, index) => {
      const field = entry.proprieta.trim();
      if (!field) {
        return;
      }
      const duplicateKey = [field, normalizeDecimalText(entry.misura_min), normalizeDecimalText(entry.misura_max)].join("|");
      rowsByKey.set(duplicateKey, [...(rowsByKey.get(duplicateKey) || []), index]);
    });

    const duplicates = new Set();
    rowsByKey.forEach((rows) => {
      if (rows.length > 1) {
        rows.forEach((index) => duplicates.add(index));
      }
    });
    return duplicates;
  }, [draft.properties]);

  function selectItem(item) {
    setSelectedId(item.id);
    const hydrated = hydrateDraft(item);
    setDraft(hydrated);
    setSavedDraft(hydrated);
    setError("");
    setStatusMessage("");
  }

  function updateDraft(field, value) {
    setDraft((current) => ({ ...current, [field]: value }));
  }

  function updateChemistry(index, field, value) {
    setDraft((current) => ({
      ...current,
      chemistry: current.chemistry.map((entry, entryIndex) => (entryIndex === index ? { ...entry, [field]: value } : entry)),
    }));
  }

  function normalizeChemistryNumber(index, field) {
    setDraft((current) => ({
      ...current,
      chemistry: current.chemistry.map((entry, entryIndex) =>
        entryIndex === index ? { ...entry, [field]: normalizeDecimalText(entry[field]) } : entry,
      ),
    }));
  }

  function normalizePropertyNumber(index, field) {
    setDraft((current) => ({
      ...current,
      properties: current.properties.map((entry, entryIndex) =>
        entryIndex === index ? { ...entry, [field]: normalizeDecimalText(entry[field]) } : entry,
      ),
    }));
  }

  function updateProperty(index, field, value) {
    setDraft((current) => ({
      ...current,
      properties: current.properties.map((entry, entryIndex) => (entryIndex === index ? { ...entry, [field]: value } : entry)),
    }));
  }

  function addChemistryRow() {
    const used = new Set(draft.chemistry.map((entry) => entry.elemento));
    const firstFree = CHEMISTRY_ELEMENTS.find((element) => !used.has(element)) || "";
    if (!firstFree) {
      setStatusMessage("Tutti gli elementi chimici disponibili sono gia presenti nello standard.");
      return;
    }
    setDraft((current) => ({
      ...current,
      chemistry: [...current.chemistry, { elemento: firstFree, min_value: "", max_value: "" }],
    }));
  }

function addPropertyRow() {
    setDraft((current) => ({
      ...current,
      properties: [
        ...current.properties,
        {
          proprieta: PROPERTY_FIELDS[0],
          misura_min: "",
          misura_max: "",
          range_label: "",
          min_value: "",
          max_value: "",
        },
      ],
    }));
  }

  function removeChemistryRow(index) {
    setDraft((current) => ({ ...current, chemistry: current.chemistry.filter((_, entryIndex) => entryIndex !== index) }));
  }

  function removePropertyRow(index) {
    setDraft((current) => ({ ...current, properties: current.properties.filter((_, entryIndex) => entryIndex !== index) }));
  }

  async function handleSave(event) {
    event.preventDefault();
    const validationErrors = validateDraft(draft);
    if (validationErrors.length) {
      setError(validationErrors[0]);
      setStatusMessage("");
      return;
    }
    setSaving(true);
    setError("");
    setStatusMessage("");
    try {
      const payload = serializeDraft(draft);
      const saved = await apiRequest(
        draft.id ? `/standards/${draft.id}` : "/standards",
        {
          method: draft.id ? "PUT" : "POST",
          body: JSON.stringify(payload),
        },
        token,
      );
      setStatusMessage(draft.id ? "Standard aggiornato" : "Standard creato");
      await refresh(saved.id);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="rounded-3xl border border-border bg-panel p-6 shadow-lg shadow-slate-200/40 xl:p-8">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
        <div>
          <p className="text-sm uppercase tracking-[0.3em] text-slate-500">Standards</p>
          <h2 className="mt-2 text-2xl font-semibold">Standard chimici e meccanici</h2>
          <p className="mt-2 max-w-3xl text-sm text-slate-500">
            Condizioni di validità, limiti chimici e proprietà.
          </p>
        </div>
        <div className="flex flex-wrap gap-3">
          <button
            className="rounded-xl border border-border bg-white px-4 py-3 text-sm font-semibold text-slate-700 hover:bg-slate-50"
            onClick={() => {
              setSelectedId(null);
              const emptyDraft = cloneEmptyStandard();
              setDraft(emptyDraft);
              setSavedDraft(emptyDraft);
              setStatusMessage("");
              setError("");
            }}
            type="button"
          >
            Nuovo standard
          </button>
          <button
            className="rounded-xl bg-accent px-4 py-3 text-sm font-semibold text-white hover:bg-teal-700 disabled:opacity-60"
            disabled={!selectedId}
            onClick={() => {
              const selected = items.find((item) => item.id === selectedId);
              if (selected) {
                setSelectedId(null);
                const duplicateDraft = buildDuplicate(selected);
                setDraft(duplicateDraft);
                setSavedDraft(cloneEmptyStandard());
              }
            }}
            type="button"
          >
            Duplica selezionato
          </button>
        </div>
      </div>

      {loading ? <p className="mt-6 text-sm text-slate-500">Caricamento standards...</p> : null}
      {error ? <p className="mt-6 text-sm text-rose-600">{error}</p> : null}
      {statusMessage ? <p className="mt-6 text-sm text-slate-600">{statusMessage}</p> : null}

      <div className="mt-8 grid gap-6 xl:grid-cols-[360px,minmax(0,1fr)]">
        <aside className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
          <label className="block text-xs font-semibold uppercase tracking-[0.22em] text-slate-500">Filtro</label>
          <input
            className="mt-2 w-full rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-ink"
            onChange={(event) => setFilter(event.target.value)}
            placeholder="Lega, norma, stato..."
            value={filter}
          />
          <div className="mt-4 max-h-[720px] space-y-2 overflow-auto pr-1">
            {visibleItems.map((item) => (
              <button
                className={`w-full rounded-xl border px-4 py-3 text-left text-sm transition ${
                  item.id === selectedId ? "border-accent bg-accent/10" : "border-slate-200 bg-white hover:bg-slate-50"
                }`}
                key={item.id}
                onClick={() => selectItem(item)}
                type="button"
              >
                <span className="block font-semibold text-ink">
                  {item.lega_designazione}
                  {item.tipo_prodotto ? ` - ${item.tipo_prodotto}` : ""}
                </span>
                <span className="mt-1 block text-xs text-slate-500">
                  {[item.norma, item.trattamento_termico, item.misura_tipo].filter(Boolean).join(" / ") || "Solo chimica"}
                </span>
                <span
                  className={`mt-2 inline-flex rounded-full px-2.5 py-1 text-[11px] font-semibold ${
                    item.stato_validazione === "attivo" ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-700"
                  }`}
                >
                  {item.stato_validazione}
                </span>
              </button>
            ))}
            {!visibleItems.length && !loading ? <p className="text-sm text-slate-500">Nessuno standard trovato.</p> : null}
          </div>
        </aside>

        <form className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm" onSubmit={handleSave}>
          <div className="border-b border-slate-100 pb-4">
            <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-500">Dettaglio standard</p>
            <h3 className="mt-2 text-xl font-semibold">
              {draft.lega_designazione || "Nuovo standard"}
              {draft.norma ? ` - ${draft.norma}` : ""}
              {draft.trattamento_termico ? ` - ${draft.trattamento_termico}` : ""}
              {draft.tipo_prodotto ? ` - ${draft.tipo_prodotto}` : ""}
            </h3>
          </div>

          <div className="mt-5 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            <Input label="Lega base" value={draft.lega_base} onChange={(value) => updateDraft("lega_base", value)} required />
            <Input label="Variante lega" value={draft.variante_lega} onChange={(value) => updateDraft("variante_lega", value)} />
            <Input label="Norma" value={draft.norma} onChange={(value) => updateDraft("norma", value)} />
            <Input label="Stato / trattamento" value={draft.trattamento_termico} onChange={(value) => updateDraft("trattamento_termico", value)} />
            <Input label="Tipo prodotto" value={draft.tipo_prodotto} onChange={(value) => updateDraft("tipo_prodotto", value)} placeholder="BARRE, PROFILI..." />
            <Input label="Misura" value={draft.misura_tipo} onChange={(value) => updateDraft("misura_tipo", value)} placeholder="diametro, spessore" />
            <Select
              label="Stato standard"
              value={draft.stato_validazione}
              onChange={(value) => updateDraft("stato_validazione", value)}
              options={["attivo", "da_verificare", "bozza"]}
            />
          </div>

          <EditableSection title="Chimica" description="Limiti min/max per elemento, senza unità nel DB." onAdd={addChemistryRow}>
            <div className="overflow-auto rounded-xl border border-slate-200">
              <table className="min-w-full divide-y divide-slate-200 text-sm">
                <thead className="bg-slate-50">
                  <tr>
                    <th className="px-3 py-2 text-left">Elemento</th>
                    <th className="px-3 py-2 text-left">Min</th>
                    <th className="px-3 py-2 text-left">Max</th>
                    <th className="w-20 px-3 py-2" />
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {draft.chemistry.map((entry, index) => {
                    const original = savedDraft.chemistry[index] || {};
                    const duplicateElement =
                      entry.elemento &&
                      draft.chemistry.some((otherEntry, otherIndex) => otherIndex !== index && otherEntry.elemento === entry.elemento);
                    const minInvalid = !isOptionalNumberText(entry.min_value);
                    const maxInvalid = !isOptionalNumberText(entry.max_value);
                    const minValue = parseOptionalNumber(entry.min_value);
                    const maxValue = parseOptionalNumber(entry.max_value);
                    const rangeInvalid = minValue !== null && maxValue !== null && minValue > maxValue;
                    return (
                    <tr key={`${entry.elemento}-${index}`}>
                      <td className="px-3 py-2">
                        <select
                          className={`w-28 rounded-lg border px-3 py-2 ${inputStateClass({
                            changed: isChanged(entry.elemento, original.elemento),
                            invalid: duplicateElement,
                          })}`}
                          value={entry.elemento}
                          onChange={(event) => updateChemistry(index, "elemento", event.target.value)}
                        >
                          {CHEMISTRY_ELEMENTS.map((element) => {
                            const usedByOther = draft.chemistry.some(
                              (otherEntry, otherIndex) => otherIndex !== index && otherEntry.elemento === element,
                            );
                            return (
                              <option disabled={usedByOther} key={element} value={element}>
                                {element}
                              </option>
                            );
                          })}
                        </select>
                      </td>
                      <td className="px-3 py-2">
                        <input
                          className={`w-28 rounded-lg border px-3 py-2 ${inputStateClass({
                            changed: isChanged(entry.min_value, original.min_value),
                            invalid: minInvalid || rangeInvalid,
                          })}`}
                          onBlur={() => normalizeChemistryNumber(index, "min_value")}
                          onChange={(event) => updateChemistry(index, "min_value", event.target.value)}
                          value={entry.min_value}
                        />
                      </td>
                      <td className="px-3 py-2">
                        <input
                          className={`w-28 rounded-lg border px-3 py-2 ${inputStateClass({
                            changed: isChanged(entry.max_value, original.max_value),
                            invalid: maxInvalid || rangeInvalid,
                          })}`}
                          onBlur={() => normalizeChemistryNumber(index, "max_value")}
                          onChange={(event) => updateChemistry(index, "max_value", event.target.value)}
                          value={entry.max_value}
                        />
                      </td>
                      <td className="px-3 py-2 text-right">
                        <button className="text-xs font-semibold text-rose-600" onClick={() => removeChemistryRow(index)} type="button">
                          Rimuovi
                        </button>
                      </td>
                    </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </EditableSection>

          <EditableSection
            title="Proprietà per range"
            description="Ogni riga rappresenta un valore valido per il range di diametro/spessore indicato. Regola Excel: limite basso escluso, limite alto incluso."
            onAdd={addPropertyRow}
          >
            <div className="overflow-auto rounded-xl border border-slate-200">
              <table className="min-w-[980px] divide-y divide-slate-200 text-sm">
                <thead className="bg-slate-50">
                  <tr>
                    <th className="px-3 py-2 text-left">Da</th>
                    <th className="px-3 py-2 text-left">A</th>
                    <th className="px-3 py-2 text-left">Campo</th>
                    <th className="px-3 py-2 text-left">Min</th>
                    <th className="px-3 py-2 text-left">Max</th>
                    <th className="w-20 px-3 py-2" />
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {draft.properties.map((entry, index) => {
                    const original = savedDraft.properties[index] || {};
                    const measureMinInvalid = !isOptionalNumberText(entry.misura_min);
                    const measureMaxInvalid = !isOptionalNumberText(entry.misura_max);
                    const propertyMinInvalid = !isOptionalNumberText(entry.min_value);
                    const propertyMaxInvalid = !isOptionalNumberText(entry.max_value);
                    const measureMin = parseOptionalNumber(entry.misura_min);
                    const measureMax = parseOptionalNumber(entry.misura_max);
                    const propertyMin = parseOptionalNumber(entry.min_value);
                    const propertyMax = parseOptionalNumber(entry.max_value);
                    const measureRangeInvalid = measureMin !== null && measureMax !== null && measureMin > measureMax;
                    const propertyRangeInvalid = propertyMin !== null && propertyMax !== null && propertyMin > propertyMax;
                    const duplicateProperty = duplicatePropertyRows.has(index);
                    return (
                    <tr key={`property-${index}`}>
                      <td className="px-3 py-2">
                        <input
                          className={`w-24 rounded-lg border px-3 py-2 ${inputStateClass({
                            changed: isChanged(entry.misura_min, original.misura_min),
                            invalid: measureMinInvalid || measureRangeInvalid || duplicateProperty,
                          })}`}
                          onBlur={() => normalizePropertyNumber(index, "misura_min")}
                          onChange={(event) => updateProperty(index, "misura_min", event.target.value)}
                          value={entry.misura_min}
                        />
                      </td>
                      <td className="px-3 py-2">
                        <input
                          className={`w-24 rounded-lg border px-3 py-2 ${inputStateClass({
                            changed: isChanged(entry.misura_max, original.misura_max),
                            invalid: measureMaxInvalid || measureRangeInvalid || duplicateProperty,
                          })}`}
                          onBlur={() => normalizePropertyNumber(index, "misura_max")}
                          onChange={(event) => updateProperty(index, "misura_max", event.target.value)}
                          value={entry.misura_max}
                        />
                      </td>
                      <td className="px-3 py-2">
                        <select
                          className={`w-28 rounded-lg border px-3 py-2 ${inputStateClass({
                            changed: isChanged(entry.proprieta, original.proprieta),
                            invalid: duplicateProperty,
                          })}`}
                          value={entry.proprieta}
                          onChange={(event) => updateProperty(index, "proprieta", event.target.value)}
                        >
                          {PROPERTY_FIELDS.map((field) => (
                            <option key={field} value={field}>
                              {field}
                            </option>
                          ))}
                        </select>
                      </td>
                      <td className="px-3 py-2">
                        <input
                          className={`w-24 rounded-lg border px-3 py-2 ${inputStateClass({
                            changed: isChanged(entry.min_value, original.min_value),
                            invalid: propertyMinInvalid || propertyRangeInvalid,
                          })}`}
                          onBlur={() => normalizePropertyNumber(index, "min_value")}
                          onChange={(event) => updateProperty(index, "min_value", event.target.value)}
                          value={entry.min_value}
                        />
                      </td>
                      <td className="px-3 py-2">
                        <input
                          className={`w-24 rounded-lg border px-3 py-2 ${inputStateClass({
                            changed: isChanged(entry.max_value, original.max_value),
                            invalid: propertyMaxInvalid || propertyRangeInvalid,
                          })}`}
                          onBlur={() => normalizePropertyNumber(index, "max_value")}
                          onChange={(event) => updateProperty(index, "max_value", event.target.value)}
                          value={entry.max_value}
                        />
                      </td>
                      <td className="px-3 py-2 text-right">
                        <button className="text-xs font-semibold text-rose-600" onClick={() => removePropertyRow(index)} type="button">
                          Rimuovi
                        </button>
                      </td>
                    </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </EditableSection>

          <div className="mt-6 flex justify-end border-t border-slate-100 pt-5">
            <button className="rounded-xl bg-accent px-5 py-3 text-sm font-semibold text-white hover:bg-teal-700 disabled:opacity-60" disabled={saving} type="submit">
              {saving ? "Salvataggio..." : draft.id ? "Salva standard" : "Crea standard"}
            </button>
          </div>
        </form>
      </div>
    </section>
  );
}

function Input({ label, value, onChange, required = false, placeholder = "" }) {
  return (
    <label className="block text-sm font-medium text-slate-700">
      {label}
      <input
        className="mt-2 w-full rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-ink"
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        required={required}
        value={value}
      />
    </label>
  );
}

function Select({ label, value, onChange, options }) {
  return (
    <label className="block text-sm font-medium text-slate-700">
      {label}
      <select
        className="mt-2 w-full rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-ink"
        onChange={(event) => onChange(event.target.value)}
        value={value}
      >
        {options.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
    </label>
  );
}

function EditableSection({ title, description, onAdd, children }) {
  return (
    <div className="mt-8 rounded-2xl border border-slate-200 bg-slate-50/70 p-4">
      <div className="mb-4 flex flex-col gap-3 border-b border-slate-200 pb-4 md:flex-row md:items-center md:justify-between">
        <div>
          <h4 className="text-lg font-semibold">{title}</h4>
          <p className="mt-1 text-sm text-slate-500">{description}</p>
        </div>
        <button className="rounded-xl border border-accent bg-white px-4 py-2 text-sm font-semibold text-accent hover:bg-accent/10" onClick={onAdd} type="button">
          Aggiungi riga
        </button>
      </div>
      {children}
    </div>
  );
}
