---
name: independent-workspace
description: 工作区软件（tools/ scripts/ .claude/skills/）与 ai-berkshire 源独立，无需同步
metadata:
  type: project
---

对当前工作区（`F:\Financial_Investment_Analysis`）下 `tools/`、`scripts/`、`.claude/skills/`、`CLAUDE.md` 等所有文件的编辑、修改，**均不需要**与 `ai-berkshire/` 子目录下的源文件同步。

**为什么：**
- `ai-berkshire/` 是上游 AI Berkshire 代码库的独立副本，其 CLAUDE.md 和 AGENTS.md 是参考源，而非同步目标
- 工作区根目录下的 `tools/` 和 `scripts/` 是独立副本，对它们的修改不应反向同步到 `ai-berkshire/tools/` 和 `ai-berkshire/scripts/`
- `.claude/skills/` 下的本地 skill 文件是独立副本，不依赖 `sync-codex-skills.py` 同步

**如何应用：**
- 编辑 `tools/`、`scripts/`、`.claude/skills/` 下的文件时，只关心它们是否能正确工作，不需考虑与 `ai-berkshire/` 对应文件的一致性
- 如需参考 `ai-berkshire/` 下的源文件逻辑，直接照搬或改编即可，无需保持双向同步
- 运行 `scripts/sync-codex-skills.py` 会导致本地 skill 被上游覆盖——**不要运行此命令**