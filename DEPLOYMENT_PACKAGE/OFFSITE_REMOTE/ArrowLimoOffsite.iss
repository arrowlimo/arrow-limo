#include "BuildVersion.iss.inc"

[Setup]
AppId={{D19F42F6-58B4-4D5B-8D1A-4F4F5B34D4A3}
AppName=Arrow Limo Offsite
AppVersion={#AppVersion}
AppPublisher=Arrow Limousine
DefaultDirName={autopf}\ArrowLimoOffsite
DefaultGroupName=Arrow Limo Offsite
AllowNoIcons=no
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir={#OutputDir}
OutputBaseFilename={#OutputBaseFilename}
UninstallDisplayIcon={app}\START_ARROW_LIMO_OFFSITE.bat

[Files]
Source: "{#StageDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Dirs]
Name: "{commonappdata}\ArrowLimoOffsite"
Name: "{commonappdata}\ArrowLimoOffsite\RemoteFiles"
Name: "{commonappdata}\ArrowLimoOffsite\Logs"
Name: "{commonappdata}\ArrowLimoOffsite\Updates"

[Icons]
Name: "{group}\Arrow Limo Offsite"; Filename: "{app}\START_ARROW_LIMO_OFFSITE.bat"; WorkingDir: "{app}"
Name: "{autodesktop}\Arrow Limo Offsite"; Filename: "{app}\START_ARROW_LIMO_OFFSITE.bat"; WorkingDir: "{app}"

[Run]
Filename: "powershell.exe"; Parameters: "-ExecutionPolicy Bypass -NoProfile -File ""{app}\Bootstrap-Prereqs.ps1"" -InstallRoot ""{app}"""; Flags: runhidden waituntilterminated
Filename: "powershell.exe"; Parameters: "-ExecutionPolicy Bypass -NoProfile -File ""{app}\Configure-OffsiteInstall.ps1"" -InstallRoot ""{app}"""; Flags: runhidden waituntilterminated
Filename: "{app}\START_ARROW_LIMO_OFFSITE.bat"; Description: "Launch Arrow Limo Offsite now"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}\_updates_backup"