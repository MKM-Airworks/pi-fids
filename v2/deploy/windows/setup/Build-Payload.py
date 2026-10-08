"""Build a credential-free Windows setup payload from a verified runtime ZIP.
Run with a Python environment containing tzdata; compile with Build-Installer.ps1.
"""
import argparse
import importlib.metadata
import importlib.util
from pathlib import Path
import tempfile
import shutil
import zipfile
parser=argparse.ArgumentParser()
parser.add_argument('--runtime',required=True)
parser.add_argument('--output',required=True)
args=parser.parse_args()
setup=Path(__file__).resolve().parent
source=setup.parents[2]/'pifids'
with tempfile.TemporaryDirectory() as temporary:
    root=Path(temporary)
    for path in setup.iterdir():
        if path.is_file() and path.suffix in ('.ps1','.py','.pyw','.cmd','.md'):
            shutil.copy2(path,root/path.name)
    with zipfile.ZipFile(args.runtime) as archive:
        for item in archive.infolist():
            relative=Path(item.filename.replace('\\','/'))
            if relative.is_absolute() or '..' in relative.parts or relative.parts[0]!='runtime':
                raise ValueError('Runtime archive must contain only runtime/ files')
            if not item.is_dir():
                target=root/relative;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(archive.read(item))
    if not (root/'runtime/pythonw.exe').exists():raise ValueError('Windows runtime missing')
    shutil.copytree(source,root/'v2/pifids',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    spec=importlib.util.find_spec('tzdata')
    if not spec:raise ValueError('Install tzdata in the build environment')
    shutil.copytree(Path(spec.origin).parent,root/'v2/tzdata',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    distribution=importlib.metadata.distribution('tzdata')
    for name in distribution.files or []:
        if 'licenses' in name.parts:
            path=Path(distribution.locate_file(name))
            if path.is_file():
                target=root/'licenses/tzdata'/path.name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target)
    with zipfile.ZipFile(args.output,'w',zipfile.ZIP_DEFLATED) as archive:
        for path in root.rglob('*'):
            if path.is_file():archive.write(path,path.relative_to(root))
print('Credential-free setup payload created')
