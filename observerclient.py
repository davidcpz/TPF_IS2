"""Cliente ObserverClient del TPFI.

Uso: python observerclient.py {-s=hostname} {-p=port} {-o=output.json} {-v}
"""

import sys

from corporate_data_server.observer_client import main

if __name__ == "__main__":
    sys.exit(main())
