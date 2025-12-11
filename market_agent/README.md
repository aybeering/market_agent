# Market Agent

事件期货可行性分析工具包。

## 安装

确保已安装依赖：

```bash
pip install -r requirements.txt
```

## 快速开始

```python
import asyncio
from market_agent import Search

async def main():
    result = await Search.go("比特币2025年突破15万美元")
    
    if result.success:
        print(result.report)
    else:
        print(f"错误: {result.error}")

asyncio.run(main())
```

## API

### `Search.go()`

异步执行事件期货可行性分析。

```python
result = await Search.go(
    topic: str,                              # 事件话题（必填）
    event_category: Optional[str] = None,    # 事件类别（可选，自动推断）
    target_date: Optional[str] = None,       # 预期结算日期（可选）
    job_id: Optional[str] = None,            # 任务ID（可选，自动生成）
    on_progress: Optional[Callable] = None,  # 进度回调（可选）
)
```

#### 参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `topic` | `str` | ✅ | 事件话题，如 "比特币2025年突破15万美元" |
| `event_category` | `str` | ❌ | 事件类别，如 "加密货币"、"政治"、"体育" |
| `target_date` | `str` | ❌ | 预期结算日期，格式 "YYYY-MM-DD" |
| `job_id` | `str` | ❌ | 任务ID，默认自动生成 UUID |
| `on_progress` | `Callable` | ❌ | 进度回调函数 |

#### 返回值

返回 `SearchResult` 对象：

```python
@dataclass
class SearchResult:
    success: bool                    # 是否成功
    topic: str                       # 事件话题
    report: str                      # 完整报告（Markdown）
    feasibility_score: float         # 可行性评分 (0-10)
    event_category: str              # 事件类别
    target_date: str                 # 结算日期
    job_id: str                      # 任务ID
    elapsed_time: float              # 耗时（秒）
    error: str                       # 错误信息（失败时）
    
    # 各维度简报
    quantifiability_briefing: str    # 可量化性简报
    oracle_briefing: str             # 预言机简报
    market_demand_briefing: str      # 市场需求简报
    compliance_risk_briefing: str    # 合规风险简报
```

## 使用示例

### 基本用法

```python
result = await Search.go("2025年美联储降息至少3次")

if result:  # 可直接用 bool 判断
    print(result.report)
```

### 带进度回调

```python
async def on_progress(node: str, status: str, message: str):
    print(f"[{node}] {message}")

result = await Search.go(
    topic="SpaceX星舰成功登陆火星",
    event_category="航天",
    target_date="2026-12-31",
    on_progress=on_progress
)
```

### 同步调用

```python
from market_agent import Search

result = Search.go_sync("比特币2025年突破15万美元")
print(result.report)
```

### 转换为字典

```python
data = result.to_dict()
```

## 环境变量

在 `.env` 文件中配置：

```
OPENAI_API_KEY=your_openai_api_key
TAVILY_API_KEY=your_tavily_api_key
```

## 工作流程

```
topic
  ↓
[Grounding] 事件背景分析
  ↓
[并行分析]
  ├── 可量化性分析
  ├── 预言机分析
  ├── 市场需求分析
  └── 合规风险分析
  ↓
[Collector] 数据收集
  ↓
[Curator] 数据筛选
  ↓
[Enricher] 内容增强
  ↓
[Briefing] 简报生成
  ↓
[Editor] 报告编译
  ↓
SearchResult
```
