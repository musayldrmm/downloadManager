/*
 * mini-IDM arka plan servisi.
 *
 * Onemli tasarim karari: tarayicinin kendi indirmesini SADECE sunucuya
 * POST basarili oldugunda iptal ediyoruz. Sunucu kapaliysa/erisilemezse
 * indirmeye hic dokunmuyoruz - kullanici dosyasiz kalmamali.
 *
 * Varsayilan davranis: minSize disinda hicbir tur filtresi yok, yani
 * "ne indirirsen indir" yakalanir. excludeExts / blocklistDomains ile
 * kullanici istisna ekleyebilir (options.html).
 */

const SERVER = "http://127.0.0.1:9614";

const DEFAULTS = {
  enabled: true,
  token: "",
  minSize: 1048576,        // bu boyutun altini yakalama (byte), 0 = hepsi
  excludeExts: [],          // yakalanmayacak uzantilar (bos = hepsi yakalanir)
  blocklistDomains: [],     // bu domainlerde uzanti devre disi
};

function getSettings() {
  return chrome.storage.local.get(DEFAULTS);
}

function guessExt(nameOrUrl) {
  const clean = (nameOrUrl || "").split(/[?#]/)[0];
  const m = clean.match(/\.([a-zA-Z0-9]+)$/);
  return m ? m[1].toLowerCase() : "";
}

function isBlockedDomain(host, list) {
  return (list || []).some((d) => d && (host === d || host.endsWith("." + d)));
}

async function buildHeaders(url, referrer) {
  const headers = { "User-Agent": navigator.userAgent };
  if (referrer) headers["Referer"] = referrer;
  try {
    const cookies = await chrome.cookies.getAll({ url });
    if (cookies.length) {
      headers["Cookie"] = cookies.map((c) => `${c.name}=${c.value}`).join("; ");
    }
  } catch (e) { /* cookie okunamadi, header'siz devam */ }
  return headers;
}

async function sendToServer(token, url, filename, headers) {
  const res = await fetch(`${SERVER}/api/add`, {
    method: "POST",
    headers: { "X-Token": token, "Content-Type": "application/json" },
    body: JSON.stringify({ url, filename, headers }),
  });
  return res.json();
}

function setBadge(text, color) {
  chrome.action.setBadgeText({ text });
  if (color) chrome.action.setBadgeBackgroundColor({ color });
}

async function updateBadge() {
  const s = await getSettings();
  if (!s.enabled || !s.token) return setBadge("");
  try {
    const status = await fetch(`${SERVER}/api/status`, {
      headers: { "X-Token": s.token },
    }).then((r) => r.json());
    const active = (status.jobs || []).filter(
      (j) => j.status === "running" || j.status === "pending"
    ).length;
    setBadge(active > 0 ? String(active) : "", "#4f8cff");
  } catch (e) {
    setBadge("!", "#e05a5a");   // sunucuya ulasilamiyor
  }
}

// ------------------------------------------------------------- yakalama

async function handleDownload(item) {
  if (!/^https?:\/\//i.test(item.url || "")) return;

  const s = await getSettings();
  if (!s.enabled || !s.token) return;

  let host;
  try { host = new URL(item.url).hostname; } catch (e) { return; }
  if (isBlockedDomain(host, s.blocklistDomains)) return;

  const ext = guessExt(item.filename || item.url);
  if (s.excludeExts.includes(ext)) return;

  // fileSize bazen -1 (bilinmiyor) gelir; bu durumda filtreleme yapmadan yakala.
  if (s.minSize > 0 && item.fileSize > 0 && item.fileSize < s.minSize) return;

  const headers = await buildHeaders(item.url, item.referrer);
  const filename = (item.filename || "").split(/[\\/]/).pop() || undefined;

  let res;
  try {
    res = await sendToServer(s.token, item.url, filename, headers);
  } catch (e) {
    // Sunucu ayakta degil: tarayici indirmesine DOKUNMA, sadece uyar.
    setBadge("!", "#e05a5a");
    return;
  }

  if (!res || !res.ok) {
    setBadge("!", "#e05a5a");
    return;
  }

  try {
    await chrome.downloads.cancel(item.id);
    await chrome.downloads.erase({ id: item.id });
  } catch (e) { /* zaten bitmis/iptal edilmis olabilir, onemli degil */ }

  chrome.notifications.create({
    type: "basic",
    iconUrl: "icons/128.png",
    title: "mini-IDM",
    message: `mini-IDM'e aktarıldı: ${filename || host}`,
  });

  updateBadge();
}

chrome.downloads.onCreated.addListener((item) => {
  handleDownload(item).catch(() => {});
});

// ------------------------------------------------------------- sag tik menusu

chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: "mini-idm-download",
    title: "mini-IDM ile indir",
    contexts: ["link", "video", "audio", "image"],
  });
});

chrome.contextMenus.onClicked.addListener(async (info) => {
  if (info.menuItemId !== "mini-idm-download") return;
  const url = info.linkUrl || info.srcUrl;
  if (!url) return;

  const s = await getSettings();
  if (!s.token) {
    chrome.runtime.openOptionsPage();
    return;
  }
  const headers = await buildHeaders(url, info.pageUrl);
  try {
    const res = await sendToServer(s.token, url, undefined, headers);
    if (res && res.ok) {
      chrome.notifications.create({
        type: "basic", iconUrl: "icons/128.png",
        title: "mini-IDM", message: "mini-IDM'e aktarıldı",
      });
      updateBadge();
    }
  } catch (e) {
    chrome.notifications.create({
      type: "basic", iconUrl: "icons/128.png",
      title: "mini-IDM", message: "Sunucuya ulaşılamadı - mini-IDM açık mı?",
    });
  }
});

// ------------------------------------------------------------- rozet guncelleme
// Service worker uyuyabilir; chrome.alarms ile periyodik uyandiriyoruz.
// Chrome guncel surumlerde tekrarlanan alarm periyodunu min 1 dakikaya
// sabitliyor (dev modda bile), o yuzden 5 sn yerine 1 dk kullaniyoruz.

chrome.alarms.create("mini-idm-badge", { periodInMinutes: 1 });
chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === "mini-idm-badge") updateBadge();
});
chrome.runtime.onStartup.addListener(updateBadge);
chrome.runtime.onInstalled.addListener(updateBadge);
