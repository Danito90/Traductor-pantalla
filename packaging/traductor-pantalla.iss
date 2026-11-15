[Setup]
AppId=TraductorPantalla
AppName=Traductor de pantalla
AppVersion=0.1.0
DefaultDirName={autopf}\Traductor de pantalla
DefaultGroupName=Traductor de pantalla
DisableProgramGroupPage=yes
UninstallDisplayIcon={app}\TraductorPantalla.exe
ArchitecturesAllowed=x64os
ArchitecturesInstallIn64BitMode=x64os
MinVersion=10.0.22000
PrivilegesRequired=admin
OutputDir=..\dist
OutputBaseFilename=TraductorPantalla-Setup-x64
Compression=lzma2
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Files]
Source: "..\dist\TraductorPantalla\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\build\VC_redist.x64.exe"; Flags: dontcopy

[Icons]
Name: "{group}\Traductor de pantalla"; Filename: "{app}\TraductorPantalla.exe"

[Run]
Filename: "{app}\TraductorPantalla.exe"; Description: "Abrir Traductor de pantalla"; Flags: postinstall nowait skipifsilent runasoriginaluser

[Code]
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  RunKey, Command: String;
begin
  if CurUninstallStep = usUninstall then
  begin
    RunKey := 'Software\Microsoft\Windows\CurrentVersion\Run';
    if RegQueryStringValue(HKCU, RunKey, 'TraductorPantalla', Command) then
      if CompareText(Command, '"' + ExpandConstant('{app}\TraductorPantalla.exe') + '"') = 0 then
        RegDeleteValue(HKCU, RunKey, 'TraductorPantalla');
  end;
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  ExitCode: Integer;
begin
  Result := '';
  ExtractTemporaryFile('VC_redist.x64.exe');
  if not Exec(ExpandConstant('{tmp}\VC_redist.x64.exe'), '/install /quiet /norestart', '',
    SW_HIDE, ewWaitUntilTerminated, ExitCode) then
    Result := 'No se pudo ejecutar Microsoft Visual C++ Redistributable. Código: ' + IntToStr(ExitCode)
  else if ExitCode = 3010 then
    NeedsRestart := True
  else if (ExitCode <> 0) and (ExitCode <> 1638) then
    Result := 'No se pudo instalar Microsoft Visual C++ Redistributable. Código: ' + IntToStr(ExitCode);
end;
