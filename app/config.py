import os
import json
import threading
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from dotenv import load_dotenv

# ============================================================
# 环境修复（必须在其他导入之前执行）
# ============================================================

# 修复 conda 环境 SSL 证书路径问题
# 注意：conda 有时会设置 SSL_CERT_FILE 指向不存在的路径，必须校验
_cert_needs_fix = True
_current_cert = os.environ.get("SSL_CERT_FILE", "")
if _current_cert:
    if Path(_current_cert).exists():
        _cert_needs_fix = False

if _cert_needs_fix:
    _certifi_paths = [
        Path(os.environ.get("CONDA_PREFIX", "")) / "Lib" / "site-packages" / "certifi" / "cacert.pem",
        Path(__file__).parent.parent / ".venv" / "Lib" / "site-packages" / "certifi" / "cacert.pem",
    ]
    for _cp in _certifi_paths:
        if _cp.exists():
            os.environ["SSL_CERT_FILE"] = str(_cp)
            break
    else:
        # 终极降级：删除错误的环境变量，让 httpx 自己找证书
        if "SSL_CERT_FILE" in os.environ:
            del os.environ["SSL_CERT_FILE"]

# 修复 OLLAMA_HOST 如果未设置
if "OLLAMA_HOST" not in os.environ:
    os.environ["OLLAMA_HOST"] = "http://127.0.0.1:11434"

# ============================================================

# 加载环境变量（始终从 app/ 目录加载，不依赖 CWD）
_APP_DIR = Path(__file__).parent
load_dotenv(_APP_DIR / ".env")

# AI 配置
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
OLLAMA_BASE_URL = "http://127.0.0.1:11434"
#OLLAMA_BASE_URL = "http://192.168.115.1:11434"


# ============================================================
# DatabaseConfig — 单库配置
# ============================================================

@dataclass
class DatabaseConfig:
    name: str
    display_name: str
    host: str
    port: int
    user: str
    password: str
    database: str
    description: str
    enabled: bool
    knowledge_dir: str  # 相对于 app/ 的路径，如 "knowledge/epmp"

    @property
    def knowledge_abs(self) -> str:
        """知识库绝对路径"""
        return str(_APP_DIR / self.knowledge_dir)


# ============================================================
# 数据库注册表加载与切换
# ============================================================

_DATABASES_PATH = _APP_DIR / "databases.json"
_databases_cache: Optional[Dict] = None
_current_db: Optional[DatabaseConfig] = None
_lock = threading.Lock()


def _load_databases_raw() -> dict:
    """加载 databases.json 原始数据"""
    global _databases_cache
    if _databases_cache is None:
        with open(_DATABASES_PATH, "r", encoding="utf-8") as f:
            _databases_cache = json.load(f)
    return _databases_cache


def get_database_names() -> List[str]:
    """返回所有启用的数据库名称列表（供前端下拉框）"""
    raw = _load_databases_raw()
    names = []
    for name, info in raw.get("databases", {}).items():
        if info.get("enabled", True):
            names.append(name)
    return names


def _make_config(db_name: str) -> DatabaseConfig:
    """根据数据库名构建 DatabaseConfig"""
    raw = _load_databases_raw()
    info = raw["databases"].get(db_name)
    if not info:
        raise ValueError(f"数据库 '{db_name}' 在 databases.json 中不存在")
    password = os.getenv(info.get("password_env", ""), "")
    return DatabaseConfig(
        name=info["name"],
        display_name=info.get("display_name", info["name"]),
        host=info.get("host", "127.0.0.1"),
        port=info.get("port", 3306),
        user=info.get("user", "root"),
        password=password,
        database=info.get("database", info["name"]),
        description=info.get("description", ""),
        enabled=info.get("enabled", True),
        knowledge_dir=info.get("knowledge_dir", f"knowledge/{db_name}"),
    )


def switch_database(db_name: str) -> DatabaseConfig:
    """切换当前数据库，返回新的 DatabaseConfig"""
    global _current_db
    with _lock:
        _current_db = _make_config(db_name)
        # 更新模块级变量（向后兼容）
        _sync_module_globals(_current_db)
        return _current_db


def get_current_db_config() -> DatabaseConfig:
    """获取当前选中的数据库配置"""
    global _current_db
    if _current_db is None:
        # 首次调用：自动加载 active_db
        raw = _load_databases_raw()
        default = raw.get("active_db", "epmp")
        _current_db = _make_config(default)
        _sync_module_globals(_current_db)
    return _current_db


def _sync_module_globals(cfg: DatabaseConfig):
    """同步模块级全局变量，保持向后兼容"""
    global DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME
    DB_HOST = cfg.host
    DB_PORT = cfg.port
    DB_USER = cfg.user
    DB_PASSWORD = cfg.password
    DB_NAME = cfg.database


# ============================================================
# 路径辅助函数（替代旧的模块级常量）
# ============================================================

def get_schema_json_path() -> str:
    return os.path.join(get_current_db_config().knowledge_abs, "final_super_schema_by_ai.json")


def get_chroma_db_path() -> str:
    return os.path.join(get_current_db_config().knowledge_abs, "schema_chroma_db")


def get_few_shot_db_path() -> str:
    return os.path.join(get_current_db_config().knowledge_abs, "few_shot_chroma_db")


def get_synonyms_path() -> str:
    return os.path.join(get_current_db_config().knowledge_abs, "domain_synonyms.json")


def get_table_knowledge_path() -> str:
    return os.path.join(get_current_db_config().knowledge_abs, "table_relationships.json")


def get_few_shot_json_path() -> str:
    return os.path.join(get_current_db_config().knowledge_abs, "few_shot_examples.json")


def get_staging_json_path() -> str:
    return os.path.join(get_current_db_config().knowledge_abs, "few_shot_examples_staging.json")


# ============================================================
# 向后兼容：模块级数据库变量（由 switch_database / get_current_db_config 自动填充）
# ============================================================
DB_HOST = ""
DB_PORT = 0
DB_USER = ""
DB_PASSWORD = ""
DB_NAME = ""

# 旧模块级路径常量（标记为废弃，子模块应改用路径函数）
CURRENT_DIR = str(_APP_DIR)
JSON_SCHEMA_PATH = None      # deprecated → 用 get_schema_json_path()
CHROMA_DB_PATH = None        # deprecated → 用 get_chroma_db_path()
FEW_SHOT_DB_PATH = None      # deprecated → 用 get_few_shot_db_path()
