from __future__ import annotations

import subprocess
from pathlib import Path


def browse_directories(path: str | None = None) -> dict:
    if path:
        current_path = Path(path).resolve()
        if not current_path.exists():
            raise ValueError("Path does not exist.")
        if not current_path.is_dir():
            raise ValueError("Path must be a directory.")
        directories = sorted(
            item for item in current_path.iterdir() if item.is_dir()
        )
        return {
            "current_path": str(current_path),
            "parent_path": str(current_path.parent) if current_path.parent != current_path else None,
            "directories": [{"name": item.name, "path": str(item)} for item in directories],
        }

    roots = []
    for drive_letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
        drive = Path(f"{drive_letter}:\\")
        if drive.exists():
            roots.append({"name": str(drive), "path": str(drive)})

    return {
        "current_path": None,
        "parent_path": None,
        "directories": roots,
    }


def open_folder_dialog(initial_path: str | None = None) -> dict:
    resolved_initial = ""
    if initial_path:
        try:
            path = Path(initial_path)
            resolved_initial = str(path if path.is_dir() else path.parent)
        except Exception:
            resolved_initial = ""

    powershell_script = f"""
Add-Type -AssemblyName System.Windows.Forms
$dialog = New-Object System.Windows.Forms.FolderBrowserDialog
$dialog.Description = 'Select Dataset Folder'
$dialog.ShowNewFolderButton = $false
if ('{_escape_ps_string(resolved_initial)}' -ne '') {{
    $dialog.SelectedPath = '{_escape_ps_string(resolved_initial)}'
}}
$result = $dialog.ShowDialog()
if ($result -eq [System.Windows.Forms.DialogResult]::OK) {{
    Write-Output $dialog.SelectedPath
}}
"""
    completed = subprocess.run(
        ["powershell", "-NoProfile", "-STA", "-Command", powershell_script],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        error_message = completed.stderr.strip() or "Native folder picker failed."
        raise RuntimeError(error_message)

    selected_path = completed.stdout.strip()
    return {
        "selected_path": selected_path or "",
        "cancelled": not bool(selected_path),
    }


def _escape_ps_string(value: str) -> str:
    return value.replace("'", "''")
