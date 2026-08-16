#!/usr/bin/env python3
"""
mini-IDM masaustu uygulamasi.

Sunucuyu arka planda baslatir, tarayici cercevesi olmayan (adres cubugu ve
sekme yok) native bir pencere acar, sistem tepsisinde kalir. Pencerenin X
tusuna basmak uygulamayi kapatmaz - IDM'in calisma bicimi bu: indirmeleri
yakalayabilmesi icin arka planda surekli acik kalmasi gerekiyor. Tamamen
kapatmak icin tepsi menusunden "Cikis".

Calistir:  pythonw app.py            (konsol penceresi acilmaz)
           pythonw app.py --hidden   (Windows acilisinda: pencere gostermeden,
                                       sadece tepside baslar)
           python app.py             (hata ayiklarken konsollu calistirmak icin)
"""
import os
import sys
import threading
import time
import webbrowser

import pystray
import webview
from PIL import Image

sys.path.insert(0, os.path.dirname(__file__))
from mini_idm import server  # noqa: E402

BASE = os.path.dirname(os.path.abspath(__file__))


def resource_path(*parts):
    # PyInstaller --onefile calisirken dosyalari gecici bir klasore
    # (sys._MEIPASS) acar; normal calisirken bu dosyanin yanindaki
    # klasoru kullanir.
    root = getattr(sys, "_MEIPASS", BASE)
    return os.path.join(root, *parts)


ICON_ICO = resource_path("mini_idm", "app_icon.ico")
ICON_PNG = resource_path("mini_idm", "tray_icon.png")

window = None


def focus_window():
    """Uzantidan/UI'dan yeni bir indirme geldiginde pencereyi one getirir."""
    if window is None:
        return
    try:
        window.show()
        window.restore()
    except Exception:
        pass


def on_closing():
    """X tusu: kapatma, tepsiye gizle."""
    window.hide()
    return False


def run_server():
    server.set_focus_callback(focus_window)
    server.run()


def wait_until_ready(timeout=10):
    import requests
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            requests.get(f"http://{server.HOST}:{server.PORT}/api/ping", timeout=0.5)
            return True
        except requests.RequestException:
            time.sleep(0.1)
    return False


PAIR_MARKER = os.path.join(server.CONFIG_DIR, "browser_paired")


def maybe_open_browser_for_pairing():
    """
    Chrome uzantisi token'i sadece 127.0.0.1:9614'u bir sekmede acinca
    otomatik alabiliyor (content script sayfa DOM'undan okuyor). Kullanici
    bunu elle yapmak zorunda kalmasin diye, sadece ILK calistirmada
    varsayilan tarayicida bu adresi bir kez aciyoruz.
    """
    if os.path.exists(PAIR_MARKER):
        return
    try:
        webbrowser.open(f"http://{server.HOST}:{server.PORT}/")
    except Exception:
        pass
    try:
        os.makedirs(server.CONFIG_DIR, exist_ok=True)
        with open(PAIR_MARKER, "w") as f:
            f.write("1")
    except OSError:
        pass


def make_tray_icon():
    image = Image.open(ICON_PNG)

    def on_open(icon, item):
        focus_window()

    def on_quit(icon, item):
        icon.stop()
        os._exit(0)

    menu = pystray.Menu(
        pystray.MenuItem("mini-IDM'i aç", on_open, default=True),
        pystray.MenuItem("Çıkış", on_quit),
    )
    return pystray.Icon("mini-idm", image, "mini-IDM", menu)


def main():
    global window

    threading.Thread(target=run_server, daemon=True).start()
    wait_until_ready()
    maybe_open_browser_for_pairing()

    tray = make_tray_icon()
    threading.Thread(target=tray.run, daemon=True).start()

    start_hidden = "--hidden" in sys.argv

    window = webview.create_window(
        "mini-IDM",
        f"http://{server.HOST}:{server.PORT}/",
        width=980, height=680, min_size=(640, 420),
        hidden=start_hidden,
    )
    window.events.closing += on_closing

    webview.start(icon=ICON_ICO)


if __name__ == "__main__":
    main()
