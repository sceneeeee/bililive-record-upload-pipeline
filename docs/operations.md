# 运维与清理验证

在目标主机运行以下只读命令；不要将含路径、任务、账号信息的原始输出提交 Git：

```sh
systemctl status pipeline-upload-cleaner.service pipeline-recorder-monitor.timer --no-pager
journalctl -u pipeline-upload-cleaner.service -u pipeline-recorder-monitor.service --since '30 min ago' --no-pager
cd /opt/bililive-stack
docker compose config --quiet
docker exec bililive-api sha256sum /app/index-DQV9sVEn.cjs /app/index-ZJeYopVC.cjs
df -h video
```

核对哈希等于 versions.lock.json。清理 status.json 在 `/var/lib/pipeline-upload-cleaner/`：timestamp 应持续刷新，blocked 记录保留原因，errors 记录删除错误，totals 记录 deleted/absent 和释放块数。周期一般2秒；监控每5分钟检查，心跳超过90秒告警。告警写本地 journal/status，不外发，不自动修复。

验证一次自然上传：记录源路径和身份；上传期间文件存在；父投稿终态、对应 uploadStatus/rawUploadStatus 已 uploaded/error、FD 关闭后，源文件消失，台账出现 delete_intent→deleted（或原生已删除时 absent）。检查所有 `/proc/*/fd` 是否仍持有该 inode，确认磁盘块实际释放。不以文件消失或任务 completed 单项认定完整成功；查询稿件和分 P，审核结果独立验证。

成功路径默认删除；失败路径默认 blocked=final_failure_deletion_disabled。显式开启后仍须完成其余保护条件，不能用开关绕过 FD/身份检查。没有明确终态的文件、手动取消、未形成上传任务的小文件及未知文件继续保留。

| 症状 | 核对与处理 |
| --- | --- |
| FileClosed 后无上传 | Webhook、房间 open/noGlobal、20 MiB过滤、账号预设、上传时间范围及补丁哈希；不在生产伪造事件 |
| completed 但文件仍在 | 父子任务、对应回调、FD、身份、blocked/errors；等待真实状态，不强删 |
| 重启后仍 blocked | 持久记录是否含未终态任务/回调，API 失踪不能证明结束；人工核对，不改台账强行授权 |
| API/FD 扫描失败 | 网络、凭据、完整任务快照、root /proc 可见性；恢复检查能力，不忽略异常 |
| 已删除但空间未释放 | 查开放 inode 和流关闭修补；不能 truncate 或强关别人的 FD |
| 重名/回退 | 中文秒级模板仍可能同秒冲突；保留上游 CreateNew 保护 |
| socket hang up/TLS/EOF | 分别取证，不关闭 TLS、不无限重试；代码修补不保证消除网络问题 |

备份台账须用 SQLite backup API，或停止清理服务后连同 WAL/SHM 一致性保存。备份0700/0600，不上传工单。运行数据库、账号、录像、未知文件不是缓存；不要清空台账或按年龄删除。video 目录不可供不受信任用户写入。
