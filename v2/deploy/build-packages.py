"""Build matching Windows x64 and Ubuntu Pi-FIDS release kits."""
import argparse
from importlib.metadata import distribution
from pathlib import Path
import re
import shutil
import tarfile
import tempfile
import zipfile

V2 = Path(__file__).resolve().parents[1]
SETUP = V2 / 'deploy/windows/setup'
UBUNTU = V2 / 'deploy/ubuntu'

WINDOWS_SCRIPTS = {
    'Manager': ('Initialize-Manager.py', 'Install-Manager.cmd', 'Install-Manager.ps1',
                'Run-Manager.pyw', 'Open-Manager.ps1', 'Prepare-Display.cmd',
                'Prepare-Display.ps1', 'Prepare-Recovery.ps1', 'Start-Recovered-Manager.ps1',
                'Backup-Recovery-ja-en.md'),
    'Display': ('Install-Display.cmd', 'Install-Display.ps1', 'Run-Receiver.pyw',
                'Open-Display.ps1', 'Hide-Taskbar.ps1', 'Update-DisplayStartup.cmd',
                'Update-DisplayStartup.ps1'),
}


def populate(root, role, download_files):
    shutil.copytree(V2 / 'pifids', root / 'v2/pifids',
                    ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    if role == 'Manager':
        (root / 'downloads').mkdir()
        for file in download_files:
            shutil.copy2(file, root / 'downloads')


def ubuntu(output, role, version, displays=()):
    name = f'Pi-FIDS-{role}-{version}-ubuntu'
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary) / name
        populate(root, role, displays)
        for name_in in ('install.py', 'launch.py'):
            shutil.copy2(UBUNTU / name_in, root)
        shutil.copy2(UBUNTU / (role.lower()+'.html'), root / 'START-HERE.html')
        (root / 'ROLE').write_text(role.lower(), encoding='utf-8')
        path = output / (name + '.tar.gz')
        with tarfile.open(path, 'w:gz') as archive:
            archive.add(root, arcname=root.name)
    return path


def windows(output, role, version, runtime, displays=()):
    import tzdata
    path = output / f'Pi-FIDS-{role}-{version}-win-x64.zip'
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        populate(root, role, displays)
        for filename in WINDOWS_SCRIPTS[role]:
            shutil.copy2(SETUP / filename, root)
        shutil.copy2(SETUP / 'START-HERE.html', root)
        shutil.copytree(Path(tzdata.__file__).parent, root/'v2/tzdata',
                        ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
        metadata = distribution('tzdata')
        with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as archive:
            for entry in metadata.files or ():
                if 'licenses' in entry.parts:
                    archive.write(metadata.locate_file(entry), 'licenses/tzdata/' + entry.name)
            for file in sorted(root.rglob('*')):
                if file.is_file():
                    archive.write(file, file.relative_to(root).as_posix())
            with zipfile.ZipFile(runtime) as embedded:
                if not {'python.exe','pythonw.exe'} <= set(embedded.namelist()):
                    raise ValueError('Use the official Windows x64 embeddable Python ZIP')
                for entry in embedded.infolist():
                    if entry.is_dir():
                        continue
                    name = Path(entry.filename)
                    if name.is_absolute() or '..' in name.parts:
                        raise ValueError('Invalid Windows runtime archive')
                    value = embedded.read(entry)
                    if name.suffix == '._pth':
                        value += b'\n..\\v2\n'
                    archive.writestr('runtime/'+name.as_posix(), value)
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--windows-runtime', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--version', required=True)
    args = parser.parse_args()
    if not re.fullmatch('[A-Za-z0-9.-]+',args.version):
        parser.error('Use a version containing letters, digits, dots or hyphens')
    args.output.mkdir(parents=True, exist_ok=True)
    output, version = args.output, args.version
    win = windows(output, 'Display', version, args.windows_runtime)
    linux = ubuntu(output, 'Display', version)
    for path in (win, linux, windows(output,'Manager',version,args.windows_runtime,(win,linux)),
                 ubuntu(output,'Manager',version,(win,linux))):
        print(path)


if __name__ == '__main__':
    main()
