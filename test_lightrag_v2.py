"""
LightRAG Demo - 通用 LLM + 本地 Embedding

支持的 LLM 提供商（需支持 OpenAI 兼容 API）:
- OpenAI: https://api.openai.com/v1
- DeepSeek: https://api.deepseek.com/v1
- Moonshot: https://api.moonshot.cn/v1
- 等等...

配置说明:
只需修改下方 LLM 配置区域的三个参数即可切换不同的 LLM
"""

import os
import asyncio
import nest_asyncio
import numpy as np
from pathlib import Path
from io import BytesIO
import logging
from datetime import datetime

from dotenv import load_dotenv
from lightrag import LightRAG, QueryParam
from lightrag.llm.openai import openai_complete_if_cache
from lightrag.utils import wrap_embedding_func_with_attrs

# 加载 .env 配置
load_dotenv()

# ==================== 日志配置 ====================
LOG_FILE = f"./logs/lightrag_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

# 配置日志 - 同时输出到文件和控制台
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

logger.info(f"日志文件: {LOG_FILE}")

nest_asyncio.apply()

WORKING_DIR = "./rag_storage_v2"
PDF_FILE = "./test.pdf"  # 修改为你的 PDF 文件路径


# ============================================================
#                    配置区域
# ============================================================

# -------- LLM 配置 (从 .env 读取) --------
LLM_API_KEY = os.environ.get("LLM_API_KEY", "")
LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "https://api.minimax.chat/v1")
LLM_MODEL = os.environ.get("LLM_MODEL", "MiniMax-M2.5")

# -------- Embedding 配置 (本地模型) --------
EMBEDDING_MODEL_PATH = "./models/bge-small-zh-v1.5"
EMBEDDING_DIM = 512


# ==================== 验证配置 ====================
if not LLM_API_KEY or LLM_API_KEY == "your-api-key-here":
    raise ValueError(
        "请设置 LLM_API_KEY！\n"
        "可以通过环境变量设置: export LLM_API_KEY='your-key'\n"
        "或直接修改脚本中的 LLM_API_KEY 变量"
    )

if not os.path.exists(WORKING_DIR):
    os.mkdir(WORKING_DIR)


# ==================== 加载本地 Embedding 模型 ====================
from transformers import AutoTokenizer, AutoModel
import torch

logger.info(f"Loading local embedding model: {EMBEDDING_MODEL_PATH}...")
embedding_tokenizer = AutoTokenizer.from_pretrained(EMBEDDING_MODEL_PATH)
embedding_model = AutoModel.from_pretrained(EMBEDDING_MODEL_PATH)
logger.info("Embedding model loaded!")


# ==================== LLM 函数 (通用 OpenAI 兼容 API) ====================
async def llm_model_func(prompt, system_prompt=None, history_messages=[], **kwargs):
    return await openai_complete_if_cache(
        LLM_MODEL,
        prompt,
        system_prompt=system_prompt,
        history_messages=history_messages,
        base_url=LLM_BASE_URL,
        api_key=LLM_API_KEY,
        **kwargs,
    )


# ==================== Embedding 函数 (本地模型) ====================
@wrap_embedding_func_with_attrs(
    embedding_dim=EMBEDDING_DIM,
    max_token_size=8192,
    model_name=EMBEDDING_MODEL_PATH,
)
async def embedding_func(texts: list[str]) -> np.ndarray:
    """使用本地 bge-small-zh-v1.5 模型生成 embedding"""
    global embedding_model

    # 检测设备
    if torch.cuda.is_available():
        device = torch.device("cuda")
    else:
        device = torch.device("cpu")

    # 将模型移到设备
    model_on_device = embedding_model.to(device)

    # Tokenize
    encoded_inputs = embedding_tokenizer(
        texts, padding=True, truncation=True, max_length=512, return_tensors="pt"
    ).to(device)

    # 生成 embedding
    with torch.no_grad():
        model_output = model_on_device(**encoded_inputs)
        # 使用 CLS token 的 embedding
        embeddings = model_output.last_hidden_state[:, 0]
        # 归一化
        embeddings = torch.nn.functional.normalize(embeddings, p=2, dim=1)

    return embeddings.cpu().numpy()


# ==================== 文档提取函数 (从 LightRAG 导入) ====================
# 从 LightRAG 内部导入文档处理函数
from lightrag.api.routers.document_routes import (
    _extract_pdf_pypdf,
    _convert_with_docling,
    _extract_docx,
    _extract_pptx,
    _extract_xlsx,
)


def extract_pdf_content(file_path: str | Path, password: str = None) -> str:
    """
    提取 PDF 内容 - 使用 LightRAG 内部的 pypdf 方法

    Args:
        file_path: PDF 文件路径
        password: 可选的 PDF 密码（用于加密 PDF）

    Returns:
        str: 提取的文本内容

    Raises:
        Exception: PDF 加密且密码错误或未提供密码
    """
    with open(file_path, "rb") as f:
        file_bytes = f.read()

    return _extract_pdf_pypdf(file_bytes, password)


# ==================== 初始化 RAG ====================
async def initialize_rag():
    rag = LightRAG(
        working_dir=WORKING_DIR,
        llm_model_func=llm_model_func,
        embedding_func=embedding_func,
        llm_model_name=LLM_MODEL,
        addon_params={
            "language": "Chinese"  # 指定使用中文提取实体
        },
    )

    await rag.initialize_storages()
    return rag


# ==================== 主程序 ====================
def main():
    # 验证 PDF 文件
    if not os.path.exists(PDF_FILE):
        raise FileNotFoundError(
            f"'{PDF_FILE}' not found. "
            f"Please put your PDF file in the current directory."
        )

    logger.info(f"Initializing LightRAG...")
    logger.info(f"  LLM: {LLM_MODEL} @ {LLM_BASE_URL}")
    logger.info(f"  Embedding: Local {EMBEDDING_MODEL_PATH}")
    logger.info(f"  Device: {'CUDA' if torch.cuda.is_available() else 'CPU'}")
    logger.info('-'*50)

    rag = asyncio.run(initialize_rag())

    # 插入 PDF - 使用 LightRAG 内部方法提取
    logger.info('+'*50)
    logger.info(f"Processing PDF: {PDF_FILE}")

    # 使用封装的 PDF 提取函数
    text_content = extract_pdf_content(PDF_FILE)

    logger.info(f"Extracted {len(text_content)} characters from PDF")
    rag.insert(text_content)
    logger.info("PDF inserted successfully!")

    # 测试问答
    query = "小米公司什么时候开始造车的？"  # 修改你的问题

    logger.info("\n" + "="*50)
    logger.info("Naive Search:")
    logger.info("="*50)
    naive_result = rag.query(query, param=QueryParam(mode="naive"))
    logger.info(f"\n{naive_result}")

    logger.info("\n" + "="*50)
    logger.info("Local Search:")
    logger.info("="*50)
    local_result = rag.query(query, param=QueryParam(mode="local"))
    logger.info(f"\n{local_result}")

    logger.info("\n" + "="*50)
    logger.info("Global Search:")
    logger.info("="*50)
    global_result = rag.query(query, param=QueryParam(mode="global"))
    logger.info(f"\n{global_result}")

    logger.info("\n" + "="*50)
    logger.info("Hybrid Search:")
    logger.info("="*50)
    hybrid_result = rag.query(query, param=QueryParam(mode="hybrid"))
    logger.info(f"\n{hybrid_result}")


if __name__ == "__main__":
    main()
