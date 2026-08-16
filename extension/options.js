const SERVER = "http://127.0.0.1:9614";

const DEFAULTS = {
  enabled: true,
  token: "",
  minSize: 1048576,
  excludeExts: [],
  blocklistDomains: [],
};

async function load() {
  const s = await chrome.storage.local.get(DEFAULTS);
  document.getElementById("token").value = s.token;
  document.getElementById("minSize").value = (s.minSize / 1048576).toFixed(1);
  document.getElementById("excludeExts").value = s.excludeExts.join(", ");
  document.getElementById("blocklist").value = s.blocklistDomains.join(", ");
}

function parseList(text) {
  return text.split(",").map((s) => s.trim().toLowerCase()).filter(Boolean);
}

document.getElementById("saveBtn").addEventListener("click", async () => {
  const patch = {
    token: document.getElementById("token").value.trim(),
    minSize: Math.round((parseFloat(document.getElementById("minSize").value) || 0) * 1048576),
    excludeExts: parseList(document.getElementById("excludeExts").value),
    blocklistDomains: parseList(document.getElementById("blocklist").value),
  };
  await chrome.storage.local.set(patch);
  const msg = document.getElementById("saveMsg");
  msg.classList.add("show");
  setTimeout(() => msg.classList.remove("show"), 1500);
});

document.getElementById("testBtn").addEventListener("click", async () => {
  const token = document.getElementById("token").value.trim();
  const result = document.getElementById("testResult");
  result.textContent = "Test ediliyor...";
  result.className = "test-result";
  try {
    const ping = await fetch(`${SERVER}/api/ping`).then((r) => r.json());
    if (!ping.ok) throw new Error();
    const status = await fetch(`${SERVER}/api/status`, {
      headers: { "X-Token": token },
    });
    if (status.status === 401) {
      result.textContent = "Sunucu bulundu ama token yanlış.";
      result.className = "test-result err";
      return;
    }
    if (!status.ok) throw new Error();
    result.textContent = `Bağlantı başarılı (mini-IDM v${ping.version}).`;
    result.className = "test-result ok";
  } catch (e) {
    result.textContent = "Sunucuya ulaşılamadı. mini-IDM çalışıyor mu? (python run.py)";
    result.className = "test-result err";
  }
});

load();
