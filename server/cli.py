#!/usr/bin/env python3
"""Sunucusuz tek seferlik indirme:  python cli.py <url> -n 8"""
import argparse
import sys
import time

from mini_idm.downloader import Download


def human(n):
    for u in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {u}"
        n /= 1024
    return f"{n:.1f} TB"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("-n", "--connections", type=int, default=8)
    ap.add_argument("-o", "--output")
    ap.add_argument("-d", "--dir", default=".")
    ap.add_argument("-l", "--limit", type=int, default=0, help="KB/sn limit")
    a = ap.parse_args()

    job = Download(a.url, a.dir, a.output, a.connections,
                   speed_limit=a.limit * 1024)
    job.start()
    while job.status in ("pending", "running"):
        time.sleep(0.3)
        s = job.to_dict()
        bar = "#" * int(s["percent"] // 2.5) + "." * (40 - int(s["percent"] // 2.5))
        sys.stdout.write(f"\r[{bar}] {s['percent']:5.1f}%  "
                         f"{human(s['speed'])}/s  {s['connections']} baglanti ")
        sys.stdout.flush()
    print()
    if job.status == "done":
        print(f"[OK] {job.path}  ({human(job.size)})")
    else:
        print(f"[HATA] {job.error}")
        sys.exit(1)


if __name__ == "__main__":
    main()
