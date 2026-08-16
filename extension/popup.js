const SERVER = "http://127.0.0.1:9614";

function fmtBytes(n) {
  if (!n || n < 0) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  let i = 0;
  while (n >= 1024 && i < units.length - 1) { n /= 1024; i++; }
  return (i === 0 ? n.toFixed(0) : n.toFixed(1)) + " " + units[i];
}

async function getSettings() {
  return chrome.storage.local.get({ enabled: true, token: "" });
}

async function refresh() {
  const s = await getSettings();
  document.getElementById("enabledToggle").checked = s.enabled;

  const dot = document.getElementById("statusDot");
  const jobList = document.getElementById("jobList");

  if (!s.token) {
    dot.className = "dot err";
    jobList.innerHTML = '<div class="empty">Token ayarlanmamış. Ayarlar\'dan token yapıştır.</div>';
    return;
  }

  try {
    const status = await fetch(`${SERVER}/api/status`, {
      headers: { "X-Token": s.token },
    }).then((r) => r.json());

    dot.className = "dot ok";
    const jobs = (status.jobs || []).filter((j) => j.status !== "done");

    if (!jobs.length) {
      jobList.innerHTML = '<div class="empty">Aktif indirme yok.</div>';
      return;
    }

    jobList.innerHTML = jobs.map((j) => `
      <div class="job">
        <div class="job-name" title="${j.filename}">${j.filename}</div>
        <div class="job-bar"><div class="job-fill" style="width:${j.percent}%"></div></div>
        <div class="job-meta">
          <span>${j.percent.toFixed(0)}%</span>
          <span>${fmtBytes(j.speed)}/s</span>
        </div>
      </div>`).join("");
  } catch (e) {
    dot.className = "dot err";
    jobList.innerHTML = '<div class="empty">Sunucuya ulaşılamıyor. mini-IDM açık mı?</div>';
  }
}

document.getElementById("enabledToggle").addEventListener("change", (e) => {
  chrome.storage.local.set({ enabled: e.target.checked });
});

document.getElementById("openBtn").addEventListener("click", () => {
  chrome.tabs.create({ url: `${SERVER}/` });
});

document.getElementById("optionsBtn").addEventListener("click", () => {
  chrome.runtime.openOptionsPage();
});

refresh();
setInterval(refresh, 1500);
