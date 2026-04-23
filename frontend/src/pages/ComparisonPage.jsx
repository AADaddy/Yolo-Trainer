import { useEffect, useMemo, useState } from "react";
import { createPortal } from "react-dom";
import Tooltip from "../components/Tooltip";

const metricTooltips = {
  best_accuracy:
    "Best Accuracy uses mAP50-95, the stricter quality metric across multiple IoU thresholds. Higher is better, and strong models keep this value high without relying only on easier matches.",
  best_speed:
    "Best Speed uses inference time per image. Lower is better for deployment, especially for real-time or batch workloads where latency matters.",
  best_balanced:
    "Best Balanced Choice combines normalized mAP50-95 and inference time. It helps highlight models that stay accurate without becoming too slow to deploy.",
  scatter:
    "Accuracy vs Speed plots inference time on the X-axis and mAP50-95 on the Y-axis. Higher and further left is generally better: more accurate with lower latency.",
  bar_chart:
    "Metric Comparison shows one selected quality metric across the filtered runs. Use it for quick side-by-side ranking when you want to compare a single signal at a time.",
  mAP50:
    "mAP50 is a quick indicator of detection quality at IoU 0.5. Higher is better. As a practical guide, >0.70 is strong, 0.50-0.70 is usable but worth reviewing, and <0.50 is usually weak for deployment decisions.",
  mAP50_95:
    "mAP50-95 averages quality across stricter IoU thresholds and is the best headline accuracy metric here. >0.50 is strong, 0.30-0.50 is moderate, and <0.30 usually means the model still needs work.",
  precision:
    "Precision shows how often predicted detections are correct. Higher precision means fewer false positives. >0.80 is strong, 0.60-0.80 is acceptable, and <0.60 means the model is producing too many wrong detections.",
  recall:
    "Recall shows how often the model finds real objects. Higher recall means fewer misses. >0.80 is strong, 0.60-0.80 is moderate, and <0.60 means the model is missing too many real objects.",
  inference_time_ms:
    "Inference time is the practical per-image latency when available. Lower is better. <10 ms is excellent for fast deployment, 10-30 ms is often acceptable, and >30 ms starts to become expensive for real-time use.",
  imgsz:
    "Image size is the training resolution used for the run.\n\nLarger image sizes can improve small-object detection because more detail reaches the model, but they train and infer more slowly.\n\nSmaller image sizes are faster, but may lose detail on small or distant objects."
};

const metricOptions = [
  { value: "mAP50", label: "mAP50" },
  { value: "precision", label: "Precision" },
  { value: "recall", label: "Recall" }
];

const sortableColumns = [
  { key: "run_id", label: "Run ID" },
  { key: "dataset_version", label: "Dataset Version" },
  { key: "model", label: "Model" },
  { key: "mAP50", label: "mAP50", tooltipKey: "mAP50" },
  { key: "mAP50_95", label: "mAP50-95", tooltipKey: "mAP50_95" },
  { key: "precision", label: "Precision", tooltipKey: "precision" },
  { key: "recall", label: "Recall", tooltipKey: "recall" },
  { key: "inference_time_ms", label: "Inference Time", tooltipKey: "inference_time_ms" },
  // Image size is more useful for comparing training behavior here; model size
  // remains in metadata but is not shown in the table to reduce scan noise.
  { key: "imgsz", label: "Image Size", tooltipKey: "imgsz" },
  { key: "started_at", label: "Started Time" }
];

const emptyComparison = {
  rows: [],
  filters: { dataset_versions: [], yolo_versions: [], model_sizes: [] },
  summaries: { best_accuracy: null, best_speed: null, best_balanced: null },
  sort: { sort_by: "started_at", sort_order: "desc" },
  counts: { total_completed_runs: 0, filtered_runs: 0, scatter_points: 0 }
};

export default function ComparisonPage({ apiBase, selectedProject }) {
  const [comparison, setComparison] = useState(emptyComparison);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [datasetVersionId, setDatasetVersionId] = useState("");
  const [yoloVersion, setYoloVersion] = useState("");
  const [modelSize, setModelSize] = useState("");
  const [sortBy, setSortBy] = useState("started_at");
  const [sortOrder, setSortOrder] = useState("desc");
  const [selectedMetric, setSelectedMetric] = useState("mAP50");
  const [selectedRun, setSelectedRun] = useState(null);
  const [downloadError, setDownloadError] = useState("");
  const [downloadingRunId, setDownloadingRunId] = useState(null);

  useEffect(() => {
    if (!selectedProject) {
          setComparison(emptyComparison);
          setError("");
          setSelectedRun(null);
          return;
        }

    let cancelled = false;
    async function loadComparison() {
      setLoading(true);
      setError("");
      try {
        // The whole page reads from one filtered payload so every card, chart, and
        // table view stays aligned to the same run subset.
        const params = new URLSearchParams({
          project_id: String(selectedProject.id),
          sort_by: sortBy,
          sort_order: sortOrder
        });
        if (datasetVersionId) params.set("dataset_version_id", datasetVersionId);
        if (yoloVersion) params.set("yolo_version", yoloVersion);
        if (modelSize) params.set("model_size", modelSize);

        const response = await fetch(`${apiBase}/comparison/runs?${params.toString()}`);
        const data = await response.json();
        if (!response.ok) {
          throw new Error(data.detail || "Unable to load comparison data.");
        }
        if (!cancelled) {
          setComparison({
            rows: Array.isArray(data.rows) ? data.rows : [],
            filters: data.filters ?? emptyComparison.filters,
            summaries: data.summaries ?? emptyComparison.summaries,
            sort: data.sort ?? emptyComparison.sort,
            counts: data.counts ?? emptyComparison.counts
          });
        }
      } catch (loadError) {
        if (!cancelled) {
          setComparison(emptyComparison);
          setError(loadError.message || "Unable to load comparison data.");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    loadComparison();
    return () => {
      cancelled = true;
    };
  }, [apiBase, datasetVersionId, modelSize, selectedProject?.id, sortBy, sortOrder, yoloVersion]);

  const rows = Array.isArray(comparison.rows) ? comparison.rows : [];
  const selectedMetricLabel = metricOptions.find((option) => option.value === selectedMetric)?.label ?? "mAP50";

  const scatterRows = useMemo(
    () => rows.filter((row) => row.inference_time_ms !== null && row.inference_time_ms !== undefined),
    [rows]
  );

  if (!selectedProject) {
    return <EmptyPanel>Choose a project to compare completed training runs.</EmptyPanel>;
  }

  return (
    <div className="space-y-6">
      <section className="rounded-3xl bg-white p-6 shadow-sm">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
          <div>
            <h2 className="text-2xl font-semibold">Model Comparison</h2>
            <p className="mt-2 text-slate-600">
              Compare completed runs for {selectedProject.name} and read the accuracy, speed, and deployment tradeoffs.
            </p>
          </div>
          <FiltersPanel
            filters={comparison.filters}
            datasetVersionId={datasetVersionId}
            yoloVersion={yoloVersion}
            modelSize={modelSize}
            onDatasetVersionChange={setDatasetVersionId}
            onYoloVersionChange={setYoloVersion}
            onModelSizeChange={setModelSize}
          />
        </div>
      </section>

      {loading ? <EmptyPanel>Loading comparison data...</EmptyPanel> : null}
      {error ? <EmptyPanel>{error}</EmptyPanel> : null}

      {!loading && !error && (
        <>
          <div className="grid gap-4 xl:grid-cols-3">
            <SummaryCard
              title="Best Accuracy"
              tooltip={metricTooltips.best_accuracy}
              summary={comparison.summaries.best_accuracy}
              emptyText="No completed runs available for accuracy ranking."
            />
            <SummaryCard
              title="Best Speed"
              tooltip={metricTooltips.best_speed}
              summary={comparison.summaries.best_speed}
              emptyText="Inference time is not available for the filtered runs yet."
            />
            <SummaryCard
              title="Best Balanced Choice"
              tooltip={metricTooltips.best_balanced}
              summary={comparison.summaries.best_balanced}
              emptyText="Balanced ranking needs runs with both accuracy and inference time."
            />
          </div>

          <div className="grid gap-4 xl:grid-cols-[1.35fr_1fr]">
            <ChartCard
              title="Accuracy vs Speed"
              tooltip={metricTooltips.scatter}
              footer={`${comparison.counts.scatter_points ?? 0} plotted run(s) with inference time.`}
            >
              <ScatterPlot rows={scatterRows} />
            </ChartCard>

            <ChartCard
              title="Metric Comparison"
              tooltip={metricTooltips.bar_chart}
              controls={
                <select
                  value={selectedMetric}
                  onChange={(event) => setSelectedMetric(event.target.value)}
                  className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm"
                >
                  {metricOptions.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              }
              footer={`Comparing ${selectedMetricLabel} across ${rows.length} filtered run(s).`}
            >
              <MetricBarChart rows={rows} metric={selectedMetric} />
            </ChartCard>
          </div>

          <section className="overflow-hidden rounded-2xl bg-white shadow-sm">
            <div className="border-b border-slate-200 px-6 py-4">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <h3 className="text-lg font-semibold text-slate-900">Comparison Table</h3>
                  <p className="mt-1 text-sm text-slate-500">
                    Sort any column to inspect accuracy, speed, and deployment footprint side by side.
                  </p>
                </div>
                <div className="text-sm text-slate-500">{comparison.counts.filtered_runs ?? 0} run(s)</div>
              </div>
            </div>
          <ComparisonTable
              apiBase={apiBase}
              rows={rows}
              sortBy={sortBy}
              sortOrder={sortOrder}
              downloadError={downloadError}
              downloadingRunId={downloadingRunId}
              onDownloadError={setDownloadError}
              onDownloadStart={setDownloadingRunId}
              onRowClick={setSelectedRun}
              onSortChange={(nextSortBy) => {
                if (nextSortBy === sortBy) {
                  setSortOrder((current) => (current === "asc" ? "desc" : "asc"));
                } else {
                  setSortBy(nextSortBy);
                  setSortOrder("desc");
                }
              }}
            />
          </section>
        </>
      )}
      {selectedRun ? <RunDetailsDrawer run={selectedRun} onClose={() => setSelectedRun(null)} /> : null}
    </div>
  );
}

function FiltersPanel({
  filters,
  datasetVersionId,
  yoloVersion,
  modelSize,
  onDatasetVersionChange,
  onYoloVersionChange,
  onModelSizeChange
}) {
  return (
    <div className="grid gap-3 sm:grid-cols-3">
      <FilterSelect
        label="Dataset Version"
        value={datasetVersionId}
        onChange={onDatasetVersionChange}
        options={(filters?.dataset_versions ?? []).map((option) => ({
          value: String(option.id),
          label: option.label
        }))}
      />
      <FilterSelect
        label="YOLO Version"
        value={yoloVersion}
        onChange={onYoloVersionChange}
        options={(filters?.yolo_versions ?? []).map((option) => ({ value: option, label: option }))}
      />
      <FilterSelect
        label="Model Size"
        value={modelSize}
        onChange={onModelSizeChange}
        options={(filters?.model_sizes ?? []).map((option) => ({ value: option, label: option.toUpperCase() }))}
      />
    </div>
  );
}

function FilterSelect({ label, value, onChange, options }) {
  return (
    <label className="block min-w-[180px] text-sm font-medium text-slate-700">
      <span className="mb-2 block">{label}</span>
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2"
      >
        <option value="">All</option>
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </label>
  );
}

function SummaryCard({ title, tooltip, summary, emptyText }) {
  return (
    <div className="rounded-2xl bg-white p-5 shadow-sm">
      <div className="flex items-center justify-between gap-3">
        <h3 className="text-base font-semibold text-slate-900">{title}</h3>
        <Tooltip body={tooltip} placement="bottom" />
      </div>
      {summary ? (
        <div className="mt-4 space-y-2">
          <div className="text-2xl font-semibold text-slate-900">Run #{summary.run_id}</div>
          <div className="text-sm text-slate-600">{summary.model}</div>
          <div className="text-sm text-slate-500">Dataset {summary.dataset_version}</div>
          <div className="rounded-xl bg-slate-50 px-3 py-2 text-sm text-slate-700">{summary.reason}</div>
        </div>
      ) : (
        <div className="mt-4 rounded-xl bg-slate-50 px-3 py-4 text-sm text-slate-500">{emptyText}</div>
      )}
    </div>
  );
}

function ChartCard({ title, tooltip, children, controls = null, footer = "" }) {
  return (
    <section className="rounded-2xl bg-white p-5 shadow-sm">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-2">
          <h3 className="text-lg font-semibold text-slate-900">{title}</h3>
          <Tooltip body={tooltip} placement="bottom" />
        </div>
        {controls}
      </div>
      <div className="mt-4">{children}</div>
      <div className="mt-4 text-sm text-slate-500">{footer}</div>
    </section>
  );
}

function ScatterPlot({ rows }) {
  const [hoveredPoint, setHoveredPoint] = useState(null);
  const width = 560;
  const height = 300;
  const padding = { top: 16, right: 20, bottom: 36, left: 46 };

  if (!rows.length) {
    return <ChartEmptyState>Runs need inference time before they can appear in the accuracy vs speed plot.</ChartEmptyState>;
  }

  const xValues = rows.map((row) => row.inference_time_ms ?? 0);
  const yValues = rows.map((row) => row.mAP50_95 ?? 0);
  const xMin = Math.min(...xValues);
  const xMax = Math.max(...xValues);
  const yMin = 0;
  const yMax = Math.max(1, ...yValues.map((value) => Math.max(value, 0.05)));

  const plotWidth = width - padding.left - padding.right;
  const plotHeight = height - padding.top - padding.bottom;

  const projectX = (value) => {
    if (xMax === xMin) return padding.left + plotWidth / 2;
    return padding.left + ((value - xMin) / (xMax - xMin)) * plotWidth;
  };

  const projectY = (value) => {
    return padding.top + plotHeight - ((value - yMin) / (yMax - yMin || 1)) * plotHeight;
  };

  return (
    <div className="relative overflow-x-auto">
      <svg viewBox={`0 0 ${width} ${height}`} className="h-[320px] w-full min-w-[420px]">
        <line x1={padding.left} y1={height - padding.bottom} x2={width - padding.right} y2={height - padding.bottom} stroke="#cbd5e1" />
        <line x1={padding.left} y1={padding.top} x2={padding.left} y2={height - padding.bottom} stroke="#cbd5e1" />

        {[0, 0.25, 0.5, 0.75, 1].map((tick) => {
          const y = padding.top + plotHeight - tick * plotHeight;
          const label = (tick * yMax).toFixed(2);
          return (
            <g key={tick}>
              <line x1={padding.left} x2={width - padding.right} y1={y} y2={y} stroke="#e2e8f0" strokeDasharray="4 4" />
              <text x={padding.left - 8} y={y + 4} textAnchor="end" fontSize="11" fill="#64748b">
                {label}
              </text>
            </g>
          );
        })}

        {rows.map((row) => {
          const x = projectX(row.inference_time_ms ?? 0);
          const y = projectY(row.mAP50_95 ?? 0);
          return (
            <g key={row.id}>
              <circle
                cx={x}
                cy={y}
                r="6"
                fill="#2563eb"
                className="cursor-pointer"
                onMouseEnter={(event) => setHoveredPoint(buildHoverState(event, row))}
                onMouseMove={(event) => setHoveredPoint(buildHoverState(event, row))}
                onMouseLeave={() => setHoveredPoint(null)}
              />
              <text x={x + 10} y={y - 10} fontSize="11" fill="#334155">
                #{row.id}
              </text>
            </g>
          );
        })}

        <text x={width / 2} y={height - 8} textAnchor="middle" fontSize="12" fill="#475569">
          Inference Time (ms/image)
        </text>
        <text x="14" y={height / 2} textAnchor="middle" fontSize="12" fill="#475569" transform={`rotate(-90 14 ${height / 2})`}>
          mAP50-95
        </text>
      </svg>

      {hoveredPoint ? <ScatterTooltip hoveredPoint={hoveredPoint} /> : null}
    </div>
  );
}

function ScatterTooltip({ hoveredPoint }) {
  const { row, left, top } = hoveredPoint;
  if (typeof document === "undefined") return null;
  return createPortal(
    <div
      className="pointer-events-none fixed z-[10000] w-64 rounded-xl border border-slate-200 bg-white p-3 text-xs shadow-lg"
      style={{ left: `${left}px`, top: `${top}px` }}
    >
      <div className="font-semibold text-slate-900">
        Run #{row.id} - {row.model}
      </div>
      <div className="mt-1 text-slate-500">Dataset {row.dataset_version}</div>
      <div className="mt-2 grid grid-cols-2 gap-2 text-slate-700">
        <TooltipValue label="mAP50" value={formatMetric(row.mAP50)} />
        <TooltipValue label="mAP50-95" value={formatMetric(row.mAP50_95)} />
        <TooltipValue label="Precision" value={formatMetric(row.precision)} />
        <TooltipValue label="Recall" value={formatMetric(row.recall)} />
        <TooltipValue label="Inference" value={formatMilliseconds(row.inference_time_ms)} />
        <TooltipValue label="Image Size" value={formatImageSize(row.imgsz)} />
      </div>
    </div>,
    document.body
  );
}

function TooltipValue({ label, value }) {
  return (
    <div>
      <div className="text-slate-400">{label}</div>
      <div className="font-medium">{value}</div>
    </div>
  );
}

function MetricBarChart({ rows, metric }) {
  if (!rows.length) {
    return <ChartEmptyState>No filtered runs available for charting.</ChartEmptyState>;
  }

  const maxValue = Math.max(0.01, ...rows.map((row) => safeNumber(row[metric])));

  return (
    <div className="space-y-3">
      {rows.map((row) => {
        const value = safeNumber(row[metric]);
        return (
          <div key={row.id} className="rounded-xl bg-slate-50 p-3">
            <div className="flex items-center justify-between gap-3 text-sm">
              <div className="font-medium text-slate-900">
                #{row.id} - {row.model}
              </div>
              <div className="text-slate-500">{formatMetric(value)}</div>
            </div>
            <div className="mt-2 h-3 overflow-hidden rounded-full bg-slate-200">
              <div className="h-full rounded-full bg-blue-500" style={{ width: `${Math.max(4, (value / maxValue) * 100)}%` }} />
            </div>
            <div className="mt-2 text-xs text-slate-500">Dataset {row.dataset_version}</div>
          </div>
        );
      })}
    </div>
  );
}

function ComparisonTable({
  apiBase,
  rows,
  sortBy,
  sortOrder,
  downloadError,
  downloadingRunId,
  onDownloadError,
  onDownloadStart,
  onSortChange,
  onRowClick
}) {
  function handleRowClick(event, row) {
    const interactiveTarget = event.target.closest("button, a, input, select, textarea, label");
    const selectedText = window.getSelection()?.toString();
    // Row click replaces a dedicated details button so quick inspection is one
    // motion, while text selection and any future interactive cells stay usable.
    if (interactiveTarget || selectedText) return;
    onRowClick(row);
  }

  async function handleRunDownload(event, row) {
    // Run ID is the download entry point to avoid adding another action column.
    // Stop propagation so the link downloads best.pt while the rest of the row
    // keeps its established details-drawer click behavior.
    event.preventDefault();
    event.stopPropagation();
    if (!row.has_best_model_artifact || downloadingRunId) return;

    onDownloadStart(row.id);
    onDownloadError("");
    try {
      const response = await fetch(`${apiBase}/comparison/runs/${row.id}/best-model`);
      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        throw new Error(payload.detail || "The best model artifact is unavailable for this run.");
      }

      const blob = await response.blob();
      const filename = getFilenameFromContentDisposition(response.headers.get("Content-Disposition")) || buildFallbackModelFilename(row);
      const objectUrl = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = objectUrl;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(objectUrl);
    } catch (downloadError) {
      onDownloadError(downloadError.message || "Unable to download best model.");
    } finally {
      onDownloadStart(null);
    }
  }

  return (
    <div className="overflow-x-auto">
      {downloadError ? <div className="border-b border-rose-100 bg-rose-50 px-4 py-2 text-sm text-rose-700">{downloadError}</div> : null}
      <table className="min-w-full text-left text-sm">
        <thead className="bg-slate-50 text-slate-600">
          <tr>
            {sortableColumns.map((column) => (
              <th key={column.key} className="px-4 py-3">
                <button
                  type="button"
                  onClick={() => onSortChange(column.key)}
                  className="inline-flex items-center gap-2 font-medium"
                >
                  <span>{column.label}</span>
                  {column.tooltipKey ? <Tooltip body={metricTooltips[column.tooltipKey]} placement="bottom" /> : null}
                  <span className="text-xs text-slate-400">
                    {sortBy === column.key ? (sortOrder === "asc" ? "▲" : "▼") : ""}
                  </span>
                </button>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr
              key={row.id}
              onClick={(event) => handleRowClick(event, row)}
              onKeyDown={(event) => {
                if (event.target.closest("button, a, input, select, textarea, label")) return;
                if (event.key === "Enter" || event.key === " ") {
                  event.preventDefault();
                  onRowClick(row);
                }
              }}
              tabIndex={0}
              className="cursor-pointer border-t border-slate-100 hover:bg-slate-50"
            >
              <td className="px-4 py-3">
                {row.has_best_model_artifact ? (
                  <a
                    href={`${apiBase}/comparison/runs/${row.id}/best-model`}
                    title={downloadingRunId === row.id ? "Downloading best model" : "Download best model"}
                    aria-disabled={downloadingRunId ? "true" : undefined}
                    onClick={(event) => handleRunDownload(event, row)}
                    onKeyDown={(event) => event.stopPropagation()}
                    className={`font-medium text-blue-600 underline decoration-blue-300 underline-offset-2 hover:text-blue-800 ${
                      downloadingRunId ? "opacity-60" : ""
                    }`}
                  >
                    {row.id}
                  </a>
                ) : (
                  <span className="cursor-not-allowed text-slate-400" title="Best model unavailable">
                    {row.id}
                  </span>
                )}
              </td>
              <td className="px-4 py-3">{row.dataset_version}</td>
              <td className="px-4 py-3">{row.model}</td>
              <td className="px-4 py-3">
                <MetricValueBadge value={row.mAP50} formatter={formatMetric} tone={scoreTone(row.mAP50, 0.7, 0.5)} />
              </td>
              <td className="px-4 py-3">
                <MetricValueBadge value={row.mAP50_95} formatter={formatMetric} tone={scoreTone(row.mAP50_95, 0.5, 0.3)} />
              </td>
              <td className="px-4 py-3">
                <MetricValueBadge value={row.precision} formatter={formatMetric} tone={scoreTone(row.precision, 0.8, 0.6)} />
              </td>
              <td className="px-4 py-3">
                <MetricValueBadge value={row.recall} formatter={formatMetric} tone={scoreTone(row.recall, 0.8, 0.6)} />
              </td>
              <td className="px-4 py-3">
                <MetricValueBadge
                  value={row.inference_time_ms}
                  formatter={formatMilliseconds}
                  tone={inverseScoreTone(row.inference_time_ms, 10, 30)}
                />
              </td>
              <td className="px-4 py-3">
                {formatImageSize(row.imgsz)}
              </td>
              <td className="px-4 py-3">{formatDate(row.started_at)}</td>
            </tr>
          ))}
          {!rows.length && (
            <tr>
              <td className="px-4 py-6 text-slate-500" colSpan={sortableColumns.length}>
                No completed runs match the selected filters.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

function RunDetailsDrawer({ run, onClose }) {
  const parameters = run.parameters && typeof run.parameters === "object" ? run.parameters : {};
  const parameterRows = [
    ["YOLO Version", valueOrFallback(parameters.yolo_version, run.yolo_version)],
    ["Model", valueOrFallback(parameters.model_name, run.model)],
    ["Dataset Version", valueOrFallback(parameters.dataset_version, run.dataset_version)],
    ["Image Size", valueOrFallback(parameters.imgsz, null)],
    ["Split Ratio", valueOrFallback(parameters.split_ratio, null)],
    ["Epochs", valueOrFallback(parameters.epochs, null)],
    ["Batch", valueOrFallback(parameters.batch, null)],
    ["Workers", valueOrFallback(parameters.workers, null)],
    ["Cache", formatBoolean(valueOrFallback(parameters.cache, null))],
    ["Rect", formatBoolean(valueOrFallback(parameters.rect, null))],
    ["Optimizer", valueOrFallback(parameters.optimizer, null)],
    ["lr0", valueOrFallback(parameters.lr0, null)],
    ["Momentum", valueOrFallback(parameters.momentum, null)],
    ["Device", valueOrFallback(parameters.device, null)],
    ["AMP", formatBoolean(valueOrFallback(parameters.amp, null))],
    ["Mosaic", formatBoolean(valueOrFallback(parameters.mosaic_enabled, run.mosaic_enabled))],
    ["Multi-scale", formatBoolean(valueOrFallback(parameters.multiscale_enabled, run.multiscale_enabled))]
  ];
  const metricRows = [
    ["mAP50", formatMetric(run.mAP50)],
    ["mAP50-95", formatMetric(run.mAP50_95)],
    ["Precision", formatMetric(run.precision)],
    ["Recall", formatMetric(run.recall)],
    ["Inference Time", formatMilliseconds(run.inference_time_ms)],
    ["Model Size", formatMegabytes(run.model_file_size_mb)]
  ];

  useEffect(() => {
    function handleKeyDown(event) {
      if (event.key === "Escape") onClose();
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-slate-950/40" onMouseDown={onClose}>
      <aside
        className="h-full w-full max-w-xl overflow-y-auto bg-white shadow-2xl"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <div className="sticky top-0 z-10 border-b border-slate-200 bg-white px-6 py-4">
          <div className="flex items-start justify-between gap-4">
            <div>
              <h3 className="text-xl font-semibold text-slate-900">Run #{run.id} Details</h3>
              <p className="mt-1 text-sm text-slate-500">Applied parameters from saved run metadata.</p>
            </div>
            <button type="button" onClick={onClose} className="rounded-xl bg-slate-900 px-4 py-2 text-sm font-medium text-white">
              Close
            </button>
          </div>
        </div>

        <div className="space-y-5 p-6">
          <DrawerSection title="Run Summary">
            <KeyValueGrid
              rows={[
                ["Run ID", run.id],
                ["Dataset Version", run.dataset_version],
                ["Model", run.model],
                ["Started", formatDate(run.started_at)]
              ]}
            />
          </DrawerSection>

          <DrawerSection title="Training Parameters">
            <div className="mb-3 rounded-xl bg-blue-50 px-3 py-2 text-sm text-blue-800">
              Image size: <span className="font-semibold">{formatValue(valueOrFallback(parameters.imgsz, null))}</span>
            </div>
            {/* The drawer reads saved parameters captured when the run started,
                not the current project defaults, so comparisons remain auditable. */}
            <KeyValueGrid rows={parameterRows} />
          </DrawerSection>

          <DrawerSection title="Metrics Summary">
            <KeyValueGrid rows={metricRows} />
          </DrawerSection>
        </div>
      </aside>
    </div>
  );
}

function DrawerSection({ title, children }) {
  return (
    <section className="rounded-2xl border border-slate-200 p-4">
      <h4 className="text-sm font-semibold uppercase tracking-wide text-slate-500">{title}</h4>
      <div className="mt-3">{children}</div>
    </section>
  );
}

function KeyValueGrid({ rows }) {
  return (
    <div className="grid gap-2">
      {rows.map(([label, value]) => (
        <div key={label} className="grid grid-cols-[150px_1fr] gap-3 rounded-xl bg-slate-50 px-3 py-2 text-sm">
          <div className="text-slate-500">{label}</div>
          <div className="break-words font-medium text-slate-900">{formatValue(value)}</div>
        </div>
      ))}
    </div>
  );
}

function MetricValueBadge({ value, formatter, tone }) {
  return (
    <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-medium ${toneClassName(tone)}`}>
      {formatter(value)}
    </span>
  );
}

function buildHoverState(event, row) {
  const left = Math.min(window.innerWidth - 272, Math.max(8, event.clientX + 12));
  const top = Math.min(window.innerHeight - 160, Math.max(8, event.clientY + 12));
  return { row, left, top };
}

function ChartEmptyState({ children }) {
  return <div className="rounded-xl bg-slate-50 p-6 text-sm text-slate-500">{children}</div>;
}

function EmptyPanel({ children }) {
  return <div className="rounded-2xl bg-white p-6 text-sm text-slate-500 shadow-sm">{children}</div>;
}

function safeNumber(value) {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : 0;
}

function scoreTone(value, goodThreshold, mediumThreshold) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return "neutral";
  if (numeric >= goodThreshold) return "good";
  if (numeric >= mediumThreshold) return "medium";
  return "bad";
}

function inverseScoreTone(value, goodThreshold, mediumThreshold) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return "neutral";
  if (numeric <= goodThreshold) return "good";
  if (numeric <= mediumThreshold) return "medium";
  return "bad";
}

function toneClassName(tone) {
  const classes = {
    good: "bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200",
    medium: "bg-amber-50 text-amber-700 ring-1 ring-amber-200",
    bad: "bg-rose-50 text-rose-700 ring-1 ring-rose-200",
    neutral: "bg-slate-100 text-slate-600 ring-1 ring-slate-200"
  };
  return classes[tone] || classes.neutral;
}

function formatMetric(value) {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric.toFixed(4) : "N/A";
}

function formatMilliseconds(value) {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? `${numeric.toFixed(2)} ms` : "N/A";
}

function formatMegabytes(value) {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? `${numeric.toFixed(2)} MB` : "N/A";
}

function formatImageSize(value) {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? String(numeric) : "N/A";
}

function valueOrFallback(value, fallback) {
  if (value === null || value === undefined || value === "") return fallback;
  return value;
}

function formatBoolean(value) {
  if (value === true || value === 1 || value === "true") return "Enabled";
  if (value === false || value === 0 || value === "false") return "Disabled";
  return "N/A";
}

function formatValue(value) {
  if (value === null || value === undefined || value === "") return "N/A";
  if (typeof value === "boolean") return value ? "Enabled" : "Disabled";
  return String(value);
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
    return value || "N/A";
  }
}

function getFilenameFromContentDisposition(headerValue) {
  if (!headerValue) return "";
  const utf8Match = headerValue.match(/filename\*=UTF-8''([^;]+)/i);
  if (utf8Match) return decodeURIComponent(utf8Match[1].replace(/["]/g, ""));
  const asciiMatch = headerValue.match(/filename="?([^";]+)"?/i);
  return asciiMatch ? asciiMatch[1] : "";
}

function buildFallbackModelFilename(row) {
  const parts = [
    `run_${String(row.id).padStart(3, "0")}`,
    row.dataset_version,
    row.model,
    `img${row.imgsz || "unknown"}`
  ];
  if (Number.isFinite(Number(row.mAP50))) {
    parts.push(`map50-${Number(row.mAP50).toFixed(2)}`);
  }
  // The server owns the canonical filename, but this mirrors its metadata-based
  // shape if a browser hides Content-Disposition from the fetch response.
  return `${parts.map(sanitizeFilenamePart).filter(Boolean).join("_").slice(0, 120) || `run_${row.id}_best`}.pt`;
}

function sanitizeFilenamePart(value) {
  return String(value ?? "")
    .trim()
    .replace(/[^A-Za-z0-9._-]+/g, "-")
    .replace(/^[._-]+|[._-]+$/g, "");
}
