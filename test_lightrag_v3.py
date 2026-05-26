"""
LightRAG Demo - 通用 LLM + API Embedding (OpenAI 兼容)

支持的 LLM 提供商（需支持 OpenAI 兼容 API）:
- OpenAI: https://api.openai.com/v1
- DeepSeek: https://api.deepseek.com/v1
- Moonshot: https://api.moonshot.cn/v1
- MiniMax: https://api.minimax.chat/v1
- 等等...

配置说明:
只需修改下方 LLM 和 Embedding 配置区域的参数即可切换不同的服务
"""

import os
import asyncio
import nest_asyncio
from pathlib import Path
import logging
from datetime import datetime

from dotenv import load_dotenv
from lightrag import LightRAG, QueryParam
from lightrag.llm.openai import openai_complete_if_cache, openai_embed
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

logger.info(f"Log file: {LOG_FILE}")

nest_asyncio.apply()

WORKING_DIR = "./rag_storage_v3"
PDF_INPUT_DIR = "./pdf_file_input"  # PDF 文件目录


# ============================================================
#                    配置区域
# ============================================================

# -------- LLM 配置 (从 .env 读取) --------
LLM_API_KEY = os.environ.get("LLM_API_KEY", "")
LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "https://api.minimax.chat/v1")
LLM_MODEL = os.environ.get("LLM_MODEL", "MiniMax-M2.5")

# -------- Embedding 配置 (从 .env 读取) --------
EMBEDDING_API_KEY = os.environ.get("EMBEDDING_API_KEY", "")
EMBEDDING_BASE_URL = os.environ.get("EMBEDDING_BASE_URL", "https://api.minimax.chat/v1")
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "text-embedding-v3")
EMBEDDING_DIM = int(os.environ.get("EMBEDDING_DIM", "1536"))  # 根据模型调整维度


# ==================== 验证配置 ====================
if not LLM_API_KEY or LLM_API_KEY == "your-api-key-here":
    raise ValueError(
        "Please set LLM_API_KEY!\n"
        "Set via env: export LLM_API_KEY='your-key'\n"
        "Or modify the LLM_API_KEY variable directly"
    )

if not EMBEDDING_API_KEY:
    raise ValueError(
        "Please set EMBEDDING_API_KEY!\n"
        "Set via env: export EMBEDDING_API_KEY='your-key'\n"
        "Or modify the EMBEDDING_API_KEY variable directly"
    )

if not os.path.exists(WORKING_DIR):
    os.mkdir(WORKING_DIR)


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


# ==================== Embedding 函数 (OpenAI 兼容 API) ====================
@wrap_embedding_func_with_attrs(
    embedding_dim=EMBEDDING_DIM,
    max_token_size=8192,
    model_name=EMBEDDING_MODEL,
)
async def embedding_func(texts: list[str]) -> "np.ndarray":
    """Generate embeddings using OpenAI compatible API"""
    return await openai_embed(
        texts=texts,
        model=EMBEDDING_MODEL,
        base_url=EMBEDDING_BASE_URL,
        api_key=EMBEDDING_API_KEY,
    )


# ==================== 文档提取函数 (使用 pypdf) ====================
from pypdf import PdfReader


def extract_pdf_content(file_path: str | Path, password: str = None) -> str:
    """
    Extract PDF content using pypdf

    Args:
        file_path: PDF file path
        password: Optional password for encrypted PDF

    Returns:
        str: Extracted text content
    """
    reader = PdfReader(file_path, password=password)

    text_parts = []
    for page in reader.pages:
        text_parts.append(page.extract_text())

    return "\n".join(text_parts)


def process_pdf_directory(pdf_dir: str) -> list[tuple[str, str]]:
    """
    Process all PDF files in directory

    Args:
        pdf_dir: PDF directory path

    Returns:
        list[tuple[str, str]]: (filename, content) list
    """
    pdf_path = Path(pdf_dir)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF directory not found: {pdf_dir}")

    pdf_files = list(pdf_path.glob("*.pdf"))
    if not pdf_files:
        raise FileNotFoundError(f"No PDF files in: {pdf_dir}")

    results = []
    for pdf_file in pdf_files:
        content = extract_pdf_content(pdf_file)
        results.append((pdf_file.name, content))
        logger.info(f"  Read: {pdf_file.name} ({len(content)} chars)")

    return results


# ==================== 初始化 RAG ====================
async def initialize_rag():
    rag = LightRAG(
        working_dir=WORKING_DIR,
        llm_model_func=llm_model_func,
        embedding_func=embedding_func,
        llm_model_name=LLM_MODEL,
        addon_params={
            "language": "Chinese"
        },
    )

    await rag.initialize_storages()
    return rag


# ==================== 主程序 ====================
def main():
    logger.info(f"Initializing LightRAG...")
    logger.info(f"  LLM: {LLM_MODEL} @ {LLM_BASE_URL}")
    logger.info(f"  Embedding: {EMBEDDING_MODEL} @ {EMBEDDING_BASE_URL}")
    logger.info(f"  Embedding Dim: {EMBEDDING_DIM}")
    logger.info('-'*50)

    rag = asyncio.run(initialize_rag())

    # Process PDFs from directory
    logger.info('+'*50)
    logger.info(f"Reading PDFs from: {PDF_INPUT_DIR}")

    pdf_docs = process_pdf_directory(PDF_INPUT_DIR)
    logger.info(f"Found {len(pdf_docs)} PDF files")

    for filename, content in pdf_docs:
        logger.info(f"Inserting: {filename}...")
        rag.insert(content)
        logger.info(f"  Done: {filename}")

    logger.info(f"All PDFs inserted successfully!")

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
