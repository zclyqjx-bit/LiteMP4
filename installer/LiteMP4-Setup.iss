[Setup]
AppId={{B5F7C9D8-6C2D-4F8A-9F6E-1A2B3C4D5E6F}
AppName=轻播 Lite
AppVersion=1.7.0.0
AppVerName=轻播 Lite 1.7
AppPublisher=沂州小帅
AppContact=zclyqjx@163.com
AppComments=轻量多格式视频播放器
DefaultDirName={userappdata}\LiteMP4
DefaultGroupName=轻播 Lite
OutputDir=..\dist
OutputBaseFilename=LiteMP4-Setup-v1.7
SetupIconFile=..\assets\LitePlayer.ico
LicenseFile=..\LICENSE.txt
InfoBeforeFile=README.txt
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
UsePreviousAppDir=no
DisableProgramGroupPage=yes
DisableReadyPage=no
DisableFinishedPage=no
ShowLanguageDialog=no
WizardStyle=modern
UninstallDisplayName=轻播 Lite
UninstallDisplayIcon={app}\LiteMP4.exe
CreateUninstallRegKey=yes
Uninstallable=yes
CloseApplications=yes
Compression=lzma2
SolidCompression=yes
VersionInfoVersion=1.7.0.0
VersionInfoCompany=沂州小帅
VersionInfoDescription=轻播 Lite 安装程序
VersionInfoCopyright=Copyright (C) 2026 沂州小帅
ChangesAssociations=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
Source: "..\dist\LiteMP4.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\dist\runtime\*"; DestDir: "{app}\runtime"; Flags: recursesubdirs createallsubdirs ignoreversion
Source: "..\README.md"; DestDir: "{app}\README.md"; Flags: ignoreversion
Source: "..\THIRD_PARTY_NOTICES.md"; DestDir: "{app}\THIRD_PARTY_NOTICES.md"; Flags: ignoreversion
Source: "..\LICENSE.txt"; DestDir: "{app}\LICENSE.txt"; Flags: ignoreversion

[Icons]
Name: "{userprograms}\轻播 Lite"; Filename: "{app}\LiteMP4.exe"; WorkingDir: "{app}"; IconFilename: "{app}\LiteMP4.exe"; IconIndex: 0
Name: "{userdesktop}\轻播 Lite"; Filename: "{app}\LiteMP4.exe"; WorkingDir: "{app}"; IconFilename: "{app}\LiteMP4.exe"; IconIndex: 0; Tasks: desktopicon
Name: "{userprograms}\卸载 轻播 Lite"; Filename: "{uninstallexe}"

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加任务"
Name: "mp4association"; Description: "将 .mp4 和 .m4v 文件关联到轻播 Lite"; GroupDescription: "附加任务"; Flags: unchecked

[Registry]
Root: HKCU; Subkey: "Software\Classes\.mp4"; ValueType: string; ValueName: ""; ValueData: "LiteMP4.Video"; Flags: uninsdeletevalue; Tasks: mp4association
Root: HKCU; Subkey: "Software\Classes\.m4v"; ValueType: string; ValueName: ""; ValueData: "LiteMP4.Video"; Flags: uninsdeletevalue; Tasks: mp4association
Root: HKCU; Subkey: "Software\Classes\LiteMP4.Video"; ValueType: string; ValueName: ""; ValueData: "轻播视频文件"; Flags: uninsdeletekey; Tasks: mp4association
Root: HKCU; Subkey: "Software\Classes\LiteMP4.Video\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\LiteMP4.exe,0"; Flags: uninsdeletevalue; Tasks: mp4association
Root: HKCU; Subkey: "Software\Classes\LiteMP4.Video\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\LiteMP4.exe"" ""%1"""; Flags: uninsdeletevalue; Tasks: mp4association

[Run]
Filename: "{app}\LiteMP4.exe"; Description: "启动轻播 Lite"; Flags: nowait postinstall skipifsilent
