# Drive Guardian — Estudo de Viabilidade e Plano de Projeto

> Automação de backup local contínuo de uma pasta do Google Drive para disco físico, com interface de configuração, logs e alertas no celular.
> **Status:** Planejamento (Cowork) · **Codificação:** Claude Code · **Data:** 07/08/2026

---

## 1. Visão do produto

Um aplicativo Windows que:

1. Conecta-se a uma conta Google Drive e monitora uma ou mais pastas.
2. Detecta novos arquivos/pastas em segundo plano, em intervalo configurável.
3. Baixa cada arquivo **no tamanho original** (byte a byte, sem recompressão) e replica a estrutura de pastas exata no disco físico apontado.
4. Executa verificação completa ao ligar o computador e continua verificando enquanto ligado.
5. **Nunca apaga nada localmente** — backup cumulativo (decisão tomada: exclusões no Drive não se propagam).
6. Possui interface para conexão de conta, apontamento de pastas/disco, intervalo de checagem, logs e erros.
7. Avisa o usuário no celular quando a automação falha e exige ação manual.

Uso pessoal inicial: fotos e vídeos do seu filho. Uso secundário: projeto público no GitHub / portfólio — o que exige código genérico, documentado e com decisões justificadas.

---

## 2. Requisitos organizados

### Funcionais

| # | Requisito | Prioridade |
|---|-----------|------------|
| RF1 | Autenticar na conta Google e listar pastas do Drive | MVP |
| RF2 | Detectar arquivos/pastas novos ou modificados na pasta monitorada | MVP |
| RF3 | Download no tamanho original + réplica exata da árvore de pastas | MVP |
| RF4 | Verificação completa no boot do Windows | MVP |
| RF5 | Polling em intervalo configurável enquanto ligado | MVP |
| RF6 | Nunca excluir arquivos locais | MVP |
| RF7 | Interface: conexões, apontamentos, parâmetros, logs, erros | v1 |
| RF8 | Notificação no celular em falha que exige ação manual | v1 |
| RF9 | Verificação de integridade pós-download (checksum) | v1 |
| RF10 | Suporte a arquivos nativos Google (Docs/Sheets) via exportação | v2 (portfólio) |

### Não funcionais

- Retomável: queda de energia/rede no meio de um download não pode corromper o backup.
- Idempotente: rodar a verificação 2x não baixa nada em dobro.
- Baixo consumo em idle (roda 24/7 em segundo plano).
- Estado persistente local (o programa "lembra" o que já baixou entre reinicializações).
- Código público: sem segredos no repositório, setup documentado para terceiros.

---

## 3. Estudo de viabilidade

### 3.1 Acesso ao Google Drive — VIÁVEL, com 2 armadilhas importantes

A [Google Drive API v3](https://developers.google.com/workspace/drive/api/guides/manage-changes) cobre 100% do necessário:

- `files.list` para varredura completa (boot/reconciliação).
- `changes.list` + `startPageToken`: a API entrega **apenas o que mudou** desde a última checagem — é o mecanismo ideal para o polling em segundo plano (barato, não varre a árvore inteira a cada ciclo).
- `files.get` com `alt=media`: baixa o **binário original**. O Drive (diferente do Google Fotos) armazena o arquivo exatamente como foi upado, então "tamanho máximo" é garantido por definição para fotos/vídeos upados no Drive.
- Metadados incluem `md5Checksum` — permite validar cada download byte a byte (RF9), de graça.
- Cotas ([modelo novo desde 01/05/2026](https://developers.google.com/workspace/drive/api/guides/limits)): 1.000.000 unidades/min por projeto (um ciclo de polling gasta ~100–300 unidades — irrelevante) e **teto de 1 TB/dia de download por projeto** antes de cobrança. Só importa na **primeira sincronização** de acervos gigantes: se o acervo passar de ~1 TB, o app deve espalhar o backup inicial por mais de um dia (throttle configurável — incluído no plano).

**Armadilha 1 — OAuth em modo "Testing":** app OAuth não publicado tem refresh token que **expira em 7 dias**, o que quebraria a automação silenciosamente toda semana. Soluções:

- **Recomendado para seu uso pessoal: Conta de Serviço (Service Account).** Você cria uma conta de serviço no Google Cloud, compartilha a pasta do Drive com o e-mail dela (como compartilharia com uma pessoa) e pronto: sem tela de consentimento, sem expiração de 7 dias, sem verificação da Google. É o caminho de menor atrito e mais robusto para rodar 24/7.
- Para o portfólio, o app deve **suportar também OAuth de usuário** (fluxo desktop), documentando que o usuário precisa publicar o app em "Production" no próprio Google Cloud Console para evitar a expiração. Cada usuário do GitHub cria seu próprio projeto/credencial — modelo padrão em ferramentas open source (é como o rclone recomenda).

**Armadilha 2 — arquivos nativos Google:** Docs/Sheets/Slides não têm binário; precisam de `files.export` (→ .docx/.xlsx/PDF), que tem **limite de 10 MB por exportação**. Para seu caso (fotos/vídeos) é irrelevante, mas para o portfólio: implementar exportação configurável e registrar em log os que excederem o limite. Fica como v2.

**Push vs polling:** a API oferece push notifications, mas exigem endpoint HTTPS público — inviável/indesejável para app desktop. **Polling com `changes.list` é a escolha certa** e é exatamente o que você pediu (intervalo editável).

### 3.2 Execução em segundo plano no Windows — VIÁVEL, trivial

Duas opções:

1. **App na bandeja do sistema (tray) com inicialização automática** — recomendado. Registro em `HKCU\...\Run` ou pasta Startup. Simples, visível, fácil de depurar.
2. Serviço do Windows — roda sem usuário logado, porém complica UI, depuração e instalação. Desnecessário aqui.

Verificação no boot = o próprio app, ao iniciar, roda um ciclo de reconciliação completa antes de entrar no loop de polling.

### 3.3 Notificação no celular — VIÁVEL; WhatsApp não vale a pena

| Opção | Custo | Complexidade | Veredito |
|-------|-------|--------------|----------|
| **[ntfy.sh](https://ntfy.sh)** | Grátis | 1 requisição HTTP POST; app leve Android/iOS; basta assinar um tópico | ✅ **Recomendado** |
| Telegram Bot | Grátis | Criar bot via @BotFather, 1 HTTP POST | ✅ Ótima 2ª opção (se já usa Telegram) |
| Pushover | US$ 5 (única vez) | 1 HTTP POST | Boa, mas paga |
| WhatsApp (API oficial Meta/Cloud) | Template pago (~US$ 0,025/msg) + conta Business + número dedicado + aprovação de template | Alta | ❌ Burocracia desproporcional para "me avise que falhou" |
| WhatsApp (libs não oficiais) | Grátis | Média | ❌ Viola ToS, risco de banir seu número |
| App próprio no celular | Grátis | Muito alta (desenvolver, assinar, distribuir, manter push) | ❌ É exatamente o que o ntfy já é |

**Recomendação:** ntfy como padrão (o "app próprio de apoio" que você imaginou já existe pronto), com o notificador implementado por interface plugável — trocar para Telegram/Pushover vira só um adapter. Bom para o portfólio.

### 3.4 Alternativas prontas (honestidade de engenharia)

[rclone](https://rclone.org/drive/) + Agendador de Tarefas do Windows já faz 90% do backup em si, e o Google Drive para Desktop faz espelhamento oficial. **Por que construir mesmo assim:** nenhum dos dois entrega o pacote completo que você quer (UI própria de configuração + política "nunca apagar" garantida + logs amigáveis + alerta no celular + verificação de integridade com relatório), e o objetivo de portfólio justifica o desenvolvimento. O README do GitHub deve citar essas alternativas e explicar o diferencial — isso valoriza o projeto, não o diminui.

### Veredito geral: **VIÁVEL**, sem bloqueadores técnicos. Os dois riscos reais (expiração OAuth e confiabilidade do "nunca apagar") têm solução conhecida.

---

## 4. Arquitetura recomendada

**Stack: Python 3.12+** — melhor relação produtividade/ecossistema (SDK Google oficial, `watchdog` desnecessário pois o watch é remoto), excelente para o Claude Code gerar e testar, e legível para quem visitar o GitHub.

```
drive-guardian/
├── core/                  # lógica pura, sem UI (testável isoladamente)
│   ├── auth.py            # Service Account + OAuth desktop (estratégias)
│   ├── watcher.py         # changes.list + reconciliação completa
│   ├── downloader.py      # download resumível → .part → rename atômico
│   ├── verifier.py        # md5 pós-download vs metadado do Drive
│   ├── planner.py         # decide o que baixar (nunca deletar)
│   ├── state.py           # SQLite: arquivos conhecidos, checksums, pageToken
│   ├── notifier/          # interface + adapters: ntfy, telegram, pushover
│   └── logger.py          # log rotativo em arquivo + eventos p/ UI
├── ui/                    # PySide6: janela de config + ícone de bandeja
├── cli.py                 # roda o core sem UI (headless — útil p/ testes e servidores)
└── config.yaml            # pastas, disco destino, intervalo, notificador
```

Decisões-chave:

- **Core desacoplado da UI** (o core roda via CLI sozinho). Facilita testes do Claude Code e agrega valor de portfólio.
- **SQLite como fonte de verdade local**: caminho no Drive, fileId, md5, tamanho, status, data. Idempotência e retomada vêm daí.
- **Download atômico**: baixa para `arquivo.ext.part`, valida md5, só então renomeia. Queda de energia nunca deixa arquivo corrompido "parecendo" completo.
- **UI em PySide6 (Qt)** com ícone na bandeja: nativo, leve, sem navegador embutido. Alternativa descartada: Electron/Tauri (peso/complexidade sem ganho aqui).
- Empacotamento: PyInstaller → `.exe` único + instalador opcional (Inno Setup).

### Fluxo principal

```
Boot → carrega config → autentica
     → RECONCILIAÇÃO: lista árvore completa do Drive ✕ SQLite ✕ disco
         → fila de pendências (novos, alterados, downloads incompletos)
     → processa fila (download → verify → commit no SQLite → log)
     → LOOP: a cada N min (config): changes.list desde último pageToken
         → novidades? → fila → processa
     → erro em qualquer etapa → retry com backoff (3x) → persiste? → notifica celular
```

---

## 5. Tratamento de erros e notificações (seu requisito central)

Classificar erros em três níveis — só o nível 3 incomoda você no celular:

1. **Transitório** (rede caiu, HTTP 5xx, rate limit): retry automático com backoff exponencial (1 min → 5 min → 30 min). Log apenas.
2. **Degradado** (arquivo individual falhou 3x, checksum divergente): pula o arquivo, marca no SQLite p/ retentar no próximo ciclo, log de aviso. Notifica só se persistir > 24 h.
3. **Crítico — exige ação manual** (credencial revogada/expirada, disco destino ausente ou sem espaço, config inválida): **notificação imediata via ntfy** com mensagem clara do que fazer, e status vermelho na UI/bandeja.

Complementos valiosos:

- **Heartbeat (dead man's switch):** o ponto cego de todo backup é quando ele *para de rodar* e ninguém percebe (PC não ligou, app travou). Solução gratuita: [healthchecks.io](https://healthchecks.io) — o app faz 1 ping por ciclo; se os pings pararem, **o serviço te avisa**. Cobre a falha que o próprio app não consegue reportar. Fortemente recomendado.
- Resumo periódico opcional (diário/semanal via ntfy): "37 arquivos novos, 2,1 GB, 0 erros" — confiança sem ruído.

---

## 6. Sugestões de adições (identificadas no estudo)

| Sugestão | Valor | Fase |
|----------|-------|------|
| Verificação md5 pós-download | Garante fidelidade real do backup, quase de graça | v1 |
| Heartbeat healthchecks.io | Detecta a automação morta — maior risco real de backup | v1 |
| Monitor de espaço do disco destino | Avisa antes de encher (nível crítico) | v1 |
| Arquivos *modificados* no Drive → versão local antiga vai para `_versões/` com timestamp | Coerente com "nunca perder nada"; evita sobrescrever silenciosamente | v1 |
| Modo dry-run ("o que seria baixado") | Confiança + depuração | v1 |
| Botão "Verificar agora" na UI | Conveniência óbvia | v1 |
| Exportação de Docs/Sheets nativos | Necessário p/ público geral do GitHub | v2 |
| Múltiplos pares pasta→destino | Generaliza o produto | v2 |
| Relatório de verificação completa (re-hash do disco) mensal | Detecta bit rot / corrupção do HD | v2 |

---

## 7. Roadmap para o Claude Code

**Fase 0 — Fundação (1 sessão):** esqueleto do repo, config.yaml, SQLite schema, logging, autenticação por Service Account, listar pasta do Drive no console.

**Fase 1 — MVP headless (1–2 sessões):** reconciliação completa + fila + download atômico com md5 + `changes.list` em loop com intervalo configurável + CLI. *Critério de aceite: derrubar a rede no meio de um vídeo grande e o backup terminar íntegro sozinho.*

**Fase 2 — Alertas (1 sessão):** níveis de erro, retry/backoff, adapter ntfy, heartbeat healthchecks.io.

**Fase 3 — UI (2 sessões):** PySide6 — bandeja, status, config de pastas/disco/intervalo, visualizador de logs, "Verificar agora". Registro no startup do Windows.

**Fase 4 — Polimento p/ GitHub (1–2 sessões):** OAuth de usuário como alternativa, README bilíngue com setup passo a passo, exportação de Docs, PyInstaller/instalador, testes.

**Definir antes da Fase 0:** nome do projeto (sugestão: *Drive Guardian*), licença (MIT sugerida) e criação do projeto no Google Cloud Console (te guio quando quiser — são ~10 min).

---

## 8. Decisões aprovadas (07/08/2026)

| Decisão | Valor |
|---------|-------|
| Nome / Licença | **Drive Guardian** / MIT |
| Custo | **Zero** — restrição formal: apenas serviços gratuitos/free tier, sem cartão de crédito |
| Política de exclusão | Nunca apagar local (cumulativo) + `_versões/` para modificados |
| Autenticação | Conta de Serviço (pessoal) + OAuth desktop como opção documentada (GitHub) |
| Notificação | ntfy (padrão, plugável) + heartbeat healthchecks.io |
| Intervalo padrão | 30 min (editável na UI) |
| Resumo periódico | Semanal via ntfy |
| Idioma | UI PT-BR (strings isoladas) + README bilíngue EN/PT |
| Plataforma | Windows como alvo; core Python portável via CLI |
| Stack | Python 3.12+, PySide6, SQLite, PyInstaller |

## 9. Fontes

- [Google Drive API — Retrieve changes](https://developers.google.com/workspace/drive/api/guides/manage-changes) · [Usage limits](https://developers.google.com/workspace/drive/api/guides/limits)
- [Expiração de refresh token (7 dias em Testing)](https://www.unipile.com/google-oauth-refresh-token/) · [Google OAuth 2.0](https://developers.google.com/identity/protocols/oauth2)
- [rclone — Google Drive backend](https://rclone.org/drive/) (referência de OAuth próprio e sync)
- [ntfy vs Gotify — push self-hosted](https://www.pistack.xyz/posts/gotify-vs-ntfy-self-hosted-push-notifications/)
- [WhatsApp Business API pricing 2026](https://www.uptail.ai/blog/whatsapp-business-api-pricing-2026-what-it-costs-and-how-billing-works)
