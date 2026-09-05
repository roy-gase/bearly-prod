"""Gunicorn configuration for the Bearly API.

Uvicorn workers under a gunicorn master: gunicorn handles process supervision and
graceful restarts, uvicorn provides the ASGI runtime.
"""
import multiprocessing
import os

bind = os.getenv("BEARLY_BIND", "0.0.0.0:8000")

# 2*cores+1 is the usual starting point. Cap it: each worker holds its own
# database pool, and Postgres connection slots are the real limit.
_default = min((multiprocessing.cpu_count() * 2) + 1, 9)
workers = int(os.getenv("BEARLY_WORKERS", _default))
worker_class = "uvicorn.workers.UvicornWorker"

# Chat replies stream for several seconds; the default 30s timeout would cut
# long tool-using turns off mid-sentence.
timeout = int(os.getenv("BEARLY_TIMEOUT", "120"))
graceful_timeout = 30
keepalive = 5

# Recycle workers periodically so a slow leak cannot accumulate indefinitely.
max_requests = 1000
max_requests_jitter = 100

accesslog = "-"
errorlog = "-"
loglevel = os.getenv("BEARLY_LOG_LEVEL", "info")
# Deliberately omits the query string: filters on the transactions endpoint carry
# amounts and search terms, which should not land in access logs.
access_log_format = '%(h)s "%(m)s %(U)s" %(s)s %(b)s %(D)sus'

forwarded_allow_ips = os.getenv("BEARLY_FORWARDED_ALLOW_IPS", "*")
proxy_protocol = False
