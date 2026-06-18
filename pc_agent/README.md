# Hunter PC Agent

Видимый агент для твоих ПК/VDS. Первый этап умеет:

- привязать ПК к Telegram-боту через `/pair`;
- отправлять heartbeat в мини-ап;
- показывать ПК в списке устройств как `pc-agent`.

Удаленный экран и управление ПК лучше делать через легальные каналы:

- Windows PC/VDS: WireGuard + RDP.
- Linux VDS: WireGuard + SSH.
- Кроссплатформенно: RustDesk/Chrome Remote Desktop с явным подтверждением владельца.

## Использование

1. В боте отправь `/pair`.
2. На ПК выполни:

```powershell
hunter-pc-agent.exe pair --server https://web-production-715d7.up.railway.app --code 123456 --name "Home PC"
```

3. Запусти агент:

```powershell
hunter-pc-agent.exe run
```

Окно должно оставаться открытым. Это сделано специально: агент не скрывается и не маскируется.
