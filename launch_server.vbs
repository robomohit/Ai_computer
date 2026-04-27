Set objShell = CreateObject("WScript.Shell")
Set objFSO = CreateObject("Scripting.FileSystemObject")

strPath = objFSO.GetParentFolderName(WScript.ScriptFullName)
strBatFile = objFSO.BuildPath(strPath, "START_SERVER.bat")

objShell.Run strBatFile, 1, False
