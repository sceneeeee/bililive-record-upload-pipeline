# 可复现补丁

目标为 biliLive-tools 3.20.0 Linux/amd64 发布 bundle。镜像、原始和输出 SHA256 在 versions.lock.json；项目脚本/units/Compose 的发布哈希在 release-files.sha256.json。完整上游 bundle 不提交。

- upload-streams-and-path.patch：每次尝试 finally 关闭源流/限速流；任务携带精确路径、字节数、dev/ino/size。保留上传主体与重试。
- immediate-upload.patch：后处理结束立即安排上传；每 live 类型队列防止 handled/raw 并发丢失。保留周期扫描，不等待上传才继续录制。

构建使用 GNU patch --batch --forward --fuzz=0，输入和输出都须精确匹配 SHA256；不接受未知版本，不覆盖不同的已有输出。更新文件时须审阅实际差异后更新发布哈希，不可只改哈希让测试通过。

上游代码版权与许可证保持原状，详见 THIRD_PARTY_NOTICES.md。补丁对应的完整源代码由上游版本链接提供。本项目仅分发差异，不将第三方依赖重新许可为本项目原创代码。
