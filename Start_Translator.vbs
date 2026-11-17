Set WshShell = CreateObject("WScript.Shell")
Set FileSystem = CreateObject("Scripting.FileSystemObject")
ProgramDir = FileSystem.GetParentFolderName(WScript.ScriptFullName)
WshShell.CurrentDirectory = ProgramDir
PythonExe = WshShell.ExpandEnvironmentStrings("%LOCALAPPDATA%\Programs\Python\Python313\pythonw.exe")
If Not FileSystem.FileExists(PythonExe) Then PythonExe = "pythonw.exe"
WshShell.Run Chr(34) & PythonExe & Chr(34) & " " & Chr(34) & ProgramDir & "\app.py" & Chr(34), 0, False
