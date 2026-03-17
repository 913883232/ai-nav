# AI NAV // 智能工具导航站

## 项目结构

```
ai-nav/
├── index.html                      # 前端页面（纯静态）
├── data.json                       # 工具数据（JSON 格式）
├── update.py                       # 爬虫更新脚本
├── requirements.txt                # Python 依赖
├── pending.json                    # 待审核的新工具（自动生成）
└── .github/
    └── workflows/
        └── daily-update.yml        # GitHub Actions 定时任务
```

---

## 一、部署到 GitHub Pages（推荐）

### 1. 创建 GitHub 仓库

```bash
cd ai-nav
git init
git add .
git commit -m "init: AI NAV 导航站"
git branch -M main
git remote add origin https://github.com/你的用户名/ai-nav.git
git push -u origin main
```

### 2. 开启 GitHub Pages

1. 进入仓库 → **Settings** → **Pages**
2. Source 选择 **GitHub Actions**
3. 保存后等待首次部署完成

### 3. 配置搜索 API（可选但推荐）

1. 进入仓库 → **Settings** → **Secrets and variables** → **Actions**
2. 添加 Secret: `SERP_API_KEY`（从 [serpapi.com](https://serpapi.com) 获取免费 key）
3. 不配置也能运行（会使用 DuckDuckGo 免费搜索）

### 4. 访问

部署完成后访问: `https://你的用户名.github.io/ai-nav/`

---

## 二、自动更新机制

### 运行流程

```
每天 08:00 (北京时间)
    ↓
GitHub Actions 触发 daily-update.yml
    ↓
运行 update.py 爬虫脚本
    ↓
搜索各分类最新 AI 工具
    ↓
验证现有工具链接是否有效（抽检 10%）
    ↓
移除死链工具
    ↓
新发现的工具写入 pending.json（待审核）
    ↓
更新 data.json 的 lastUpdated 时间戳
    ↓
自动 commit + push
    ↓
触发 GitHub Pages 重新部署
```

### 手动触发更新

1. 进入仓库 → **Actions** → **Daily AI NAV Update**
2. 点击 **Run workflow** → **Run workflow**

### 手动审核新工具

```bash
# 下载最新代码
git pull

# 交互式审核 pending.json 中的候选工具
python update.py approve

# 推送更新
git add data.json
git commit -m "chore: approve new tools"
git push
```

---

## 三、如何修改

### 修改现有工具信息

直接编辑 `data.json`，每个工具的字段:

```json
{
  "name": "工具名称",
  "cat": "分类ID",
  "url": "https://工具网址",
  "desc": "中文描述，控制在 40 字以内",
  "tag": "free | freemium | paid"
}
```

分类 ID 对照:
| ID | 分类名 |
|---|---|
| `chat` | AI 聊天 |
| `image` | 文生图 |
| `video` | 文生视频 |
| `coding` | AI 编程 |
| `search` | AI 搜索 |
| `writing` | AI 写作 |
| `audio` | AI 音频 |
| `design` | AI 设计 |
| `editing` | 图像编辑 |
| `free` | 免费工具 |

### 手动添加新工具

在 `data.json` 的 `tools` 数组末尾添加:

```json
{
  "name": "新工具",
  "cat": "chat",
  "url": "https://example.com",
  "desc": "工具描述",
  "tag": "freemium"
}
```

### 手动删除工具

在 `data.json` 中找到对应条目，删除整个 `{...}` 块。

### 修改分类

编辑 `index.html` 中的 `CATEGORIES` 数组:

```js
const CATEGORIES = [
  { id: 'new_cat', name: '新分类', icon: '&#9733;' },
  // ...
];
```

### 修改更新频率

编辑 `.github/workflows/daily-update.yml` 中的 cron 表达式:

```yaml
schedule:
  - cron: '0 0 * * *'    # 每天一次
  - cron: '0 */12 * * *' # 每 12 小时一次
  - cron: '0 0 * * 1'    # 每周一一次
```

### 修改搜索关键词

编辑 `update.py` 中的 `SEARCH_QUERIES` 字典。

### 修改页面样式

编辑 `index.html` 中的 `<style>` 标签，CSS 变量在 `:root` 中定义。

---

## 四、备选部署方案

### Vercel 部署

```bash
npm i -g vercel
cd ai-nav
vercel
```
然后在 Vercel 仪表板添加 Cron Job 或使用 GitHub Actions。

### Cloudflare Pages 部署

1. 连接 GitHub 仓库到 Cloudflare Pages
2. Build command 留空
3. Output directory 设为 `/`
4. Cron 任务仍通过 GitHub Actions 触发

### Netlify 部署

1. 连接 GitHub 仓库
2. Build command 留空
3. Publish directory 设为 `/`

### 自有服务器 (crontab)

```bash
# 安装依赖
pip install -r requirements.txt

# 编辑 crontab
crontab -e

# 添加定时任务（每天凌晨 2 点执行）
0 2 * * * cd /path/to/ai-nav && python update.py >> /var/log/ainav-update.log 2>&1
```

---

## 五、注意事项

1. **SerpAPI 免费额度**: 每月 100 次搜索，足够每日更新
2. **DuckDuckGo 限制**: 免费但可能被限速，建议配合 SerpAPI 使用
3. **新工具审核**: 爬虫发现的新工具不会自动上线，需要执行 `python update.py approve` 人工审核
4. **数据安全**: data.json 是唯一数据源，建议定期备份
5. **自定义域名**: 在 GitHub Pages 设置中绑定自定义域名
