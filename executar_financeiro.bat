@echo off
REM Executa script_financeiro.py pelo Agendador de Tarefas (ou com duplo clique).
REM O log normal fica em logs\consulta_linx.log. Aqui so vao erros que
REM acontecem antes do log do Python existir (venv quebrado, import falhando etc.).
setlocal
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
if not exist logs mkdir logs

if not exist ".venv\Scripts\python.exe" (
    echo [%date% %time%] ERRO: .venv\Scripts\python.exe nao encontrado >> logs\erros_agendador.log
    exit /b 9
)

".venv\Scripts\python.exe" script_financeiro.py > nul 2>> logs\erros_agendador.log
set RC=%ERRORLEVEL%
if not "%RC%"=="0" echo [%date% %time%] script_financeiro.py terminou com codigo %RC% >> logs\erros_agendador.log
exit /b %RC%
