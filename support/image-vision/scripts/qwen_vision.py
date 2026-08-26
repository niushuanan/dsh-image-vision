#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Qwen3-VL-Plus 视觉助手（image-vision skill 的后端脚本）

给纯文本主模型（如 DeepSeek）提供"看图"能力：
- 支持本地路径、http(s) URL、data URI，以及各 agent 平台的附件引用（自动识别所在平台）
- 不传图片时，自动从当前平台（zcode / claude / codex / opencode / workbuddy / hermes）最近会话里找附件
- 同一组图片的多次提问自动续接多轮对话（历史保存在 ../state/ 目录，按图片内容指纹区分）
- API key：优先环境变量 DASHSCOPE_API_KEY，其次本机配置文件 ~/.config/image-vision/config.json（0600，不入任何仓库）

用法：
  python3 qwen_vision.py <图片路径或URL或平台附件引用> [-q "问题"]
  python3 qwen_vision.py                        # 自动从当前平台找最近的图
  python3 qwen_vision.py --recent 3 -q "..."    # 自动找最近 3 张图
  python3 qwen_vision.py --setup-key            # 首次使用：配置你的 API key（仅存本机）
  python3 qwen_vision.py <图片> --history       # 只打印该组图片的对话历史并退出
  python3 qwen_vision.py <图片> -q "..." --reset / --no-history
"""
import argparse
import base64
import glob
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile

API_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
MODEL = "qwen3-vl-plus"
MAX_IMAGE_BYTES = 10 * 1024 * 1024  # 10MB，超出需先压缩
MAX_HISTORY_MESSAGES = 12           # 保留最近 12 条消息（约 6 轮问答）
DEFAULT_QUESTION = "请详细描述这张图片的内容，包括主体、所有可见文字、布局等一切可见信息。"

CONFIG_DIR = os.path.expanduser("~/.config/image-vision")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")

# 各 agent 平台的附件可能位置（自动检测，全部宽松 glob，找不到就算了）
CANDIDATE_GLOBS = [
    ("zcode",     os.path.expanduser("~/.zcode/cli/artifacts/*/*tool-result-*")),
    ("claude",    os.path.expanduser("~/.claude/projects/*/attachments/*/*")),
    ("codex",     os.path.expanduser("~/.codex/sessions/*/*.jsonl")),
    ("opencode",  os.path.expanduser("~/.local/share/opencode/opencode.db")),
    ("workbuddy", os.path.expanduser("~/.workbuddy/*")),
    ("hermes",    os.path.expanduser("~/.hermes/*")),
]
# 会话记录类文件（jsonl / sqlite 等），从中直接提取 data URI 图片
SESSION_SCAN_GLOBS = [
    ("claude",  os.path.expanduser("~/.claude/projects/*/*.jsonl")),
    ("codex",   os.path.expanduser("~/.codex/sessions/*/rollout.jsonl")),
    ("opencode", os.path.expanduser("~/.local/share/opencode/opencode.db")),
]

MIME_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".bmp": "image/bmp",
}
DATA_URI_RE = re.compile(rb"data:image/(?:png|jpeg|jpg|gif|webp|bmp);base64,[A-Za-z0-9+/=]+")
BASE64_IMG_RE = re.compile(rb'"media_type"\s*:\s*"(image/[a-z0-9+]+)"\s*,\s*"data"\s*:\s*"([A-Za-z0-9+/=]{100,})"')

STATE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "state")


def die(msg):
    print(f"[image-vision] {msg}", file=sys.stderr)
    sys.exit(1)


# ---------- API key：环境变量 > 本机配置文件，绝不硬编码 ----------

def get_api_key():
    key = os.environ.get("DASHSCOPE_API_KEY", "").strip()
    if key:
        return key
    if os.path.isfile(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, encoding="utf-8") as f:
                key = json.load(f).get("api_key", "").strip()
        except Exception:
            pass
    return key


def setup_key_interactive():
    print("【image-vision】首次使用：需要配置一个阿里云百炼的 API key（用于 qwen3-vl-plus 视觉模型）。")
    print("申请步骤：打开 https://bailian.console.aliyun.com/ → 右上角头像 → API-KEY → 创建我的API-KEY")
    print("（也可以不用本命令：设置环境变量 DASHSCOPE_API_KEY 即可，环境变量优先于本文件）")
    key = input("请粘贴你的 API key 并回车（仅保存到本机，不会进入任何聊天记录）: ").strip()
    if not key:
        die("未输入 key，已取消。")
    os.makedirs(CONFIG_DIR, exist_ok=True)
    os.chmod(CONFIG_DIR, 0o700)
    tmp = CONFIG_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"api_key": key, "model": MODEL}, f, ensure_ascii=False, indent=2)
    os.chmod(tmp, 0o600)
    os.replace(tmp, CONFIG_FILE)
    print(f"✅ key 已保存到 {CONFIG_FILE}（仅本机当前用户可读），现在可以直接使用了。")


# ---------- 图片来源解析 ----------

def resolve_ref(ref):
    """把各平台附件引用解析成实际路径；URL/data URI 原样返回。"""
    if ref.startswith("zcode-artifact://"):
        rest = ref[len("zcode-artifact://"):]
        session, _, tail = rest.partition("/")
        d = os.path.join(os.path.expanduser("~/.zcode/cli/artifacts"), session)
        if not os.path.isdir(d):
            die(f"找不到 ZCode 会话附件目录：{d}")
        matches = [f for f in os.listdir(d) if tail in f]
        if not matches:
            die(f"ZCode 会话里找不到附件 {tail}（目录：{d}）")
        if len(matches) > 1:
            die(f"附件引用 {tail} 匹配到多个文件：{matches}")
        return os.path.join(d, matches[0])
    return ref


def mime_from_bytes(path):
    with open(path, "rb") as f:
        head = f.read(16)
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if head.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if head.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if head.startswith(b"BM"):
        return "image/bmp"
    if head.startswith(b"RIFF") and head[8:12] == b"WEBP":
        return "image/webp"
    return None


def is_image_file(path):
    if not os.path.isfile(path):
        return False
    size = os.path.getsize(path)
    if size == 0 or size > MAX_IMAGE_BYTES:
        return False
    ext = os.path.splitext(path)[1].lower()
    if ext in MIME_TYPES:
        return True
    return mime_from_bytes(path) is not None


def find_recent_attachments(limit):
    """按平台自动查找最近的用户图片附件，返回 [(平台, 内容)]；内容为本地路径或 data URI 字符串。"""
    found = []  # (mtime, 平台, 内容)

    # 1) 附件目录：直接 glob 图片文件（ZCode 附件内容是 data URI 文本，单独处理）
    for platform, pattern in CANDIDATE_GLOBS:
        if platform == "zcode":
            for p in glob.glob(pattern):
                try:
                    mtime = os.path.getmtime(p)
                except OSError:
                    continue
                # ZCode 附件：文件内容就是 data URI
                try:
                    with open(p, "r", encoding="utf-8", errors="ignore") as f:
                        head = f.read(64)
                    if head.startswith("data:"):
                        with open(p, "r", encoding="utf-8") as f:
                            found.append((mtime, platform, f.read()))
                        continue
                except OSError:
                    pass
                if is_image_file(p):
                    found.append((mtime, platform, p))
        elif platform == "opencode":
            db = os.path.expanduser("~/.local/share/opencode/opencode.db")
            if os.path.isfile(db):
                for uri in scan_data_uris(db, limit):
                    found.append((os.path.getmtime(db), platform, uri))
        elif platform in ("workbuddy", "hermes"):
            for p in glob.glob(pattern):
                try:
                    if is_image_file(p):
                        found.append((os.path.getmtime(p), platform, p))
                except OSError:
                    continue
        else:
            for p in glob.glob(pattern):
                try:
                    if is_image_file(p):
                        found.append((os.path.getmtime(p), platform, p))
                except OSError:
                    continue

    # 2) 会话记录（jsonl/sqlite）：直接提取其中最近的图片 data URI
    for platform, pattern in SESSION_SCAN_GLOBS:
        for p in glob.glob(pattern):
            try:
                mtime = os.path.getmtime(p)
            except OSError:
                continue
            if platform == "opencode":
                for uri in scan_data_uris(p, limit):
                    found.append((mtime, platform, uri))
            else:
                for uri in scan_jsonl_images(p, limit):
                    found.append((mtime, platform, uri))

    # 按时间倒序去重取最近
    seen = set()
    out = []
    for mtime, platform, content in sorted(found, key=lambda x: -x[0]):
        key = content if len(content) < 300 else content[:300]
        if key in seen:
            continue
        seen.add(key)
        out.append((platform, content))
        if len(out) >= limit:
            break
    return out


def scan_jsonl_images(path, limit):
    """从 agent 会话 jsonl 里提取图片 data URI（返回最近 limit 个）。"""
    try:
        with open(path, "rb") as f:
            data = f.read()
    except OSError:
        return []
    return extract_data_uris(data, limit)


def scan_data_uris(path, limit):
    """从任意文件（含 sqlite 等二进制）里扫出 data URI 图片（返回最近 limit 个）。"""
    try:
        with open(path, "rb") as f:
            data = f.read()
    except OSError:
        return []
    return extract_data_uris(data, limit)


def extract_data_uris(data, limit):
    """从字节流中提取 data URI 图片；data URI 找不到时退回 media_type+base64 形态。"""
    out = []
    for m in re.finditer(DATA_URI_RE, data):
        out.append(m.group(0).decode("ascii", errors="ignore"))
    if not out:
        for m in re.finditer(BASE64_IMG_RE, data):
            mime, b64 = m.group(1).decode(), m.group(2).decode("ascii", errors="ignore")
            out.append(f"data:{mime};base64,{b64}")
    return out[-limit:]


def to_image_part(content):
    """把来源内容统一成 API 的 image_url 内容块。"""
    if content.startswith(("http://", "https://", "data:")):
        return {"type": "image_url", "image_url": {"url": content}}
    path = resolve_ref(content)
    if not os.path.isfile(path):
        die(f"找不到图片文件：{path}")
    # ZCode 附件落盘格式：文件内容本身就是 data URI（data:image/...;base64,...），直接可用
    if os.path.getsize(path) < MAX_IMAGE_BYTES:
        try:
            with open(path, "rb") as f:
                head = f.read(64)
            if head.startswith(b"data:"):
                with open(path, "r", encoding="utf-8") as f:
                    return {"type": "image_url", "image_url": {"url": f.read()}}
        except (OSError, UnicodeDecodeError):
            pass
    size = os.path.getsize(path)
    if size > MAX_IMAGE_BYTES:
        die(f"图片过大（{size / 1024 / 1024:.1f}MB > 10MB）：{path}，请先压缩或改用 URL。")
    mime = MIME_TYPES.get(os.path.splitext(path)[1].lower()) or mime_from_bytes(path)
    if not mime:
        die(f"不支持的图片格式：{path}（仅支持 png/jpg/jpeg/webp/gif/bmp）")
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    return {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}}


def content_fingerprint(content):
    """图片指纹：本地文件用内容哈希（改名/移动不影响多轮历史），URL/data URI 直接用内容前缀哈希。"""
    if content.startswith(("http://", "https://", "data:")):
        return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]
    path = resolve_ref(content)
    h = hashlib.sha256()
    with open(path, "rb") as f:
        h.update(f.read())
    return h.hexdigest()[:16]


def state_path(images):
    key = "_".join(content_fingerprint(i) for i in images)
    return os.path.join(STATE_DIR, key + ".json")


def load_state(path):
    if os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"images": [], "messages": []}


def save_state(path, state):
    os.makedirs(STATE_DIR, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def call_api(api_key, messages):
    body = json.dumps({"model": MODEL, "messages": messages})
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        f.write(body)
        tmp = f.name
    try:
        proc = subprocess.run(
            ["curl", "-sS", "--fail-with-body", "--max-time", "120",
             "-X", "POST", API_URL,
             "-H", f"Authorization: Bearer {api_key}",
             "-H", "Content-Type: application/json",
             "-d", f"@{tmp}"],
            capture_output=True, text=True)
    finally:
        os.unlink(tmp)
    if proc.returncode != 0:
        detail = proc.stderr.strip() or proc.stdout.strip()
        die(f"API 请求失败（curl 退出码 {proc.returncode}）：{detail[:500]}")
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        die(f"API 响应不是合法 JSON：{proc.stdout[:500]}")
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        die(f"API 响应异常：{json.dumps(data, ensure_ascii=False)[:500]}")


def main():
    parser = argparse.ArgumentParser(description="调用 qwen3-vl-plus 为纯文本模型提供图片描述")
    parser.add_argument("images", nargs="*", help="图片路径 / URL / data URI / 平台附件引用；不传则自动找当前平台最近的图")
    parser.add_argument("-q", "--question", help=f"对图片的提问（默认：{DEFAULT_QUESTION}）")
    parser.add_argument("-n", "--recent", type=int, default=1, help="不传图片时，自动找最近 N 张图（默认 1）")
    parser.add_argument("--setup-key", action="store_true", help="首次使用：把 API key 保存到本机配置文件")
    parser.add_argument("--history", action="store_true", help="只打印该组图片的对话历史并退出")
    parser.add_argument("--reset", action="store_true", help="清空该组图片的历史后再提问")
    parser.add_argument("--no-history", action="store_true", help="本次提问不携带历史（单轮）")
    args = parser.parse_args()

    if args.setup_key:
        setup_key_interactive()
        return

    api_key = get_api_key()
    if not api_key:
        print("[image-vision] 还没有配置 API key。执行一次下面命令（key 仅保存到本机）：", file=sys.stderr)
        print(f"  python3 {os.path.abspath(__file__)} --setup-key", file=sys.stderr)
        print("  或设置环境变量：export DASHSCOPE_API_KEY=你的key", file=sys.stderr)
        sys.exit(1)

    # 图片来源：命令行参数，或自动从当前平台找最近的图
    sources = list(args.images)
    if not sources:
        found = find_recent_attachments(args.recent)
        if not found:
            die("没有找到任何最近会话里的图片附件。请直接传入图片路径/URL/附件引用。")
        for platform, content in found:
            label = content[:80] + "..." if len(content) > 80 and not os.path.isfile(content) else content
            print(f"[image-vision] 自动取用 {platform} 平台的附件：{label}", file=sys.stderr)
        sources = [c for _, c in found]

    user_content = [to_image_part(s) for s in sources]
    user_content.append({"type": "text", "text": args.question or DEFAULT_QUESTION})

    state = load_state(state_path(sources))
    if args.reset:
        state = {"images": sources, "messages": []}

    messages = state["messages"][-MAX_HISTORY_MESSAGES:] if not args.no_history else []
    messages.append({"role": "user", "content": user_content})

    reply = call_api(api_key, messages)

    if not args.no_history:
        state["images"] = sources
        state["messages"].append({"role": "user", "content": user_content})
        state["messages"].append({"role": "assistant", "content": reply})
        state["messages"] = state["messages"][-MAX_HISTORY_MESSAGES:]
        save_state(state_path(sources), state)

    print(reply)


if __name__ == "__main__":
    main()
