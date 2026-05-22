# LightRAG 流程图

本文档展示 LightRAG 的核心处理流程，包括文档索引流程和查询流程。

---

## 1. 文档索引流程

从文档输入到知识图谱构建的完整流程：

```mermaid
flowchart TD
    Start([开始: 文档输入]) --> CheckFormat{文档格式?}

    CheckFormat -->|纯文本| TextProcess["文本处理"]
    CheckFormat -->|DOCX| NativeParser["原生解析器<br/>native_parser/docx"]
    CheckFormat -->|PDF/Office/图片| ParseRouting["解析路由<br/>parser_routing.py"]

    ParseRouting --> MinerU["MinerU服务<br/>external_parser/mineru"]
    ParseRouting --> Docling["Docling服务<br/>external_parser/docling"]

    NativeParser --> ExtractContent["内容提取"]
    MinerU --> ExtractContent
    Docling --> ExtractContent

    ExtractContent --> CheckMultimodal{包含多模态<br/>内容?}

    CheckMultimodal -->|是<br/>图片/表格| VLMAnalysis["VLM多模态分析<br/>analyze_multimodal()<br/>使用VLM角色LLM"]
    CheckMultimodal -->|否| ChunkingStage["分块阶段"]

    VLMAnalysis --> ChunkingStage

    ChunkingStage --> ChunkingStrategy{分块策略?}

    ChunkingStrategy -->|F| TokenChunk["Token分块<br/>chunking_by_token_size"]
    ChunkingStrategy -->|R| RecursiveChunk["递归字符分块<br/>chunking_by_recursive_character"]
    ChunkingStrategy -->|V| SemanticChunk["语义向量分块<br/>chunking_by_semantic_vector"]
    ChunkingStrategy -->|P| ParagraphChunk["段落语义分块<br/>chunking_by_paragraph_semantic"]

    TokenChunk --> EntityExtract
    RecursiveChunk --> EntityExtract
    SemanticChunk --> EntityExtract
    ParagraphChunk --> EntityExtract

    EntityExtract["实体提取<br/>extract_entities()<br/>operate.py<br/>使用EXTRACT角色LLM"] --> EntityProcessing["实体处理<br/>- 边界检查<br/>- 去重<br/>- 合并相似实体"]

    EntityProcessing --> GenerateEmbed["生成嵌入<br/>EmbeddingFunc"]

    GenerateEmbed --> UpdateVectorDB["更新向量数据库<br/>BaseVectorStorage.upsert()"]
    GenerateEmbed --> UpdateGraphDB["更新图数据库<br/>BaseGraphStorage.upsert_node()<br/>.upsert_edge()"]
    GenerateEmbed --> UpdateChunkDB["更新块存储<br/>BaseKVStorage.upsert()"]

    UpdateVectorDB --> UpdateDocStatus
    UpdateGraphDB --> UpdateDocStatus
    UpdateChunkDB --> UpdateDocStatus

    UpdateDocStatus["更新文档状态<br/>DocStatusStorage.set_status()"] --> CheckDone{检查完成状态}

    CheckDone -->|全部块完成| IndexDone["index_done_callback()<br/>持久化操作"]
    CheckDone -->|部分完成| WaitForChunks["等待其他块"]

    WaitForChunks --> CheckDone

    IndexDone --> EndIndex([索引完成])

    TextProcess --> ChunkingStage

    classDef startEndClass fill:#c8e6c9,stroke:#2e7d32,stroke-width:2px,rx:10,ry:10
    classDef processClass fill:#bbdefb,stroke:#1565c0,stroke-width:2px
    classDef decisionClass fill:#fff9c4,stroke:#f57f17,stroke-width:2px,rx:5,ry:5
    classDef llmClass fill:#d1c4e9,stroke:#4527a0,stroke-width:2px

    class Start,EndIndex startEndClass
    class TextProcess,NativeParser,ParseRouting,MinerU,Docling,ExtractContent,VLMAnalysis,ChunkingStage,TokenChunk,RecursiveChunk,SemanticChunk,ParagraphChunk,EntityExtract,EntityProcessing,GenerateEmbed,UpdateVectorDB,UpdateGraphDB,UpdateChunkDB,UpdateDocStatus,IndexDone,WaitForChunks processClass
    class CheckFormat,CheckMultimodal,ChunkingStrategy,CheckDone decisionClass
    class VLMAnalysis,EntityExtract llmClass
```

---

## 2. 查询流程

从用户查询到返回结果的完整流程：

```mermaid
flowchart TD
    QueryStart([开始: 用户查询]) --> QueryAPI["API入口<br/>/query 或 /query/stream"]

    QueryAPI --> ParseQueryParams["解析查询参数<br/>QueryParam<br/>- mode: 查询模式<br/>- only_need_context<br/>- only_need_prompt<br/>- stream: 是否流式"]

    ParseQueryParams --> QueryMode{查询模式?}

    QueryMode -->|naive| NaivePath["简单向量检索<br/>naive_query()"]
    QueryMode -->|local| LocalPath["局部检索<br/>kg_query(mode='local')"]
    QueryMode -->|global| GlobalPath["全局检索<br/>kg_query(mode='global')"]
    QueryMode -->|hybrid| HybridPath["混合检索<br/>kg_query(mode='hybrid')"]
    QueryMode -->|mix| MixPath["混合模式<br/>kg_query(mode='mix')"]
    QueryMode -->|bypass| BypassPath["绕过检索<br/>直接生成"]

    NaivePath --> BuildContext
    LocalPath --> KeywordExtraction
    GlobalPath --> KeywordExtraction
    HybridPath --> KeywordExtraction
    MixPath --> KeywordExtraction
    BypassPath --> BuildPrompt

    KeywordExtraction["关键词提取<br/>get_keywords_from_query()<br/>使用KEYWORDS角色LLM<br/>HL: 高层关键词<br/>LL: 低层关键词"] --> BuildContext

    BuildContext["构建查询上下文<br/>_build_query_context()"]

    BuildContext --> NaiveRetrieval{检索类型?}

    NaiveRetrieval -->|naive| ChunkVector["块向量检索<br/>chunks_vdb.query()"]
    NaiveRetrieval -->|local| EntityVector["实体向量检索<br/>entities_vdb.query()"]
    NaiveRetrieval -->|global| RelationVector["关系向量检索<br/>relationships_vdb.query()"]
    NaiveRetrieval -->|hybrid/mix| HybridVector["混合向量检索<br/>entities + relations"]

    ChunkVector --> SelectChunks
    EntityVector --> SelectChunks
    RelationVector --> SelectChunks
    HybridVector --> SelectChunks

    SelectChunks["选择相关块<br/>根据权重/相似度"] --> CheckMixMode{是否mix模式?}

    CheckMixMode -->|是| AddChunkVector["添加块向量检索<br/>chunks_vdb.query()"]
    CheckMixMode -->|否| CheckRerank
    AddChunkVector --> CheckRerank

    CheckRerank{启用Rerank?} -->|是| RerankChunks["Rerank块<br/>rerank_chunks()<br/>重新排序"]
    CheckRerank -->|否| BuildPrompt
    RerankChunks --> BuildPrompt

    BuildPrompt["构建提示词<br/>_parse_global_options<br/>包含实体、关系、<br/>块上下文"] --> CheckOutput{输出类型?}

    CheckOutput -->|only_need_context| ReturnContext([返回上下文])
    CheckOutput -->|only_need_prompt| ReturnPrompt([返回提示词])
    CheckOutput -->|stream| StreamLLM["流式LLM生成<br/>使用QUERY角色LLM"]
    CheckOutput -->|默认| NormalLLM["正常LLM生成<br/>使用QUERY角色LLM"]

    StreamLLM --> StreamResponse([流式响应])
    NormalLLM --> BuildResult["构建结果<br/>QueryResult"]

    BuildResult --> AddReferences{包含引用?}

    AddReferences -->|是| WithRefs["添加引用列表<br/>reference_list"]
    AddReferences -->|否| FinalResult

    WithRefs --> FinalResult
    ReturnContext --> FinalResult
    ReturnPrompt --> FinalResult
    StreamResponse --> FinalResult

    FinalResult([返回查询结果])

    classDef startEndClass fill:#c8e6c9,stroke:#2e7d32,stroke-width:2px,rx:10,ry:10
    classDef processClass fill:#bbdefb,stroke:#1565c0,stroke-width:2px
    classDef decisionClass fill:#fff9c4,stroke:#f57f17,stroke-width:2px,rx:5,ry:5
    classDef llmClass fill:#d1c4e9,stroke:#4527a0,stroke-width:2px

    class QueryStart,FinalResult,ReturnContext,ReturnPrompt,StreamResponse startEndClass
    class QueryAPI,ParseQueryParams,NaivePath,LocalPath,GlobalPath,HybridPath,MixPath,BypassPath,KeywordExtraction,BuildContext,ChunkVector,EntityVector,RelationVector,HybridVector,SelectChunks,AddChunkVector,RerankChunks,BuildPrompt,StreamLLM,NormalLLM,BuildResult,WithRefs processClass
    class QueryMode,NaiveRetrieval,CheckMixMode,CheckRerank,CheckOutput,AddReferences decisionClass
    class KeywordExtraction,StreamLLM,NormalLLM llmClass
```

---

## 3. 查询模式详解

```mermaid
graph TB
    Query["用户查询"] --> ModeSelection{选择查询模式}

    ModeSelection --> M1["naive<br/>纯向量检索"]
    ModeSelection --> M2["local<br/>局部检索"]
    ModeSelection --> M3["global<br/>全局检索"]
    ModeSelection --> M4["hybrid<br/>混合检索"]
    ModeSelection --> M5["mix<br/>混合+向量"]

    M1 --> D1["检索: 文档块向量<br/>适用: 简单问答"]
    M2 --> D2["检索: 实体向量 + 1-hop邻居<br/>适用: 实体相关问题"]
    M3 --> D3["检索: 关系向量 + 实体<br/>适用: 全局关系问题"]
    M4 --> D4["检索: 实体 + 关系向量<br/>适用: 复杂推理"]
    M5 --> D5["检索: 实体 + 关系 + 块向量<br/>适用: 全面检索"]

    classDef modeClass fill:#e1bee7,stroke:#4a148c,stroke-width:2px
    classDef descClass fill:#c5cae9,stroke:#1a237e,stroke-width:2px

    class M1,M2,M3,M4,M5 modeClass
    class D1,D2,D3,D4,D5 descClass
```

---

## 4. 存储交互流程

```mermaid
sequenceDiagram
    participant User as 用户
    participant API as FastAPI
    participant Core as LightRAG
    participant Pipeline as 处理管道
    participant Extract as 实体提取
    participant LLM as LLM服务
    participant Embed as 嵌入服务
    participant KV as KV存储
    participant VDB as 向量存储
    participant GDB as 图存储

    User->>API: 上传文档
    API->>Core: ainsert()
    Core->>Pipeline: 解析文档

    Pipeline->>Extract: 发送文本块
    Extract->>LLM: 提取实体和关系
    LLM-->>Extract: 返回实体/关系

    Extract->>Embed: 生成嵌入
    Embed-->>Extract: 返回向量

    Extract->>KV: 保存块数据
    Extract->>VDB: 保存实体/关系向量
    Extract->>GDB: 保存图节点和边

    GDB->>KV: 保存图快照

    Core-->>API: 处理完成
    API-->>User: 返回结果
```

---

## 5. 查询交互流程

```mermaid
sequenceDiagram
    participant User as 用户
    participant API as FastAPI
    participant Core as LightRAG
    participant Keys as 关键词提取
    participant VDB as 向量存储
    participant GDB as 图存储
    participant Build as 上下文构建
    participant LLM as LLM服务

    User->>API: 发送查询
    API->>Core: aquery()

    alt local/global/hybrid模式
        Core->>Keys: 提取关键词
        Keys->>LLM: HL/LL关键词提取
        LLM-->>Keys: 返回关键词

        Core->>VDB: 向量检索
        VDB-->>Core: 返回相关实体/关系

        Core->>GDB: 获取子图
        GDB-->>Core: 返回图数据
    else naive模式
        Core->>VDB: 块向量检索
        VDB-->>Core: 返回相关块
    end

    Core->>Build: 构建提示词上下文
    Build-->>Core: 返回格式化上下文

    Core->>LLM: 生成回答
    LLM-->>Core: 返回响应

    Core-->>API: 返回结果
    API-->>User: 返回回答
```

---

## 6. 文档删除流程

```mermaid
flowchart TD
    Start([开始: 删除文档]) --> GetDocID["获取文档ID"]

    GetDocID --> GetStatus["获取文档状态<br/>DocStatusStorage.get()"]

    GetStatus --> CheckStatus{文档状态?}

    CheckStatus -->|已索引| GetChunks["获取文档关联的所有块<br/>从chunks KV存储"]
    CheckStatus -->|处理中/失败| DeleteStatus["直接删除状态记录"]

    GetChunks --> GetEntityIDs["获取块关联的实体ID"]

    GetEntityIDs --> GetEntitySources["获取每个实体的source_ids"]

    GetEntitySources --> CheckOtherDocs{实体被其他<br/>文档引用?}

    CheckOtherDocs -->|是| RemoveDocRef["从source_ids移除当前文档"]
    CheckOtherDocs -->|否| MarkDelete["标记实体待删除"]

    RemoveDocRef --> CheckNextEntity
    MarkDelete --> CheckNextEntity

    CheckNextEntity{还有实体?} -->|是| GetEntitySources
    CheckNextEntity -->|否| DeleteMarked["删除标记的实体<br/>从向量存储和图存储"]

    DeleteMarked --> Regraph["重新构建知识图谱<br/>rebuild_knowledge_from_chunks()"]

    Regraph --> DeleteStatus["删除文档状态记录"]

    DeleteStatus --> End([完成])

    classDef startEndClass fill:#c8e6c9,stroke:#2e7d32,stroke-width:2px,rx:10,ry:10
    classDef processClass fill:#bbdefb,stroke:#1565c0,stroke-width:2px
    classDef decisionClass fill:#fff9c4,stroke:#f57f17,stroke-width:2px,rx:5,ry:5

    class Start,End startEndClass
    class GetDocID,GetStatus,GetChunks,GetEntityIDs,GetEntitySources,RemoveDocRef,MarkDelete,DeleteMarked,Regraph,DeleteStatus processClass
    class CheckStatus,CheckOtherDocs,CheckNextEntity decisionClass
```

---

## 关键处理阶段说明

### 索引流程关键点

1. **文档解析**: 支持原生解析(DOCX)和外部服务解析(MinerU/Docling)
2. **多模态处理**: VLM分析图片、表格等非文本内容
3. **分块策略**: 四种策略可选，适应不同文档类型
4. **实体提取**: LLM提取实体和关系，构建知识图谱
5. **并行处理**: 支持多块并行处理，提高效率

### 查询流程关键点

1. **查询模式**: 六种模式适应不同查询需求
2. **关键词提取**: 分为高层(HL)和低层(LL)关键词
3. **向量检索**: 基于嵌入相似度检索相关内容
4. **图遍历**: 获取相关实体的邻居信息
5. **Rerank**: 可选的重排序提高检索精度
6. **上下文构建**: 整合检索结果构建完整上下文
7. **LLM生成**: 基于上下文生成最终回答

### LLM 角色

LightRAG 为不同处理阶段使用专门的 LLM 配置：

| 角色 | 用途 | 配置参数 |
|-----|------|---------|
| EXTRACT | 实体和关系提取 | `EXTRACT_MODEL` |
| QUERY | 查询响应生成 | `QUERY_MODEL` |
| KEYWORDS | 关键词提取 | `KEYWORDS_MODEL` |
| VLM | 多模态内容分析 | `VLM_MODEL` |
