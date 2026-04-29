# Arrow Limo Offsite Installer

This folder contains the offsite one-PC deployment pipeline for the Arrow Limo desktop application.

It is separate from the existing LAN and dispatch-main installer flow in `DEPLOYMENT_PACKAGE`.

## What it builds

- A private offsite installer payload with:
  - the desktop application
  - bundled Python runtime from `.venv`
  - prerequisite bootstrap for system runtime checks/install
  - support folders for backend and frontend assets
  - Neon cloud configuration as the default database target
  - a post-install configuration step that creates local file/cache/update folders
- A separate update package that can be sent later and applied over the existing install.

## Important security note

The generated offsite release uses the Neon deployment credentials currently stored in `.env.neon`.

Treat the generated installer and update packages as private internal deployment artifacts.

## Files

- `build_offsite_release.ps1`
  - stages the application/runtime and optionally compiles the installer with Inno Setup
- `build_offsite_update.ps1`
  - creates an update payload zip for later deployments
- `ArrowLimoOffsite.iss`
  - Inno Setup script for a Microsoft-style installer experience
- `runtime\Configure-OffsiteInstall.ps1`
  - writes the installed `.env`, workstation id, and local support paths
- `runtime\Bootstrap-Prereqs.ps1`
  - enforces/support-installs required machine prerequisites before first launch
- `runtime\Apply-OffsiteUpdate.ps1`
  - applies a shipped update payload onto an installed machine
## Prerequisites handled by bootstrap

Current bootstrap checks/install behavior:

- Verifies Administrator context.
- Verifies 64-bit Windows.
- Verifies bundled Python runtime exists in install folder.
- Verifies Visual C++ runtime availability required by many Python native wheels.
- Runs bundled `prerequisites\vc_redist.x64.exe` silently when VC++ runtime is missing.
- Fails installation/update with a clear message if prerequisites remain unmet after install attempt.

`build_offsite_release.ps1` automatically downloads `vc_redist.x64.exe` into `prerequisites` during release build if it is not already present.

- `runtime\START_ARROW_LIMO_OFFSITE.bat`
  - installed launcher shortcut target
- `runtime\launcher.py`
  - installed Python launcher entrypoint

## Build the installer payload

Run from the repo root in an elevated PowerShell session:

```powershell
Set-Location L:\limo
PowerShell -ExecutionPolicy Bypass -File .\DEPLOYMENT_PACKAGE\OFFSITE_REMOTE\build_offsite_release.ps1
```

To compile the `.exe` installer as well, install Inno Setup 6 and run:

```powershell
Set-Location L:\limo
PowerShell -ExecutionPolicy Bypass -File .\DEPLOYMENT_PACKAGE\OFFSITE_REMOTE\build_offsite_release.ps1 -CompileInstaller
```

## Build an update package

```powershell
Set-Location L:\limo
PowerShell -ExecutionPolicy Bypass -File .\DEPLOYMENT_PACKAGE\OFFSITE_REMOTE\build_offsite_update.ps1
```

## Install on the dispatcher PC

Preferred path:

1. Build the installer on the source machine.
2. Send the generated installer from `DEPLOYMENT_PACKAGE\OFFSITE_REMOTE\build\output`.
3. Run the installer as Administrator on the offsite PC.
4. Launch `Arrow Limo Offsite` from the desktop or Start menu.

Fallback path if Inno Setup is not available:

1. Send the staged folder zip from `DEPLOYMENT_PACKAGE\OFFSITE_REMOTE\build\output`.
2. Extract it to a local folder.
3. Run `Configure-OffsiteInstall.ps1` as Administrator.
4. Launch `START_ARROW_LIMO_OFFSITE.bat`.

## Install location

The installer defaults to:

- App: `C:\Program Files\ArrowLimoOffsite`
- Local data and file cache: `C:\ProgramData\ArrowLimoOffsite`

## Update flow

1. Build the update zip with `build_offsite_update.ps1`.
2. Send the zip to the dispatcher.
3. Extract it locally.
4. Run `Apply-OffsiteUpdate.ps1` as Administrator.

The updater preserves the installed `.env` and local data folders.