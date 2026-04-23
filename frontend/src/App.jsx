import { useEffect, useState } from "react";
import ProjectsPage from "./pages/ProjectsPage";
import DatasetPage from "./pages/DatasetPage";
import DatasetDashboard from "./pages/DatasetDashboard";
import DatasetInspectionPage from "./pages/DatasetInspectionPage";
import TrainingPage from "./pages/TrainingPage";
import ComparisonPage from "./pages/ComparisonPage";

const apiBase = "http://127.0.0.1:8000/api";

const navItems = [
  { key: "projects", label: "Projects" },
  { key: "datasets", label: "Datasets" },
  { key: "dashboard", label: "Dataset Dashboard" },
  { key: "training", label: "Training" },
  { key: "comparison", label: "Model Comparison" }
];

export default function App() {
  const [page, setPage] = useState("projects");
  const [projects, setProjects] = useState([]);
  const [selectedProjectId, setSelectedProjectId] = useState(null);
  const [inspectionDatasetId, setInspectionDatasetId] = useState(null);
  const [datasets, setDatasets] = useState([]);
  const [runs, setRuns] = useState([]);

  async function fetchProjects(nextSelectedProjectId) {
    const response = await fetch(`${apiBase}/projects`);
    const data = await response.json();
    setProjects(data);

    if (typeof nextSelectedProjectId !== "undefined") {
      const explicitSelection = data.find((project) => project.id === nextSelectedProjectId);
      setSelectedProjectId(explicitSelection ? explicitSelection.id : data[0]?.id ?? null);
      return;
    }

    const currentSelection = data.find((project) => project.id === selectedProjectId);
    if (currentSelection) return;
    setSelectedProjectId(data[0]?.id ?? null);
  }

  async function fetchDatasets(projectId) {
    if (!projectId) {
      setDatasets([]);
      return;
    }
    const response = await fetch(`${apiBase}/datasets/projects/${projectId}`);
    const data = await response.json();
    setDatasets(data);
  }

  async function fetchRuns(projectId) {
    const query = projectId ? `?project_id=${projectId}` : "";
    const response = await fetch(`${apiBase}/training/runs${query}`);
    const data = await response.json();
    setRuns(data);
  }

  useEffect(() => {
    fetchProjects();
  }, []);

  useEffect(() => {
    fetchDatasets(selectedProjectId);
    fetchRuns(selectedProjectId);
  }, [selectedProjectId]);

  const selectedProject = projects.find((project) => project.id === selectedProjectId) ?? null;
  const inspectionDataset = datasets.find((dataset) => dataset.id === inspectionDatasetId) ?? null;

  function goToPage(nextPage) {
    if (nextPage !== "inspection") {
      setInspectionDatasetId(null);
    }
    setPage(nextPage);
  }

  function openInspection(dataset) {
    setInspectionDatasetId(dataset.id);
    setPage("inspection");
  }

  return (
    <div className="min-h-screen md:flex">
      <aside className="w-full bg-panel text-white md:min-h-screen md:w-72">
        <div className="border-b border-slate-800 px-6 py-5">
          <h1 className="text-2xl font-semibold">Yolo Trainer</h1>
          <p className="mt-2 text-sm text-slate-300">Local model ops for camera teams</p>
        </div>
        <nav className="space-y-2 px-4 py-5">
          {navItems.map((item) => (
            <button
              key={item.key}
              onClick={() => goToPage(item.key)}
              className={`w-full rounded-xl px-4 py-3 text-left transition ${
                page === item.key ? "bg-accent text-white" : "bg-slate-900/40 text-slate-300 hover:bg-slate-800"
              }`}
            >
              {item.label}
            </button>
          ))}
        </nav>
      </aside>

      <main className="flex-1 p-4 md:p-8">
        <Breadcrumbs
          page={page}
          selectedProject={selectedProject}
          inspectionDataset={inspectionDataset}
          onNavigate={goToPage}
        />
        {page === "projects" && (
          <ProjectsPage
            apiBase={apiBase}
            projects={projects}
            selectedProjectId={selectedProjectId}
            setSelectedProjectId={setSelectedProjectId}
            refreshProjects={fetchProjects}
          />
        )}
        {page === "datasets" && (
          <DatasetPage
            apiBase={apiBase}
            selectedProject={selectedProject}
            datasets={datasets}
            refreshDatasets={() => fetchDatasets(selectedProjectId)}
            onViewDataset={openInspection}
          />
        )}
        {page === "inspection" && (
          <DatasetInspectionPage
            apiBase={apiBase}
            selectedProject={selectedProject}
            datasetVersion={inspectionDataset}
            onBack={() => goToPage("datasets")}
          />
        )}
        {page === "dashboard" && (
          <DatasetDashboard apiBase={apiBase} selectedProject={selectedProject} datasets={datasets} />
        )}
        {page === "training" && (
          <TrainingPage
            apiBase={apiBase}
            selectedProject={selectedProject}
            datasets={datasets}
            runs={runs}
            refreshRuns={() => fetchRuns(selectedProjectId)}
          />
        )}
        {page === "comparison" && (
          <ComparisonPage apiBase={apiBase} selectedProject={selectedProject} />
        )}
      </main>
    </div>
  );
}

function Breadcrumbs({ page, selectedProject, inspectionDataset, onNavigate }) {
  const crumbs = [{ label: "Projects", page: "projects" }];
  if (selectedProject) {
    crumbs.push({ label: selectedProject.name, page: "projects" });
  }
  if (page === "datasets" || page === "dashboard" || page === "inspection") {
    crumbs.push({ label: "Datasets", page: "datasets" });
  }
  if (page === "inspection" && inspectionDataset) {
    crumbs.push({ label: inspectionDataset.version, page: "datasets" });
    crumbs.push({ label: "View Dataset", page: "inspection" });
  }
  if (page === "training") {
    crumbs.push({ label: "Training", page: "training" });
  }
  if (page === "comparison") {
    crumbs.push({ label: "Model Comparison", page: "comparison" });
  }

  return (
    <nav className="mb-5 flex flex-wrap items-center gap-2 text-sm text-slate-500">
      {crumbs.map((crumb, index) => {
        const isLast = index === crumbs.length - 1;
        return (
          <span key={`${crumb.label}-${index}`} className="flex items-center gap-2">
            {index > 0 && <span>/</span>}
            {isLast ? (
              <span className="font-medium text-slate-700">{crumb.label}</span>
            ) : (
              <button
                type="button"
                onClick={() => onNavigate(crumb.page)}
                className="font-medium text-blue-700 hover:text-blue-900"
              >
                {crumb.label}
              </button>
            )}
          </span>
        );
      })}
    </nav>
  );
}
