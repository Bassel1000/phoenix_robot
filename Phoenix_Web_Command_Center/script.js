const modeSwitch = document.getElementById("modeSwitch");
const manualControls = document.getElementById("manualControls");
const overrideBadge = document.getElementById("overrideBadge");
const modeFeedback = document.getElementById("modeFeedback");
const themeSwitch = document.getElementById("themeSwitch");

const showFeedback = (message) => {
  if (!modeFeedback) return;
  modeFeedback.textContent = message;
  modeFeedback.classList.add("show");
  window.clearTimeout(showFeedback.timer);
  showFeedback.timer = window.setTimeout(() => {
    modeFeedback.classList.remove("show");
  }, 1700);
};

const applyTheme = (theme) => {
  document.body.classList.toggle("light", theme === "light");
  if (themeSwitch) {
    themeSwitch.checked = theme === "dark";
  }
};

const storedTheme = window.localStorage.getItem("phoenixTheme") || "dark";
applyTheme(storedTheme);

if (themeSwitch) {
  themeSwitch.addEventListener("change", () => {
    const nextTheme = themeSwitch.checked ? "dark" : "light";
    applyTheme(nextTheme);
    window.localStorage.setItem("phoenixTheme", nextTheme);
  });
}

if (modeSwitch && manualControls && overrideBadge) {
  modeSwitch.addEventListener("change", (event) => {
    const isManual = event.target.checked;
    manualControls.hidden = !isManual;
    overrideBadge.textContent = isManual ? "MANUAL OVERRIDE ON" : "MANUAL OVERRIDE OFF";
    overrideBadge.classList.toggle("active", isManual);
    overrideBadge.classList.toggle("muted", !isManual);
    showFeedback(isManual ? "Manual mode enabled: controls are live." : "Autonomous mode restored.");
  });
}

const mainTabs = document.querySelectorAll(".main-tab");
const mainPanels = document.querySelectorAll(".main-content-panel");

for (const tab of mainTabs) {
  tab.addEventListener("click", () => {
    const targetId = tab.dataset.panel;
    mainTabs.forEach((item) => item.classList.toggle("active", item === tab));
    mainPanels.forEach((panel) => panel.classList.toggle("active", panel.id === targetId));
  });
}

const fullscreenButtons = document.querySelectorAll(".icon-button[data-target]");

for (const button of fullscreenButtons) {
  button.addEventListener("click", async () => {
    const target = document.getElementById(button.dataset.target);
    if (!target) return;

    if (document.fullscreenElement === target) {
      await document.exitFullscreen();
      return;
    }

    if (document.fullscreenElement) {
      await document.exitFullscreen();
    }

    await target.requestFullscreen();
  });
}

if (window.location.hash === "#panelSettings") {
  const settingsTab = document.querySelector('.main-tab[data-panel="panelSettings"]');
  settingsTab?.click();
}
