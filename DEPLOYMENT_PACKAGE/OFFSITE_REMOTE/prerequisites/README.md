# Offsite Installer Prerequisites

This folder is staged into the offsite installer and update payload under `prerequisites`.

Expected bundled installers:

- `vc_redist.x64.exe` (Visual C++ Redistributable)

`build_offsite_release.ps1` will automatically download `vc_redist.x64.exe` from Microsoft if it is missing.