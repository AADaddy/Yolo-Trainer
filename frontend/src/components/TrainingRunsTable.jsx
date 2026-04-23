export default function TrainingRunsTable({ apiBase, runs, onDeleted }) {
  async function handleDelete(run) {
    const confirmation = window.prompt(`Type DELETE to remove training run "${run.run_name}".`);
    if (confirmation !== "DELETE") {
      return;
    }
    const response = await fetch(`${apiBase}/training/runs/${run.id}`, {
      method: "DELETE",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ confirmation })
    });
    const data = await response.json();
    if (!response.ok) {
      window.alert(data.detail || "Unable to delete training run.");
      return;
    }
    onDeleted();
  }

  return (
    <div className="overflow-hidden rounded-2xl bg-white shadow-sm">
      <div className="border-b border-slate-200 px-6 py-4">
        <h3 className="text-lg font-semibold">Training Runs</h3>
      </div>
      <div className="overflow-x-auto">
        <table className="min-w-full text-left text-sm">
          <thead className="bg-slate-50 text-slate-600">
            <tr>
              <th className="px-4 py-3">Run ID</th>
              <th className="px-4 py-3">Dataset Version</th>
              <th className="px-4 py-3">Model</th>
              <th className="px-4 py-3">Started Time</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3">mAP50</th>
              <th className="px-4 py-3">Actions</th>
            </tr>
          </thead>
          <tbody>
            {runs.map((run) => (
              <tr key={run.id} className="border-t border-slate-100">
                <td className="px-4 py-3">{run.id}</td>
                <td className="px-4 py-3">{run.parameters_json.dataset_version}</td>
                <td className="px-4 py-3">{run.model_name}</td>
                <td className="px-4 py-3">{formatDate(run.created_at)}</td>
                <td className="px-4 py-3 capitalize">{run.status}</td>
                <td className={`px-4 py-3 font-medium ${map50ColorClass(run.map50_color)}`}>
                  {(run.metrics_json.mAP50 ?? 0).toFixed(4)}
                </td>
                <td className="px-4 py-3">
                  <button
                    type="button"
                    onClick={() => handleDelete(run)}
                    className="rounded-lg border border-rose-200 px-3 py-1.5 text-xs font-medium text-rose-700 hover:bg-rose-50"
                  >
                    Delete
                  </button>
                </td>
              </tr>
            ))}
            {!runs.length && (
              <tr>
                <td className="px-4 py-6 text-slate-500" colSpan="7">
                  No training runs yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
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

function map50ColorClass(level) {
  const classes = {
    high: "text-emerald-600",
    medium: "text-amber-600",
    low: "text-rose-600"
  };
  return classes[level] || "text-slate-700";
}
