# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['C:\\Users\\makito akatsu\\Dropbox\\001_(株)ACE総合コンサル\\01_物件\\09_AZRAS\\00_技術放流\\Platform\\core\\AZRAS_Platform_Core_v3_3_0_Regional_Project_Generator_build_kit\\main.py'],
    pathex=[],
    binaries=[],
    datas=[('C:\\Users\\makito akatsu\\Dropbox\\001_(株)ACE総合コンサル\\01_物件\\09_AZRAS\\00_技術放流\\Platform\\core\\AZRAS_Platform_Core_v3_3_0_Regional_Project_Generator_build_kit\\lang', 'lang'), ('C:\\Users\\makito akatsu\\Dropbox\\001_(株)ACE総合コンサル\\01_物件\\09_AZRAS\\00_技術放流\\Platform\\core\\AZRAS_Platform_Core_v3_3_0_Regional_Project_Generator_build_kit\\data', 'data')],
    hiddenimports=['cv2', 'fitz', 'PIL'],
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
    [],
    exclude_binaries=True,
    name='AZRAS_Platform_Core_v3_3_0',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='AZRAS_Platform_Core_v3_3_0',
)
