#define AppName "PhoneXR Companion"
[Setup]
AppId={{AAE0EB75-B7D2-4870-B615-18EB329DCB55}
AppName={#AppName}
AppVersion=0.2.0
AppPublisher=PhoneXR contributors
DefaultDirName={localappdata}\Programs\PhoneXR
DefaultGroupName=PhoneXR
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=installer-dist
OutputBaseFilename=PhoneXR-Companion-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\PhoneXRCompanion.exe
CloseApplications=yes
RestartApplications=no
[Files]
Source: "{#StageDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
[Icons]
Name: "{group}\PhoneXR Companion"; Filename: "{app}\PhoneXRCompanion.exe"; WorkingDir: "{app}"
[Run]
Filename: "{app}\PhoneXRCompanion.exe"; Description: "Open PhoneXR Companion"; Flags: nowait postinstall skipifsilent
