"""Indirme kuyrugu: es zamanli is limiti + ayarlarin saklanmasi."""

import json
import os
import threading
import time
from urllib.parse import unquote, urlparse

from .downloader import Download

CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".mini-idm")
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")

# IDM'deki gibi tur bazli varsayilan klasorler. "dir" bos ise
# out_dir/<Baslik> kullanilir; kullanici settings'ten sabit bir yol atayabilir.
DEFAULT_CATEGORIES = {
    "documents": {"label": "Belgeler", "dir": "",
                  "exts": ["pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "txt", "csv"]},
    "compressed": {"label": "Sıkıştırılmış", "dir": "",
                   "exts": ["zip", "rar", "7z", "tar", "gz", "xz", "iso"]},
    "programs": {"label": "Programlar", "dir": "",
                 "exts": ["exe", "msi", "dmg", "pkg", "deb", "apk"]},
    "video": {"label": "Video", "dir": "",
              "exts": ["mp4", "mkv", "avi", "mov", "wmv", "flv", "webm"]},
    "music": {"label": "Müzik", "dir": "",
              "exts": ["mp3", "flac", "wav", "aac", "ogg", "m4a"]},
}

DEFAULTS = {
    "out_dir": os.path.join(os.path.expanduser("~"), "Downloads", "mini-idm"),
    "connections": 8,
    "max_concurrent": 3,
    "speed_limit": 0,          # byte/sn, 0 = sinirsiz
    "categories": DEFAULT_CATEGORIES,
}


def resolve_out_dir(config, url, filename=None):
    """URL/dosya adinin uzantisina gore hangi kategori klasorune dusecegini bulur."""
    name = filename or os.path.basename(unquote(urlparse(url).path))
    ext = os.path.splitext(name)[1].lstrip(".").lower()
    for key, cat in config.get("categories", {}).items():
        if ext in cat.get("exts", []):
            return cat.get("dir") or os.path.join(config["out_dir"], cat.get("label", key))
    return config["out_dir"]


def load_config():
    cfg = dict(DEFAULTS)
    try:
        with open(CONFIG_PATH) as f:
            cfg.update(json.load(f))
    except (OSError, ValueError):
        pass
    return cfg


def save_config(cfg):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        json.dump(cfg, f, indent=2)


class Manager:
    def __init__(self):
        self.config = load_config()
        self.jobs = {}              # id -> Download
        self.order = []             # eklenme sirasi
        self.lock = threading.Lock()
        threading.Thread(target=self._scheduler, daemon=True).start()

    # -------------------------------------------------------------- is ekleme

    def add(self, url, filename=None, headers=None, connections=None,
            out_dir=None, start=True):
        # Ayni URL icin zaten bekleyen/inen bir is varsa yeni bir tane
        # acma - kullanici "tepki vermedi" sanip birden fazla tikladiginda
        # ayni dosyayi paralel N defa indirmeye baslamamak icin.
        with self.lock:
            for jid in self.order:
                existing = self.jobs.get(jid)
                if existing and existing.url == url and existing.status in (
                    Download.PENDING, Download.RUNNING, Download.PAUSED,
                ):
                    return existing

        job = Download(
            url=url,
            out_dir=out_dir or resolve_out_dir(self.config, url, filename),
            filename=filename,
            connections=connections or self.config["connections"],
            headers=headers,
            speed_limit=self.config["speed_limit"],
        )
        with self.lock:
            self.jobs[job.id] = job
            self.order.append(job.id)
        if not start:
            job.status = Download.PAUSED
        return job

    # -------------------------------------------------------------- kontroller

    def get(self, job_id):
        return self.jobs.get(job_id)

    def pause(self, job_id):
        job = self.get(job_id)
        if job:
            job.pause()

    def resume(self, job_id):
        job = self.get(job_id)
        if job and job.status in (Download.PAUSED, Download.ERROR):
            job.status = Download.PENDING     # scheduler siraya alsin

    def cancel(self, job_id, delete_file=True):
        job = self.get(job_id)
        if job:
            job.cancel(delete_file)

    def remove(self, job_id):
        job = self.get(job_id)
        if not job:
            return
        if job.status == Download.RUNNING:
            job.pause()
            time.sleep(0.3)
        with self.lock:
            self.jobs.pop(job_id, None)
            if job_id in self.order:
                self.order.remove(job_id)

    def clear_finished(self):
        for jid in [j for j in self.order
                    if self.jobs[j].status == Download.DONE]:
            self.remove(jid)

    def update_config(self, patch):
        allowed = {k: v for k, v in patch.items() if k in DEFAULTS}
        self.config.update(allowed)
        save_config(self.config)
        for job in self.jobs.values():
            job.bucket.limit = self.config["speed_limit"]
        return self.config

    # -------------------------------------------------------------- scheduler

    def _scheduler(self):
        """PENDING isleri limit dahilinde baslatir."""
        while True:
            time.sleep(0.4)
            with self.lock:
                running = sum(1 for j in self.jobs.values()
                              if j.status == Download.RUNNING)
                slots = self.config["max_concurrent"] - running
                if slots <= 0:
                    continue
                waiting = [self.jobs[i] for i in self.order
                           if self.jobs[i].status == Download.PENDING]
            for job in waiting[:slots]:
                job.start()
                time.sleep(0.1)

    # -------------------------------------------------------------- durum

    def snapshot(self):
        with self.lock:
            jobs = [self.jobs[i].to_dict() for i in self.order if i in self.jobs]
        return {
            "jobs": jobs,
            "config": self.config,
            "total_speed": sum(j["speed"] for j in jobs),
        }
