# Consulta Linx

Gera um relatório consolidado de pedidos, faturamento e canais em Excel.

## Estrutura

- `script_consulta.py`: ponto de entrada e coordenação da execução.
- `script_consulta_historico.py`: relatório histórico desde 01/12/2023.
- `consulta_linx/config.py`: credenciais, parâmetros e regras compartilhadas.
- `consulta_linx/database.py`: conexão Firebird e consultas de extração.
- `consulta_linx/transform.py`: normalização, classificação e regras de negócio.
- `consulta_linx/excel.py`: resumo por canal e geração do arquivo Excel.
- `consulta_linx/utils.py`: log, limpeza e normalização de valores.

## Configuração e execução

As configurações são carregadas do `.env`; consulte `.env.example` para ver as opções disponíveis. As credenciais do Firebird são `FB_HOST`, `FB_DATABASE`, `FB_PORT`, `FB_USER`, `FB_PASSWORD` e `FB_CHARSET`. Os parâmetros operacionais incluem `DIAS_JANELA`, `PASTA_SAIDA_EXCEL`, `ARQUIVO_SAIDA`, `ARQUIVO_SAIDA_HISTORICO` e `MODO_COMPATIVEL`. A pasta de relatórios é criada automaticamente. Caminhos absolutos definidos diretamente em `ARQUIVO_SAIDA` ou `ARQUIVO_SAIDA_HISTORICO` têm prioridade sobre `PASTA_SAIDA_EXCEL`.

As execuções aparecem no terminal e são gravadas em `logs/consulta_linx.log`. O arquivo gira ao atingir 5 MB e mantém até cinco cópias anteriores. `ARQUIVO_LOG`, `LOG_MAX_BYTES` e `LOG_BACKUP_COUNT` permitem ajustar isso no `.env`. Logs são excluídos do Git.

Instale as dependências e execute pela raiz do projeto:

```powershell
uv pip install -r requirements.txt
uv run python script_consulta.py
```

O script acima usa a janela recente configurada em `consulta_linx/config.py` e salva em `pedidos_unificado.xlsx`. Para gerar o histórico desde 01/12/2023 até hoje, execute:

```powershell
uv run python script_consulta_historico.py
```

O histórico é salvo em `pedidos_unificado_historico.xlsx`. Esse caminho pode ser alterado pela variável `ARQUIVO_SAIDA_HISTORICO` no `.env`.

## Agendador de Tarefas do Windows

Para a rotina diária, agende `script_consulta.py`; ele usa `DIAS_JANELA`. O script histórico consulta desde 01/12/2023 e normalmente deve ser executado manualmente, pois a extração é mais longa.

Na ação da tarefa, configure:

- **Programa/script:** caminho completo para `.venv\Scripts\python.exe`.
- **Adicionar argumentos:** caminho completo para `script_consulta.py`, entre aspas.
- **Iniciar em:** caminho da pasta do projeto, sem aspas.

Escolha o usuário da tarefa com acesso ao Firebird e à pasta de saída. Para salvar em uma pasta de rede, use um caminho UNC (por exemplo, `\\servidor\relatorios\linx`) e confirme que esse usuário tem permissão de gravação. O arquivo de log fica em `logs/consulta_linx.log`, relativo à pasta do projeto.
