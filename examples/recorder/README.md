# 录播姬配置示例

config.example.json 对应 v2.18.0 configV3，rooms 默认空数组，避免误录真实房间。不要覆盖现有配置。先备份，用 UI 添加房间最稳妥；手动新增时复制以下结构并将 RoomId 的 Value 替换为自己的房间号：

```json
{"RoomId":{"HasValue":true,"Value":0},"AutoRecord":{"HasValue":true,"Value":false},"CuttingMode":{"HasValue":true,"Value":2},"CuttingNumber":{"HasValue":true,"Value":5120}}
```

0 是占位符，不能用于实际录制。完成 tools 房间和投稿预设后才启用 AutoRecord。全局 WebHookUrlsV2 指向 Compose 内网 API，修改网络名/端口时同步调整。每个选项的 HasValue 表示显式覆盖；房间覆盖可能使全局分段设置不生效。

模板使用本地中文秒级时间和分段序号；同秒重连不保证唯一，上游原生 CreateNew/回退保护保留。不要把真实账号、Cookie、房间清单或配置快照提交到示例。
