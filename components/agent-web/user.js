// Prefs for the agent-web profile; agent-web writes this over the profile on every launch
// and appends the home page and kept domains (limde.agentweb.*).
user_pref("toolkit.legacyUserProfileCustomizations.stylesheets", true);
user_pref("browser.startup.page", 1);
user_pref("browser.shell.checkDefaultBrowser", false);
user_pref("browser.aboutwelcome.enabled", false);
user_pref("browser.sessionstore.resume_from_crash", false);
user_pref("browser.toolbars.bookmarks.visibility", "never");
user_pref("datareporting.policy.dataSubmissionPolicyBypassNotification", true);
user_pref("browser.tabs.warnOnClose", false);
// No "Open previous tabs?" bar or other Firefox nudges in this window.
user_pref("browser.startup.couldRestoreSession.count", -1);
user_pref("browser.startup.upgradeDialog.enabled", false);
user_pref("browser.messaging-system.whatsNewPanel.enabled", false);
user_pref("browser.newtabpage.activity-stream.asrouter.userprefs.cfr.addons", false);
user_pref("browser.newtabpage.activity-stream.asrouter.userprefs.cfr.features", false);
user_pref("browser.uitour.enabled", false);
user_pref("browser.translations.automaticallyPopup", false);
user_pref("signon.rememberSignons", false);
user_pref("app.shield.optoutstudies.enabled", false);
// Links handed to the main Firefox open their short-lived tab in the background,
// so the agent page does not flicker; no Ctrl+Q quit.
user_pref("browser.tabs.loadDivertedInBackground", true);
user_pref("browser.quitShortcut.disabled", true);
// Alt alone does not show the File/Edit/View menu bar.
user_pref("ui.key.menuAccessKeyFocuses", false);
// Agent sites probe for read-aloud; without speech-dispatcher Firefox shows a bar about it.
user_pref("media.webspeech.synth.dont_notify_on_error", true);
