# -*- mode: python ; coding: utf-8 -*-
specpath = os.path.dirname(os.path.abspath(SPEC))

def get_version():
    # Read version from a version.py file (we'll create this)
    version_dict = {}
    with open("src/version.py") as f:
        exec(f.read(), version_dict)
    return version_dict['__version__']

a = Analysis(
    ['src\\main.py'],
    pathex=[],
    binaries=[],
    datas=[('src/resources/', './resources')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name=f'VCM-v{get_version()}',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(specpath, 'src/resources/logo.ico'),
    i=os.path.join(specpath, 'src/resources/logo.ico'),
)
