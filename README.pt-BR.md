# Drive Guardian

> 🇬🇧 [English version](README.md)

Backup local contínuo de pastas do Google Drive para um disco físico no Windows.
App de bandeja com UI de configuração (PySide6) sobre um núcleo headless (CLI),
detecção de mudanças via polling da Drive API, download íntegro no tamanho
original e alertas no celular via ntfy.

**Princípios:** nunca excluir ou sobrescrever arquivos locais de forma destrutiva
(política cumulativa), download sempre atômico (validado por md5), zero
dependências pagas e nenhum segredo no repositório. Ver [`CLAUDE.md`](CLAUDE.md)
e [`SPEC.md`](SPEC.md).

## Status

Em desenvolvimento, entrega por fases:

- **Fase 0 — Fundação ✅** — esqueleto, config, estado SQLite, logging, auth por
  conta de serviço, `python cli.py list` imprime a árvore da pasta do Drive.
- **Fase 1 — MVP headless ✅** — reconciliação completa, fila de download, download
  atômico (`.part` → md5 → rename) com retomada via Range, `_versões/` para
  modificados, polling incremental `changes.list` e CLI `sync` / `watch` / `--dry-run`.
- **Fase 2 — Alertas ✅** — três níveis de erro com retry/backoff para transitórios,
  alerta ntfy imediato nos críticos (com anti-spam), heartbeat (healthchecks.io),
  resumo semanal e **toda movimentação registrada** no SQLite — inclusive arquivos
  que sumiram do Drive, cuja cópia local é sempre mantida.
- **Fase 3 — UI ✅** — bandeja com três estados, janela de configuração com as quatro
  abas (Conexão, Pastas, Parâmetros, Atividade), navegador de pastas do Drive, log de
  atividade com filtro e exportação, "Verificar agora" e iniciar com o Windows.
- **Fase 4 — Polimento GitHub** — OAuth de usuário, export de Docs nativos, READMEs, PyInstaller, testes.

## Início rápido (desenvolvedores)

Requer Python 3.12+.

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows
pip install -e ".[dev]"

copy config.example.yaml config.yaml   # depois edite
python cli.py list                      # imprime a árvore da pasta monitorada
```

### CLI

```bash
python cli.py sync --dry-run   # simula: não baixa nem grava nada
python cli.py sync             # um ciclo completo
python cli.py watch            # loop contínuo no intervalo da config
python cli.py status           # últimos ciclos, arquivos por status, alertas
python cli.py events -n 30     # log de movimentações (mesma fonte da futura UI)
python cli.py summary [--send] # resumo semanal, opcionalmente enviado pelo ntfy
python cli.py test-alert       # teste ponta a ponta do ntfy + heartbeat
```

### Interface

```bash
pip install -e ".[ui]"   # PySide6
python gui.py            # ícone na bandeja + janela de configuração
```

O app vive na bandeja: fechar a janela não para o backup. Para encerrar de verdade,
use "Sair" no menu da bandeja.

### Configuração

Copie `config.example.yaml` para `config.yaml` (fora do git) e informe o ID da
pasta do Drive, o caminho da chave da conta de serviço e as notificações.
Referência completa: [`SPEC.md` §1](SPEC.md).

**Conta de serviço:** crie uma conta de serviço no Google Cloud Console, baixe o
JSON para `secrets/sa-key.json` e compartilhe a pasta do Drive com o e-mail da
conta de serviço (papel Leitor).

## Desenvolvimento

```bash
ruff check . && mypy core/ && pytest   # gate antes de todo commit
```

## Licença

[MIT](LICENSE)
