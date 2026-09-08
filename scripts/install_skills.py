"""Install only this project's skills into the selected Hermes home."""
import argparse
import json
import os
from pathlib import Path
import shutil
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--hermes-home', type=Path,
                        default=Path(os.environ.get('HERMES_HOME', Path.home() / '.hermes')))
    parser.add_argument('--data-dir', type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    home = args.hermes_home.expanduser().resolve()
    data = args.data_dir.expanduser().resolve()
    sources = sorted((root / 'skills').iterdir())
    targets = [(source, home / 'skills' / source.name) for source in sources if source.is_dir()]
    for source, target in targets:
        if target.exists() or target.is_symlink():
            parser.error(f'Skill already exists: {target}. Review and back it up before replacing it.')
    # No provider configuration, credentials, SOUL, other profiles or databases are changed.
    for source, target in targets:
        shutil.copytree(source, target)
        config = {'python': sys.executable, 'project_dir': str(root), 'data_dir': str(data)}
        (target / 'runtime.json').write_text(json.dumps(config, indent=2) + '\n')
        print(f'Installed {target.name}: {target}')
    print('Start a new Hermes session to load the installed skills.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
