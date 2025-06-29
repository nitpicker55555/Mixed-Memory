# Memory Graph Project

这个项目整合了记忆图生成的所有组件，包括数据处理、图构建和可视化功能。

## 📁 项目结构

```
MemoryGraph/
├── data/                           # 数据文件夹
│   ├── events.json                 # 事件数据
│   ├── meta_events.json            # 元事件数据
│   ├── books/                      # 生成的书籍数据
│   │   └── model_claude-3-5-sonnet-20240620_itermax_10_Idefault_nbchapters_19_nbtokens_10397/
│   │       ├── book.json           # 书籍内容
│   │       ├── df_book_groundtruth.parquet
│   │       ├── df_qa.parquet
│   │       └── df_qa_debug_widespreadness.parquet
│   └── graph_answers/              # 图答案数据
│       ├── 356.json
│       ├── 357.json
│       └── ...                     # 所有图答案文件
├── memory_graph_builder.py         # 主类定义
├── extract_graph_elements.py       # 提取图元素
├── build_graphs.py                # 构建R图和L字典
├── visualize_graphs.py            # 可视化图
├── main.py                        # 主运行脚本
├── process_data.py                # 数据处理脚本
├── README.md                      # 本文件
└── graph_generation.py            # 原始文件（保留）
```

## 🎯 项目功能

### 1. 数据处理
- **事件数据**: 从 `events.json` 和 `meta_events.json` 加载事件信息
- **书籍数据**: 从生成的书籍中提取内容
- **图答案**: 从 `graph_answers/` 文件夹加载所有图答案

### 2. 记忆图生成
- **R图**: 关系图，描述实体间的关系随时间变化
- **L字典**: 标签字典，为每个实体分配语义标签

### 3. 可视化
- 生成R图的可视化图片
- 显示L字典的内容
- 创建数据摘要

## 🚀 使用方法

### 方法1: 完整数据处理管道

```bash
# 运行完整的数据处理管道
python process_data.py
```

这将：
1. 加载所有数据文件
2. 分析图答案数据
3. 从事件创建故事文本
4. 生成记忆图
5. 创建可视化

### 方法2: 单独使用模块

```python
# 导入模块
from memory_graph_builder import MemoryGraphBuilder
from extract_graph_elements import extract_graph_elements
from build_graphs import build_all_graphs
from visualize_graphs import visualize_all_graphs

# 使用自定义内容
builder = MemoryGraphBuilder("Your story content")
extract_graph_elements(builder)
build_all_graphs(builder)
visualize_all_graphs(builder)
```

### 方法3: 命令行工具

```bash
# 使用主脚本处理自定义内容
python main.py --book_content "Your story content here"

# 从文件读取内容
python main.py --book_file path/to/your/story.txt
```

## 📊 数据结构

### 事件数据格式
```json
[
  ["September 13, 2025", "Bethpage Black Course", "Ezra Edwards", "Parkour Workshop", "Demonstrated cat leaps"],
  ...
]
```

### 图答案格式
每个 `graph_answers/*.json` 文件包含一个问题的答案：
```json
"On September 22, 2026, the following key events occurred..."
```

### 生成的记忆图格式
```json
{
  "R": [
    {
      "E1": "Entity A",
      "E2": "Entity B", 
      "R": [
        {
          "time": "2024-01",
          "relationship": "met",
          "event": "Entity A met Entity B at a conference."
        }
      ]
    }
  ],
  "L": [
    {
      "Label": "Instructor",
      "Entity": "Noa Middleton",
      "time": "2025-09-13"
    }
  ]
}
```

## 🔧 环境要求

```bash
pip install openai python-dotenv networkx matplotlib pandas
```

## ⚙️ 配置

创建 `.env` 文件：
```
OPENAI_API_KEY=your_openai_api_key_here
```

## 📈 输出文件

运行 `process_data.py` 后会生成：
- `generated_memory_graph.json`: 生成的记忆图数据
- `generated_graphs/R_Graph.png`: R图可视化
- 控制台输出: L字典内容和数据摘要

## 🔍 数据分析

`process_data.py` 会分析：
- 事件和元事件的数量
- 图答案的统计信息（长度、分布等）
- 生成的记忆图结构

## 📝 注意事项

1. **API密钥**: 确保设置了有效的OpenAI API密钥
2. **数据路径**: 确保所有数据文件都在正确的位置
3. **内存使用**: 处理大量数据时注意内存使用
4. **网络连接**: 需要网络连接来调用OpenAI API

## 🛠️ 扩展功能

可以轻松扩展的功能：
- 添加更多数据源
- 实现不同的图构建算法
- 添加更多可视化选项
- 集成其他LLM API

## 📞 支持

如有问题，请检查：
1. 数据文件是否完整
2. API密钥是否正确设置
3. 依赖包是否已安装
4. 网络连接是否正常 