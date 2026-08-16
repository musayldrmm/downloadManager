/*
 * Sadece http://127.0.0.1:9614/* uzerinde calisir (manifest'te sinirli).
 * mini-IDM web arayuzunun <meta name="mini-idm-token"> etiketinden token'i
 * okuyup arka plana iletir - kullanicinin token'i elle kopyalamasina
 * gerek kalmaz. Bu sayfayi sadece bu makinedeki mini-IDM sunucusu
 * uretebildigi icin (ayni port + ayni token dosyasi) guven sinirini
 * bozmuyor.
 */
const meta = document.querySelector('meta[name="mini-idm-token"]');
const token = meta && meta.content;
if (token) {
  chrome.runtime.sendMessage({ type: "mini-idm-pair", token });
}
