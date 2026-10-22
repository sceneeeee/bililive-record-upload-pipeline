# 维护约定

- 先读 README、docs/ 和本文件；保持 BililiveRecorder 2.18.0 / biliLive-tools 3.20.0 锁定，未经兼容性验证不升级。
- 这是通用开源仓库，不含个人部署信息。运行凭据、真实 .env、录像、数据库/WAL、台账、备份、原始日志、temp_report.md 不得进入文件或 Git 历史。
- 默认只删除成功终态；最终失败删除必须通过 --delete-final-failure 显式开启。任何清理修改不得绕过身份、任务、父子关系、回调、FD、API 完整性与重启保护。
- 保持核心流程最小修改，录制上传并行；handled/raw 不可错误合并。不得按年龄或“API 无任务”删录像。
- 修改后运行 bash tests/run.sh；发布前运行构建与 SHA256 校验、Compose/systemd 校验、暂存区及历史敏感扫描，人工审阅 git diff --cached、git ls-files、所有配置与 .gitignore。
- CI 仅使用合成数据及上游锁定镜像，不连接任何生产主机。Git 发布与生产部署是独立操作；没有明确生产授权不得部署、重启或删除录像。
- 修改受 release-files.sha256.json 覆盖的文件时审阅差异后更新哈希，不得为通过测试降低保护。保留上游许可证和版权，禁止 force push。
