<#
    criar_tarefas.ps1 - Cria as tarefas agendadas da Consulta Linx

    Tarefas criadas (pasta "ConsultaLinx" no Agendador de Tarefas):
      - Consulta Linx - Diaria    : script_consulta.py, 3x ao dia
      - Consulta Linx - Historico : script_consulta_historico.py, 1x por mes

    Uso (PowerShell aberto na pasta do projeto):
      powershell -ExecutionPolicy Bypass -File .\criar_tarefas.ps1

    Opções:
      -HorariosConsulta "07:00","12:00","17:00"
      -DiaHistorico 1 -HorarioHistorico "06:00"
      -SomenteQuandoLogado   (não pede senha, mas só roda com você logado)

    Rodar o script de novo substitui as tarefas com as novas configurações.
#>
param(
    [string[]]$HorariosConsulta = @("07:00", "12:00", "17:00"),
    [ValidateRange(1, 28)][int]$DiaHistorico = 1,
    [string]$HorarioHistorico = "06:00",
    [switch]$SomenteQuandoLogado
)

$ErrorActionPreference = "Stop"
$pasta = $PSScriptRoot
$pastaTarefas = "\ConsultaLinx\"
$usuario = "$env:USERDOMAIN\$env:USERNAME"

# ---------------------------------------------------------------- conferências
$obrigatorios = @(
    "executar_consulta.bat",
    "executar_historico.bat",
    "script_consulta.py",
    "script_consulta_historico.py",
    ".venv\Scripts\python.exe",
    ".env"
)
foreach ($item in $obrigatorios) {
    if (-not (Test-Path (Join-Path $pasta $item))) {
        throw "Não encontrei '$item' em $pasta. Rode este script na pasta do projeto."
    }
}
if ($pasta.StartsWith("\\")) {
    Write-Warning "O projeto está numa pasta de rede. Prefira uma pasta local (ex.: C:\python_consulta_linx)."
}

# ---------------------------------------------------------------- montagem do XML
function Escapar([string]$texto) { [System.Security.SecurityElement]::Escape($texto) }

function Hora([string]$hhmm) {
    $h = [datetime]::ParseExact($hhmm, "HH:mm", $null)
    return (Get-Date).Date.AddHours($h.Hour).AddMinutes($h.Minute).ToString("yyyy-MM-ddTHH:mm:ss")
}

function Montar-Xml([string]$descricao, [string]$gatilhos, [string]$bat, [string]$limite) {
    $logon = if ($SomenteQuandoLogado) { "InteractiveToken" } else { "Password" }
    return @"
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>$(Escapar $descricao)</Description>
  </RegistrationInfo>
  <Triggers>
$gatilhos
  </Triggers>
  <Principals>
    <Principal id="Author">
      <UserId>$(Escapar $usuario)</UserId>
      <LogonType>$logon</LogonType>
      <RunLevel>LeastPrivilege</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <StartWhenAvailable>true</StartWhenAvailable>
    <RunOnlyIfNetworkAvailable>true</RunOnlyIfNetworkAvailable>
    <ExecutionTimeLimit>$limite</ExecutionTimeLimit>
    <Enabled>true</Enabled>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>$(Escapar (Join-Path $pasta $bat))</Command>
      <WorkingDirectory>$(Escapar $pasta)</WorkingDirectory>
    </Exec>
  </Actions>
</Task>
"@
}

$gatilhosDiarios = ($HorariosConsulta | ForEach-Object {
@"
    <CalendarTrigger>
      <StartBoundary>$(Hora $_)</StartBoundary>
      <Enabled>true</Enabled>
      <ScheduleByDay><DaysInterval>1</DaysInterval></ScheduleByDay>
    </CalendarTrigger>
"@
}) -join "`n"

$meses = "<January/><February/><March/><April/><May/><June/><July/><August/><September/><October/><November/><December/>"
$gatilhoMensal = @"
    <CalendarTrigger>
      <StartBoundary>$(Hora $HorarioHistorico)</StartBoundary>
      <Enabled>true</Enabled>
      <ScheduleByMonth>
        <DaysOfMonth><Day>$DiaHistorico</Day></DaysOfMonth>
        <Months>$meses</Months>
      </ScheduleByMonth>
    </CalendarTrigger>
"@

$tarefas = @(
    @{
        Nome = "Consulta Linx - Diaria"
        Xml  = Montar-Xml "Atualiza pedidos_unificado.xlsx (janela recente)" $gatilhosDiarios "executar_consulta.bat" "PT1H"
    },
    @{
        Nome = "Consulta Linx - Historico"
        Xml  = Montar-Xml "Atualiza pedidos_unificado_historico.xlsx (desde 01/12/2023)" $gatilhoMensal "executar_historico.bat" "PT4H"
    }
)

# ---------------------------------------------------------------- registro
$senha = $null
if (-not $SomenteQuandoLogado) {
    $cred = Get-Credential -UserName $usuario -Message "Senha do Windows de $usuario (para rodar mesmo sem ninguém logado)"
    $senha = $cred.GetNetworkCredential().Password
}

foreach ($t in $tarefas) {
    if ($SomenteQuandoLogado) {
        Register-ScheduledTask -TaskPath $pastaTarefas -TaskName $t.Nome -Xml $t.Xml -Force | Out-Null
    } else {
        Register-ScheduledTask -TaskPath $pastaTarefas -TaskName $t.Nome -Xml $t.Xml `
            -User $usuario -Password $senha -Force | Out-Null
    }
    Write-Host "OK: $pastaTarefas$($t.Nome)" -ForegroundColor Green
}
$senha = $null

Write-Host ""
Write-Host "Consulta diária : $($HorariosConsulta -join ', ')"
Write-Host "Histórico       : todo dia $DiaHistorico às $HorarioHistorico"
Write-Host ""
Write-Host "Para testar agora:"
Write-Host "  Start-ScheduledTask -TaskPath '$pastaTarefas' -TaskName 'Consulta Linx - Diaria'"
Write-Host "Para ver o resultado (0 = sucesso):"
Write-Host "  Get-ScheduledTask -TaskPath '$pastaTarefas' | Get-ScheduledTaskInfo | Select TaskName, LastRunTime, LastTaskResult, NextRunTime"
