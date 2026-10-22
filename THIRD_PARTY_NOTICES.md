# 第三方声明

本项目新增集成、维护代码按GPL-3.0-only发布；以下第三方项目保留其原始版权和许可，本项目不主张其版权或官方关联。

| 项目 | 固定版本与来源 | 版权/许可 |
| --- | --- | --- |
| BililiveRecorder | [v2.18.0源码](https://github.com/BililiveRecorder/BililiveRecorder/tree/v2.18.0) | Copyright © 2018–2025 Genteure；GNU GPL v3，原文见licenses/recorder-GPL-3.0.txt及上游声明 |
| biliLive-tools | [3.20.0源码](https://github.com/renmu123/biliLive-tools/tree/3.20.0) | renmu123及项目贡献者；GNU GPL v3，原文见licenses/tools-GPL-3.0.txt及上游逐文件声明 |

两份patch是针对biliLive-tools发布bundle的局部修改；版权归属和包内依赖注释保持原状。构建输入固定digest/SHA，未删除上游bundle内许可证/版权注释，不在仓库分发完整bundle。对应源代码可从以上固定版本链接取得，镜像依其发布者条款使用。

上游bundle内还包含不同许可的依赖，依赖的许可证和NOTICE不被本项目LICENSE替代；分发自行构建的镜像或完整程序时须保留其全部声明并满足相应源代码提供义务。构建与CI使用的GNU patch、Python、Node.js、Docker Compose、Gitleaks及GitHub Actions各有其许可，不作为本项目原创代码分发。
