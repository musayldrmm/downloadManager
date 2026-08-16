# mini-IDM — Proje Spesifikasyonu

IDM benzeri, çok bağlantılı indirme yöneticisi + Chrome uzantısı.

## Mimari

```
mini-idm/
├── server/                      # Python indirme motoru
│   ├── mini_idm/
│   │   ├── __init__.py
│   │   ├── downloader.py        [TAMAM] çekirdek motor
│   │   ├── manager.py           [TAMAM] kuyruk + ayarlar
│   │   ├── server.py            [TAMAM] HTTP API (127.0.0.1:9614)
│   │   └── ui/index.html        [YAPILACAK] web arayüzü
│   ├── run.py                   [TAMAM] sunucuyu başlatır
│   ├── cli.py                   [TAMAM] sunucusuz tek indirme
│   └── requirements.txt         [TAMAM]
└── extension/                   [YAPILACAK] Chrome MV3 uzantısı
    ├── manifest.json
    ├── background.js
    ├── popup.html / popup.js
    ├── options.html / options.js
    └── icons/
```

## Çalışma prensibi

1. Kullanıcı tarayıcıda bir dosyaya tıklar.
2. Uzantı `chrome.downloads.onCreated` ile yakalar, filtreye uyuyorsa
   `chrome.downloads.cancel()` ile tarayıcının indirmesini iptal eder.
3. Uzantı URL + cookie + referer + user-agent bilgisini yerel sunucuya POST eder.
4. Sunucu dosyayı N parçaya bölüp `Range` header'ı ile paralel indirir.
5. Web arayüzü / popup ilerlemeyi gösterir.

## Tamamlanmış: indirme motoru

`downloader.py` içindeki `Download` sınıfı şunları yapıyor:

- **Probe** — HEAD (olmazsa 1 byte'lık Range GET) ile `Content-Length`,
  `Accept-Ranges`, `Content-Disposition` okunur.
- **Segmentasyon** — dosya N parçaya bölünür, dosya `truncate()` ile
  baştan tam boyutta ayrılır (sparse), her thread `seek(offset)` ile yazar.
  Birleştirme adımı yok.
- **Dynamic segmentation** — işi biten thread `_claim_work()` çağırır;
  en çok kalanı olan aktif parçayı ikiye böler ve ikinci yarısını devralır.
  IDM'in hız avantajının asıl kaynağı bu.
- **Resume** — `.midm` JSON metadata dosyasında her parçanın `done` değeri
  tutulur; program kapanırsa `Range: bytes=<kalan>-<end>` ile devam eder.
- **Hız limiti** — `TokenBucket`, tüm thread'lerin paylaştığı ortak kova.
- **Retry** — exponential backoff ile 5 deneme.

## API sözleşmesi

Sunucu `127.0.0.1:9614`, tüm `/api/*` istekleri `X-Token` header'ı ister.
Token `~/.mini-idm/token` dosyasında, sunucu açılışta ekrana basar.

| Method | Yol | Gövde | Döner |
|---|---|---|---|
| GET | `/api/ping` | — | `{ok, version}` (token gerekmez) |
| GET | `/api/status` | — | `{jobs[], config, total_speed}` |
| POST | `/api/add` | `{url, filename?, headers?, connections?}` | `{ok, id}` |
| POST | `/api/pause` | `{id}` | `{ok}` |
| POST | `/api/resume` | `{id}` | `{ok}` |
| POST | `/api/cancel` | `{id}` | `{ok}` |
| POST | `/api/remove` | `{id}` | `{ok}` |
| POST | `/api/clear` | — | `{ok}` |
| POST | `/api/config` | `{out_dir?, connections?, max_concurrent?, speed_limit?}` | `{ok, config}` |

`job` nesnesi: `id, url, filename, path, size, downloaded, percent, speed,
eta, status, error, connections, resumable, segments[]`

`status` değerleri: `pending | running | paused | done | error`

---

# YAPILACAKLAR

## 1. Web arayüzü — `server/mini_idm/ui/index.html`

Tek dosya, framework yok, vanilla JS.

- Sunucu `index.html` içindeki `__TOKEN__` string'ini gerçek token ile
  değiştirerek servis ediyor — JS'te `const TOKEN = "__TOKEN__";` şeklinde al.
- 1 saniyede bir `/api/status` polling.
- Her iş için kart: dosya adı, ilerleme çubuğu, `%`, hız (MB/s), ETA,
  duraklat/devam/iptal/sil butonları.
- **Segment görselleştirmesi**: `segments[]` dizisini kullanarak IDM'deki gibi
  parça parça dolan çubuk çiz (her segment kendi genişliği oranında bir div,
  içinde `done/total` kadar dolu alt div).
- Üstte: toplam hız, "URL yapıştır + İndir" kutusu, ayarlar paneli
  (klasör, bağlantı sayısı, eşzamanlı iş, hız limiti KB/s).
- Koyu tema. Byte'ları insan okunur formatla (`1.4 MB/s`), ETA'yı `mm:ss`.

## 2. Chrome uzantısı — `extension/`

### `manifest.json` (Manifest V3)
```jsonc
{
  "manifest_version": 3,
  "name": "mini-IDM",
  "version": "0.1.0",
  "permissions": ["downloads", "storage", "cookies", "contextMenus", "notifications"],
  "host_permissions": ["http://127.0.0.1:9614/*", "<all_urls>"],
  "background": { "service_worker": "background.js" },
  "action": { "default_popup": "popup.html" },
  "options_page": "options.html",
  "icons": { "16": "icons/16.png", "48": "icons/48.png", "128": "icons/128.png" }
}
```

### `background.js` — kalbi burası
- `chrome.downloads.onCreated` dinle.
- `chrome.storage.local`'dan ayarları oku: `enabled`, `token`,
  `minSize` (bu boyutun altını yakalama, varsayılan 1 MB),
  `extensions` (yakalanacak uzantı listesi: zip, rar, 7z, iso, exe, msi, dmg,
  pkg, deb, mp4, mkv, avi, mp3, flac, pdf, apk, tar, gz, xz),
  `blocklist` (bu domainlerde devre dışı).
- Filtre geçerse:
  1. `chrome.downloads.cancel(item.id)` + `chrome.downloads.erase({id})`
  2. `chrome.cookies.getAll({url})` ile cookie'leri topla, `name=value; ...`
     formatında `Cookie` header'ı yap
  3. `POST /api/add` gövdesi:
     `{url, filename, headers: {Cookie, Referer, "User-Agent"}}`
  4. `chrome.notifications.create` ile "mini-IDM'e aktarıldı" bildirimi
- Sunucu ayakta değilse (fetch hatası): indirmeyi **iptal etme**, tarayıcıya
  bırak ve badge'i kırmızı yap. Kullanıcı dosyasız kalmamalı — bu kritik.
- Sağ tık menüsü: link ve medya üzerinde "mini-IDM ile indir"
  (`chrome.contextMenus.create({contexts: ["link", "video", "audio", "image"]})`).
- Badge: aktif iş sayısını göster, `chrome.alarms` ile 5 sn'de bir
  `/api/status` çekerek güncelle (service worker uyuyabilir, alarm kullan).

### `popup.html` / `popup.js`
- Açık/kapalı toggle (`enabled`).
- Aktif indirmeler listesi (mini ilerleme çubukları), `/api/status`'tan.
- "Arayüzü aç" butonu → `chrome.tabs.create({url: "http://127.0.0.1:9614/"})`.
- Sunucu bağlantı durumu göstergesi (yeşil/kırmızı nokta, `/api/ping`).

### `options.html` / `options.js`
- Token yapıştırma alanı + "Bağlantıyı test et" butonu.
- Minimum boyut, yakalanacak uzantılar, domain kara listesi.
- `chrome.storage.local` ile kaydet.

### `icons/`
- 16/48/128 px PNG. Basit bir aşağı ok simgesi yeterli, SVG'den üret.

## 3. README.md

Kurulum adımları:
1. `cd server && pip install -r requirements.txt && python run.py`
2. Konsoldaki token'ı kopyala
3. Chrome → `chrome://extensions` → Developer mode → Load unpacked → `extension/`
4. Uzantı ayarlarına token'ı yapıştır → Test et

---

## Kod stili

- Python: stdlib + `requests` dışında bağımlılık yok. Type hint şart değil,
  docstring Türkçe, kod İngilizce.
- JS: vanilla, build adımı yok, `async/await`, framework yok.
- Yorumlar "ne" değil "neden" anlatsın.

## Test edilecekler

- [ ] 1 MB'lık dosya, `httpbin.org/bytes/1048576` — Range desteği var mı
- [ ] Range desteklemeyen sunucu → tek bağlantıya düşmeli, dosya bozulmamalı
- [ ] Yarıda durdur → yeniden başlat → dosya hash'i bozulmadan tamamlanmalı
- [ ] Sunucu kapalıyken indirme → tarayıcı normal indirmeli
- [ ] Cookie gerektiren indirme (giriş yapılmış bir site)
