"""Auto-update checks against Dropbox deploy payload with safe path fallbacks."""

# Application version — updated by build/publish_to_dropbox.ps1 each release
import json
import os
import os as _os
import subprocess
import sys
from pathlib import Path
from typing import Callable

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import QMessageBox

def _load_app_version() -> str:
    """Load version from version.txt with fallback for packaged and dev environments."""
    candidates = []
    
    # For packaged apps prefer the install-root version file first.
    # This reflects in-place updates where the external file changes between
    # releases while the prior executable may still be running.
    if getattr(sys, 'frozen', False):
        exe_dir = _os.path.dirname(sys.executable)
        candidates.append(_os.path.join(exe_dir, "version.txt"))

        # Fallback to bundled version in the unpacked temporary runtime.
        candidates.append(_os.path.join(sys._MEIPASS, "version.txt"))
    
    # For development: version.txt in workspace root
    candidates.append(_os.path.join(_os.path.dirname(__file__), "..", "version.txt"))
    
    # Also try from current working directory
    candidates.append("version.txt")
    
    for vfile in candidates:
        try:
            if _os.path.exists(vfile):
                with open(vfile) as _vf:
                    version = _vf.read().strip()
                    if version:
                        return version
        except Exception:
            pass
    
    return "1.0.0"

APP_VERSION = _load_app_version()
APP_BUILD_DATE = "2026-01-31"  # fallback; overwritten by version.txt

# Dropbox deploy configuration (replaces legacy OneDrive path)
DROPBOX_DEPLOY = str(Path.home() / "Dropbox" / "limo_deploy")
UPDATE_MANIFEST = "update_manifest.json"


def _resolve_deploy_candidates(preferred_path: str | None = None) -> list[Path]:
    """Return candidate deploy roots in search order (deduplicated)."""
    candidates: list[Path] = []

    env_path = (_os.getenv("ARROW_LIMO_DEPLOY_PATH") or "").strip()
    if env_path:
        candidates.append(Path(env_path))

    if preferred_path:
        candidates.append(Path(preferred_path))

    # Per-user default Dropbox path (works on remote PCs with different usernames).
    candidates.append(Path.home() / "Dropbox" / "limo_deploy")

    # Legacy hard-coded path retained as last-resort fallback.
    candidates.append(Path(r"C:\Users\info\Dropbox\limo_deploy"))

    unique: list[Path] = []
    seen = set()
    for candidate in candidates:
        key = str(candidate).lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(candidate)
    return unique


class UpdateChecker(QThread):
    """Background thread to check for updates without blocking UI"""

    update_available = pyqtSignal(dict)  # Emits update info
    no_update = pyqtSignal()
    error_occurred = pyqtSignal(str)

    def __init__(self, dropbox_path: str = None, silent: bool = False) -> None:
        super().__init__()
        self.deploy_path = Path(dropbox_path or DROPBOX_DEPLOY)
        self.deploy_candidates = _resolve_deploy_candidates(str(self.deploy_path))
        self.silent = silent

    def run(self) -> None:
        """Check for updates in Dropbox deploy location"""
        try:
            manifest = None
            manifest_path = None
            for deploy_root in self.deploy_candidates:
                probe = deploy_root / UPDATE_MANIFEST
                if not probe.exists():
                    continue
                with open(probe, encoding="utf-8-sig") as f:
                    raw = f.read().strip()
                if not raw:
                    continue
                manifest = json.loads(raw)
                manifest_path = probe
                break

            if manifest is None or manifest_path is None:
                looked = "\n".join(str(p / UPDATE_MANIFEST) for p in self.deploy_candidates)
                self.error_occurred.emit(
                    "Update manifest not found. Checked:\n" + looked
                )
                return

            latest_version = manifest.get("latest_version", "")

            if self._is_newer_version(latest_version, APP_VERSION):
                update_info = {
                    "version": latest_version,
                    "release_date": manifest.get("release_date", ""),
                    "changelog": manifest.get("changelog", []),
                    "installer_path": manifest.get("installer_path", ""),
                    "file_size": manifest.get("file_size_mb", 0),
                    "mandatory": manifest.get("mandatory", False),
                    "deploy_path": str(manifest_path.parent),
                }
                self.update_available.emit(update_info)
            else:
                self.no_update.emit()

        except Exception as e:
            self.error_occurred.emit(f"Update check failed: {e!s}")

    def _is_newer_version(self, new_ver: str, current_ver: str) -> bool:
        """Compare version strings (semantic versioning)"""
        try:
            new_parts = [int(x) for x in new_ver.split(".")]
            current_parts = [int(x) for x in current_ver.split(".")]

            # Pad to same length
            max_len = max(len(new_parts), len(current_parts))
            new_parts += [0] * (max_len - len(new_parts))
            current_parts += [0] * (max_len - len(current_parts))

            return new_parts > current_parts
        except ValueError as e:
            import logging

            logging.warning(
                f"Invalid version format: {new_ver} vs {current_ver}: {e}"
            )
            return False


class AutoUpdater:
    """Handles automatic updates from Dropbox deploy location"""

    def __init__(
        self,
        parent_widget=None,
        dropbox_path: str = None,
        on_update_available: Callable[[dict], None] | None = None,
    ) -> None:
        self.parent = parent_widget
        self.deploy_path = dropbox_path or DROPBOX_DEPLOY
        self.update_checker = None
        self.on_update_available = on_update_available
        self.latest_update_info: dict | None = None
        self._passive_mode = False

    def check_for_updates(self, silent: bool = False, passive: bool = False) -> None:
        """
        Check for updates in background

        Args:
            silent: If True, don't show "no updates" message
            passive: If True, do not show update popup automatically
        """
        self._passive_mode = bool(passive)
        self.update_checker = UpdateChecker(self.deploy_path, silent=silent)
        self.update_checker.update_available.connect(self._on_update_available)
        self.update_checker.no_update.connect(
            lambda: self._on_no_update(silent)
        )
        self.update_checker.error_occurred.connect(self._on_error)
        self.update_checker.start()

    def _on_update_available(self, update_info: dict) -> None:
        """Handle when update is available"""
        self.latest_update_info = dict(update_info or {})

        if self._passive_mode:
            if callable(self.on_update_available):
                try:
                    self.on_update_available(self.latest_update_info)
                except Exception:
                    import logging

                    logging.exception("Passive update callback failed")
            return

        version = update_info["version"]
        changelog = update_info["changelog"]
        mandatory = update_info["mandatory"]

        # Build message
        message = f"<h3>Update Available: Version {version}</h3>"
        message += f"<p>Current version: {APP_VERSION}</p>"
        release_date = update_info.get("release_date", "Unknown")
        message += f"<p>Released: {release_date}</p>"

        if changelog:
            message += "<p><b>What's New:</b></p><ul>"
            for item in changelog[:5]:  # Show first 5 items
                message += f"<li>{item}</li>"
            message += "</ul>"

        file_size = update_info.get("file_size", 0)
        message += f"<p>Download size: {file_size} MB</p>"

        if mandatory:
            message += (
                "<p><b style='color: red;'>This is a mandatory update.</b></p>"
            )

        # Show dialog
        msg_box = QMessageBox(self.parent)
        msg_box.setWindowTitle("Update Available")
        msg_box.setTextFormat(Qt.TextFormat.RichText)
        msg_box.setText(message)
        msg_box.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        msg_box.setDefaultButton(QMessageBox.StandardButton.Yes)
        msg_box.button(QMessageBox.StandardButton.Yes).setText(
            "Update Now"
        )
        msg_box.button(QMessageBox.StandardButton.No).setText(
            "Remind Me Later" if not mandatory else "Exit"
        )

        result = msg_box.exec()

        if result == QMessageBox.StandardButton.Yes:
            self._download_and_install(update_info)
        elif mandatory:
            # Force exit for mandatory updates
            QMessageBox.critical(
                self.parent,
                "Update Required",
                "This update is mandatory. The application will now exit.",
            )
            sys.exit(0)

    def _on_no_update(self, silent: bool) -> None:
        """Handle when no update is available"""
        if not silent:
            QMessageBox.information(
                self.parent,
                "Up to Date",
                f"You're running the latest version ({APP_VERSION}).",
            )

    def _on_error(self, error_msg: str) -> None:
        """Handle update check errors — silent if this was a background check."""
        silent = (
            self.update_checker is not None
            and getattr(self.update_checker, 'silent', False)
        )
        if silent:
            import logging
            logging.warning("Auto-update check failed (silent): %s", error_msg)
            return
        QMessageBox.warning(self.parent, "Update Check Failed", error_msg)

    def _download_and_install(self, update_info: dict) -> None:
        """Launch installer entrypoint from Dropbox payload and exit app."""
        deploy_path = Path(update_info.get("deploy_path") or self.deploy_path)
        if not deploy_path.exists():
            QMessageBox.critical(
                self.parent,
                "Update Error",
                f"Dropbox deploy folder not found:\n{deploy_path}",
            )
            return

        # Determine install root: two levels up from this file
        # (deploy/desktop_app/auto_updater.py  →  install root = deploy/..)
        # On remote machines the app lives at Y:\limo or similar.
        install_root = Path(sys.executable).parent
        # If running from source (python.exe in .venv), go up to workspace root
        if install_root.name.lower() in (".venv", "scripts", "bin"):
            install_root = Path(__file__).resolve().parent.parent

        installer_rel = (update_info.get("installer_path") or "install.bat").strip()
        installer_path = deploy_path / installer_rel

        # Fallbacks for older/newer manifests or payload layouts.
        if not installer_path.exists():
            default_bat = deploy_path / "install.bat"
            dispatcher_ps1 = deploy_path / "update" / "update_dispatcher.ps1"
            if default_bat.exists():
                installer_path = default_bat
            elif dispatcher_ps1.exists():
                installer_path = dispatcher_ps1

        msg = (
            f"A new version ({update_info['version']}) is ready to install.\n\n"
            f"Source: {deploy_path}\n"
            f"Target: {install_root}\n\n"
            "Click Update Now to install and reboot the application."
        )
        result = QMessageBox.question(
            self.parent,
            "Ready to Install",
            msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if result != QMessageBox.StandardButton.Yes:
            return

        if installer_path.exists():
            try:
                installer_suffix = installer_path.suffix.lower()
                if installer_suffix == ".bat":
                    subprocess.Popen(
                        ["cmd.exe", "/c", str(installer_path)],
                        cwd=str(deploy_path),
                    )
                elif installer_suffix == ".ps1":
                    subprocess.Popen(
                        [
                            "powershell.exe",
                            "-NoProfile",
                            "-ExecutionPolicy",
                            "Bypass",
                            "-File",
                            str(installer_path),
                        ],
                        cwd=str(deploy_path),
                    )
                else:
                    subprocess.Popen([str(installer_path)], cwd=str(deploy_path))

                QMessageBox.information(
                    self.parent,
                    "Updater Started",
                    "The updater has been started.\n\n"
                    "This app will now close so files can be updated.",
                )
                sys.exit(0)
            except Exception as e:
                QMessageBox.critical(
                    self.parent,
                    "Update Launch Failed",
                    f"Failed to launch updater automatically:\n{e}\n\n"
                    f"Run manually if needed:\n{installer_path}",
                )
        else:
            QMessageBox.warning(
                self.parent,
                "Installer Not Found",
                "No installer entrypoint was found in deploy payload.\n\n"
                f"Expected: {installer_path}\n"
                f"Deploy folder: {deploy_path}",
            )

    def start_update(self, update_info: dict | None = None) -> bool:
        """Launch update install flow from explicit or cached update info."""
        info = update_info or self.latest_update_info
        if not info:
            QMessageBox.information(
                self.parent,
                "No Update Pending",
                f"You're running the latest version ({APP_VERSION}).",
            )
            return False
        self._download_and_install(info)
        return True

    @staticmethod
    def get_current_version() -> str:
        """Get current application version"""
        return APP_VERSION

    @staticmethod
    def get_build_date() -> str:
        """Get application build date"""
        return APP_BUILD_DATE


def create_sample_manifest() -> None:
    """
    Create a sample update manifest file for OneDrive
    Run this on the deployment/build machine
    """
    manifest = {
        "latest_version": "1.0.1",
        "release_date": "2026-02-01",
        "mandatory": False,
        "installer_path": "v1.0.1/ArrowLimo-1.0.1.exe",
        "file_size_mb": 85,
        "changelog": [
            "Fixed charter payment matching issue",
            "Improved GST calculation accuracy",
            "Added new beverage management features",
            "Performance improvements for large datasets",
            "Security updates",
        ],
        "min_required_version": "1.0.0",
        "notes": "Regular maintenance update",
    }

    output_path = Path(DROPBOX_DEPLOY) / UPDATE_MANIFEST
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"Sample manifest created at: {output_path}")
    print("\nUpdate this file each time you release a new version!")


if __name__ == "__main__":
    # Run this to create initial manifest structure
    create_sample_manifest()
