抽卡机的运行说明在仓库的 `dify/README.md`。本文件只描述同目录下的 PowerContext 插件骨架。

# PowerContext Dify plugin skeleton

Packageable Dify tool plugin for the `dify/` ecosystem directory. It declares a PowerContext Server credential and one tool, `pc_ping`. The tool returns a fixed skeleton payload and does not call PowerContext Server.

## Layout

| Path | Role |
| --- | --- |
| `manifest.yaml` | Plugin identity, Python 3.12 runner, and tool provider entry |
| `main.py` | Dify plugin process entrypoint |
| `provider/powercontext.yaml` | Credential form and tool list |
| `provider/powercontext.py` | Local credential shape check |
| `tools/pc_ping.yaml` | `pc_ping` declaration |
| `tools/pc_ping.py` | `pc_ping` implementation |
| `requirements.txt` | Runtime pin installed by the plugin daemon |
| `.env.example` | Remote debug install settings |

## Credentials

`server_url` must be an `http` or `https` URL, and `api_token` must be non-empty. `scope_id` is stored for later tools and is not resolved. Validation does not open a network connection.

One credential is a shared Server URL and token. This skeleton does not infer a user or conversation from Dify runtime fields.

## Run and package

Use Python 3.12:

```sh
python -m pip install -r requirements.txt
cp .env.example .env
python main.py
```

Fill `REMOTE_INSTALL_KEY` in `.env` before a remote debug session. Package with the Dify CLI from this directory:

```sh
dify plugin package . -o powercontext-0.0.1.difypkg
```

`.env`, virtual environments, and `*.difypkg` files stay out of Git.

## Adding a tool

1. Add `tools/<name>.yaml` and `tools/<name>.py`.
2. Set `extra.python.source` in the YAML to that Python file.
3. Append `tools/<name>.yaml` to `tools` in `provider/powercontext.yaml`.

Memory, context, Source capture, Handoff, Experience, Skill, and candidate tools are not part of this skeleton.
