# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files
from PyInstaller.utils.hooks import copy_metadata
#import site
import platform

#site_packages_path = site.getsitepackages()
datas = [('img/dpsg_logo.png', 'img'), ('img/favicon.ico', 'img'), ('img/favicon.icns', 'img')]
#datas.append((f'{site_packages_path[1]}/schwifty/bank_registry/', 'bank_registry'))
#datas.append((f'{site_packages_path[1]}/schwifty/iban_registry/', 'iban_registry'))
datas += collect_data_files('sv_ttk')
datas += collect_data_files('pycountry')
datas += collect_data_files('schwifty')
datas += copy_metadata('schwifty')


block_cipher = None

if platform.system() == "Windows":
    iconPath = 'img/favicon.ico'
else:
    iconPath = 'img/favicon.icns'

a = Analysis(
    ['src//main.py'],
    pathex=['//src'],
    binaries=[],
    datas=datas,
    hiddenimports=['babel.numbers'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='Nami Beitragsrechner',
    debug=False,
    manifest=None,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    entitlements_file=None,
    icon=iconPath,
)
app = BUNDLE(
    exe,
    name='Nami Beitragsrechner.app',
    icon=iconPath,
    bundle_identifier='com.dpsg.nami-beitragsrechner',
)
