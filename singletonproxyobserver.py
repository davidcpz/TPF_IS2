"""Servidor SingletonProxyObserver del TPFI.

Uso: python singletonproxyobserver.py {-p=port} {-v}
"""

import sys

from corporate_data_server.server import main

if __name__ == "__main__":
    sys.exit(main())
