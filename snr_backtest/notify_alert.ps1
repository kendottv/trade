param(
    [Parameter(Mandatory = $true)][string]$Title,
    [Parameter(Mandatory = $true)][string]$Body
)
$ErrorActionPreference = "Stop"

function Escape-Xml([string]$s) {
    if ($null -eq $s) { return "" }
    return ($s -replace "&", "&amp;" -replace "<", "&lt;" -replace ">", "&gt;" -replace '"', "&quot;")
}

$aumid = "TW.Paper.Alert"
$reg = "HKCU:\Software\Classes\AppUserModelId\$aumid"
if (-not (Test-Path $reg)) {
    New-Item -Path $reg -Force | Out-Null
}
New-ItemProperty -Path $reg -Name DisplayName -Value "TW Paper Alert" -PropertyType String -Force | Out-Null

$null = [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime]
$null = [Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom, ContentType = WindowsRuntime]

$xmlText = @"
<toast duration="long">
  <visual>
    <binding template="ToastGeneric">
      <text>$(Escape-Xml $Title)</text>
      <text>$(Escape-Xml $Body)</text>
    </binding>
  </visual>
  <audio src="ms-winsoundevent:Notification.Default" />
</toast>
"@

$xml = New-Object Windows.Data.Xml.Dom.XmlDocument
$xml.LoadXml($xmlText)
$toast = [Windows.UI.Notifications.ToastNotification]::new($xml)
$toast.ExpirationTime = [DateTimeOffset]::Now.AddHours(12)

try {
    $notifier = [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($aumid)
    $notifier.Show($toast)
} catch {
    $fallback = "{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe"
    $notifier = [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($fallback)
    $notifier.Show($toast)
}
