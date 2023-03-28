#!/bin/bash

gunicorn server:app \
  --bind "${HTTP_HOST:-127.0.0.1}":8000 \
  --daemon \
  --preload \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --access-logfile /var/log/ctf/gunicorn.access.log \
  --error-logfile /var/log/ctf/gunicorn.error.log \
  --capture-output

source /xinetd.sh
