"""
下载 bge-small-zh-v1.5 模型到本地
"""
import os

# 配置 HuggingFace 镜像加速下载
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

from transformers import AutoTokenizer, AutoModel

model_name = "BAAI/bge-small-zh-v1.5"
save_dir = "./models/bge-small-zh-v1.5"

print(f"Using mirror: {os.environ['HF_ENDPOINT']}")
print(f"Downloading {model_name}...")
print(f"Save directory: {save_dir}")

print(f"Downloading {model_name}...")
print(f"Save directory: {save_dir}")

# 下载 tokenizer
print("\nDownloading tokenizer...")
tokenizer = AutoTokenizer.from_pretrained(model_name)
tokenizer.save_pretrained(save_dir)
print("Tokenizer saved!")

# 下载模型
print("\nDownloading model...")
model = AutoModel.from_pretrained(model_name)
model.save_pretrained(save_dir)
print("Model saved!")

print(f"\nDone! Model saved to: {save_dir}")
