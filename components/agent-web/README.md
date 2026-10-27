# agent-web

Your web AI agent (Claude, ChatGPT, Gemini, Copilot, Le Chat, Perplexity, or any other
site) in its own window: a separate Firefox profile, so the sign-in persists, with no tabs or
toolbars. It always sits at the left of the panel and reopens if it is closed.

- **First start:** a welcome page lists common agents. Open yours and sign in the way it asks,
  including Google or Apple sign-in or a separate login domain. During this first session
  the window may go anywhere: agent-web remembers the first site as home, and every domain
  visited on the way.
- **After that:** the window opens on your agent and only those domains stay in it. Every
  other link, or one sent to the window from elsewhere, opens in your main Firefox. The
  window remembers the conversation it was last on and reopens there (not sign-in or
  settings pages, and not pages on the extra domains).
- **Commands:** `agent-web stop` closes it until your next login. `agent-web set-home
  https://...` picks a page directly, until the window moves to another one. `agent-web reset` forgets the page and shows the
  welcome page again.
- **Turning it off:** create an empty `~/.config/limde/autostart.d/60-agent-web.sh`, then
  run `agent-web stop`. Delete that file to bring the window back at the next login.
- **Settings:** `~/.config/limde/agent-web.conf`, with lines `url=...` and
  `keep=domain ...` (extra domains to keep in the window, such as a separate login site).
- **Keys:** Super+W, Super+Q, Alt+F4 and Firefox's Ctrl+W and Ctrl+Q don't close it, so it
  isn't closed by accident. Ctrl+T, Ctrl+N and their Shift variants do nothing: the window
  has no tab bar, so a new tab or window would have no way back.

How it works: the `agent-web` script launches Firefox with its own profile and Wayland app
ID `limde.AgentWeb`. Firefox autoconfig (`agent-web.cfg`, copied into the Firefox
install folder at each start, because Firefox updates can replace it) decides which pages
stay. Tinybar puts that app ID first; the labwc config guards it from the close keys.
