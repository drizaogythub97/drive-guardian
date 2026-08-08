# Drive Guardian — Checklist de preparação (manual, antes de codificar)

Tudo abaixo é **gratuito e sem cartão de crédito**. Tempo total: ~25 min. Marque conforme concluir.

## A. Google Cloud + Conta de Serviço (~10 min)

- [x] Acessar [console.cloud.google.com](https://console.cloud.google.com) com sua conta Google.
- [x] Criar projeto novo: `drive-guardian` (não requer billing).
- [x] Menu **APIs e serviços → Biblioteca** → buscar **Google Drive API** → **Ativar**.
- [x] **IAM e administrador → Contas de serviço → Criar conta de serviço**: nome `drive-guardian-sa` (sem papéis/roles — não precisa).
- [x] Na conta criada: **Chaves → Adicionar chave → JSON** → baixar o arquivo. Guardar em local seguro (será o `secrets/sa-key.json`; **nunca** vai para o GitHub).
- [x] Copiar o e-mail da conta de serviço (formato `drive-guardian-sa@....iam.gserviceaccount.com`).
- [x] No **Google Drive**, na pasta das memórias: **Compartilhar** → colar o e-mail da SA → papel **Leitor**.
- [x] Anotar o **ID da pasta** (na URL do Drive: `folders/<ESTE-ID>`).

## B. ntfy — alertas no celular (~5 min)

- [x] Instalar o app **ntfy** (Play Store / App Store).
- [x] Criar/assinar um tópico com nome impossível de adivinhar (o nome é a "senha"), ex.: `drive-guardian-a8f3k2m9x7`.
- [x] Testar no navegador do PC: `https://ntfy.sh/<seu-topico>` → publicar mensagem → deve chegar no celular.
- [x] Anotar o nome do tópico.

## C. healthchecks.io — vigia do vigia (~5 min)

- [x] Criar conta gratuita em [healthchecks.io](https://healthchecks.io) (free: 20 checks; usaremos 1).
- [x] Criar check `drive-guardian`: **Period** = 45 min, **Grace** = 30 min (ajustaremos se mudar o intervalo).
- [x] Em **Integrations**, adicionar notificação por **e-mail** (imediato) — depois integraremos ao ntfy via webhook.
- [x] Anotar a **URL de ping** (`https://hc-ping.com/<uuid>`).

## D. Máquina e repositório (~5 min)

- [x] Instalar **Python 3.12+** ([python.org](https://www.python.org/downloads/), marcar "Add to PATH") — verificar: `python --version`.
- [x] Instalar **Git** ([git-scm.com](https://git-scm.com)) — verificar: `git --version`.
- [x] Criar repositório **`drive-guardian`** no GitHub (público, licença MIT, sem README inicial — o Claude Code cria).
- [x] Conectar o disco físico de destino e anotar o caminho (ex.: `E:\BackupDrive`).

## E. Informações a ter em mãos na 1ª sessão do Claude Code

> ✅ Preenchido em `secrets/valores.md` (fora do git — este arquivo aqui é público).

## F. Prompt de partida (colar no Claude Code, na pasta do repo clonado + CLAUDE.md e SPEC.md copiados para lá)

> Leia CLAUDE.md e SPEC.md. Execute a **Fase 0**: esqueleto do repositório conforme SPEC §7, config.example.yaml conforme SPEC §1, schema SQLite conforme SPEC §2, logging, autenticação por conta de serviço e o comando `python cli.py list` imprimindo a árvore da pasta do Drive. Critério de aceite: SPEC §6-F0. Não avance para a Fase 1 sem eu validar.
