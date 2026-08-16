# mini-IDM

IDM benzeri, çok bağlantılı indirme yöneticisi + Chrome uzantısı.

## Kurulum

### 1. Masaüstü uygulaması

**Python kaynağından kurulum (önerilen):** Derlenmiş `.exe` yerine bilerek
bu yol öneriliyor — Windows'un Smart App Control özelliği imzasız/yeni
derlenmiş `.exe` dosyalarını (bir Inno Setup sihirbazının içine sarılmış
olsa bile) tamamen engelleyebiliyor ve bunun kullanıcı tarafından
onaylanabileceği bir istisna mekanizması yok. `pythonw.exe` ile çalıştırmak
bu sorunu tamamen ortadan kaldırıyor çünkü Python zaten sistemde bilinen/
güvenilir bir çalıştırılabilir.

```powershell
cd server
powershell -ExecutionPolicy Bypass -File install.ps1
```

Bu script:
- `requirements.txt` bağımlılıklarını kurar
- **Başlangıç** klasörüne bir kısayol koyar → her Windows açılışında
  pencere göstermeden, sadece sistem tepsisinde sessizce başlar
- **Masaüstüne** "elle aç" kısayolu koyar → pencere görünür açılır
- Uygulamayı hemen başlatır

Kaldırmak için: `powershell -ExecutionPolicy Bypass -File uninstall.ps1`

Uygulama açılınca sistem tepsisinde bir simge belirir; pencereyi kapatman
uygulamayı kapatmaz (indirmeleri yakalayabilmesi için arka planda kalır) —
tamamen kapatmak için tepsi menüsünden **Çıkış**.

**Manuel çalıştırmak istersen** (script kullanmadan, açılışta otomatik
başlamadan):

```bash
cd server
pip install -r requirements.txt
python app.py            # native pencere + sistem tepsisi
python app.py --hidden   # pencere gizli, sadece tepside baslar
# veya sadece sunucu, tarayicidan manuel acmak icin:
python run.py
```

Konsolda (ya da uygulama ilk açıldığında arka planda) bir token basılır,
aynı zamanda `~/.mini-idm/token` dosyasında durur — Chrome uzantısı bunu
ister.

<details>
<summary><code>.exe</code> / kurulum sihirbazı (denendi, bazı sistemlerde çalışmıyor)</summary>

PyInstaller (`--onedir`) + Inno Setup ile bir `mini-IDM-Setup.exe` kurulum
sihirbazı da üretilebiliyor (`server/installer.iss`). Sihirbazın kendisi
Smart App Control'ü genelde geçiyor, ama içindeki asıl `mini-IDM.exe`
imzasız olduğu için yine de engellenebiliyor — installer "kurulumu"
tamamlıyor ama uygulama açılmıyor. Gerçek çözüm kod imzalama sertifikası
(ücretli, ör. Sectigo/DigiCert) ya da açık kaynak projeler için ücretsiz
[SignPath.io](https://signpath.io) (başvuru/inceleme süreci günler-haftalar
sürebilir). Bu yüzden şu an için Python kaynağından kurulum önerilen yol.

</details>

### 2. Chrome uzantısı

1. Chrome'da `chrome://extensions` adresine git
2. Sağ üstten **Geliştirici modu**'nu aç
3. **Paketlenmemiş öğe yükle** → bu depodaki `extension/` klasörünü seç
   (ya da [Releases](../../releases) sayfasından `mini-idm-extension.zip`'i
   indirip aç)
4. `http://127.0.0.1:9614/` adresini Chrome'da bir kez aç — uzantı token'ı
   sayfadan otomatik okuyup kendini eşler, elle bir şey kopyalaman gerekmez

Eşleşme başarılı olduysa uzantı ikonuna tıklayınca yeşil bir nokta görürsün.
Otomatik eşleşme çalışmazsa (ör. sayfayı hiç açmadıysan) uzantı ikonu →
**Ayarlar**'dan token'ı elle yapıştırıp **Bağlantıyı test et** diyebilirsin.

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
│   ├── install.ps1 / uninstall.ps1   kurulum (Başlangıç + Masaüstü kısayolu)
│   └── installer.iss            Inno Setup .exe tarifi (opsiyonel, bkz. README)
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
