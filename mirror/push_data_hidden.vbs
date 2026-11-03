Set sh = CreateObject("WScript.Shell")
sh.Run "powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File ""C:\Users\AUSER\Desktop\trade\mirror\push_mirror.ps1"" -Mode data", 0, True
