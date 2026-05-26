

# 1. 从官方源安装 torch（CPU 版本）
pip install torch --index-url https://download.pytorch.org/whl/cpu

# 2. 从清华源安装 transformers
pip install transformers -i https://pypi.tuna.tsinghua.edu.cn/simple

# 3. 安装 sentence-transformers
pip install sentence-transformers -i https://pypi.tuna.tsinghua.edu.cn/simple

pip install "lightrag-hku[api]" -i https://pypi.tuna.tsinghua.edu.cn/simple


pip install pypdf -i https://pypi.tuna.tsinghua.edu.cn/simple



git init


 # 5. 关联 GitHub 仓库
  git remote add origin https://github.com/bingofhy/LightRag-tmp

  # 6. 设置主分支名为 main
  git branch -M main

  # 7. 推送到 GitHub
  git push -u origin main