<p align="left">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="website/docs/assets/images/logo/dark.svg">
    <img src="website/docs/assets/images/logo/light.svg" alt="Tamagooshi" height="34">
  </picture>
</p>

<p align="left"><a href="https://gooshi.me/">Docs</a> · <a href="https://gooshi.me/#config">Configure</a> · <a href="https://gooshi.me/#build">Flash from the browser</a></p>

<p align="left">Pixel-art pet for M5Stack StickC Plus and StickS3 that turns live metrics into its mood. Local hub feeds readings from metric sources such as Datadog and PostHog over BLE/MQTT. <code>config.yaml</code> selects the mascot, themes, games, and more that ship in the firmware. Follows sessions from coding agents such as Claude and Cursor, down to approving or denying their requests from the device.</p>

<p align="left">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="website/docs/assets/images/architecture-dark.svg">
    <img src="website/docs/assets/images/architecture-light.svg" alt="Tamagooshi overview" width="920">
  </picture>
</p>

<p align="left">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="website/docs/assets/images/header/rule-dark.svg">
    <img src="website/docs/assets/images/header/rule-light.svg" alt="" width="920" height="1">
  </picture>
</p>

<p align="left">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="website/docs/assets/images/header/quickstart-dark.svg">
    <img src="website/docs/assets/images/header/quickstart-light.svg" alt="Quick start" height="28">
  </picture>
</p>

```bash
make hub        # run the hub, pairs with your device over BLE
make sim        # desktop simulator, no board needed
```

`make` lists every target.

<p align="left">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="website/docs/assets/images/header/rule-dark.svg">
    <img src="website/docs/assets/images/header/rule-light.svg" alt="" width="920" height="1">
  </picture>
</p>

<p align="left">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="website/docs/assets/images/header/hardware-dark.svg">
    <img src="website/docs/assets/images/header/hardware-light.svg" alt="Hardware" height="28">
  </picture>
</p>

M5Stack StickC Plus, StickC Plus SE, and StickS3. Flash from the browser via the [docs](https://gooshi.me/#build), or locally:

```bash
cd firmware
TAMA_BRAND=<id> pio run -e m5sticks3 -t upload   # or m5stickc-plus, m5stickc-plus-se
```

`<id>` is a folder under `brands/`, its `config.yaml` defines what the build includes.

<p align="left">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="website/docs/assets/images/header/rule-dark.svg">
    <img src="website/docs/assets/images/header/rule-light.svg" alt="" width="920" height="1">
  </picture>
</p>

<p align="left">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="website/docs/assets/images/header/hub-dark.svg">
    <img src="website/docs/assets/images/header/hub-light.svg" alt="Hub" height="28">
  </picture>
</p>

Runs on the machine and communicates with the device over BLE. `TAMA_BRAND` selects the brand config.

```bash
python3 -m venv .venv && source .venv/bin/activate   # once; re-run `source .venv/bin/activate`
                                                       # in every new terminal before `make hub`
pip install -e "hub/backend[voice,claude,cursor]"     # once, Python 3.10+, extras optional
make hub TAMA_BRAND=<id>          # pairs with your device over BLE
make hub-test                     # hub unit tests
```

`make hub` (and every other `make hub-*` target) just runs plain `python`, so the venv must be
active in that terminal first — otherwise it fails with `ModuleNotFoundError`.

#### GitHub Copilot brand (`TAMA_BRAND=copilot`)

The `copilot` brand tracks local GitHub Copilot CLI/app sessions instead of voice chat: live
session status plus approve/deny of tool-permission requests, shown on the device. No extra pip
extras needed (it only uses the hub's base dependencies). One-time setup registers a
[Copilot CLI hook](https://docs.github.com/en/copilot/concepts/agents/hooks) that talks to the hub
over localhost:

```bash
source .venv/bin/activate                 # if not already active in this terminal
make hub-install-copilot-hooks            # once, writes ~/.copilot/hooks/tamagooshi.json
make hub TAMA_BRAND=copilot               # run the hub; pairs with your device over BLE
```

With the hub running, use `copilot`/`gh copilot` in any terminal as normal — the device shows the
live activity feed, and pauses with an approve/deny prompt whenever Copilot actually needs a
permission decision.

<p align="left">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="website/docs/assets/images/header/rule-dark.svg">
    <img src="website/docs/assets/images/header/rule-light.svg" alt="" width="920" height="1">
  </picture>
</p>

<p align="left">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="website/docs/assets/images/header/apps-games-dark.svg">
    <img src="website/docs/assets/images/header/apps-games-light.svg" alt="Apps & Games" height="28">
  </picture>
</p>

Apps and games ship in firmware (`device.apps`, `device.games`). Claude Desktop Buddy and Cursor both support voice conversations via the hub.

<p align="left">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="website/docs/assets/images/catalog-dark.svg">
    <img src="website/docs/assets/images/catalog-light.svg" alt="Apps, games, and AI catalog" width="920">
  </picture>
</p>

<p align="left">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="website/docs/assets/images/header/rule-dark.svg">
    <img src="website/docs/assets/images/header/rule-light.svg" alt="" width="920" height="1">
  </picture>
</p>

<p align="left">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="website/docs/assets/images/header/license-dark.svg">
    <img src="website/docs/assets/images/header/license-light.svg" alt="License" height="28">
  </picture>
</p>

MIT. See [LICENSE](LICENSE).