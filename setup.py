"""
usage:
    python setup.py
"""

import os
import sys
import zipfile
import subprocess

ROOT     = os.path.dirname(os.path.abspath(__file__))
ZIP_PATH = os.path.join(ROOT, 'data.zip')
DATA_DIR = os.path.join(ROOT, 'data')

EXPECTED_FILES = [
    'toy_cases.jsonl',
    'toy_cases.json',
    'legimap_1M.json',
    'legimap_1M.jsonl'
]


def check_zip():
    if not os.path.exists(ZIP_PATH):
        print('data.zip not found in the project root.')
        print('    Download it from the repo releases page and place it here:')
        print(f'    {ZIP_PATH}')
        sys.exit(1)
    size_mb = os.path.getsize(ZIP_PATH) / 1024**2
    print(f'Found data.zip  ({size_mb:.1f} MB)')


def extract():
    os.makedirs(DATA_DIR, exist_ok=True)
    print(f'Extracting to {DATA_DIR}/ ...')
    with zipfile.ZipFile(ZIP_PATH, 'r') as zf:
        members = zf.namelist()
        for member in members:
            target_name = member
            if member.startswith('data/'):
                target_name = member[len('data/'):]
            if not target_name:
                continue
            target_path = os.path.join(DATA_DIR, target_name)
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            with zf.open(member) as src, open(target_path, 'wb') as dst:
                dst.write(src.read())
            print(f'  extracted: {target_name}')
    print(f'Extracted {len(members)} files')


def verify():
    print('Verifying expected files ...')
    missing = []
    for fname in EXPECTED_FILES:
        path = os.path.join(DATA_DIR, fname)
        if os.path.exists(path):
            size_kb = os.path.getsize(path) / 1024
            print(f' {fname}  ({size_kb:.0f} KB)')
        else:
            print(f' {fname}  — NOT FOUND')
            missing.append(fname)

    if missing:
        print(f'\n{len(missing)} expected file(s) missing from data.zip.')
        print('   The app may still work if legimap_1M.jsonl is present.')
    else:
        print('All expected files present')


def install_deps():
    req = os.path.join(ROOT, 'requirements.txt')
    if not os.path.exists(req):
        print('requirements.txt not found — skipping dependency install')
        return
    print('\nInstalling dependencies ...')
    result = subprocess.run(
        [sys.executable, '-m', 'pip', 'install', '-r', req, '-q'],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        print('Dependencies installed')
    else:
        print('pip install had warnings/errors:')
        print(result.stderr[:400])


if __name__ == '__main__':
    print('LegiMap — Setup\n' + '=' * 40)
    check_zip()
    extract()
    verify()
    install_deps()
    print('\n' + '=' * 40)
    print('Setup complete. To run the app:')
    print('  PYTHONPATH=. python src/api/app.py')
    print('\nTo run the demo notebook:')
    print('  PYTHONPATH=. jupyter notebook demo_notebook.ipynb')
