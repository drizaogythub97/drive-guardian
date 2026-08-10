# Drive Guardian — Handoff de sprint

> Documento de continuidade entre sessões. Sem segredos (valores privados em
> `secrets/valores.md`, fora do git). Atualizado em **10/08/2026**.

## Onde estamos

- **Fase 0 (Fundação):** ✅ concluída, validada por você, no `main`.
- **Fase 1 (MVP headless):** ✅ **código completo no `main`** e **validação supervisionada
  100% concluída** (6/6 critérios provados em 10/08/2026). CI verde, gate verde (39 testes).
- **Aguardando:** aval do dono para iniciar a **Fase 2 (Alertas)**.

### Validação da Fase 1 (SPEC §6-F1) — CONCLUÍDA

| Critério | Descrição | Status |
|---|---|---|
| a | 1º sync clona a árvore inteira | ✅ provado (118 arquivos, 12.6 GB baixados) |
| b | 2º sync não baixa nada | ✅ provado (0 baixados, DB 118 `synced`) |
| c | Queda no meio → retoma, md5 confere | ✅ provado (kill real → resync transferiu só o restante via `Range`/206; md5 confere) |
| d | Apagar no Drive → cópia local intacta | ✅ provado (10/08 — ver abaixo) |
| e | Modificar no Drive → local novo + antigo em `_versões/` | ✅ provado (10/08 — ver abaixo) |
| f | `--dry-run` não grava nada | ✅ provado (sem `state.db`, sem destino, sem log) |

Além disso: **fidelidade** verificada — 10 arquivos aleatórios, md5 local == `md5Checksum` do Drive (10/10).

#### Evidências de (d) — exclusão (10/08/2026)

`ScreenRecording_11-05-2025 09-25-11_1.mp4` (57 MB) foi para a lixeira do Drive.
Detecção automática via diff contra o snapshot `remote_meta.json` (118 → 117 remotos).

- `cli.py sync` → `0 baixados, 0 versões, 0 falhas`; cópia local **intacta**,
  md5 `ab7de9cab80d837539423f8857fcabbf` idêntico ao original.
- `D:\DriveGuardian` ficou com **118** arquivos enquanto o remoto tem 117 (política cumulativa).
- Caminho do `watch` também exercitado (rebobinando o `page_token` para reprocessar as
  mudanças reais): log `Item removido/lixeira no Drive; mantido localmente (fileId=…)`,
  nada apagado, nada baixado.

#### Evidências de (e) — versionamento (10/08/2026)

`ScreenRecording_05-10-2026 19-24-57_1.mp4` recebeu nova versão no Drive
(mesmo `file_id`, md5 `428721e9…` → `742e92ec…`, 234.790.361 → 1.920.357 bytes).

- `cli.py sync` → `1 baixado, 1 versão, 0 falhas, 1.8 MB transferidos`.
- Novo local: md5 `742e92ec523f44d5559abadd5eea318a` == md5 novo do Drive ✅
- Versão anterior preservada em
  `D:\DriveGuardian\_versões\ScreenRecording_05-10-2026 19-24-57_1.20260810T104029.mp4`,
  md5 `428721e9…` (bit a bit igual ao original) ✅
- Nenhum `.part` órfão; `state.db` atualizado para o novo md5/size, 118 `synced`.
- 2º ciclo logo em seguida: `0 baixados, 0 versões` e `_versões/` continua com **1**
  arquivo → idempotência do versionamento confirmada.

**Armadilha observada:** subir *o mesmo arquivo* em "Gerenciar versões" muda o
`modifiedTime`/`version` no Drive mas **não** o md5 — o app corretamente não faz nada.
Para testar (e) o conteúdo precisa ser realmente diferente.

## ▶️ Próximo passo exato para retomar

Fase 1 fechada. **Pedir/obter o aval do dono e iniciar a Fase 2 (Alertas):** níveis de
erro (SPEC §4), ntfy, heartbeat healthchecks.io, resumo semanal. Não avançar sem o "ok"
dele (regra de gate por fase).

Comando de captura de metadados remotos (reutilizável para futuros diffs):
```bash
./.venv/Scripts/python.exe -c "import json;from core.auth import build_auth;from core.config import load_config;from core.drive import build_service,build_tree,iter_files;cfg=load_config('config.yaml');svc=build_service(build_auth(cfg.auth));fs=iter_files(build_tree(svc,cfg.sync.pairs[0].drive_folder_id));json.dump({f.name:{'md5':f.md5,'size':f.size,'id':f.id} for f in fs},open('remote_meta.json','w'));print(len(fs))"
```

Comando de captura de metadados (reutilizável):
```bash
./.venv/Scripts/python.exe -c "import json;from core.auth import build_auth;from core.config import load_config;from core.drive import build_service,build_tree,iter_files;cfg=load_config('config.yaml');svc=build_service(build_auth(cfg.auth));fs=iter_files(build_tree(svc,cfg.sync.pairs[0].drive_folder_id));json.dump({f.name:{'md5':f.md5,'size':f.size,'id':f.id} for f in fs},open('remote_meta.json','w'));print(len(fs))"
```

## Estado concreto da máquina (não versionado)

- **Backup real existe:** `D:\DriveGuardian\` com **118** arquivos no topo (o remoto tem
  **117** — a diferença é o arquivo apagado no Drive e preservado localmente), mais
  `_versões\` com 1 arquivo (a versão antiga do teste (e)). ~12.4 GB.
- **Estado:** `%LOCALAPPDATA%\DriveGuardian\state.db` → 118 `synced`, `page_token` = 133.
  Logs em `%LOCALAPPDATA%\DriveGuardian\logs\drive-guardian.log`.
- **`config.yaml`** real na raiz (git-ignored); valores em `secrets/valores.md`.
- **`remote_meta.json`** na raiz (git-ignored) = snapshot dos metadados remotos, já
  **atualizado para o estado pós-validação** (117 arquivos) — serve de baseline para
  o próximo diff.

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
- **Nova versão idêntica no Drive** muda `modifiedTime`/`version` mas não o `md5Checksum`
  → o app (corretamente) não baixa nada. Só md5 diferente dispara o versionamento.
- **Reprocessar mudanças passadas** (útil em teste): os `pageToken` do Drive pessoal são
  inteiros sequenciais; dá para rebobinar `sync_state.page_token` para um valor anterior
  e rodar um ciclo incremental sobre mudanças já ocorridas.
- **`sync` completo vs. `watch`:** no `sync` o arquivo apagado apenas some da árvore
  remota (local intacto, sem log específico); a mensagem "removido; mantido localmente"
  vem do `watch` (via `changes.list`). A linha dele no `state.db` permanece `synced`.

## Arquitetura (resumo)

`core/`: `config` (validação Nível 3), `state` (SQLite WAL: files/sync_state/events + CRUD),
`auth` (SA; OAuth stub Fase 4), `drive` (árvore), `planner` (`build_plan`/`classify`,
puro/leitura), `downloader` (atômico+retomada+`_versões/`), `verifier` (md5),
`disk` (unidade/espaço), `watcher` (`changes.list`+`FolderResolver`), `sync` (`SyncEngine`:
`run_once`/`watch`). `cli.py` fino. `ui/` só stubs (Fase 3).

## Depois da Fase 1

**Fase 2 — Alertas:** níveis de erro (SPEC §4), ntfy (tópico em `secrets/valores.md`),
heartbeat healthchecks.io (URL em `secrets/valores.md`), resumo semanal.
