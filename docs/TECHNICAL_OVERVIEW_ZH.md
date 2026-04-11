# 中文技术概览

最后更新：2026-04-11

## 项目定位

这个仓库当前实现的是一个“女优作品元数据整理 MVP”，不是下载器成品。

它当前能完成的事情是：

1. 输入一个女优名称或别名
2. 解析成标准化身份
3. 找出关联作品编号
4. 为作品生成结构化标签
5. 将结果写入 PostgreSQL
6. 为每个作品导出一个本地 sidecar 元数据文件

当前明确还没有做的内容：

- 下载工作流
- 种子 / 磁力 / 迅雷集成
- 下载任务管理
- 真正的在线全站抓取

## 当前实现范围

### 1. 命令行入口

入口文件是 [cli.py](/C:/Users/94611/PyCharmMiscProject/actress_downloader/src/actress_downloader/cli.py)。

CLI 当前支持：

- 输入女优名或别名
- 指定配置文件路径
- 指定离线 seed 数据文件
- 指定数据库名覆盖
- 指定 sidecar 输出目录

CLI 会输出解析到的演员、别名、模型配置、发现的作品和标签数量。

### 2. 流水线编排

流水线实现位于：

- [pipeline.py](/C:/Users/94611/PyCharmMiscProject/actress_downloader/src/actress_downloader/pipeline.py)
- [graph.py](/C:/Users/94611/PyCharmMiscProject/actress_downloader/src/actress_downloader/graph.py)

当前有两套执行路径：

- 默认优先使用 LangGraph
- 如果运行环境没有 LangGraph，则退回线性 pipeline

图中的节点已经实现为：

1. `normalize_input`
2. `resolve_identity`
3. `discover_works`
4. `tag_works`
5. `persist_works`
6. `export_sidecars`

这说明项目的编排骨架已经成型，不是只有一个脚本把逻辑全堆在一起。

### 3. 身份解析与作品发现

当前连接器实现位于 [seed.py](/C:/Users/94611/PyCharmMiscProject/actress_downloader/src/actress_downloader/connectors/seed.py)，它读取 [examples/demo_catalog.json](/C:/Users/94611/PyCharmMiscProject/actress_downloader/examples/demo_catalog.json)。

现阶段已经具备：

- 别名匹配
- 模糊匹配
- 同一作品多个演员
- 基于演员身份回查作品

但这里的关键限制也很明确：

- 这是离线 seed connector，不是真实网络数据源
- 没有在线别名发现
- 没有真实站点抓取

所以它更像“产品原型用的数据适配层”，而不是最终 connector。

### 4. 数据库存储

数据库相关实现位于：

- [sql/init_schema.sql](/C:/Users/94611/PyCharmMiscProject/actress_downloader/sql/init_schema.sql)
- [storage.py](/C:/Users/94611/PyCharmMiscProject/actress_downloader/src/actress_downloader/storage.py)
- [init_db.py](/C:/Users/94611/PyCharmMiscProject/actress_downloader/scripts/init_db.py)

当前 schema 已经覆盖：

- `performers`
- `performer_aliases`
- `works`
- `work_performers`
- `tags`
- `work_tags`
- `source_records`

这套设计已经支持：

- 稳定演员身份
- 历史别名
- 多演员作品
- 标签归一化
- 原始 source payload 留档

从工程角度看，这部分已经超过“仅演示用表结构”的阶段，具备继续向真实数据源扩展的价值。

### 5. 标签系统

标签逻辑位于：

- [tagging.py](/C:/Users/94611/PyCharmMiscProject/actress_downloader/src/actress_downloader/tagging.py)
- [llm.py](/C:/Users/94611/PyCharmMiscProject/actress_downloader/src/actress_downloader/llm.py)

当前标签分两层：

- 规则标签：稳定结构化标签，比如 `studio:*`、`series:*`、`year:*`、`performer-group:*`
- LLM 补充标签：用于在有限候选范围内补充更中性的 catalog 标签

这说明项目当前的 LLM 用法不是“全靠模型猜标签”，而是“规则优先，模型补充”的保守设计。

### 6. Sidecar 导出

导出逻辑位于 [sidecar.py](/C:/Users/94611/PyCharmMiscProject/actress_downloader/src/actress_downloader/sidecar.py)。

当前每个作品会导出到：

- `library/<work_code>/metadata.json`

sidecar 中包含：

- 作品编号
- 标题
- 发行日期
- 厂牌
- 系列
- 全部演员
- 归一化标签
- 原始标签
- 来源信息
- 简介
- 额外字段

现有目录 [library](/C:/Users/94611/PyCharmMiscProject/actress_downloader/library) 里已经能看到示例输出，说明这条链路是实际落地的。

## 目前做到什么程度

如果按“元数据整理 MVP”来评估，这个仓库已经完成了一个可运行的第一阶段骨架：

- 有配置加载
- 有 CLI
- 有流程编排
- 有数据模型
- 有 PostgreSQL 落库
- 有 sidecar 导出
- 有基础测试

如果按“最终下载器产品”来评估，它还远没有进入完整可用阶段：

- 没有真实在线 connector
- 没有下载能力
- 没有任务系统
- 没有增量同步
- 没有冲突合并
- 没有人工复核闭环

因此更准确的判断是：

- 这是一个“可运行的元数据 MVP”
- 不是一个“可投入使用的下载器”

## 当前真实状态判断

结合代码、文档和本地验证，当前状态可以概括为：

### 已经比较稳的部分

- PostgreSQL schema 和 upsert 设计
- 多演员作品支持
- sidecar 导出
- LangGraph + 线性 fallback 双路径
- 配置加载和 provider 区分

### 还停留在演示阶段的部分

- 数据源连接器
- 在线别名发现
- 在线作品发现
- 手工审核流程

### 有明显维护问题的部分

- README 存在编码污染，当前可读性很差
- 示例数据和部分测试文本也存在 mojibake
- 配置文件里当前包含明文数据库密码和 API key，不适合继续保留在仓库里
- 文档宣称 LLM 标签策略是合规中性，但代码一度发生过 prompt 漂移，需要持续保证文档和实现一致

## 当前测试与验证

当前仓库已有这些测试文件：

- [test_seed_connector.py](/C:/Users/94611/PyCharmMiscProject/actress_downloader/tests/test_seed_connector.py)
- [test_sidecar.py](/C:/Users/94611/PyCharmMiscProject/actress_downloader/tests/test_sidecar.py)
- [test_config.py](/C:/Users/94611/PyCharmMiscProject/actress_downloader/tests/test_config.py)
- [test_tagging.py](/C:/Users/94611/PyCharmMiscProject/actress_downloader/tests/test_tagging.py)
- [test_llm_prompt.py](/C:/Users/94611/PyCharmMiscProject/actress_downloader/tests/test_llm_prompt.py)

这些测试当前更偏向：

- 配置逻辑验证
- 种子连接器行为验证
- sidecar 导出结构验证
- tagger 的降级行为验证
- LLM prompt 形状和安全上下文验证

它们能证明项目“骨架是通的”，但还不足以证明：

- 真实网络 connector 可用
- 真库写入 smoke test 稳定
- 真实 xAI Responses API 线上链路可靠

## 建议的下一批优先工作

结合当前代码状态，最值得优先推进的是：

1. 保证 LLM 标签逻辑继续维持合规中性，并让测试与实现保持一致
2. 清理 README、示例数据和测试里的编码问题，恢复仓库可读性
3. 移除仓库中的明文凭据，并改成环境变量或本地私有配置覆盖
4. 用真实在线 connector 取代 seed connector
5. 补一条真实数据库和真实 LLM API 的 smoke test

## 一句话结论

这个仓库已经有一套能跑通的“元数据采集与整理 MVP”骨架，但距离真正的“下载器产品”还差真实数据源、交互复核、线上 smoke test 和完整下载工作流。
