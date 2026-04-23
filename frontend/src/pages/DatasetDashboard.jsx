import DatasetStatsPanel from "../components/DatasetStatsPanel";
import { useEffect, useState } from "react";

export default function DatasetDashboard({ apiBase, selectedProject, datasets }) {
  const [selectedDatasetId, setSelectedDatasetId] = useState("");
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!datasets.length) {
      setSelectedDatasetId("");
      setStats(null);
      return;
    }
    setSelectedDatasetId((current) => {
      if (current && datasets.some((dataset) => String(dataset.id) === String(current))) {
        return current;
      }
      return String(datasets[0].id);
    });
  }, [datasets]);

  useEffect(() => {
    let cancelled = false;

    async function loadStats() {
      if (!selectedProject || !selectedDatasetId) {
        setStats(null);
        setError("");
        return;
      }
      setLoading(true);
      setError("");
      try {
        const response = await fetch(`${apiBase}/datasets/${selectedDatasetId}/dashboard`);
        const data = await response.json();
        if (!response.ok) {
          throw new Error(data.detail || "Unable to load dataset dashboard.");
        }
        if (!cancelled) {
          setStats(data ?? {});
        }
      } catch (loadError) {
        if (!cancelled) {
          setStats(null);
          setError(loadError.message || "Unable to load dataset dashboard.");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    loadStats();
    return () => {
      cancelled = true;
    };
  }, [apiBase, selectedDatasetId, selectedProject?.id]);

  return (
    <div className="space-y-6">
      <div className="max-w-sm">
        <label className="block text-sm font-medium text-slate-700">
          <span className="mb-2 block">Dataset Version</span>
          <select
            className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2"
            value={selectedDatasetId}
            onChange={(event) => setSelectedDatasetId(event.target.value)}
            disabled={!datasets.length}
          >
            {!datasets.length && <option value="">No dataset versions</option>}
            {datasets.map((dataset) => (
              <option key={dataset.id} value={dataset.id}>
                {dataset.version}
              </option>
            ))}
          </select>
        </label>
      </div>
      <DatasetStatsPanel stats={stats} loading={loading} error={error} />
    </div>
  );
}
