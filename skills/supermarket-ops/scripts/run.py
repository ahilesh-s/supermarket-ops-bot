"""Forward to this skill's explicitly bound local store, without shell evaluation."""
import json
import os
from pathlib import Path
import subprocess
import sys


def main():
    binding = Path(__file__).resolve().parents[1] / 'runtime.json'
    if not binding.is_file():
        raise SystemExit('Missing runtime.json. Run the repository skill installer first.')
    config = json.loads(binding.read_text())
    env = {**os.environ, 'SUPERMARKET_DATA_DIR': config['data_dir']}
    return subprocess.run([config['python'], '-m', 'abi_store', *sys.argv[1:]],
                          cwd=config['project_dir'], env=env).returncode


if __name__ == '__main__':
    raise SystemExit(main())
