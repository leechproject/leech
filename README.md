# leech

> [!WARNING]
> IN EARLY STAGE OF DEVELOPMENT

for now, this dotfiles have only Hyprland, Niri and MangoWM support.

### necessary (Arch Linux)
* python
* python-gobject
* python-cairo
* gtk3
* gtk-layer-shell
* python-fabric-git (AUR)(TESTED ON r249.e8162e4)
* otf-font-awesome

### optional (for additional functions)
* wpctl or pactl
* brightnessctl
* grim
* gpu-screen-recorder
* mpv & libmpv
* webp-pixbuf-loader
* power-profiles-daemon
* bluez
* glib2

### CTL USAGE
```
# leectl = <projectdir>/main/ctl.py
# available values
leectl toggle:
cc
cc-full
launcher
wallpaper
battery
power
player

leectl apps [query]
leectl pin | unpin [apps]
leectl pins 
leectl volume up | down
leectl brightness up | down
leectl stats
leectl reload
```
### install
```sh
git clone https://github.com/leechproject/leech ~/.config/leech
```
### launch
```sh
python ~/.config/leech/main/main.py
```
> [!IMPORTANT]
> you need to reload this shell to apply configuration changes
