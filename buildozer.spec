[app]
title = Twitch Clipper
package.name = twitchclipper
package.domain = com.errorpromts
source.dir = .
source.include_exts = py
version = 1.0

requirements = python3,kivy

orientation = portrait
fullscreen = 1
android.permissions = WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE

android.api = 33
android.minapi = 24
android.ndk = 28c

p4a.bootstrap = sdl2

[buildozer]
log_level = 2
warn_on_root = 0
