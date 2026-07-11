from dictate.network import install_runtime_network_policy

install_runtime_network_policy()

from dictate.__main__ import main

if __name__ == "__main__":
    raise SystemExit(main())
