# Drive Guardian — Especificação Técnica

Complementa `CLAUDE.md`. Decisões e justificativas: `ESTUDO-VIABILIDADE.md`.

## 1. Configuração (`config.yaml`)

```yaml
# Drive Guardian — config.example.yaml
auth:
  strategy: service_account            # service_account | user_oauth
  service_account_key: ./secrets/sa-key.json   # fora do git
sync:
  pairs:                               # múltiplos pares pasta→destino (v2; MVP usa 1)
    - drive_folder_id: "1AbC..."       # ID da pasta no Drive
      local_path: "E:/BackupDrive/MemoriasFilho"
  interval_minutes: 30                 # editável na UI; mín. 5
  bandwidth_limit_mbps: 0              # 0 = sem limite; usar no backup inicial >1TB
  export_google_docs: false            # v2: exportar Docs/Sheets nativos
  export_formats: {document: docx, spreadsheet: xlsx, presentation: pptx}
notifications:
  ntfy:
    enabled: true
    server: https://ntfy.sh
    topic: "drive-guardian-<sufixo-aleatorio>"   # tópico = senha; usar sufixo longo
  weekly_summary: true                 # resumo semanal (dia/hora abaixo)
  summary_day: sunday
  summary_hour: 20
heartbeat:
  enabled: true
  url: "https://hc-ping.com/<uuid>"    # healthchecks.io, period = interval + folga
logging:
  level: INFO
  max_file_mb: 10
  backups: 5
```

Validação da config na inicialização = erro Nível 3 se inválida (caminho inexistente, ID vazio, intervalo < 5).

## 2. Banco de estado (SQLite)

Arquivo: `%LOCALAPPDATA%/DriveGuardian/state.db` (WAL mode).

```sql
CREATE TABLE files (
  file_id      TEXT PRIMARY KEY,   -- ID do Drive (estável em renomes/moves)
  drive_path   TEXT NOT NULL,      -- caminho lógico atual no Drive
  local_path   TEXT NOT NULL,      -- caminho absoluto no disco
  md5          TEXT,               -- md5Checksum do Drive na última sync
  size         INTEGER,
  modified_time TEXT,              -- modifiedTime do Drive (RFC3339)
  status       TEXT NOT NULL,      -- synced | pending | downloading | failed | versioned
  fail_count   INTEGER DEFAULT 0,
  last_error   TEXT,
  updated_at   TEXT NOT NULL
);

CREATE TABLE sync_state (          -- singleton (id=1)
  id INTEGER PRIMARY KEY CHECK (id=1),
  page_token   TEXT,               -- changes.list startPageToken corrente
  last_full_scan TEXT,             -- última reconciliação completa
  last_cycle_ok  TEXT
);

CREATE TABLE events (              -- alimenta a aba de logs da UI e o resumo semanal
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT NOT NULL,
  level TEXT NOT NULL,             -- INFO | WARN | ERROR | CRITICAL
  category TEXT NOT NULL,          -- download | auth | disk | config | notify | cycle
  message TEXT NOT NULL,
  file_id TEXT
);
```

## 3. Algoritmos centrais

### Reconciliação completa (boot e 1x/dia)

1. Listar árvore da pasta monitorada (`files.list`, paginado, campos: id, name, parents, md5Checksum, size, modifiedTime, mimeType, trashed).
2. Para cada arquivo remoto: sem registro no SQLite OU md5 diferente OU arquivo local ausente → fila.
3. Arquivos com `status IN (pending, downloading, failed)` → fila (retomada pós-queda).
4. Registrar novo `startPageToken` ao final.

### Ciclo incremental (a cada `interval_minutes`)

1. `changes.list(pageToken)` → mudanças desde o último ciclo.
2. Novos/modificados dentro da pasta monitorada → fila. Removidos/trashed → apenas log INFO (política: nunca apagar).
3. Processar fila; persistir novo pageToken; ping heartbeat.

### Download de um arquivo

1. Criar diretórios; se já existe local com md5 antigo → mover para `_versões/` com timestamp.
2. `files.get(alt=media)` → `<nome>.part` (chunked, resumível via Range).
3. md5 local == md5 do Drive? → rename atômico + `status=synced`. Diferente → apagar `.part`, `fail_count++`, Nível 2.
4. Antes de baixar: checar espaço livre no destino (mínimo: tamanho do arquivo + 500 MB de folga) → senão Nível 3.

## 4. Erros e notificações

| Nível | Exemplos | Ação | Notifica? |
|-------|----------|------|-----------|
| 1 Transitório | timeout, 5xx, 429 | backoff 1→5→30 min, máx. 3 tentativas no ciclo | Não (log) |
| 2 Degradado | arquivo falhou 3x, md5 divergente | pular, retentar no próximo ciclo | Se persistir >24h |
| 3 Crítico | credencial inválida, disco ausente/cheio, config inválida | pausar sync, status vermelho | **Imediata (ntfy, priority=high)** |

Mensagens ntfy em PT-BR, acionáveis: *"Drive Guardian: o disco E: não foi encontrado. Conecte o disco e clique em 'Verificar agora'."*
Resumo semanal (domingo 20h, config.): arquivos novos, bytes, versões criadas, erros pendentes.
Heartbeat: ping só após ciclo **bem-sucedido**; healthchecks.io configurado com period = intervalo + 15 min de folga.

## 5. UI (PySide6) — Fase 3

Bandeja: ícone com 3 estados (verde ok / amarelo sincronizando / vermelho ação necessária); menu: Abrir, Verificar agora, Pausar, Sair.
Janela com 4 abas:

1. **Conexão** — status da credencial, e-mail da SA p/ compartilhamento, teste de conexão.
2. **Pastas** — par pasta Drive (navegador de pastas via API) → destino local; espaço livre do destino.
3. **Parâmetros** — intervalo, limite de banda, resumo semanal, heartbeat, iniciar com Windows (toggle → chave em `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`).
4. **Atividade** — tabela de `events` com filtro por nível, contadores do último ciclo, botão exportar log.

## 6. Critérios de aceite por fase

- **F0:** `python cli.py list` imprime a árvore da pasta do Drive autenticando via SA. `ruff`/`mypy`/`pytest` verdes.
- **F1:** (a) 1º `sync` clona a árvore inteira; (b) 2º `sync` não baixa nada; (c) derrubar rede no meio de arquivo grande → próximo `sync` completa e md5 confere; (d) deletar arquivo no Drive → local intacto; (e) modificar no Drive → local novo correto + antigo em `_versões/`; (f) `--dry-run` não grava nada.
- **F2:** revogar credencial → notificação ntfy em <1 min no celular; desligar app → healthchecks alerta após o period; resumo semanal chega.
- **F3:** usuário leigo configura tudo pela UI sem editar YAML; app sobrevive a reboot e roda sozinho.
- **F4:** `git clone` → seguir README → funcionando em máquina limpa; `.exe` do PyInstaller roda sem Python instalado.

## 7. Onboarding para terceiros (decisão 07/08/2026 — Fase 4)

Objetivo: usuário leigo conecta a conta pelo botão "Login com Google" na UI e escolhe a pasta num navegador visual — sem tocar no Google Cloud Console.

- Restrição: verificação Google para escopo restrito (`drive.readonly`) exige auditoria CASA paga → **fora de cogitação** (custo zero).
- **Spike prioritário na Fase 4:** escopo `drive.file` (não restrito) + **Google Picker** para seleção da pasta. Validar: o acesso concedido à pasta selecionada cobre arquivos/subpastas **criados depois**? Se sim → vira o modo padrão para terceiros (UX limpa + privacidade máxima: o app só enxerga a pasta escolhida).
- Fallback documentado no README: (a) OAuth com client do usuário (modelo rclone, passo a passo com prints) ou (b) client do projeto publicado sem verificação (tela de aviso "app não verificado", limite 100 usuários).
- Segurança local: token/credencial criptografados com DPAPI (Windows); escopo somente leitura; sem servidor intermediário — nenhum dado transita por terceiros.

## 8. Estrutura do repositório

```
drive-guardian/
├── CLAUDE.md  SPEC.md  README.md  README.pt-BR.md  LICENSE (MIT)
├── config.example.yaml   .gitignore (secrets/, *.db, logs/, config.yaml)
├── core/    # auth.py watcher.py planner.py downloader.py verifier.py
│            # state.py logger.py notifier/{base,ntfy}.py heartbeat.py
├── ui/      # app.py tray.py windows/  strings.py
├── cli.py
└── tests/   # unit (planner, state, verifier c/ mocks) + fixtures
```
