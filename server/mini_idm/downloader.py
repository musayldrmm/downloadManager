"""
Çekirdek indirme motoru.

IDM mantığı:
  1. HEAD ile boyut + Accept-Ranges öğrenilir
  2. Dosya N parçaya bölünür, her parça ayrı bağlantıda Range ile çekilir
  3. Tek dosyaya seek(offset) ile yazılır -> birleştirme yok
  4. .midm metadata dosyasi ile kaldigi yerden devam
  5. Biten thread, en yavas parcanin kalanini ikiye bolup yardima gider
     (dynamic segmentation / work stealing)
"""

import json
import os
import threading
import time
import uuid
from urllib.parse import unquote, urlparse

import requests

CHUNK = 64 * 1024
DEFAULT_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

# Bir parca bu boyutun altina dustuyse bolmeye degmez
MIN_SPLIT = 1 * 1024 * 1024


class Part:
    __slots__ = ("index", "start", "end", "done", "active")

    def __init__(self, index, start, end, done=0):
        self.index = index
        self.start = start          # mutlak baslangic byte'i
        self.end = end              # mutlak bitis byte'i (dahil)
        self.done = done            # bu parcadan inen byte
        self.active = False         # bir thread uzerinde calisiyor mu

    @property
    def total(self):
        return self.end - self.start + 1

    @property
    def remaining(self):
        return self.total - self.done

    @property
    def finished(self):
        return self.done >= self.total

    def to_dict(self):
        return {"index": self.index, "start": self.start,
                "end": self.end, "done": self.done}


class TokenBucket:
    """Hiz limiti icin basit token bucket. limit=0 -> sinirsiz."""

    def __init__(self, limit_bps=0):
        self.limit = limit_bps
        self.tokens = float(limit_bps)
        self.stamp = time.monotonic()
        self.lock = threading.Lock()

    def consume(self, amount):
        if self.limit <= 0:
            return
        while True:
            with self.lock:
                now = time.monotonic()
                self.tokens = min(self.limit,
                                  self.tokens + (now - self.stamp) * self.limit)
                self.stamp = now
                if self.tokens >= amount:
                    self.tokens -= amount
                    return
                wait = (amount - self.tokens) / self.limit
            time.sleep(min(wait, 0.25))


class Download:
    """Tek bir indirme isi."""

    PENDING, RUNNING, PAUSED, DONE, ERROR = "pending", "running", "paused", "done", "error"

    def __init__(self, url, out_dir=".", filename=None, connections=8,
                 headers=None, speed_limit=0, job_id=None):
        self.id = job_id or uuid.uuid4().hex[:12]
        self.url = url
        self.out_dir = out_dir
        self.filename = filename or self._guess_name()
        self.connections = max(1, connections)
        self.headers = {"User-Agent": DEFAULT_UA, **(headers or {})}
        self.bucket = TokenBucket(speed_limit)

        self.size = 0
        self.resumable = False
        self.parts = []
        self.status = self.PENDING
        self.error = ""

        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._threads = []
        self._speed = 0.0
        self._last_sample = (0, time.monotonic())
        self._session = requests.Session()

    # ------------------------------------------------------------------ yollar

    @property
    def path(self):
        return os.path.join(self.out_dir, self.filename)

    @property
    def meta_path(self):
        return self.path + ".midm"

    def _guess_name(self):
        name = os.path.basename(unquote(urlparse(self.url).path))
        return name or "download.bin"

    def _unique_name(self):
        """Ayni isimde dosya varsa dosya(1).ext yap."""
        base, ext = os.path.splitext(self.filename)
        i, name = 1, self.filename
        while os.path.exists(os.path.join(self.out_dir, name)) and \
                not os.path.exists(os.path.join(self.out_dir, name + ".midm")):
            name = f"{base}({i}){ext}"
            i += 1
        self.filename = name

    # ------------------------------------------------------------------ hazirlik

    def probe(self):
        """Boyut, range destegi ve sunucunun onerdigi dosya adini ogren."""
        r = None
        try:
            r = self._session.head(self.url, headers=self.headers,
                                   allow_redirects=True, timeout=20)
            if r.status_code >= 400:
                r = None
        except requests.RequestException:
            r = None

        if r is None:
            # Bazi sunucular HEAD kabul etmez -> 1 byte'lik Range GET
            r = self._session.get(self.url,
                                  headers={**self.headers, "Range": "bytes=0-0"},
                                  stream=True, timeout=20)
            r.close()
        r.raise_for_status()

        self.size = int(r.headers.get("Content-Length") or 0)
        cr = r.headers.get("Content-Range", "")
        if "/" in cr:
            tail = cr.rsplit("/", 1)[-1]
            if tail.isdigit():
                self.size = int(tail)

        self.resumable = (r.headers.get("Accept-Ranges", "").lower() == "bytes"
                          or r.status_code == 206)

        # Content-Disposition varsa gercek dosya adi orada
        cd = r.headers.get("Content-Disposition", "")
        if "filename" in cd:
            try:
                raw = cd.split("filename")[-1].split("=", 1)[1].strip()
                raw = raw.split(";")[0].strip().strip('"\'')
                if raw.lower().startswith("utf-8''"):
                    raw = unquote(raw[7:])
                if raw:
                    self.filename = os.path.basename(unquote(raw))
            except (IndexError, ValueError):
                pass

        if self.size <= 0 or not self.resumable:
            self.connections = 1

    def _load_meta(self):
        if not (os.path.exists(self.meta_path) and os.path.exists(self.path)):
            return False
        try:
            with open(self.meta_path) as f:
                meta = json.load(f)
        except (OSError, ValueError):
            return False
        if meta.get("url") != self.url or meta.get("size") != self.size:
            return False
        self.parts = [Part(**p) for p in meta["parts"]]
        return True

    def save_meta(self):
        if not self.parts:
            return
        tmp = self.meta_path + ".tmp"
        try:
            with open(tmp, "w") as f:
                json.dump({"url": self.url, "size": self.size,
                           "parts": [p.to_dict() for p in self.parts]}, f)
            os.replace(tmp, self.meta_path)
        except OSError:
            pass

    def plan(self):
        os.makedirs(self.out_dir, exist_ok=True)
        if self._load_meta():
            return
        self._unique_name()

        if self.size <= 0:
            self.parts = [Part(0, 0, -1)]      # boyut bilinmiyor, tek akis
        else:
            per = self.size // self.connections
            self.parts = []
            for i in range(self.connections):
                start = i * per
                end = self.size - 1 if i == self.connections - 1 else start + per - 1
                self.parts.append(Part(i, start, end))

        with open(self.path, "wb") as f:
            if self.size > 0:
                f.truncate(self.size)           # sparse file, disk hemen dolmaz

    # ------------------------------------------------------------------ indirme

    def downloaded(self):
        return sum(p.done for p in self.parts)

    def _claim_work(self):
        """
        Bos kalan thread icin is bul:
        en cok kalani olan AKTIF parcayi ikiye bol, ikinci yarisini devral.
        IDM'in dynamic segmentation dedigi sey bu.
        """
        with self._lock:
            victim = max((p for p in self.parts if p.active and not p.finished),
                         key=lambda p: p.remaining, default=None)
            if victim is None or victim.remaining < MIN_SPLIT * 2:
                return None
            mid = victim.start + victim.done + victim.remaining // 2
            new = Part(len(self.parts), mid, victim.end)
            victim.end = mid - 1                # kurban parca kisalir
            self.parts.append(new)
            new.active = True
            return new

    def _worker(self, part):
        part.active = True
        try:
            while not part.finished and not self._stop.is_set():
                self._fetch(part)
            # Kendi isi bitti -> baskasina yardim et
            while not self._stop.is_set():
                nxt = self._claim_work()
                if nxt is None:
                    break
                while not nxt.finished and not self._stop.is_set():
                    self._fetch(nxt)
                nxt.active = False
        finally:
            part.active = False

    def _fetch(self, part, tries=0):
        begin = part.start + part.done
        headers = dict(self.headers)
        if self.size > 0:
            headers["Range"] = f"bytes={begin}-{part.end}"
        try:
            with self._session.get(self.url, headers=headers,
                                   stream=True, timeout=30) as r:
                r.raise_for_status()
                with open(self.path, "r+b") as f:
                    f.seek(begin)
                    for block in r.iter_content(CHUNK):
                        if self._stop.is_set():
                            return
                        if not block:
                            break
                        # parca baskasi tarafindan bolunmus olabilir
                        if self.size > 0 and part.start + part.done > part.end:
                            return
                        self.bucket.consume(len(block))
                        f.write(block)
                        with self._lock:
                            part.done += len(block)
                if self.size <= 0:              # boyut bilinmiyordu, bitti
                    part.end = part.start + part.done - 1
        except requests.RequestException as e:
            if tries >= 4 or self._stop.is_set():
                raise
            time.sleep(min(2 ** tries, 10))     # exponential backoff
            self._fetch(part, tries + 1)

    def _monitor(self):
        while any(t.is_alive() for t in self._threads):
            time.sleep(0.5)
            now, t_now = self.downloaded(), time.monotonic()
            prev, t_prev = self._last_sample
            dt = t_now - t_prev
            if dt > 0:
                self._speed = (now - prev) / dt
            self._last_sample = (now, t_now)
            self.save_meta()

    def start(self):
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        try:
            self.status = self.RUNNING
            self._stop.clear()
            if not self.parts:
                self.probe()
                self.plan()

            self._last_sample = (self.downloaded(), time.monotonic())
            self._threads = [
                threading.Thread(target=self._worker, args=(p,), daemon=True)
                for p in self.parts if not p.finished
            ]
            for t in self._threads:
                t.start()
            self._monitor()
            for t in self._threads:
                t.join()

            if self._stop.is_set():
                self.status = self.PAUSED
                self.save_meta()
                return

            if self.size <= 0 or self.downloaded() >= self.size:
                self.status = self.DONE
                self._speed = 0
                if os.path.exists(self.meta_path):
                    os.remove(self.meta_path)
            else:
                self.status = self.ERROR
                self.error = "Eksik veri"
        except Exception as e:                  # noqa: BLE001
            self.status = self.ERROR
            self.error = f"{type(e).__name__}: {e}"
            self.save_meta()

    def pause(self):
        if self.status == self.RUNNING:
            self._stop.set()

    def resume(self):
        if self.status in (self.PAUSED, self.ERROR):
            self.start()

    def cancel(self, delete_file=True):
        self._stop.set()
        self.status = self.ERROR
        self.error = "Iptal edildi"
        time.sleep(0.3)
        if delete_file:
            for p in (self.path, self.meta_path):
                try:
                    os.remove(p)
                except OSError:
                    pass

    # ------------------------------------------------------------------ durum

    def to_dict(self):
        done = self.downloaded()
        pct = (done / self.size * 100) if self.size else 0
        eta = int((self.size - done) / self._speed) if self._speed > 1 else -1
        return {
            "id": self.id,
            "url": self.url,
            "filename": self.filename,
            "path": self.path,
            "size": self.size,
            "downloaded": done,
            "percent": round(pct, 2),
            "speed": round(self._speed),
            "eta": eta,
            "status": self.status,
            "error": self.error,
            "connections": len(self.parts),
            "resumable": self.resumable,
            "segments": [
                {"start": p.start, "total": p.total, "done": p.done}
                for p in self.parts
            ],
        }
