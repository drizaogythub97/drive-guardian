"""Iniciar com o Windows: chave ``HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run``
(SPEC.md §5, aba Parâmetros).

Fica em ``HKCU`` de propósito: não exige privilégio de administrador e vale só para
o usuário atual. Nada de serviço do Windows — o app é de bandeja.

Sem Qt aqui, o que torna este módulo testável sem abrir janela. Em sistemas não
Windows as funções viram no-op para o resto da UI não precisar de ``if``.
"""

from __future__ import annotations

import sys
from pathlib import Path

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "DriveGuardian"


def is_supported() -> bool:
    return sys.platform == "win32"


def launch_command(config_path: str | Path | None = None) -> str:
    """Comando que o Windows executará no login.

    Empacotado (PyInstaller, Fase 4) o próprio executável basta; rodando do fonte,
    aponta para o ``pythonw.exe`` do ambiente para não abrir janela de console.
    """
    if getattr(sys, "frozen", False):
        command = f'"{sys.executable}"'
    else:
        interpreter = Path(sys.executable)
        windowless = interpreter.with_name("pythonw.exe")
        exe = windowless if windowless.exists() else interpreter
        entry = Path(__file__).resolve().parent.parent / "gui.py"
        command = f'"{exe}" "{entry}"'

    if config_path:
        command += f' --config "{config_path}"'
    return command


def is_enabled() -> bool:
    """A entrada de inicialização existe?"""
    if not is_supported():
        return False
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            winreg.QueryValueEx(key, VALUE_NAME)
    except FileNotFoundError:
        return False
    except OSError:
        return False
    return True


def enable(config_path: str | Path | None = None) -> bool:
    """Cria/atualiza a entrada. Retorna ``True`` se ficou ligada."""
    if not is_supported():
        return False
    import winreg

    try:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            winreg.SetValueEx(
                key, VALUE_NAME, 0, winreg.REG_SZ, launch_command(config_path)
            )
    except OSError:
        return False
    return True


def disable() -> bool:
    """Remove a entrada. Retorna ``True`` se ela não existe mais."""
    if not is_supported():
        return False
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, VALUE_NAME)
    except FileNotFoundError:
        return True  # já não estava lá
    except OSError:
        return False
    return True


def set_enabled(enabled: bool, config_path: str | Path | None = None) -> bool:
    return enable(config_path) if enabled else disable()
