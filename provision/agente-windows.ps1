Param([string]$ServerIp = "192.168.56.30", [string]$AgentHostname = "zbx-winserver")
$ErrorActionPreference = "Stop"

$AgentVersion = "6.0.35"
$Msi = "zabbix_agent2-$AgentVersion-windows-amd64-openssl.msi"
$Url = "https://cdn.zabbix.com/zabbix/binaries/stable/6.0/$AgentVersion/$Msi"
$Dst = "C:\Windows\Temp\$Msi"
$SvcName = "Zabbix Agent 2"

if (Get-Service $SvcName -ErrorAction SilentlyContinue) {
  Write-Host "[zbx-agent] $SvcName ya instalado; no reinstalo."
}
else {
  Write-Host "[zbx-agent] Descargando $Msi ..."
  Import-Module BitsTransfer
  Start-BitsTransfer -Source $Url -Destination $Dst

  Write-Host "[zbx-agent] Instalando (Server=$ServerIp, Hostname=$AgentHostname) ..."
  $log = "C:\Windows\Temp\zbxagent-install.log"
  $msiArgs = "/i `"$Dst`" /qn /norestart /l*v `"$log`" SERVER=$ServerIp SERVERACTIVE=$ServerIp HOSTNAME=$AgentHostname ENABLEPATH=1"
  $p = Start-Process msiexec.exe -ArgumentList $msiArgs -Wait -PassThru
  if ($p.ExitCode -ne 0) { throw "msiexec fallo con codigo $($p.ExitCode). Revisa $log" }
}

if (-not (Get-NetFirewallRule -DisplayName "Zabbix Agent 2 (10050)" -ErrorAction SilentlyContinue)) {
  New-NetFirewallRule -DisplayName "Zabbix Agent 2 (10050)" -Direction Inbound `
    -Protocol TCP -LocalPort 10050 -Action Allow | Out-Null
  Write-Host "[zbx-agent] Regla de firewall creada (TCP 10050 entrante)."
}

Set-Service $SvcName -StartupType Automatic
if ((Get-Service $SvcName).Status -ne "Running") { Start-Service $SvcName }

$svc = Get-Service $SvcName
Write-Host "[zbx-agent] Servicio '$SvcName': $($svc.Status)"
if ($svc.Status -ne "Running") { throw "El servicio $SvcName no esta corriendo." }
Write-Host "[zbx-agent] Listo. Apuntando a $ServerIp; se reporta como '$AgentHostname'."
Write-Host "[zbx-agent] Da de alta el host:  cd scripts; python alta_hosts.py; python monitorizacion.py"
