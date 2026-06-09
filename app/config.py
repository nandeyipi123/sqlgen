import os
from pathlib import Path
from dotenv import load_dotenv

# 加载环境变量（始终从 app/ 目录加载，不依赖 CWD）
load_dotenv(Path(__file__).parent / ".env")

# AI 配置
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
OLLAMA_BASE_URL = "http://127.0.0.1:11434"
#OLLAMA_BASE_URL = "http://192.168.115.1:11434"

# 数据库配置 (从环境变量读取，默认值用于开发)
DB_HOST = os.getenv("DB_HOST", "10.11.0.95")
DB_PORT = int(os.getenv("DB_PORT", "10050"))
DB_USER = os.getenv("DB_USER", "readonlyuser")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "epmp")

# 文件路径配置
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
JSON_SCHEMA_PATH = os.path.join(CURRENT_DIR, "final_super_schema_by_ai.json")
CHROMA_DB_PATH = os.path.join(CURRENT_DIR, "schema_chroma_db")
FEW_SHOT_DB_PATH = os.path.join(CURRENT_DIR, "few_shot_chroma_db")