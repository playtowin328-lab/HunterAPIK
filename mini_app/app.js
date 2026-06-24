const tg = window.Telegram?.WebApp;

if (tg) {
  tg.ready();
  tg.expand();
}

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];

const themeButton = $("#themeButton");
const deviceForm = $("#deviceForm");
const deviceName = $("#deviceName");
const deviceType = $("#deviceType");
const deviceList = $("#deviceList");
const currentDeviceText = $("#currentDeviceText");
const connectCurrentDevice = $("#connectCurrentDevice");
const setupText = $("#setupText");
const installAgentButton = $("#installAgentButton");
const openInstalledAgentButton = $("#openInstalledAgentButton");
const requestPairButton = $("#requestPairButton");
const refreshButton = $("#refreshButton");
const pairResult = $("#pairResult");
const pairQrImage = $("#pairQrImage");
const pairCode = $("#pairCode");
const openPairPageButton = $("#openPairPageButton");
const openAgentDeepLinkButton = $("#openAgentDeepLinkButton");
const deployPanel = $("#deployPanel");
const deployRefreshButton = $("#deployRefreshButton");
const deployStatusTitle = $("#deployStatusTitle");
const deployReadyStatus = $("#deployReadyStatus");
const deployFixCount = $("#deployFixCount");
const deployPublicUrl = $("#deployPublicUrl");
const deployChecklist = $("#deployChecklist");
const totalDevices = $("#totalDevices");
const onlineDevices = $("#onlineDevices");
const userName = $("#userName");
const template = $("#deviceCardTemplate");
const remotePanel = $("#remotePanel");
const remoteDeviceTitle = $("#remoteDeviceTitle");
const remoteDeviceMeta = $("#remoteDeviceMeta");
const closeRemotePanel = $("#closeRemotePanel");
const remoteScreenPreview = $("#remoteScreenPreview");
const remoteScreenImage = $("#remoteScreenImage");
const remoteControlNote = $("#remoteControlNote");
const remotePanelTextInput = $("#remotePanelTextInput");
const remotePanelSendText = $("#remotePanelSendText");
const remoteConnectionStatus = $("#remoteConnectionStatus");
const remoteBatteryStatus = $("#remoteBatteryStatus");
const remoteSecurityStatus = $("#remoteSecurityStatus");
const remoteCommandStatus = $("#remoteCommandStatus");
const remoteTabs = $$(".remote-tabs button");
const remoteTabPanels = $$(".remote-tab-panel");
const remoteSetupAutomation = $("#remoteSetupAutomation");
const remoteSetupProgress = $("#remoteSetupProgress");
const remoteSetupChecklist = $("#remoteSetupChecklist");
const nextSetupStepButton = $("#nextSetupStepButton");
const remoteActionLog = $("#remoteActionLog");
const remoteLogClearButton = $("#remoteLogClearButton");
const deviceAlertPanel = $("#deviceAlertPanel");
const deviceAlertRefreshButton = $("#deviceAlertRefreshButton");
const deviceAlertSaveButton = $("#deviceAlertSaveButton");
const deviceAlertsEnabled = $("#deviceAlertsEnabled");
const deviceAlertsQuietEnabled = $("#deviceAlertsQuietEnabled");
const deviceAlertsQuietStart = $("#deviceAlertsQuietStart");
const deviceAlertsQuietEnd = $("#deviceAlertsQuietEnd");
const deviceAlertKinds = $("#deviceAlertKinds");
const deviceAlertLog = $("#deviceAlertLog");

const telegramUser = tg?.initDataUnsafe?.user;
const profileName = telegramUser?.first_name || telegramUser?.username || "Я";
const urlParams = new URLSearchParams(window.location.search);
const ownerId = String(telegramUser?.id || urlParams.get("owner_id") || localStorage.getItem("apk_owner_id") || crypto.randomUUID());
localStorage.setItem("apk_owner_id", ownerId);

const apiBaseUrl = window.location.origin;
const agentOpenLink = `apkagent://open?server=${encodeURIComponent(apiBaseUrl)}&owner_id=${encodeURIComponent(ownerId)}&setup=1`;
const agentInstallUrl = `${apiBaseUrl}/agent?owner_id=${encodeURIComponent(ownerId)}`;
const localDeviceIdKey = "apk_converter_local_device_id";
const typeNames = {
  phone: "Телефон",
  tablet: "Планшет",
  pc: "Компьютер",
};
const qualityProfiles = {
  fast: { label: "Быстро", requestMs: 650, frameMs: 500, waitMs: 1200, max_size: 720 },
  balanced: { label: "Баланс", requestMs: 900, frameMs: 700, waitMs: 1800, max_size: 960 },
  quality: { label: "Качество", requestMs: 1400, frameMs: 1000, waitMs: 2600, max_size: 1440 },
};
const remoteCommandMessages = {
  back: "Кнопка Назад отправлена.",
  home: "Кнопка Домой отправлена.",
  recents: "Открываются недавние приложения.",
  notifications: "Шторка уведомлений открывается.",
  quick_settings: "Быстрые настройки открываются.",
  wake_screen: "Экран пробуждается.",
  dismiss_keyguard: "Запрос разблокировки отправлен. PIN и биометрию нужно подтвердить на телефоне.",
  swipe_up: "Свайп вверх отправлен.",
  swipe_down: "Свайп вниз отправлен.",
  swipe_left: "Свайп влево отправлен.",
  swipe_right: "Свайп вправо отправлен.",
  lost_mode_on: "Режим кражи включается: экран закрывается, сигнал запускается, блокировка запрошена.",
  lost_mode_off: "Режим кражи выключается.",
  blackout_on: "Черный защитный экран включается.",
  blackout_off: "Черный экран выключается.",
  play_alarm: "Громкий сигнал запускается на телефоне.",
  stop_alarm: "Сигнал останавливается.",
  lock_screen: "Блокировка экрана запрошена.",
  request_notification_permission: "Запрос уведомлений открыт на телефоне.",
  request_battery_permission: "Запрос работы в фоне открыт на телефоне.",
  request_accessibility_permission: "Настройки жестов и Accessibility открыты на телефоне.",
  request_screen_permission: "Запрос доступа к экрану открыт на телефоне.",
  setup_wizard: "Мастер автонастройки открыт на телефоне.",
  repair_agent: "Ремонт связи запущен на телефоне.",
  ping: "Агент отвечает.",
  open_settings: "Открываются настройки телефона.",
  open_wifi_settings: "Открываются настройки Wi-Fi.",
  open_battery_settings: "Открываются настройки батареи.",
  request_actions: "Проверка модуля управления отправлена.",
  request_files: "Запрос файлов отправлен агенту.",
  key_enter: "Enter отправлен.",
  key_delete: "Delete отправлен.",
};

const deviceAlertKindLabels = {
  online: "Online",
  offline: "Offline",
  battery: "Батарея",
  charging: "Зарядка",
  network: "Сеть",
  lost_mode: "Lost Mode",
  blackout: "Черный экран",
  accessibility: "Жесты",
  screen: "Экран",
  agent_error: "Ошибка агента",
  screen_error: "Ошибка экрана",
  command_queue: "Очередь команд",
  health: "Здоровье",
};

let devices = [];
let currentPairLinks = null;
let currentPairExpiresAt = 0;
let selectedDeviceId = localStorage.getItem("hunter_selected_device_id") || "";
let remotePanelCollapsed = false;
let refreshInFlight = false;
let refreshTimer = null;
let setupStatus = null;
let setupStatusLoading = false;
let remoteCommandBusy = false;
let remoteLogItems = [];
let activeRemoteTab = localStorage.getItem("hunter_remote_tab") || "setup";
let deviceAlertSettings = null;
let deviceAlertEvents = [];
let deviceAlertKindList = [];
const screenPollers = new Map();
const pendingScreenRequests = new Set();
window.currentDeviceScope = "own";

function getLocalDeviceId() {
  const existingId = localStorage.getItem(localDeviceIdKey);
  if (existingId) return existingId;
  const newId = crypto.randomUUID();
  localStorage.setItem(localDeviceIdKey, newId);
  return newId;
}

const localDeviceId = getLocalDeviceId();

function openExternal(url) {
  if (tg?.openLink) {
    tg.openLink(url);
    return;
  }
  window.open(url, "_blank", "noopener");
}

function sendBotEvent(event, payload = {}) {
  if (!tg?.sendData) return false;
  tg.sendData(JSON.stringify({ event, ...payload }));
  return true;
}

function isAdbBridge(device) {
  return /adb-bridge/i.test(`${device.agent || ""} ${device.platform || ""}`);
}

function qualityStorageKey(device) {
  return `hunter_quality_${device.device_id}`;
}

function getDeviceQuality(device) {
  const saved = localStorage.getItem(qualityStorageKey(device)) || "balanced";
  return qualityProfiles[saved] ? saved : "balanced";
}

function setDeviceQuality(device, value) {
  const quality = qualityProfiles[value] ? value : "balanced";
  localStorage.setItem(qualityStorageKey(device), quality);
  return quality;
}

function qualityPayload(device) {
  const quality = getDeviceQuality(device);
  return {
    stream: true,
    quality,
    max_size: qualityProfiles[quality].max_size,
    reveal_blackout: true,
    blackout_reveal_ms: 1400,
  };
}

function selectedDevice() {
  return devices.find((device) => device.device_id === selectedDeviceId) || null;
}

function selectDevice(device) {
  selectedDeviceId = device.device_id;
  remotePanelCollapsed = false;
  localStorage.setItem("hunter_selected_device_id", selectedDeviceId);
  renderRemotePanel(false);
}

function setRemoteTab(tabName) {
  const availableTabs = new Set(remoteTabs.map((button) => button.dataset.remoteTab));
  activeRemoteTab = availableTabs.has(tabName) ? tabName : "setup";
  localStorage.setItem("hunter_remote_tab", activeRemoteTab);

  remoteTabs.forEach((button) => {
    const active = button.dataset.remoteTab === activeRemoteTab;
    button.classList.toggle("active", active);
    button.setAttribute("aria-selected", String(active));
  });

  remoteTabPanels.forEach((panel) => {
    panel.classList.toggle("active", panel.dataset.tabPanel === activeRemoteTab);
  });
}

function detectCurrentDevice() {
  const platform = tg?.platform || "unknown";
  const userAgent = navigator.userAgent;
  const isIphone = /iPhone/i.test(userAgent) || platform === "ios";
  const isIpad = /iPad/i.test(userAgent);
  const isAndroid = /Android/i.test(userAgent) || platform === "android";
  const androidModelMatch = userAgent.match(/Android[^;]*;\s?([^;)]+)[;)]/i);

  if (isIphone) return { name: "iPhone", type: "phone", platform: "iOS" };
  if (isIpad) return { name: "iPad", type: "tablet", platform: "iPadOS" };
  if (isAndroid) {
    const model = androidModelMatch?.[1]?.replace(/Build\/.*/i, "").trim();
    return { name: model && model.length < 32 ? model : "Android телефон", type: "phone", platform: "Android" };
  }
  return { name: "Это устройство", type: "pc", platform: platform === "unknown" ? "Браузер" : platform };
}

function formatLastSeen(value) {
  if (!value) return "нет данных";
  return new Intl.DateTimeFormat("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value * 1000));
}

function formatTelemetry(device) {
  const telemetry = device.telemetry || {};
  const diagnostics = device.diagnostics || {};
  const items = [];

  if (typeof telemetry.battery_percent === "number" && telemetry.battery_percent >= 0) {
    items.push(`${telemetry.battery_percent}%${telemetry.charging ? " · зарядка" : ""}`);
  }
  if (telemetry.network) items.push(`сеть: ${telemetry.network}`);
  if (telemetry.android) items.push(`Android ${telemetry.android}`);
  if (typeof telemetry.full_control === "boolean") items.push(telemetry.full_control ? "Full APK" : "Lite APK");
  if (typeof telemetry.agent_enabled === "boolean") items.push(`agent: ${telemetry.agent_enabled ? "on" : "off"}`);
  if (typeof telemetry.last_success_age === "number" && telemetry.last_success_age >= 0) items.push(`last ok: ${telemetry.last_success_age} сек`);
  if (typeof telemetry.lost_mode === "boolean") items.push(`lost: ${telemetry.lost_mode ? "on" : "off"}`);
  if (typeof telemetry.blackout === "boolean") items.push(`blackout: ${telemetry.blackout ? "on" : "off"}`);
  if (telemetry.setup_wizard) items.push(`setup: ${telemetry.setup_waiting_for || "active"}`);
  if (typeof telemetry.notifications_ready === "boolean") items.push(`уведомления: ${telemetry.notifications_ready ? "on" : "off"}`);
  if (typeof telemetry.battery_ready === "boolean") items.push(`фон: ${telemetry.battery_ready ? "on" : "off"}`);
  if (typeof telemetry.accessibility === "boolean") items.push(`жесты: ${telemetry.accessibility ? "on" : "off"}`);
  if (typeof telemetry.screen_streaming === "boolean") items.push(`экран: ${telemetry.screen_streaming ? "on" : "off"}`);
  if (typeof telemetry.loop_ms === "number" && telemetry.loop_ms > 0) items.push(`agent: ${telemetry.loop_ms} ms`);
  if (typeof telemetry.command_ms === "number" && telemetry.command_ms > 0) items.push(`cmd: ${telemetry.command_ms} ms`);
  if (typeof telemetry.gesture_ms === "number" && telemetry.gesture_ms > 0) items.push(`gesture: ${telemetry.gesture_ms} ms`);
  if (telemetry.gesture_result) items.push(`gesture: ${telemetry.gesture_result}`);
  if (typeof telemetry.screen_ms === "number" && telemetry.screen_ms > 0) items.push(`screen: ${telemetry.screen_ms} ms`);
  if (typeof telemetry.screen_frames === "number" && telemetry.screen_frames > 0) items.push(`frames: ${telemetry.screen_frames}`);
  if (typeof telemetry.screen_dropped === "number" && telemetry.screen_dropped > 0) items.push(`drop: ${telemetry.screen_dropped}`);
  if (typeof telemetry.error_count === "number" && telemetry.error_count > 0) items.push(`errors: ${telemetry.error_count}`);
  if (diagnostics.pending_commands) items.push(`очередь: ${diagnostics.pending_commands}`);
  if (typeof diagnostics.frame_age === "number") items.push(`кадр: ${diagnostics.frame_age} сек`);
  if (telemetry.last_error) items.push(`ошибка: ${telemetry.last_error}`);
  if (telemetry.screen_error) items.push(`screen error: ${telemetry.screen_error}`);
  return items;
}

function formatDiagnostics(device) {
  const diagnostics = device.diagnostics || {};
  const telemetry = device.telemetry || {};
  const parts = [];

  if (typeof diagnostics.frame_age === "number") parts.push(`кадр ${diagnostics.frame_age} сек`);
  if (diagnostics.pending_commands) parts.push(`очередь ${diagnostics.pending_commands}`);
  if (diagnostics.delivered_commands) parts.push(`доставлено ${diagnostics.delivered_commands}`);
  if (diagnostics.last_command) {
    const last = diagnostics.last_command;
    parts.push(`последняя: ${last.type} · ${last.status} · ${last.duration_ms || 0} ms`);
  }
  if (typeof telemetry.loop_ms === "number" && telemetry.loop_ms > 0) parts.push(`агент ${telemetry.loop_ms} ms`);
  if (typeof telemetry.screen_ms === "number" && telemetry.screen_ms > 0) parts.push(`экран ${telemetry.screen_ms} ms`);
  if (typeof telemetry.gesture_ms === "number" && telemetry.gesture_ms > 0) parts.push(`жест ${telemetry.gesture_ms} ms`);
  if (telemetry.gesture_result) parts.push(telemetry.gesture_result);
  if (telemetry.last_error) parts.push(`ошибка: ${telemetry.last_error}`);
  return parts.join(" · ");
}

function formatHealthHint(device, fallback = "") {
  const health = device.health || {};
  const hints = Array.isArray(health.hints) ? health.hints.filter(Boolean) : [];
  if (hints.length) return hints.join(" ");
  if (fallback) return fallback;
  return device.online ? "Готов к командам." : "Запусти Android Agent на телефоне.";
}

function formatDeviceNote(device) {
  const diagnostics = formatDiagnostics(device);
  const healthHint = formatHealthHint(device);
  if (device.online) {
    return diagnostics ? `${healthHint} ${diagnostics}` : healthHint;
  }
  return diagnostics ? `${healthHint} Последнее: ${diagnostics}` : healthHint;
}

function formatRemoteStatus(device) {
  const telemetry = device?.telemetry || {};
  const diagnostics = device?.diagnostics || {};
  const battery = typeof telemetry.battery_percent === "number" && telemetry.battery_percent >= 0
    ? `${telemetry.battery_percent}%${telemetry.charging ? " · заряд" : ""}`
    : "нет данных";
  const security = [
    telemetry.lost_mode ? "Lost" : "",
    telemetry.blackout ? "Black" : "",
    telemetry.accessibility ? "жесты" : "",
    telemetry.screen_streaming ? "экран" : "",
  ].filter(Boolean).join(" · ") || "готово";
  const pending = Number(diagnostics.pending_commands || 0);
  const delivered = Number(diagnostics.delivered_commands || 0);
  const last = diagnostics.last_command?.type ? ` · ${diagnostics.last_command.type}` : "";
  return {
    connection: device?.online ? (device.health?.label || "Online") : "Offline",
    battery,
    security,
    commands: pending ? `ждет ${pending}${last}` : (delivered ? `дост. ${delivered}${last}` : `чисто${last}`),
  };
}

function setupSteps(device) {
  const telemetry = device?.telemetry || {};
  const isOnline = Boolean(device?.online);
  const isAndroid = /android/i.test(`${device?.platform || ""} ${device?.name || ""} ${telemetry.android || ""}`);
  const isFull = telemetry.full_control === true;
  const isLite = telemetry.full_control === false;
  const agentReady = isOnline && telemetry.agent_enabled !== false;
  const notificationsKnown = typeof telemetry.notifications_ready === "boolean";
  const batteryKnown = typeof telemetry.battery_ready === "boolean";

  return [
    {
      key: "agent",
      title: "Связь с агентом",
      detail: agentReady ? "Heartbeat приходит, команды можно отправлять." : "Открой Agent или запусти ремонт связи.",
      status: agentReady ? "ready" : "blocked",
      command: "repair_agent",
    },
    {
      key: "notifications",
      title: "Уведомления",
      detail: notificationsKnown
        ? (telemetry.notifications_ready ? "Foreground-сервис не будет тихо выключен Android." : "Нужно подтвердить уведомления на телефоне.")
        : "Обнови APK, чтобы видеть точный статус уведомлений.",
      status: !isAndroid ? "skipped" : (telemetry.notifications_ready === true ? "ready" : "todo"),
      command: "request_notification_permission",
    },
    {
      key: "battery",
      title: "Работа в фоне",
      detail: isLite
        ? "Lite APK не просит отключать оптимизацию батареи."
        : (batteryKnown && telemetry.battery_ready ? "Оптимизация батареи отключена для агента." : "Нужно разрешить работу в фоне."),
      status: !isAndroid || isLite ? "skipped" : (telemetry.battery_ready === true ? "ready" : "todo"),
      command: "request_battery_permission",
    },
    {
      key: "accessibility",
      title: "Жесты и ввод",
      detail: isLite
        ? "Жесты доступны только в Full APK."
        : (telemetry.accessibility ? "Accessibility включен, тапы и свайпы готовы." : "Включи Hunter Agent в Accessibility."),
      status: !isAndroid || isLite ? "skipped" : (telemetry.accessibility ? "ready" : "todo"),
      command: "request_accessibility_permission",
    },
    {
      key: "screen",
      title: "Экран",
      detail: isLite
        ? "Трансляция экрана доступна только в Full APK."
        : (telemetry.screen_streaming ? "Трансляция активна." : "Запусти запрос экрана и подтверди системное окно."),
      status: !isAndroid || isLite ? "skipped" : (telemetry.screen_streaming ? "ready" : "todo"),
      command: "request_screen_permission",
    },
    {
      key: "wizard",
      title: "Мастер",
      detail: telemetry.setup_wizard
        ? `Ожидает шаг: ${telemetry.setup_waiting_for || "следующее подтверждение"}.`
        : "Может провести по разрешениям на телефоне.",
      status: telemetry.setup_wizard ? "todo" : (isFull || isLite ? "ready" : "skipped"),
      command: "setup_wizard",
    },
  ];
}

function setupStatusLabel(status) {
  if (status === "ready") return "готово";
  if (status === "skipped") return "не нужно";
  if (status === "blocked") return "нет связи";
  return "нужно действие";
}

function nextSetupStep(device) {
  const steps = setupSteps(device);
  return steps.find((step) => step.status === "blocked") || steps.find((step) => step.status === "todo") || null;
}

function renderSetupAutomation(device) {
  if (!remoteSetupAutomation || !remoteSetupChecklist || !remoteSetupProgress) return;
  const steps = setupSteps(device);
  const actionableSteps = steps.filter((step) => step.status !== "skipped");
  const readyCount = actionableSteps.filter((step) => step.status === "ready").length;
  const nextStep = nextSetupStep(device);

  remoteSetupProgress.textContent = nextStep
    ? `${readyCount}/${actionableSteps.length} готово · дальше: ${nextStep.title}`
    : `${readyCount}/${actionableSteps.length} готово · настройка завершена`;

  remoteSetupChecklist.innerHTML = steps.map((step) => `
    <div class="setup-check" data-status="${step.status}">
      <span>${setupStatusLabel(step.status)}</span>
      <strong>${escapeHtml(step.title)}</strong>
      <small>${escapeHtml(step.detail)}</small>
    </div>
  `).join("");

  if (nextSetupStepButton) {
    nextSetupStepButton.disabled = !nextStep || remoteCommandBusy || !device?.online;
    nextSetupStepButton.dataset.command = nextStep?.command || "";
    nextSetupStepButton.textContent = nextStep ? `Открыть: ${nextStep.title}` : "Все готово";
  }
}

function canControlDevice(device) {
  return Boolean(device?.online && device?.health?.state !== "revoked");
}

function setTelegramTheme() {
  const savedTheme = localStorage.getItem("apk_converter_theme");
  const dark = savedTheme ? savedTheme === "dark" : tg?.colorScheme === "dark";
  document.documentElement.classList.toggle("dark", dark);
}

async function apiJson(url, options = {}) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), options.timeoutMs || 12000);
  const response = await fetch(url, { ...options, signal: controller.signal }).finally(() => clearTimeout(timeout));
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.error || `HTTP ${response.status}`);
  }
  return payload;
}

function renderSetupStatus() {
  if (!deployPanel || !deployStatusTitle || !deployChecklist) return;
  const status = setupStatus;
  deployPanel.dataset.ready = status?.ok ? "ready" : "fix";

  if (setupStatusLoading && !status) {
    deployStatusTitle.textContent = "Проверяю настройку";
    deployReadyStatus.textContent = "-";
    deployFixCount.textContent = "-";
    deployPublicUrl.textContent = "-";
    deployChecklist.innerHTML = `<div class="deploy-check" data-status="pending"><span>WAIT</span><strong>Загрузка</strong><small>Получаю /setup-status...</small></div>`;
    return;
  }

  if (!status) {
    deployStatusTitle.textContent = "Статус недоступен";
    deployReadyStatus.textContent = "нет данных";
    deployFixCount.textContent = "-";
    deployPublicUrl.textContent = apiBaseUrl;
    deployChecklist.innerHTML = `<div class="deploy-check" data-status="fix"><span>FIX</span><strong>Setup API</strong><small>Нажми «Проверить» или обнови мини-апп.</small></div>`;
    return;
  }

  const checks = Array.isArray(status.checks) ? status.checks : [];
  const failed = checks.filter((item) => !item.ok);
  const importantChecks = failed.length ? failed : checks.filter((item) => item.required).slice(0, 4);
  deployStatusTitle.textContent = status.ok ? "Настройка готова" : "Нужна настройка";
  deployReadyStatus.textContent = status.ok ? "готово" : "исправить";
  deployFixCount.textContent = String(status.required_failed_count ?? failed.length);
  deployPublicUrl.textContent = status.public_url || apiBaseUrl;
  deployChecklist.innerHTML = importantChecks.length
    ? importantChecks.map((item) => `
      <div class="deploy-check" data-status="${item.ok ? "ready" : "fix"}">
        <span>${item.ok ? "OK" : "FIX"}</span>
        <strong>${escapeHtml(item.name || "check")}</strong>
        <small>${escapeHtml(item.ok ? item.detail : (item.fix || item.detail || "Проверь Railway variables"))}</small>
      </div>
    `).join("")
    : `<div class="deploy-check" data-status="ready"><span>OK</span><strong>Railway</strong><small>Базовые переменные готовы.</small></div>`;
}

async function loadSetupStatus() {
  if (setupStatusLoading) return;
  setupStatusLoading = true;
  renderSetupStatus();
  try {
    setupStatus = await apiJson(`${apiBaseUrl}/setup-status`, { timeoutMs: 8000 });
  } catch (error) {
    setupStatus = {
      ok: false,
      public_url: apiBaseUrl,
      required_failed_count: 1,
      checks: [
        {
          name: "setup-status",
          ok: false,
          detail: error.message,
          fix: "Проверь деплой Railway и endpoint /setup-status",
          required: true,
        },
      ],
    };
  } finally {
    setupStatusLoading = false;
    renderSetupStatus();
  }
}

async function loadDevicesFromApi() {
  const params = new URLSearchParams({ owner_id: ownerId });
  if (tg?.initData) params.set("init_data", tg.initData);
  const payload = await apiJson(`${apiBaseUrl}/api/devices?${params.toString()}`);
  devices = payload.devices || [];
  window.currentDeviceScope = payload.scope || "own";
}

function createPairingQr() {
  return apiJson(`${apiBaseUrl}/api/pair/new?owner_id=${encodeURIComponent(ownerId)}`);
}

function apiAuthPayload(extra = {}) {
  if (!tg?.initData) return { ...extra };
  return { actor_id: ownerId, init_data: tg.initData, ...extra };
}

function apiAuthParams(extra = {}) {
  const params = new URLSearchParams({ ...extra });
  if (tg?.initData) {
    params.set("actor_id", ownerId);
    params.set("init_data", tg.initData);
  }
  return params;
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  }[char]));
}

function formatAlertTime(timestamp) {
  if (!timestamp) return "";
  return new Intl.DateTimeFormat("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(timestamp * 1000));
}

async function loadDeviceAlerts() {
  if (!tg?.initData || !deviceAlertPanel) return;
  const params = apiAuthParams({ limit: "30" });
  try {
    const payload = await apiJson(`${apiBaseUrl}/api/alerts/device?${params.toString()}`);
    deviceAlertSettings = payload.settings || null;
    deviceAlertEvents = payload.events || [];
    deviceAlertKindList = payload.kinds || [];
    renderDeviceAlerts();
  } catch (_) {
    deviceAlertPanel.classList.add("hidden");
  }
}

function currentDeviceAlertSettingsFromForm() {
  const checkedKinds = $$(".alert-kind-grid input:checked", deviceAlertPanel).map((input) => input.value);
  return {
    enabled: Boolean(deviceAlertsEnabled?.checked),
    quiet_hours_enabled: Boolean(deviceAlertsQuietEnabled?.checked),
    quiet_hours_start: Number(deviceAlertsQuietStart?.value || 23),
    quiet_hours_end: Number(deviceAlertsQuietEnd?.value || 8),
    enabled_kinds: checkedKinds,
  };
}

async function saveDeviceAlertSettings() {
  if (!deviceAlertSettings) return;
  deviceAlertSaveButton.disabled = true;
  try {
    const payload = await apiJson(`${apiBaseUrl}/api/alerts/device/settings`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(apiAuthPayload({ settings: currentDeviceAlertSettingsFromForm() })),
    });
    deviceAlertSettings = payload.settings;
    deviceAlertKindList = payload.kinds || deviceAlertKindList;
    renderDeviceAlerts();
  } catch (error) {
    deviceAlertLog.innerHTML = `<li data-status="error"><p>${escapeHtml(error.message)}</p></li>`;
  } finally {
    deviceAlertSaveButton.disabled = false;
  }
}

function renderDeviceAlerts() {
  if (!deviceAlertSettings || !deviceAlertPanel) return;
  deviceAlertPanel.classList.remove("hidden");
  deviceAlertsEnabled.checked = Boolean(deviceAlertSettings.enabled);
  deviceAlertsQuietEnabled.checked = Boolean(deviceAlertSettings.quiet_hours_enabled);
  deviceAlertsQuietStart.value = deviceAlertSettings.quiet_hours_start ?? 23;
  deviceAlertsQuietEnd.value = deviceAlertSettings.quiet_hours_end ?? 8;

  const enabledKinds = new Set(deviceAlertSettings.enabled_kinds || []);
  deviceAlertKinds.innerHTML = deviceAlertKindList.map((kind) => `
    <label class="alert-kind">
      <input type="checkbox" value="${escapeHtml(kind)}" ${enabledKinds.has(kind) ? "checked" : ""}>
      <span>${escapeHtml(deviceAlertKindLabels[kind] || kind)}</span>
    </label>
  `).join("");

  deviceAlertLog.innerHTML = deviceAlertEvents.length
    ? deviceAlertEvents.map((event) => {
      const metadata = event.metadata || {};
      const kind = metadata.kind || event.action;
      const deviceName = metadata.name || metadata.device_id || "Устройство";
      return `<li data-status="${escapeHtml(kind)}">
        <span>${escapeHtml(formatAlertTime(event.created_at))} · ${escapeHtml(deviceAlertKindLabels[kind] || kind)}</span>
        <strong>${escapeHtml(deviceName)}</strong>
        <p>${escapeHtml(event.detail)}</p>
      </li>`;
    }).join("")
    : '<li class="muted-log"><p>Пока нет уведомлений по устройствам.</p></li>';
}

function deviceOwnerId(device) {
  return String(device?.owner_id || ownerId);
}

function registerDevice(device) {
  return apiJson(`${apiBaseUrl}/api/devices/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(apiAuthPayload({ owner_id: ownerId, ...device })),
  });
}

function sendCommand(device, type, payload = {}) {
  return apiJson(`${apiBaseUrl}/api/devices/command`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(apiAuthPayload({ owner_id: deviceOwnerId(device), device_id: device.device_id, type, payload })),
  });
}

function getCommandStatus(device, commandId) {
  const params = apiAuthParams({
    owner_id: deviceOwnerId(device),
    device_id: device.device_id,
    command_id: commandId,
  });
  return apiJson(
    `${apiBaseUrl}/api/devices/commands/status?${params.toString()}`
  );
}

async function waitForCommandResult(device, commandPayload, timeoutMs = 9000) {
  const startedAt = performance.now();
  const commandId = commandPayload?.command?.command_id;
  if (!commandId) return commandPayload;

  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const payload = await getCommandStatus(device, commandId);
    const status = payload.command?.status;
    if (status && status !== "pending" && status !== "delivered") {
      payload.command.client_latency_ms = Math.round(performance.now() - startedAt);
      return payload;
    }
    await new Promise((resolve) => setTimeout(resolve, 250));
  }

  return {
    command: {
      ...commandPayload.command,
      status: "timeout",
      result: `Агент не подтвердил команду за ${Math.max(1, Math.round(timeoutMs / 1000))} сек.`,
    },
  };
}

async function sendCommandAndWait(device, type, payload = {}, timeoutMs = 9000) {
  const commandPayload = await sendCommand(device, type, payload);
  return waitForCommandResult(device, commandPayload, timeoutMs);
}

function commandResultText(payload, fallback) {
  const command = payload?.command;
  if (!command) return fallback;
  const latency = command.client_latency_ms ? ` · ${command.client_latency_ms} ms` : "";
  const result = command.result ? ` ${command.result}` : "";
  if (command.status === "acknowledged" || command.status === "done") return `${fallback}${latency}${result}`;
  if (command.status === "rejected") return `Отклонено.${result}`;
  if (command.status === "timeout") return command.result;
  return `${command.status || "Статус"}:${result}`;
}

function renderRemoteLog() {
  if (!remoteActionLog) return;
  remoteActionLog.innerHTML = remoteLogItems.length
    ? remoteLogItems.map((item) => `<li data-status="${item.status}"><span>${item.time}</span><strong>${item.title}</strong><p>${item.detail}</p></li>`).join("")
    : '<li class="muted-log"><p>Пока нет действий в этой сессии.</p></li>';
}

function addRemoteLog(title, detail, status = "info") {
  const time = new Intl.DateTimeFormat("ru-RU", { hour: "2-digit", minute: "2-digit", second: "2-digit" }).format(new Date());
  remoteLogItems = [{ time, title, detail, status }, ...remoteLogItems].slice(0, 8);
  renderRemoteLog();
}

function setRemoteBusy(value) {
  remoteCommandBusy = value;
  remotePanel.classList.toggle("busy", value);
  [
    ...$$(".remote-command-button", remotePanel),
    ...$$(".remote-manage-button", remotePanel),
    $(".remote-screen-button", remotePanel),
    $(".remote-stop-screen-button", remotePanel),
    remotePanelSendText,
    nextSetupStepButton,
  ].filter(Boolean).forEach((button) => {
    button.disabled = value;
  });

  if (!value) {
    renderSetupAutomation(selectedDevice());
  }
}
function manageDevice(device, action, payload = {}) {
  return apiJson(`${apiBaseUrl}/api/devices/manage`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(apiAuthPayload({ owner_id: deviceOwnerId(device), device_id: device.device_id, action, ...payload })),
  });
}

function loadScreenFrame(device) {
  const params = apiAuthParams({ owner_id: deviceOwnerId(device), device_id: device.device_id });
  return apiJson(`${apiBaseUrl}/api/devices/screen?${params.toString()}`);
}

async function requestFreshScreenFrame(device) {
  if (!device.online || pendingScreenRequests.has(device.device_id)) return;
  pendingScreenRequests.add(device.device_id);
  try {
    const profile = qualityProfiles[getDeviceQuality(device)];
    await sendCommandAndWait(device, "request_screen", qualityPayload(device), profile.waitMs);
  } catch (_) {
    // Live polling will show the stale/no-frame state.
  } finally {
    pendingScreenRequests.delete(device.device_id);
  }
}

function stopScreenPolling(deviceId) {
  const poller = screenPollers.get(deviceId);
  if (!poller) return;
  clearInterval(poller.frameTimer);
  if (poller.requestTimer) clearInterval(poller.requestTimer);
  screenPollers.delete(deviceId);
  pendingScreenRequests.delete(deviceId);
}

function startScreenPolling(device, screenPreview, screenImage, controlNote) {
  stopScreenPolling(device.device_id);

  const loadFrame = async () => {
    try {
      const payload = await loadScreenFrame(device);
      screenImage.src = payload.frame.image_data;
      screenPreview.hidden = false;
      const frameAge = Math.max(0, Math.round(Date.now() / 1000 - payload.frame.updated_at));
      controlNote.textContent = frameAge > 4
        ? `Кадр устарел на ${frameAge} сек. Проверь разрешение экрана и что телефон не заблокирован.`
        : `Кадр обновлён: ${formatLastSeen(payload.frame.updated_at)}. Тапай по экрану для управления.`;
    } catch (error) {
      controlNote.textContent = `Жду кадр. ${error.message}`;
    }
  };

  if (isAdbBridge(device)) requestFreshScreenFrame(device);
  loadFrame();
  const profile = qualityProfiles[getDeviceQuality(device)];
  const frameTimer = setInterval(loadFrame, isAdbBridge(device) ? profile.frameMs : 1200);
  const requestTimer = isAdbBridge(device) ? setInterval(() => requestFreshScreenFrame(device), profile.requestMs) : null;
  screenPollers.set(device.device_id, { frameTimer, requestTimer });
}

async function sendSimpleDeviceCommand(device, type, controlNote, successText, payload = {}, timeoutMs = 9000) {
  if (!device) {
    controlNote.textContent = "Сначала выбери устройство.";
    return;
  }
  if (remoteCommandBusy && controlNote === remoteControlNote) {
    controlNote.textContent = "Предыдущая команда еще выполняется.";
    return;
  }
  if (!canControlDevice(device)) {
    controlNote.textContent = formatHealthHint(device);
    if (controlNote === remoteControlNote) {
      addRemoteLog(type, "Устройство не готово к командам.", "warn");
    }
    return;
  }

  try {
    if (controlNote === remoteControlNote) {
      setRemoteBusy(true);
      addRemoteLog(type, "Команда отправлена, жду ответ агента.", "pending");
    }
    controlNote.textContent = "Команда отправлена, жду ответ агента...";
    const result = await sendCommandAndWait(device, type, payload, timeoutMs);
    const message = commandResultText(result, successText);
    controlNote.textContent = message;
    if (controlNote === remoteControlNote) {
      addRemoteLog(type, message, result?.command?.status === "rejected" ? "warn" : "done");
    }
  } catch (error) {
    controlNote.textContent = error.message;
    if (controlNote === remoteControlNote) {
      addRemoteLog(type, error.message, "error");
    }
  } finally {
    if (controlNote === remoteControlNote) {
      setRemoteBusy(false);
    }
  }
}

function updateQualityButtons(device, root, selector) {
  const quality = device ? getDeviceQuality(device) : "balanced";
  $$(selector, root).forEach((button) => button.classList.toggle("active", button.dataset.quality === quality));
}

function renderRemotePanel(restartScreen = false) {
  const device = selectedDevice();
  if (!device || remotePanelCollapsed) {
    remotePanel.classList.add("hidden");
    return;
  }

  remotePanel.classList.remove("hidden");
  remoteDeviceTitle.textContent = device.name;
  const remoteStatus = formatRemoteStatus(device);
  remoteConnectionStatus.textContent = remoteStatus.connection;
  remoteBatteryStatus.textContent = remoteStatus.battery;
  remoteSecurityStatus.textContent = remoteStatus.security;
  remoteCommandStatus.textContent = remoteStatus.commands;
  remoteDeviceMeta.textContent = `${device.platform || "unknown"} · ${device.agent || "agent"} · ${device.health?.label || (device.online ? "Online" : "Offline")}`;
  updateQualityButtons(device, remotePanel, ".remote-quality-button");
  setRemoteTab(activeRemoteTab);
  renderSetupAutomation(device);
  remoteControlNote.textContent = formatDeviceNote(device);

  if (restartScreen && device.online) {
    startScreenPolling(device, remoteScreenPreview, remoteScreenImage, remoteControlNote);
  }
}

async function startRemoteScreen() {
  const device = selectedDevice();
  if (!device) return;
  if (remoteCommandBusy) {
    remoteControlNote.textContent = "Предыдущая команда еще выполняется.";
    return;
  }
  if (/iphone|ios|ipad/i.test(`${device.platform} ${device.name}`)) {
    remoteControlNote.textContent = "iPhone требует Apple screen sharing или approved-сервис. Прямое управление сторонним APK невозможно.";
    return;
  }
  if (!canControlDevice(device)) {
    remoteControlNote.textContent = formatHealthHint(device, "Устройство offline. Запусти агент или ADB-мост.");
    addRemoteLog("request_screen", "Устройство не готово к трансляции экрана.", "warn");
    return;
  }
  try {
    setRemoteBusy(true);
    addRemoteLog("request_screen", "Запрашиваю доступ к экрану.", "pending");
    remoteControlNote.textContent = "Запрашиваю экран...";
    const profile = qualityProfiles[getDeviceQuality(device)];
    const result = await sendCommandAndWait(device, "request_screen", qualityPayload(device), profile.waitMs);
    const screenMessage = commandResultText(result, `Экран запущен: ${qualityProfiles[getDeviceQuality(device)].label}.`);
    remoteControlNote.textContent = screenMessage;
    addRemoteLog("request_screen", screenMessage, result?.command?.status === "rejected" ? "warn" : "done");
    startScreenPolling(device, remoteScreenPreview, remoteScreenImage, remoteControlNote);
  } catch (error) {
    remoteControlNote.textContent = error.message;
    addRemoteLog("request_screen", error.message, "error");
  } finally {
    setRemoteBusy(false);
  }
}

function normalizedPoint(event, image) {
  const rect = image.getBoundingClientRect();
  const naturalRatio = image.naturalWidth && image.naturalHeight ? image.naturalWidth / image.naturalHeight : rect.width / rect.height;
  const viewRatio = rect.width / rect.height;
  let contentWidth = rect.width;
  let contentHeight = rect.height;
  let offsetX = 0;
  let offsetY = 0;

  if (naturalRatio > viewRatio) {
    contentHeight = rect.width / naturalRatio;
    offsetY = (rect.height - contentHeight) / 2;
  } else if (naturalRatio < viewRatio) {
    contentWidth = rect.height * naturalRatio;
    offsetX = (rect.width - contentWidth) / 2;
  }

  return {
    x: Math.max(0, Math.min(1, (event.clientX - rect.left - offsetX) / contentWidth)),
    y: Math.max(0, Math.min(1, (event.clientY - rect.top - offsetY) / contentHeight)),
  };
}

function bindScreenGestures(image, getDevice, note) {
  let pointerStart = null;
  image.addEventListener("pointerdown", (event) => {
    pointerStart = normalizedPoint(event, image);
    image.setPointerCapture?.(event.pointerId);
  });
  image.addEventListener("pointercancel", () => {
    pointerStart = null;
  });
  image.addEventListener("pointerup", async (event) => {
    const device = getDevice();
    if (!device || !device.online) {
      note.textContent = "Жест недоступен, пока устройство offline.";
      pointerStart = null;
      return;
    }
    const start = pointerStart || normalizedPoint(event, image);
    const end = normalizedPoint(event, image);
    const distance = Math.hypot(end.x - start.x, end.y - start.y);
    pointerStart = null;
    try {
      if (distance > 0.06) {
        const result = await sendCommandAndWait(device, "swipe", { x: start.x, y: start.y, end_x: end.x, end_y: end.y });
        note.textContent = commandResultText(result, "Свайп выполнен.");
        return;
      }
      const result = await sendCommandAndWait(device, "tap", { x: end.x, y: end.y });
      note.textContent = commandResultText(result, `Тап: ${Math.round(end.x * 100)}%, ${Math.round(end.y * 100)}%.`);
    } catch (error) {
      note.textContent = error.message;
    }
  });
  image.addEventListener("dblclick", async (event) => {
    const device = getDevice();
    if (!device || !device.online) {
      note.textContent = "Long tap недоступен, пока устройство offline.";
      return;
    }
    try {
      const result = await sendCommandAndWait(device, "long_tap", normalizedPoint(event, image));
      note.textContent = commandResultText(result, "Long tap выполнен.");
    } catch (error) {
      note.textContent = error.message;
    }
  });
}

function render() {
  const activeScreenIds = new Set(screenPollers.keys());
  const restartRemoteScreen = Boolean(selectedDeviceId && activeScreenIds.has(selectedDeviceId));
  activeScreenIds.forEach((deviceId) => stopScreenPolling(deviceId));

  deviceList.innerHTML = "";
  totalDevices.textContent = devices.length;
  const onlineCount = devices.filter((device) => device.online).length;
  onlineDevices.textContent = onlineCount;
  userName.textContent = profileName;
  const scopeText = window.currentDeviceScope === "all" ? "все устройства проекта" : "твои устройства";
  setupText.textContent = devices.length
    ? `${scopeText}: ${devices.length}, online: ${onlineCount}.`
    : "Установи APK, получи QR и запусти Android Agent на телефоне.";

  if (!devices.length) {
    renderRemotePanel(false);
    deviceList.innerHTML = '<p class="empty-state">Пока нет подключённых устройств. Нажми «Скачать APK», затем «Получить QR» и открой QR-ссылку на телефоне. Экран и жесты доступны только в Full APK после явного разрешения на телефоне.</p>';
    return;
  }

  if (!selectedDevice()) {
    selectedDeviceId = devices[0].device_id;
    localStorage.setItem("hunter_selected_device_id", selectedDeviceId);
  }

  devices.forEach((device) => {
    const card = template.content.firstElementChild.cloneNode(true);
    const healthState = device.health?.state || (device.online ? "online" : "offline");
    card.classList.toggle("offline", !device.online);
    card.classList.toggle("selected", device.device_id === selectedDeviceId);
    card.dataset.health = healthState;
    $("h2", card).textContent = device.name;
    $(".status-pill", card).textContent = device.health?.label || (device.online ? "Online" : "Offline");

    const platform = device.platform ? ` · ${device.platform}` : "";
    const agent = device.agent ? ` · ${device.agent}` : "";
    $(".meta", card).textContent = `${typeNames[device.type] || "Устройство"}${platform}${agent} · сигнал ${formatLastSeen(device.last_seen)}`;

    $(".telemetry", card).innerHTML = formatTelemetry(device).map((item) => `<span>${item}</span>`).join("");

    const controlNote = $(".control-note", card);
    controlNote.textContent = formatDeviceNote(device);

    $(".open-remote-button", card).addEventListener("click", () => {
      selectDevice(device);
      remotePanel.scrollIntoView({ behavior: "smooth", block: "start" });
    });

    $(".rename-device-button", card).addEventListener("click", async () => {
      const name = prompt("Новое имя устройства", device.name);
      if (!name?.trim()) return;
      try {
        await manageDevice(device, "rename", { name: name.trim() });
        await refreshDevices();
      } catch (error) {
        controlNote.textContent = error.message;
      }
    });

    $(".revoke-device-button", card).addEventListener("click", async () => {
      if (!confirm("Сбросить привязку устройства? Агенту понадобится новый QR.")) return;
      try {
        await manageDevice(device, "revoke");
        await refreshDevices();
      } catch (error) {
        controlNote.textContent = error.message;
      }
    });

    $(".delete-device-button", card).addEventListener("click", async () => {
      if (!confirm("Удалить устройство из списка?")) return;
      try {
        await manageDevice(device, "delete");
        stopScreenPolling(device.device_id);
        await refreshDevices();
      } catch (error) {
        controlNote.textContent = error.message;
      }
    });

    const idButton = $(".id-button", card);
    idButton.addEventListener("click", () => {
      navigator.clipboard?.writeText(device.device_id);
      idButton.textContent = "Скопировано";
      setTimeout(() => {
        idButton.textContent = "ID";
      }, 1200);
    });

    deviceList.append(card);
  });

  renderRemotePanel(restartRemoteScreen);
}

function renderCurrentDevice() {
  const currentDevice = detectCurrentDevice();
  currentDeviceText.textContent = `${currentDevice.name} · ${currentDevice.platform} · owner ${ownerId}`;
}

async function refreshDevices() {
  if (refreshInFlight) return;
  refreshInFlight = true;
  try {
    await loadDevicesFromApi();
    render();
    loadDeviceAlerts();
  } catch (error) {
    if (!devices.length) {
      deviceList.innerHTML = `<p class="empty-state">${error.message}</p>`;
    }
    setupText.textContent = `API connection issue: ${error.message}`;
  } finally {
    refreshInFlight = false;
  }
}

deviceForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const name = deviceName.value.trim();
  if (!name) return;
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

connectCurrentDevice.addEventListener("click", () => {
  currentDeviceText.textContent = "Открываю страницу установки Android Agent...";
  openExternal(agentInstallUrl);
});

installAgentButton.addEventListener("click", () => {
  setupText.textContent = "Открываю страницу установки APK...";
  openExternal(agentInstallUrl);
});

openInstalledAgentButton.addEventListener("click", () => {
  setupText.textContent = "Готовлю автономное подключение Agent...";
  openAgentWithPairing();
});

requestPairButton.addEventListener("click", async () => {
  setupText.textContent = "Создаю QR и код подключения...";
  try {
    const payload = await createPairingQr();
    currentPairLinks = payload.links;
    currentPairExpiresAt = Date.now() + (payload.expires_in || 600) * 1000;
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
  if (currentPairLinks?.web_link) openExternal(currentPairLinks.web_link);
});

openAgentDeepLinkButton.addEventListener("click", () => {
  window.location.href = currentPairLinks?.app_link || agentOpenLink;
});

async function openAgentWithPairing() {
  try {
    const pairIsFresh = currentPairLinks && Date.now() < currentPairExpiresAt - 5000;
    const payload = pairIsFresh ? null : await createPairingQr();
    if (payload) {
      currentPairLinks = payload.links;
      currentPairExpiresAt = Date.now() + (payload.expires_in || 600) * 1000;
      pairQrImage.src = payload.qr_image_data;
      pairCode.textContent = payload.code;
      pairResult.classList.remove("hidden");
    }
    setupText.textContent = "Открываю Agent с готовым кодом подключения...";
    window.location.href = currentPairLinks?.app_link || agentOpenLink;
  } catch (error) {
    setupText.textContent = `${error.message}. Открываю Agent без кода.`;
    window.location.href = agentOpenLink;
  }
}

closeRemotePanel.addEventListener("click", () => {
  const device = selectedDevice();
  if (device) stopScreenPolling(device.device_id);
  remotePanelCollapsed = true;
  remotePanel.classList.add("hidden");
});

remoteTabs.forEach((button) => {
  button.addEventListener("click", () => setRemoteTab(button.dataset.remoteTab));
});

remoteLogClearButton?.addEventListener("click", () => {
  remoteLogItems = [];
  renderRemoteLog();
});

$(".remote-screen-button", remotePanel).addEventListener("click", startRemoteScreen);

$(".remote-stop-screen-button", remotePanel).addEventListener("click", async () => {
  const device = selectedDevice();
  if (!device) return;
  await sendSimpleDeviceCommand(device, "stop_screen", remoteControlNote, "Команда остановки экрана отправлена.");
  stopScreenPolling(device.device_id);
});

$$(".remote-quality-button", remotePanel).forEach((button) => {
  button.addEventListener("click", () => {
    const device = selectedDevice();
    if (!device) return;
    const quality = setDeviceQuality(device, button.dataset.quality);
    updateQualityButtons(device, remotePanel, ".remote-quality-button");
    remoteControlNote.textContent = `Режим экрана: ${qualityProfiles[quality].label}.`;
    if (screenPollers.has(device.device_id)) {
      startScreenPolling(device, remoteScreenPreview, remoteScreenImage, remoteControlNote);
    }
  });
});

$$(".remote-command-button", remotePanel).forEach((button) => {
  button.addEventListener("click", () => {
    const command = button.dataset.command;
    const textPayload = command === "input_text" ? { text: remotePanelTextInput.value.trim() } : {};
    const successText = remoteCommandMessages[command] || "Команда отправлена.";
    const timeoutMs = Number(button.dataset.timeout || 9000);
    sendSimpleDeviceCommand(selectedDevice(), command, remoteControlNote, successText, textPayload, timeoutMs);
  });
});

$$(".remote-manage-button", remotePanel).forEach((button) => {
  button.addEventListener("click", async () => {
    const device = selectedDevice();
    if (!device) return;
    const action = button.dataset.action;
    if (action !== "clear_commands") return;
    try {
      setRemoteBusy(true);
      remoteControlNote.textContent = "Очищаю зависшие команды...";
      const result = await manageDevice(device, "clear_commands");
      const cleared = Number(result.cleared || 0);
      const message = cleared ? `Очередь очищена: ${cleared} команд.` : "Очередь уже чистая.";
      remoteControlNote.textContent = message;
      addRemoteLog("clear_commands", message, cleared ? "done" : "info");
      await refreshDevices();
    } catch (error) {
      remoteControlNote.textContent = error.message;
      addRemoteLog("clear_commands", error.message, "error");
    } finally {
      setRemoteBusy(false);
    }
  });
});

nextSetupStepButton?.addEventListener("click", () => {
  const device = selectedDevice();
  const step = nextSetupStep(device);
  if (!step) {
    remoteControlNote.textContent = "Автонастройка уже выглядит готовой.";
    return;
  }
  const successText = remoteCommandMessages[step.command] || `Открываю шаг: ${step.title}.`;
  sendSimpleDeviceCommand(device, step.command, remoteControlNote, successText);
});

remotePanelSendText.addEventListener("click", async () => {
  const text = remotePanelTextInput.value.trim();
  if (!text) {
    remoteControlNote.textContent = "Введи текст для отправки.";
    return;
  }
  await sendSimpleDeviceCommand(selectedDevice(), "input_text", remoteControlNote, "Текст отправлен.", { text });
  remotePanelTextInput.value = "";
});

bindScreenGestures(remoteScreenImage, selectedDevice, remoteControlNote);

refreshButton.addEventListener("click", async () => {
  setupText.textContent = "Обновляю список устройств...";
  await Promise.all([refreshDevices(), loadSetupStatus()]);
});

deployRefreshButton?.addEventListener("click", loadSetupStatus);
deviceAlertRefreshButton?.addEventListener("click", loadDeviceAlerts);
deviceAlertSaveButton?.addEventListener("click", saveDeviceAlertSettings);

themeButton.addEventListener("click", () => {
  const dark = !document.documentElement.classList.contains("dark");
  document.documentElement.classList.toggle("dark", dark);
  localStorage.setItem("apk_converter_theme", dark ? "dark" : "light");
});

function startRefreshLoop() {
  if (refreshTimer) clearInterval(refreshTimer);
  refreshTimer = setInterval(() => {
    if (!document.hidden) refreshDevices();
  }, 15000);
}

document.addEventListener("visibilitychange", () => {
  if (!document.hidden) refreshDevices();
});

setTelegramTheme();
renderRemoteLog();
renderCurrentDevice();
renderSetupStatus();
loadSetupStatus();
refreshDevices();
startRefreshLoop();
