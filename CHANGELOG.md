# Changelog

本项目记录集成层、补丁和维护工具的变化。仓库版本号独立于上游 BililiveRecorder 2.18.0 与 biliLive-tools 3.20.0。

本文件遵循 Keep a Changelog 的组织方式；正式发布时将日期、标签和用户可见变化从 Unreleased 移入对应版本。

## [Unreleased]

### Documentation

- 补充中英文项目介绍、功能边界和生产证据说明。
- 明确历史生产祖先版本与当前公开调度、清理实现之间的差异。
- 补充预发布和正式发布检查清单。

### Maintenance

- 保持上游版本、镜像 digest 和 bundle SHA256 锁定。
- 不将生产部署、凭据、录像、日志、数据库或审计交接文件纳入公开仓库。

## Initial public snapshot

当前公开仓库最初的可见提交为 `199486d9aaa1bcce48f90205535202d2f7580237`。该提交已包含锁定构建、上传流与调度补丁、持久化清理器、systemd/Compose 示例、部署/运维/回滚文档和离线测试。

尚未创建历史 Release 标签；不会为已有代码虚构多个版本或发布日期。
