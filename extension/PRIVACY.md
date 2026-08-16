# mini-IDM Chrome Uzantısı — Gizlilik Politikası

Son güncelleme: 2026-08-16

## Ne topluyoruz, ne göndeririz

mini-IDM uzantısı, yakaladığı indirmelere ait URL, dosya adı, cookie ve
Referer/User-Agent başlıklarını **sadece kendi bilgisayarınızda çalışan**
mini-IDM sunucusuna (`http://127.0.0.1:9614`) gönderir.

- Hiçbir veri üçüncü bir sunucuya, bulut hizmetine veya geliştiriciye
  gönderilmez.
- Uzantı, `127.0.0.1` (localhost) dışında hiçbir adrese ağ isteği atmaz.
- Toplanan hiçbir veri saklanmaz, satılmaz, paylaşılmaz.

## Neden bu izinler isteniyor

| İzin | Neden |
|---|---|
| `downloads` | Tarayıcının indirmesini yakalayıp mini-IDM'e devretmek için |
| `cookies` | Giriş gerektiren indirmelerde (ör. bir siteye üye olarak indirilen dosya) oturum bilgisini mini-IDM'e aktarmak için — cookie'ler sadece ilgili indirme isteğiyle birlikte localhost'a gönderilir |
| `storage` | Ayarları (token, filtre listeleri) tarayıcıda saklamak için |
| `contextMenus` | Sağ tık → "mini-IDM ile indir" menüsü için |
| `notifications` | "mini-IDM'e aktarıldı" bildirimi için |
| `alarms` | Servis çalışanı uyandırıp araç çubuğu rozetini güncellemek için |
| `<all_urls>` host izni | İndirme herhangi bir siteden gelebileceği için tüm sitelerde çalışabilmesi gerekiyor |
| `http://127.0.0.1:9614/*` host izni | Yalnızca yerel mini-IDM sunucusuyla konuşmak için |

## Veri saklama

Ayarlar (token, filtre listeleri, açık/kapalı durumu) tarayıcının yerel
`chrome.storage.local` alanında, yalnızca sizin cihazınızda tutulur.

## İletişim

Sorularınız için: [GitHub deposu](https://github.com/musayldrmm/downloadManager)
üzerinden bir issue açabilirsiniz.
