import { useState } from "react";
import ProjectList from "../components/ProjectList";

export default function ProjectsPage({
  apiBase,
  projects,
  selectedProjectId,
  setSelectedProjectId,
  refreshProjects
}) {
  const [form, setForm] = useState({ name: "", camera_name: "", description: "" });
  const [message, setMessage] = useState("");
  const [editingProjectId, setEditingProjectId] = useState(null);

  async function handleSubmit(event) {
    event.preventDefault();
    const isEditing = editingProjectId !== null;
    const response = await fetch(`${apiBase}/projects${isEditing ? `/${editingProjectId}` : ""}`, {
      method: isEditing ? "PUT" : "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(form)
    });
    const data = await response.json();
    if (!response.ok) {
      setMessage(data.detail || `Unable to ${isEditing ? "update" : "create"} project.`);
      return;
    }
    setMessage(`${isEditing ? "Updated" : "Created"} project ${data.name}.`);
    setForm({ name: "", camera_name: "", description: "" });
    setEditingProjectId(null);
    await refreshProjects(data.id);
  }

  function handleEdit(project) {
    setEditingProjectId(project.id);
    setForm({
      name: project.name,
      camera_name: project.camera_name,
      description: project.description || ""
    });
    setMessage(`Editing ${project.name}.`);
    setSelectedProjectId(project.id);
  }

  async function handleDelete(project) {
    const confirmed = window.confirm(`Delete project "${project.name}"? This removes linked dataset and training metadata.`);
    if (!confirmed) return;

    const response = await fetch(`${apiBase}/projects/${project.id}`, {
      method: "DELETE"
    });
    const data = await response.json();
    if (!response.ok) {
      setMessage(data.detail || "Unable to delete project.");
      return;
    }

    const remainingProjects = projects.filter((item) => item.id !== project.id);
    const nextProjectId =
      selectedProjectId === project.id ? (remainingProjects[0]?.id ?? null) : selectedProjectId;
    setMessage(`Deleted project ${project.name}.`);
    if (editingProjectId === project.id) {
      setEditingProjectId(null);
      setForm({ name: "", camera_name: "", description: "" });
    }
    await refreshProjects(nextProjectId);
  }

  function handleCancelEdit() {
    setEditingProjectId(null);
    setForm({ name: "", camera_name: "", description: "" });
    setMessage("Edit cancelled.");
  }

  return (
    <div className="space-y-6">
      <section className="rounded-3xl bg-white p-6 shadow-sm">
        <h2 className="text-2xl font-semibold">Project Management</h2>
        <p className="mt-2 text-slate-600">
          Create one project per camera or deployment scenario, then edit or remove it whenever needed.
        </p>
        <form onSubmit={handleSubmit} className="mt-6 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <input
            className="rounded-xl border border-slate-200 px-4 py-3"
            placeholder="Project name"
            value={form.name}
            onChange={(event) => setForm({ ...form, name: event.target.value })}
            required
          />
          <input
            className="rounded-xl border border-slate-200 px-4 py-3"
            placeholder="Camera name"
            value={form.camera_name}
            onChange={(event) => setForm({ ...form, camera_name: event.target.value })}
            required
          />
          <input
            className="rounded-xl border border-slate-200 px-4 py-3 md:col-span-2"
            placeholder="Description"
            value={form.description}
            onChange={(event) => setForm({ ...form, description: event.target.value })}
          />
          <div className="flex flex-wrap gap-3 xl:col-span-4">
            <button className="rounded-xl bg-accent px-5 py-3 font-medium text-white">
              {editingProjectId !== null ? "Save Changes" : "Create Project"}
            </button>
            {editingProjectId !== null && (
              <button
                type="button"
                onClick={handleCancelEdit}
                className="rounded-xl border border-slate-200 px-5 py-3 font-medium text-slate-700"
              >
                Cancel
              </button>
            )}
          </div>
        </form>
        <div className="mt-3 text-sm text-slate-500">{message}</div>
      </section>

      <ProjectList
        projects={projects}
        selectedProjectId={selectedProjectId}
        setSelectedProjectId={setSelectedProjectId}
        onEdit={handleEdit}
        onDelete={handleDelete}
      />
    </div>
  );
}
