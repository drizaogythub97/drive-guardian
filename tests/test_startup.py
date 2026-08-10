"""Entrada de inicialização do Windows (``HKCU\\...\\Run``).

Os testes que mexem no registro salvam e devolvem o valor anterior — a máquina do
dono pode ter a inicialização ligada de verdade, e um teste não pode desligá-la.
Fora do Windows tudo vira no-op e é isso que se verifica.
"""

from __future__ import annotations

import sys
from collections.abc import Iterator

import pytest

from ui import startup


def test_launch_command_points_to_the_app() -> None:
    command = startup.launch_command()
    assert command.startswith('"')
    assert "gui.py" in command or command.count('"') == 2  # fonte ou executável


def test_launch_command_includes_config_when_given() -> None:
    assert '--config "C:\\dg\\config.yaml"' in startup.launch_command(r"C:\dg\config.yaml")


def test_launch_command_avoids_console_window(monkeypatch: pytest.MonkeyPatch) -> None:
    """Rodando do fonte deve preferir pythonw.exe: senão abre um console no login."""
    if not startup.is_supported():
        pytest.skip("só faz sentido no Windows")
    command = startup.launch_command()
    assert "pythonw.exe" in command or "python.exe" in command


@pytest.mark.skipif(sys.platform == "win32", reason="caminho de sistema não Windows")
def test_no_op_outside_windows() -> None:
    assert startup.is_supported() is False
    assert startup.is_enabled() is False
    assert startup.enable() is False
    assert startup.disable() is False


@pytest.fixture
def preserve_registry() -> Iterator[None]:
    """Guarda o estado real da chave e restaura ao final."""
    if not startup.is_supported():
        yield
        return
    import winreg

    previous: str | None = None
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, startup.RUN_KEY) as key:
            previous = str(winreg.QueryValueEx(key, startup.VALUE_NAME)[0])
    except OSError:
        previous = None

    yield

    if previous is None:
        startup.disable()
    else:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, startup.RUN_KEY) as key:
            winreg.SetValueEx(key, startup.VALUE_NAME, 0, winreg.REG_SZ, previous)


@pytest.mark.skipif(sys.platform != "win32", reason="registro só existe no Windows")
def test_enable_disable_round_trip(preserve_registry: None) -> None:
    assert startup.enable() is True
    assert startup.is_enabled() is True
    assert startup.disable() is True
    assert startup.is_enabled() is False


@pytest.mark.skipif(sys.platform != "win32", reason="registro só existe no Windows")
def test_disable_is_idempotent(preserve_registry: None) -> None:
    startup.disable()
    assert startup.disable() is True  # já não estava lá: sucesso, não erro


@pytest.mark.skipif(sys.platform != "win32", reason="registro só existe no Windows")
def test_set_enabled_matches_enable_disable(preserve_registry: None) -> None:
    startup.set_enabled(True)
    assert startup.is_enabled() is True
    startup.set_enabled(False)
    assert startup.is_enabled() is False
