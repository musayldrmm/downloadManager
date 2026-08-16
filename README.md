# mini-IDM

IDM benzeri, çok bağlantılı indirme yöneticisi + Chrome uzantısı.

## Kurulum

### 1. Masaüstü uygulaması

**Kurulum sihirbazı (önerilen):** `server/dist_installer/mini-IDM-Setup.exe`'yi
çalıştır. Admin istemez (kullanıcı klasörüne kurulur), Başlat menüsü
kısayolu ve kaldırma sihirbazı ekler, isteğe bağlı masaüstü simgesi ve
Windows açılışında otomatik başlatma sunar.

Bu installer da imzasız olduğu için Windows SmartScreen bir uyarı
gösterebilir ("Windows bilgisayarınızı korudu") — açık kaynaklı/imzasız
programlarda beklenen bir durumdur:

1. Uyarı penceresinde **"Daha fazla bilgi"** yazısına tıkla
2. Çıkan **"Yine de çalıştır"** butonuna bas

*Not:* Ham `--onefile` exe (kendini her açılışta geçici klasöre açan tek
dosya) Windows'un Smart App Control özelliği tarafından tamamen
engellenebiliyordu; bu yüzden `--onedir` derleme + Inno Setup kurulum
sihirbazına geçildi — installer formatı heuristiklerde daha az şüpheli
görünüyor ve testte Smart App Control'ü sorunsuz geçti. Yine de illa
engellenirse: **Windows Güvenliği → Uygulama ve tarayıcı denetimi → Smart
App Control**'den elle onaylaman gerekir (bu özellik bir kez kapatılırsa
geri açılamaz, bilerek yap).

Uygulama açılınca sistem tepsisinde bir simge belirir; pencereyi kapatman
uygulamayı kapatmaz (indirmeleri yakalayabilmesi için arka planda kalır) —
tamamen kapatmak için tepsi menüsünden **Çıkış**.

**Kaynaktan çalıştırmak istersen** (geliştirme / exe'ye güvenmiyorsan):

```bash
cd server
pip install -r requirements.txt
python app.py        # native pencere + sistem tepsisi
# veya sadece sunucu, tarayicidan manuel acmak icin:
python run.py
```

**Kendin derlemek istersen:**

```bash
cd server
pip install pyinstaller
pyinstaller --name mini-IDM --onedir --windowed --icon mini_idm/app_icon.ico ^
  --add-data "mini_idm/ui;mini_idm/ui" --add-data "mini_idm/app_icon.ico;mini_idm" ^
  --add-data "mini_idm/tray_icon.png;mini_idm" ^
  --collect-all webview --collect-all pystray --collect-all clr_loader app.py

# Inno Setup (jrsoftware.org veya `winget install JRSoftware.InnoSetup`) ile:
"C:\Users\<kullanıcı>\AppData\Local\Programs\Inno Setup 6\ISCC.exe" installer.iss
```

Konsolda (ya da uygulama ilk açıldığında arka planda) bir token basılır,
aynı zamanda `~/.mini-idm/token` dosyasında durur — Chrome uzantısı bunu
ister.

### 2. Chrome uzantısı

1. Chrome'da `chrome://extensions` adresine git
2. Sağ üstten **Geliştirici modu**'nu aç
3. **Paketlenmemiş öğe yükle** → bu depodaki `extension/` klasörünü seç
4. Uzantı ikonuna tıkla → **Ayarlar** → sunucu konsolundaki token'ı yapıştır →
   **Bağlantıyı test et**

Bundan sonra tarayıcıda tıkladığın her indirme (varsayılan: 1 MB üzeri, tür
sınırı yok) mini-IDM'e yönlenir. Sunucu kapalıyken hiçbir şey yakalanmaz,
tarayıcı normal indirir — dosyasız kalmazsın.

## Özellikler

- **Native masaüstü penceresi + sistem tepsisi**: tarayıcı sekmesi değil,
  IDM gibi kendi penceresi olan bir program. Uzantı bir indirme yakaladığında
  pencere otomatik öne gelir. Pencereyi kapatmak uygulamayı kapatmaz, tepside
  arka planda çalışmaya devam eder.
- **Çok bağlantılı + dinamik segmentasyon**: dosya N parçaya bölünür, işi
  biten bağlantı en yavaş parçayı ikiye bölüp yardıma gider (IDM'in hız
  avantajının kaynağı).
- **Devam ettirme**: yarıda kesilen indirme kaldığı yerden devam eder.
- **Tür bazlı klasörler**: pdf/doc → Belgeler, zip/rar → Sıkıştırılmış,
  exe/msi → Programlar, mp4/mkv → Video, mp3/flac → Müzik. Her biri
  ayarlardan "Gözat" ile değiştirilebilir (native Windows klasör penceresi).
- **İndirme başına klasör override'ı**: ana ekrandaki "Kayıt klasörü"
  kutusuna manuel yol girip o indirmeyi otomatik kategoriden bağımsız kaydet.
- **Hız birimi Mbps** (internet hız testleriyle karşılaştırılabilir olması
  için MB/s değil bit/s tabanlı).
- Duraklat / devam / iptal / hız limiti (Mbps) / eşzamanlı iş limiti.

## Mimari

```
mini-idm/
├── server/                      Python indirme motoru
│   ├── mini_idm/
│   │   ├── downloader.py        çekirdek motor (segmentasyon, resume, hız limiti)
│   │   ├── manager.py           kuyruk, ayarlar, kategori->klasör eşleme
│   │   ├── server.py            HTTP API (127.0.0.1:9614) + native klasör seçici
│   │   ├── app_icon.ico / tray_icon.png
│   │   └── ui/index.html        web arayüzü
│   ├── app.py                   masaüstü uygulaması (native pencere + tepsi)
│   ├── run.py                   sadece sunucu, tarayıcıdan manuel açmak için
│   ├── cli.py                   sunucusuz tek indirme
│   ├── installer.iss            Inno Setup kurulum sihirbazı tarifi
│   └── dist_installer/mini-IDM-Setup.exe   kurulum sihirbazı (kuracağın tek exe bu)
└── extension/                   Chrome MV3 uzantısı
    ├── manifest.json
    ├── background.js            indirme yakalama, sağ tık menüsü, rozet
    ├── popup.html / popup.js    aktif indirmeler + açık/kapalı
    ├── options.html / options.js  token, istisna kuralları
    └── icons/
```

## API

Sunucu `127.0.0.1:9614`, tüm `/api/*` istekleri `X-Token` header'ı ister
(token `~/.mini-idm/token`).

| Method | Yol | Gövde | Döner |
|---|---|---|---|
| GET | `/api/ping` | — | `{ok, version}` (token gerekmez) |
| GET | `/api/status` | — | `{jobs[], config, total_speed}` |
| GET | `/api/browse-folder?start=` | — | `{ok, path}` — native klasör seçici açar |
| POST | `/api/add` | `{url, filename?, headers?, connections?, out_dir?}` | `{ok, id}` |
| POST | `/api/pause` \| `/resume` \| `/cancel` \| `/remove` | `{id}` | `{ok}` |
| POST | `/api/clear` | — | `{ok}` |
| POST | `/api/config` | `{out_dir?, connections?, max_concurrent?, speed_limit?, categories?}` | `{ok, config}` |

## Test edilecekler

- [x] Range destekleyen sunucu → çoklu bağlantı + dinamik segmentasyon
- [x] Range desteklemeyen sunucu → tek bağlantıya düşer, dosya bozulmaz
- [x] Yarıda durdur → devam et → kaldığı yerden bozulmadan tamamlanır
- [x] Tür bazlı klasör yönlendirmesi (pdf → Belgeler vb.)
- [ ] Sunucu kapalıyken tarayıcıdan indirme → normal iner (uzantı, manuel test gerekir)
- [ ] Cookie gerektiren indirme (giriş yapılmış bir site, manuel test gerekir)
