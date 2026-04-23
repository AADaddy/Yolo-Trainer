export default function ProjectList({
  projects,
  selectedProjectId,
  setSelectedProjectId,
  onEdit,
  onDelete
}) {
  return (
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
      {projects.map((project) => (
        <div
          key={project.id}
          className={`rounded-2xl border p-5 text-left shadow-sm transition ${
            selectedProjectId === project.id
              ? "border-blue-500 bg-blue-50"
              : "border-slate-200 bg-white hover:border-slate-300"
          }`}
        >
          <button className="w-full text-left" onClick={() => setSelectedProjectId(project.id)}>
            <div className="flex items-center justify-between gap-3">
              <h3 className="text-lg font-semibold">{project.name}</h3>
              <span className="rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-600">
                {project.camera_name}
              </span>
            </div>
            <p className="mt-3 text-sm text-slate-600">{project.description || "No description provided."}</p>
          </button>

          <div className="mt-4 flex gap-3">
            <button
              onClick={() => onEdit(project)}
              className="rounded-xl border border-slate-200 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
            >
              Edit
            </button>
            <button
              onClick={() => onDelete(project)}
              className="rounded-xl border border-rose-200 px-4 py-2 text-sm font-medium text-rose-700 hover:bg-rose-50"
            >
              Delete
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}
