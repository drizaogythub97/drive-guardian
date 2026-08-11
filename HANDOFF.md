# Drive Guardian — Handoff de sprint

> Documento de continuidade entre sessões. Sem segredos (valores privados em
> `secrets/valores.md`, fora do git). **Sprint encerrada em 11/08/2026.**
>
> **Resumo de uma linha:** Fases 0–3 completas e **validadas** (só falta o dono fazer o
> teste de reboot); **Fase 4 autorizada** e ainda não começada — o próximo agente pode
> pegar o item 1 da lista em "Próximo passo exato".

## Onde estamos

- **Fase 0 (Fundação):** ✅ concluída, validada por você, no `main`.
- **Fase 1 (MVP headless):** ✅ **código completo no `main`** e **validação supervisionada
  100% concluída** (6/6 critérios provados em 10/08/2026).
- **Fase 2 (Alertas):** ✅ **código completo no `main`** (commit `27592cc`), CI verde.
  Critérios de aceite exercitados — detalhes abaixo.
- **Fase 3 (UI PySide6):** ✅ **código completo** (`5e6655f`) e **validada pelo dono em
  11/08/2026**, com 5 defeitos achados e corrigidos em `94034d1`. Gate verde
  (**115 testes**). Pendente só o item 7 do roteiro (reboot), que ele fará depois.
- **Fase 4 (polimento GitHub):** 🔓 **autorizada em 11/08/2026** ("seguimos as próximas
  fases"), **nenhuma linha escrita ainda**. Ordem combinada em "Próximo passo exato".

### Fase 3 — o que foi entregue (SPEC §5)

| Peça | Onde | Observação |
|---|---|---|
| Bandeja 3 estados | `ui/tray.py`, `ui/icons.py` | Ícone desenhado em runtime com `QPainter` (nenhum `.ico` para o PyInstaller empacotar); verde/amarelo/vermelho + cinza pausado; tooltip repete o estado em texto |
| Menu da bandeja | `ui/tray.py` | Abrir, Verificar agora, Pausar/Retomar, Sair |
| Janela + 4 abas | `ui/main_window.py`, `ui/tabs/` | Conexão, Pastas, Parâmetros, Atividade |
| Navegador de pastas do Drive | `ui/tabs/folders.py` | Raiz = `sharedWithMe` (a SA não tem Meu Drive); o ID salvo é traduzido para o nome real em segundo plano |
| Log de atividade | `ui/tabs/activity.py` | Tabela de `events` com segmentado Tudo/Normal/Problemas, exportar log, KPIs do último ciclo vindos de `cycles` |
| Startup do Windows | `ui/startup.py` | `HKCU\...\Run`; usa `pythonw.exe` para não abrir console no login |
| Thread de sync | `ui/worker.py` | `SyncEngine` fora da thread da UI, com `State` próprio |
| Tema | `ui/theme.py`, `ui/widgets.py` | Padrão "Minimalista" do dono **adaptado ao desktop** (valores "cheios"): escala tipográfica, cartão com cabeçalho + divisor, segmentado, sem ícone decorativo |

**Fechar a janela não encerra o app** — ele volta para a bandeja e continua
sincronizando; sair de verdade é pelo menu. Rodar: `python gui.py`
(precisa de `pip install -e ".[ui]"`).

### Validação da Fase 3 (11/08/2026) — CONCLUÍDA, menos o reboot

O dono percorreu o roteiro na máquina dele. Aprovados: janela e bandeja, "Testar
conexão", navegador de pastas, "Enviar aviso de teste" (chegou no celular), aba
Atividade inteira (filtros, KPIs, exportar log) e todo o menu da bandeja
(Verificar agora, Pausar/Retomar, X que não fecha o app). **Falta só o item 7,
reiniciar o Windows** — ele disse que faz depois e avisa se falhar.

Enquanto a janela ficou aberta o app provou o principal sozinho: às 12:44 UTC de
11/08 baixou **50 arquivos novos** que tinham aparecido no Drive, sem ninguém pedir
(`Ciclo completo: 50 baixados, 0 versões, 0 falhas`).

#### Os 5 defeitos que a validação revelou (corrigidos em `94034d1`)

| Defeito | Causa | Correção |
|---|---|---|
| Setas do campo de minutos inertes | Ao estilizar `QSpinBox` no QSS o Qt **para de desenhar as setas nativas** e a geometria dos sub-botões colapsa. Provado com `QTest`: clique no canto superior direito não mudava o valor e o meio-direita fazia `30 → 29` | Sub-botões zerados no QSS + `widgets.stepper()`, que põe botões **− / +** de verdade ao lado do campo (alvo grande, no espírito do padrão minimalista) |
| "Salvar" parecia sempre ativo | A lógica estava certa (rodei o app com `_mark_dirty` instrumentado: ninguém marca sozinho — o que acendeu foi o dono mexer no spin quebrado). O problema era o **azul-claro** do estado desabilitado, que ainda lê como "botão azul clicável" | `QPushButton[role="primary"]:disabled` agora é cinza com texto apagado. Medido no pixel: `#f7f7f8` desligado × `#2563eb` ligado |
| "Atualizar" da aba Atividade sem feedback | A leitura do SQLite é instantânea e a tabela costuma vir idêntica → o clique parece ignorado | Rótulo `Atualizado às HH:MM:SS — N registro(s)`; o relógio muda a cada clique |
| Faixa cinza sobre o cartão branco | O container de `widgets.row()` herdava o fundo do `QWidget` (mesmo motivo pelo qual `QLabel`/`QCheckBox` são transparentes) | `QWidget[role="row"]` transparente — sumiu em todas as abas |
| Texto do teste de conexão | Dizia "N item(ns) visíveis na pasta", mas o número vem de `list_folders()`: são **pastas que a conta de serviço enxerga**, não arquivos dentro da pasta | "a conta de serviço enxerga N pasta(s) compartilhada(s)" |

`tests/test_ui_theme.py` (3 testes) trava essas decisões de QSS. Roda no CI **sem Qt**,
porque `ui/theme.py` não importa PySide6 — é só string.

### Fase 2 — o que foi entregue (SPEC §4)

| Peça | Onde | Observação |
|---|---|---|
| Níveis de erro 1/2/3 | `core/errors.py` | Classifica exceção de terceiros por status HTTP: 429/5xx → transitório; 401/403 → crítico; demais 4xx → degradado |
| Retry com backoff | `core/retry.py` | 1 → 5 → 30 min, máx. 3 tentativas; só transitórios; `sleep` injetável nos testes |
| Notificador ntfy | `core/notifier/ntfy.py` | POST no tópico, headers Title/Priority/Tags; **falha de envio nunca derruba o ciclo** |
| Heartbeat | `core/heartbeat.py` | `ping()` só após ciclo bem-sucedido; `/fail` em erro crítico |
| Política de alerta | `core/alerts.py` | Crítico imediato (priority=high, texto acionável em PT-BR); degradado só após 24h de falha; **anti-spam persistido em `events`** (evento com `category='alerta:<chave>'`), sobrevive a reinício |
| Resumo semanal | `core/summary.py` | Números vêm da tabela `cycles`; agendamento preguiçoso — se o PC estava desligado no domingo 20h, sai no primeiro ciclo depois |
| Registro de movimentações | `core/sync.py` | Detecta no `sync` completo o que sumiu do Drive → status `removido_no_drive` + evento; restaura se voltar; grava cada ciclo em `cycles` |
| CLI de inspeção | `cli.py` | `status`, `events`, `summary [--send]`, `test-alert` |

**Decisão do dono (10/08):** toda movimentação precisa ficar registrada para aparecer no
log da UI. Antes, no `sync` completo, um arquivo apagado no Drive sumia em silêncio —
agora vira status + evento. Registrado também em `CLAUDE.md`.

### Validação da Fase 2 (SPEC §6-F2)

| Critério | Status |
|---|---|
| Credencial inválida → ntfy em <1 min | ✅ exercitado com credencial **simulada** (config de teste com chave quebrada): erro Nível 3 → notificação no celular na hora. Revogação real da SA não foi feita (destrutiva, decisão sua) |
| App desligado → healthchecks alerta após o period | ⚠️ **parcial** — o caminho `/fail` foi disparado e o check voltou ao verde com um ping ok. Falta você conferir no painel do healthchecks.io se o *period* está como intervalo + 15 min de folga e deixar o app parado além disso |
| Resumo semanal chega | ✅ enviado de verdade (`cli.py summary --send`), recebido no tópico ntfy |

Extra provado na prática: **anti-spam** (2ª falha idêntica em seguida gera log mas
**não** gera notificação) e **migração de schema** no banco real da Fase 1 sem perda.

**Cuidado tomado:** o marcador de dedup do teste de credencial foi apagado do `state.db`
para não silenciar um alerta **real** nas 6 h seguintes. Os dois eventos de log do teste
(`Nível 3 (auth): …`) foram mantidos — são registro honesto.

**Polimentos feitos depois (10/08, pedido do dono ao ver os prints):**
1. A mensagem crítica passou a liderar com linguagem simples e a ação; o jargão da
   exceção vai no fim, como "Detalhe técnico".
2. O marcador de anti-spam saiu do texto da mensagem (aparecia como
   `[alerta:resumo-semanal] …` no log que a UI mostra) e foi para a coluna `category`.
   A aba Atividade ainda limpa o prefixo antigo em bancos já existentes.

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

Nada pendente de commit ou push. **A Fase 4 está autorizada e ainda não começou** — o
dono encerrou a sprint com *"faremos depois"*. Comece pelo item 1, que não depende dele:

1. **Export de Docs nativos.** Documentos/Planilhas/Apresentações do Google não têm
   binário para baixar: precisam de `files.export` para `.docx`/`.xlsx`/`.pdf`.
   `sync.export_google_docs` e `sync.export_formats` **já existem na config e são
   ignorados pelo core** — é aí que entra. Atenção: arquivos exportados **não têm
   `md5Checksum`**, então a verificação de integridade da regra 2 do `CLAUDE.md`
   precisa de um caminho próprio (decidir e documentar: tamanho? sem verificação com
   evento explícito?). Vale também tratar `size` ausente na fila.
2. **Login com Google (OAuth de usuário)** + token cifrado com DPAPI.
   `core/auth.py` tem `UserOAuthAuth` como stub com a interface pronta.
3. **PyInstaller**: .exe único. `ui/startup.py:launch_command()` já trata `sys.frozen` e
   `ui/icons.py` desenha o ícone em runtime (nenhum recurso para empacotar).
4. **READMEs** bilíngues completos (EN + pt-BR).
5. **Spike `drive.file` + Google Picker** (SPEC §7): o acesso concedido à pasta escolhida
   cobre arquivos criados **depois**? Se sim, vira o modo padrão para terceiros.

**Precisa do dono nos itens 2 e 5:** criar um **client OAuth de desktop** no Google Cloud
Console (grátis). Avisar com o passo a passo antes de chegar lá — não deixe isso virar
bloqueio no meio do trabalho; faça 1, 3 e 4 enquanto isso.

Pendências do lado dele (só avisar, não bloqueiam):
- Item 7 do roteiro da Fase 3: **reiniciar o Windows** e ver o app voltar sozinho.
- Fase 2: conferir no painel do healthchecks.io se o *period* está em intervalo + 15 min
  (os alertas mostraram **45 min**; o intervalo agora está em **26**, então o period
  continua folgado — só confirmar a *grace*).

### Roteiro da validação da Fase 3 (já percorrido em 11/08; mantido para regressão)

1. `python gui.py` → confirmar ícone na bandeja e a janela abrindo.
2. **Conexão** → "Testar conexão" deve responder com o número de pastas visíveis.
3. **Pastas** → "Escolher pasta…" abre o navegador (raiz = compartilhadas com a SA);
   descer com duplo clique, "Voltar" sobe; escolher e ver o nome no campo.
4. **Parâmetros** → mudar o intervalo, marcar "Iniciar junto com o Windows",
   "Enviar aviso de teste" (chega no celular) e **Salvar** (o botão só habilita quando
   há mudança). Conferir que o `config.yaml` foi reescrito com cabeçalho de comentário.
5. **Atividade** → filtros Tudo/Normal/Problemas, "Atualizar", "Exportar log".
6. Bandeja → "Verificar agora" (status vira amarelo e volta a verde), "Pausar"/"Retomar",
   fechar a janela no X (o app **continua** na bandeja), "Sair" encerra de verdade.
7. **Reiniciar o Windows** e conferir que o app volta sozinho (critério F3).

Se algo falhar, a aba Atividade e `%LOCALAPPDATA%\DriveGuardian\logs\` têm o registro.

Comando de captura de metadados remotos (reutilizável para futuros diffs):
```bash
./.venv/Scripts/python.exe -c "import json;from core.auth import build_auth;from core.config import load_config;from core.drive import build_service,build_tree,iter_files;cfg=load_config('config.yaml');svc=build_service(build_auth(cfg.auth));fs=iter_files(build_tree(svc,cfg.sync.pairs[0].drive_folder_id));json.dump({f.name:{'md5':f.md5,'size':f.size,'id':f.id} for f in fs},open('remote_meta.json','w'));print(len(fs))"
```

## Estado concreto da máquina (não versionado) — 11/08/2026, fim da sprint

- **Backup real:** `D:\DriveGuardian\` com **168** arquivos no topo e `_versões\` com 1,
  **18.53 GB**. Cresceu 50 arquivos hoje (o Drive recebeu novidades e o app baixou
  sozinho durante a validação).
- **Estado:** `%LOCALAPPDATA%\DriveGuardian\state.db` → 168 conhecidos = **167 `synced` +
  1 `removido_no_drive`** (o arquivo apagado no Drive, cópia local intacta).
  Último ciclo ok: `2026-08-11T14:01:44Z`. Logs em
  `%LOCALAPPDATA%\DriveGuardian\logs\drive-guardian.log`.
- **⚠️ O app FICOU RODANDO** (a UI, iniciada às 10:35 local; PIDs 11132/14412 naquela
  sessão) — de propósito, para o backup continuar e o heartbeat não cair. Para encerrar:
  menu da bandeja → Sair, ou `Stop-Process` (ver gotcha).
- **`config.yaml`** real na raiz (git-ignored); valores em `secrets/valores.md`.
  **`interval_minutes` está em 26** — o dono mexeu no campo durante o teste, antes da
  correção das setas. Não é defeito; se ele quiser 30, é pela aba Parâmetros.
- **`.venv` tem o PySide6 instalado** (6.11.1), então `python gui.py` roda direto.
- **`remote_meta.json`** na raiz (git-ignored) = snapshot dos metadados remotos, **de
  10/08 (117 arquivos), portanto DESATUALIZADO** frente aos 167 de hoje. Regerar com o
  comando acima antes de usá-lo como baseline de diff.

## Ambiente e comandos

- venv em `.venv`. Gate: `ruff check . && mypy core/ ui/ gui.py cli.py && pytest`
  (115 testes verdes, 1 skip). O `[tool.mypy] platform = "win32"` do `pyproject.toml` faz
  o `winreg` do `ui/startup.py` resolver também no Linux do CI.
- `python cli.py list | sync | sync --dry-run | watch | status | events | summary | test-alert`.
- `python gui.py` abre a interface (requer `pip install -e ".[ui]"`).
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
- **`sync` completo vs. `watch` na exclusão:** os dois registram, com textos diferentes.
  O `sync` compara a árvore remota com o estado e grava
  `Sumiu do Drive (lixeira/exclusão); cópia local mantida: …` + status
  `removido_no_drive`; o `watch` vê o evento em `changes.list` e grava
  `Item removido/lixeira no Drive; mantido localmente (fileId=…)`. Nenhum dos dois toca
  no arquivo local.
- **Qt e SQLite:** conexões sqlite pertencem à thread que as abriu. A UI e o
  `ui/worker.py` têm cada um o seu `State` sobre o mesmo arquivo — o modo WAL deixa a
  janela ler enquanto o worker escreve.
- **`QLabel`/`QCheckBox` herdam o fundo do `QWidget`** e desenham uma faixa cinza sobre o
  cartão branco; o QSS os força a `background: transparent`.
- **Screenshot da UI para conferência:** `QT_QPA_PLATFORM=offscreen` renderiza sem
  fontes (tudo vira quadradinho). Usar o backend nativo e `widget.grab()` sem `show()`.
- **QSS mata os sub-controles nativos.** Estilizar `QSpinBox` (ou `QComboBox`) faz o Qt
  trocar o estilo nativo pelo `QStyleSheetStyle`: as setas deixam de ser desenhadas e a
  área de clique colapsa. Se estilizar o campo, ou define `::up-button`/`::down-button`
  na mão (e mesmo assim **a seta não aparece sem `image:`**, que exigiria recurso
  empacotado), ou usa controles próprios — foi o caminho do `widgets.stepper`.
- **Como provar defeito de UI sem depender do olho:** `QTest.mouseClick(widget, ..., pos)`
  para o comportamento e `widget.grab().toImage().pixelColor(x, y)` + `Counter` para a
  cor dominante de uma região. Foi assim que se mostrou que "o clique sempre diminuía" e
  que o botão desabilitado estava com o azul cheio `#2563eb`.
- **Descobrir quem dispara um sinal:** monkeypatch do método (`MainWindow._mark_dirty`)
  com `traceback.print_stack()` e rodar o app real por alguns segundos. Foi o que
  inocentou a lógica do botão Salvar.
- **`ruff` RUF001/RUF002** barram o sinal de menos `U+2212` em string e docstring. No
  código use `chr(0x2212)`; nos comentários, escreva "menos/mais" por extenso.
- **Heartbeat cai sozinho quando o app não está rodando** — é o comportamento correto
  (é assim que o healthchecks avisa que o backup parou). Depois de testar à mão, ou
  deixe o `watch`/a UI rodando, ou pause o check no painel.

## Arquitetura (resumo)

`core/` (nunca importa `ui/`): `config` (validação Nível 3 + `save_config` atômico),
`state` (SQLite WAL: `files`/`sync_state`/`events`/`cycles` + migrações), `auth`
(SA; OAuth stub Fase 4), `drive` (árvore + `list_folders`/`folder_name`), `planner`
(`build_plan`/`classify`, puro/leitura), `downloader` (atômico+retomada+`_versões/`),
`verifier` (md5), `disk` (unidade/espaço), `watcher` (`changes.list`+`FolderResolver`),
`errors` (níveis 1/2/3 + classificação), `retry` (backoff), `notifier/` (ntfy),
`heartbeat`, `alerts` (política + anti-spam), `summary` (resumo semanal),
`sync` (`SyncEngine`: `run_once`/`watch`).

`ui/`: `app` (entrada), `main_window` (janela + abas), `tray`, `worker` (thread do
engine), `tabs/{connection,folders,parameters,activity}`, `widgets` (Card/Kpi/
Segmented/badge/**stepper**), `theme` (QSS + tokens), `icons` (bandeja em runtime),
`startup` (registro do Windows), `formatting` (apresentação sem Qt, testável no CI),
`strings` (PT-BR).

`cli.py` fino; `gui.py` é o atalho da interface.

## Fase 4 — pontos de apoio

A ordem de ataque está em "Próximo passo exato". Pontos já mapeados que a fase encosta:
- `ui/startup.py:launch_command()` já trata o caso empacotado (`sys.frozen`).
- `ui/icons.py` desenha o ícone em runtime — o PyInstaller não precisa de recursos.
- `core/auth.py` tem o `UserOAuthAuth` como stub, com a interface já definida.
- `sync.export_google_docs` / `export_formats` existem na config e são ignorados no core.
