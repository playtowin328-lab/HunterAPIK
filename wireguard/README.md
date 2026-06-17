# WireGuard mode

WireGuard нужен не для деплоя Telegram-бота на Railway, а для стабильной приватной сети между твоими устройствами и backend.

Рекомендуемая схема:

```text
Android Agent / Phone
        |
        | WireGuard VPN
        v
VPS with WireGuard + bot/backend
        |
        v
Telegram Mini App / Bot
```

Railway можно оставить для публичного бота и мини-аппа, но сам WireGuard лучше поднимать на VPS с UDP-портом `51820`.

## Почему не Railway

WireGuard использует UDP. Для нормального VPN-сервера обычно нужен VPS/сервер, где можно открыть UDP-порт и управлять сетевым интерфейсом `wg0`.

## Server example

На VPS:

```bash
sudo apt update
sudo apt install wireguard
wg genkey | tee server_private.key | wg pubkey > server_public.key
wg genkey | tee phone_private.key | wg pubkey > phone_public.key
```

Создай `/etc/wireguard/wg0.conf`:

```ini
[Interface]
Address = 10.66.66.1/24
ListenPort = 51820
PrivateKey = SERVER_PRIVATE_KEY

[Peer]
PublicKey = PHONE_PUBLIC_KEY
AllowedIPs = 10.66.66.2/32
```

Запуск:

```bash
sudo systemctl enable wg-quick@wg0
sudo systemctl start wg-quick@wg0
sudo wg
```

## Android phone config

В WireGuard Android app создай tunnel:

```ini
[Interface]
PrivateKey = PHONE_PRIVATE_KEY
Address = 10.66.66.2/32
DNS = 1.1.1.1

[Peer]
PublicKey = SERVER_PUBLIC_KEY
Endpoint = VPS_PUBLIC_IP:51820
AllowedIPs = 10.66.66.1/32
PersistentKeepalive = 25
```

`AllowedIPs = 10.66.66.1/32` означает, что через VPN пойдёт только трафик к backend-серверу, а не весь интернет телефона.

## Android Agent settings

Если backend запущен на VPS и слушает `0.0.0.0:8080`, в Android Agent можно указать:

```text
Server URL: http://10.66.66.1:8080
```

Если backend остаётся на Railway, WireGuard не нужен для соединения с ним: Android Agent продолжит ходить на публичный `https://...up.railway.app`.

## Security notes

- Не коммить приватные ключи.
- Для каждого телефона создавай отдельный peer.
- Если телефон потерян, удаляй его `[Peer]` из `wg0.conf`.
- Открывай только UDP `51820` наружу.
