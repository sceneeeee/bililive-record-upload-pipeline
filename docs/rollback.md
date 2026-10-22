# 更新、发布与回滚

Git 发布不自动部署。先 `git pull --ff-only`，审阅目标提交和版本锁，在独立环境重建补丁、测试和扫描。上游升级必须重查镜像 digest、文件名、原始/输出 SHA、patch 上下文、API 任务字段、回调和 FD；禁止只改 tag 或把旧 bundle 挂到新版。

当前版本的 prepare_deployment 只接受仓库中的**基础 Compose**，用于首次修补/原版本回滚后再准备。它不是任意现有补丁版本的自动迁移器。已有修补部署升级须另外审阅迁移差异，保存旧镜像、Compose、stage/backup、脚本、units、账号配置和一致性台账，生成独立新 stage，不覆盖旧目录，不复用 approved/applied 标记。

每次部署均须确认下播、全任务终态、回调结束，超过最大合并窗口；API 重建会丢内存队列与稿件合并状态。先停清理器，再做一致性备份，审阅并执行目标主机生成的 guard。旧生产 guard/历史文档不能代替当前窗口和数据核对。

回滚当前 stage：

```sh
sudo env STACK_ROOT=/opt/bililive-stack bash scripts/rollback_api.sh --approved-window
```

包装器停用清理器和 API 窗口 timer；guard 再检查配置、Compose、文件哈希、直播和任务，恢复该 stage 备份中的基础 Compose，只重建 API。需要原始 digest 镜像仍可用，使用 --pull never。若检查拒绝，保留停用状态供人工复核，不删除 marker 或绕过检查。

API 启动失败会尝试恢复此前 Compose；后置哈希或受保护配置断言失败不保证自动回滚，须检查备份/evidence。回退维护脚本/units 时先备份当前文件，再恢复安装器的 maintenance-units-* 备份并 daemon-reload，安排服务重启。保留状态和台账，不删除录像。

**永久删除的录像不能由代码、配置或台账回滚恢复。** 成功不等于过审，最终失败删除意味着无法使用该源文件重传。启用该功能前自行保存所需的独立备份。

发布新版本：更新最小差异与锁→重建→tests/run.sh→Compose/systemd→Gitleaks目录及全部历史→审阅暂存文件/配置/ignore→正常commit/push。部署仓库通过 submodule 固定通过审查的准确提交，再独立安排部署，不跟随移动分支自动更新。
