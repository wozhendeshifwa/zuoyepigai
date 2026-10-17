# 作业批改

## Agent skills

### Issue tracker

issue 与规格都作为 GitHub issue 存放在 `wozhendeshifwa/zuoyepigai`，统一走 `gh` CLI（面板场景优先用 `deck_` 工具）。详见 `docs/agents/issue-tracker.md`。

### Triage labels

五个 triage 角色沿用默认标签串：`needs-triage`、`needs-info`、`ready-for-agent`、`ready-for-human`、`wontfix`。详见 `docs/agents/triage-labels.md`。

### Domain docs

single-context（仓库根目录一份 `GLOSSARY.md`，架构决定放 `docs/adr/`）。详见 `docs/agents/domain.md`。

## 跑这个程序

- 入口是 `python scripts/cx.py <子命令>`（`roster` / `export` / `collect` / `grade` / `review` / `emit` / `score` / `back` / `inspect` / `check`）；Windows 下用 `.\scripts\run.ps1 <子命令>`，它会先修控制台编码再挑可用的 python。
- 动学习通之前先跑 `.\scripts\run.ps1 check`，跑守卫与调分的单元测试。
- 学习通接口的坑（分页、附件判定、导入按行全量写、没有「恢复未交」）见 `docs/agents/xuexitong-api.md`。

## 交代分产物

- 导入文件只由 `scripts/cx.py emit` 生成：它带「文件行数必须等于提交人数」的守卫，并强制作业分落在 75–98。
- 改一个人的分用 `cx.py score`，不要用导入（学习通会拒收只含部分学生的表）。
- 判分默认单跑一次；成绩要落定之前用 `cx.py grade --samples 3`，同一份跑三次取多数，分歧题自动降为低把握进复核。
- 手工拼导入文件是上一次 87 个未交学生被写成 0 分的直接原因。
