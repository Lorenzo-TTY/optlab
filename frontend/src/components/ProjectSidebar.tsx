import { Plus, Save } from "lucide-react";

import type { OptimizationProject } from "../projectStorage";

interface ProjectSidebarProps {
  activeProjectId: string;
  projects: OptimizationProject[];
  onCreate: () => void;
  onRename: (projectId: string, name: string) => void;
  onSave: () => void;
  onSelect: (projectId: string) => void;
}

export function ProjectSidebar({
  activeProjectId,
  projects,
  onCreate,
  onRename,
  onSave,
  onSelect,
}: ProjectSidebarProps) {
  const activeProject = projects.find((project) => project.id === activeProjectId) ?? projects[0];

  return (
    <aside className="project-sidebar" aria-label="Optimization projects">
      <div className="project-sidebar-header">
        <div>
          <h2>Projects</h2>
          <p>Save and resume local optimization work.</p>
        </div>
        <button className="secondary-button icon-button-text" type="button" onClick={onCreate}>
          <Plus aria-hidden="true" size={16} />
          New project
        </button>
      </div>

      {activeProject ? (
        <label className="field project-name-field">
          <span>Project name</span>
          <input
            aria-label="Project name"
            value={activeProject.name}
            onChange={(event) => onRename(activeProject.id, event.target.value)}
          />
        </label>
      ) : null}

      <button className="primary-button save-project-button icon-button-text" type="button" onClick={onSave}>
        <Save aria-hidden="true" size={16} />
        Save project
      </button>

      <div className="project-list" aria-label="Project list">
        {projects.map((project) => (
          <button
            className={`project-list-item ${project.id === activeProjectId ? "active" : ""}`}
            key={project.id}
            aria-current={project.id === activeProjectId ? "true" : undefined}
            type="button"
            onClick={() => onSelect(project.id)}
          >
            <span>{project.name || "Untitled project"}</span>
            <small>
              {project.observations.length} saved / {project.rows.filter((row) => row.status !== "submitted").length} editable
            </small>
            <small>Updated {formatTimestamp(project.updatedAt)}</small>
          </button>
        ))}
      </div>
    </aside>
  );
}

function formatTimestamp(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "just now";
  }
  return date.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}
