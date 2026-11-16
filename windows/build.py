"""Build the credential-free Windows kits and Ubuntu display kit for Render."""
import io
from importlib.metadata import distribution
from pathlib import Path
import shutil
import tarfile
import tempfile
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
VERSION = 'v2-b01ef1c'
PYTHON = '3.13.17'
RUNTIME_URL = f'https://www.python.org/ftp/python/{PYTHON}/python-{PYTHON}-embed-amd64.zip'
OUTPUT = ROOT / 'dist'
DISPLAY = f'Pi-FIDS-Display-{VERSION}-win-x64.zip'
MANAGER = f'Pi-FIDS-Manager-{VERSION}-win-x64.zip'
UBUNTU = f'Pi-FIDS-Display-{VERSION}-ubuntu'


def ubuntu_display():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / UBUNTU
        shutil.copytree(ROOT/'pifids', root/'v2/pifids',
                        ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
        for filename in ('install.py','launch.py'):
            shutil.copy2(ROOT/'ubuntu'/filename, root)
        shutil.copy2(ROOT/'ubuntu/display.html', root/'START-HERE.html')
        (root/'ROLE').write_text('display', encoding='utf-8')
        with tarfile.open(OUTPUT/(UBUNTU+'.tar.gz'), 'w:gz') as archive:
            archive.add(root, arcname=root.name)


def build():
    import tzdata

    OUTPUT.mkdir(exist_ok=True)
    ubuntu_display()
    with urllib.request.urlopen(RUNTIME_URL, timeout=60) as response:
        runtime_bytes = response.read()
    setup = ROOT / 'windows' / 'setup'
    tz_root = Path(tzdata.__file__).parent
    manager_only = {
        'Backup-Recovery-ja-en.md', 'Initialize-Manager.py', 'Install-Manager.cmd',
        'Install-Manager.ps1', 'Open-Manager.ps1', 'Prepare-Display.cmd',
        'Prepare-Display.ps1', 'Prepare-Recovery.ps1', 'Run-Manager.pyw',
        'Start-Recovered-Manager.ps1',
    }
    display_only = {
        'Hide-Taskbar.ps1', 'Install-Display.cmd', 'Install-Display.ps1',
        'Open-Display.ps1', 'Run-Receiver.pyw', 'Update-DisplayStartup.cmd',
        'Update-DisplayStartup.ps1',
    }
    for role, filename, scripts in (
        ('display', DISPLAY, display_only), ('manager', MANAGER, manager_only),
    ):
        target = OUTPUT / filename
        with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as archive:
            with zipfile.ZipFile(io.BytesIO(runtime_bytes)) as runtime:
                for name in runtime.namelist():
                    value = runtime.read(name)
                    if name.endswith('._pth'):
                        value += b'\n..\\v2\n'
                    archive.writestr('runtime/' + name, value)
            for directory, prefix in ((ROOT / 'pifids', 'v2/pifids'), (tz_root, 'v2/tzdata')):
                for path in sorted(directory.rglob('*')):
                    if path.is_file() and '__pycache__' not in path.parts:
                        archive.write(path, f'{prefix}/{path.relative_to(directory).as_posix()}')
            tz_dist = distribution('tzdata')
            for entry in tz_dist.files or ():
                if 'licenses' in entry.parts:
                    archive.write(tz_dist.locate_file(entry), 'licenses/tzdata/' + entry.name)
            for name in sorted(scripts):
                archive.write(setup / name, name)
            archive.write(ROOT / 'windows' / f'{role}-guide.html', 'START-HERE.html')
            if role == 'manager':
                archive.write(OUTPUT / DISPLAY, 'downloads/' + DISPLAY)
                archive.write(OUTPUT / (UBUNTU+'.tar.gz'), 'downloads/' + UBUNTU + '.tar.gz')
        with zipfile.ZipFile(target) as archive:
            if archive.testzip() is not None or 'runtime/pythonw.exe' not in archive.namelist():
                raise ValueError(f'Invalid Windows package: {target.name}')
        print(target)


if __name__ == '__main__':
    build()
