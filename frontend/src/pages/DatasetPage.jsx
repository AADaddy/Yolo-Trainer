import { useEffect, useState } from "react";
import DatasetVersions from "../components/DatasetVersions";

const importModes = [
  { key: "combined", label: "Direct Import", description: "Select one folder that contains images/ and labels/" },
  { key: "labelstudio", label: "Label Studio", description: "Connect to self-hosted Label Studio (Coming Soon)" }
];

const visualDupThresholdOptions = [
  { value: -1, label: "Off", title: "Disabled", description: "Turns off perceptual visual-duplicate cleanup for this import. Exact file-hash duplicate skipping still stays active." },
  { value: 0, label: "0", title: "Identical perceptual only", description: "Most conservative. Only images with the same perceptual hash are treated as visual duplicates." },
  { value: 1, label: "1", title: "Very strict", description: "Allows tiny perceptual differences. Good if you only want to catch almost-identical frames." },
  { value: 2, label: "2", title: "Strict", description: "Catches very close near-duplicates while usually keeping small pose or object shifts." },
  { value: 3, label: "3", title: "Balanced", description: "Moderate sensitivity. Useful for heavily repeated video frames, but may start removing some distinct samples." },
  { value: 4, label: "4", title: "Aggressive", description: "More permissive. Can remove images that still look useful for training in camera datasets." },
  { value: 5, label: "5", title: "Very aggressive", description: "Strong near-duplicate cleanup. Recommended only for extremely repetitive imports." },
  { value: 6, label: "6", title: "High sensitivity", description: "Treats many visually similar scenes as duplicates. Use with caution." },
  { value: 7, label: "7", title: "Extreme", description: "Very broad duplicate matching. Likely to remove many frames that differ only slightly." },
  { value: 8, label: "8", title: "Maximum", description: "Most aggressive setting. Best used only for experimentation, not as a default." }
];

export default function DatasetPage({ apiBase, selectedProject, datasets, refreshDatasets, onViewDataset }) {
  const [form, setForm] = useState({
    version: "",
    note: "",
    import_mode: "",
    dataset_path: "",
    visual_dup_threshold: -1
  });
  const [message, setMessage] = useState("");
  const [progressById, setProgressById] = useState({});
  const [activeDatasetId, setActiveDatasetId] = useState(null);
  const [pendingActiveImport, setPendingActiveImport] = useState(null);

  useEffect(() => {
    const runningIds = datasets
      .filter((dataset) => {
        const status = progressById[dataset.id]?.status ?? dataset.progress_json?.status;
        return status === "running" || status === "queued";
      })
      .map((dataset) => dataset.id);

    if (!runningIds.length) return undefined;
    const timer = window.setInterval(async () => {
      const updates = await Promise.all(
        runningIds.map(async (datasetId) => {
          const response = await fetch(`${apiBase}/datasets/${datasetId}/progress`);
          return [datasetId, await response.json()];
        })
      );
      const nextProgress = Object.fromEntries(updates);
      setProgressById((current) => ({ ...current, ...nextProgress }));
      const done = updates.every(([, progress]) => progress.status === "completed" || progress.status === "failed");
      if (done) {
        refreshDatasets();
      }
    }, 1500);

    return () => window.clearInterval(timer);
  }, [apiBase, datasets, progressById, refreshDatasets]);

  useEffect(() => {
    if (!datasets.length) {
      setActiveDatasetId(null);
      setPendingActiveImport(null);
      return;
    }
    if (activeDatasetId === null) {
      setActiveDatasetId(datasets[0].id);
    }
  }, [activeDatasetId, datasets]);

  useEffect(() => {
    if (!pendingActiveImport) return;
    const importedDataset = datasets.find((dataset) => dataset.id === pendingActiveImport.id);
    if (importedDataset) {
      setPendingActiveImport(null);
    }
  }, [datasets, pendingActiveImport]);

  async function handleSubmit(event) {
    event.preventDefault();
    if (!selectedProject || !form.import_mode || form.import_mode === "labelstudio") return;
    const response = await fetch(`${apiBase}/datasets/projects/${selectedProject.id}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(form)
    });
    const data = await response.json();
    if (!response.ok) {
      setMessage(data.detail || "Unable to import dataset.");
      return;
    }
    setMessage(`Started import for ${data.version_name || data.version}.`);
    setForm({
      version: "",
      note: "",
      import_mode: "",
      dataset_path: "",
      visual_dup_threshold: -1
    });
    // Make the brand-new import the tracked progress card immediately so the
    // panel does not fall back to the previous completed version.
    setActiveDatasetId(data.id);
    setPendingActiveImport({ id: data.id, version: data.version_name || data.version });
    setProgressById((current) => ({ ...current, [data.id]: data.progress_json || {} }));
    refreshDatasets();
  }

  async function handleDelete(dataset) {
    const confirmation = window.prompt(`Type DELETE to remove dataset version "${dataset.version}".`);
    if (confirmation !== "DELETE") {
      setMessage("Dataset deletion cancelled.");
      return;
    }
    const response = await fetch(`${apiBase}/datasets/${dataset.id}`, {
      method: "DELETE",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ confirmation })
    });
    const data = await response.json();
    if (!response.ok) {
      setMessage(data.detail || "Unable to delete dataset version.");
      return;
    }
    setMessage(`Deleted dataset version ${dataset.version}.`);
    if (dataset.id === activeDatasetId) {
      setActiveDatasetId(null);
    }
    refreshDatasets();
  }

  async function openBrowser(targetField) {
    try {
      const startPath = form[targetField] || null;
      const response = await fetch(
        `${apiBase}/datasets/browse-dialog${startPath ? `?path=${encodeURIComponent(startPath)}` : ""}`
      );

      let data = {};
      try {
        data = await response.json();
      } catch {
        data = {};
      }

      if (!response.ok) {
        setMessage(data.detail || "Unable to open folder picker. Please check the backend and try again.");
        return;
      }
      if (data.cancelled) {
        setMessage("Folder selection cancelled.");
        return;
      }
      if (!data.selected_path) {
        setMessage("No folder was selected.");
        return;
      }

      setForm((current) => ({ ...current, [targetField]: data.selected_path }));
      setMessage(`Selected folder for ${targetField.replace("_", " ")}.`);
    } catch (error) {
      console.error("Folder picker failed", error);
      setMessage("Folder picker failed. Restart the backend and try again.");
    }
  }

  const submitLabel =
    form.import_mode === "labelstudio"
      ? "Link Dataset"
      : "Import";
  const selectedVisualDupThreshold = visualDupThresholdOptions.find(
    (option) => option.value === Number(form.visual_dup_threshold)
  ) ?? visualDupThresholdOptions[0];

  const activeDataset =
    activeDatasetId === null
      ? datasets[0] ?? null
      : (datasets.find((dataset) => dataset.id === activeDatasetId) ?? null);
  const activeProgress =
    activeDataset
      ? progressById[activeDataset.id] ?? activeDataset.progress_json ?? {}
      : (activeDatasetId !== null ? progressById[activeDatasetId] ?? null : null);
  const activeSummary = activeDataset?.import_summary_json ?? null;
  const activeStatus = activeProgress?.status ?? activeDataset?.status ?? "idle";
  const activeVersionLabel = activeDataset?.version ?? pendingActiveImport?.version ?? null;
  const importDetailsExpanded = !!form.import_mode && form.import_mode !== "labelstudio";

  return (
    <div className="space-y-6">
      <section className="rounded-3xl bg-white p-6 shadow-sm">
        <h2 className="text-2xl font-semibold">Dataset Import + Cleanse</h2>
        <p className="mt-2 text-slate-600">
          {selectedProject
            ? `Import datasets into ${selectedProject.name}, cleanse them immediately, and keep each version as a delta only. Train/val split stays in the training workflow.`
            : "Choose a project first to start importing datasets."}
        </p>

        <div className="mt-6 grid gap-3 md:grid-cols-3">
          {importModes.map((mode) => (
            <button
              key={mode.key}
              type="button"
              onClick={() =>
                mode.key === "labelstudio"
                  ? undefined
                  : setForm((current) => ({ ...current, import_mode: current.import_mode === mode.key ? "" : mode.key }))
              }
              className={`rounded-2xl border p-4 text-left ${
                form.import_mode === mode.key ? "border-blue-500 bg-blue-50" : "border-slate-200 bg-slate-50"
              } ${mode.key === "labelstudio" ? "opacity-70" : ""}`}
            >
              <div className="flex items-center justify-between gap-3 text-sm font-semibold text-slate-900">
                <span>{mode.label}</span>
                {mode.key === "labelstudio" && (
                  <span className="rounded-full bg-slate-200 px-2 py-1 text-[11px] uppercase tracking-wide text-slate-600">
                    Coming Soon
                  </span>
                )}
              </div>
              <div className="mt-1 text-sm text-slate-600">{mode.description}</div>
            </button>
          ))}
        </div>

        {importDetailsExpanded ? (
        <form onSubmit={handleSubmit} className="mt-6 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <label className="block text-sm font-medium text-slate-700">
            <span className="mb-2 block">Version Name *</span>
            <input
              className="w-full rounded-xl border border-slate-200 px-4 py-3"
              placeholder="Version Name"
              value={form.version}
              onChange={(event) => setForm({ ...form, version: event.target.value })}
              required
              disabled={!selectedProject || form.import_mode === "labelstudio"}
            />
          </label>

          {form.import_mode === "combined" && (
            <label className="block text-sm font-medium text-slate-700">
              <span className="mb-2 block">Dataset Path *</span>
              <div className="flex gap-3">
                <input
                  className="flex-1 rounded-xl border border-slate-200 px-4 py-3"
                  placeholder="E:\\datasets\\parking_camera"
                  value={form.dataset_path}
                  onChange={(event) => setForm({ ...form, dataset_path: event.target.value })}
                  required
                  disabled={!selectedProject}
                />
                <button
                  type="button"
                  onClick={() => openBrowser("dataset_path")}
                  className="rounded-xl border border-slate-200 px-4 py-3 font-medium text-slate-700"
                  disabled={!selectedProject}
                >
                  Browse
                </button>
              </div>
            </label>
          )}

          <label className="block text-sm font-medium text-slate-700 md:col-span-2 xl:col-span-4">
            <span className="mb-2 block">Version Note</span>
            <textarea
              className="min-h-28 w-full rounded-xl border border-slate-200 px-4 py-3"
              placeholder="Version note"
              value={form.note}
              onChange={(event) => setForm({ ...form, note: event.target.value })}
              disabled={!selectedProject || form.import_mode === "labelstudio"}
            />
          </label>

          <div className="md:col-span-2 xl:col-span-4 text-xs text-slate-500">
            `*` indicates required fields.
          </div>

          {form.import_mode === "combined" && (
            <div className="hidden xl:block" />
          )}

          {form.import_mode === "labelstudio" && (
            <div className="rounded-2xl border border-dashed border-slate-300 bg-slate-50 p-4 text-sm text-slate-500 md:col-span-2 xl:col-span-4">
              Label Studio integration is reserved for a future release.
            </div>
          )}

          <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4 md:col-span-2 xl:col-span-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h3 className="text-sm font-semibold text-slate-900">Visual Duplicate Threshold</h3>
                <p className="mt-1 text-sm text-slate-600">
                  Choose how aggressively perceptual duplicate detection should skip visually similar images inside this import.
                </p>
              </div>
              <div className="rounded-full bg-white px-3 py-2 text-sm font-medium text-slate-700">
                Threshold {selectedVisualDupThreshold.label}
              </div>
            </div>

            <div className="mt-4">
              <input
                className="w-full accent-blue-600"
                type="range"
                min="-1"
                max="8"
                step="1"
                value={form.visual_dup_threshold}
                onChange={(event) => setForm({ ...form, visual_dup_threshold: Number(event.target.value) })}
                disabled={!selectedProject || form.import_mode === "labelstudio"}
              />
              <div className="mt-2 flex justify-between text-xs text-slate-400">
                {visualDupThresholdOptions.map((option) => (
                  <span key={option.value}>{option.label}</span>
                ))}
              </div>
            </div>

            <div className="mt-4 rounded-xl bg-white p-4">
              <div className="text-sm font-semibold text-slate-900">{selectedVisualDupThreshold.title}</div>
              <div className="mt-1 text-sm text-slate-600">{selectedVisualDupThreshold.description}</div>
              <div className="mt-2 text-xs text-slate-500">
                `Off` disables perceptual visual-duplicate cleanup completely, and it is now the default. Exact file-hash duplicates are still skipped separately at every threshold.
              </div>
            </div>
          </div>

          <button
            className="rounded-xl bg-accent px-5 py-3 font-medium text-white md:w-52"
            disabled={!selectedProject || form.import_mode === "labelstudio"}
          >
            {submitLabel}
          </button>
        </form>
        ) : (
          <div className="mt-6 rounded-2xl border border-dashed border-slate-300 bg-slate-50 p-5 text-sm text-slate-500">
            Select an import option to configure a dataset import.
          </div>
        )}
        <div className="mt-3 text-sm text-slate-500">{message}</div>

        <div className="mt-8 rounded-2xl border border-slate-200 bg-slate-50 p-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h3 className="text-lg font-semibold text-slate-900">Cleanse Progress</h3>
              <p className="mt-1 text-sm text-slate-600">
                {activeVersionLabel
                  ? `Tracking ${activeVersionLabel}. Only valid new files are committed to project storage.`
                  : "Start an import to see validation, duplicate checks, and accepted-file commit progress."}
              </p>
            </div>
            {activeVersionLabel && (
              <button
                type="button"
                onClick={() => activeDataset && setActiveDatasetId(activeDataset.id)}
                className="rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700"
              >
                {activeVersionLabel}
              </button>
            )}
          </div>

          {activeVersionLabel ? (
            <>
              <div className="mt-5 flex items-center justify-between gap-3 text-sm text-slate-600">
                <span className="font-medium capitalize">{(activeStatus || "queued").replaceAll("_", " ")}</span>
                <span>{activeProgress?.percent ?? 0}%</span>
              </div>
              <div className="mt-3 h-3 overflow-hidden rounded-full bg-slate-200">
                <div
                  className={`h-full rounded-full transition-all ${
                    activeStatus === "failed" ? "bg-rose-500" : "bg-blue-500"
                  }`}
                  style={{ width: `${activeProgress?.percent ?? 0}%` }}
                />
              </div>
              <div className="mt-2 text-xs text-slate-500">
                {activeProgress?.message || "Waiting to start import."}
              </div>

              {activeStatus === "failed" && (
                <div className="mt-4 rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">
                  <div className="font-medium">Import failed</div>
                  <div className="mt-1 whitespace-pre-wrap break-words">{activeDataset?.error_message || "Unknown import error."}</div>
                </div>
              )}

              <div className="mt-5 grid gap-3 md:grid-cols-3 xl:grid-cols-6">
                <SummaryCard label="Imported" value={activeSummary?.imported_files_count ?? 0} />
                <SummaryCard label="Accepted" value={activeSummary?.accepted_new_images_count ?? 0} />
                <SummaryCard label="Duplicates" value={activeSummary?.duplicates_skipped ?? 0} />
                <SummaryCard label="Exact Dups" value={activeSummary?.exact_duplicates_skipped ?? 0} />
                <SummaryCard label="Visual Dups" value={activeSummary?.perceptual_duplicates_skipped ?? 0} />
                <SummaryCard label="Visual Threshold" value={activeSummary?.visual_dup_threshold ?? 0} />
                <SummaryCard label="Corrupt" value={activeSummary?.corrupt_images_skipped ?? 0} />
                <SummaryCard label="Invalid Labels" value={activeSummary?.invalid_labels_skipped ?? 0} />
                <SummaryCard label="Empty Labels Kept" value={activeSummary?.empty_labels_accepted ?? 0} />
              </div>
            </>
          ) : (
            <div className="mt-5 rounded-2xl border border-dashed border-slate-300 bg-white p-6 text-sm text-slate-500">
              No dataset imports yet.
            </div>
          )}
        </div>
      </section>

      <section className="rounded-3xl bg-white p-6 shadow-sm">
        <div className="flex items-center justify-between gap-3">
          <div>
            <h2 className="text-2xl font-semibold">Dataset Versions</h2>
            <p className="mt-2 text-slate-600">
              Each row is one additive import event. The total column shows cumulative accepted images up to that version.
            </p>
          </div>
        </div>

        <div className="mt-6">
          <DatasetVersions
            datasets={datasets}
            selectedDatasetId={activeDatasetId}
            onSelect={setActiveDatasetId}
            onDelete={handleDelete}
            onViewDataset={onViewDataset}
          />
        </div>
      </section>
    </div>
  );
}

function SummaryCard({ label, value }) {
  return (
    <div className="rounded-xl bg-white p-4">
      <div className="text-sm text-slate-500">{label}</div>
      <div className="mt-2 text-2xl font-semibold text-slate-900">{value}</div>
    </div>
  );
}
