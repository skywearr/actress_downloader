# Actress Downloader MVP

这是一个成人作品目录元数据 MVP，不是下载器成品。

当前仓库已经能完成一条基础元数据流水线：

1. 输入女优名称或别名
2. 解析标准身份
3. 发现关联作品编号
4. 为作品生成结构化标签
5. 将结果写入 PostgreSQL
6. 为每个作品导出一个本地 sidecar 元数据文件

当前还没有实现：

- 真正的下载工作流
- 种子 / 磁力 / 迅雷集成
- 下载任务管理
- 真实在线全站抓取

## 当前架构

核心目录：

```text
src/actress_downloader/
  connectors/
  cli.py
  config.py
  domain.py
  graph.py
  llm.py
  pipeline.py
  sidecar.py
  storage.py
  tagging.py
  utils.py
sql/
  init_schema.sql
scripts/
  init_db.py
examples/
  demo_catalog.json
tests/
```

流水线节点：

1. `normalize_input`
2. `resolve_identity`
3. `discover_works`
4. `tag_works`
5. `persist_works`
6. `export_sidecars`

项目默认优先使用 LangGraph；如果运行环境里没有 LangGraph，会退回线性 pipeline。

## 配置原则

当前仓库使用下面这套配置规则：

- 非敏感配置放在 [config/settings.toml](/C:/Users/94611/PyCharmMiscProject/actress_downloader/config/settings.toml)
- 敏感配置优先从系统环境变量读取
- 如果系统环境变量里没有，再从项目根目录 `.env` 读取
- 如果两边都没有，就直接报错

当前被视为敏感配置的字段是：

- PostgreSQL 用户名：`PGUSER`
- PostgreSQL 密码：`PGPASSWORD`
- LLM API key：
  - xAI 用 `XAI_API_KEY`
  - GLM 用 `GLM_API_KEY` 或 `ZHIPUAI_API_KEY`
  - 通用回退变量是 `LLM_API_KEY`

`.env` 已经加入 `.gitignore`，不会被提交到 Git 仓库。

## 第一次配置

### 1. 安装依赖

```bash
pip install -e .
```

### 2. 检查非敏感配置

[config/settings.toml](/C:/Users/94611/PyCharmMiscProject/actress_downloader/config/settings.toml) 当前保留的是非敏感项，例如：

```toml
[postgres]
host = "127.0.0.1"
port = 5432
sslmode = "prefer"

[llm]
provider = "xai"
model = "grok-4.20"
base_url = "https://api.x.ai/v1/responses"
temperature = 0.2
timeout_seconds = 60.0
enabled = true

[paths]
seed_file = "examples/demo_catalog.json"
library_root = "library"
schema_file = "sql/init_schema.sql"
```

### 3. 设置敏感信息

你有两种方式。

方式 A：用系统环境变量。

PowerShell 示例：

```powershell
$env:PGUSER="postgres"
$env:PGPASSWORD="replace-with-your-password"
$env:XAI_API_KEY="replace-with-your-xai-api-key"
```

方式 B：在项目根目录创建 `.env`。

示例：

```dotenv
PGUSER=postgres
PGPASSWORD=replace-with-your-password
XAI_API_KEY=replace-with-your-xai-api-key
```

当前仓库已经根据你原来的本地配置生成了一份 `.env`。这个文件默认不会被 Git 跟踪。

### 4. 初始化数据库

```bash
python scripts/init_db.py
```

默认数据库名固定为 `actress_downloader`。

如果当前 PostgreSQL 账号有 `CREATEDB` 权限，脚本会尝试自动创建数据库并初始化 schema。

如果没有建库权限，请手动创建数据库后再运行；如果你必须使用别的数据库名，可以这样指定：

```bash
python scripts/init_db.py --database-name my_manual_db
```

## 运行示例

```bash
python -m actress_downloader.cli "鬼头桃菜"
```

默认会：

- 读取 [examples/demo_catalog.json](/C:/Users/94611/PyCharmMiscProject/actress_downloader/examples/demo_catalog.json)
- 初始化并写入 PostgreSQL
- 在 `library/<work_code>/metadata.json` 导出 sidecar

## 已实现能力

- PostgreSQL schema 初始化
- 自动建库尝试
- 作品 / 演员 / 别名 / 标签 / 原始记录的 upsert
- 多演员作品支持
- sidecar 导出
- LangGraph 编排和线性 fallback
- 成人目录场景下的 LLM prompt 请求构造

## 当前限制

- 当前 connector 仍然是离线 seed connector
- 还没有真实在线 metadata source
- 还没有增量同步
- 还没有人工复核闭环
- README 之外的部分文档和示例数据仍有编码清理工作待做

## 下一步最值得做的事

1. 接入真实在线 connector，替代 `SeedCatalogConnector`
2. 继续清理仓库中的编码乱码
3. 做一条真实数据库和真实 xAI Responses API 的 smoke test
