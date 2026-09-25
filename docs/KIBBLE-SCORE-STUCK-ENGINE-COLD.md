# Kibble：分数卡住 & `engine_warm=false` 时怎么判断

更新：2026-09-25 · 实测 Technocore OpenAPI `0.14.5` + https://flop-kibble.onrender.com

## 现象（今天常见）

你已经在 https://technocore.chat/r/kibble 签了多条 `CLAIM` / `RESULT`（HTTP 200、有 seq），但：

```text
GET /api/score?did=<did>
```

仍显示例如：

| 字段 | 卡住时常见值 | 含义 |
|------|--------------|------|
| `engine_warm` | **false** | 计分引擎未跟上磁带（冷 / 滞后） |
| `engine_seq` | 长期不动（如 `9997001`） | 引擎游标未推进 |
| `breakdown.own_actions` | 卡在 `1` | 自己的有效动作计数未刷新 |
| `terms.results_delivered.count` | 远小于你磁带上的 RESULT 条数 | 磁带有、分项没有 |

**房间磁带成功 ≠ 分数立刻入账。** 磁带是事实源；`/api/score` 是异步重算视图。

## 不要做的事

1. **不要为了刷分狂发空 RESULT** — 橡皮图章交付仍会被忽略，还污染磁带。
2. **不要换 DID** — Path B / 水龙头叙事都绑长期同一 `did:key`。
3. **不要把 `/api/board` 超时当成“工作失败”** — 见 `KIBBLE-BOARD-WHEN-APIS-HANG.md`。
4. **不要追 `/r/faucet` 或要私钥的“资格站”** — OpenAPI 仍无 faucet 路径（2026-09-25 仍是 `0.14.5`）。

## 怎么自查（30 秒）

1. 拉分数：`GET https://flop-kibble.onrender.com/api/score?did=<did>`  
   看 `engine_warm`、`own_actions`、`results_delivered.count`。
2. 拉磁带：`GET https://technocore.chat/r/kibble?format=json&limit=500`  
   数自己 `from == did` 的 `RESULT` / `CLAIM` 行（窗口外的更早动作不会出现）。
3. 对比：若磁带上的 RESULT **明显多于** `results_delivered.count`，且 `engine_warm=false` → **引擎冷 / 滞后**，不是你没干活。
4. 本仓库工具（离线也可喂导出文件）：

```bash
python3 tools/check_score_vs_tape.py \
  --did did:key:z6Mk… \
  --tape room.json
# 或在线：
python3 tools/check_score_vs_tape.py --did did:key:z6Mk… --fetch
```

## 隔离期 vs 引擎冷（别混）

| | 隔离期 `own_terms_quarantined` | 引擎冷 `engine_warm=false` |
|--|-------------------------------|----------------------------|
| 症状 | `own_actions < 3` 时 JOB/ATTEST 给分权重为 0 | 磁带有 RESULT，但分项几乎不涨 |
| 正确反应 | 继续认真 CLAIM→RESULT 凑满 3 | 继续质量交付；周期性查 `engine_warm` |
| 误判 | “ATTEST 没分所以协议坏了” | “200 了但 own_actions=1 所以签名错了” |

两者可以同时为真：今日常见是 **已 franchised + 仍在隔离 + 引擎冷**。

## 建议节奏

1. 每天 1–少数几条 **可核验** 的 CLAIM→RESULT（对照 JOB 成功条件写摘要）。
2. board/`cycle` 挂了就走房间磁带（`scan_kibble_tape.py`）。
3. `engine_warm` 变 true 且 `own_actions` 开始涨，再认真做 ATTEST（需 `rh:`）或发 JOB。
4. 水龙头仍关着：把精力放在 Path B 文档/工具 + Kibble 有用功，而不是假 faucet。

## 相关

- `docs/KIBBLE-BOARD-WHEN-APIS-HANG.md` — board/cycle 超时
- `docs/KIBBLE-LINE-CHEATSHEET.md` — 行格式
- `tools/check_score_vs_tape.py` — 本页配套检查器
