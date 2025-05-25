# -*- mode: python ; coding: utf-8 -*-
specpath = os.path.dirname(os.path.abspath(SPEC))

def get_version():
    version_dict = {}
    # Path to version.py, assuming build.spec is at the project root
    # and version.py is in src/
    version_file_path = os.path.join(specpath, "src", "version.py")
    with open(version_file_path) as f:
        exec(f.read(), version_dict)
    return version_dict['__version__']

VERSION = get_version()

a = Analysis(
    ["src/main.py"], # Path to your main script
    pathex=["src"],     # Add 'src' to module search path
    binaries=[
      ('src/softcam/', './softcam/')
    ],
    datas=[
        ('src/resources/', './resources/'), # Bundles the resources folder
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe_obj = EXE(
    pyz,
    a.scripts,
    [], # Let COLLECT handle datas primarily for onedir
    name='VCM', # Name of the executable
    debug=False,
    exclude_binaries=True,
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
    icon=os.path.join(specpath, 'src/resources/logo.ico') # Icon for the executable
)

# COLLECT stage for one-dir build
# This creates a folder named 'VCM-{VERSION}' in the 'dist' directory
coll = COLLECT(
    exe_obj,            # The EXE object created above
    a.binaries,         # Collect any binaries discovered by Analysis
    a.datas,            # Collect any datas discovered by Analysis
    name=f'VCM-{VERSION}' # This will be the name of the output folder in dist/
)
