set shell := ["bash", "-cu"]

test:
    python3 -m unittest discover -s tests -v

bench:
    python3 scripts/agent_token_saver.py bench "debug failing pytest in agent prompt builder"

install target="all":
    ./install.sh {{target}}

check:
    python3 -m py_compile scripts/agent_token_saver.py
    python3 -m unittest discover -s tests -v
