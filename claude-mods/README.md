# Claude Code mods

Five Claude Code mods, published from this repository as the `harshit-mods` plugin marketplace (`.claude-plugin/marketplace.json` at the repository root). `.claude/settings.json` enables them, plus the Claritymaxx plugin, in every Claude Code session opened on this repository after you trust the folder.

| Mod | Command | What it does |
|---|---|---|
| token-weather | `/weather`, `/weather hide`, `/weather show` | A band above the prompt: context fill as weather, a sparkline of the last 12 turns, growth per turn, turns left, and a `/compact` hint near the limit. |
| blast-radius | `/blast-radius`, `/blast-radius <command>` (dry run) | Catches `rm -rf`, `git reset --hard`, force pushes, `git clean -f`, `git checkout .`, `git branch -D`, `git stash drop/clear`, `DROP`/`TRUNCATE`, `mkfs`, `dd of=/dev/...`. It shows what the command would touch in a pane and forces a permission prompt. A deny from your settings is never loosened. |
| replay-theater | `/replay`, `/replay 2` | Records each turn's Edit and Write calls. In the pane, `n`/`p` step through the diffs, `o`/`w` change turn, and Esc closes it. |
| changed-files | `/changed-files` | A live sidebar of every file touched this session, with +/- counts, edit counts and a `new` tag. It opens by itself on the first edit. |
| session-meter | `/meter` | The status line shows elapsed time, tool calls and files edited. A toast appears when a turn takes 60 s or more; change `toastAfterSeconds` in `/config`. |

## Use them on every device

The repository settings cover sessions opened on this repository. To get the mods and Claritymaxx in every Claude Code session on any machine where you are signed in, add them to your claude.ai account once:

1. On claude.ai, open **Customize**, then **Plugins**, then **Add**, then **Add marketplace**.
2. Enter `harshitmywork17/AI_Chatbot`. Claude reads the default branch, so merge these files into `main` first. Your GitHub account must be connected to Claude, because the repository is private.
3. Turn on each mod.
4. Add the marketplace `v60samurai/claritymaxx` the same way and turn on Claritymaxx.

Account plugins sync to Claude Code v2.1.273 or later at session start when you are signed in with that account. Run `/reload-plugins` or start a new session to load them.

Mods run in Claude Code only: the terminal, the desktop app's Code tab, IDE extensions and cloud sessions. Claude chat on the web, desktop and mobile shows no mod UI. Claritymaxx is a skill, so it also works in Claude chat and Cowork.

## Develop

Each mod has tests: `claude plugin test claude-mods/<mod>`. Check a mod with `claude plugin validate claude-mods/<mod>`. Increase `version` in a mod's `plugin.json` when you change it, because installed copies are cached by version.
