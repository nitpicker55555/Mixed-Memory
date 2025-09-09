# AgenticSearch - 知识图谱问答系统

> 🚀 **端到端的知识图谱问答解决方案**  
> 从书籍文本到智能问答，完整的AI驱动流程

## 📁 项目结构

```
AgenticSearch/
├── src/                                    # 源代码
│   ├── graph_generation/                   # 📊 图谱生成模块
│   │   ├── neo4j_book2graph_improved.py    # 书籍转知识图谱 ⭐
│   │   ├── neo4j_book2graph_chapter_by_chapter_fixed.py # 按章节处理 🆕 ⭐
│   │   ├── create_node_embeddings.py       # 节点嵌入生成 ⭐
│   │   └── database_preparation.py         # 数据库准备工具 ⭐
│   ├── question_answering/                 # 🤖 问答系统模块
│   │   ├── run_agentic_batch.py           # 批处理脚本 (主要入口) ⭐
│   │   ├── agentic_qa_interface.py        # QA接口 ⭐
│   │   ├── agentic_search_engine.py       # 核心搜索引擎 ⭐
│   │   ├── enhanced_agentic_engine.py     # 增强搜索引擎 (可选)
│   │   ├── entity_linker.py               # 实体链接器 (可选)
│   │   ├── multi_candidate_scorer.py      # 多候选评分器 (可选)
│   │   ├── dsl_compiler.py                # DSL编译器 (可选)
│   │   └── query_dsl.py                   # 查询DSL (可选)
│   └── default_config.json                # 配置文件
├── data/                                   # 数据文件
│   ├── book.json                          # 源书籍数据 (51KB) ⭐
│   └── questions_new_book.json            # 问题数据集 (438题) ⭐
├── cache/                                  # 缓存文件
│   ├── embedding_test9.json               # 节点嵌入缓存 (4.9MB) ⭐
│   └── propertykey_test9.json             # 属性键缓存 ⭐
├── results/                               # 结果输出
└── README.md                              # 本文件
```

## 🎯 核心功能

### 1. 📊 图谱生成 (Graph Generation)
- **书籍解析**: 将JSON格式的书籍内容转换为结构化知识图谱
- **按章节处理** 🆕: 逐章解析并实时更新数据库，避免数据覆盖
- **实体抽取**: 使用GPT-4o提取事件、人物、地点等实体
- **关系建立**: 创建实体间的语义关系
- **嵌入生成**: 为所有节点生成768维向量嵌入

### 2. 🤖 智能问答 (Question Answering)
- **自然语言查询**: 接受自然语言问题输入
- **动态查询生成**: 基于问题内容动态生成Cypher查询
- **迭代搜索**: OTAR循环 (观察-思考-行动-反思)
- **结果评估**: 智能评估答案质量和置信度

## 🚀 快速开始

### 环境设置

1. **激活环境**
   ```bash
   conda activate cv3
   ```

2. **配置环境变量**
   ```bash
   # 复制环境变量模板
   cp src/env_example.txt .env
   
   # 编辑 .env 文件
   NEO4J_URI=bolt://localhost:7687
   NEO4J_USER=neo4j
   NEO4J_PASSWORD=your_password
   NEO4J_DATABASE=test10  # 使用最新的test10数据库
   OPENAI_API_KEY=your_api_key
   ```

3. **启动Neo4j数据库**
   ```bash
   neo4j start
   ```

### 使用方法

#### 步骤1: 生成知识图谱 (首次使用)

**方法1: 按章节处理 (推荐)** 🆕
```bash
# 按章节逐步生成图谱，实时保存，数据更完整
python src/graph_generation/neo4j_book2graph_chapter_by_chapter_fixed.py
```

**方法2: 整体处理 (传统)**
```bash
# 一次性处理整本书籍
python src/graph_generation/neo4j_book2graph_improved.py

# 生成节点嵌入
python src/graph_generation/create_node_embeddings.py
```

#### 步骤2: 运行问答系统

```bash
# 运行单个问题测试
python src/question_answering/run_agentic_batch.py \
    --questions data/questions_new_book.json \
    --range 1 \
    --output results/

# 运行问题1-5
python src/question_answering/run_agentic_batch.py \
    --questions data/questions_new_book.json \
    --range 1-5 \
    --output results/

# 运行问题1-10
python src/question_answering/run_agentic_batch.py \
    --questions data/questions_new_book.json \
    --range 1-10 \
    --output results/

# 运行自定义范围
python src/question_answering/run_agentic_batch.py \
    --questions data/questions_new_book.json \
    --range 1,5,10-15 \
    --output results/
```

## 📊 系统架构

### 核心流程
```
书籍文本 → GPT解析 → Neo4j图谱 → 嵌入生成 → 问答系统
   ↓           ↓         ↓         ↓         ↓
book.json → 实体抽取 → test9数据库 → 向量缓存 → 智能回答
```

### 问答流程
```
自然语言问题 → 策略选择 → Cypher生成 → 数据库查询 → 结果评估 → 最终答案
      ↓            ↓         ↓          ↓         ↓        ↓
   "问题文本"   → 实体识别 → 动态查询 → Neo4j执行 → 置信度评分 → JSON输出
```

## 🔧 配置说明

### 数据库配置
- **数据库**: Neo4j test10 (最新) / test9 (传统)
- **节点类型**: Event (事件), Person (人物), Location (地点)
- **关系类型**: PARTICIPATED_IN, OCCURRED_AT
- **数据规模**:
  - **按章节处理** 🆕: 106个节点, 99个关系 (test10)
  - **整体处理**: 114个节点, 多种关系 (test9)

### 缓存系统
- **嵌入缓存**: `cache/embedding_test10.json` / `cache/embedding_test9.json` (4.9MB)
- **属性缓存**: `cache/propertykey_test10.json` / `cache/propertykey_test9.json` (448B)
- **自动加载**: 系统启动时自动检测和加载缓存
- **按数据库自动切换**: 根据环境变量 `NEO4J_DATABASE` 选择对应缓存

### 问题数据集
- **文件**: `data/questions_new_book.json`
- **总题数**: 438题
- **格式**: JSON数组，包含问题文本和期望答案

## 🔄 按章节处理功能 🆕

### 核心优势
- **✅ 数据完整性**: 避免MERGE操作导致的数据覆盖
- **✅ 实时更新**: 每章处理完立即写入数据库
- **✅ 进度可见**: 实时显示处理进度和数据库变化
- **✅ 错误隔离**: 单章失败不影响其他章节
- **✅ 可中断恢复**: 随时中断，已处理数据保留

### 工作流程
```
书籍文本 → 按章节分割 → 逐章GPT解析 → 实时数据库更新 → 结果文件保存
   ↓           ↓           ↓            ↓             ↓
book.json → 19个章节 → 章节实体抽取 → CREATE操作 → chapter_results/
```

### 处理统计 (test10数据库)
- **总章节数**: 19章
- **最终节点**: 106个 (平均每章5.6个)
- **最终关系**: 99个 (平均每章5.2个)
- **处理时间**: ~2-3分钟 (包含GPT调用)
- **输出文件**: 
  - 19个章节结果文件: `results/chapter_results_fixed/chapter_X_graph.json`
  - 1个处理总结: `results/chapter_processing_summary_fixed_*.json`

### 使用方法
```bash
# 运行按章节处理
python src/graph_generation/neo4j_book2graph_chapter_by_chapter_fixed.py

# 系统会提示是否清空数据库
🗑️ Clear existing data in database 'test10'? (y/N): y

# 处理过程中会显示每章进度
📝 Processing Chapter 1 (1/19)...
✅ Created 5 unique nodes from Chapter 1
✅ Created 4 relationships from Chapter 1
📊 Database now has 5 nodes (+5) and 4 relationships (+4)
```

## 📈 性能指标

### 处理能力
- **图谱规模**: 106个节点 (test10) / 114个节点 (test9)
- **问答速度**: ~4秒/题 (包含多轮迭代)
- **最大迭代**: 5轮自适应搜索
- **缓存命中**: 秒级响应

### 准确性
- **成功率**: 在API配额充足时可达80-100%
- **置信度**: 0.0-1.0评分系统
- **迭代优化**: 自动策略调整

## 🛠️ 故障排除

### 常见问题

1. **模块导入错误**
   ```bash
   # 确保在正确目录运行
   cd /path/to/AgenticSearch
   python src/question_answering/run_agentic_batch.py ...
   ```

2. **缓存未找到**
   - 确认 `cache/` 目录存在
   - 检查 `embedding_test9.json` 和 `propertykey_test9.json` 文件

3. **Neo4j连接失败**
   ```bash
   # 检查Neo4j状态
   neo4j status
   # 验证 .env 配置
   cat .env
   ```

4. **API配额不足**
   ```
   错误: insufficient_user_quota
   解决: 充值OpenAI账户或更换API密钥
   ```

5. **按章节处理相关问题** 🆕
   ```bash
   # 数据库认证错误
   错误: unauthorized due to authentication failure
   解决: 更新 .env 中的 NEO4J_PASSWORD
   
   # 章节结果文件路径
   位置: results/chapter_results_fixed/
   格式: chapter_X_graph.json
   
   # 中断后恢复
   问题: 处理中断后如何恢复？
   解决: 重新运行脚本，选择不清空数据库 (N)
   ```

### 日志和调试
- 系统会自动显示详细的执行日志
- 结果保存在 `results/agentic_results_*/` 目录
- 包含JSON、TXT、CSV三种格式的输出

## 📋 输出格式

### 结果文件
```
results/agentic_results_YYYYMMDD_HHMMSS/
├── results_X_YYYYMMDD_HHMMSS.json      # 详细结果数据
├── report_X_YYYYMMDD_HHMMSS.txt        # 人类可读报告
└── summary_X_YYYYMMDD_HHMMSS.csv       # CSV格式摘要
```

### JSON结果结构
```json
{
  "session_id": "唯一会话ID",
  "question": "问题文本",
  "final_answer": "最终答案",
  "confidence_score": 0.85,
  "total_iterations": 3,
  "search_successful": true,
  "reasoning_chain": ["推理步骤"],
  "query_history": ["执行的查询"]
}
```

## 🎯 核心特性

- ✅ **零预设架构**: 无硬编码查询模板，完全动态生成
- ✅ **按章节处理** 🆕: 逐章解析，数据完整性保障，避免覆盖
- ✅ **智能迭代**: 自适应搜索策略，最多5轮优化
- ✅ **缓存优化**: 秒级响应，避免重复计算
- ✅ **模块化设计**: 图谱生成与问答系统分离
- ✅ **多格式输出**: JSON/TXT/CSV多种结果格式
- ✅ **完整日志**: 全程追踪，便于调试和优化

## 📚 使用示例

### 单题测试
```bash
python src/question_answering/run_agentic_batch.py \
    --questions data/questions_new_book.json \
    --range 1 \
    --output results/test_single/
```

### 批量处理
```bash
python src/question_answering/run_agentic_batch.py \
    --questions data/questions_new_book.json \
    --range 1-50 \
    --output results/batch_50/
```

---

**AgenticSearch - 让AI理解您的知识图谱！** 🚀 