[app]
title = Orcamentos JM
package.name = orcamentosjm
package.domain = br.com.jmservicos
source.dir = .
source.include_exts = py,png,jpg,jpeg,kv,atlas,json,ttf
source.exclude_patterns = _test_*.py,_t2.py,_t3.py,_saida_teste.pdf,vis_*.png,limpo_*.png,iso_*.png,_shot_*.png,dados_orcamentosjm/*
version = 1.0
requirements = python3,kivy==2.3.0,kivymd==1.1.1,pillow,reportlab,plyer,android
orientation = portrait
fullscreen = 0

# Ícone e tela de abertura
icon.filename = %(source.dir)s/data/icon.png
presplash.filename = %(source.dir)s/data/presplash.png
android.presplash_color = #4C6FD0

# Configuração do Android
android.api = 33
android.minapi = 21
android.archs = arm64-v8a
android.accept_sdk_license = True
android.permissions = INTERNET, WRITE_EXTERNAL_STORAGE, READ_EXTERNAL_STORAGE

[buildozer]
log_level = 2
warn_on_root = 0
