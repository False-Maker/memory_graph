# Memory Graph 故障排查

## 先确认你跑的是默认链路

当前前端是 React Web。

正确命令：

```bash
npm --prefix frontend run dev
```

## 1. 前端打不开

检查开发服务器：

```bash
npm --prefix frontend run dev
```

预期看到：

- `Local: http://127.0.0.1:5173/` 或 `http://localhost:5173/`

如果端口被占用，换一个端口：

```bash
npm --prefix frontend run dev -- --host 127.0.0.1 --port 5174
```

## 2. 页面打开了，但 API 全红

默认开发态前端会请求：

- `http://127.0.0.1:8000/api/v1`
- `http://127.0.0.1:8000/health`
- `http://127.0.0.1:3001/health`

先启动 FastAPI：

```bash
PYTHONPATH=. python3 -m uvicorn src.api.main:app --host 127.0.0.1 --port 8000 --reload
```

再检查：

```bash
curl -sf http://127.0.0.1:8000/health
```

如需 Startup 页面里的 Sidecar 探测正常，再启动：

```bash
npm --prefix frontend/api run build
HOST=127.0.0.1 PORT=3001 npm --prefix frontend/api run start
```

并检查：

```bash
curl -sf http://127.0.0.1:3001/health
curl -sf http://127.0.0.1:3001/ready
```

## 3. 本地开发跨域失败

仓库默认已经把常见本地端口加入 CORS 白名单：

- `3000`
- `4173`
- `5173`

如果你用了别的前端端口，需要调整 `config/settings.yaml` 中的 `app.cors.allow_origins`。

## 4. 构建成功，但部署后首页空白

先确认是否生成了默认产物目录：

```bash
npm --prefix frontend run build
find frontend/dist -maxdepth 2 -type f | head
```

FastAPI 只会托管 `frontend/dist`。

再确认是通过 FastAPI 访问，而不是直接打开本地文件：

```bash
SIDECAR_BASE_URL=http://127.0.0.1:3001 PYTHONPATH=. python3 -m uvicorn src.api.main:app --host 127.0.0.1 --port 8000
```

然后访问：

- `http://127.0.0.1:8000/`

## 5. Startup 页面里 Sidecar 一直是 DOWN

部署态默认会走 FastAPI 代理：

- `GET /sidecar/health`
- `GET /sidecar/ready`

如果代理返回失败，优先检查：

```bash
echo "$SIDECAR_BASE_URL"
curl -sf http://127.0.0.1:3001/health
```

如果 Sidecar 不在本机 3001 端口，启动 FastAPI 时显式传入：

```bash
SIDECAR_BASE_URL=http://your-sidecar-host:3001 PYTHONPATH=. python3 -m uvicorn src.api.main:app --host 127.0.0.1 --port 8000
```

## 6. 单节点部署怎么自检

```bash
cp scripts/deployment/.env.intranet.example .env.intranet
bash scripts/deployment/intranet-single-node-start.sh
bash scripts/deployment/intranet-health-check.sh
```

预期：

- `http://127.0.0.1:8000/` 可访问
- `http://127.0.0.1:8000/health` 返回健康状态
- `http://127.0.0.1:8000/sidecar/health` 返回 Sidecar 健康状态

## 7. 还不清楚问题在哪

按这个顺序贴信息最快：

1. `npm --prefix frontend run build` 的报错
2. `curl -i http://127.0.0.1:8000/health`
3. `curl -i http://127.0.0.1:8000/sidecar/health`
4. 浏览器 Console 第一条报错

## 8. 远程 provider 主链路怎么判绿

直接跑：

```bash
npm --prefix frontend run qa:real-stack-smoke:remote:verify
```

只读现有 evidence、不重新发请求时：

```bash
npm --prefix frontend run qa:real-stack-smoke:remote:doctor
```

退出码：

- `0`: 全绿
- `1`: readiness 或 matrix 存在 blocked/failed provider
- `2`: evidence 缺失、损坏或 scope/suffix 不匹配

关键 evidence：

- `.sisyphus/evidence/task-15-provider-readiness-remote.json`
- `.sisyphus/evidence/task-16-provider-matrix-summary-remote.json`

## 9. remote verify 在 CI 里直接失败

先确认 GitHub Actions secrets 至少满足以下之一：

- 推荐：`BIGMODEL_API_KEY`
- 或者：同时提供 `OPENAI_API_KEY` 与 `ANTHROPIC_API_KEY`

如果 workflow 失败但需要先看证据，不要手翻 job 日志，优先下载 artifact：

- `remote-provider-verify-evidence`

如果结论是 `exit_code=1`，先看 matrix summary 里哪个 provider 被阻断；如果是 `exit_code=2`，先看 evidence 文件是否缺失、损坏，或 `provider_scope` / `evidence_suffix` 是否不一致。
