#!/bin/sh
set -eu
server=${1:-}
case "$server" in ''|*[!a-zA-Z0-9.-]*) echo 'Provide the management PC IPv4 address or hostname' >&2;exit 1;;esac
[ "$(id -u)" -eq 0 ] || { echo 'Run with sudo' >&2;exit 1; }
# Do not replace an existing chrony/ntpd service silently.
for service in chrony.service chronyd.service ntp.service ntpsec.service;do
 if systemctl is-active --quiet "$service";then echo 'An existing NTP daemon is active; configure it to use the management PC' >&2;exit 1;fi
done
systemctl cat systemd-timesyncd.service >/dev/null
mkdir -p /etc/systemd/timesyncd.conf.d
printf '[Time]\nNTP=%s\nFallbackNTP=\nPollIntervalMinSec=32\nPollIntervalMaxSec=64\n' "$server" > /etc/systemd/timesyncd.conf.d/pifids-lan.conf
timedatectl set-ntp true
systemctl restart systemd-timesyncd.service
timedatectl show-timesync --all
