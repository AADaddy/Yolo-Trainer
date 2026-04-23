import { useEffect } from "react";

import TrainingForm from "../components/TrainingForm";
import TrainingRunsTable from "../components/TrainingRunsTable";

export default function TrainingPage({ apiBase, selectedProject, datasets, runs, refreshRuns }) {
  useEffect(() => {
    if (!selectedProject) return undefined;

    refreshRuns();
    const intervalId = window.setInterval(() => {
      refreshRuns();
    }, 5000);

    return () => {
      window.clearInterval(intervalId);
    };
  }, [selectedProject?.id]);

  return (
    <div className="space-y-6">
      <section className="rounded-3xl bg-white p-6 shadow-sm">
        <h2 className="text-2xl font-semibold">Training Execution</h2>
        <p className="mt-2 text-slate-600">
          Configure deterministic YOLO training jobs for local GPU or CPU execution.
        </p>
      </section>
      <TrainingForm apiBase={apiBase} selectedProject={selectedProject} datasets={datasets} onCreated={refreshRuns} />
      <section className="rounded-2xl border border-dashed border-slate-300 bg-white p-6 text-slate-600 shadow-sm">
        <h3 className="text-lg font-semibold text-slate-900">Hyperparameter Tuning</h3>
        <p className="mt-2">Coming Soon</p>
      </section>
      <TrainingRunsTable apiBase={apiBase} runs={runs} onDeleted={refreshRuns} />
    </div>
  );
}
