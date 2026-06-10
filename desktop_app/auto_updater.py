"""
Auto-Update System for Arrow Limousine Desktop Application
Checks Dropbox deploy location for newer versions using a version stamp file.

Dropbox path: C:\\Users\\info\\Dropbox\\limo_deploy
"""

# Application version — updated by build/publish_to_dropbox.ps1 each release
import json
import os as _os
import subprocess
import sys
from pathlib import Path

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import QMessageBox

_VFILE = _os.path.join(_os.path.dirname(__file__), "..", "version.txt")
try:
    with open(_VFILE) as _vf:
        APP_VERSION = _vf.read().strip() or "1.0.0"
except Exception:
    APP_VERSION = "1.0.0"
APP_BUILD_DATE = "2026-01-31"  # fallback; overwritten by version.txt

# Dropbox deploy configuration (replaces legacy OneDrive path)
DROPBOX_DEPLOY = r"C:\Users\info\Dropbox\limo_deploy"
UPDATE_MANIFEST = "update_manifest.json"


class UpdateChecker(QThread):
    """Background thread to check for updates without blocking UI"""

    update_available = pyqtSignal(dict)  # Emits update info
    no_update = pyqtSignal()
    error_occurred = pyqtSignal(str)

    def __init__(self, dropbox_path: str = None, silent: bool = False) -> None:
        super().__init__()
        self.deploy_path = Path(dropbox_path or DROPBOX_DEPLOY)
        self.silent = silent

    def run(self) -> None:
        """Check for updates in Dropbox deploy location"""
        try:
            manifest_path = self.deploy_path / UPDATE_MANIFEST

            if not manifest_path.exists():
                self.error_occurred.emit(
                    f"Update manifest not found at: {manifest_path}"
                )
                return

            with open(manifest_path, encoding="utf-8-sig") as f:
                raw = f.read().strip()
            if not raw:
                # Dropbox may present an empty placeholder while syncing
                self.error_occurred.emit(
                    "Update manifest is empty (Dropbox still syncing?)")
                return
            manifest = json.loads(raw)

            latest_version = manifest.get("latest_version", "")

            if self._is_newer_version(latest_version, APP_VERSION):
                update_info = {
                    "version": latest_version,
                    "release_date": manifest.get("release_date", ""),
                    "changelog": manifest.get("changelog", []),
                    "installer_path": manifest.get("installer_path", ""),
                    "file_size": manifest.get("file_size_mb", 0),
                    "mandatory": manifest.get("mandatory", False),
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

    def __init__(self, parent_widget=None, dropbox_path: str = None) -> None:
        self.parent = parent_widget
        self.deploy_path = dropbox_path or DROPBOX_DEPLOY
        self.update_checker = None

    def check_for_updates(self, silent: bool = False) -> None:
        """
        Check for updates in background

        Args:
            silent: If True, don't show "no updates" message
        """
        self.update_checker = UpdateChecker(self.deploy_path, silent=silent)
        self.update_checker.update_available.connect(self._on_update_available)
        self.update_checker.no_update.connect(
            lambda: self._on_no_update(silent)
        )
        self.update_checker.error_occurred.connect(self._on_error)
        self.update_checker.start()

    def _on_update_available(self, update_info: dict) -> None:
        """Handle when update is available"""
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
            "Download && Install"
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
        """Apply update by robocopy-ing from the Dropbox deploy folder."""
        deploy_path = Path(self.deploy_path)
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

        msg = (
            f"A new version ({update_info['version']}) is ready to install.\n\n"
            f"Source: {deploy_path}\n"
            f"Target: {install_root}\n\n"
            "The application will restart after updating."
        )
        result = QMessageBox.question(
            self.parent,
            "Ready to Install",
            msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if result != QMessageBox.StandardButton.Yes:
            return

        try:
            # robocopy source dest /E /XO /XD __pycache__ /NFL /NDL /NJH
            proc = subprocess.run(
                [
                    "robocopy",
                    str(deploy_path),
                    str(install_root),
                    "/E",    # recurse including empty dirs
                    "/XO",   # skip older (only copy newer)
                    "/XD", "__pycache__",
                    "/NFL", "/NDL", "/NJH",  # suppress verbose listing
                ],
                capture_output=True,
                text=True,
            )
            # robocopy exit codes 0-7 are success (8+ are errors)
            if proc.returncode >= 8:
                QMessageBox.critical(
                    self.parent,
                    "Update Error",
                    f"Robocopy failed (code {proc.returncode}):\n{proc.stderr or proc.stdout}",
                )
                return

            QMessageBox.information(
                self.parent,
                "Update Complete",
                "Update applied. The application will now restart.",
            )
            # Restart the app
            subprocess.Popen([sys.executable] + sys.argv)
            sys.exit(0)
        except Exception as e:
            QMessageBox.critical(
                self.parent,
                "Installation Error",
                f"Failed to apply update:\n{e!s}",
            )

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

    output_path = Path(ONEDRIVE_BASE) / INSTALLER_FOLDER / UPDATE_MANIFEST
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"Sample manifest created at: {output_path}")
    print("\nUpdate this file each time you release a new version!")


if __name__ == "__main__":
    # Run this to create initial manifest structure
    create_sample_manifest()
