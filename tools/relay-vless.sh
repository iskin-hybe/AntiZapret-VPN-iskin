#!/bin/bash
#
# Релей для мобильных сетей с «глушилками»:
#   телефон --VLESS+Reality (TCP 443)--> этот сервер (в РФ) --WireGuard--> основной сервер АЗ (полный VPN) --> интернет
#
# Подготовка:
#   1. Домен релея (например, поддомен DuckDNS) указывает на IPv4 этого сервера.
#   2. На основном сервере создан клиент WireGuard: /root/antizapret/client.sh 4 <имя_клиента>
#      (профиль берётся из /root/antizapret/client/wireguard/vpn/vpn-<имя_клиента>-*-wg.conf по scp).
#
# Запуск на релее (Ubuntu 24.04):
#   bash relay-vless.sh <IPv4_основного_сервера> <домен_релея> [имя_клиента, по умолчанию relay]
#
# Повторный запуск выдаёт новые ключи VLESS (старые ссылки перестают работать), туннель не трогает.
# Отпечаток TLS в ссылке — firefox: приветствия Chrome/Safari/iOS (с ML-KEM, ~1,8 КБ) на части сетей
# не проходят, соединения застревают на первых 1440 байтах (см. docs/kb/our-experience.md).
#
set -eu
MAIN="${1:?Укажи IPv4 основного сервера: bash relay-vless.sh <IP> <домен> [клиент]}"
DOMAIN="${2:?Укажи домен релея: bash relay-vless.sh <IP> <домен> [клиент]}"
CLIENT="${3:-relay}"                # имя клиента WireGuard на основном сервере
FP=firefox                          # отпечаток TLS в ссылке
VER=v26.9.30
SHA=f851110beaff16e78d643f0ccfd9524b4a44dfd59bae3e34bb52bba378f7690e
WG=to-main                          # имя туннеля до основного сервера
MARK=100                            # метка пакетов Xray и номер таблицы маршрутов
export DEBIAN_FRONTEND=noninteractive

IP="$(ip route get 1.2.3.4 | grep -oP 'src \K\S+')"
RES="$(getent ahostsv4 "$DOMAIN" | awk 'NR==1{print $1}')"
[ "$RES" = "$IP" ] || { echo "Домен $DOMAIN указывает на '$RES', а адрес этого сервера $IP"; exit 1; }
if ss -ltn 'sport = :443' | grep -q LISTEN && ! systemctl -q is-active xray-relay; then
    echo "TCP 443 уже занят:"; ss -ltnp 'sport = :443'; exit 1
fi

apt-get install -y -qq wireguard-tools nginx certbot qrencode </dev/null >/dev/null

# 1. Туннель WireGuard до основного сервера (клиент полного VPN «relay»)
if [ ! -f "/etc/wireguard/$WG.conf" ]; then
    echo "Забираю профиль клиента $CLIENT с основного сервера (введи пароль root основного сервера):"
    scp "root@$MAIN:/root/antizapret/client/wireguard/vpn/vpn-$CLIENT-*-wg.conf" /root/$WG.src
    ADDR="$(awk -F' *= *' '/^Address/{print $2}' /root/$WG.src | cut -d/ -f1)"
    [ -n "$ADDR" ] || { echo "Не нашёл Address в профиле"; exit 1; }
    awk -v addr="$ADDR" -v m="$MARK" '
        /^DNS *=/ {next}
        {print}
        /^Address *=/ {
            print "MTU = 1380"
            print "Table = " m
            print "PostUp = ip rule add fwmark " m " lookup " m " priority 1000; ip rule add from " addr " lookup " m " priority 1001"
            print "PostDown = ip rule del fwmark " m " lookup " m " priority 1000; ip rule del from " addr " lookup " m " priority 1001"
        }' /root/$WG.src > "/etc/wireguard/$WG.conf"
    chmod 600 "/etc/wireguard/$WG.conf"
    rm -f /root/$WG.src
fi
systemctl enable -q "wg-quick@$WG"
systemctl restart "wg-quick@$WG"
for i in $(seq 1 20); do ping -c 1 -W 2 -I "$WG" 1.1.1.1 >/dev/null 2>&1 && break; done
EXIT_IP="$(curl -s --max-time 10 --interface "$WG" https://1.1.1.1/cdn-cgi/trace | awk -F= '/^ip=/{print $2}')"
echo "Выход через туннель: ${EXIT_IP:-нет ответа}"
[ "$EXIT_IP" = "$MAIN" ] || { echo "Туннель до основного сервера не работает"; wg show "$WG"; exit 1; }

# 2. Сайт-витрина и настоящий сертификат на домен релея
mkdir -p "/var/www/$DOMAIN"
cat > "/var/www/$DOMAIN/index.html" <<HTML
<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>Personal storage</title></head>
<body><h1>Personal storage</h1><p>Personal storage.</p></body></html>
HTML
rm -f /etc/nginx/sites-enabled/default
write_nginx() {
cat > "/etc/nginx/sites-available/$DOMAIN" <<NGX
server {
    listen 80;
    server_name $DOMAIN;
    server_tokens off;
    location /.well-known/acme-challenge/ { root /var/www/$DOMAIN; }
    location / { return 301 https://\$host\$request_uri; }
}
NGX
if [ "${1:-}" = tls ]; then
cat >> "/etc/nginx/sites-available/$DOMAIN" <<NGX

server {
    listen 127.0.0.1:8443 ssl http2;
    server_name $DOMAIN;
    server_tokens off;
    ssl_certificate /etc/letsencrypt/live/$DOMAIN/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/$DOMAIN/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    root /var/www/$DOMAIN;
    index index.html;
}
NGX
fi
ln -sf "/etc/nginx/sites-available/$DOMAIN" "/etc/nginx/sites-enabled/$DOMAIN"
nginx -t -q
systemctl enable -q nginx
systemctl reload-or-restart nginx
}
write_nginx
certbot certonly --webroot -w "/var/www/$DOMAIN" -d "$DOMAIN" --agree-tos \
    --register-unsafely-without-email -n --keep-until-expiring \
    --deploy-hook "systemctl reload nginx"
write_nginx tls

# 3. Xray: VLESS + Reality на 443, весь трафик — в туннель до основного сервера
if [ ! -x /usr/local/bin/xray ]; then
    curl -fL --connect-timeout 30 -o /tmp/xray.zip "https://github.com/XTLS/Xray-core/releases/download/$VER/Xray-linux-64.zip"
    echo "$SHA  /tmp/xray.zip" | sha256sum -c -
    python3 -I -c "import zipfile; zipfile.ZipFile('/tmp/xray.zip').extract('xray', '/tmp/xray-x')"
    install -m 755 /tmp/xray-x/xray /usr/local/bin/xray
    rm -rf /tmp/xray.zip /tmp/xray-x
fi
id xray &>/dev/null || useradd -r -M -s /usr/sbin/nologin xray

KEYS="$(/usr/local/bin/xray x25519)"
PRIV="$(echo "$KEYS" | awk -F': ' '/^PrivateKey/{print $2}')"
PUB="$(echo "$KEYS" | awk -F': ' '/^Password/{print $2}')"
[ -n "$PRIV" ] && [ -n "$PUB" ] || { echo "Не удалось получить ключи:"; echo "$KEYS"; exit 1; }
ID="$(cat /proc/sys/kernel/random/uuid)"
SID="$(openssl rand -hex 8)"

mkdir -p /etc/xray-relay
cat > /etc/xray-relay/config.json <<CFG
{
  "log": { "loglevel": "warning" },
  "dns": { "servers": [ "1.1.1.1" ], "queryStrategy": "UseIPv4", "tag": "dns-q" },
  "inbounds": [
    {
      "tag": "in-vless",
      "listen": "0.0.0.0",
      "port": 443,
      "protocol": "vless",
      "settings": {
        "clients": [ { "id": "$ID", "flow": "xtls-rprx-vision" } ],
        "decryption": "none"
      },
      "streamSettings": {
        "network": "raw",
        "security": "reality",
        "realitySettings": {
          "target": "127.0.0.1:8443",
          "serverNames": [ "$DOMAIN" ],
          "privateKey": "$PRIV",
          "shortIds": [ "$SID" ]
        }
      },
      "sniffing": { "enabled": true, "destOverride": [ "http", "tls", "quic" ] }
    }
  ],
  "outbounds": [
    {
      "tag": "via-main",
      "protocol": "freedom",
      "settings": {},
      "streamSettings": { "sockopt": { "mark": $MARK, "domainStrategy": "UseIPv4" } }
    },
    { "tag": "block", "protocol": "blackhole" }
  ],
  "routing": {
    "rules": [
      { "inboundTag": [ "dns-q" ], "outboundTag": "via-main" },
      { "ip": [ "0.0.0.0/8", "10.0.0.0/8", "100.64.0.0/10", "127.0.0.0/8", "169.254.0.0/16", "172.16.0.0/12", "192.168.0.0/16" ], "outboundTag": "block" },
      { "inboundTag": [ "in-vless" ], "outboundTag": "via-main" }
    ]
  }
}
CFG
chown -R xray:xray /etc/xray-relay
chmod 600 /etc/xray-relay/config.json
/usr/local/bin/xray run -test -c /etc/xray-relay/config.json

cat > /etc/systemd/system/xray-relay.service <<UNIT
[Unit]
Description=Xray VLESS relay to main server
After=network-online.target nginx.service wg-quick@$WG.service
Wants=network-online.target
Requires=wg-quick@$WG.service

[Service]
User=xray
AmbientCapabilities=CAP_NET_BIND_SERVICE CAP_NET_ADMIN
CapabilityBoundingSet=CAP_NET_BIND_SERVICE CAP_NET_ADMIN
ExecStart=/usr/local/bin/xray run -c /etc/xray-relay/config.json
Restart=on-failure
LimitNOFILE=65535
NoNewPrivileges=yes
ProtectSystem=strict
ProtectHome=yes
PrivateTmp=yes

[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl enable -q xray-relay
systemctl restart xray-relay
sleep 2
systemctl is-active xray-relay || { journalctl -u xray-relay -n 30 --no-pager; exit 1; }

if curl -fsS --max-time 10 --resolve "$DOMAIN:443:127.0.0.1" "https://$DOMAIN/" | grep -q "Personal storage"; then
    echo "Проверка сайта через 443: OK"
else
    echo "ВНИМАНИЕ: сайт через 443 не открылся"
fi

Q="encryption=none&flow=xtls-rprx-vision&security=reality&sni=$DOMAIN&fp=$FP&pbk=$PUB&sid=$SID&type=tcp"
LINK="vless://$ID@$DOMAIN:443?$Q#Relay-VLESS"
echo
echo "Ссылка для приложения (через домен релея):"
echo "$LINK"
echo
echo "Запасная (через IP): vless://$ID@$IP:443?$Q#Relay-VLESS-IP"
echo
qrencode -t ansiutf8 "$LINK"
