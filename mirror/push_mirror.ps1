# Push a secret-free snapshot of trade + trade_NN to the 3090 via Taildrop. View-only mirror; never includes keys.
param([ValidateSet('data','code')][string]$Mode='data')
$ErrorActionPreference='Continue'
$D='C:\Users\AUSER\Desktop'; $S="$env:TEMP\trade_mirror_stage_$Mode"; $Z="$env:TEMP\trade_mirror_$Mode.zip"
$TS='C:\Program Files\Tailscale\tailscale.exe'; $LOG="$D\trade\mirror\push.log"
$XF=@('.env','.env.*','*.env','broker_secrets.json','*secret*','*.pem','*.key','*.pfx','*.p12','*.crt','*.cer','*.lock','shioaji.log','_dash_err.txt','_dash_out.txt','webapp_console.log','*.bak*')
$XD=@('.venv','venv','.git','__pycache__','node_modules')
if(Test-Path $S){Remove-Item $S -Recurse -Force}
function rc($src,$dst,$extra){ & robocopy $src $dst /E /R:1 /W:1 /NFL /NDL /NJH /NJS /NP /XD @XD /XF @XF @extra | Out-Null }
if($Mode -eq 'data'){
  rc "$D\trade\snr_backtest\paper" "$S\trade\snr_backtest\paper" @('/XD','replay*','backup*')
  rc "$D\trade\snr_backtest\paper_nn" "$S\trade\snr_backtest\paper_nn" @()
  rc "$D\trade_NN\out" "$S\trade_NN\out" @()
  rc "$D\trade_NN\data" "$S\trade_NN\data" @()
  rc "$D\trade_NN\paper" "$S\trade_NN\paper" @()
} else {
  rc "$D\trade" "$S\trade" @('/XD',"$D\trade\mirror")
  rc "$D\trade_NN" "$S\trade_NN" @()
}
# belt and braces: drop anything secret-looking that slipped through
Get-ChildItem $S -Recurse -Force -File | ? { $_.Name -match '(^\.env|secret|\.pem$|\.key$|\.pfx$|\.p12$)' } | Remove-Item -Force
if(Test-Path $Z){Remove-Item $Z -Force}
Compress-Archive -Path "$S\*" -DestinationPath $Z -CompressionLevel Optimal
& $TS file cp $Z desktop-im41nrb: 2>&1 | Out-Null
"$(Get-Date -f s) $Mode rc=$LASTEXITCODE size=$((Get-Item $Z).Length)" | Add-Content $LOG
Remove-Item $S -Recurse -Force
