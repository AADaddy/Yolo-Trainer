export default function DatasetVersions({ datasets, selectedDatasetId, onSelect, onDelete, onViewDataset }) {
  if (!datasets.length) {
    return <div className="rounded-2xl bg-slate-50 p-6 text-slate-500">No dataset versions added yet.</div>;
  }

  return (
    <div className="space-y-3">
      {datasets.map((dataset) => {
        const isSelected = dataset.id === selectedDatasetId;
        return (
          <div
            key={dataset.id}
            className={`rounded-2xl border p-5 transition ${
              isSelected ? "border-blue-300 bg-blue-50/70" : "border-slate-200 bg-slate-50"
            }`}
          >
            <div className="flex flex-wrap items-center gap-4">
              <button type="button" onClick={() => onSelect(dataset.id)} className="flex-1 text-left">
                <div className="flex flex-wrap items-center gap-3">
                  <h3 className="text-lg font-semibold text-slate-900">{dataset.version}</h3>
                  <StatusBadge status={dataset.status} />
                </div>
                <p className="mt-1 text-sm text-slate-500">{dataset.note || "No notes for this version."}</p>
              </button>

              <div className="min-w-40 text-sm text-slate-600">
                <div className="text-xs uppercase tracking-wide text-slate-400">Total Images</div>
                <div className="mt-1 text-lg font-semibold text-slate-900">{dataset.cumulative_image_count}</div>
              </div>

              <div className="min-w-44 text-sm text-slate-600">
                <div className="text-xs uppercase tracking-wide text-slate-400">Added</div>
                <div className="mt-1">{formatDate(dataset.created_at)}</div>
              </div>

              <button
                type="button"
                onClick={() => onViewDataset(dataset)}
                className="rounded-xl border border-blue-200 bg-white px-4 py-2 text-sm font-medium text-blue-700 hover:bg-blue-50"
              >
                View Dataset
              </button>

              <button
                type="button"
                onClick={() => onDelete(dataset)}
                className="rounded-xl border border-rose-200 bg-white px-4 py-2 text-sm font-medium text-rose-700 hover:bg-rose-50"
              >
                Delete Version
              </button>
            </div>
          </div>
        );
      })}
    </div>
  );
}

function StatusBadge({ status }) {
  const normalized = status || "completed";
  const styles = {
    completed: "bg-emerald-100 text-emerald-700",
    running: "bg-blue-100 text-blue-700",
    queued: "bg-amber-100 text-amber-700",
    failed: "bg-rose-100 text-rose-700"
  };
  return (
    <span className={`rounded-full px-2 py-1 text-[11px] font-medium uppercase tracking-wide ${styles[normalized] || "bg-slate-200 text-slate-700"}`}>
      {normalized}
    </span>
  );
}

function formatDate(value) {
  try {
    return new Intl.DateTimeFormat(undefined, {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit"
    }).format(new Date(value));
  } catch {
    return value;
  }
}
