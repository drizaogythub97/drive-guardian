# Drive Guardian — CLAUDE.md

> Este arquivo vai na raiz do repositório e orienta o Claude Code durante toda a codificação.
> Documentos-irmãos: `SPEC.md` (especificação técnica) e `ESTUDO-VIABILIDADE.md` (contexto e justificativas).

## O que é

Backup local contínuo de pastas do Google Drive para um disco físico no Windows. App de bandeja com UI de configuração (PySide6), núcleo headless (CLI), detecção de mudanças via polling da Drive API, download íntegro no tamanho original, alertas no celular via ntfy.

## Regras invioláveis

1. **NUNCA excluir ou sobrescrever destrutivamente arquivos locais.** Política cumulativa: arquivos removidos no Drive permanecem no disco; arquivos modificados movem a versão local anterior para `_versões/<caminho>/<nome>.<timestamp>.<ext>` antes de gravar a nova.
2. **Download atômico sempre:** gravar em `<nome>.part`, validar `md5Checksum` contra o metadado do Drive, só então renomear. Nunca deixar arquivo parcial com nome final.
3. **Custo zero:** nenhuma dependência ou serviço pago. Sem serviços que exijam cartão de crédito. Free tiers permitidos: ntfy.sh, healthchecks.io.
4. **Sem segredos no repositório:** chave da conta de serviço, tokens e config real ficam fora do git (`.gitignore` desde o commit 1). Fornecer `config.example.yaml`.
5. **Idempotência:** qualquer ciclo pode ser repetido sem duplicar downloads. Fonte de verdade: SQLite (ver `SPEC.md`).
6. **Core desacoplado da UI:** `core/` não importa nada de `ui/`. Tudo do core funciona via `cli.py`.

## Stack e convenções

- Python 3.12+, PySide6 (UI), SQLite (estado), `google-api-python-client` + `google-auth` (Drive), `requests` (ntfy/heartbeat), PyInstaller (empacotamento).
- Tipagem estática (`mypy` limpo), `ruff` para lint/format, `pytest` para testes.
- Strings de UI em PT-BR isoladas em módulo próprio (`ui/strings.py`) para futura tradução.
- Logs: arquivo rotativo em `%LOCALAPPDATA%/DriveGuardian/logs/` + eventos persistidos no SQLite para exibição na UI.
- Commits em inglês, curtos, convencionais (`feat:`, `fix:`, `docs:`...).
- README bilíngue: `README.md` (EN) + `README.pt-BR.md`.

## Autenticação (duas estratégias, mesma interface)

- `ServiceAccountAuth` (padrão pessoal): JSON da conta de serviço; a pasta do Drive é compartilhada com o e-mail da SA.
- `UserOAuthAuth` (opção para terceiros): fluxo desktop OAuth; documentar que o app OAuth do usuário deve estar em "Production" para o refresh token não expirar em 7 dias.
- Escopo mínimo: `https://www.googleapis.com/auth/drive.readonly`.

## Tratamento de erros (resumo — detalhes no SPEC.md)

Nível 1 transitório → retry/backoff, só log. Nível 2 degradado → pula, retenta no próximo ciclo, notifica se persistir >24h. Nível 3 crítico (credencial inválida, disco ausente/cheio, config inválida) → notificação ntfy imediata + status vermelho na bandeja. Heartbeat: ping ao healthchecks.io ao fim de cada ciclo bem-sucedido.

## Fases (critérios de aceite no SPEC.md)

0. Fundação: esqueleto, config, SQLite, logging, auth SA, listar pasta no console.
1. MVP headless: reconciliação + fila + download atômico + polling `changes.list` + CLI.
2. Alertas: níveis de erro, ntfy, heartbeat, resumo semanal.
3. UI: bandeja, config, logs, "Verificar agora", startup do Windows.
4. Polimento GitHub: OAuth de usuário, export de Docs nativos, READMEs, PyInstaller, testes.

## Comandos

```bash
ruff check . && mypy core/ ui/ gui.py cli.py && pytest   # gate antes de todo commit
python cli.py sync --dry-run                  # simula sem baixar
python cli.py sync                            # ciclo único
python cli.py watch                           # loop contínuo (intervalo da config)
python cli.py status                          # últimos ciclos e arquivos por status
python cli.py events -n 30                    # log de movimentações (fonte da UI)
python cli.py summary [--send]                # resumo semanal
python cli.py test-alert                      # testa ntfy + heartbeat
python gui.py                                 # abre a interface (bandeja + janela)
```

## Registro de movimentações (decisão do dono, 10/08/2026)

**Toda** movimentação (download, versionamento, falha, arquivo que sumiu do Drive ou
voltou, ciclo executado) tem de ficar registrada no SQLite para aparecer no log da UI.
Nada de movimentação visível só no console: se um caminho de código muda o estado do
backup, ele grava evento em `events` — e ciclos vão para a tabela `cycles`.
