"""Atalho para abrir a interface: ``python gui.py`` (equivale a ``python -m ui.app``).

Existe para dar um caminho único e estável ao atalho de inicialização do Windows
(ver ``ui/startup.py``) e para quem prefere clicar em vez de digitar módulo.
"""

from __future__ import annotations

from ui.app import main

if __name__ == "__main__":
    raise SystemExit(main())
