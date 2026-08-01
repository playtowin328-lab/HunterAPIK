# Hunter PC Agent

Видимый агент для твоего Windows ПК/VDS. После одноразовой привязки он добавляет компьютер в общий Hunter Control: live-экран, мышь, клавиатура, настройки, диагностика и блокировка. Произвольные shell-команды агент не выполняет.

## Подключить сам Windows ПК

1. В боте или мини-аппе получи одноразовый код.
2. Скачай `hunter-pc-agent.exe` и открой PowerShell в папке с ним.
3. Запусти:

```powershell
hunter-pc-agent.exe setup --server https://web-production-715d7.up.railway.app --code 123456 --name "Home PC" --startup
```

После heartbeat компьютер появится рядом с телефонами и будет открываться той же кнопкой `Пульт`.

## Самый простой режим для телефона дома

1. В боте нажми `Получить QR / код`.
2. На домашнем ПК установи Android Platform Tools, чтобы команда `adb` работала в PowerShell.
3. На телефоне включи `Для разработчиков` -> `USB debugging`.
4. Подключи телефон к ПК и подтверди RSA-ключ на экране телефона.
5. Запусти одну команду:

```powershell
hunter-pc-agent.exe setup --server https://web-production-715d7.up.railway.app --code 123456 --name "Home PC" --startup --adb
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
hunter-pc-agent.exe run --adb --interval 1
```

## Автозапуск

```powershell
hunter-pc-agent.exe startup install
hunter-pc-agent.exe startup remove
```

После `startup install` агент копирует EXE в `%APPDATA%\HunterPCAgent`, создаёт резервную копию и восстанавливает основной файл при следующем входе в Windows, если он был повреждён или удалён. Для ручной проверки и восстановления:

```powershell
hunter-pc-agent.exe doctor
hunter-pc-agent.exe repair
hunter-pc-agent.exe support-bundle
```

Конфигурация хранится атомарно вместе с резервной копией, а подробный журнал доступен в `%APPDATA%\HunterPCAgent\agent.log`.

Автозапуск использует watchdog-файл `%APPDATA%\HunterPCAgent\startup.enabled`: после аварийного завершения агент перезапускается, а удалённый или повреждённый основной EXE восстанавливается из резервной копии. События запуска и восстановления пишутся отдельно в `watchdog.log`.

Выполненные команды сохраняются в ограниченном `command_receipts.json`. Если сеть оборвалась после действия, повторная доставка только отправляет прежний результат и не повторяет клик, ввод или другую команду.

Начиная с версии `0.5.0`, канал команд защищён adaptive circuit breaker. После нескольких полных сетевых сбоев опрос команд временно приостанавливается с увеличивающимся backoff, при этом heartbeat продолжает работать. Затем Agent автоматически выполняет контрольный запрос и закрывает circuit после восстановления связи.

`support-bundle` создаёт ZIP с журналами и диагностикой в `%APPDATA%\HunterPCAgent`. Токены, PIN и секрет привязки автоматически заменяются на `***redacted***`.

Команды используют long-poll: агент держит один короткий ожидающий запрос вместо частого пустого опроса. Время ожидания не учитывается как задержка сети в Smart Link.

PC Agent не скрывается, не ставит себя в автозапуск без твоей команды и не включает ADB без подтверждения на телефоне.
