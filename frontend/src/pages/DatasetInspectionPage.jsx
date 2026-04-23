import { useEffect, useMemo, useState } from "react";

const pageSizeOptions = [24, 48, 72];

export default function DatasetInspectionPage({ apiBase, selectedProject, datasetVersion, onBack }) {
  const [filtersMeta, setFiltersMeta] = useState(null);
  const [itemsPayload, setItemsPayload] = useState(null);
  const [filters, setFilters] = useState({ filename: "", resolution: "", area_bucket: "", label_state: "" });
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(24);
  const [viewMode, setViewMode] = useState("grid");
  const [preview, setPreview] = useState(null);
  const [previewIndex, setPreviewIndex] = useState(-1);
  const [showBoxes, setShowBoxes] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    async function loadFilters() {
      if (!datasetVersion) return;
      setError("");
      try {
        const response = await fetch(`${apiBase}/datasets/inspection/${datasetVersion.id}/filters`);
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || "Unable to load inspection filters.");
        if (!cancelled) setFiltersMeta(data);
      } catch (loadError) {
        if (!cancelled) setError(loadError.message || "Unable to load inspection filters.");
      }
    }
    loadFilters();
    return () => {
      cancelled = true;
    };
  }, [apiBase, datasetVersion?.id]);

  useEffect(() => {
    let cancelled = false;
    async function loadItems() {
      if (!datasetVersion) return;
      setError("");
      const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
      Object.entries(filters).forEach(([key, value]) => {
        if (value) params.set(key, value);
      });
      try {
        const response = await fetch(`${apiBase}/datasets/inspection/${datasetVersion.id}/items?${params.toString()}`);
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || "Unable to load dataset images.");
        if (!cancelled) setItemsPayload(data);
      } catch (loadError) {
        if (!cancelled) setError(loadError.message || "Unable to load dataset images.");
      }
    }
    loadItems();
    return () => {
      cancelled = true;
    };
  }, [apiBase, datasetVersion?.id, filters, page, pageSize]);

  useEffect(() => {
    setPreview(null);
    setPreviewIndex(-1);
  }, [filters, page, pageSize, datasetVersion?.id]);

  const summary = itemsPayload?.summary ?? {};
  const items = Array.isArray(itemsPayload?.items) ? itemsPayload.items : [];
  const totalPages = Number(summary.total_pages || 1);

  function updateFilter(key, value) {
    setFilters((current) => ({ ...current, [key]: value }));
    setPage(1);
  }

  async function openPreview(item, index, resetOverlay = true) {
    try {
      const response = await fetch(`${apiBase}/datasets/inspection/${datasetVersion.id}/items/${item.id}`);
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Unable to load preview.");
      setPreview(data);
      setPreviewIndex(index);
      if (resetOverlay) setShowBoxes(true);
    } catch (previewError) {
      setError(previewError.message || "Unable to load preview.");
    }
  }

  function closePreview() {
    setPreview(null);
    setPreviewIndex(-1);
  }

  function navigatePreview(direction) {
    const nextIndex = previewIndex + direction;
    // The preview stays bound to the current paginated result order; edge
    // buttons are disabled before this guard, but the guard avoids index errors.
    if (nextIndex < 0 || nextIndex >= items.length) return;
    openPreview(items[nextIndex], nextIndex, false);
  }

  useEffect(() => {
    if (!preview) return undefined;
    function handleKeyDown(event) {
      const target = event.target;
      const tagName = target?.tagName;
      if (target?.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(tagName)) return;
      if (event.key === "Escape") closePreview();
      if (event.key === "ArrowLeft") navigatePreview(-1);
      if (event.key === "ArrowRight") navigatePreview(1);
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [preview, previewIndex, items]);

  const scopeText = useMemo(() => {
    if (!datasetVersion) return "No dataset version selected.";
    return `Inspecting cumulative dataset up to ${datasetVersion.version}.`;
  }, [datasetVersion]);

  if (!datasetVersion) {
    return <EmptyPanel>No dataset version selected for inspection.</EmptyPanel>;
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <button type="button" onClick={onBack} className="rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700">
          Back to Datasets
        </button>
      </div>

      <section className="rounded-3xl bg-white p-6 shadow-sm">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h2 className="text-2xl font-semibold">Dataset Inspection</h2>
            <p className="mt-2 text-slate-600">{scopeText}</p>
          </div>
          <div className="grid gap-2 text-sm text-slate-600 sm:grid-cols-3">
            <MiniStat label="Project" value={selectedProject?.name || "N/A"} />
            <MiniStat label="Version" value={datasetVersion.version} />
            <MiniStat label="Cumulative Images" value={summary.total_images ?? filtersMeta?.total_images ?? 0} />
          </div>
        </div>
      </section>

      <section className="rounded-2xl bg-white p-5 shadow-sm">
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
          <TextField
            label="File Name Search"
            value={filters.filename}
            placeholder="cam12_ or 00123"
            onChange={(value) => updateFilter("filename", value)}
          />
          <SelectField label="Resolution" value={filters.resolution} onChange={(value) => updateFilter("resolution", value)}>
            <option value="">All resolutions</option>
            {(filtersMeta?.resolutions ?? []).map((resolution) => (
              <option key={resolution} value={resolution}>{resolution}</option>
            ))}
          </SelectField>
          <SelectField label="Box Area Bucket" value={filters.area_bucket} onChange={(value) => updateFilter("area_bucket", value)}>
            <option value="">All box sizes</option>
            {(filtersMeta?.area_buckets ?? []).map((bucket) => (
              <option key={bucket.value} value={bucket.value}>{bucket.label} ({bucket.range})</option>
            ))}
          </SelectField>
          <SelectField label="Label State" value={filters.label_state} onChange={(value) => updateFilter("label_state", value)}>
            <option value="">All label states</option>
            {(filtersMeta?.label_states ?? []).map((state) => (
              <option key={state.value} value={state.value}>{state.label}</option>
            ))}
          </SelectField>
          <SelectField label="Page Size" value={pageSize} onChange={(value) => { setPageSize(Number(value)); setPage(1); }}>
            {pageSizeOptions.map((size) => (
              <option key={size} value={size}>{size} images</option>
            ))}
          </SelectField>
        </div>
        <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
          <div className="text-sm text-slate-500">
            {summary.filtered_images ?? 0} images match. Empty-label/background images are valid and included.
          </div>
          <div className="flex rounded-xl border border-slate-200 bg-slate-50 p-1">
            {["grid", "list"].map((mode) => (
              <button
                key={mode}
                type="button"
                onClick={() => setViewMode(mode)}
                className={`rounded-lg px-3 py-1.5 text-sm font-medium capitalize ${viewMode === mode ? "bg-white text-blue-700 shadow-sm" : "text-slate-600"}`}
              >
                {mode}
              </button>
            ))}
          </div>
        </div>
      </section>

      {error && <EmptyPanel>{error}</EmptyPanel>}

      <section className="rounded-2xl bg-white p-5 shadow-sm">
        {items.length ? (
          viewMode === "grid" ? (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4">
              {items.map((item, index) => <DatasetTile key={item.id} item={item} apiBase={apiBase} onClick={() => openPreview(item, index)} />)}
            </div>
          ) : (
            <div className="space-y-3">
              {items.map((item, index) => <DatasetListRow key={item.id} item={item} apiBase={apiBase} onClick={() => openPreview(item, index)} />)}
            </div>
          )
        ) : (
          <EmptyPanel>No images match the current filters.</EmptyPanel>
        )}
        <Pagination page={page} totalPages={totalPages} onPageChange={setPage} />
      </section>

      {preview && (
        <PreviewModal
          preview={preview}
          apiBase={apiBase}
          showBoxes={showBoxes}
          setShowBoxes={setShowBoxes}
          onClose={closePreview}
          onPrevious={() => navigatePreview(-1)}
          onNext={() => navigatePreview(1)}
          canPrevious={previewIndex > 0}
          canNext={previewIndex >= 0 && previewIndex < items.length - 1}
          positionText={previewIndex >= 0 ? `${previewIndex + 1} of ${items.length}` : ""}
        />
      )}
    </div>
  );
}

function DatasetTile({ item, apiBase, onClick }) {
  return (
    <button type="button" onClick={onClick} className="overflow-hidden rounded-xl border border-slate-200 bg-slate-50 text-left hover:border-blue-300">
      <div className="aspect-video bg-slate-200">
        <img src={assetUrl(apiBase, item.thumbnail_url)} alt={item.source_image_name} className="h-full w-full object-cover" />
      </div>
      <ItemMeta item={item} />
    </button>
  );
}

function DatasetListRow({ item, apiBase, onClick }) {
  return (
    <button type="button" onClick={onClick} className="flex w-full gap-4 rounded-xl border border-slate-200 bg-slate-50 p-3 text-left hover:border-blue-300">
      <img src={assetUrl(apiBase, item.thumbnail_url)} alt={item.source_image_name} className="h-20 w-28 rounded-lg object-cover" />
      <ItemMeta item={item} compact />
    </button>
  );
}

function ItemMeta({ item, compact = false }) {
  return (
    <div className={compact ? "flex-1" : "p-3"}>
      <div className="truncate text-sm font-semibold text-slate-900">{item.source_image_name || item.image_filename}</div>
      <div className="mt-1 flex flex-wrap gap-2 text-xs text-slate-500">
        <span>{item.resolution}</span>
        <span>{item.object_count} objects</span>
        <span>{labelStateText(item)}</span>
      </div>
    </div>
  );
}

function PreviewModal({
  preview,
  apiBase,
  showBoxes,
  setShowBoxes,
  onClose,
  onPrevious,
  onNext,
  canPrevious,
  canNext,
  positionText,
}) {
  const boxes = Array.isArray(preview.boxes) ? preview.boxes : [];
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/75 p-3" onMouseDown={onClose}>
      <div
        className="flex h-[94vh] w-[96vw] max-w-[1600px] flex-col overflow-hidden rounded-2xl bg-white p-4 shadow-xl"
        onMouseDown={(event) => event.stopPropagation()}
      >
        {/* Clicking the dimmed empty space closes the modal, while this content
            handler keeps image review and overlay controls from dismissing it. */}
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 className="text-lg font-semibold text-slate-900">{preview.source_image_name || preview.image_filename}</h3>
            <p className="mt-1 text-sm text-slate-500">
              {preview.resolution} - {preview.is_empty_label ? "Background / empty-label image" : `${preview.object_count} labeled objects`}
              {positionText ? ` - ${positionText}` : ""}
            </p>
          </div>
          <div className="flex flex-wrap gap-3">
            <label className="flex items-center gap-2 rounded-xl border border-slate-200 px-3 py-2 text-sm text-slate-700">
              <input type="checkbox" checked={showBoxes} onChange={(event) => setShowBoxes(event.target.checked)} />
              Show boxes
            </label>
            <button type="button" onClick={onClose} className="rounded-xl bg-slate-900 px-4 py-2 text-sm font-medium text-white">Close</button>
          </div>
        </div>
        <div className="mt-4 flex min-h-0 flex-1 items-center justify-center overflow-hidden rounded-xl bg-slate-100">
          <div className="relative inline-flex max-h-full max-w-full">
            <img src={assetUrl(apiBase, preview.image_url)} alt={preview.source_image_name} className="max-h-full max-w-full object-contain" />
            {showBoxes && boxes.map((box) => <BoxOverlay key={`${box.line}-${box.class_id}`} box={box} />)}
          </div>
        </div>
        <div className="mt-3 flex items-center justify-center gap-3">
          <button
            type="button"
            onClick={onPrevious}
            disabled={!canPrevious}
            className="rounded-xl border border-slate-200 px-4 py-2 text-sm font-medium text-slate-700 disabled:opacity-40"
          >
            {"<"} Previous
          </button>
          <span className="min-w-20 text-center text-sm text-slate-500">{positionText}</span>
          <button
            type="button"
            onClick={onNext}
            disabled={!canNext}
            className="rounded-xl border border-slate-200 px-4 py-2 text-sm font-medium text-slate-700 disabled:opacity-40"
          >
            Next {">"}
          </button>
        </div>
        {!boxes.length && (
          <div className="mt-3 rounded-xl border border-slate-200 bg-slate-50 p-3 text-sm text-slate-600">
            No boxes to draw. This empty-label image is preserved as background training context.
          </div>
        )}
      </div>
    </div>
  );
}

function BoxOverlay({ box }) {
  const left = (box.x_center - box.width / 2) * 100;
  const top = (box.y_center - box.height / 2) * 100;
  return (
    <div
      className="absolute border-2 border-emerald-400"
      style={{ left: `${left}%`, top: `${top}%`, width: `${box.width * 100}%`, height: `${box.height * 100}%` }}
    >
      <span className="absolute left-0 top-0 -translate-y-full bg-emerald-500 px-1.5 py-0.5 text-xs font-medium text-white">
        {box.class_label}
      </span>
    </div>
  );
}

function Pagination({ page, totalPages, onPageChange }) {
  return (
    <div className="mt-5 flex items-center justify-between gap-3 text-sm text-slate-600">
      <button type="button" onClick={() => onPageChange(Math.max(1, page - 1))} disabled={page <= 1} className="rounded-xl border border-slate-200 px-4 py-2 disabled:opacity-40">
        Previous
      </button>
      <span>Page {page} of {totalPages}</span>
      <button type="button" onClick={() => onPageChange(Math.min(totalPages, page + 1))} disabled={page >= totalPages} className="rounded-xl border border-slate-200 px-4 py-2 disabled:opacity-40">
        Next
      </button>
    </div>
  );
}

function SelectField({ label, value, onChange, children }) {
  return (
    <label className="block text-sm font-medium text-slate-700">
      <span className="mb-2 block">{label}</span>
      <select className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2" value={value} onChange={(event) => onChange(event.target.value)}>
        {children}
      </select>
    </label>
  );
}

function TextField({ label, value, placeholder, onChange }) {
  return (
    <label className="block text-sm font-medium text-slate-700">
      <span className="mb-2 block">{label}</span>
      <input
        type="search"
        className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2"
        value={value}
        placeholder={placeholder}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  );
}

function MiniStat({ label, value }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2">
      <div className="text-xs text-slate-500">{label}</div>
      <div className="mt-1 text-sm font-semibold text-slate-900">{value}</div>
    </div>
  );
}

function EmptyPanel({ children }) {
  return <div className="rounded-2xl border border-slate-200 bg-white p-5 text-sm text-slate-500 shadow-sm">{children}</div>;
}

function labelStateText(item) {
  if (item.is_empty_label) return "empty label";
  if (item.object_count === 1) return "single object";
  return "multiple objects";
}

function assetUrl(apiBase, path) {
  if (!path) return "";
  if (path.startsWith("http")) return path;
  const origin = apiBase.replace(/\/api$/, "");
  return `${origin}${path}`;
}
