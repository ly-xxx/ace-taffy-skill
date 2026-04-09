# 来源与采集路线

## 一手来源

### 微博

- 官方主页：`https://weibo.com/acetaffy`
- 首选路线：`m.weibo.cn` 官方移动站访客态抓取
- 本地采集脚本：`tools/collect_weibo.py`

当前优先策略：

- 先通过 `visitor.passport.weibo.cn` 建立访客 cookie
- 再调用 `m.weibo.cn/api/container/getIndex`
- 评论优先用 `m.weibo.cn/comments/hotflow`

推荐抓取：

- profile
- feeds
- comments
- 置顶微博和近期原创微博

### Bilibili

- 空间：`https://space.bilibili.com/1265680561`
- 直播间：`https://live.bilibili.com/22603245`
- 首选元数据脚本：`tools/collect_bilibili.py`
- 官方稳定接口：
  - `m.bilibili.com/space/{mid}` 空间初始态
  - `x/web-interface/view/detail` 视频详情
  - `x/v2/reply/main` 热门评论
  - `live_user/v1/Master/info` / `room/v1/Room/get_info`
- 可补充检索：
  - `bilibili-mcp-js`
  - `bilibili-mcp-server`
  - `RSSHub` B 站用户视频 / 动态路由

推荐抓取：

- UP 主资料
- 视频列表
- 视频详情
- 官方动态
- 直播间信息

## 工具路线

### 微博

- 官方移动站接口：
  - 通过访客态可稳定拿到用户主页、微博流、热门评论
  - 当前环境比 `mcp-server-weibo` 更稳定

- 仓库：`https://github.com/qinyuanpei/mcp-server-weibo`
  - 仍可作为备用路线
  - 当前环境下代理握手不稳定，不再作为主路线

### Bilibili

- 仓库：`https://github.com/34892002/bilibili-mcp-js`
  - 更偏搜索、视频详情、UP 主信息
  - 最近活跃度更好

- 仓库：`https://github.com/huccihuang/bilibili-mcp-server`
  - 能补充精确搜索与弹幕
  - 适合配合使用

## 数据优先级

### P0

- 微博原创正文
- B 站官方视频标题/简介/评论
- B 站官方视频转录

### P1

- B 站官方动态
- 官方直播间标题/公告
- 官方视频评论区高赞互动

### P2

- 授权切片
- 粉丝评论
- RSS 订阅式增量同步

## 采集后的建议落桶

- `sources/raw/weibo/`
- `sources/raw/bilibili/`
- `sources/transcripts/`
- `sources/processed/corpus/`

## 这轮实际计数

- 微博公开正文：`658` 条
- 微博转发文案：`102` 条
- Bilibili 视频详情：`180` 条
- Bilibili 空间动态：`149` 条
- 直播间公开信息：`1` 条
- 当前公开 source corpus：`1090` 条

## 恢复说明

- 使用当前仓库的 `tools/collect_bilibili_public.py` 或 `tools/source_refresh_public.py` 刷新时，会写 `sources/raw/bilibili/_collector_state.json`
- 即使中途断开，也可以保留中间产物后继续续跑
