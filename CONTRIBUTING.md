# 贡献

先读 README、AGENTS.md 和 docs。请提供可复现问题、目标行为、最小修改与验证结果。涉及清理须解释身份、状态、重试、回调、FD、重启和取消边界；涉及调度须覆盖handled/raw并发。测试使用合成数据，不连接真实生产。

```sh
bash scripts/extract_upstream.sh
bash tests/run.sh
bash tests/validate_units.sh
git diff --check
git diff --cached --check
python3 scripts/scan_repository.py --staged
```

提交前运行 Gitleaks目录及完整历史扫描，人工审阅 git status、git ls-files、git diff --cached、所有配置与ignore。不得提交真实.env、凭据、录像、数据库/WAL、台账、备份、原始日志、temp_report.md或完整第三方bundle。不要把TypeScript源码按*.ts全部忽略。

新增代码以GPL-3.0-only贡献，保留上游版权和声明。未经兼容性验证不要升级上游，不为了重构改变已验证的核心流程。发布不包含生产部署授权。
