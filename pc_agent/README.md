# Hunter PC Agent

Видимый агент для твоего домашнего ПК/VDS. Он нужен, чтобы держать связь с ботом и, при включенном ADB-мосте, управлять своим Android-телефоном через официальный Android Debug Bridge.

## Самый простой режим для телефона дома

1. В боте нажми `Получить QR / код`.
2. На домашнем ПК установи Android Platform Tools, чтобы команда `adb` работала в PowerShell.
3. На телефоне включи `Для разработчиков` -> `USB debugging`.
4. Подключи телефон к ПК и подтверди RSA-ключ на экране телефона.
5. Запусти одну команду:

```powershell
hunter-pc-agent.exe setup --server https://web-production-715d7.up.railway.app --code 123456 --name "Home PC" --startup
```

Эта команда:

- привяжет ПК к боту;
- проверит ADB;
- включит ADB-мост;
- добавит автозапуск Windows;
- оставит агент работать.

После этого в мини-апе появится устройство `adb-...`. Им можно управлять из другой страны, пока домашний ПК включен, агент запущен, а телефон подключен по USB или заранее настроенному Wireless debugging.

## Проверка

```powershell
hunter-pc-agent.exe doctor --adb
```

Если увидишь `unauthorized`, посмотри на экран телефона и подтверди RSA-ключ. Если `ADB не найден`, установи Android Platform Tools и добавь `platform-tools` в PATH.

## Ручной режим

```powershell
hunter-pc-agent.exe pair --server https://web-production-715d7.up.railway.app --code 123456 --name "Home PC"
hunter-pc-agent.exe run --adb --interval 3
```

## Автозапуск

```powershell
hunter-pc-agent.exe startup install
hunter-pc-agent.exe startup remove
```

PC Agent не скрывается, не ставит себя в автозапуск без твоей команды и не включает ADB без подтверждения на телефоне.
