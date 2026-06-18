const tg = window.Telegram?.WebApp;

if (tg) {
  tg.ready();
  tg.expand();
}

const themeButton = document.querySelector("#themeButton");
const deviceForm = document.querySelector("#deviceForm");
const deviceName = document.querySelector("#deviceName");
const deviceType = document.querySelector("#deviceType");
const deviceList = document.querySelector("#deviceList");
const currentDeviceText = document.querySelector("#currentDeviceText");
const connectCurrentDevice = document.querySelector("#connectCurrentDevice");
const setupText = document.querySelector("#setupText");
const installAgentButton = document.querySelector("#installAgentButton");
const requestPairButton = document.querySelector("#requestPairButton");
const refreshButton = document.querySelector("#refreshButton");
const pairResult = document.querySelector("#pairResult");
const pairQrImage = document.querySelector("#pairQrImage");
const pairCode = document.querySelector("#pairCode");
const openPairPageButton = document.querySelector("#openPairPageButton");
const openAgentDeepLinkButton = document.querySelector("#openAgentDeepLinkButton");
const totalDevices = document.querySelector("#totalDevices");
const onlineDevices = document.querySelector("#onlineDevices");
const userName = document.querySelector("#userName");
const template = document.querySelector("#deviceCardTemplate");

const telegramUser = tg?.initDataUnsafe?.user;
const profileName = telegramUser?.first_name || telegramUser?.username || "Я";
const ownerId = String(telegramUser?.id || localStorage.getItem("apk_owner_id") || crypto.randomUUID());
localStorage.setItem("apk_owner_id", ownerId);

const localDeviceIdKey = "apk_converter_local_device_id";
const localDeviceId = getLocalDeviceId();
const apiBaseUrl = window.location.origin;

const typeNames = {
  phone: "Телефон",
  tablet: "Планшет",
  pc: "Компьютер",
};

let devices = [];
let currentPairLinks = null;
const screenPollers = new Map();

function getLocalDeviceId() {
  const existingId = localStorage.getItem(localDeviceIdKey);
  if (existingId) {
    return existingId;
  }

  const newId = crypto.randomUUID();
  localStorage.setItem(localDeviceIdKey, newId);
  return newId;
}

function openExternal(url) {
  if (tg?.openLink) {
    tg.openLink(url);
    return;
  }
  window.open(url, "_blank", "noopener");
}

function sendBotEvent(event, payload = {}) {
  if (!tg?.sendData) {
    setupText.textContent = "Открой мини-апп из Telegram, чтобы бот мог прислать QR в чат.";
    return false;
  }
  tg.sendData(JSON.stringify({ event, ...payload }));
  return true;
}

function detectCurrentDevice() {
  const platform = tg?.platform || "unknown";
  const userAgent = navigator.userAgent;
  const isIphone = /iPhone/i.test(userAgent) || platform === "ios";
  const isIpad = /iPad/i.test(userAgent);
  const isAndroid = /Android/i.test(userAgent) || platform === "android";
  const androidModelMatch = userAgent.match(/Android[^;]*;\s?([^;)]+)[;)]/i);

  if (isIphone) {
    return { name: "iPhone", type: "phone", platform: "iOS" };
  }

  if (isIpad) {
    return { name: "iPad", type: "tablet", platform: "iPadOS" };
  }

  if (isAndroid) {
    const model = androidModelMatch?.[1]?.replace(/Build\/.*/i, "").trim();
    return {
      name: model && model.length < 32 ? model : "Android телефон",
      type: "phone",
      platform: "Android",
    };
  }

  return {
    name: "Это устройство",
    type: "pc",
    platform: platform === "unknown" ? "Браузер" : platform,
  };
}

function formatLastSeen(value) {
  if (!value) {
    return "нет данных";
  }

  return new Intl.DateTimeFormat("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value * 1000));
}

function formatTelemetry(device) {
  const telemetry = device.telemetry || {};
  const items = [];

  if (typeof telemetry.battery_percent === "number" && telemetry.battery_percent >= 0) {
    items.push(`${telemetry.battery_percent}%${telemetry.charging ? " · зарядка" : ""}`);
  }
  if (telemetry.network) {
    items.push(`сеть: ${telemetry.network}`);
  }
  if (telemetry.android) {
    items.push(`Android ${telemetry.android}`);
  }
  if (typeof telemetry.accessibility === "boolean") {
    items.push(`жесты: ${telemetry.accessibility ? "on" : "off"}`);
  }

  return items;
}

function setTelegramTheme() {
  const scheme = tg?.colorScheme;
  const savedTheme = localStorage.getItem("apk_converter_theme");
  const dark = savedTheme ? savedTheme === "dark" : scheme === "dark";
  document.documentElement.classList.toggle("dark", dark);
}

async function loadDevicesFromApi() {
  const response = await fetch(`${apiBaseUrl}/api/devices?owner_id=${encodeURIComponent(ownerId)}`);
  if (!response.ok) {
    throw new Error("Не получилось загрузить устройства");
  }

  const payload = await response.json();
  devices = payload.devices || [];
}

async function createPairingQr() {
  const response = await fetch(`${apiBaseUrl}/api/pair/new?owner_id=${encodeURIComponent(ownerId)}`);
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.error || "Не удалось создать QR");
  }
  return response.json();
}

async function registerDevice(device) {
  const response = await fetch(`${apiBaseUrl}/api/devices/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      owner_id: ownerId,
      device_id: device.device_id,
      name: device.name,
      type: device.type,
      platform: device.platform,
      agent: device.agent || "mini-app",
    }),
  });

  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.error || "Устройство не принято сервером");
  }
}

async function sendCommand(device, type, payload = {}) {
  const response = await fetch(`${apiBaseUrl}/api/devices/command`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      owner_id: ownerId,
      device_id: device.device_id,
      type,
      payload,
    }),
  });

  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.error || "Команда не принята сервером");
  }

  return response.json();
}

async function getCommandStatus(device, commandId) {
  const response = await fetch(
    `${apiBaseUrl}/api/devices/commands/status?owner_id=${encodeURIComponent(ownerId)}&device_id=${encodeURIComponent(device.device_id)}&command_id=${encodeURIComponent(commandId)}`
  );
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.error || "Не удалось получить статус команды");
  }
  return response.json();
}

async function waitForCommandResult(device, commandPayload, timeoutMs = 9000) {
  const commandId = commandPayload?.command?.command_id;
  if (!commandId) {
    return commandPayload;
  }

  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const payload = await getCommandStatus(device, commandId);
    const status = payload.command?.status;
    if (status && status !== "pending" && status !== "delivered") {
      return payload;
    }
    await new Promise((resolve) => setTimeout(resolve, 550));
  }
  return { command: { ...commandPayload.command, status: "timeout", result: "Агент не подтвердил команду за 9 секунд." } };
}

async function sendCommandAndWait(device, type, payload = {}) {
  const commandPayload = await sendCommand(device, type, payload);
  return waitForCommandResult(device, commandPayload);
}

function commandResultText(payload, fallback) {
  const command = payload?.command;
  if (!command) {
    return fallback;
  }
  const result = command.result ? ` ${command.result}` : "";
  if (command.status === "acknowledged" || command.status === "done") {
    return `${fallback}${result}`;
  }
  if (command.status === "rejected") {
    return `Отклонено.${result}`;
  }
  if (command.status === "timeout") {
    return command.result;
  }
  return `${command.status || "Статус"}:${result}`;
}

async function manageDevice(device, action, payload = {}) {
  const response = await fetch(`${apiBaseUrl}/api/devices/manage`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      owner_id: ownerId,
      device_id: device.device_id,
      action,
      ...payload,
    }),
  });

  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(data.error || "Действие не выполнено");
  }
}

async function loadScreenFrame(device) {
  const response = await fetch(
    `${apiBaseUrl}/api/devices/screen?owner_id=${encodeURIComponent(ownerId)}&device_id=${encodeURIComponent(device.device_id)}`
  );
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.error || "Кадр экрана пока не готов");
  }

  return response.json();
}

function startScreenPolling(device, screenPreview, screenImage, controlNote) {
  if (screenPollers.has(device.device_id)) {
    clearInterval(screenPollers.get(device.device_id));
  }

  const loadFrame = async () => {
    try {
      const payload = await loadScreenFrame(device);
      screenImage.src = payload.frame.image_data;
      screenPreview.hidden = false;
      controlNote.textContent = `Кадр обновлён: ${formatLastSeen(payload.frame.updated_at)}`;
    } catch (error) {
      controlNote.textContent = `Жду первый кадр. ${error.message}.`;
    }
  };

  loadFrame();
  screenPollers.set(device.device_id, setInterval(loadFrame, 1200));
}

function stopScreenPolling(deviceId) {
  if (!screenPollers.has(deviceId)) {
    return;
  }

  clearInterval(screenPollers.get(deviceId));
  screenPollers.delete(deviceId);
}

async function sendSimpleDeviceCommand(device, type, controlNote, successText) {
  if (!device.online) {
    controlNote.textContent = "Устройство offline. Запусти агент на телефоне.";
    return;
  }

  try {
    controlNote.textContent = "Команда отправлена, жду ответ агента...";
    const result = await sendCommandAndWait(device, type);
    controlNote.textContent = commandResultText(result, successText);
  } catch (error) {
    controlNote.textContent = error.message;
  }
}

function render() {
  deviceList.innerHTML = "";
  totalDevices.textContent = devices.length;
  const onlineCount = devices.filter((device) => device.online).length;
  onlineDevices.textContent = onlineCount;
  userName.textContent = profileName;
  setupText.textContent = devices.length
    ? `${devices.length} устройств, online: ${onlineCount}.`
    : "Установи Lite APK, получи QR и запусти Android Agent на телефоне.";

  if (!devices.length) {
    deviceList.innerHTML = `<p class="empty-state">Пока нет подключенных устройств. Нажми "Скачать APK", затем "Получить QR" и запусти Android Agent. Экран и жесты доступны только в Full-сборке.</p>`;
    return;
  }

  devices.forEach((device) => {
    const card = template.content.firstElementChild.cloneNode(true);
    card.classList.toggle("offline", !device.online);

    card.querySelector("h2").textContent = device.name;
    card.querySelector(".status-pill").textContent = device.online ? "Online" : "Offline";

    const deviceTypeName = typeNames[device.type] || "Устройство";
    const platform = device.platform ? ` · ${device.platform}` : "";
    const agent = device.agent ? ` · ${device.agent}` : "";
    card.querySelector(".meta").textContent = `${deviceTypeName}${platform}${agent} · сигнал ${formatLastSeen(device.last_seen)}`;

    const telemetry = card.querySelector(".telemetry");
    const telemetryItems = formatTelemetry(device);
    telemetry.innerHTML = telemetryItems.map((item) => `<span>${item}</span>`).join("");

    const controlNote = card.querySelector(".control-note");
    const screenPreview = card.querySelector(".screen-preview");
    const screenImage = screenPreview.querySelector("img");
    controlNote.textContent = device.online
      ? "Готов к командам агента. Просмотр экрана требует отдельного разрешения на телефоне."
      : "Устройство offline. Запусти агент на телефоне.";

    card.querySelector(".screen-button").addEventListener("click", async () => {
      if (/iphone|ios|ipad/i.test(`${device.platform} ${device.name}`)) {
        controlNote.textContent = "iPhone: стороннее приложение не может полноценно управлять экраном. Нужен Apple screen sharing или внешний approved-сервис.";
        return;
      }

      if (!device.online) {
        controlNote.textContent = "Сначала запусти Android Agent, чтобы устройство стало Online.";
        return;
      }

      try {
        controlNote.textContent = "Запрашиваю экран, жду ответ агента...";
        const result = await sendCommandAndWait(device, "request_screen");
        controlNote.textContent = "Запрос экрана отправлен. Подтверди запись экрана на телефоне, если Android спросит разрешение.";
        controlNote.textContent = commandResultText(result, "Запрос экрана обработан.");
        setTimeout(() => startScreenPolling(device, screenPreview, screenImage, controlNote), 1200);
      } catch (error) {
        controlNote.textContent = error.message;
      }
    });

    card.querySelector(".stop-screen-button").addEventListener("click", async () => {
      await sendSimpleDeviceCommand(device, "stop_screen", controlNote, "Команда остановки экрана отправлена.");
      stopScreenPolling(device.device_id);
    });

    card.querySelector(".back-button").addEventListener("click", () => {
      sendSimpleDeviceCommand(device, "back", controlNote, "Back отправлен.");
    });

    card.querySelector(".home-button").addEventListener("click", () => {
      sendSimpleDeviceCommand(device, "home", controlNote, "Home отправлен.");
    });

    card.querySelector(".recents-button").addEventListener("click", () => {
      sendSimpleDeviceCommand(device, "recents", controlNote, "Recent apps отправлен.");
    });

    card.querySelector(".notifications-button").addEventListener("click", () => {
      sendSimpleDeviceCommand(device, "notifications", controlNote, "Шторка уведомлений отправлена.");
    });

    card.querySelector(".quick-settings-button").addEventListener("click", () => {
      sendSimpleDeviceCommand(device, "quick_settings", controlNote, "Быстрые настройки отправлены.");
    });

    card.querySelector(".lock-screen-button").addEventListener("click", () => {
      sendSimpleDeviceCommand(device, "lock_screen", controlNote, "Блокировка экрана отправлена.");
    });

    card.querySelector(".settings-button").addEventListener("click", () => {
      sendSimpleDeviceCommand(device, "open_settings", controlNote, "Открытие Settings отправлено.");
    });

    card.querySelector(".wifi-settings-button").addEventListener("click", () => {
      sendSimpleDeviceCommand(device, "open_wifi_settings", controlNote, "Открытие Wi-Fi отправлено.");
    });

    card.querySelector(".battery-settings-button").addEventListener("click", () => {
      sendSimpleDeviceCommand(device, "open_battery_settings", controlNote, "Открытие Battery отправлено.");
    });

    card.querySelector(".swipe-up-button").addEventListener("click", () => {
      sendSimpleDeviceCommand(device, "swipe_up", controlNote, "Swipe up отправлен.");
    });

    card.querySelector(".swipe-down-button").addEventListener("click", () => {
      sendSimpleDeviceCommand(device, "swipe_down", controlNote, "Swipe down отправлен.");
    });

    card.querySelector(".swipe-left-button").addEventListener("click", () => {
      sendSimpleDeviceCommand(device, "swipe_left", controlNote, "Swipe left отправлен.");
    });

    card.querySelector(".swipe-right-button").addEventListener("click", () => {
      sendSimpleDeviceCommand(device, "swipe_right", controlNote, "Swipe right отправлен.");
    });

    const remoteTextInput = card.querySelector(".remote-text-input");
    card.querySelector(".send-text-button").addEventListener("click", async () => {
      const text = remoteTextInput.value.trim();
      if (!text) {
        controlNote.textContent = "Введи текст для отправки.";
        return;
      }

      try {
        const result = await sendCommandAndWait(device, "input_text", { text });
        controlNote.textContent = "Текст отправлен.";
        controlNote.textContent = commandResultText(result, "Текст отправлен.");
        remoteTextInput.value = "";
      } catch (error) {
        controlNote.textContent = error.message;
      }
    });

    card.querySelector(".enter-button").addEventListener("click", () => {
      sendSimpleDeviceCommand(device, "key_enter", controlNote, "Enter отправлен.");
    });

    card.querySelector(".delete-key-button").addEventListener("click", () => {
      sendSimpleDeviceCommand(device, "key_delete", controlNote, "Delete отправлен.");
    });

    card.querySelector(".rename-device-button").addEventListener("click", async () => {
      const name = prompt("Новое имя устройства", device.name);
      if (!name || !name.trim()) {
        return;
      }

      try {
        await manageDevice(device, "rename", { name: name.trim() });
        controlNote.textContent = "Устройство переименовано.";
        await refreshDevices();
      } catch (error) {
        controlNote.textContent = error.message;
      }
    });

    card.querySelector(".revoke-device-button").addEventListener("click", async () => {
      if (!confirm("Сбросить привязку устройства? Агенту понадобится новый /pair.")) {
        return;
      }

      try {
        await manageDevice(device, "revoke");
        controlNote.textContent = "Привязка сброшена.";
        await refreshDevices();
      } catch (error) {
        controlNote.textContent = error.message;
      }
    });

    card.querySelector(".delete-device-button").addEventListener("click", async () => {
      if (!confirm("Удалить устройство из списка?")) {
        return;
      }

      try {
        await manageDevice(device, "delete");
        stopScreenPolling(device.device_id);
        await refreshDevices();
      } catch (error) {
        controlNote.textContent = error.message;
      }
    });

    let pointerStart = null;
    const normalizedPoint = (event) => {
      const rect = screenImage.getBoundingClientRect();
      return {
        x: Math.max(0, Math.min(1, (event.clientX - rect.left) / rect.width)),
        y: Math.max(0, Math.min(1, (event.clientY - rect.top) / rect.height)),
      };
    };

    screenImage.addEventListener("pointerdown", (event) => {
      pointerStart = normalizedPoint(event);
      screenImage.setPointerCapture?.(event.pointerId);
    });

    screenImage.addEventListener("pointercancel", () => {
      pointerStart = null;
    });

    screenImage.addEventListener("pointerup", async (event) => {
      if (!device.online) {
        controlNote.textContent = "Жест недоступен, пока устройство offline.";
        pointerStart = null;
        return;
      }

      const start = pointerStart || normalizedPoint(event);
      const end = normalizedPoint(event);
      const distance = Math.hypot(end.x - start.x, end.y - start.y);
      pointerStart = null;

      try {
        if (distance > 0.06) {
          const result = await sendCommandAndWait(device, "swipe", {
            x: start.x,
            y: start.y,
            end_x: end.x,
            end_y: end.y,
          });
          controlNote.textContent = "Свайп по экрану отправлен.";
          return;
        }

        const result = await sendCommandAndWait(device, "tap", { x: end.x, y: end.y });
        controlNote.textContent = `Тап отправлен: ${Math.round(end.x * 100)}%, ${Math.round(end.y * 100)}%.`;
      } catch (error) {
        controlNote.textContent = error.message;
      }
    });

    screenImage.addEventListener("dblclick", async (event) => {
      if (!device.online) {
        controlNote.textContent = "Long tap недоступен, пока устройство offline.";
        return;
      }

      const point = normalizedPoint(event);
      try {
        const result = await sendCommandAndWait(device, "long_tap", point);
        controlNote.textContent = "Long tap отправлен.";
      } catch (error) {
        controlNote.textContent = error.message;
      }
    });

    card.querySelector(".files-button").addEventListener("click", async () => {
      if (!device.online) {
        controlNote.textContent = "Файлы недоступны, пока устройство offline.";
        return;
      }

      try {
        const result = await sendCommandAndWait(device, "request_files");
        controlNote.textContent = "Запрос файлов отправлен агенту. Следующий модуль откроет выбор разрешённых папок на Android.";
      } catch (error) {
        controlNote.textContent = error.message;
      }
    });

    card.querySelector(".commands-button").addEventListener("click", async () => {
      if (!device.online) {
        controlNote.textContent = "Команды появятся после запуска агента.";
        return;
      }

      try {
        const result = await sendCommandAndWait(device, "request_actions");
        controlNote.textContent = "Команда отправлена агенту. Агент подтвердит получение в своём статусе.";
      } catch (error) {
        controlNote.textContent = error.message;
      }
    });

    const idButton = card.querySelector(".id-button");
    idButton.addEventListener("click", () => {
      navigator.clipboard?.writeText(device.device_id);
      idButton.textContent = "Скопировано";
      setTimeout(() => {
        idButton.textContent = "ID";
      }, 1200);
    });

    deviceList.append(card);
  });
}

function renderCurrentDevice() {
  const currentDevice = detectCurrentDevice();
  currentDeviceText.textContent = `${currentDevice.name} · ${currentDevice.platform} · owner ${ownerId}`;
}

async function refreshDevices() {
  try {
    await loadDevicesFromApi();
    render();
  } catch (error) {
    deviceList.innerHTML = `<p class="empty-state">${error.message}</p>`;
  }
}

deviceForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  const name = deviceName.value.trim();
  if (!name) {
    return;
  }

  try {
    await registerDevice({
      device_id: `manual-${crypto.randomUUID()}`,
      name,
      type: deviceType.value,
      platform: "Вручную",
      agent: "mini-app-dev",
    });
    deviceName.value = "";
    await refreshDevices();
  } catch (error) {
    currentDeviceText.textContent = error.message;
  }
});

connectCurrentDevice.addEventListener("click", async () => {
  currentDeviceText.textContent = "Открываю установку Android Agent...";
  openExternal(`${apiBaseUrl}/agent`);
  return;

  const currentDevice = detectCurrentDevice();

  try {
    await registerDevice({
      device_id: localDeviceId,
      name: currentDevice.name,
      type: currentDevice.type,
      platform: currentDevice.platform,
      agent: "mini-app-dev",
    });
    await refreshDevices();
    renderCurrentDevice();
  } catch (error) {
    currentDeviceText.textContent = `${error.message}. Для продакшена устройство должен добавлять агент.`;
  }
});

installAgentButton.addEventListener("click", () => {
  setupText.textContent = "Открываю страницу установки APK...";
  openExternal(`${apiBaseUrl}/agent`);
});

requestPairButton.addEventListener("click", async () => {
  setupText.textContent = "Создаю QR и код подключения...";
  try {
    const payload = await createPairingQr();
    currentPairLinks = payload.links;
    pairQrImage.src = payload.qr_image_data;
    pairCode.textContent = payload.code;
    pairResult.classList.remove("hidden");
    setupText.textContent = "QR готов. Открой его на телефоне или введи код в Android Agent.";
    sendBotEvent("request_pair");
  } catch (error) {
    setupText.textContent = `${error.message}. Запасной способ: отправь /pair боту.`;
  }
});

openPairPageButton.addEventListener("click", () => {
  if (currentPairLinks?.web_link) {
    openExternal(currentPairLinks.web_link);
  }
});

openAgentDeepLinkButton.addEventListener("click", () => {
  if (currentPairLinks?.app_link) {
    openExternal(currentPairLinks.app_link);
  }
});

refreshButton.addEventListener("click", async () => {
  setupText.textContent = "Обновляю список устройств...";
  await refreshDevices();
});

themeButton.addEventListener("click", () => {
  const dark = !document.documentElement.classList.contains("dark");
  document.documentElement.classList.toggle("dark", dark);
  localStorage.setItem("apk_converter_theme", dark ? "dark" : "light");
});

setTelegramTheme();
renderCurrentDevice();
refreshDevices();
setInterval(refreshDevices, 15000);
