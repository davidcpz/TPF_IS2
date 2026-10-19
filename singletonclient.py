"""Cliente SingletonClient del TPFI.

Uso: python singletonclient.py -i=input.json {-o=output.json} {-v}
"""

import sys

from corporate_data_server.singleton_client import main

if __name__ == "__main__":
    sys.exit(main())
