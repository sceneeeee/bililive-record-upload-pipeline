# 安装与部署

以下命令在自己的新目标主机执行。需要 Linux/amd64、Docker Compose、systemd、Python 3.10+、Node.js 22、GNU patch、Bash；Python 无第三方依赖。空间至少能容纳多份 5 GiB 分段，留出上传失败积压余量。已有运行栈须先备份，勿用示例覆盖真实配置。

## 构建与锁定

在仓库根目录运行 `bash scripts/extract_upstream.sh`。脚本从 versions.lock.json 的 API 镜像 digest 创建**不启动**的提取容器，退出时移除；不会修改运行容器。两份原始 bundle 先校验 SHA256，再以 `patch --fuzz=0` 应用，最后检查输出 SHA256。不匹配立即拒绝，完整 bundle 只写 ignored build/。

离线方式为 `python3 scripts/build_patches.py --upstream /path/to/upstream`。完成后运行 `bash tests/run.sh`。Compose 的三个镜像均锁定 digest（2.18.0 / 3.20.0），不依赖可变 tag。

## 配置录播和投稿

```sh
export STACK_ROOT=/opt/bililive-stack
sudo install -d -m 0750 "$STACK_ROOT" "$STACK_ROOT/data" "$STACK_ROOT/video" "$STACK_ROOT/recorder"
sudo install -m 0644 compose/compose.base.example.yaml "$STACK_ROOT/compose.yaml"
sudo install -m 0600 compose/.env.example "$STACK_ROOT/.env"
sudo install -m 0600 examples/recorder/config.example.json "$STACK_ROOT/recorder/config.json"
```

在主机本地生成并填写 .env 的四个认证变量。示例为空，Compose 会拒绝缺失值。不要将真实值放入 Git、聊天、命令参数或日志。示例的房间列表为空，**不会自动录制任何真实房间**。

通过录播姬 UI 新增自己有权录制的房间，先关闭 AutoRecord 完成配置；或按 configV3 schema 添加 rooms 元素：RoomId 与 AutoRecord 同其他选项一样为 `{ "HasValue": true, "Value": ... }`。字段参见 [示例说明](../examples/recorder/README.md)。全局/房间 CuttingMode=2、CuttingNumber=5120，Standard 引擎；房间已有覆盖也应核对。中文秒级模板保留上游重名保护，同秒重连仍可能回退默认路径。

在 `$STACK_ROOT` 下运行：

```sh
sudo docker compose config --quiet
sudo docker compose up -d
```

三管理端口仅绑定 127.0.0.1，使用自己配置的受控隧道或反向代理访问。录播姬 Webhook 使用 Docker 内网 `http://bililive-api:18010/webhook/bililiverecorder`，视频路径映射保持示例一致。

在 tools UI 本地登录自己的 B 站账号，配置投稿 uid、预设、房间 open/noGlobal、生效配置。推荐起点：recoderFolder=/app/video、webhook.open=true、minSize=20 MiB、convert2Mp4=false、flvRepair=false、afterUploadDeletAction=delete；不启用小文件直接删除。标题、分区、隐私和合并窗口由部署者选择，检查房间覆盖实际生效值。上传可配置 retryTimes=10、retryDelay=7000 ms、concurrency=3、useUploadPartPersistence=true；不关闭 TLS 校验。tools 内置录制器不启用，录制由录播姬承担。

`afterUploadDeletAction=delete` 保留原生成功删除，不等待审核；不保证最终失败删除。下面独立清理器提供持久化安全重试与可选失败删除。上传完成不等于稿件通过审核或远端永久可用，按自己的备份需求决定是否启用成功删除。

## 准备与安装补丁

保持 AutoRecord 暂停且无真实任务，完成全部配置后：

```sh
sudo env STACK_ROOT="$STACK_ROOT" python3 scripts/prepare_deployment.py --prepare
```

准备器检查已审阅的基础 Compose、构建 SHA、必需本地配置；创建0700备份与 patches/uploader-3.20.0 stage，拒绝覆盖已有 stage，不重启服务。生成的 guard 固定本次 root/stage/backup；不含认证值。可选 PATCH_STAGE 必须在 root/patches 下，每次维护使用新目录并先人工审阅。

确认下播、任务全终态、回调完成、超过最大合并窗口加一分钟，并备份当前业务数据后明确执行：

```sh
sudo python3 "$STACK_ROOT/patches/uploader-3.20.0/apply.py" --approved-window
sudo env STACK_ROOT="$STACK_ROOT" bash scripts/install_maintenance.sh --install
```

guard 只重建 API（--no-deps --pull never），核对源/输出 SHA、Compose 和受保护配置、录播姬/Web PID。API 重建会丢失内存队列及合并关系；不能凭旧任务 JSON 保证恢复。不能在真实录制/上传期间执行。安装器备份已有脚本/units，安装清理服务和监控 timer；不启用可选的 API 窗口 timer。已有服务不会因覆盖脚本自动重启，更新时须另行安排窗口。

## 清理策略与路径

`/etc/bililive-pipeline/maintenance.env` 是维护服务配置（与业务 .env 分开），默认：

```ini
STACK_ROOT=/opt/bililive-stack
CLEANER_POLICY_ARGS=
```

此时只清理最终成功；最终失败保留。显式接受不可恢复风险后，设：

```ini
CLEANER_POLICY_ARGS=--delete-final-failure
```

然后在自己的维护窗口重启 `pipeline-upload-cleaner.service`。命令行直接运行同样需要 `--apply` 才删除，`--delete-final-failure` 只控制失败资格。默认 state=/var/lib/pipeline-upload-cleaner，可用 CLEANER_STATE 调整；监控用 MONITOR_STATE 指定完整状态文件名。自定义 state 时还需相应调整 unit 的 StateDirectory/ReadWritePaths。安装器渲染 STACK_ROOT/PATCH_STAGE 的 systemd 路径；环境文件中已有配置会保留，部署者须核对它和 unit 一致。

API 默认回环2356/18010，容器名、内部视频路径沿用 Compose；改变这些布局前须同步审阅所有 guard/监控/清理器及测试，不能只改一个端口变量。

最后核对清理/监控 active、bundle 哈希与 lock 一致、Webhook/投稿预设正确，再启用自己的房间 AutoRecord；按运维文档观察自然直播。
