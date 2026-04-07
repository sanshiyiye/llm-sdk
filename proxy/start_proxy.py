import sys
import os
import builtins
import socket
import subprocess
from urllib.parse import urlparse
from pathlib import Path
from dotenv import load_dotenv

# 设置标准输出的编码为 utf-8，解决 Windows 下打印 emoji 报错的问题
if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

def check_db_connection(db_url):
    if not db_url or not db_url.startswith("postgres"):
        return True
    
    parsed = urlparse(db_url)
    host = parsed.hostname or "localhost"
    port = parsed.port or 5432
    
    print(f"🔄 正在检查 PostgreSQL 数据库连接 ({host}:{port})...")
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(3)
        s.connect((host, port))
        s.close()
        print("✅ PostgreSQL 数据库连接成功！\n")
        return True
    except Exception as e:
        print(f"❌ 无法连接到 PostgreSQL 数据库 ({host}:{port})")
        print(f"   错误详情: {e}")
        print("   👉 请确保你的 PostgreSQL 容器或服务已经启动！")
        return False

def ensure_prisma_client():
    schema_path = Path(sys.prefix) / "Lib" / "site-packages" / "litellm" / "proxy" / "schema.prisma"
    if not schema_path.exists():
        return

    print("🔧 正在生成 Prisma Client...")
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"

    completed = subprocess.run(
        [
            sys.executable,
            "-X",
            "utf8",
            "-m",
            "prisma",
            "py",
            "generate",
            "--schema",
            str(schema_path),
        ],
        cwd=str(schema_path.parent),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    if completed.returncode != 0:
        print("❌ Prisma Client 生成失败")
        if completed.stdout.strip():
            print(completed.stdout.strip())
        if completed.stderr.strip():
            print(completed.stderr.strip())
        sys.exit(completed.returncode)

    print("✅ Prisma Client 已准备完成")

_originalOpen = builtins.open
def _utf8Open(file, *args, **kwargs):
    mode = args[0] if args else kwargs.get("mode", "r")
    if "b" not in mode:
        kwargs.setdefault("encoding", "utf-8")
    return _originalOpen(file, *args, **kwargs)
builtins.open = _utf8Open

# 加载 .env 文件中的环境变量
proxy_dir = Path(__file__).parent
root_env_path = proxy_dir.parent / '.env'
env_path = proxy_dir / '.env'
config_path = proxy_dir / 'config' / 'config.yaml'
if root_env_path.exists():
    load_dotenv(root_env_path)
    print(f"✅ 已加载根目录环境变量文件: {root_env_path}")

if env_path.exists():
    load_dotenv(env_path, override=True)
    print(f"✅ 已加载环境变量文件: {env_path}")
else:
    print(f"⚠️  未找到 .env 文件，使用系统环境变量: {env_path}")

# 从环境变量获取配置（优先级：系统环境变量 > .env 文件 > 默认值）
openai_api_key = os.getenv("OPENAI_API_KEY") or "sk-your-openai-key-here"
siliconflow_api_key = os.getenv("SILICONFLOW_API_KEY") or "sk-your-siliconflow-key-here"
litellm_master_key = os.getenv("LITELLM_MASTER_KEY") or "sk-123456"
database_url = os.getenv("DATABASE_URL") or os.getenv("LITELLM_DB_URL") or ""

# 设置环境变量
os.environ["OPENAI_API_KEY"] = openai_api_key
os.environ["SILICONFLOW_API_KEY"] = siliconflow_api_key
os.environ["LITELLM_MASTER_KEY"] = litellm_master_key
if database_url:
    os.environ["DATABASE_URL"] = database_url
    os.environ["LITELLM_DB_URL"] = database_url

# 打印配置信息（隐藏敏感信息）
print(f"🔑 LiteLLM Master Key: {'*' * 10}{litellm_master_key[-4:] if len(litellm_master_key) > 4 else '****'}")
print(f"🔑 OpenAI API Key: {'*' * 10}{openai_api_key[-4:] if len(openai_api_key) > 4 else '****'}")
print(f"🔑 SiliconFlow API Key: {'*' * 10}{siliconflow_api_key[-4:] if len(siliconflow_api_key) > 4 else '****'}")
if database_url:
    print("🗄️ 已启用 PostgreSQL 审计日志配置")
    if not check_db_connection(database_url):
        sys.exit(1)
    ensure_prisma_client()
else:
    print("ℹ️ 未配置 DATABASE_URL，跳过 PostgreSQL 连接检查")

sys.argv = ["litellm", "--config", str(config_path), "--port", "4000"]

from litellm.proxy.proxy_cli import run_server
run_server()
