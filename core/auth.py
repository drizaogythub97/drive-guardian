"""Autenticação com o Google Drive — duas estratégias, mesma interface
(CLAUDE.md §Autenticação). Escopo mínimo: ``drive.readonly``.

- :class:`ServiceAccountAuth` (padrão pessoal): JSON da conta de serviço.
- :class:`UserOAuthAuth` (terceiros, Fase 4): fluxo desktop OAuth — stub por ora.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from pathlib import Path

from google.oauth2.service_account import Credentials as ServiceAccountCredentials

from core.config import AuthConfig
from core.errors import AuthError

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]


class Auth(ABC):
    """Interface comum de autenticação."""

    @abstractmethod
    def credentials(self) -> object:
        """Retorna credenciais google-auth prontas para uso pela Drive API."""

    @abstractmethod
    def account_label(self) -> str:
        """Rótulo legível da conta (ex.: e-mail da SA) para exibir na UI/CLI."""


class ServiceAccountAuth(Auth):
    """Autentica via JSON de conta de serviço compartilhada com a pasta do Drive."""

    def __init__(self, key_path: str | Path) -> None:
        self._key_path = Path(key_path)
        self._email = self._read_client_email()

    def _read_client_email(self) -> str:
        if not self._key_path.is_file():
            raise AuthError(
                f"auth: chave da conta de serviço não encontrada: {self._key_path}. "
                "Baixe o JSON no Google Cloud Console e ajuste auth.service_account_key."
            )
        try:
            data = json.loads(self._key_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            raise AuthError(f"auth: JSON da conta de serviço inválido: {exc}") from exc
        email = data.get("client_email")
        if not email:
            raise AuthError("auth: JSON da conta de serviço sem 'client_email'")
        return str(email)

    def credentials(self) -> object:
        try:
            creds = ServiceAccountCredentials.from_service_account_file(  # type: ignore[no-untyped-call]
                str(self._key_path), scopes=SCOPES
            )
        except Exception as exc:
            raise AuthError(
                f"auth: falha ao carregar credenciais da conta de serviço: {exc}"
            ) from exc
        return creds

    def account_label(self) -> str:
        return self._email


class UserOAuthAuth(Auth):
    """Fluxo OAuth de usuário (Fase 4). Ainda não implementado."""

    def credentials(self) -> object:
        raise AuthError("auth: estratégia user_oauth ainda não implementada (Fase 4)")

    def account_label(self) -> str:
        raise AuthError("auth: estratégia user_oauth ainda não implementada (Fase 4)")


def build_auth(config: AuthConfig) -> Auth:
    """Fábrica: monta a estratégia de autenticação a partir da config."""
    if config.strategy == "service_account":
        if config.service_account_key is None:  # já validado em config, defensivo
            raise AuthError("auth: service_account_key ausente na config")
        return ServiceAccountAuth(config.service_account_key)
    if config.strategy == "user_oauth":
        return UserOAuthAuth()
    raise AuthError(f"auth: estratégia desconhecida: {config.strategy}")
