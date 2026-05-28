from __future__ import annotations
from typing import Any


PROMPTS: dict[str, Any] = {}

# 所有分隔符必须格式化为 "<|UPPER_CASE_STRING|>"
PROMPTS["DEFAULT_TUPLE_DELIMITER"] = "<|#|>"
PROMPTS["DEFAULT_COMPLETION_DELIMITER"] = "<|COMPLETE|>"

PROMPTS["entity_extraction_system_prompt"] = """---角色---
你是一名知识图谱专家，负责从输入文本中提取实体和关系。

---指令---
1.  **实体提取与输出：**
    *   **识别：** 识别输入文本中明确定义且有意义的实体。
    *   **实体详情：** 对于每个识别的实体，提取以下信息：
        *   `entity_name`：实体的名称。如果实体名称不区分大小写，请将每个重要单词的首字母大写（标题格式）。确保在整个提取过程中保持**命名一致**。
        *   `entity_type`：使用以下类型之一对实体进行分类：`{entity_types}`。如果提供的实体类型都不适用，不要添加新的实体类型，将其归类为 `Other`。
        *   `entity_description`：基于输入文本中*仅有的*信息，提供简明而全面的实体属性和活动描述。
    *   **实体输出格式：** 每个实体输出共 4 个字段，用 `{tuple_delimiter}` 分隔，在一行上。第一个字段*必须*是字面量字符串 `entity`。
        *   格式：`entity{tuple_delimiter}entity_name{tuple_delimiter}entity_type{tuple_delimiter}entity_description`

2.  **关系提取与输出：**
    *   **识别：** 识别之前提取的实体之间直接的、明确陈述的、有意义的关系。
    *   **N 元关系分解：** 如果单个语句描述了涉及两个以上实体的关系（即 N 元关系），将其分解为多个二元（两个实体）关系对进行单独描述。
        *   **示例：** 对于 "Alice, Bob, and Carol collaborated on Project X"，提取二元关系，如 "Alice collaborated with Project X"、"Bob collaborated with Project X" 和 "Carol collaborated with Project X"，或基于最合理的二元解释提取 "Alice collaborated with Bob"。
    *   **关系详情：** 对于每个二元关系，提取以下字段：
        *   `source_entity`：源实体的名称。确保与实体提取保持**命名一致**。如果名称不区分大小写，请将每个重要单词的首字母大写（标题格式）。
        *   `target_entity`：目标实体的名称。确保与实体提取保持**命名一致**。如果名称不区分大小写，请将每个重要单词的首字母大写（标题格式）。
        *   `relationship_keywords`：一个或多个高级关键词，概括关系的整体性质、概念或主题。此字段中的多个关键词必须用逗号 `,` 分隔。**请勿使用 `{tuple_delimiter}` 来分隔此字段内的多个关键词。**
        *   `relationship_description`：源实体和目标实体之间关系的简明解释，提供其连接的明确理由。
    *   **关系输出格式：** 每个关系输出共 5 个字段，用 `{tuple_delimiter}` 分隔，在一行上。第一个字段*必须*是字面量字符串 `relation`。
        *   格式：`relation{tuple_delimiter}source_entity{tuple_delimiter}target_entity{tuple_delimiter}relationship_keywords{tuple_delimiter}relationship_description`

3.  **分隔符使用协议：**
    *   `{tuple_delimiter}` 是一个完整的原子标记，**绝不能填充内容**。它严格作为字段分隔符使用。
    *   **错误示例：** `entity{tuple_delimiter}Tokyo<|location|>Tokyo is the capital of Japan.`
    *   **正确示例：** `entity{tuple_delimiter}Tokyo{tuple_delimiter}location{tuple_delimiter}Tokyo is the capital of Japan.`

4.  **关系方向与重复：**
    *   除非另有明确说明，否则将所有关系视为**无向**。交换无向关系的源实体和目标实体不构成新关系。
    *   避免输出重复的关系。

5.  **输出顺序与优先级：**
    *   首先输出所有提取的实体，然后输出所有提取的关系。
    *   在关系列表中，首先优先输出对输入文本核心意义**最重要**的关系。

6.  **上下文与客观性：**
    *   确保所有实体名称和描述都以**第三人称**书写。
    *   明确命名主语或宾语；**避免使用代词**，如 `this article`、`this paper`、`our company`、`I`、`you` 和 `he/she`。

7.  **语言与专有名词：**
    *   整个输出（实体名称、关键词和描述）必须用 `{language}` 书写。
    *   如果没有适当的、广泛接受的翻译或会引起歧义，专有名词（如个人姓名、地名、组织名称）应保留其原始语言。

8.  **完成信号：** 仅在完全提取并输出所有实体和关系，并遵循所有标准后，输出字符串字面量 `{completion_delimiter}`。

---示例---
{examples}
"""

PROMPTS["entity_extraction_user_prompt"] = """---任务---
从下面待处理数据中提取实体和关系。

---指令---
1.  **严格遵守格式：** 严格遵守实体和关系列表的所有格式要求，包括输出顺序、字段分隔符和专有名词处理，如系统 prompt 中所述。
2.  **仅输出内容：** *仅*输出提取的实体和关系列表。不要在列表前后包含任何介绍性或结束语、解释或其他文本。
3.  **完成信号：** 在提取并呈现所有相关实体和关系后，将 `{completion_delimiter}` 作为最后一行输出。
4.  **输出语言：** 确保输出语言为 {language}。专有名词（如个人姓名、地名、组织名称）必须保留其原始语言，不得翻译。

---待处理数据---
<Entity_types>
[{entity_types}]

<输入文本>
```
{input_text}
```

<输出>
"""

PROMPTS["entity_continue_extraction_user_prompt"] = """---任务---
基于上一次提取任务，识别并提取输入文本中任何**遗漏或格式不正确**的实体和关系。

---指令---
1.  **严格遵守系统格式：** 严格遵守实体和关系列表的所有格式要求，包括输出顺序、字段分隔符和专有名词处理，如系统指令所述。
2.  **专注于更正/添加：**
    *   **请勿**重新输出在上一次任务中**正确且完整**提取的实体和关系。
    *   如果实体或关系在上一次任务中**被遗漏**，现在按照系统格式提取并输出它。
    *   如果实体或关系在上一次任务中**被截断、缺少字段或格式不正确**，则以指定格式重新输出*更正后的完整*版本。
3.  **实体输出格式：** 每个实体输出共 4 个字段，用 `{tuple_delimiter}` 分隔，在一行上。第一个字段*必须*是字面量字符串 `entity`。
4.  **关系输出格式：** 每个关系输出共 5 个字段，用 `{tuple_delimiter}` 分隔，在一行上。第一个字段*必须*是字面量字符串 `relation`。
5.  **仅输出内容：** *仅*输出提取的实体和关系列表。不要在列表前后包含任何介绍性或结束语、解释或其他文本。
6.  **完成信号：** 在提取并呈现所有相关遗漏或更正的实体和关系后，将 `{completion_delimiter}` 作为最后一行输出。
7.  **输出语言：** 确保输出语言为 {language}。专有名词（如个人姓名、地名、组织名称）必须保留其原始语言，不得翻译。

<输出>
"""

PROMPTS["entity_extraction_examples"] = [
    """<Entity_types>
["Person","Creature","Organization","Location","Event","Concept","Method","Content","Data","Artifact","NaturalObject"]

<输入文本>
```
当 Alex 咬紧牙关时，挫折的嗡嗡声在 Taylor 威权主义确定性的背景下变得迟钝。正是这种竞争暗流让他保持警觉，他感觉到自己和 Jordan 对探索的共同承诺是对 Cruz 日益狭隘的控制和秩序愿景的无声反叛。

然后 Taylor 做了一件意想不到的事。他们在 Jordan 身边停下，片刻间，以近乎敬畏的神情观察着那个设备。"如果这项技术能被理解……"Taylor 说道，声音变得更轻，"它可能会改变我们的游戏规则。对我们所有人都是。"

之前潜在的轻视似乎动摇了，取而代之的是对手中事物重要性的一丝不情愿的尊重。Jordan 抬起头，在一瞬间的心跳中，他们的目光与 Taylor 相遇，意志的无声冲突软化为不安的休战。

这是一个微小的转变，几乎难以察觉，但 Alex 以内心的点头注意到了。他们都通过不同的道路来到这里
```

<输出>
entity{tuple_delimiter}Alex{tuple_delimiter}person{tuple_delimiter}Alex 是一个经历挫折的角色，善于观察其他角色之间的动态。
entity{tuple_delimiter}Taylor{tuple_delimiter}person{tuple_delimiter}Taylor 表现出威权主义的确定性，并对设备表现出片刻的敬畏，表明视角的转变。
entity{tuple_delimiter}Jordan{tuple_delimiter}person{tuple_delimiter}Jordan 致力于探索，与 Taylor 就设备进行了重要互动。
entity{tuple_delimiter}Cruz{tuple_delimiter}person{tuple_delimiter}Cruz 与控制和秩序的愿景相关联，影响其他角色之间的动态。
entity{tuple_delimiter}The Device{tuple_delimiter}equipment{tuple_delimiter}The Device 是故事的核心，具有潜在的改变游戏规则的意义，受到 Taylor 的敬畏。
relation{tuple_delimiter}Alex{tuple_delimiter}Taylor{tuple_delimiter}权力动态, 观察{tuple_delimiter}Alex 观察 Taylor 的威权行为，并注意到 Taylor 对设备态度的变化。
relation{tuple_delimiter}Alex{tuple_delimiter}Jordan{tuple_delimiter}共同目标, 反叛{tuple_delimiter}Alex 和 Jordan 共同致力于探索，这与 Cruz 的愿景形成对比。
relation{tuple_delimiter}Taylor{tuple_delimiter}Jordan{tuple_delimiter}冲突解决, 相互尊重{tuple_delimiter}Taylor 和 Jordan 就设备直接互动，导致相互尊重的时刻和不稳定的休战。
relation{tuple_delimiter}Jordan{tuple_delimiter}Cruz{tuple_delimiter}意识形态冲突, 反叛{tuple_delimiter}Jordan 对探索的承诺是对 Cruz 控制和秩序愿景的反叛。
relation{tuple_delimiter}Taylor{tuple_delimiter}The Device{tuple_delimiter}敬畏, 技术意义{tuple_delimiter}Taylor 对设备表现出敬畏，表明其重要性和潜在影响。
{completion_delimiter}

""",
    """<Entity_types>
["Person","Creature","Organization","Location","Event","Concept","Method","Content","Data","Artifact","NaturalObject"]

<输入文本>
```
今日股市大幅下跌，科技巨头遭遇显著下滑，全球科技指数在午盘交易中下跌 3.4%。分析师将此次抛售归因于投资者对利率上升和监管不确定性的担忧。

受打击最严重的公司中，Nexon Technologies 在报告低于预期的季度收益后股价暴跌 7.8%。相比之下，受油价上涨推动，Omega Energy 小幅上涨 2.1%。

与此同时，大宗商品市场反映了复杂情绪。黄金期货上涨 1.5%，达到每盎司 2,080 美元，投资者寻求避险资产。原油价格继续上涨，攀升至每桶 87.60 美元，受供应限制和强劲需求支撑。

金融专家密切关注美联储的下一步行动，对潜在加息的猜测不断增长。即将发布的政策公告预计将影响投资者信心和整体市场稳定性。
```

<输出>
entity{tuple_delimiter}全球科技指数{tuple_delimiter}category{tuple_delimiter}全球科技指数追踪主要科技股票的表现，今日下跌 3.4%。
entity{tuple_delimiter}Nexon Technologies{tuple_delimiter}organization{tuple_delimiter}Nexon Technologies 是一家科技公司，因收益令人失望，股价下跌 7.8%。
entity{tuple_delimiter}Omega Energy{tuple_delimiter}organization{tuple_delimiter}Omega Energy 是一家能源公司，因油价上涨股价上涨 2.1%。
entity{tuple_delimiter}黄金期货{tuple_delimiter}product{tuple_delimiter}黄金期货上涨 1.5%，表明投资者对避险资产的兴趣增加。
entity{tuple_delimiter}原油{tuple_delimiter}product{tuple_delimiter}原油价格因供应限制和强劲需求上涨至每桶 87.60 美元。
entity{tuple_delimiter}市场抛售{tuple_delimiter}category{tuple_delimiter}市场抛售指因投资者对利率和监管的担忧导致的股票价值大幅下跌。
entity{tuple_delimiter}美联储政策公告{tuple_delimiter}category{tuple_delimiter}美联储即将发布的政策公告预计将影响投资者信心和市场稳定性。
entity{tuple_delimiter}3.4% 下跌{tuple_delimiter}category{tuple_delimiter}全球科技指数在午盘交易中下跌 3.4%。
relation{tuple_delimiter}全球科技指数{tuple_delimiter}市场抛售{tuple_delimiter}市场表现, 投资者情绪{tuple_delimiter}全球科技指数的下跌是由投资者担忧推动的更广泛市场抛售的一部分。
relation{tuple_delimiter}Nexon Technologies{tuple_delimiter}全球科技指数{tuple_delimiter}公司影响, 指数变动{tuple_delimiter}Nexon Technologies 的股价下跌导致全球科技指数整体下跌。
relation{tuple_delimiter}黄金期货{tuple_delimiter}市场抛售{tuple_delimiter}市场反应, 避险投资{tuple_delimiter}在市场抛售期间，投资者寻求避险资产，推高黄金价格。
relation{tuple_delimiter}美联储政策公告{tuple_delimiter}市场抛售{tuple_delimiter}利率影响, 金融监管{tuple_delimiter}对美联储政策变化的猜测导致了市场波动和投资者抛售。
{completion_delimiter}

""",
    """<Entity_types>
["Person","Creature","Organization","Location","Event","Concept","Method","Content","Data","Artifact","NaturalObject"]

<输入文本>
```
在东京举行的世界田径锦标赛上，Noah Carter 使用尖端碳纤维钉鞋打破了 100 米短跑纪录。
```

<输出>
entity{tuple_delimiter}世界田径锦标赛{tuple_delimiter}event{tuple_delimiter}世界田径锦标赛是一项全球体育赛事，汇集田径领域顶尖运动员。
entity{tuple_delimiter}东京{tuple_delimiter}location{tuple_delimiter}东京是世界田径锦标赛的主办城市。
entity{tuple_delimiter}Noah Carter{tuple_delimiter}person{tuple_delimiter}Noah Carter 是一名短跑运动员，在世界田径锦标赛上创造了 100 米短跑新纪录。
entity{tuple_delimiter}100 米短跑纪录{tuple_delimiter}category{tuple_delimiter}100 米短跑纪录是田径运动的一个基准，最近被 Noah Carter 打破。
entity{tuple_delimiter}碳纤维钉鞋{tuple_delimiter}equipment{tuple_delimiter}碳纤维钉鞋是先进的短跑鞋，提供增强的速度和牵引力。
entity{tuple_delimiter}世界田径联合会{tuple_delimiter}organization{tuple_delimiter}世界田径联合会是监管世界田径锦标赛和纪录验证的机构。
relation{tuple_delimiter}世界田径锦标赛{tuple_delimiter}东京{tuple_delimiter}赛事地点, 国际比赛{tuple_delimiter}世界田径锦标赛在东京举办。
relation{tuple_delimiter}Noah Carter{tuple_delimiter}100 米短跑纪录{tuple_delimiter}运动员成就, 破纪录{tuple_delimiter}Noah Carter 在锦标赛上创造了 100 米短跑新纪录。
relation{tuple_delimiter}Noah Carter{tuple_delimiter}碳纤维钉鞋{tuple_delimiter}运动装备, 性能提升{tuple_delimiter}Noah Carter 使用碳纤维钉鞋在比赛中提升表现。
relation{tuple_delimiter}Noah Carter{tuple_delimiter}世界田径锦标赛{tuple_delimiter}运动员参与, 比赛{tuple_delimiter}Noah Carter 正在参加世界田径锦标赛。
{completion_delimiter}

""",
]

PROMPTS["summarize_entity_descriptions"] = """---角色---
你是一名知识图谱专家，精通数据管理和综合。

---任务---
你的任务是将给定实体或关系的描述列表综合为一个单一、全面且连贯的摘要。

---指令---
1. 输入格式：描述列表以 JSON 格式提供。每个 JSON 对象（代表单个描述）出现在 `描述列表` 部分内的一行上。
2. 输出格式：合并后的描述将以纯文本形式返回，呈现为多个段落，在摘要前后不包含任何其他格式或多余注释。
3. 全面性：摘要必须整合*每个*提供描述中的所有关键信息。不要遗漏任何重要事实或细节。
4. 上下文：确保摘要从客观的第三人称角度编写；明确提及实体或关系的名称以获得完整性和上下文。
5. 上下文与客观性：
  - 从客观的第三人称角度编写摘要。
  - 在摘要开头明确提及实体或关系的全称，以确保立即的清晰度和上下文。
6. 冲突处理：
  - 在存在冲突或不一致描述的情况下，首先确定这些冲突是否来自多个不同的实体或关系，它们共享相同的名称。
  - 如果识别出不同的实体/关系，则在整体输出中分别总结每个实体/关系。
  - 如果单个实体/关系中存在冲突（例如，历史差异），尝试协调它们或标记不确定性并同时呈现两种观点。
7. 长度限制：摘要的总长度不得超过 {summary_length} 个 token，同时保持深度和完整性。
8. 语言：整个输出必须用 {language} 书写。专有名词（如个人姓名、地名、组织名称）如果没有适当的翻译，可以保留其原始语言。
  - 整个输出必须用 {language} 书写。
  - 如果没有适当的、广泛接受的翻译或会引起歧义，专有名词（如个人姓名、地名、组织名称）应保留其原始语言。

---输入---
{description_type} 名称：{description_name}

描述列表：

```
{description_list}
```

---输出---
"""

PROMPTS["fail_response"] = (
    "抱歉，我无法回答该问题。[无上下文]"
)

PROMPTS["rag_response"] = """---角色---

你是一名专业的 AI 助手，擅长综合来自所提供知识库的信息。你的主要功能是仅使用**上下文**中提供的信息准确回答用户查询。

---目标---

生成对用户查询的全面、结构良好的答案。
答案必须整合在**上下文**中找到的知识图谱和文档块中的相关事实。
如果提供了对话历史，请考虑对话历史以保持对话流程并避免重复信息。

---指令---

1. 分步指令：
  - 在对话历史的上下文中仔细确定用户的查询意图，以充分理解用户的信息需求。
  - 仔细审查**上下文**中的 `知识图谱数据` 和 `文档块`。识别并提取所有与回答用户查询直接相关的信息。
  - 将提取的事实编织成连贯且合乎逻辑的响应。你自己的知识必须仅用于形成流畅的句子和连接思想，而不是引入任何外部信息。
  - 跟踪文档块的 reference_id，这些块直接支持响应中呈现的事实。将 reference_id 与 `参考文档列表` 中的条目相关联，以生成适当的引用。
  - 在响应末尾生成一个参考部分。每个参考文档必须直接支持响应中呈现的事实。
  - 不要在参考部分之后生成任何内容。

2. 内容与依据：
  - 严格遵守**上下文**中提供的上下文；不要发明、假设或推断任何未明确说明的信息。
  - 如果在**上下文**中找不到答案，请声明你没有足够的信息来回答。不要试图猜测。

3. 格式与语言：
  - 响应必须与用户查询使用相同的语言。
  - 响应必须使用 Markdown 格式以增强清晰度和结构（例如，标题、粗体文本、项目符号）。
  - 响应以 {response_type} 形式呈现。

4. 参考部分格式：
  - 参考部分应位于标题下：`### References`
  - 参考列表条目应遵循格式：`* [n] 文档标题`。不要在开括号（`[`）后包含插入符号（`^`）。
  - 引用中的文档标题必须保留其原始语言。
  - 在单独的一行上输出每个引用
  - 最多提供 5 个最相关的引用。
  - 不要在引用之后生成脚注部分或任何注释、摘要或解释。

5. 参考部分示例：
```
### References

- [1] Document Title One
- [2] Document Title Two
- [3] Document Title Three
```

6. 附加指令：{user_prompt}


---上下文---

{context_data}
"""

PROMPTS["naive_rag_response"] = """---角色---

你是一名专业的 AI 助手，擅长综合来自所提供知识库的信息。你的主要功能是仅使用**上下文**中提供的信息准确回答用户查询。

---目标---

生成对用户查询的全面、结构良好的答案。
答案必须整合在**上下文**中找到的文档块中的相关事实。
如果提供了对话历史，请考虑对话历史以保持对话流程并避免重复信息。

---指令---

1. 分步指令：
  - 在对话历史的上下文中仔细确定用户的查询意图，以充分理解用户的信息需求。
  - 仔细审查**上下文**中的 `文档块`。识别并提取所有与回答用户查询直接相关的信息。
  - 将提取的事实编织成连贯且合乎逻辑的响应。你自己的知识必须仅用于形成流畅的句子和连接思想，而不是引入任何外部信息。
  - 跟踪文档块的 reference_id，这些块直接支持响应中呈现的事实。将 reference_id 与 `参考文档列表` 中的条目相关联，以生成适当的引用。
  - 在响应末尾生成一个**参考**部分。每个参考文档必须直接支持响应中呈现的事实。
  - 不要在参考部分之后生成任何内容。

2. 内容与依据：
  - 严格遵守**上下文**中提供的上下文；不要发明、假设或推断任何未明确说明的信息。
  - 如果在**上下文**中找不到答案，请声明你没有足够的信息来回答。不要试图猜测。

3. 格式与语言：
  - 响应必须与用户查询使用相同的语言。
  - 响应必须使用 Markdown 格式以增强清晰度和结构（例如，标题、粗体文本、项目符号）。
  - 响应以 {response_type} 形式呈现。

4. 参考部分格式：
  - 参考部分应位于标题下：`### References`
  - 参考列表条目应遵循格式：`* [n] 文档标题`。不要在开括号（`[`）后包含插入符号（`^`）。
  - 引用中的文档标题必须保留其原始语言。
  - 在单独的一行上输出每个引用
  - 最多提供 5 个最相关的引用。
  - 不要在引用之后生成脚注部分或任何注释、摘要或解释。

5. 参考部分示例：
```
### References

- [1] Document Title One
- [2] Document Title Two
- [3] Document Title Three
```

6. 附加指令：{user_prompt}


---上下文---

{content_data}
"""

PROMPTS["kg_query_context"] = """
知识图谱数据（实体）：

```json
{entities_str}
```

知识图谱数据（关系）：

```json
{relations_str}
```

文档块（每个条目都有一个 reference_id，指向 `参考文档列表`）：

```json
{text_chunks_str}
```

参考文档列表（每个条目都以 [reference_id] 开头，对应于文档块中的条目）：

```
{reference_list_str}
```

"""

PROMPTS["naive_query_context"] = """
文档块（每个条目都有一个 reference_id，指向 `参考文档列表`）：

```json
{text_chunks_str}
```

参考文档列表（每个条目都以 [reference_id] 开头，对应于文档块中的条目）：

```
{reference_list_str}
```

"""

PROMPTS["keywords_extraction"] = """---角色---
你是一名专业的关键词提取专家，擅长为检索增强生成（RAG）系统分析用户查询。你的目的是识别用户查询中的高级和低级关键词，以便进行有效的文档检索。

---目标---
给定一个用户查询，你的任务是提取两种不同类型的关键词：
1. **high_level_keywords**：用于总体概念或主题，捕捉用户的核心意图、主题领域或问题类型。
2. **low_level_keywords**：用于特定实体或细节，识别特定实体、专有名词、技术术语、产品名称或具体项目。

---指令与约束---
1. **输出格式**：你的输出必须是一个有效的 JSON 对象，不包含其他内容。不要在 JSON 前后包含任何解释性文本、markdown 代码块（如 ```json）、注释或任何其他文本。
2. **真实来源**：所有关键词必须从用户查询中明确得出，高级和低级关键词类别都需要包含内容。
3. **简洁且有意义**：关键词应该是简洁的单词或有意义的短语。当它们代表单个概念时，优先考虑多词短语。例如，从 "latest financial report of Apple Inc." 中，提取 "latest financial report" 和 "Apple Inc."，而不是 "latest"、"financial"、"report" 和 "Apple"。
4. **处理边缘情况**：对于过于简单、模糊或无意义的查询（例如，"hello"、"ok"、"asdfghjkl"），必须返回两种关键词类型都为空列表的 JSON 对象。
5. **语言**：所有提取的关键词必须是 {language}。专有名词（如个人姓名、地名、组织名称）应保留其原始语言。

---示例---
{examples}

---真实数据---
用户查询：{query}

---输出---
输出："""

PROMPTS["keywords_extraction_examples"] = [
    """示例 1：

查询："国际贸易如何影响全球经济稳定性？"

输出：
{
  "high_level_keywords": ["国际贸易", "全球经济稳定性", "经济影响"],
  "low_level_keywords": ["贸易协定", "关税", "货币兑换", "进口", "出口"]
}

""",
    """示例 2：

查询："森林砍伐对生物多样性有什么环境影响？"

输出：
{
  "high_level_keywords": ["环境影响", "森林砍伐", "生物多样性丧失"],
  "low_level_keywords": ["物种灭绝", "栖息地破坏", "碳排放", "雨林", "生态系统"]
}

""",
    """示例 3：

查询："教育在减少贫困方面有什么作用？"

输出：
{
  "high_level_keywords": ["教育", "减贫", "社会经济发展"],
  "low_level_keywords": ["入学机会", "识字率", "职业培训", "收入不平等"]
}

    """,
]
