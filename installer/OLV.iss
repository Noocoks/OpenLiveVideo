#define MyAppName "OLV"
#define MyAppVersion "0.4.0"
#define MyAppPublisher "Open Live Video"
#define MyAppExeName "OLV.exe"

[Setup]
AppId={{A5B5D291-39D5-4A52-8B8E-0A0200000001}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\OLV
DefaultGroupName=OLV
LicenseFile=..\LICENSE
DisableDirPage=no
OutputDir=..\dist\installer
OutputBaseFilename=OLV-Setup-0.4.0
ArchitecturesInstallIn64BitMode=x64
PrivilegesRequired=lowest
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\OLV.exe

[Files]
Source: "..\dist\OLV\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{group}\OLV"; Filename: "{app}\OLV.exe"
Name: "{autodesktop}\OLV"; Filename: "{app}\OLV.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Crear acceso directo en el escritorio"; GroupDescription: "Accesos directos:"

[Run]
Filename: "{app}\OLV.exe"; Description: "Abrir OLV"; Flags: postinstall nowait skipifsilent
