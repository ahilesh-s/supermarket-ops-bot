import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def test_skill_install_and_bound_runner(tmp_path):
    home = tmp_path / 'profile'
    data = tmp_path / 'store'
    args = [sys.executable, str(ROOT / 'scripts/install_skills.py'),
            '--hermes-home', str(home), '--data-dir', str(data)]
    result = subprocess.run(args, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    installed = home / 'skills/supermarket-ops'
    assert (installed / 'SKILL.md').is_file()
    cfg = json.loads((installed / 'runtime.json').read_text())
    assert cfg['data_dir'] == str(data)
    # Even conflicting inherited state must not select another shop.
    result = subprocess.run([sys.executable, str(installed / 'scripts/run.py'), 'init'],
                            env={**os.environ, 'SUPERMARKET_DATA_DIR': str(tmp_path / 'wrong')},
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert (data / 'database/stock.db').is_file()
    assert not (tmp_path / 'wrong/database/stock.db').exists()
    # No silent overwriting of an installed skill.
    again = subprocess.run(args, capture_output=True, text=True)
    assert again.returncode != 0
    assert 'already exists' in again.stderr


def test_skill_metadata():
    import yaml
    skills = sorted((ROOT / 'skills').glob('*/SKILL.md'))
    assert len(skills) >= 2
    for file in skills:
        front = yaml.safe_load(file.read_text().split('---', 2)[1])
        assert front['name'] == file.parent.name
        assert len(front['description']) <= 60
        assert front['description'].endswith('.')
        assert 'AHILESH' in front['author']
        assert '/home/' not in file.read_text()
