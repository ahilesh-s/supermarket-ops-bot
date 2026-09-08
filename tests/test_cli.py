import json
import os
from pathlib import Path
import subprocess
import sys


def run_cli(tmp_path, *args, data=None):
    return subprocess.run([sys.executable, '-m', 'abi_store', *args],
                          env={**os.environ, 'SUPERMARKET_DATA_DIR': str(tmp_path)},
                          input=data, capture_output=True, text=True)


def test_init_and_stock_workflow(tmp_path):
    result = run_cli(tmp_path, 'init', '--shop-name', 'Demo Market')
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)['ok'] is True
    payload = json.dumps(dict(sku='DEMO-1', name='Demo Rice', unit='kg', hsn_code='1006',
                              gst_rate=0, cost_price=40, mrp=50))
    denied = run_cli(tmp_path, 'call', 'inventory.add_product', '--json', payload)
    assert denied.returncode != 0
    assert 'confirm' in denied.stderr.lower()
    accepted = run_cli(tmp_path, 'call', 'inventory.add_product', '--confirm', '--json', payload)
    assert accepted.returncode == 0, accepted.stderr
    found = run_cli(tmp_path, 'call', 'inventory.resolve_product', data='{"query":"Demo Rice"}')
    assert found.returncode == 0, found.stderr
    assert json.loads(found.stdout)['result']['sku'] == 'DEMO-1'


def test_arbitrary_function_rejected(tmp_path):
    result = run_cli(tmp_path, 'call', 'os.system', '--json', '{"command":"anything"}')
    assert result.returncode != 0
    assert 'Unknown operation' in result.stderr


def test_invalid_json_returns_clean_error(tmp_path):
    result = run_cli(tmp_path, 'call', 'inventory.resolve_product', data='[]')
    assert result.returncode != 0
    assert 'JSON object' in result.stderr
