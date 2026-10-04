#!/bin/bash
set -euo pipefail

: "${YEMOT_SIP_USERNAME:?YEMOT_SIP_USERNAME is required}"
: "${YEMOT_SIP_PASSWORD:?YEMOT_SIP_PASSWORD is required}"
: "${YEMOT_SIP_SERVER:=sip.yemot.co.il}"
: "${YEMOT_SIP_PORT:=5060}"
: "${ASTERISK_EXTERNAL_IP:?ASTERISK_EXTERNAL_IP is required}"
: "${ASTERISK_LOCAL_NET:=172.20.0.0/16}"

export YEMOT_SIP_USERNAME YEMOT_SIP_PASSWORD YEMOT_SIP_SERVER YEMOT_SIP_PORT
export ASTERISK_EXTERNAL_IP ASTERISK_LOCAL_NET

envsubst < /etc/asterisk/pjsip.conf.template > /etc/asterisk/pjsip.conf
envsubst < /etc/asterisk/extensions.conf.template > /etc/asterisk/extensions.conf

exec /usr/local/bin/entrypoint.sh "$@"
