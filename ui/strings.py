"""Strings de UI em PT-BR isoladas para futura tradução (CLAUDE.md §Stack).

Também abriga textos de notificação acionáveis (SPEC.md §4), reutilizáveis
pelo core via injeção — sem que o core importe ``ui`` (CLAUDE.md §6).

Português claro e simples: quem usa o app não conhece "reconciliação",
"checksum" nem "token". Jargão só quando não há alternativa, e explicado.
"""

from __future__ import annotations

APP_NAME = "Drive Guardian"
APP_TAGLINE = "Backup do seu Google Drive num disco seu"

# Bandeja / menu (SPEC §5)
TRAY_OPEN = "Abrir"
TRAY_CHECK_NOW = "Verificar agora"
TRAY_PAUSE = "Pausar"
TRAY_RESUME = "Retomar"
TRAY_QUIT = "Sair"

# Status
STATUS_OK = "Tudo sincronizado"
STATUS_SYNCING = "Sincronizando…"
STATUS_ACTION_NEEDED = "Ação necessária"
STATUS_PAUSED = "Pausado"
STATUS_NEVER_RAN = "Ainda não sincronizou"

# Abas
TAB_CONNECTION = "Conexão"
TAB_FOLDERS = "Pastas"
TAB_PARAMETERS = "Parâmetros"
TAB_ACTIVITY = "Atividade"

# --- Aba Conexão ------------------------------------------------------------
CONN_TITLE = "Conta do Google"
CONN_DESC = (
    "O app lê seus arquivos com uma conta de serviço do Google. "
    "Compartilhe a pasta do Drive com o e-mail abaixo para ele enxergar os arquivos."
)
CONN_STRATEGY = "Forma de acesso"
CONN_KEY_FILE = "Arquivo da chave"
CONN_KEY_CHOOSE = "Escolher arquivo…"
CONN_SA_EMAIL = "Compartilhe a pasta com este e-mail"
CONN_COPY = "Copiar"
CONN_COPIED = "E-mail copiado."
CONN_TEST = "Testar conexão"
CONN_TESTING = "Testando…"
CONN_OK = "Conexão funcionando: a conta de serviço enxerga {n} pasta(s) compartilhada(s)."
CONN_FAIL = "Não deu certo: {error}"
CONN_NO_KEY = "Nenhum arquivo de chave selecionado."
CONN_UNTESTED = "Não testado"

# --- Aba Pastas -------------------------------------------------------------
FOLDERS_TITLE = "O que copiar e para onde"
FOLDERS_DESC = "Escolha a pasta do Drive que será copiada e o disco de destino."
FOLDERS_DRIVE = "Pasta no Google Drive"
FOLDERS_DRIVE_CHOOSE = "Escolher pasta…"
FOLDERS_LOCAL = "Pasta de destino no computador"
FOLDERS_LOCAL_CHOOSE = "Escolher destino…"
FOLDERS_FREE_SPACE = "Espaço livre no destino: {free}"
FOLDERS_DISK_MISSING = "O disco do destino não está conectado."
FOLDERS_PICKER_TITLE = "Escolher pasta do Drive"
FOLDERS_PICKER_ROOT = "Pastas compartilhadas com a conta de serviço"
FOLDERS_PICKER_UP = "Voltar"
FOLDERS_PICKER_EMPTY = (
    "Nenhuma pasta encontrada. Compartilhe a pasta do Drive com o e-mail da conta "
    "de serviço (aba Conexão) e tente de novo."
)
FOLDERS_PICKER_LOADING = "Carregando…"
FOLDERS_NONE = "(nenhuma escolhida)"

# --- Aba Parâmetros ---------------------------------------------------------
PARAMS_SYNC_TITLE = "Sincronização"
PARAMS_INTERVAL = "Verificar novidades a cada"
PARAMS_INTERVAL_SUFFIX = " minutos"
PARAMS_BANDWIDTH = "Limite de velocidade"
PARAMS_BANDWIDTH_SUFFIX = " Mbps (0 = sem limite)"
PARAMS_STARTUP = "Iniciar junto com o Windows"
PARAMS_ALERTS_TITLE = "Avisos no celular"
PARAMS_NTFY_ENABLED = "Enviar avisos pelo ntfy"
PARAMS_NTFY_SERVER = "Servidor"
PARAMS_NTFY_TOPIC = "Tópico"
PARAMS_NTFY_TOPIC_HINT = "O tópico funciona como senha: use um nome longo e difícil de adivinhar."
PARAMS_SUMMARY = "Enviar resumo semanal"
PARAMS_SUMMARY_DAY = "Dia"
PARAMS_SUMMARY_HOUR = "Hora"
PARAMS_HEARTBEAT_TITLE = "Aviso se o app parar"
PARAMS_HEARTBEAT_ENABLED = "Avisar quando o backup parar de rodar (healthchecks.io)"
PARAMS_HEARTBEAT_URL = "Endereço de ping"
PARAMS_HEARTBEAT_HINT = "Configure lá o período como o intervalo acima + 15 minutos de folga."
PARAMS_TEST_ALERT = "Enviar aviso de teste"
PARAMS_TEST_SENT = "Aviso enviado. Confira o celular."
PARAMS_TEST_FAIL = "Não foi possível enviar. Veja a aba Atividade."

WEEKDAYS = [
    ("monday", "Segunda-feira"),
    ("tuesday", "Terça-feira"),
    ("wednesday", "Quarta-feira"),
    ("thursday", "Quinta-feira"),
    ("friday", "Sexta-feira"),
    ("saturday", "Sábado"),
    ("sunday", "Domingo"),
]

# --- Aba Atividade ----------------------------------------------------------
ACTIVITY_TITLE = "O que o app fez"
ACTIVITY_DESC = "Todas as movimentações ficam registradas aqui."
ACTIVITY_FILTER_ALL = "Tudo"
ACTIVITY_FILTER_INFO = "Normal"
ACTIVITY_FILTER_PROBLEM = "Problemas"
ACTIVITY_COL_TIME = "Quando"
ACTIVITY_COL_LEVEL = "Tipo"
ACTIVITY_COL_MESSAGE = "O que aconteceu"
ACTIVITY_EXPORT = "Exportar log"
ACTIVITY_EXPORTED = "Log salvo em {path}"
ACTIVITY_EMPTY = "Nada registrado ainda."
ACTIVITY_REFRESH = "Atualizar"
ACTIVITY_REFRESHED = "Atualizado às {time} — {n} registro(s)."

# Contadores do último ciclo
KPI_LAST_CYCLE = "Última verificação"
KPI_DOWNLOADED = "Baixados"
KPI_VERSIONED = "Versões guardadas"
KPI_FAILED = "Com erro"
KPI_KEPT = "Mantidos após sumirem do Drive"
KPI_NEVER = "—"

# --- Comuns -----------------------------------------------------------------
SAVE = "Salvar"
SAVED = "Configurações salvas."
SAVE_FAILED = "Não foi possível salvar: {error}"
CLOSE = "Fechar"
CANCEL = "Cancelar"
CHOOSE = "Escolher"
UNSAVED_TITLE = "Alterações não salvas"
UNSAVED_BODY = "Você mudou as configurações e ainda não salvou. Salvar agora?"

# Mensagens de ciclo mostradas na janela
CYCLE_RUNNING = "Verificando o Drive…"
CYCLE_DONE = "{downloaded} baixado(s), {versioned} versão(ões), {failed} com erro."
CYCLE_ERROR = "A verificação falhou: {error}"
