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
  screenPollers.set(device.device_id, setInterval(loadFrame, 3000));
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
    await sendCommand(device, type);
    controlNote.textContent = successText;
  } catch (error) {
    controlNote.textContent = error.message;
  }
}

function render() {
  deviceList.innerHTML = "";
  totalDevices.textContent = devices.length;
  onlineDevices.textContent = devices.filter((device) => device.online).length;
  userName.textContent = profileName;

  if (!devices.length) {
    deviceList.innerHTML = `<p class="empty-state">Пока нет подключенных устройств. Запусти агент на телефоне или нажми "Подключить" для проверки.</p>`;
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
        await sendCommand(device, "request_screen");
        controlNote.textContent = "Запрос экрана отправлен. Подтверди запись экрана на телефоне, если Android спросит разрешение.";
        setTimeout(() => startScreenPolling(device, screenPreview, screenImage, controlNote), 2500);
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
        await sendCommand(device, "input_text", { text });
        controlNote.textContent = "Текст отправлен.";
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

    screenImage.addEventListener("click", async (event) => {
      if (!device.online) {
        controlNote.textContent = "Тап недоступен, пока устройство offline.";
        return;
      }

      const rect = screenImage.getBoundingClientRect();
      const x = (event.clientX - rect.left) / rect.width;
      const y = (event.clientY - rect.top) / rect.height;
      try {
        await sendCommand(device, "tap", {
          x: Math.max(0, Math.min(1, x)),
          y: Math.max(0, Math.min(1, y)),
        });
        controlNote.textContent = `Тап отправлен: ${Math.round(x * 100)}%, ${Math.round(y * 100)}%.`;
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
        await sendCommand(device, "request_files");
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
        await sendCommand(device, "request_actions");
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

themeButton.addEventListener("click", () => {
  const dark = !document.documentElement.classList.contains("dark");
  document.documentElement.classList.toggle("dark", dark);
  localStorage.setItem("apk_converter_theme", dark ? "dark" : "light");
});

setTelegramTheme();
renderCurrentDevice();
refreshDevices();
setInterval(refreshDevices, 15000);
