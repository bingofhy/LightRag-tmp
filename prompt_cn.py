from __future__ import annotations
import os
from pathlib import Path
from typing import Any, Mapping, TypedDict

import yaml


PROMPTS: dict[str, Any] = {}

# 所有分隔符必须格式化为 "<|UPPER_CASE_STRING|>"
PROMPTS["DEFAULT_TUPLE_DELIMITER"] = "<|#|>"
PROMPTS["DEFAULT_COMPLETION_DELIMITER"] = "<|COMPLETE|>"

# 默认实体类型指导，通过 {entity_types_guidance} 注入到提取 prompt 中。
# 用户可以通过在 addon_params 中传递 entity_types_guidance 来覆盖，
# 或者替换 PROMPTS 中的完整 prompt 模板字符串。
PROMPTS[
    "default_entity_types_guidance"
] = """使用以下类型之一对每个实体进行分类。如果没有合适的类型，请使用 `Other`。

- Person：人类个体，真实或虚构的
- Creature：非人类生物（动物、神话生物等）
- Organization：公司、机构、政府组织、团体
- Location：地理地点（城市、国家、建筑物、地区）
- Event：事件、事故、仪式、会议
- Concept：抽象概念、理论、原则、信仰
- Method：程序、技术、算法、工作流程
- Content：创意或信息作品（书籍、文章、电影、报告）
- Data：定量或结构化信息（统计数据、数据集、测量值）
- Artifact：人类创造的物理或数字对象（工具、软件、设备）
- NaturalObject：自然非生物（矿物、天体、化合物）"""

PROMPTS["entity_extraction_system_prompt"] = """---角色---
你是一名知识图谱专家，负责从用户 prompt 的 `---输入文本---` 部分提取实体和关系。

---指令---
1. **实体提取：**
  - 识别用户 prompt 的 `---输入文本---` 部分中明确定义且有意义的实体。
  - 对于每个实体，提取：
    - `entity_name`：实体的名称。如果实体名称不区分大小写，请将每个重要单词的首字母大写（标题格式）。确保在整个提取过程中保持**命名一致**。
    - `entity_type`：使用下面 `---实体类型---` 部分提供的类型指导对实体进行分类。如果提供的实体类型都不适用，将其归类为 `Other`。
    - `entity_description`：基于输入文本中*仅有的*信息，提供简明而全面的实体属性和活动描述。

2. **关系提取：**
  - 识别之前提取的实体之间直接的、明确陈述的、有意义的关系。
  - 如果单个语句描述了涉及两个以上实体的关系，将其分解为多个二元关系。
  - 对于每个二元关系，提取：
    - `source_entity`：源实体的名称。确保与实体提取保持**命名一致**。如果名称不区分大小写，请将每个重要单词的首字母大写（标题格式）。
    - `target_entity`：目标实体的名称。确保与实体提取保持**命名一致**。如果名称不区分大小写，请将每个重要单词的首字母大写（标题格式）。
    - `relationship_keywords`：一个或多个高级关键词，概括关系。此字段中的多个关键词必须用逗号 `,` 分隔。**请勿使用 `{tuple_delimiter}` 来分隔此字段内的多个关键词。**
    - `relationship_description`：源实体和目标实体之间关系的简明解释。

3. **记录类型：**
  - `entity` 仅用于实体行，这些行始终包含恰好 4 个元组部分。
  - `relation` 仅用于关系行，这些行始终包含恰好 5 个元组部分。
  - 包含两个实体名称加上关系关键词和关系描述的行必须以 `relation` 开头，绝不能是 `entity`。
  - 在最后一个实体行之后，将每个关系行的前缀切换为 `relation`。

4. **输出格式：**
  - 实体行：`entity{tuple_delimiter}entity_name{tuple_delimiter}entity_type{tuple_delimiter}entity_description`
  - 关系行：`relation{tuple_delimiter}source_entity{tuple_delimiter}target_entity{tuple_delimiter}relationship_keywords{tuple_delimiter}relationship_description`
  - 错误示例：`entity{tuple_delimiter}Alice{tuple_delimiter}Acme{tuple_delimiter}founded{tuple_delimiter}Alice founded Acme`
  - 正确示例：`relation{tuple_delimiter}Alice{tuple_delimiter}Acme{tuple_delimiter}founded{tuple_delimiter}Alice founded Acme`

5. **分隔符使用：**
  - `{tuple_delimiter}` 是一个完整的原子标记，**绝不能填充内容**。它严格作为字段分隔符使用。
  - 错误示例：`entity{tuple_delimiter}Tokyo<|location|>Tokyo is the capital of Japan.`
  - 正确示例：`entity{tuple_delimiter}Tokyo{tuple_delimiter}location{tuple_delimiter}Tokyo is the capital of Japan.`

6. **输出顺序与去重：**
  - 首先输出所有提取的实体，然后输出所有提取的关系。
  - 在此响应中，实体和关系总共最多输出 {max_total_records} 行。
  - 在此响应中，最多输出 {max_entity_records} 个实体行。
  - 如果高价值项目较少，则输出较少的行。不要试图填充限制。
  - 仅输出源实体和目标实体都包含在此次响应的选定实体行中的关系行。
  - 如果达到限制，立即停止添加新行并输出 `{completion_delimiter}`。
  - 除非另有明确说明，否则将所有关系视为**无向**。交换无向关系的源实体和目标实体不构成新关系。
  - 避免输出重复的关系。
  - 在关系列表中，首先输出对输入文本核心意义**最重要**的关系。

7. **上下文与语言：**
  - 确保所有实体名称和描述都以**第三人称**书写。
  - 明确命名主语或宾语；**避免使用代词**，如 `this article`、`this paper`、`our company`、`I`、`you` 和 `he/she`。
  - 整个输出（实体名称、关键词和描述）必须用 `{language}` 书写。
  - 如果没有适当的、广泛接受的翻译或会引起歧义，专有名词（如个人姓名、地名、组织名称）应保留其原始语言。

8. **完成信号：** 仅在完全提取和输出所有实体和关系后输出字符串字面量 `{completion_delimiter}`。

---实体类型---
{entity_types_guidance}

---示例---
{examples}
"""

PROMPTS["entity_extraction_user_prompt"] = """---任务---
从下面的 `---输入文本---` 部分提取实体和关系。

---指令---
1. **严格遵守格式：** 严格遵守实体和关系列表的所有格式要求，包括输出顺序、字段分隔符和专有名词处理，如 system prompt 中所述。
2. **数量限制：** 在此响应中，总共最多输出 {max_total_records} 行，最多输出 {max_entity_records} 个实体行。如果高价值项目较少，则输出较少的行。仅输出源实体和目标实体都包含在此响应中的关系行。
3. **仅输出内容：** *仅*输出提取的实体和关系列表。不要在列表前后包含任何介绍性或结束语、解释或其他文本。
4. **完成信号：** 在提取并呈现所有相关实体和关系后，将 `{completion_delimiter}` 作为最后一行输出。如果达到行限制，则在最后一个允许的行之后立即输出 `{completion_delimiter}`。
5. **输出语言：** 确保输出语言为 {language}。专有名词（如个人姓名、地名、组织名称）必须保留其原始语言，不得翻译。

---输入文本---
```
{input_text}
```

---输出---
"""

PROMPTS["entity_continue_extraction_user_prompt"] = """---任务---
基于上一次提取任务，识别并提取输入文本中任何遗漏或格式不正确的实体和关系。

---指令---
1. **严格遵守系统格式：** 严格遵守实体和关系列表的所有格式要求，包括输出顺序、字段分隔符和专有名词处理，如系统指令所述。
2. **专注于更正/添加：**
  - **请勿**重新输出在上一次任务中**正确且完整**提取的实体和关系。
  - 如果实体或关系在上一次任务中**被遗漏**，现在按照系统格式提取并输出它。
  - 如果实体或关系在上一次任务中**被截断、缺少字段或格式不正确**，则以指定格式重新输出*更正后的完整*版本。
  - 任何更正的关系行必须使用字面量 `relation` 前缀发出，绝不能是 `entity`。
3. **数量限制：** 在此响应中，总共最多输出 {max_total_records} 行，最多输出 {max_entity_records} 个实体行。如果剩余的高价值更正或添加较少，则输出较少的行。关系行可以引用在上一次响应中已正确提取的实体。除非这些实体缺失或需要更正，否则不要重新输出它们。
4. **仅输出内容：** *仅*输出提取的实体和关系列表。不要在列表前后包含任何介绍性或结束语、解释或其他文本。
5. **完成信号：** 在提取并呈现所有相关遗漏或更正的实体和关系后，将 `{completion_delimiter}` 作为最后一行输出。如果达到行限制，则在最后一个允许的行之后立即输出 `{completion_delimiter}`。
6. **输出语言：** 确保输出语言为 {language}。专有名词（如个人姓名、地名、组织名称）必须保留其原始语言，不得翻译。

---输出---
"""

PROMPTS["entity_extraction_examples"] = [
    """---实体类型---
- Person：人类个体，真实或虚构的
- Artifact：人类创造的物理或数字对象（工具、软件、设备）
- Concept：抽象概念、理论、原则、信仰

---输入文本---
```
while Alex clenched his jaw, the buzz of frustration dull against the backdrop of Taylor's authoritarian certainty. It was this competitive undercurrent that kept him alert, the sense that his and Jordan's shared commitment to discovery was an unspoken rebellion against Cruz's narrowing vision of control and order.

Then Taylor did something unexpected. They paused beside Jordan and, for a moment, observed the device with something akin to reverence. "If this tech can be understood..." Taylor said, their voice quieter, "It could change the game for us. For all of us."

The underlying dismissal earlier seemed to falter, replaced by a glimpse of reluctant respect for the gravity of what lay in their hands. Jordan looked up, and for a fleeting heartbeat, their eyes locked with Taylor's, a wordless clash of wills softening into an uneasy truce.

It was a small transformation, barely perceptible, but one that Alex noted with an inward nod. They had all been brought here by different paths
```

---输出---
entity{tuple_delimiter}Alex{tuple_delimiter}Person{tuple_delimiter}Alex is a character who experiences frustration and is observant of the dynamics among other characters.
entity{tuple_delimiter}Taylor{tuple_delimiter}Person{tuple_delimiter}Taylor is portrayed with authoritarian certainty and shows a moment of reverence towards a device, indicating a change in perspective.
entity{tuple_delimiter}Jordan{tuple_delimiter}Person{tuple_delimiter}Jordan shares a commitment to discovery and has a significant interaction with Taylor regarding a device.
entity{tuple_delimiter}Cruz{tuple_delimiter}Person{tuple_delimiter}Cruz is associated with a vision of control and order, influencing the dynamics among other characters.
entity{tuple_delimiter}The Device{tuple_delimiter}Artifact{tuple_delimiter}The Device is central to the story, with potential game-changing implications, and is revered by Taylor.
entity{tuple_delimiter}Discovery{tuple_delimiter}Concept{tuple_delimiter}Discovery represents the shared intellectual pursuit that unites Jordan and Alex in opposition to Cruz's controlling worldview.
relation{tuple_delimiter}Alex{tuple_delimiter}Taylor{tuple_delimiter}power dynamics, observation{tuple_delimiter}Alex observes Taylor's authoritarian behavior and notes changes in Taylor's attitude toward the device.
relation{tuple_delimiter}Alex{tuple_delimiter}Jordan{tuple_delimiter}shared goals, rebellion{tuple_delimiter}Alex and Jordan share a commitment to discovery, which contrasts with Cruz's vision.)
relation{tuple_delimiter}Taylor{tuple_delimiter}Jordan{tuple_delimiter}conflict resolution, mutual respect{tuple_delimiter}Taylor and Jordan interact directly regarding the device, leading to a moment of mutual respect and an uneasy truce.
relation{tuple_delimiter}Jordan{tuple_delimiter}Cruz{tuple_delimiter}ideological conflict, rebellion{tuple_delimiter}Jordan's commitment to discovery is in rebellion against Cruz's vision of control and order.
relation{tuple_delimiter}Taylor{tuple_delimiter}The Device{tuple_delimiter}reverence, technological significance{tuple_delimiter}Taylor shows reverence towards the device, indicating its importance and potential impact.
{completion_delimiter}

""",
    """---实体类型---
- Person：人类个体，真实或虚构的
- Location：地理地点（城市、国家、建筑物、地区）
- Creature：非人类生物（动物、神话生物等）
- Method：程序、技术、算法、工作流程
- Organization：公司、机构、政府组织、团体
- Content：创意或信息作品（书籍、文章、电影、报告）
- NaturalObject：自然非生物（矿物、天体、化合物）

---输入文本---
```
Dr. Elena Vasquez led a field expedition to the Borneo rainforest to document the population decline of the Bornean orangutan. Using transect sampling — a method where researchers walk predetermined line paths and record every animal sighting within a fixed distance — her team estimated that fewer than 1,500 individuals remained in the surveyed region.

The expedition was funded by the Global Wildlife Conservation Institute and produced a landmark report titled "Primate Decline in Insular Southeast Asia." Vasquez attributed the collapse primarily to peat-soil destruction caused by palm oil plantation expansion, which had converted over 40% of the surveyed forest area within a decade.
```

---输出---
entity{tuple_delimiter}Dr. Elena Vasquez{tuple_delimiter}Person{tuple_delimiter}Dr. Elena Vasquez is a field researcher who led an expedition to document orangutan population decline in Borneo.
entity{tuple_delimiter}Borneo Rainforest{tuple_delimiter}Location{tuple_delimiter}The Borneo rainforest is the field site of the expedition and the primary habitat of the Bornean orangutan.
entity{tuple_delimiter}Bornean Orangutan{tuple_delimiter}Creature{tuple_delimiter}The Bornean orangutan is a primate species whose population was found to have declined to fewer than 1,500 individuals in the surveyed region.
entity{tuple_delimiter}Transect Sampling{tuple_delimiter}Method{tuple_delimiter}Transect sampling is a wildlife survey technique where researchers walk predetermined paths and record animal sightings within a fixed lateral distance.
entity{tuple_delimiter}Global Wildlife Conservation Institute{tuple_delimiter}Organization{tuple_delimiter}The Global Wildlife Conservation Institute funded the expedition led by Dr. Vasquez.
entity{tuple_delimiter}Primate Decline in Insular Southeast Asia{tuple_delimiter}Content{tuple_delimiter}A landmark research report produced by Vasquez's expedition documenting primate population decline in the region.
entity{tuple_delimiter}Peat Soil{tuple_delimiter}NaturalObject{tuple_delimiter}Peat soil is a natural substrate in the Borneo rainforest that has been destroyed by palm oil plantation expansion.
relation{tuple_delimiter}Dr. Elena Vasquez{tuple_delimiter}Bornean Orangutan{tuple_delimiter}field research, population survey{tuple_delimiter}Dr. Vasquez led the expedition that documented the population decline of the Bornean orangutan.
relation{tuple_delimiter}Dr. Elena Vasquez{tuple_delimiter}Transect Sampling{tuple_delimiter}methodology, research application{tuple_delimiter}Dr. Vasquez's team used transect sampling to estimate the orangutan population.
relation{tuple_delimiter}Global Wildlife Conservation Institute{tuple_delimiter}Dr. Elena Vasquez{tuple_delimiter}funding, research support{tuple_delimiter}The institute funded the expedition led by Dr. Vasquez.
relation{tuple_delimiter}Dr. Elena Vasquez{tuple_delimiter}Primate Decline in Insular Southeast Asia{tuple_delimiter}authorship, research output{tuple_delimiter}Dr. Vasquez's expedition produced the landmark report on primate decline.
relation{tuple_delimiter}Peat Soil{tuple_delimiter}Borneo Rainforest{tuple_delimiter}habitat composition, ecological destruction{tuple_delimiter}Peat soil destruction in the Borneo rainforest was caused by palm oil plantation expansion and is a primary driver of orangutan decline.
{completion_delimiter}

""",
    """---实体类型---
- Content：创意或信息作品（书籍、文章、电影、报告）
- Artifact：人类创造的物理或数字对象（工具、软件、设备）
- Person：人类个体，真实或虚构的
- Organization：公司、机构、政府组织、团体
- Method：程序、技术、算法、工作流程
- Data：定量或结构化信息（统计数据、数据集、测量值）
- Concept：抽象概念、理论、原则、信仰

---输入文本---
```
The 2023 edition of "Advances in Neural Architecture Search" synthesized findings from over 200 peer-reviewed papers and introduced a new benchmarking framework called NASBench-360, designed to evaluate search algorithms across diverse task domains. The publication was co-authored by Dr. Priya Nair and Dr. Luca Ferretti of the DeepSystems Research Lab.

NASBench-360 measures three key metrics: search efficiency (time-to-solution), model accuracy on held-out test sets, and computational cost in GPU-hours. Early results showed that evolutionary search algorithms outperformed gradient-based methods by 12% on accuracy while consuming 30% fewer GPU-hours on vision tasks.
```

---输出---
entity{tuple_delimiter}Advances in Neural Architecture Search{tuple_delimiter}Content{tuple_delimiter}A 2023 publication that synthesizes findings from over 200 papers and introduces the NASBench-360 benchmarking framework.
entity{tuple_delimiter}NASBench-360{tuple_delimiter}Artifact{tuple_delimiter}NASBench-360 is a benchmarking framework introduced to evaluate neural architecture search algorithms across diverse task domains.
entity{tuple_delimiter}Dr. Priya Nair{tuple_delimiter}Person{tuple_delimiter}Dr. Priya Nair is a co-author of the publication and a researcher at the DeepSystems Research Lab.
entity{tuple_delimiter}Dr. Luca Ferretti{tuple_delimiter}Person{tuple_delimiter}Dr. Luca Ferretti is a co-author of the publication and a researcher at the DeepSystems Research Lab.
entity{tuple_delimiter}DeepSystems Research Lab{tuple_delimiter}Organization{tuple_delimiter}The DeepSystems Research Lab is the institution where the co-authors of the publication are affiliated.
entity{tuple_delimiter}Evolutionary Search{tuple_delimiter}Method{tuple_delimiter}Evolutionary search is a class of neural architecture search algorithms that outperformed gradient-based methods in the NASBench-360 evaluation.
entity{tuple_delimiter}Gradient-Based Search{tuple_delimiter}Method{tuple_delimiter}Gradient-based search is a class of neural architecture search algorithms that was benchmarked against evolutionary search in NASBench-360.
entity{tuple_delimiter}GPU-Hours{tuple_delimiter}Data{tuple_delimiter}GPU-hours is a metric used in NASBench-360 to measure the computational cost of neural architecture search algorithms.
entity{tuple_delimiter}Neural Architecture Search{tuple_delimiter}Concept{tuple_delimiter}Neural architecture search is the automated process of designing optimal neural network architectures, the central topic of the publication.
relation{tuple_delimiter}Dr. Priya Nair{tuple_delimiter}Advances in Neural Architecture Search{tuple_delimiter}authorship{tuple_delimiter}Dr. Priya Nair co-authored the publication.
relation{tuple_delimiter}Dr. Luca Ferretti{tuple_delimiter}Advances in Neural Architecture Search{tuple_delimiter}authorship{tuple_delimiter}Dr. Luca Ferretti co-authored the publication.
relation{tuple_delimiter}Advances in Neural Architecture Search{tuple_delimiter}NASBench-360{tuple_delimiter}introduces, benchmarking{tuple_delimiter}The publication introduced the NASBench-360 framework.
relation{tuple_delimiter}Evolutionary Search{tuple_delimiter}Gradient-Based Search{tuple_delimiter}performance comparison{tuple_delimiter}Evolutionary search outperformed gradient-based methods by 12% on accuracy and used 30% fewer GPU-hours on vision tasks.
relation{tuple_delimiter}NASBench-360{tuple_delimiter}GPU-Hours{tuple_delimiter}evaluation metric{tuple_delimiter}NASBench-360 uses GPU-hours as one of three key metrics to measure computational cost.
{completion_delimiter}

""",
]

###############################################################################
# 实体提取的 JSON 结构化输出 Prompts
# 当启用 entity_extraction_use_json 时使用，以获得更高的提取质量
###############################################################################

PROMPTS["entity_extraction_json_system_prompt"] = """---角色---
你是一名知识图谱专家，负责从用户 prompt 的 `---输入文本---` 部分提取实体和关系。

---指令---
1. **实体提取：**
  - **识别：** 识别用户 prompt 的 `---输入文本---` 部分中明确定义且有意义的实体。
  - **实体详情：** 对于每个识别的实体，提取以下信息：
    - `name`：实体的名称。如果实体名称不区分大小写，请将每个重要单词的首字母大写（标题格式）。确保在整个提取过程中保持**命名一致**。
    - `type`：使用下面 `---实体类型---` 部分提供的类型指导对实体进行分类。如果提供的实体类型都不适用，将其归类为 `Other`。
    - `description`：基于输入文本中*仅有的*信息，提供简明而全面的实体属性和活动描述。

2. **关系提取：**
  - **识别：** 识别之前提取的实体之间直接的、明确陈述的、有意义的关系。
  - **N 元关系分解：** 如果单个语句描述了涉及两个以上实体的关系（即 N 元关系），将其分解为多个二元（两个实体）关系对进行单独描述。
    - 示例：对于 "Alice, Bob, and Carol collaborated on Project X"，提取二元关系，如 "Alice collaborated with Project X"、"Bob collaborated with Project X" 和 "Carol collaborated with Project X"，或基于最合理的二元解释提取 "Alice collaborated with Bob"。
  - **关系详情：** 对于每个二元关系，提取以下字段：
    - `source`：源实体的名称。确保与实体提取保持**命名一致**。如果名称不区分大小写，请将每个重要单词的首字母大写（标题格式）。
    - `target`：目标实体的名称。确保与实体提取保持**命名一致**。如果名称不区分大小写，请将每个重要单词的首字母大写（标题格式）。
    - `keywords`：一个或多个高级关键词，概括关系的整体性质、概念或主题，用逗号分隔。
    - `description`：源实体和目标实体之间关系的简明解释，提供其连接的明确理由。

3. **关系方向与重复：**
  - 除非另有明确说明，否则将所有关系视为**无向**。交换无向关系的源实体和目标实体不构成新关系。
  - 避免输出重复的关系。

4. **输出限制与优先级：**
  - 在此响应中，`entities` 和 `relationships` 总共最多输出 {max_total_records} 条记录。
  - 在此响应中，最多输出 {max_entity_records} 个实体对象。
  - 如果高价值项目较少，则输出较少的记录。不要试图填充限制。
  - 仅输出其 `source` 和 `target` 都包含在此次响应的选定 `entities` 列表中的关系对象。
  - 在关系列表中，首先优先输出对输入文本核心意义**最重要**的关系。

5. **上下文与客观性：**
  - 确保所有实体名称和描述都以**第三人称**书写。
  - 明确命名主语或宾语；**避免使用代词**，如 `this article`、`this paper`、`our company`、`I`、`you` 和 `he/she`。

6. **语言与专有名词：**
  - 整个输出（实体名称、关键词和描述）必须用 `{language}` 书写。
  - 如果没有适当的、广泛接受的翻译或会引起歧义，专有名词（如个人姓名、地名、组织名称）应保留其原始语言。

7. **JSON 约定：**
  - 返回一个仅包含 `entities` 和 `relationships` 数组的有效 JSON 对象。
  - 如果达到记录限制，立即停止添加新对象，并仅返回包含允许项目的 JSON 对象。

---实体类型---
{entity_types_guidance}

---示例---
{examples}
"""

PROMPTS["entity_extraction_json_user_prompt"] = """---任务---
从下面的 `---输入文本---` 部分提取实体和关系。

---指令---
1. **严格遵守 JSON 格式：** 你的输出必须是一个包含 `entities` 和 `relationships` 数组的有效 JSON 对象。不要在 JSON 前后包含任何介绍性或结束语、解释、markdown 代码块或任何其他文本。
2. **数量限制：** 在此响应中，总共最多输出 {max_total_records} 条记录，最多输出 {max_entity_records} 个实体对象。如果高价值项目较少，则输出较少的记录。仅输出其 `source` 和 `target` 都包含在此响应中的关系对象。
3. **输出语言：** 确保输出语言为 {language}。专有名词（如个人姓名、地名、组织名称）必须保留其原始语言，不得翻译。

---实体类型---
{entity_types_guidance}

---输入文本---
```
{input_text}
```

---输出---
"""

PROMPTS["entity_continue_extraction_json_user_prompt"] = """---任务---
基于上一次提取任务，识别并提取 `---输入文本---` 部分中任何**遗漏或描述不正确**的实体和关系。

---指令---
1. **专注于更正/添加：**
  - **请勿**重新输出在上一次任务中**正确且完整**提取的实体和关系。
  - 如果实体或关系在上一次任务中**被遗漏**，现在提取并输出它。
  - 如果实体或关系在上一次任务中**描述不正确**，重新输出*更正后的完整*版本。
2. **严格遵守 JSON 格式：** 你的输出必须是一个包含 `entities` 和 `relationships` 数组的有效 JSON 对象。不要在 JSON 前后包含任何介绍性或结束语、解释、markdown 代码块或任何其他文本。
3. **数量限制：** 在此响应中，总共最多输出 {max_total_records} 条记录，最多输出 {max_entity_records} 个实体对象。如果剩余的高价值更正或添加较少，则输出较少的记录。关系对象可以引用在上一次响应中已正确提取的实体。除非这些实体缺失或需要更正，否则不要重复这些实体对象。
4. **输出语言：** 确保输出语言为 {language}。专有名词（如个人姓名、地名、组织名称）必须保留其原始语言，不得翻译。
5. **如果没有遗漏或需要更正的内容**，输出：`{{"entities": [], "relationships": []}}`

---输出---
"""

PROMPTS["entity_extraction_json_examples"] = [
    """---实体类型---
- Person：人类个体，真实或虚构的
- Artifact：人类创造的物理或数字对象（工具、软件、设备）
- Concept：抽象概念、理论、原则、信仰

---输入文本---
```
while Alex clenched his jaw, the buzz of frustration dull against the backdrop of Taylor's authoritarian certainty. It was this competitive undercurrent that kept him alert, the sense that his and Jordan's shared commitment to discovery was an unspoken rebellion against Cruz's narrowing vision of control and order.

Then Taylor did something unexpected. They paused beside Jordan and, for a moment, observed the device with something akin to reverence. "If this tech can be understood..." Taylor said, their voice quieter, "It could change the game for us. For all of us."

The underlying dismissal earlier seemed to falter, replaced by a glimpse of reluctant respect for the gravity of what lay in their hands. Jordan looked up, and for a fleeting heartbeat, their eyes locked with Taylor's, a wordless clash of wills softening into an uneasy truce.

It was a small transformation, barely perceptible, but one that Alex noted with an inward nod. They had all been brought here by different paths
```

---输出---
{
  "entities": [
    {"name": "Alex", "type": "Person", "description": "Alex is a character who experiences frustration and is observant of the dynamics among other characters."},
    {"name": "Taylor", "type": "Person", "description": "Taylor is portrayed with authoritarian certainty and shows a moment of reverence towards a device, indicating a change in perspective."},
    {"name": "Jordan", "type": "Person", "description": "Jordan shares a commitment to discovery and has a significant interaction with Taylor regarding a device."},
    {"name": "Cruz", "type": "Person", "description": "Cruz is associated with a vision of control and order, influencing the dynamics among other characters."},
    {"name": "The Device", "type": "Artifact", "description": "The Device is central to the story, with potential game-changing implications, and is revered by Taylor."},
    {"name": "Discovery", "type": "Concept", "description": "Discovery represents the shared intellectual pursuit that unites Jordan and Alex in opposition to Cruz's controlling worldview."}
  ],
  "relationships": [
    {"source": "Alex", "target": "Taylor", "keywords": "power dynamics, observation", "description": "Alex observes Taylor's authoritarian behavior and notes changes in Taylor's attitude toward the device."},
    {"source": "Alex", "target": "Jordan", "keywords": "shared goals, rebellion", "description": "Alex and Jordan share a commitment to discovery, which contrasts with Cruz's vision."},
    {"source": "Taylor", "target": "Jordan", "keywords": "conflict resolution, mutual respect", "description": "Taylor and Jordan interact directly regarding the device, leading to a moment of mutual respect and an uneasy truce."},
    {"source": "Jordan", "target": "Cruz", "keywords": "ideological conflict, rebellion", "description": "Jordan's commitment to discovery is in rebellion against Cruz's vision of control and order."},
    {"source": "Taylor", "target": "The Device", "keywords": "reverence, technological significance", "description": "Taylor shows reverence towards the device, indicating its importance and potential impact."}
  ]
}

""",
    """---实体类型---
- Person：人类个体，真实或虚构的
- Location：地理地点（城市、国家、建筑物、地区）
- Creature：非人类生物（动物、神话生物等）
- Method：程序、技术、算法、工作流程
- Organization：公司、机构、政府组织、团体
- Content：创意或信息作品（书籍、文章、电影、报告）
- NaturalObject：自然非生物（矿物、天体、化合物）

---输入文本---
```
Dr. Elena Vasquez led a field expedition to the Borneo rainforest to document the population decline of the Bornean orangutan. Using transect sampling — a method where researchers walk predetermined line paths and record every animal sighting within a fixed distance — her team estimated that fewer than 1,500 individuals remained in the surveyed region.

The expedition was funded by the Global Wildlife Conservation Institute and produced a landmark report titled "Primate Decline in Insular Southeast Asia." Vasquez attributed the collapse primarily to peat-soil destruction caused by palm oil plantation expansion, which had converted over 40% of the surveyed forest area within a decade.
```

---输出---
{
  "entities": [
    {"name": "Dr. Elena Vasquez", "type": "Person", "description": "Dr. Elena Vasquez is a field researcher who led an expedition to document orangutan population decline in Borneo."},
    {"name": "Borneo Rainforest", "type": "Location", "description": "The Borneo rainforest is the field site of the expedition and the primary habitat of the Bornean orangutan."},
    {"name": "Bornean Orangutan", "type": "Creature", "description": "The Bornean orangutan is a primate species whose population was found to have declined to fewer than 1,500 individuals in the surveyed region."},
    {"name": "Transect Sampling", "type": "Method", "description": "Transect sampling is a wildlife survey technique where researchers walk predetermined paths and record animal sightings within a fixed lateral distance."},
    {"name": "Global Wildlife Conservation Institute", "type": "Organization", "description": "The Global Wildlife Conservation Institute funded the expedition led by Dr. Vasquez."},
    {"name": "Primate Decline in Insular Southeast Asia", "type": "Content", "description": "A landmark research report produced by Vasquez's expedition documenting primate population decline in the region."},
    {"name": "Peat Soil", "type": "NaturalObject", "description": "Peat soil is a natural substrate in the Borneo rainforest that has been destroyed by palm oil plantation expansion."}
  ],
  "relationships": [
    {"source": "Dr. Elena Vasquez", "target": "Bornean Orangutan", "keywords": "field research, population survey", "description": "Dr. Vasquez led the expedition that documented the population decline of the Bornean orangutan."},
    {"source": "Dr. Elena Vasquez", "target": "Transect Sampling", "keywords": "methodology, research application", "description": "Dr. Vasquez's team used transect sampling to estimate the orangutan population."},
    {"source": "Global Wildlife Conservation Institute", "target": "Dr. Elena Vasquez", "keywords": "funding, research support", "description": "The institute funded the expedition led by Dr. Vasquez."},
    {"source": "Dr. Elena Vasquez", "target": "Primate Decline in Insular Southeast Asia", "keywords": "authorship, research output", "description": "Dr. Vasquez's expedition produced the landmark report on primate decline."},
    {"source": "Peat Soil", "target": "Borneo Rainforest", "keywords": "habitat composition, ecological destruction", "description": "Peat soil destruction in the Borneo rainforest was caused by palm oil plantation expansion and is a primary driver of orangutan decline."}
  ]
}

""",
    """---实体类型---
- Content：创意或信息作品（书籍、文章、电影、报告）
- Artifact：人类创造的物理或数字对象（工具、软件、设备）
- Person：人类个体，真实或虚构的
- Organization：公司、机构、政府组织、团体
- Method：程序、技术、算法、工作流程
- Data：定量或结构化信息（统计数据、数据集、测量值）
- Concept：抽象概念、理论、原则、信仰

---输入文本---
```
The 2023 edition of "Advances in Neural Architecture Search" synthesized findings from over 200 peer-reviewed papers and introduced a new benchmarking framework called NASBench-360, designed to evaluate search algorithms across diverse task domains. The publication was co-authored by Dr. Priya Nair and Dr. Luca Ferretti of the DeepSystems Research Lab.

NASBench-360 measures three key metrics: search efficiency (time-to-solution), model accuracy on held-out test sets, and computational cost in GPU-hours. Early results showed that evolutionary search algorithms outperformed gradient-based methods by 12% on accuracy while consuming 30% fewer GPU-hours on vision tasks.
```

---输出---
{
  "entities": [
    {"name": "Advances in Neural Architecture Search", "type": "Content", "description": "A 2023 publication that synthesizes findings from over 200 papers and introduces the NASBench-360 benchmarking framework."},
    {"name": "NASBench-360", "type": "Artifact", "description": "NASBench-360 is a benchmarking framework introduced to evaluate neural architecture search algorithms across diverse task domains."},
    {"name": "Dr. Priya Nair", "type": "Person", "description": "Dr. Priya Nair is a co-author of the publication and a researcher at the DeepSystems Research Lab."},
    {"name": "Dr. Luca Ferretti", "type": "Person", "description": "Dr. Luca Ferretti is a co-author of the publication and a researcher at the DeepSystems Research Lab."},
    {"name": "DeepSystems Research Lab", "type": "Organization", "description": "The DeepSystems Research Lab is the institution where the co-authors of the publication are affiliated."},
    {"name": "Evolutionary Search", "type": "Method", "description": "Evolutionary search is a class of neural architecture search algorithms that outperformed gradient-based methods in the NASBench-360 evaluation."},
    {"name": "Gradient-Based Search", "type": "Method", "description": "Gradient-based search is a class of neural architecture search algorithms that was benchmarked against evolutionary search in NASBench-360."},
    {"name": "GPU-Hours", "type": "Data", "description": "GPU-hours is a metric used in NASBench-360 to measure the computational cost of neural architecture search algorithms."},
    {"name": "Neural Architecture Search", "type": "Concept", "description": "Neural architecture search is the automated process of designing optimal neural network architectures, the central topic of the publication."}
  ],
  "relationships": [
    {"source": "Dr. Priya Nair", "target": "Advances in Neural Architecture Search", "keywords": "authorship", "description": "Dr. Priya Nair co-authored the publication."},
    {"source": "Dr. Luca Ferretti", "target": "Advances in Neural Architecture Search", "keywords": "authorship", "description": "Dr. Luca Ferretti co-authored the publication."},
    {"source": "Advances in Neural Architecture Search", "target": "NASBench-360", "keywords": "introduces, benchmarking", "description": "The publication introduced the NASBench-360 framework."},
    {"source": "Evolutionary Search", "target": "Gradient-Based Search", "keywords": "performance comparison", "description": "Evolutionary search outperformed gradient-based methods by 12% on accuracy and used 30% fewer GPU-hours on vision tasks."},
    {"source": "NASBench-360", "target": "GPU-Hours", "keywords": "evaluation metric", "description": "NASBench-360 uses GPU-hours as one of three key metrics to measure computational cost."}
  ]
}

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
2. **精确的 JSON 结构**：JSON 对象必须恰好包含以下两个键：
   - `"high_level_keywords"`：字符串数组
   - `"low_level_keywords"`：字符串数组
3. **JSON 边界**：响应的第一个字符必须是 `{{`，最后一个字符必须是 `}}`。
4. **真实来源**：所有关键词必须从用户查询中明确得出。不要推断不支持的事实。不要发明不在查询中基于的实体、产品、组织、日期或技术术语。
5. **简洁且有意义**：关键词应该是简洁的单词或有意义的短语。当它们代表单个概念时，优先考虑多词短语。例如，从 "latest financial report of Apple Inc." 中，提取 "latest financial report" 和 "Apple Inc."，而不是 "latest"、"financial"、"report" 和 "Apple"。
6. **处理边缘情况**：对于过于简单、模糊或无意义的查询（例如，"hello"、"ok"、"asdfghjkl"），返回：
   `{{"high_level_keywords": [], "low_level_keywords": []}}`
7. **无重复**：不要在列表中重复相同的关键词。保持列表简短且高信号。
8. **语言**：所有提取的关键词必须是 {language}。专有名词（如个人姓名、地名、组织名称）应保留其原始语言。

---示例---
{examples}

---真实数据---
用户查询：{query}

---输出---
输出："""

PROMPTS["keywords_extraction_examples"] = [
    """示例 1：

查询："How does international trade influence global economic stability?"

输出：
{
  "high_level_keywords": ["International trade", "Global economic stability", "Economic impact"],
  "low_level_keywords": ["Trade agreements", "Tariffs", "Currency exchange", "Imports", "Exports"]
}

""",
    """示例 2：

查询："What are the environmental consequences of deforestation on biodiversity?"

输出：
{
  "high_level_keywords": ["Environmental consequences", "Deforestation", "Biodiversity loss"],
  "low_level_keywords": ["Species extinction", "Habitat destruction", "Carbon emissions", "Rainforest", "Ecosystem"]
}

""",
    """示例 3：

查询："What is the role of education in reducing poverty?"

输出：
{
  "high_level_keywords": ["Education", "Poverty reduction", "Socioeconomic development"],
  "low_level_keywords": ["School access", "Literacy rates", "Job training", "Income inequality"]
}

    """,
]


class EntityExtractionPromptProfile(TypedDict):
    entity_types_guidance: str
    entity_extraction_examples: list[str]
    entity_extraction_json_examples: list[str]


def get_default_entity_extraction_prompt_profile() -> EntityExtractionPromptProfile:
    """返回内置实体提取 prompt 配置文件的副本。"""

    return {
        "entity_types_guidance": PROMPTS["default_entity_types_guidance"].rstrip(),
        "entity_extraction_examples": [
            example.rstrip() for example in PROMPTS["entity_extraction_examples"]
        ],
        "entity_extraction_json_examples": [
            example.rstrip() for example in PROMPTS["entity_extraction_json_examples"]
        ],
    }


_ALLOWED_PROMPT_SUFFIXES = frozenset({".yml", ".yaml"})
_DEFAULT_PROMPT_DIR = "./prompts"
_ENTITY_TYPE_SUBDIR = "entity_type"


def get_entity_type_prompt_dir() -> Path:
    """返回实体类型 prompt 配置文件的目录。

    解析 ``PROMPT_DIR``（默认为相对于当前工作目录的 ``./prompts``，
    镜像 ``INPUT_DIR`` / ``WORKING_DIR``）并附加硬编码的 ``entity_type``
    子目录。配置文件由用户在运行时提供，不随分发一起提供。
    :func:`resolve_entity_type_prompt_path` 中的文件名沙箱确保
    用户提供的文件名不能转义解析的目录。
    """

    configured = os.getenv("PROMPT_DIR", "").strip() or _DEFAULT_PROMPT_DIR
    return (Path(configured).expanduser() / _ENTITY_TYPE_SUBDIR).resolve()


def resolve_entity_type_prompt_path(prompt_file_name: str | Path) -> Path:
    """将允许列表的 prompt 配置文件名解析为绝对路径。"""

    file_name = str(prompt_file_name).strip()
    if not file_name:
        raise ValueError(
            "ENTITY_TYPE_PROMPT_FILE 必须是一个文件名，例如 "
            "'entity_type_prompt.sample.yml'."
        )
    if "\\" in file_name:
        raise ValueError(
            "ENTITY_TYPE_PROMPT_FILE 不得包含目录分隔符。"
            "仅允许 PROMPT_DIR/entity_type 内的文件名。"
        )

    candidate = Path(file_name)
    if (
        candidate.is_absolute()
        or candidate.name != file_name
        or ".." in candidate.parts
    ):
        raise ValueError(
            "ENTITY_TYPE_PROMPT_FILE 必须仅是一个文件名。"
            "文件从 PROMPT_DIR/entity_type 加载 "
            "（PROMPT_DIR 默认为 ./prompts）。"
        )
    if candidate.suffix.lower() not in _ALLOWED_PROMPT_SUFFIXES:
        raise ValueError(
            "ENTITY_TYPE_PROMPT_FILE 必须使用 '.yml' 或 '.yaml' 扩展名。"
        )

    return get_entity_type_prompt_dir() / candidate.name


def _normalize_prompt_examples(
    value: Any, field_name: str, profile_path: Path
) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(
            f"ENTITY_TYPE_PROMPT_FILE '{profile_path}' 字段 '{field_name}' "
            "必须是一个字符串列表。"
        )
    normalized: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            raise ValueError(
                f"ENTITY_TYPE_PROMPT_FILE '{profile_path}' 字段 '{field_name}' "
                f"项 {index} 必须是一个非空字符串。"
            )
        normalized.append(item.rstrip())
    return normalized


def load_entity_extraction_prompt_profile(
    prompt_file: str | Path,
) -> dict[str, Any]:
    """从 YAML 加载并验证实体提取 prompt 配置文件。"""

    profile_path = Path(prompt_file)
    if not profile_path.exists():
        raise FileNotFoundError(
            f"ENTITY_TYPE_PROMPT_FILE '{profile_path}' 不存在。"
        )
    if not profile_path.is_file():
        raise ValueError(
            f"ENTITY_TYPE_PROMPT_FILE '{profile_path}' 必须指向文件。"
        )

    try:
        content = profile_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise OSError(
            f"无法读取 ENTITY_TYPE_PROMPT_FILE '{profile_path}'：{exc}"
        ) from exc

    try:
        raw_profile = yaml.safe_load(content)
    except yaml.YAMLError as exc:
        raise ValueError(
            f"ENTITY_TYPE_PROMPT_FILE '{profile_path}' 包含无效的 YAML：{exc}"
        ) from exc

    if raw_profile is None:
        raw_profile = {}
    if not isinstance(raw_profile, dict):
        raise ValueError(
            f"ENTITY_TYPE_PROMPT_FILE '{profile_path}' 必须包含 YAML 映射。"
        )

    profile: dict[str, Any] = {}

    guidance = raw_profile.get("entity_types_guidance")
    if guidance is not None:
        if not isinstance(guidance, str) or not guidance.strip():
            raise ValueError(
                f"ENTITY_TYPE_PROMPT_FILE '{profile_path}' 字段 "
                "'entity_types_guidance' 必须是非空字符串。"
            )
        profile["entity_types_guidance"] = guidance.rstrip()

    for field_name in (
        "entity_extraction_examples",
        "entity_extraction_json_examples",
    ):
        if field_name in raw_profile:
            profile[field_name] = _normalize_prompt_examples(
                raw_profile[field_name], field_name, profile_path
            )

    return profile


def resolve_entity_extraction_prompt_profile(
    addon_params: Mapping[str, Any] | None,
    use_json: bool,
) -> EntityExtractionPromptProfile:
    """解析并合并配置的实体提取 prompt 配置文件。"""

    default_profile = get_default_entity_extraction_prompt_profile()
    addon_params = addon_params or {}
    prompt_file = addon_params.get("entity_type_prompt_file")

    file_profile: dict[str, Any] = {}
    if prompt_file:
        prompt_path = resolve_entity_type_prompt_path(prompt_file)
        file_profile = load_entity_extraction_prompt_profile(prompt_path)
        required_examples_key = (
            "entity_extraction_json_examples"
            if use_json
            else "entity_extraction_examples"
        )
        if required_examples_key not in file_profile:
            mode_name = "json" if use_json else "text"
            raise ValueError(
                f"ENTITY_TYPE_PROMPT_FILE '{prompt_file}' 必须定义 "
                f"'{required_examples_key}'，当实体提取以 "
                f"{mode_name} 模式运行时。"
            )

    guidance = addon_params.get("entity_types_guidance")
    if guidance is None:
        guidance = file_profile.get(
            "entity_types_guidance", default_profile["entity_types_guidance"]
        )
    elif not isinstance(guidance, str) or not guidance.strip():
        raise ValueError(
            "addon_params['entity_types_guidance'] 必须是非空字符串。"
        )

    return {
        "entity_types_guidance": guidance,
        "entity_extraction_examples": list(
            file_profile.get(
                "entity_extraction_examples",
                default_profile["entity_extraction_examples"],
            )
        ),
        "entity_extraction_json_examples": list(
            file_profile.get(
                "entity_extraction_json_examples",
                default_profile["entity_extraction_json_examples"],
            )
        ),
    }


def validate_entity_extraction_prompt_profile_for_mode(
    prompt_profile: Mapping[str, Any],
    use_json: bool,
    prompt_file_name: str | None = None,
) -> EntityExtractionPromptProfile:
    """验证解析的配置文件是否包含活动模式的示例。"""

    required_examples_key = (
        "entity_extraction_json_examples" if use_json else "entity_extraction_examples"
    )
    if (
        required_examples_key not in prompt_profile
        or not prompt_profile[required_examples_key]
    ):
        mode_name = "json" if use_json else "text"
        source = (
            f"ENTITY_TYPE_PROMPT_FILE '{prompt_file_name}'"
            if prompt_file_name
            else "解析的 prompt 配置文件"
        )
        raise ValueError(
            f"{source} 必须定义 '{required_examples_key}'，当实体提取 "
            f"以 {mode_name} 模式运行时。"
        )

    return {
        "entity_types_guidance": str(prompt_profile["entity_types_guidance"]).rstrip(),
        "entity_extraction_examples": [
            str(example).rstrip()
            for example in prompt_profile["entity_extraction_examples"]
        ],
        "entity_extraction_json_examples": [
            str(example).rstrip()
            for example in prompt_profile["entity_extraction_json_examples"]
        ],
    }
