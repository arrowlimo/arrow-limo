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
UninstallDisplayIcon={cmd}

[Files]
Source: "{#StageDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Dirs]
Name: "{commonappdata}\ArrowLimoOffsite"

[Icons]
Name: "{group}\Arrow Limo Offsite"; Filename: "{cmd}"; Parameters: "/c ""{app}\START_ARROW_LIMO_OFFSITE.bat"""; WorkingDir: "{app}"; IconFilename: "{app}\START_ARROW_LIMO_OFFSITE.bat"
Name: "{autodesktop}\Arrow Limo Offsite"; Filename: "{cmd}"; Parameters: "/c ""{app}\START_ARROW_LIMO_OFFSITE.bat"""; WorkingDir: "{app}"; IconFilename: "{app}\START_ARROW_LIMO_OFFSITE.bat"

[Run]
Filename: "powershell.exe"; Parameters: "-ExecutionPolicy Bypass -NoProfile -File ""{app}\Bootstrap-Prereqs.ps1"" -InstallRoot ""{app}"""; Flags: runhidden waituntilterminated
Filename: "powershell.exe"; Parameters: "-ExecutionPolicy Bypass -NoProfile -File ""{app}\Configure-OffsiteInstall.ps1"" -InstallRoot ""{app}"" -DataRoot ""{code:GetDataRoot}"""; Flags: runhidden waituntilterminated
Filename: "{app}\START_ARROW_LIMO_OFFSITE.bat"; Description: "Launch Arrow Limo Offsite now"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}\_updates_backup"

[Code]
var
  DataDirPage: TInputDirWizardPage;

procedure InitializeWizard();
begin
  DataDirPage := CreateInputDirPage(
    wpSelectDir,
    'Select Data Storage Folder',
    'Where should Arrow Limo Offsite store reports, receipts and photos?',
    'The installer will create the following subfolders here:'#13#10 +
    '  - Reports'#13#10 +
    '  - Receipts'#13#10 +
    '  - Photos'#13#10 +
    '  - Logs'#13#10 +
    '  - Updates'#13#10#13#10 +
    'Choose a folder on a local drive (e.g. C:\ArrowLimoData).',
    False,
    '');
  DataDirPage.Add('');
  DataDirPage.Values[0] := ExpandConstant('{commonappdata}\ArrowLimoOffsite\Data');
end;

function GetDataRoot(Param: String): String;
begin
  Result := DataDirPage.Values[0];
end;

function NextButtonClick(CurPageID: Integer): Boolean;
var
  DataRoot: String;
begin
  Result := True;
  if CurPageID = DataDirPage.ID then
  begin
    DataRoot := DataDirPage.Values[0];
    if DataRoot = '' then
    begin
      MsgBox('Please select a data storage folder.', mbError, MB_OK);
      Result := False;
      Exit;
    end;
    if not ForceDirectories(DataRoot) then
    begin
      MsgBox('Cannot create the folder: ' + DataRoot + #13#10 +
             'Please choose a different location.', mbError, MB_OK);
      Result := False;
      Exit;
    end;
  end;
end;