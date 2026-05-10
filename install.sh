#!/bin/bash
# install.sh — Bakåtkompatibel wrapper. Använd deploy.sh för full funktionalitet.
exec "$(dirname "$0")/deploy.sh" install "$@"
