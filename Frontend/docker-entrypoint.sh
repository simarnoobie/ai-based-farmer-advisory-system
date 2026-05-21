#!/bin/sh
# Write runtime config before nginx starts so the browser JS can read it.
# BACKEND_URL is set by docker-compose or the ECS task definition.
echo "window.BACKEND_URL = '${BACKEND_URL:-http://localhost:8000}';" \
  > /usr/share/nginx/html/config.js
exec nginx -g 'daemon off;'
