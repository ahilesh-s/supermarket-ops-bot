import json
import os
from pathlib import Path
import subprocess
import sys


def test_demo_creates_real_artifacts_and_refuses_reuse(tmp_path):
    output = tmp_path / 'demo'
    command = [sys.executable, 'examples/demo.py', '--output', str(output)]
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert data['sample_data'] is True
    assert data['bill']['payable'] == 100
    assert Path(data['invoice']).read_bytes().startswith(b'%PDF')
    assert Path(data['deck']).read_bytes().startswith(b'PK')
    from pptx import Presentation
    from pypdf import PdfReader
    assert len(Presentation(data['deck']).slides) >= 4
    assert 'Demonstration Market' in '\n'.join(page.extract_text() for page in PdfReader(data['invoice']).pages)
    second = subprocess.run(command, capture_output=True, text=True)
    assert second.returncode != 0
    assert 'already exists' in second.stderr
