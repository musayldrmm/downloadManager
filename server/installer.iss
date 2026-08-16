; mini-IDM kurulum sihirbazi. Inno Setup ile derlenir:
;   "C:\Users\musa\AppData\Local\Programs\Inno Setup 6\ISCC.exe" installer.iss
;
; Admin gerektirmeyen (per-user) bir kuruluma bilerek karar verildi -
; hem daha az supheli davraniyor (UAC yukseltme istemiyor) hem de
; kullanicidan yonetici sifresi istemiyor.

#define MyAppName "mini-IDM"
#define MyAppVersion "0.1.0"
#define MyAppExeName "mini-IDM.exe"

[Setup]
AppId={{B7F2E4A1-9C3D-4E5F-8A1B-6D2C3E4F5A6B}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
PrivilegesRequired=lowest
DisableProgramGroupPage=yes
OutputDir=dist_installer
OutputBaseFilename=mini-IDM-Setup
SetupIconFile=mini_idm\app_icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "turkish"; MessagesFile: "compiler:Languages\Turkish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Masaüstü simgesi oluştur"; GroupDescription: "Ek simgeler:"
Name: "startupicon"; Description: "Windows açılışında otomatik başlat"; GroupDescription: "Ek simgeler:"; Flags: unchecked

[Files]
Source: "dist\mini-IDM\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
Name: "{userstartup}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: startupicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent
