# Drive Guardian — Handoff de sprint

> Documento de continuidade entre sessões. Sem segredos (valores privados em
> `secrets/valores.md`, fora do git). Atualizado ao **encerrar a sprint em 08/08/2026**.

## Onde estamos

- **Fase 0 (Fundação):** ✅ concluída, validada por você, no `main`.
- **Fase 1 (MVP headless):** ✅ **código completo e no `main`** (commit `1797f39`), CI verde.
  Validação supervisionada **em andamento** — faltam 2 dos 6 critérios.

### Validação da Fase 1 (SPEC §6-F1) — estado atual

| Critério | Descrição | Status |
|---|---|---|
| a | 1º sync clona a árvore inteira | ✅ provado (118 arquivos, 12.6 GB baixados) |
| b | 2º sync não baixa nada | ✅ provado (0 baixados, DB 118 `synced`) |
| c | Queda no meio → retoma, md5 confere | ✅ provado (kill real → resync transferiu só o restante via `Range`/206; md5 confere) |
| f | `--dry-run` não grava nada | ✅ provado (sem `state.db`, sem destino, sem log) |
| **e** | **Modificar no Drive → local novo + antigo em `_versões/`** | ⏳ **PENDENTE** (aguardando ação manual no Drive) |
| **d** | **Apagar no Drive → cópia local intacta** | ⏳ **PENDENTE** (aguardando ação manual no Drive) |

Além disso: **fidelidade** verificada — 10 arquivos aleatórios, md5 local == `md5Checksum` do Drive (10/10).

## ▶️ Próximo passo exato para retomar

Estávamos **pausados aguardando o dono fazer, no site do Drive** (pasta monitorada):

1. **Editar 1 arquivo** — botão direito → *Gerenciar versões* → *Fazer upload de nova
   versão* (mantém o mesmo `file_id`, muda o md5). → prova critério **(e)**.
2. **Apagar 1 arquivo** — mover um arquivo (já baixado) para a lixeira do Drive.
   Temos os 118 localmente; o app nunca apaga local; recuperável na lixeira do Drive.
   → prova critério **(d)**.

Quando o dono confirmar ("pronto"), o agente deve:

1. **Re-capturar** os metadados remotos e **comparar com `remote_meta.json`** (snapshot
   "antes", git-ignored, na raiz do repo — mapa `{nome: {md5, size, id}}` dos 118 arquivos)
   para detectar automaticamente qual arquivo foi **editado** (mesmo `id`, md5 diferente)
   e qual foi **apagado** (sumiu da árvore).
2. Rodar `python cli.py sync` (um ciclo completo — reconciliação via `files.list`).
3. **Provar (e):** o arquivo editado foi rebaixado; a versão local anterior está em
   `D:\DriveGuardian\_versões\...\<nome>.<timestamp>.<ext>`; o novo md5 local == novo md5 do Drive.
4. **Provar (d):** o arquivo apagado **continua** em `D:\DriveGuardian\` com o md5 original
   (comparar com `remote_meta.json`). Obs.: no `sync` completo o apagado apenas some da
   árvore remota e é ignorado (local intacto); o log "removido; mantido localmente" só
   aparece no modo `watch` (via `changes.list`).
5. Relatório final da Fase 1 → pedir aval do dono para a **Fase 2**.

Comando de captura de metadados (reutilizável):
```bash
./.venv/Scripts/python.exe -c "import json;from core.auth import build_auth;from core.config import load_config;from core.drive import build_service,build_tree,iter_files;cfg=load_config('config.yaml');svc=build_service(build_auth(cfg.auth));fs=iter_files(build_tree(svc,cfg.sync.pairs[0].drive_folder_id));json.dump({f.name:{'md5':f.md5,'size':f.size,'id':f.id} for f in fs},open('remote_meta.json','w'));print(len(fs))"
```

## Estado concreto da máquina (não versionado)

- **Backup real existe:** `D:\DriveGuardian\` com os 118 arquivos (12.6 GB).
- **Estado:** `%LOCALAPPDATA%\DriveGuardian\state.db` → 118 `synced`. Logs em
  `%LOCALAPPDATA%\DriveGuardian\logs\drive-guardian.log`.
- **`config.yaml`** real na raiz (git-ignored); valores em `secrets/valores.md`.
- **`remote_meta.json`** na raiz (git-ignored) = snapshot "antes" para o diff de (d)/(e).

## Ambiente e comandos

- venv em `.venv`. Gate: `./.venv/Scripts/python.exe -m ruff check . && ... mypy core/ && ... pytest` (39 testes verdes).
- `python cli.py list | sync | sync --dry-run | watch`.
- `gh` autenticado (`drizaogythub97`); CI (`.github/workflows/ci.yml`) roda o gate a cada push.

## Gotchas aprendidos

- **Matar o processo no Windows:** `kill`/`kill -9` do Git Bash **não** encerra o
  `python.exe` nativo (ele continua e conclui o download). Use PowerShell
  `Stop-Process -Id <pid> -Force` com o PID nativo (via `Start-Process -PassThru`).
- **Console cp1252:** `cli.py` força stdout/stderr para UTF-8 (árvore usa `├└│—`).
- **Retomada:** o downloader usa `AuthorizedSession` + cabeçalho `Range`; o Drive
  responde 206 e concatenamos no `.part`. 416 (part já completo) é tratado.

## Arquitetura (resumo)

`core/`: `config` (validação Nível 3), `state` (SQLite WAL: files/sync_state/events + CRUD),
`auth` (SA; OAuth stub Fase 4), `drive` (árvore), `planner` (`build_plan`/`classify`,
puro/leitura), `downloader` (atômico+retomada+`_versões/`), `verifier` (md5),
`disk` (unidade/espaço), `watcher` (`changes.list`+`FolderResolver`), `sync` (`SyncEngine`:
`run_once`/`watch`). `cli.py` fino. `ui/` só stubs (Fase 3).

## Depois da Fase 1

**Fase 2 — Alertas:** níveis de erro (SPEC §4), ntfy (tópico em `secrets/valores.md`),
heartbeat healthchecks.io (URL em `secrets/valores.md`), resumo semanal.
