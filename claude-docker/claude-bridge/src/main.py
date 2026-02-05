import logging
from logging.handlers import TimedRotatingFileHandler
import os
import subprocess
import time
import hashlib
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Optional, Tuple, Any

# 📡 [설정] SSH 접속 정보
SSH_HOST = os.getenv("SSH_HOST", "claude-ssh-server")
SSH_USER = os.getenv("SSH_USER", "claudeuser")
SSH_PASS = os.getenv("SSH_PASS", "1234")

# 📝 [설정] 로깅 설정
logger = logging.getLogger("claude_bridge")

def setup_logging():
    """일일 로그 회전 설정 (7일 보관)"""
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    log_file = os.path.join(log_dir, "claude-bridge.log")
    
    formatter = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Rotating File Handler (Daily)
    file_handler = TimedRotatingFileHandler(
        filename=log_file,
        when='midnight',
        interval=1,
        backupCount=7,
        encoding='utf-8'
    )
    file_handler.suffix = "%Y-%m-%d"
    file_handler.setFormatter(formatter)
    
    # Console Handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    
    logger.setLevel(logging.INFO)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

setup_logging()


# 🔗 [설정] Claude Monitor URL (있으면 ANTHROPIC_BASE_URL로 전달)
CLAUDE_MONITOR_URL = os.getenv("CLAUDE_MONITOR_URL", "")

# 📋 [최신 모델 목록] 2025년 1월 기준 실제 지원 모델
CLAUDE_MODELS = {
    "claude-opus-4-5-20251101": "claude-opus-4-5-20251101",
    "claude-sonnet-4-5-20250929": "claude-sonnet-4-5-20250929",
    "claude-haiku-4-5-20251001": "claude-haiku-4-5-20251001",
    "claude-opus": "opus",
    "claude-sonnet": "sonnet",
    "claude-haiku": "haiku",
}

GEMINI_MODELS = {
    "gemini-2.5-pro": "gemini-2.5-pro",
    "gemini-2.5-flash": "gemini-2.5-flash",
    "gemini-3-pro": "gemini-3-pro",
    "gemini-3-flash": "gemini-3-flash",
    "gemini-auto": "auto",
    "gemini-pro": "pro",
    "gemini-flash": "flash",
}

CODEX_MODELS = {
    "codex-gpt-5.2-codex": "gpt-5.2-codex",
    "codex-gpt-5.1-codex-max": "gpt-5.1-codex-max",
    "codex-gpt-5.1-codex": "gpt-5.1-codex",
    "codex-gpt-5.1-codex-mini": "gpt-5.1-codex-mini",
    "codex-gpt-5-codex": "gpt-5-codex",
    "codex-gpt-5-codex-mini": "gpt-5-codex-mini",
    "codex-gpt-5.2": "gpt-5.2",
    "codex-gpt-5.1": "gpt-5.1",
    "codex-gpt-5": "gpt-5",
    "codex-o4-mini": "o4-mini",
}

# ⚙️ [설정] 도구별 설정
TOOL_CONFIG = {
    "claude": {
        "bin": "claude",
        "base_args": ["--dangerously-skip-permissions", "-p"],
        "model_flag": "--model",
        "session_flag": None,
        "resume_flag": "--resume",           # 기존 세션 이어가기
        "models": CLAUDE_MODELS,
        "default_model": "sonnet",
        "version_cmd": ["claude", "--version"],
        "supports_monitor": True,
        "supports_resume": True,             # resume 지원 여부
    },
    "gemini": {
        "bin": "gemini",
        "base_args": ["-y", "--sandbox=false"],  # sandbox 비활성화로 /workspace 쓰기 허용
        "model_flag": "--model",
        "session_flag": None,
        "resume_flag": "--resume latest",
        "models": GEMINI_MODELS,
        "default_model": "auto",
        "version_cmd": ["gemini", "--version"],
        "supports_monitor": False,
        "output_format": "--output-format json",
        "supports_resume": True,
    },
    "codex": {
        "bin": "codex",
        "base_args": ["exec", "-s", "workspace-write", "--skip-git-repo-check", "--add-dir", "/workspace"],
        "model_flag": "-m",
        "session_flag": None,
        "resume_flag": None,
        "models": CODEX_MODELS,
        "default_model": "gpt-5-codex",
        "version_cmd": ["codex", "--version"],
        "supports_monitor": False,
        "supports_resume": False,
    }
}

# 실제로 서비스할 모델 목록 (서버 시작 시 업데이트됨)
AVAILABLE_TOOLS: Dict[str, bool] = {}
SUPPORTED_MODELS: List[str] = []
MODEL_MAPPING: Dict[str, Tuple[str, str]] = {}



def get_ssh_base_cmd() -> List[str]:
    """SSH 기본 명령어 생성"""
    return [
        "sshpass", "-p", SSH_PASS,
        "ssh", "-o", "StrictHostKeyChecking=no",
        "-o", "ConnectTimeout=5",
        f"{SSH_USER}@{SSH_HOST}"
    ]


def log_remote_execution(session_dir: str, command: str, return_code: int, stdout: str, stderr: str):
    """원격 workspace/logs 디렉토리에 실행 로그 중앙 저장"""
    try:
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 로그 저장할 중앙 디렉토리
        target_log_dir = "/workspace/logs"
        
        log_content = f"""
[{timestamp}] Command Execution
Session: {session_dir}
==================================================
CMD: {command}
EXIT: {return_code}
STDOUT:
{stdout}
STDERR:
{stderr}
==================================================
"""
        ssh_base = get_ssh_base_cmd()
        
        # 1. logs 디렉토리 생성 (없으면 생성)
        mkdir_cmd = ssh_base + [f'mkdir -p "{target_log_dir}"']
        subprocess.run(mkdir_cmd, capture_output=True, text=True, timeout=5)
        
        # 2. 중앙 로그 파일에 추가
        write_cmd = ssh_base + [f'cat >> "{target_log_dir}/execution.log"']
        
        # 로그 저장 실행
        subprocess.run(write_cmd, input=log_content, text=True, timeout=5)
        
    except Exception as e:
        logger.warning(f"   ⚠️ Failed to write remote log: {e}")



def get_session_dir(session_id: str) -> str:
    """세션 ID 기반 작업 디렉토리 경로 반환"""
    # 세션 ID에서 안전한 디렉토리명 생성
    safe_id = session_id.replace("/", "_").replace("\\", "_").replace("..", "_")
    return f"/workspace/sessions/{safe_id}"


def ensure_session_dir(session_id: str) -> Tuple[str, bool]:
    """
    세션 디렉토리 생성/확인
    Returns: (디렉토리 경로, 기존 세션 존재 여부)
    """
    session_dir = get_session_dir(session_id)
    ssh_base = get_ssh_base_cmd()
    
    # 디렉토리 존재 여부 확인
    check_cmd = ssh_base + [f'test -d "{session_dir}" && echo "exists" || echo "new"']
    try:
        result = subprocess.run(check_cmd, capture_output=True, text=True, timeout=10)
        exists = "exists" in result.stdout
        
        if not exists:
            # 디렉토리 생성
            mkdir_cmd = ssh_base + [f'mkdir -p "{session_dir}"']
            subprocess.run(mkdir_cmd, capture_output=True, text=True, timeout=10)
            logger.info(f"   📁 Created session directory: {session_dir}")
        else:
            logger.info(f"   📁 Using existing session: {session_dir}")
        
        return session_dir, exists
    except Exception as e:
        logger.error(f"   ⚠️ Session dir error: {e}, using /workspace")
        return "/workspace", False


def check_gemini_session_exists(session_dir: str) -> bool:
    """Gemini 세션 파일 존재 여부 확인"""
    ssh_base = get_ssh_base_cmd()
    # Gemini는 .gemini/tmp 또는 프로젝트 내에 세션 저장
    check_cmd = ssh_base + [f'ls -la "{session_dir}/.gemini" 2>/dev/null | grep -q session && echo "yes" || echo "no"']
    try:
        result = subprocess.run(check_cmd, capture_output=True, text=True, timeout=10)
        return "yes" in result.stdout
    except:
        return False


def parse_gemini_json_response(raw_output: str, tool_name: str) -> str:
    """Gemini JSON 응답 파싱 및 도구 실행 통계 로깅"""
    try:
        import json
        json_response = json.loads(raw_output)
        response_text = json_response.get("response", "")
        
        # 통계 정보 추출
        stats = json_response.get("stats", {})
        tools_stats = stats.get("tools", {})
        files_stats = stats.get("files", {})
        
        total_calls = tools_stats.get("totalCalls", 0)
        total_success = tools_stats.get("totalSuccess", 0)
        lines_added = files_stats.get("totalLinesAdded", 0)
        lines_removed = files_stats.get("totalLinesRemoved", 0)
        
        if total_calls > 0:
            logger.info(f"   🔨 Tools called: {total_calls} (success: {total_success})")
        if lines_added > 0 or lines_removed > 0:
            logger.info(f"   📁 Files modified: +{lines_added} -{lines_removed} lines")
        
        # response가 비어있으면 도구 실행 결과로 메시지 생성
        if not response_text or response_text.strip() == "":
            if total_calls > 0 and total_success == total_calls:
                parts = []
                if lines_added > 0:
                    parts.append(f"파일에 {lines_added}줄 추가됨")
                if lines_removed > 0:
                    parts.append(f"{lines_removed}줄 삭제됨")
                
                tool_names = list(tools_stats.get("byName", {}).keys())
                if tool_names:
                    parts.append(f"실행된 도구: {', '.join(tool_names)}")
                
                response_text = f"✅ 작업 완료! ({total_success}개 도구 실행 성공)"
                if parts:
                    response_text += "\n" + "\n".join(parts)
            elif total_calls > 0:
                response_text = f"⚠️ 작업 부분 완료 ({total_success}/{total_calls} 도구 성공)"
            else:
                response_text = "작업이 완료되었습니다."
        
        return response_text
        
    except Exception as e:
        logger.warning(f"   ⚠️ JSON parse failed: {e}")
        return raw_output


def check_tool_available(tool_name: str, config: dict) -> Optional[str]:
    """SSH를 통해 도구 설치 여부 및 버전 확인"""
    ssh_base = get_ssh_base_cmd()
    version_cmd = config.get("version_cmd")
    
    if not version_cmd:
        version_cmd = ["which", config["bin"]]
    
    try:
        full_cmd = ssh_base + version_cmd
        result = subprocess.run(full_cmd, capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            version_info = result.stdout.strip()
            return version_info.split('\n')[0] if version_info else "installed"
        return None
        
    except subprocess.TimeoutExpired:
        logger.warning(f"   ⏱️ Timeout checking {tool_name}")
        return None
    except Exception as e:
        logger.error(f"   ❌ Error checking {tool_name}: {e}")
        return None


def build_model_mapping():
    """모델 매핑 테이블 구축"""
    global MODEL_MAPPING, SUPPORTED_MODELS
    
    MODEL_MAPPING.clear()
    all_models = []
    
    for tool_name, config in TOOL_CONFIG.items():
        if not AVAILABLE_TOOLS.get(tool_name, False):
            continue
            
        for display_name, cli_name in config["models"].items():
            MODEL_MAPPING[display_name] = (tool_name, cli_name)
            all_models.append(display_name)
    
    SUPPORTED_MODELS = sorted(all_models)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """서버 시작 시 사용 가능한 도구 및 모델 목록 갱신"""
    logger.info("🚀 Server starting... Checking available tools...")
    global AVAILABLE_TOOLS
    
    for tool_name, config in TOOL_CONFIG.items():
        logger.info(f"🔍 Checking {tool_name}...")
        version = check_tool_available(tool_name, config)
        
        if version:
            AVAILABLE_TOOLS[tool_name] = True
            logger.info(f"   ✅ {tool_name} available: {version}")
        else:
            AVAILABLE_TOOLS[tool_name] = False
            logger.warning(f"   ❌ {tool_name} not available")
    
    build_model_mapping()
    
    logger.info(f"\n✨ Available Tools: {[k for k, v in AVAILABLE_TOOLS.items() if v]}")
    logger.info(f"✨ Total Supported Models: {len(SUPPORTED_MODELS)}")
    logger.info(f"📋 Model List: {SUPPORTED_MODELS}")
    
    yield
    logger.info("🛑 Server shutting down...")


app = FastAPI(
    title="Multi-CLI Bridge API",
    description="Bridge API for Claude Code, Gemini CLI, and Codex (n8n AI Agent Compatible)",
    version="2.3.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    body = b""
    client_host = request.client.host if request.client else 'unknown'
    if request.method in ["POST", "PUT", "PATCH"]:
        body = await request.body()
        logger.info(f"🌐 [{request.method}] {request.url.path} <- {client_host}")
        # body는 민감할 수 있으므로 debug 레벨이나 글자수 제한
        logger.info(f"   📦 Body: {body.decode('utf-8', errors='ignore')[:500]}")
    else:
        logger.info(f"🌐 [{request.method}] {request.url.path} <- {client_host}")
    
    async def receive():
        return {"type": "http.request", "body": body}
    
    request = Request(request.scope, receive)
    response = await call_next(request)
    logger.info(f"   └─ Response: {response.status_code}")
    return response


class Message(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    model: str
    messages: List[Message]
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    user: Optional[str] = None


def generate_session_id(messages: List[Message]) -> str:
    """메시지 기반 세션 ID 자동 생성"""
    first_user_msg = ""
    for msg in messages:
        if msg.role == "user":
            first_user_msg = msg.content[:100]
            break
    
    hash_input = f"{first_user_msg}-{int(time.time())}"
    short_hash = hashlib.md5(hash_input.encode()).hexdigest()[:12]
    return f"auto-{short_hash}"


def resolve_model(model_name: str) -> Tuple[str, str, str]:
    """모델명에서 도구와 실제 전달할 모델명 해석"""
    if model_name in MODEL_MAPPING:
        tool_name, cli_name = MODEL_MAPPING[model_name]
        return (tool_name, cli_name, model_name)
    
    for tool_name in TOOL_CONFIG.keys():
        prefix = f"{tool_name}-"
        if model_name.lower().startswith(prefix):
            cli_name = model_name[len(prefix):]
            return (tool_name, cli_name, model_name)
    
    model_lower = model_name.lower()
    if "claude" in model_lower or model_lower in ["opus", "sonnet", "haiku"]:
        return ("claude", model_name, model_name)
    elif "gemini" in model_lower or model_lower in ["auto", "pro", "flash"]:
        return ("gemini", model_name, model_name)
    elif "gpt" in model_lower or "codex" in model_lower or model_lower.startswith("o4"):
        return ("codex", model_name, model_name)
    
    return ("claude", model_name, model_name)


def parse_gemini_json_response(raw_output: str, tool_name: str) -> str:
    """Gemini JSON 응답 파싱 및 빈 응답 처리"""
    try:
        import json
        json_response = json.loads(raw_output)
        response_text = json_response.get("response", "")
        
        # 통계 정보 추출
        stats = json_response.get("stats", {})
        tools_stats = stats.get("tools", {})
        files_stats = stats.get("files", {})
        
        total_calls = tools_stats.get("totalCalls", 0)
        total_success = tools_stats.get("totalSuccess", 0)
        lines_added = files_stats.get("totalLinesAdded", 0)
        lines_removed = files_stats.get("totalLinesRemoved", 0)
        
        if total_calls > 0:
            logger.info(f"   🔨 Tools called: {total_calls} (success: {total_success})")
        if lines_added > 0 or lines_removed > 0:
            logger.info(f"   📁 Files modified: +{lines_added} -{lines_removed} lines")
        
        # response가 비어있으면 도구 실행 결과로 메시지 생성
        if not response_text or response_text.strip() == "":
            if total_calls > 0 and total_success == total_calls:
                tool_names = list(tools_stats.get("byName", {}).keys())
                parts = []
                if lines_added > 0:
                    parts.append(f"파일 {lines_added}줄 추가")
                if lines_removed > 0:
                    parts.append(f"{lines_removed}줄 삭제")
                if tool_names:
                    parts.append(f"도구: {', '.join(tool_names)}")
                
                response_text = f"✅ 작업 완료! ({total_success}개 도구 실행)\n" + ", ".join(parts) if parts else f"✅ 작업 완료! ({total_success}개 도구 실행)"
            elif total_calls > 0:
                response_text = f"⚠️ 작업 부분 완료 ({total_success}/{total_calls} 도구 성공)"
            else:
                response_text = raw_output
                
        return response_text
        
    except Exception as e:
        logger.warning(f"   ⚠️ JSON parse failed: {e}")
        return raw_output


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "available_tools": AVAILABLE_TOOLS,
        "total_models": len(SUPPORTED_MODELS),
        "claude_monitor_url": CLAUDE_MONITOR_URL or None,
    }


@app.get("/v1/models")
@app.get("/models")
async def list_models():
    """OpenAI 호환 모델 목록 반환"""
    models_data = []
    current_time = int(time.time())
    
    for display_name in SUPPORTED_MODELS:
        tool_name, cli_name = MODEL_MAPPING.get(display_name, ("unknown", display_name))
        models_data.append({
            "id": display_name,
            "object": "model",
            "created": current_time,
            "owned_by": f"{tool_name}",
            "permission": [],
            "root": display_name,
            "parent": None,
        })
    
    return {"object": "list", "data": models_data}


@app.get("/v1/tools")
async def list_tools():
    """사용 가능한 도구 및 모델 상세 정보"""
    tools_info = {}
    
    for tool_name, config in TOOL_CONFIG.items():
        tool_models = {
            display: cli 
            for display, (tool, cli) in MODEL_MAPPING.items() 
            if tool == tool_name
        }
        tools_info[tool_name] = {
            "available": AVAILABLE_TOOLS.get(tool_name, False),
            "binary": config["bin"],
            "default_model": config["default_model"],
            "models": tool_models,
        }
    
    return tools_info


@app.post("/v1/chat/completions")
@app.post("/chat/completions")
async def chat_completions(
    request: ChatCompletionRequest,
    x_session_id: Optional[str] = Header(None, alias="X-Session-Id")
):
    """OpenAI 호환 채팅 완료 엔드포인트"""
    
    base_session_id = x_session_id or request.user or generate_session_id(request.messages)
    target_tool, cli_model, display_name = resolve_model(request.model)
    
    # 도구별 고유 세션 ID (충돌 방지)
    tool_session_id = f"{target_tool}-{base_session_id}"
    
    if not AVAILABLE_TOOLS.get(target_tool, False):
        available = [k for k, v in AVAILABLE_TOOLS.items() if v]
        raise HTTPException(status_code=503, detail=f"Tool '{target_tool}' not available. Available: {available}")
    
    tool_settings = TOOL_CONFIG[target_tool]
    logger.info(f"📡 [Chat] Model: {request.model} -> Tool: {target_tool}, CLI: {cli_model}, Session: {tool_session_id}")
    
    # 프롬프트 구성
    full_prompt = ""
    for msg in request.messages:
        if msg.role == "system":
            full_prompt += f"System: {msg.content}\n\n"
        elif msg.role == "user":
            full_prompt += f"User: {msg.content}\n\n"
        elif msg.role == "assistant":
            full_prompt += f"Assistant: {msg.content}\n\n"
    full_prompt += "Assistant: "
    
    clean_prompt = full_prompt.replace('"', '\\"').replace('$', '\\$').replace('`', '\\`')
    
    # 세션 디렉토리 설정 (도구별로 다름)
    if tool_settings.get("use_session_dir", True):
        # 세션 디렉토리 사용 (Claude, Gemini)
        session_dir, session_exists = ensure_session_dir(tool_session_id)
    else:
        # 세션 디렉토리 미사용 (Codex) - /workspace에서 직접 실행
        session_dir = "/workspace"
        session_exists = False
    
    # SSH 명령 구성
    ssh_base = get_ssh_base_cmd()
    
    # 환경변수 설정
    env_prefix = ""
    if CLAUDE_MONITOR_URL and tool_settings.get("supports_monitor"):
        env_prefix = f'ANTHROPIC_BASE_URL="{CLAUDE_MONITOR_URL}" '
        logger.info(f"🔗 Using Claude Monitor: {CLAUDE_MONITOR_URL}")
    
    # 작업 디렉토리로 이동
    cd_prefix = f'cd "{session_dir}" && '
    
    # CLI 명령어 구성
    cli_cmd_parts = [tool_settings["bin"]] + tool_settings["base_args"]
    
    # 기존 세션이 있고 resume을 지원하면 resume 플래그 추가
    if session_exists and tool_settings.get("supports_resume") and tool_settings.get("resume_flag"):
        resume_flags = tool_settings["resume_flag"].split()
        cli_cmd_parts.extend(resume_flags)
        logger.info(f"   🔄 Resuming existing session")
    
    # 모델 플래그
    if cli_model.lower() != tool_settings["default_model"].lower():
        cli_cmd_parts.extend([tool_settings["model_flag"], cli_model])
    
    # JSON 출력 포맷
    if tool_settings.get("output_format"):
        cli_cmd_parts.append(tool_settings["output_format"])
    
    # 프롬프트 추가
    if target_tool == "gemini":
        cli_cmd_parts.extend(["-p", f'"{clean_prompt}"'])
    else:
        cli_cmd_parts.append(f'"{clean_prompt}"')
    
    # 최종 명령어
    shell_cmd = cd_prefix + env_prefix + " ".join(cli_cmd_parts)
    final_cmd = ssh_base + [shell_cmd]
    
    logger.info(f"🔧 Executing in {session_dir}: {tool_settings['bin']} ...")
    
    try:
        result = subprocess.run(final_cmd, capture_output=True, text=True, timeout=300, shell=False)
        
        # [New] 실행 로그 원격 저장
        if tool_settings.get("use_session_dir", True):
             log_remote_execution(session_dir, shell_cmd, result.returncode, result.stdout, result.stderr)

        if result.returncode != 0:
            logger.error(f"❌ CLI Error: {result.stderr}")
            response_text = f"[Error from {target_tool} CLI]\n{result.stderr}"
        else:
            raw_output = result.stdout.strip()
            
            if tool_settings.get("output_format") and "json" in tool_settings.get("output_format", ""):
                response_text = parse_gemini_json_response(raw_output, target_tool)
            else:
                response_text = raw_output
        
        return {
            "id": f"chatcmpl-{target_tool}-{tool_session_id}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": request.model,
            "session_id": tool_session_id,
            "choices": [{
                "index": 0,
                "message": {"role": "assistant", "content": response_text},
                "finish_reason": "stop"
            }],
            "usage": {
                "prompt_tokens": len(full_prompt.split()),
                "completion_tokens": len(response_text.split()),
                "total_tokens": len(full_prompt.split()) + len(response_text.split())
            }
        }
    
    except subprocess.TimeoutExpired:
        logger.error(f"⏱️ Request timeout for {target_tool}")
        raise HTTPException(status_code=504, detail="Request timeout")
    except Exception as e:
        logger.error(f"💥 Server Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/v1/refresh")
async def refresh_models():
    """수동으로 도구 및 모델 목록 갱신"""
    global AVAILABLE_TOOLS
    
    for tool_name, config in TOOL_CONFIG.items():
        version = check_tool_available(tool_name, config)
        AVAILABLE_TOOLS[tool_name] = version is not None
    
    build_model_mapping()
    
    return {
        "status": "refreshed",
        "available_tools": AVAILABLE_TOOLS,
        "total_models": len(SUPPORTED_MODELS),
        "models": SUPPORTED_MODELS
    }


# ============================================================
# OpenAI Responses API 호환 엔드포인트
# ============================================================

class ResponsesRequest(BaseModel):
    """OpenAI Responses API 요청 형식"""
    model: str
    input: Optional[Any] = None
    instructions: Optional[str] = None
    messages: Optional[List[dict]] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    max_output_tokens: Optional[int] = None
    user: Optional[str] = None
    tools: Optional[List[dict]] = None
    tool_choice: Optional[Any] = None
    
    class Config:
        extra = "allow"


@app.post("/responses")
@app.post("/v1/responses")
async def responses_api(
    request: ResponsesRequest,
    x_session_id: Optional[str] = Header(None, alias="X-Session-Id")
):
    """OpenAI Responses API 호환 엔드포인트"""
    
    base_session_id = x_session_id or request.user or f"auto-{hashlib.md5(str(time.time()).encode()).hexdigest()[:12]}"
    target_tool, cli_model, display_name = resolve_model(request.model)
    
    # 도구별 고유 세션 ID (충돌 방지)
    tool_session_id = f"{target_tool}-{base_session_id}"
    
    if not AVAILABLE_TOOLS.get(target_tool, False):
        available = [k for k, v in AVAILABLE_TOOLS.items() if v]
        raise HTTPException(status_code=503, detail=f"Tool '{target_tool}' not available. Available: {available}")
    
    tool_settings = TOOL_CONFIG[target_tool]
    logger.info(f"📡 [Responses API] Model: {request.model} -> Tool: {target_tool}, CLI: {cli_model}, Session: {tool_session_id}")
    
    # 프롬프트 구성
    full_prompt = ""
    
    if request.instructions:
        full_prompt += f"System: {request.instructions}\n\n"
    
    if request.messages:
        for msg in request.messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                full_prompt += f"System: {content}\n\n"
            elif role == "user":
                full_prompt += f"User: {content}\n\n"
            elif role == "assistant":
                full_prompt += f"Assistant: {content}\n\n"
    
    if request.input:
        if isinstance(request.input, str):
            full_prompt += f"User: {request.input}\n\n"
        elif isinstance(request.input, list):
            for item in request.input:
                if isinstance(item, str):
                    full_prompt += f"User: {item}\n\n"
                elif isinstance(item, dict):
                    role = item.get("role", "user")
                    content = item.get("content", "")
                    if isinstance(content, list):
                        text_parts = []
                        for part in content:
                            if isinstance(part, dict) and part.get("type") in ["input_text", "text"]:
                                text_parts.append(part.get("text", ""))
                            elif isinstance(part, str):
                                text_parts.append(part)
                        content = " ".join(text_parts)
                    
                    if role == "system":
                        full_prompt += f"System: {content}\n\n"
                    elif role == "user":
                        full_prompt += f"User: {content}\n\n"
                    elif role == "assistant":
                        full_prompt += f"Assistant: {content}\n\n"
    
    full_prompt += "Assistant: "
    clean_prompt = full_prompt.replace('"', '\\"').replace('$', '\\$').replace('`', '\\`')
    
    # 세션 디렉토리 설정 (도구별로 다름)
    if tool_settings.get("use_session_dir", True):
        # 세션 디렉토리 사용 (Claude, Gemini)
        session_dir, session_exists = ensure_session_dir(tool_session_id)
    else:
        # 세션 디렉토리 미사용 (Codex) - /workspace에서 직접 실행
        session_dir = "/workspace"
        session_exists = False
    
    # SSH 명령 구성
    ssh_base = get_ssh_base_cmd()
    
    # 환경변수 설정
    env_prefix = ""
    if CLAUDE_MONITOR_URL and tool_settings.get("supports_monitor"):
        env_prefix = f'ANTHROPIC_BASE_URL="{CLAUDE_MONITOR_URL}" '
        logger.info(f"🔗 Using Claude Monitor: {CLAUDE_MONITOR_URL}")
    
    # 작업 디렉토리로 이동
    cd_prefix = f'cd "{session_dir}" && '
    
    # CLI 명령어 구성
    cli_cmd_parts = [tool_settings["bin"]] + tool_settings["base_args"]
    
    # 기존 세션이 있고 resume을 지원하면 resume 플래그 추가
    if session_exists and tool_settings.get("supports_resume") and tool_settings.get("resume_flag"):
        resume_flags = tool_settings["resume_flag"].split()
        cli_cmd_parts.extend(resume_flags)
        logger.info(f"   🔄 Resuming existing session")
    
    # 모델 플래그
    if cli_model.lower() != tool_settings["default_model"].lower():
        cli_cmd_parts.extend([tool_settings["model_flag"], cli_model])
    
    # JSON 출력 포맷
    if tool_settings.get("output_format"):
        cli_cmd_parts.append(tool_settings["output_format"])
    
    # 프롬프트 추가
    if target_tool == "gemini":
        cli_cmd_parts.extend(["-p", f'"{clean_prompt}"'])
    else:
        cli_cmd_parts.append(f'"{clean_prompt}"')
    
    # 최종 명령어: cd /workspace/sessions/{id} && [env] command
    shell_cmd = cd_prefix + env_prefix + " ".join(cli_cmd_parts)
    final_cmd = ssh_base + [shell_cmd]
    
    logger.info(f"🔧 Executing in {session_dir}: {tool_settings['bin']} ...")
    
    try:
        result = subprocess.run(final_cmd, capture_output=True, text=True, timeout=300, shell=False)
        
        # [New] 실행 로그 원격 저장
        if tool_settings.get("use_session_dir", True):
             log_remote_execution(session_dir, shell_cmd, result.returncode, result.stdout, result.stderr)

        if result.returncode != 0:
            logger.error(f"❌ CLI Error: {result.stderr}")
            response_text = f"[Error from {target_tool} CLI]\n{result.stderr}"
        else:
            raw_output = result.stdout.strip()
            
            if tool_settings.get("output_format") and "json" in tool_settings.get("output_format", ""):
                response_text = parse_gemini_json_response(raw_output, target_tool)
            else:
                response_text = raw_output
        
        return {
            "id": f"resp-{target_tool}-{tool_session_id}",
            "object": "response",
            "created_at": int(time.time()),
            "model": request.model,
            "session_id": tool_session_id,
            "session_dir": session_dir,
            "session_resumed": session_exists,
            "output": [{
                "type": "message",
                "role": "assistant",
                "content": [{"type": "output_text", "text": response_text}]
            }],
            "usage": {
                "input_tokens": len(full_prompt.split()),
                "output_tokens": len(response_text.split()),
                "total_tokens": len(full_prompt.split()) + len(response_text.split())
            }
        }
    
    except subprocess.TimeoutExpired:
        logger.error(f"⏱️ Request timeout for {target_tool}")
        raise HTTPException(status_code=504, detail="Request timeout")
    except Exception as e:
        logger.error(f"💥 Server Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/v1/model-mapping")
async def get_model_mapping():
    """디버깅용: 모델 매핑 테이블 조회"""
    return {
        display: {"tool": tool, "cli_name": cli_name}
        for display, (tool, cli_name) in MODEL_MAPPING.items()
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
