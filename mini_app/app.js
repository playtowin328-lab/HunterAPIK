const tg = window.Telegram?.WebApp;

if (tg) {
  tg.ready();
  tg.expand();
  tg.disableVerticalSwipes?.();
}

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];

const themeButton = $("#themeButton");
const fullscreenButton = $("#fullscreenButton");
const installPwaButton = $("#installPwaButton");
const commandPaletteButton = $("#commandPaletteButton");
const commandPalette = $("#commandPalette");
const commandPaletteBackdrop = $("#commandPaletteBackdrop");
const commandPaletteClose = $("#commandPaletteClose");
const commandPaletteInput = $("#commandPaletteInput");
const commandPaletteItems = $$("#commandPaletteList > button");
const commandPaletteEmpty = $("#commandPaletteEmpty");
const deviceForm = $("#deviceForm");
const deviceName = $("#deviceName");
const deviceType = $("#deviceType");
const deviceList = $("#deviceList");
const deviceSearchInput = $("#deviceSearchInput");
const deviceFilterButtons = $$("[data-device-filter]");
const filterAllCount = $("#filterAllCount");
const filterOnlineCount = $("#filterOnlineCount");
const filterAttentionCount = $("#filterAttentionCount");
const currentDeviceText = $("#currentDeviceText");
const connectCurrentDevice = $("#connectCurrentDevice");
const setupText = $("#setupText");
const fleetLiveStatus = $("#fleetLiveStatus");
const fleetAttentionStatus = $("#fleetAttentionStatus");
const localClock = $("#localClock");
const installAgentButton = $("#installAgentButton");
const openInstalledAgentButton = $("#openInstalledAgentButton");
const openDesktopAppButton = $("#openDesktopAppButton");
const requestPairButton = $("#requestPairButton");
const installationProgress = $("#installationProgress");
const installationProgressFill = $("#installationProgressFill");
const installationProgressLabel = $("#installationProgressLabel");
const installationProgressTitle = $("#installationProgressTitle");
const installationProgressPercent = $("#installationProgressPercent");
const installationProgressDetail = $("#installationProgressDetail");
const installationStepElements = [$("#installStepApk"), $("#installStepOpen"), $("#installStepPair"), $("#installStepOnline")];
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
const copyRemoteStatusButton = $("#copyRemoteStatusButton");
const remoteScreenPreview = $("#remoteScreenPreview");
const remoteScreenImage = $("#remoteScreenImage");
const remoteControlNote = $("#remoteControlNote");
const remotePanelTextInput = $("#remotePanelTextInput");
const blackoutMessage = $("#blackoutMessage");
const remotePanelSendText = $("#remotePanelSendText");
const remoteConnectionStatus = $("#remoteConnectionStatus");
const remoteBatteryStatus = $("#remoteBatteryStatus");
const remoteSecurityStatus = $("#remoteSecurityStatus");
const remoteCommandStatus = $("#remoteCommandStatus");
const remoteNowTitle = $("#remoteNowTitle");
const remoteNowDetail = $("#remoteNowDetail");
const deviceHistoryStrip = $("#deviceHistoryStrip");
const quickActionButtons = $$(".quick-action-button");
const emergencyStopButton = $(".emergency-stop-button");
const remoteHealthCard = $("#remoteHealthCard");
const remoteHealthStatus = $("#remoteHealthStatus");
const remoteHealthTitle = $("#remoteHealthTitle");
const remoteHealthDetail = $("#remoteHealthDetail");
const remoteHealthActionButton = $("#remoteHealthActionButton");
const remoteTabs = $$(".remote-tabs button");
const remoteTabPanels = $$(".remote-tab-panel");
const remoteSetupAutomation = $("#remoteSetupAutomation");
const remoteSetupProgress = $("#remoteSetupProgress");
const remoteSetupChecklist = $("#remoteSetupChecklist");
const nextSetupStepButton = $("#nextSetupStepButton");
const remoteActionLog = $("#remoteActionLog");
const remoteLogClearButton = $("#remoteLogClearButton");
const remoteLogCopyButton = $("#remoteLogCopyButton");
const deviceAlertPanel = $("#deviceAlertPanel");
const deviceAlertRefreshButton = $("#deviceAlertRefreshButton");
const deviceAlertSaveButton = $("#deviceAlertSaveButton");
const deviceAlertsEnabled = $("#deviceAlertsEnabled");
const deviceAlertsQuietEnabled = $("#deviceAlertsQuietEnabled");
const deviceAlertsTravelMode = $("#deviceAlertsTravelMode");
const deviceAlertsQuietStart = $("#deviceAlertsQuietStart");
const deviceAlertsQuietEnd = $("#deviceAlertsQuietEnd");
const deviceAlertKinds = $("#deviceAlertKinds");
const deviceAlertLog = $("#deviceAlertLog");
const personalAlertsPanel = $("#personalAlertsPanel");
const personalAlertsEnabled = $("#personalAlertsEnabled");
const personalAlertKinds = $("#personalAlertKinds");
const personalAlertsSave = $("#personalAlertsSave");
const companionState = $("#companionState");
const companionCapabilities = $("#companionCapabilities");
const companionScreenButton = $("#companionScreenButton");
const companionCameraButton = $("#companionCameraButton");
const companionLocationButton = $("#companionLocationButton");
const companionNotificationButton = $("#companionNotificationButton");
const companionStopButton = $("#companionStopButton");
const companionPreview = $("#companionPreview");
const companionVideo = $("#companionVideo");
const companionPreviewTitle = $("#companionPreviewTitle");
const companionDetail = $("#companionDetail");
const timelinePanel = $("#timelinePanel");
const timelineList = $("#timelineList");
const timelineIntegrity = $("#timelineIntegrity");
const timelineRefreshButton = $("#timelineRefreshButton");

const telegramUser = tg?.initDataUnsafe?.user;
const profileName = telegramUser?.first_name || telegramUser?.username || "Я";
const urlParams = new URLSearchParams(window.location.search);
const ownerId = String(telegramUser?.id || urlParams.get("owner_id") || localStorage.getItem("apk_owner_id") || crypto.randomUUID());
localStorage.setItem("apk_owner_id", ownerId);
const webSessionStorageKey = `hunter_web_session_${ownerId}`;
let webSessionToken = localStorage.getItem(webSessionStorageKey) || "";
const remoteLogStorageKey = `hunter_remote_log_${ownerId}`;
const installStartedKey = "hunter_agent_install_started";
const agentOpenAttemptKey = "hunter_agent_open_attempted";

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
  request_notification_listener_permission: "Настройки доступа к уведомлениям открыты на телефоне.",
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

const remoteCommandLabels = {
  ...remoteCommandMessages,
  tap: "Тап по экрану",
  long_tap: "Long tap по экрану",
  swipe: "Свайп по экрану",
  input_text: "Ввод текста",
  request_screen: "Запрос live-экрана",
  stop_screen: "Остановка live-экрана",
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
let remoteLogItems = loadRemoteLogItems();
let activeRemoteTab = localStorage.getItem("hunter_remote_tab") || "setup";
let deviceAlertSettings = null;
let deviceAlertEvents = [];
let timelineEvents = [];
let deviceAlertKindList = [];
let fullscreenFallbackActive = false;
let pwaInstallPrompt = null;
let activeDeviceFilter = localStorage.getItem("hunter_device_filter") || "all";
let deviceSearchQuery = "";
if (!["all", "online", "attention"].includes(activeDeviceFilter)) activeDeviceFilter = "all";
const screenPollers = new Map();
const pendingScreenRequests = new Set();
const companionStreams = new Set();
window.currentDeviceScope = "own";

function setCommandPalette(open) {
  commandPalette?.classList.toggle("hidden", !open);
  document.documentElement.classList.toggle("palette-open", open);
  if (open) {
    commandPaletteInput.value = "";
    commandPaletteItems.forEach((item) => item.classList.remove("hidden"));
    commandPaletteEmpty.classList.add("hidden");
    setTimeout(() => commandPaletteInput?.focus(), 0);
  }
}

function filterCommandPalette() {
  const query = commandPaletteInput.value.trim().toLocaleLowerCase("ru");
  let visible = 0;
  commandPaletteItems.forEach((item) => {
    const matches = !query || (item.dataset.paletteLabel || "").includes(query);
    item.classList.toggle("hidden", !matches);
    if (matches) visible += 1;
  });
  commandPaletteEmpty.classList.toggle("hidden", visible !== 0);
}

async function installPwa() {
  if (!pwaInstallPrompt) return;
  pwaInstallPrompt.prompt();
  await pwaInstallPrompt.userChoice;
  pwaInstallPrompt = null;
  installPwaButton.classList.add("hidden");
}

function companionFeatures() {
  return [
    {
      key: "pairing",
      title: "QR-подключение",
      detail: device?.pairing_required
        ? "APK найден. Подтверди владельца по QR — до этого команды безопасно заблокированы."
        : "Владелец подтверждён, защищённое подключение готово.",
      status: device?.pairing_required ? "todo" : "ready",
      command: null,
    },
    { label: "HTTPS", ready: window.isSecureContext },
    { label: "Экран", ready: Boolean(navigator.mediaDevices?.getDisplayMedia) },
    { label: "Камера", ready: Boolean(navigator.mediaDevices?.getUserMedia) },
    { label: "Геопозиция", ready: Boolean(navigator.geolocation) },
    { label: "Уведомления", ready: "Notification" in window },
  ];
}

function renderCompanionCapabilities() {
  if (!companionCapabilities) return;
  companionCapabilities.innerHTML = companionFeatures()
    .map((feature) => `<span data-ready="${feature.ready}"><i></i>${feature.label}<strong>${feature.ready ? "готово" : "нет"}</strong></span>`)
    .join("");
  companionScreenButton.disabled = !window.isSecureContext || !navigator.mediaDevices?.getDisplayMedia;
  companionCameraButton.disabled = !window.isSecureContext || !navigator.mediaDevices?.getUserMedia;
  companionLocationButton.disabled = !window.isSecureContext || !navigator.geolocation;
  companionNotificationButton.disabled = !window.isSecureContext || !("Notification" in window);
}

function setCompanionState(text, state = "active") {
  if (!companionState) return;
  companionState.dataset.state = state;
  companionState.innerHTML = `<i></i> ${text}`;
  companionStopButton.disabled = companionStreams.size === 0;
}

function showCompanionStream(stream, title, detail) {
  companionStreams.add(stream);
  companionVideo.srcObject = stream;
  companionPreview.classList.remove("hidden");
  companionPreviewTitle.textContent = title;
  companionDetail.textContent = detail;
  stream.getTracks().forEach((track) => track.addEventListener("ended", stopCompanionAccess, { once: true }));
  setCompanionState("Доступ активен");
}

function stopCompanionAccess() {
  companionStreams.forEach((stream) => stream.getTracks().forEach((track) => track.stop()));
  companionStreams.clear();
  if (companionVideo) companionVideo.srcObject = null;
  companionPreview?.classList.add("hidden");
  setCompanionState("Не активен", "idle");
}

async function startCompanionScreen() {
  try {
    const stream = await navigator.mediaDevices.getDisplayMedia({ video: true, audio: false });
    showCompanionStream(stream, "Экран доступен", "Передача завершится при закрытии вкладки или через системную кнопку браузера.");
  } catch (error) {
    setCompanionState(error.name === "NotAllowedError" ? "Доступ не разрешён" : "Ошибка экрана", "warning");
  }
}

async function startCompanionCamera() {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" }, audio: false });
    showCompanionStream(stream, "Камера активна", "Видео остаётся локальным, пока не создана подтверждённая удалённая сессия.");
  } catch (error) {
    setCompanionState(error.name === "NotAllowedError" ? "Камера не разрешена" : "Ошибка камеры", "warning");
  }
}

function requestCompanionLocation() {
  navigator.geolocation.getCurrentPosition(
    (position) => {
      const accuracy = Math.round(position.coords.accuracy || 0);
      companionPreview.classList.remove("hidden");
      companionVideo.srcObject = null;
      companionPreviewTitle.textContent = "Геопозиция получена";
      companionDetail.textContent = `Точность около ${accuracy} м. Координаты не отправлены и остаются на этой странице.`;
      setCompanionState("Геопозиция разрешена");
    },
    (error) => setCompanionState(error.code === 1 ? "Геопозиция не разрешена" : "Ошибка геопозиции", "warning"),
    { enableHighAccuracy: true, timeout: 12000, maximumAge: 0 },
  );
}

async function requestCompanionNotifications() {
  const permission = await Notification.requestPermission();
  setCompanionState(permission === "granted" ? "Уведомления разрешены" : "Уведомления не разрешены", permission === "granted" ? "active" : "warning");
}

function updateLocalClock() {
  if (!localClock) return;
  localClock.textContent = new Intl.DateTimeFormat("ru-RU", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).format(new Date());
}

function renderFleetPulse(onlineCount) {
  const attentionCount = devices.filter((device) => {
    const state = device.health?.state || (device.online ? "online" : "offline");
    return ["warning", "degraded", "revoked", "offline"].includes(state);
  }).length;
  const allOnline = devices.length > 0 && onlineCount === devices.length;

  document.documentElement.dataset.fleet = !devices.length ? "empty" : (allOnline ? "ready" : "attention");
  if (fleetLiveStatus) {
    fleetLiveStatus.innerHTML = `<i aria-hidden="true"></i> ${allOnline ? "Все устройства на связи" : `${onlineCount} из ${devices.length} на связи`}`;
  }
  if (fleetAttentionStatus) {
    fleetAttentionStatus.textContent = attentionCount
      ? `Внимание: ${attentionCount}`
      : (devices.length ? "Система стабильна" : "Добавьте первое устройство");
  }
}

function needsAttention(device) {
  const state = device.health?.state || (device.online ? "online" : "offline");
  return ["warning", "degraded", "revoked", "offline"].includes(state);
}

function visibleDevices() {
  const query = deviceSearchQuery.trim().toLocaleLowerCase("ru");
  return devices.filter((device) => {
    if (activeDeviceFilter === "online" && !device.online) return false;
    if (activeDeviceFilter === "attention" && !needsAttention(device)) return false;
    if (!query) return true;
    return [device.name, device.device_id, device.platform, device.agent, device.type]
      .filter(Boolean)
      .some((value) => String(value).toLocaleLowerCase("ru").includes(query));
  });
}

function renderDeviceToolbar() {
  if (filterAllCount) filterAllCount.textContent = devices.length;
  if (filterOnlineCount) filterOnlineCount.textContent = devices.filter((device) => device.online).length;
  if (filterAttentionCount) filterAttentionCount.textContent = devices.filter(needsAttention).length;
  deviceFilterButtons.forEach((button) => {
    const active = button.dataset.deviceFilter === activeDeviceFilter;
    button.classList.toggle("active", active);
    button.setAttribute("aria-pressed", String(active));
  });
}

function renderInstallationProgress() {
  if (!installationProgress) return;
  const installStarted = localStorage.getItem(installStartedKey) === "1";
  const agentOpened = localStorage.getItem(agentOpenAttemptKey) === "1";
  const paired = devices.length > 0;
  const online = devices.some((device) => device.online);
  let step = 0;
  if (installStarted) step = 1;
  if (agentOpened) step = 2;
  if (paired) step = 3;
  if (online) step = 4;
  const states = [
    ["Шаг 1 из 4", "Установите Hunter Agent", "Скачайте APK на Android-устройство и подтвердите установку."],
    ["Шаг 2 из 4", "Откройте установленный Agent", "После установки вернитесь сюда и нажмите «Открыть Agent»."],
    ["Шаг 3 из 4", "Подключите приложение", "Agent открывается с одноразовым кодом. Подтвердите подключение на телефоне."],
    ["Шаг 4 из 4", "Устройство подключено", "Agent зарегистрирован. Осталось дождаться первого сигнала Online."],
    ["Готово", "Устройство Online", "Установка и подключение завершены. Устройство доступно в пульте управления."],
  ];
  const [label, title, detail] = states[step];
  const percent = [0, 25, 50, 75, 100][step];
  installationProgress.dataset.step = String(step);
  installationProgressFill.style.width = `${percent}%`;
  installationProgressLabel.textContent = label;
  installationProgressTitle.textContent = title;
  installationProgressPercent.textContent = `${percent}%`;
  installationProgressDetail.textContent = detail;
  installationStepElements.forEach((element, index) => {
    element?.classList.toggle("complete", index < step);
    element?.classList.toggle("active", index === Math.min(step, 3));
  });
  installAgentButton.textContent = step === 0 ? "1. Установить Agent" : "APK / страница установки";
  openInstalledAgentButton.classList.toggle("recommended", step >= 1 && step < 3);
}

function timelineEventLabel(action) {
  return ({ device_added: "Добавлено устройство", device_paired: "Устройство подключено", device_manage: "Изменено устройство", device_alert: "Событие устройства", device_command: "Команда отправлена", device_command_result: "Команда завершена", pairing_code_created: "Создан код подключения", grant_access: "Выдан доступ", revoke_access: "Доступ отозван", build_apk_lite: "Сборка Lite APK", build_apk_full: "Сборка Full APK" })[action] || "Системное событие";
}

function renderTimeline(payload = {}) {
  if (!timelineList) return;
  const events = payload.events || timelineEvents;
  timelineList.innerHTML = events.length ? events.map((event) => {
    const time = new Date(Number(event.created_at || 0) * 1000).toLocaleString("ru-RU", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
    return `<article class="timeline-event" data-severity="${escapeHtml(event.severity || "info")}"><i></i><div><strong>${escapeHtml(timelineEventLabel(event.action))}</strong><p>${escapeHtml(event.detail || "Событие зарегистрировано")}</p><small>${escapeHtml(time)}</small></div></article>`;
  }).join("") : '<p class="hint">Событий для вашей роли пока нет.</p>';
  if (timelineIntegrity && payload.integrity) {
    timelineIntegrity.textContent = payload.integrity.ok ? `✓ Журнал цел · ${payload.integrity.checked}` : "⚠ Целостность нарушена";
    timelineIntegrity.dataset.ok = String(Boolean(payload.integrity.ok));
  }
}

async function loadTimeline() {
  if (!tg?.initData || !timelinePanel) return;
  try {
    const payload = await apiJson(`/api/timeline?${apiAuthParams({ limit: 20 })}`);
    timelineEvents = payload.events || [];
    renderTimeline(payload);
  } catch (error) {
    timelineList.innerHTML = `<p class="hint">${escapeHtml(error.message)}</p>`;
  }
}

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
  if (typeof telemetry.notification_listener_ready === "boolean") items.push(`чтение уведомлений: ${telemetry.notification_listener_ready ? "on" : "off"}`);
  if (telemetry.notification_last_app) {
    const title = telemetry.notification_last_title ? ` · ${telemetry.notification_last_title}` : "";
    items.push(`последнее уведомление: ${telemetry.notification_last_app}${title}`);
  }
  if (typeof telemetry.battery_ready === "boolean") items.push(`фон: ${telemetry.battery_ready ? "on" : "off"}`);
  if (typeof telemetry.accessibility === "boolean") items.push(`жесты: ${telemetry.accessibility ? "on" : "off"}`);
  if (typeof telemetry.screen_streaming === "boolean") items.push(`экран: ${telemetry.screen_streaming ? "on" : "off"}`);
  if (typeof telemetry.loop_ms === "number" && telemetry.loop_ms > 0) items.push(`agent: ${telemetry.loop_ms} ms`);
  if (typeof telemetry.command_ms === "number" && telemetry.command_ms > 0) items.push(`cmd: ${telemetry.command_ms} ms`);
  if (typeof telemetry.gesture_ms === "number" && telemetry.gesture_ms > 0) items.push(`gesture: ${telemetry.gesture_ms} ms`);
  if (telemetry.gesture_result) items.push(`gesture: ${telemetry.gesture_result}`);
  if (telemetry.active_app_label || telemetry.active_app_package) items.push(`активно: ${telemetry.active_app_label || telemetry.active_app_package}`);
  if (typeof telemetry.screen_ms === "number" && telemetry.screen_ms > 0) items.push(`screen: ${telemetry.screen_ms} ms`);
  if (typeof telemetry.screen_frames === "number" && telemetry.screen_frames > 0) items.push(`frames: ${telemetry.screen_frames}`);
  if (typeof telemetry.screen_dropped === "number" && telemetry.screen_dropped > 0) items.push(`drop: ${telemetry.screen_dropped}`);
  if (telemetry.screen_black_frame) items.push(`screen: protected/black`);
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
  if (telemetry.screen_black_frame) parts.push("кадр черный: приложение может блокировать захват");
  if (typeof telemetry.gesture_ms === "number" && telemetry.gesture_ms > 0) parts.push(`жест ${telemetry.gesture_ms} ms`);
  if (telemetry.gesture_result) parts.push(telemetry.gesture_result);
  if (telemetry.active_app_label || telemetry.active_app_package) parts.push(`активно ${telemetry.active_app_label || telemetry.active_app_package}`);
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
    telemetry.notification_listener_ready ? "уведомления" : "",
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

function primaryDeviceIssue(device) {
  if (!device) {
    return {
      status: "info",
      label: "Статус",
      title: "Устройство не выбрано",
      detail: "Выбери устройство из списка, чтобы увидеть подсказку.",
      action: "",
      actionLabel: "Действие",
    };
  }

  const telemetry = device.telemetry || {};
  const diagnostics = device.diagnostics || {};
  const health = device.health || {};
  const issues = new Set(health.issues || []);
  const pending = Number(diagnostics.pending_commands || 0);
  const delivered = Number(diagnostics.delivered_commands || 0);

  if (issues.has("pairing_revoked")) {
    return {
      status: "danger",
      label: "Привязка",
      title: "Нужен новый QR",
      detail: "Привязка сброшена. Получи новый код и открой его на телефоне.",
      action: "pair",
      actionLabel: "Получить QR",
    };
  }
  if (!device.online) {
    return {
      status: "danger",
      label: "Связь",
      title: "Агент offline",
      detail: formatHealthHint(device, "Открой Android Agent на телефоне и проверь интернет."),
      action: "stabilize",
      actionLabel: "Стабилизировать",
    };
  }
  if (pending >= 3 || delivered >= 2 || issues.has("command_queue_stuck") || issues.has("command_delivery_stuck")) {
    return {
      status: "warn",
      label: "Очередь",
      title: "Команды зависают",
      detail: `Активных команд: ${pending + delivered}. Очисти очередь и проверь ping агента.`,
      action: "stabilize",
      actionLabel: "Стабилизировать",
    };
  }
  if (telemetry.last_error) {
    return {
      status: "warn",
      label: "Агент",
      title: "Ошибка агента",
      detail: String(telemetry.last_error).slice(0, 160),
      action: "stabilize",
      actionLabel: "Ремонт связи",
    };
  }
  if (telemetry.screen_error) {
    return {
      status: "warn",
      label: "Экран",
      title: "Ошибка трансляции",
      detail: String(telemetry.screen_error).slice(0, 160),
      action: "screen",
      actionLabel: "Запустить экран",
    };
  }
  if (telemetry.screen_black_frame) {
    return {
      status: "warn",
      label: "Экран",
      title: "Приложение блокирует захват",
      detail: "Android не отдает картинку для защищенного окна. Управлять можно жестами, но картинка будет черной, пока открыто это приложение.",
      action: "home",
      actionLabel: "Домой",
    };
  }
  if (telemetry.full_control === false) {
    return {
      status: "info",
      label: "APK",
      title: "Lite режим",
      detail: "Жесты и live-экран доступны только в Full APK. Для статуса и базовых команд Lite подходит.",
      action: "setup",
      actionLabel: "Проверить setup",
    };
  }
  if (telemetry.notification_listener_ready === false) {
    return {
      status: "info",
      label: "Уведомления",
      title: "Чтение уведомлений не включено",
      detail: "Для журнала уведомлений нужно вручную включить Hunter Agent в Android Notification Access.",
      action: "notification_listener",
      actionLabel: "Открыть доступ",
    };
  }
  if (telemetry.full_control === true && telemetry.accessibility !== true) {
    return {
      status: "warn",
      label: "Жесты",
      title: "Accessibility не включен",
      detail: "Тапы, свайпы и ввод заработают после включения Hunter Agent в Accessibility.",
      action: "setup",
      actionLabel: "Открыть шаг",
    };
  }
  if (telemetry.full_control === true && telemetry.screen_streaming !== true) {
    return {
      status: "info",
      label: "Экран",
      title: "Live-экран не запущен",
      detail: "Можно запросить трансляцию и подтвердить системное окно на телефоне.",
      action: "screen",
      actionLabel: "Запустить live",
    };
  }

  return {
    status: "ready",
    label: "Готово",
    title: "Управление выглядит стабильным",
    detail: formatHealthHint(device, "Связь, очередь и базовые разрешения выглядят нормально."),
    action: "report",
    actionLabel: "Скопировать статус",
  };
}

function renderRemoteHealth(device) {
  if (!remoteHealthCard || !remoteHealthStatus || !remoteHealthTitle || !remoteHealthDetail || !remoteHealthActionButton) return;
  const issue = primaryDeviceIssue(device);
  remoteHealthCard.dataset.status = issue.status;
  remoteHealthStatus.textContent = issue.label;
  remoteHealthTitle.textContent = issue.title;
  remoteHealthDetail.textContent = issue.detail;
  remoteHealthActionButton.textContent = issue.actionLabel;
  remoteHealthActionButton.dataset.action = issue.action;
  remoteHealthActionButton.disabled = !issue.action || remoteCommandBusy;
}

async function copyTextToClipboard(text) {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text);
    return true;
  }

  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.setAttribute("readonly", "");
  textarea.style.position = "fixed";
  textarea.style.opacity = "0";
  document.body.append(textarea);
  textarea.select();
  const copied = document.execCommand("copy");
  textarea.remove();
  return copied;
}

async function copySelectedDeviceReport() {
  const device = selectedDevice();
  if (!device) {
    remoteControlNote.textContent = "Сначала выбери устройство.";
    return;
  }

  const status = formatRemoteStatus(device);
  const telemetry = formatTelemetry(device).join(", ") || "нет телеметрии";
  const diagnostics = formatDiagnostics(device) || "нет диагностики";
  const recentLog = remoteLogItems.length
    ? remoteLogItems.map((item) => `${item.time} ${item.title}: ${item.detail}`).join("\n")
    : "нет действий в этой сессии";
  const report = [
    `Hunter Agent report`,
    `Устройство: ${device.name}`,
    `ID: ${device.device_id}`,
    `Платформа: ${device.platform || "unknown"}`,
    `Agent: ${device.agent || "unknown"}`,
    `Связь: ${status.connection}`,
    `Батарея: ${status.battery}`,
    `Защита: ${status.security}`,
    `Очередь: ${status.commands}`,
    `Последний сигнал: ${formatLastSeen(device.last_seen)}`,
    `Подсказка: ${formatHealthHint(device)}`,
    `Телеметрия: ${telemetry}`,
    `Диагностика: ${diagnostics}`,
    "",
    "Последние действия:",
    recentLog,
  ].join("\n");

  try {
    await copyTextToClipboard(report);
    remoteControlNote.textContent = "Отчет по устройству скопирован.";
    addRemoteLog("report", "Статус устройства скопирован в буфер.", "done");
  } catch (error) {
    remoteControlNote.textContent = `Не удалось скопировать отчет: ${error.message}`;
  }
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
      key: "notification_listener",
      title: "Чтение уведомлений",
      detail: telemetry.notification_listener_ready
        ? "Notification Listener включен. Агент видит новые уведомления после явного разрешения."
        : "Открой системный доступ к уведомлениям и включи Hunter Agent вручную.",
      status: !isAndroid ? "skipped" : (telemetry.notification_listener_ready === true ? "ready" : "todo"),
      command: "request_notification_listener_permission",
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
    nextSetupStepButton.disabled = !nextStep?.command || remoteCommandBusy || !device?.online || device?.pairing_required;
    nextSetupStepButton.dataset.command = nextStep?.command || "";
    nextSetupStepButton.textContent = nextStep ? `Открыть: ${nextStep.title}` : "Все готово";
  }
}

function canControlDevice(device) {
  return Boolean(device?.online && !device?.pairing_required && device?.health?.state !== "revoked");
}

function setTelegramTheme() {
  const savedTheme = localStorage.getItem("apk_converter_theme");
  const dark = savedTheme ? savedTheme === "dark" : tg?.colorScheme === "dark";
  document.documentElement.classList.toggle("dark", dark);
}

function syncFullscreenState() {
  const browserFullscreenElement = document.fullscreenElement || document.webkitFullscreenElement;
  const isFullscreen = Boolean(browserFullscreenElement || fullscreenFallbackActive || tg?.isFullscreen);
  document.documentElement.classList.toggle("is-fullscreen", isFullscreen);
  document.documentElement.classList.toggle("telegram-viewport", Boolean(tg));
  if (fullscreenButton) {
    if (isTelegramDesktopMiniApp()) {
      fullscreenButton.textContent = "↗";
      fullscreenButton.setAttribute("aria-label", "Открыть во внешнем браузере");
      fullscreenButton.title = "Открыть во внешнем браузере на весь экран";
      return;
    }
    fullscreenButton.textContent = isFullscreen ? "↙" : "⛶";
    fullscreenButton.setAttribute("aria-label", isFullscreen ? "Выйти из полноэкранного режима" : "Во весь экран");
    fullscreenButton.title = isFullscreen ? "Выйти из полноэкранного режима" : "Во весь экран";
  }
}

function isTelegramDesktopMiniApp() {
  const platform = String(tg?.platform || "").toLowerCase();
  return Boolean(tg && /tdesktop|desktop|windows|macos|linux/.test(platform));
}

function miniAppExternalUrl() {
  const url = new URL(window.location.href);
  url.searchParams.set("owner_id", ownerId);
  url.searchParams.set("desktop", "1");
  return url.toString();
}

function openMiniAppInExternalBrowser() {
  const url = miniAppExternalUrl();
  setupText.textContent = "Открываю mini app во внешнем браузере. Там можно развернуть на весь экран.";
  if (tg?.openLink) {
    tg.openLink(url);
    return;
  }
  window.open(url, "_blank", "noopener");
}

async function toggleFullscreenMode() {
  tg?.expand?.();
  tg?.disableVerticalSwipes?.();

  if (isTelegramDesktopMiniApp()) {
    openMiniAppInExternalBrowser();
    return;
  }

  try {
    const browserFullscreenElement = document.fullscreenElement || document.webkitFullscreenElement;
    if (browserFullscreenElement || fullscreenFallbackActive || tg?.isFullscreen) {
      fullscreenFallbackActive = false;
      if (document.exitFullscreen && browserFullscreenElement) {
        await document.exitFullscreen();
      } else if (document.webkitExitFullscreen && browserFullscreenElement) {
        document.webkitExitFullscreen();
      }
      tg?.exitFullscreen?.();
    } else {
      fullscreenFallbackActive = true;
      syncFullscreenState();
      if (document.documentElement.requestFullscreen) {
        await document.documentElement.requestFullscreen();
        fullscreenFallbackActive = false;
      } else if (document.documentElement.webkitRequestFullscreen) {
        document.documentElement.webkitRequestFullscreen();
        fullscreenFallbackActive = false;
      } else if (tg?.requestFullscreen) {
        tg.requestFullscreen();
      }
    }
  } catch (_) {
    fullscreenFallbackActive = true;
  } finally {
    syncFullscreenState();
  }
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
  if (webSessionToken) params.set("web_token", webSessionToken);
  const payload = await apiJson(`${apiBaseUrl}/api/devices?${params.toString()}`);
  devices = payload.devices || [];
  window.currentDeviceScope = payload.scope || "own";
}

function createPairingQr() {
  return apiJson(`${apiBaseUrl}/api/pair/new?owner_id=${encodeURIComponent(ownerId)}`);
}

function apiAuthPayload(extra = {}) {
  return { actor_id: ownerId, init_data: tg?.initData || "", web_token: webSessionToken, ...extra };
}

function apiAuthParams(extra = {}) {
  const params = new URLSearchParams({ ...extra });
  if (tg?.initData) {
    params.set("actor_id", ownerId);
    params.set("init_data", tg.initData);
  }
  if (webSessionToken) params.set("web_token", webSessionToken);
  return params;
}

async function refreshWebSession() {
  if (!tg?.initData) return;
  try {
    const params = new URLSearchParams({ init_data: tg.initData });
    const session = await apiJson(`${apiBaseUrl}/api/web-session?${params.toString()}`);
    if (session.web_token) {
      webSessionToken = session.web_token;
      localStorage.setItem(webSessionStorageKey, webSessionToken);
    }
  } catch (_) {
    // Existing signed session remains usable in PWA/standalone mode.
  }
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
  if ((!tg?.initData && !webSessionToken) || !deviceAlertPanel) return;
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
    travel_mode: Boolean(deviceAlertsTravelMode?.checked),
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
  deviceAlertsTravelMode.checked = Boolean(deviceAlertSettings.travel_mode);
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

async function loadPersonalAlerts() {
  if ((!tg?.initData && !webSessionToken) || !personalAlertsPanel) return;
  try {
    const payload = await apiJson(`${apiBaseUrl}/api/alerts/me?${apiAuthParams().toString()}`);
    const settings = payload.settings || {};
    const enabled = new Set(settings.enabled_kinds || payload.kinds || []);
    personalAlertsEnabled.checked = settings.enabled !== false;
    personalAlertKinds.innerHTML = (payload.kinds || []).map((kind) => `<label class="alert-kind"><input type="checkbox" value="${escapeHtml(kind)}" ${enabled.has(kind) ? "checked" : ""}><span>${escapeHtml(deviceAlertKindLabels[kind] || kind)}</span></label>`).join("");
  } catch (_) {
    personalAlertsPanel.classList.add("hidden");
  }
}

async function savePersonalAlerts() {
  const enabledKinds = $$("input:checked", personalAlertKinds).map((input) => input.value);
  personalAlertsSave.disabled = true;
  try {
    await apiJson(`${apiBaseUrl}/api/alerts/me`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(apiAuthPayload({ settings: { enabled: personalAlertsEnabled.checked, enabled_kinds: enabledKinds } })),
    });
    personalAlertsSave.textContent = "Сохранено ✓";
    setTimeout(() => { personalAlertsSave.textContent = "Сохранить"; }, 1500);
  } finally {
    personalAlertsSave.disabled = false;
  }
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
  const dangerous = new Set(["lock_screen", "play_alarm", "blackout_on", "lost_mode_on"]);
  const controlPin = dangerous.has(type) ? prompt("Введите безопасный PIN для подтверждения команды") : "";
  if (dangerous.has(type) && !controlPin) return Promise.reject(new Error("Команда отменена: PIN не введён."));
  return apiJson(`${apiBaseUrl}/api/devices/command`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(apiAuthPayload({ owner_id: deviceOwnerId(device), device_id: device.device_id, type, payload, control_pin: controlPin })),
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

function loadRemoteLogItems() {
  try {
    const parsed = JSON.parse(localStorage.getItem(remoteLogStorageKey) || "[]");
    return Array.isArray(parsed) ? parsed.slice(0, 50) : [];
  } catch (_) {
    return [];
  }
}

function saveRemoteLogItems() {
  localStorage.setItem(remoteLogStorageKey, JSON.stringify(remoteLogItems.slice(0, 50)));
}

function percent(value) {
  return `${Math.round(Number(value || 0) * 100)}%`;
}

function commandPayloadSummary(type, payload = {}) {
  if (type === "tap" || type === "long_tap") return `координаты: ${percent(payload.x)}, ${percent(payload.y)}`;
  if (type === "swipe") return `свайп: ${percent(payload.x)}, ${percent(payload.y)} -> ${percent(payload.end_x)}, ${percent(payload.end_y)}`;
  if (type === "input_text") return `текст: ${String(payload.text || "").length} символов, содержимое не сохраняется`;
  if (type === "request_screen") return `качество: ${payload.quality || getDeviceQuality(selectedDevice() || {})}`;
  return "";
}

function commandLogTitle(type) {
  const label = remoteCommandLabels[type] || type || "Команда";
  return String(label).replace(/\.$/, "");
}

function commandLogDetail(device, type, payload = {}, result = null) {
  const deviceName = device?.name || "устройство";
  const parts = [`${deviceName}`, `действие: ${commandLogTitle(type)}`];
  const payloadSummary = commandPayloadSummary(type, payload);
  if (payloadSummary) parts.push(payloadSummary);
  if (result?.command?.command_id) parts.push(`id: ${result.command.command_id}`);
  if (result?.command?.status) parts.push(`статус: ${result.command.status}`);
  if (result?.command?.client_latency_ms) parts.push(`${result.command.client_latency_ms} ms`);
  if (result?.command?.result) parts.push(String(result.command.result).slice(0, 160));
  return parts.join(" · ");
}

function renderRemoteLog() {
  if (!remoteActionLog) return;
  remoteActionLog.innerHTML = remoteLogItems.length
    ? remoteLogItems.slice(0, 30).map((item) => `<li data-status="${escapeHtml(item.status)}"><span>${escapeHtml(item.time)}${item.device ? ` · ${escapeHtml(item.device)}` : ""}</span><strong>${escapeHtml(item.title)}</strong><p>${escapeHtml(item.detail)}</p></li>`).join("")
    : '<li class="muted-log"><p>Пока нет действий в этой сессии.</p></li>';
}

function addRemoteLog(title, detail, status = "info", meta = {}) {
  const time = new Intl.DateTimeFormat("ru-RU", { hour: "2-digit", minute: "2-digit", second: "2-digit" }).format(new Date());
  const device = meta.device || selectedDevice();
  remoteLogItems = [{
    time,
    title,
    detail,
    status,
    device: device?.name || "",
    device_id: device?.device_id || "",
    command_id: meta.command_id || "",
  }, ...remoteLogItems].slice(0, 50);
  saveRemoteLogItems();
  renderRemoteLog();
}

function remoteLogText() {
  if (!remoteLogItems.length) return "Журнал действий пуст.";
  return remoteLogItems.map((item) => [
    item.time,
    item.device || "устройство",
    item.status,
    item.title,
    item.detail,
    item.command_id ? `command_id=${item.command_id}` : "",
  ].filter(Boolean).join(" · ")).join("\n");
}

function setRemoteBusy(value) {
  remoteCommandBusy = value;
  remotePanel.classList.toggle("busy", value);
  [
    ...$$(".remote-command-button", remotePanel),
    ...$$(".remote-manage-button", remotePanel),
    ...$$(".remote-diagnose-button", remotePanel),
    ...$$(".remote-macro-button", remotePanel),
    ...quickActionButtons,
    $(".remote-screen-button", remotePanel),
    $(".remote-stop-screen-button", remotePanel),
    remotePanelSendText,
    nextSetupStepButton,
    remoteHealthActionButton,
  ].filter(Boolean).forEach((button) => {
    button.disabled = value;
  });

  if (!value) {
    renderSetupAutomation(selectedDevice());
    renderRemoteHealth(selectedDevice());
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
      screenPreview.dataset.capture = payload.frame.black_frame ? "blocked" : "live";
      const frameAge = Math.max(0, Math.round(Date.now() / 1000 - payload.frame.updated_at));
      if (payload.frame.black_frame) {
        const ratio = Math.round(Number(payload.frame.black_ratio || 0) * 100);
        controlNote.textContent = `Кадр почти черный (${ratio}%). Обычно это защищенное приложение/DRM/FLAG_SECURE: Android блокирует трансляцию. Можно нажать Домой или управлять жестами вслепую.`;
        return;
      }
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
      addRemoteLog(commandLogTitle(type), commandLogDetail(device, type, payload), "pending", { device });
    }
    controlNote.textContent = "Команда отправлена, жду ответ агента...";
    const result = await sendCommandAndWait(device, type, payload, timeoutMs);
    const message = commandResultText(result, successText);
    controlNote.textContent = message;
    if (controlNote === remoteControlNote) {
      addRemoteLog(
        commandLogTitle(type),
        commandLogDetail(device, type, payload, result),
        result?.command?.status === "rejected" ? "warn" : "done",
        { device, command_id: result?.command?.command_id }
      );
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

async function runDeviceDiagnostic() {
  const device = selectedDevice();
  if (!device) {
    remoteControlNote.textContent = "Сначала выбери устройство.";
    return;
  }
  if (remoteCommandBusy) {
    remoteControlNote.textContent = "Предыдущая команда еще выполняется.";
    return;
  }

  const diagnostics = device.diagnostics || {};
  const pending = Number(diagnostics.pending_commands || 0);
  const delivered = Number(diagnostics.delivered_commands || 0);

  try {
    setRemoteBusy(true);
    addRemoteLog("diagnostic", "Запускаю проверку связи.", "pending");

    if (pending || delivered) {
      remoteControlNote.textContent = `В очереди ${pending + delivered} активных команд. Очищаю перед ping...`;
      const cleared = await manageDevice(device, "clear_commands");
      addRemoteLog("clear_commands", `Снято команд: ${Number(cleared.cleared || 0)}.`, "done");
    }

    if (!canControlDevice(device)) {
      const message = formatHealthHint(device, "Устройство offline. Запусти агент на телефоне и повтори диагностику.");
      remoteControlNote.textContent = message;
      addRemoteLog("diagnostic", message, "warn");
      await refreshDevices();
      return;
    }

    remoteControlNote.textContent = "Проверяю ping агента...";
    const ping = await sendCommandAndWait(device, "ping", {}, 5000);
    const status = ping?.command?.status;
    const message = commandResultText(ping, "Агент отвечает.");
    remoteControlNote.textContent = message;
    addRemoteLog("ping", message, status === "timeout" || status === "rejected" ? "warn" : "done");

    if (status === "timeout" || status === "rejected") {
      remoteControlNote.textContent = `${message} Очисти очередь или запусти ремонт связи.`;
    }
    await refreshDevices();
  } catch (error) {
    remoteControlNote.textContent = error.message;
    addRemoteLog("diagnostic", error.message, "error");
  } finally {
    setRemoteBusy(false);
  }
}

async function runWakeUnlockMacro() {
  const device = selectedDevice();
  if (!device) {
    remoteControlNote.textContent = "Сначала выбери устройство.";
    return;
  }
  if (remoteCommandBusy) {
    remoteControlNote.textContent = "Предыдущая команда еще выполняется.";
    return;
  }
  if (!canControlDevice(device)) {
    const message = formatHealthHint(device, "Устройство offline. Запусти агент и повтори.");
    remoteControlNote.textContent = message;
    addRemoteLog("wake_unlock", message, "warn");
    return;
  }

  try {
    setRemoteBusy(true);
    addRemoteLog("wake_unlock", "Бужу экран и запрашиваю снятие keyguard.", "pending");
    remoteControlNote.textContent = "Бужу экран...";
    const wake = await sendCommandAndWait(device, "wake_screen", {}, 5000);
    addRemoteLog("wake_screen", commandResultText(wake, "Экран пробужден."), wake?.command?.status === "timeout" ? "warn" : "done");

    remoteControlNote.textContent = "Запрашиваю разблокировку. PIN/биометрию нужно подтвердить на телефоне.";
    const unlock = await sendCommandAndWait(device, "dismiss_keyguard", {}, 7000);
    const message = commandResultText(
      unlock,
      "Запрос разблокировки отправлен. Если стоит PIN/биометрия, подтверди на телефоне."
    );
    remoteControlNote.textContent = message;
    addRemoteLog("dismiss_keyguard", message, unlock?.command?.status === "timeout" ? "warn" : "done");
    await refreshDevices();
  } catch (error) {
    remoteControlNote.textContent = error.message;
    addRemoteLog("wake_unlock", error.message, "error");
  } finally {
    setRemoteBusy(false);
  }
}

async function runStabilizeMacro() {
  const device = selectedDevice();
  if (!device) {
    remoteControlNote.textContent = "Сначала выбери устройство.";
    return;
  }
  if (remoteCommandBusy) {
    remoteControlNote.textContent = "Предыдущая команда еще выполняется.";
    return;
  }

  try {
    setRemoteBusy(true);
    addRemoteLog("stabilize", "Запускаю стабилизацию связи.", "pending");

    const diagnostics = device.diagnostics || {};
    const activeCommands = Number(diagnostics.pending_commands || 0) + Number(diagnostics.delivered_commands || 0);
    if (activeCommands) {
      remoteControlNote.textContent = `Снимаю зависшую очередь: ${activeCommands} активных команд.`;
      const cleared = await manageDevice(device, "clear_commands");
      addRemoteLog("clear_commands", `Снято команд: ${Number(cleared.cleared || 0)}.`, "done");
      await refreshDevices();
    }

    const freshDevice = selectedDevice() || device;
    if (!canControlDevice(freshDevice)) {
      const message = formatHealthHint(freshDevice, "Устройство offline. Очередь очищена, теперь открой Agent на телефоне.");
      remoteControlNote.textContent = message;
      addRemoteLog("stabilize", message, "warn");
      return;
    }

    remoteControlNote.textContent = "Проверяю связь ping...";
    const firstPing = await sendCommandAndWait(freshDevice, "ping", {}, 5000);
    const firstStatus = firstPing?.command?.status;
    const firstMessage = commandResultText(firstPing, "Агент отвечает.");
    addRemoteLog("ping", firstMessage, firstStatus === "timeout" || firstStatus === "rejected" ? "warn" : "done");

    if (firstStatus !== "timeout" && firstStatus !== "rejected") {
      remoteControlNote.textContent = `${firstMessage} Связь стабильна.`;
      await refreshDevices();
      return;
    }

    remoteControlNote.textContent = "Ping нестабилен. Запускаю ремонт связи...";
    const repair = await sendCommandAndWait(freshDevice, "repair_agent", {}, 8000);
    const repairStatus = repair?.command?.status;
    const repairMessage = commandResultText(repair, "Ремонт связи запущен.");
    addRemoteLog("repair_agent", repairMessage, repairStatus === "timeout" || repairStatus === "rejected" ? "warn" : "done");

    remoteControlNote.textContent = "Повторно проверяю ping...";
    const secondPing = await sendCommandAndWait(freshDevice, "ping", {}, 6000);
    const secondStatus = secondPing?.command?.status;
    const secondMessage = commandResultText(secondPing, "Агент отвечает после ремонта.");
    remoteControlNote.textContent = secondStatus === "timeout" || secondStatus === "rejected"
      ? `${secondMessage} Если не ожило, открой Agent на телефоне вручную.`
      : `${secondMessage} Связь восстановлена.`;
    addRemoteLog("ping_after_repair", secondMessage, secondStatus === "timeout" || secondStatus === "rejected" ? "warn" : "done");
    await refreshDevices();
  } catch (error) {
    remoteControlNote.textContent = error.message;
    addRemoteLog("stabilize", error.message, "error");
  } finally {
    setRemoteBusy(false);
  }
}

function updateQualityButtons(device, root, selector) {
  const quality = device ? getDeviceQuality(device) : "balanced";
  $$(selector, root).forEach((button) => button.classList.toggle("active", button.dataset.quality === quality));
}

function runQuickAction(action) {
  if (action === "screen") {
    setRemoteTab("screen");
    startRemoteScreen();
    return;
  }
  if (action === "stabilize") {
    setRemoteTab("system");
    runStabilizeMacro();
    return;
  }
  if (action === "setup") {
    setRemoteTab("setup");
    nextSetupStepButton?.click();
    return;
  }
  if (action === "wake_unlock") {
    setRemoteTab("screen");
    runWakeUnlockMacro();
    return;
  }
  if (action === "report") {
    copySelectedDeviceReport();
    return;
  }
  if (action === "pair") {
    requestPairButton.click();
    return;
  }
  if (action === "notification_listener") {
    setRemoteTab("system");
    sendSimpleDeviceCommand(
      selectedDevice(),
      "request_notification_listener_permission",
      remoteControlNote,
      remoteCommandMessages.request_notification_listener_permission
    );
    return;
  }
  if (action === "home") {
    setRemoteTab("nav");
    sendSimpleDeviceCommand(selectedDevice(), "home", remoteControlNote, remoteCommandMessages.home);
  }
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
  const telemetry = device.telemetry || {};
  const activeCommand = device.diagnostics?.last_command;
  remoteNowTitle.textContent = telemetry.active_app_label || telemetry.active_app_package || (device.online ? "Агент работает в фоне" : "Устройство не на связи");
  remoteNowDetail.textContent = activeCommand
    ? `Команда: ${activeCommand.type} · ${activeCommand.status}. Агент: ${telemetry.agent_enabled === false ? "выключен" : "активен"}.`
    : `Активных команд нет. Агент: ${telemetry.agent_enabled === false ? "выключен" : "активен"}.`;
  loadDeviceHistory(device);
  updateQualityButtons(device, remotePanel, ".remote-quality-button");
  setRemoteTab(activeRemoteTab);
  renderSetupAutomation(device);
  renderRemoteHealth(device);
  remoteControlNote.textContent = formatDeviceNote(device);

  if (restartScreen && device.online) {
    startScreenPolling(device, remoteScreenPreview, remoteScreenImage, remoteControlNote);
  }
}

async function loadDeviceHistory(device) {
  if (!deviceHistoryStrip) return;
  try {
    const params = apiAuthParams({ owner_id: deviceOwnerId(device), device_id: device.device_id, hours: "24" });
    const payload = await apiJson(`${apiBaseUrl}/api/devices/history?${params.toString()}`);
    const history = (payload.history || []).slice(0, 10);
    deviceHistoryStrip.innerHTML = history.length ? history.map((item) => {
      const telemetry = item.telemetry || {};
      const battery = telemetry.battery_percent;
      const title = item.error || `${item.online ? "Online" : "Offline"}${Number.isFinite(Number(battery)) ? ` · ${battery}%` : ""}`;
      return `<span data-status="${item.error ? "error" : (item.online ? "online" : "offline")}" title="${escapeHtml(title)}"></span>`;
    }).join("") : '<small>История начнёт заполняться после новых heartbeat.</small>';
  } catch (_) {
    deviceHistoryStrip.innerHTML = '<small>История временно недоступна.</small>';
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
        const payload = { x: start.x, y: start.y, end_x: end.x, end_y: end.y };
        addRemoteLog("Свайп по экрану", commandLogDetail(device, "swipe", payload), "pending", { device });
        const result = await sendCommandAndWait(device, "swipe", payload);
        note.textContent = commandResultText(result, "Свайп выполнен.");
        addRemoteLog("Свайп по экрану", commandLogDetail(device, "swipe", payload, result), result?.command?.status === "rejected" ? "warn" : "done", { device, command_id: result?.command?.command_id });
        return;
      }
      const payload = { x: end.x, y: end.y };
      addRemoteLog("Тап по экрану", commandLogDetail(device, "tap", payload), "pending", { device });
      const result = await sendCommandAndWait(device, "tap", payload);
      note.textContent = commandResultText(result, `Тап: ${Math.round(end.x * 100)}%, ${Math.round(end.y * 100)}%.`);
      addRemoteLog("Тап по экрану", commandLogDetail(device, "tap", payload, result), result?.command?.status === "rejected" ? "warn" : "done", { device, command_id: result?.command?.command_id });
    } catch (error) {
      note.textContent = error.message;
      addRemoteLog("Жест по экрану", error.message, "error", { device });
    }
  });
  image.addEventListener("dblclick", async (event) => {
    const device = getDevice();
    if (!device || !device.online) {
      note.textContent = "Long tap недоступен, пока устройство offline.";
      return;
    }
    try {
      const payload = normalizedPoint(event, image);
      addRemoteLog("Long tap по экрану", commandLogDetail(device, "long_tap", payload), "pending", { device });
      const result = await sendCommandAndWait(device, "long_tap", payload);
      note.textContent = commandResultText(result, "Long tap выполнен.");
      addRemoteLog("Long tap по экрану", commandLogDetail(device, "long_tap", payload, result), result?.command?.status === "rejected" ? "warn" : "done", { device, command_id: result?.command?.command_id });
    } catch (error) {
      note.textContent = error.message;
      addRemoteLog("Long tap по экрану", error.message, "error", { device });
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
  renderFleetPulse(onlineCount);
  renderDeviceToolbar();
  renderInstallationProgress();
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

  const filteredDevices = visibleDevices();
  if (!filteredDevices.length) {
    deviceList.innerHTML = '<p class="empty-state compact-empty">По этому фильтру устройств нет. Измени поиск или покажи весь список.</p>';
  }

  filteredDevices.forEach((device) => {
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
    if (device.pairing_required) {
      card.classList.add("pairing-required");
      controlNote.textContent = "APK установлен и запущен. Разрешения уже отслеживаются, управление откроется после QR-подключения.";
      card.querySelectorAll("button").forEach((button) => {
        button.disabled = true;
        button.title = "Сначала подтвердите владельца по QR";
      });
    }

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
    loadTimeline();
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

deviceSearchInput?.addEventListener("input", () => {
  deviceSearchQuery = deviceSearchInput.value;
  render();
});

deviceFilterButtons.forEach((button) => {
  button.addEventListener("click", () => {
    activeDeviceFilter = button.dataset.deviceFilter || "all";
    localStorage.setItem("hunter_device_filter", activeDeviceFilter);
    render();
  });
});

connectCurrentDevice.addEventListener("click", () => {
  currentDeviceText.textContent = "Открываю страницу установки Android Agent...";
  openExternal(agentInstallUrl);
});

installAgentButton.addEventListener("click", () => {
  localStorage.setItem(installStartedKey, "1");
  renderInstallationProgress();
  setupText.textContent = "Открываю страницу установки APK...";
  openExternal(agentInstallUrl);
});

openInstalledAgentButton.addEventListener("click", () => {
  localStorage.setItem(agentOpenAttemptKey, "1");
  renderInstallationProgress();
  setupText.textContent = "Готовлю автономное подключение Agent...";
  openAgentWithPairing();
});

openDesktopAppButton?.addEventListener("click", openMiniAppInExternalBrowser);

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

copyRemoteStatusButton?.addEventListener("click", copySelectedDeviceReport);

remoteTabs.forEach((button) => {
  button.addEventListener("click", () => setRemoteTab(button.dataset.remoteTab));
});

quickActionButtons.forEach((button) => {
  button.addEventListener("click", () => runQuickAction(button.dataset.action));
});

remoteHealthActionButton?.addEventListener("click", () => runQuickAction(remoteHealthActionButton.dataset.action));

remoteLogClearButton?.addEventListener("click", () => {
  remoteLogItems = [];
  saveRemoteLogItems();
  renderRemoteLog();
});

remoteLogCopyButton?.addEventListener("click", async () => {
  try {
    await copyTextToClipboard(remoteLogText());
    remoteControlNote.textContent = "Журнал действий скопирован.";
  } catch (error) {
    remoteControlNote.textContent = `Не удалось скопировать журнал: ${error.message}`;
  }
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
    const textPayload = command === "input_text"
      ? { text: remotePanelTextInput.value.trim() }
      : (command === "blackout_on" ? { text: blackoutMessage?.value.trim() || "Устройство временно недоступно" } : {});
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

$$(".remote-diagnose-button", remotePanel).forEach((button) => {
  button.addEventListener("click", runDeviceDiagnostic);
});

$$(".remote-macro-button", remotePanel).forEach((button) => {
  button.addEventListener("click", () => {
    if (button.dataset.macro === "wake_unlock") {
      runWakeUnlockMacro();
      return;
    }
    if (button.dataset.macro === "stabilize") {
      runStabilizeMacro();
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

remotePanelTextInput.addEventListener("keydown", (event) => {
  if (event.key !== "Enter" || event.shiftKey) return;
  event.preventDefault();
  remotePanelSendText.click();
});

bindScreenGestures(remoteScreenImage, selectedDevice, remoteControlNote);

emergencyStopButton?.addEventListener("click", async () => {
  const device = selectedDevice();
  if (!device) return;
  const controlPin = prompt("Аварийная остановка: введите безопасный PIN");
  if (!controlPin) return;
  try {
    setRemoteBusy(true);
    const result = await manageDevice(device, "emergency_stop", { control_pin: controlPin });
    remoteControlNote.textContent = `Аварийная остановка выполнена. Очередь очищена: ${Number(result.cleared || 0)}.`;
    addRemoteLog("Аварийная остановка", "Команды и трансляции остановлены.", "done", { device });
  } catch (error) {
    remoteControlNote.textContent = error.message;
  } finally {
    setRemoteBusy(false);
  }
});

refreshButton.addEventListener("click", async () => {
  setupText.textContent = "Обновляю список устройств...";
  await Promise.all([refreshDevices(), loadSetupStatus()]);
});

deployRefreshButton?.addEventListener("click", loadSetupStatus);
deviceAlertRefreshButton?.addEventListener("click", loadDeviceAlerts);
timelineRefreshButton?.addEventListener("click", loadTimeline);
deviceAlertSaveButton?.addEventListener("click", saveDeviceAlertSettings);
personalAlertsSave?.addEventListener("click", savePersonalAlerts);
companionScreenButton?.addEventListener("click", startCompanionScreen);
companionCameraButton?.addEventListener("click", startCompanionCamera);
companionLocationButton?.addEventListener("click", requestCompanionLocation);
companionNotificationButton?.addEventListener("click", requestCompanionNotifications);
companionStopButton?.addEventListener("click", stopCompanionAccess);
window.addEventListener("pagehide", stopCompanionAccess);

themeButton.addEventListener("click", () => {
  const dark = !document.documentElement.classList.contains("dark");
  document.documentElement.classList.toggle("dark", dark);
  localStorage.setItem("apk_converter_theme", dark ? "dark" : "light");
});

fullscreenButton?.addEventListener("click", toggleFullscreenMode);
commandPaletteButton?.addEventListener("click", () => setCommandPalette(true));
commandPaletteClose?.addEventListener("click", () => setCommandPalette(false));
commandPaletteBackdrop?.addEventListener("click", () => setCommandPalette(false));
commandPaletteInput?.addEventListener("input", filterCommandPalette);
commandPaletteItems.forEach((item) => item.addEventListener("click", async () => {
  setCommandPalette(false);
  if (item.dataset.target) document.querySelector(item.dataset.target)?.scrollIntoView({ behavior: "smooth", block: "start" });
  if (item.dataset.action === "refresh") await Promise.all([refreshDevices(), loadSetupStatus()]);
  if (item.dataset.action === "theme") themeButton.click();
}));
document.addEventListener("keydown", (event) => {
  if ((event.ctrlKey || event.metaKey) && event.key.toLocaleLowerCase() === "k") {
    event.preventDefault();
    setCommandPalette(true);
  } else if (event.key === "Escape" && !commandPalette?.classList.contains("hidden")) {
    setCommandPalette(false);
  }
});
window.addEventListener("beforeinstallprompt", (event) => {
  event.preventDefault();
  pwaInstallPrompt = event;
  installPwaButton?.classList.remove("hidden");
});
installPwaButton?.addEventListener("click", installPwa);

document.addEventListener("fullscreenchange", syncFullscreenState);
document.addEventListener("webkitfullscreenchange", syncFullscreenState);

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
renderCompanionCapabilities();
syncFullscreenState();
renderRemoteLog();
renderCurrentDevice();
renderSetupStatus();
loadSetupStatus();
loadTimeline();
refreshWebSession().finally(() => {
  refreshDevices();
  loadPersonalAlerts();
});
startRefreshLoop();
updateLocalClock();
setInterval(updateLocalClock, 1000);
