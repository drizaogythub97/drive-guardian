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
- **Fase 1 — MVP headless** — reconciliação, fila, download atômico, polling
  incremental (`changes.list`), CLI.
- **Fase 2 — Alertas** — níveis de erro, ntfy, heartbeat (healthchecks.io), resumo semanal.
- **Fase 3 — UI** — bandeja, janela de config, logs, "Verificar agora", startup do Windows.
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
