"""Song Resolver — 搜索结果的歌曲选择器。

职责：
  1. normalize_song_name() — 归一化歌名
  2. pick_best_song() — 从搜索结果中选出最佳版本
  3. dedup_candidates() — 队列去重

核心原则（v9.1）：
  LLM 负责"想播放什么" → Tool 负责"找到什么" → Resolver 负责"最终播放哪个"
  LLM 不参与 song_id 决策，Resolve 保证原版优先。
"""

import logging
import re

logger = logging.getLogger(__name__)

# 版本后缀权重：值越低越优先
_VERSION_WEIGHTS: dict[str, int] = {
    # 原版 / 录音室版 — 最高优先级
    "original": 0,
    "studio": 0,
    "录音室": 0,
    "album": 0,
    # 现场版 — 中等优先级
    "live": 10,
    "现场": 10,
    "演唱会": 11,
    "演奏": 12,
    # 翻唱 — 低优先级
    "cover": 20,
    "翻唱": 20,
    "remix": 30,
    "mix": 30,
    "伴奏": 40,
    "instrumental": 40,
    "karaoke": 40,
    "钢琴": 41,
    "piano": 41,
    "吉他": 41,
    "guitar": 41,
}

# ★ v9.13: 版本惩罚值（pick_best_song 用，与 _VERSION_WEIGHTS 的优先级权重分开）
_VERSION_PENALTIES: dict[str, int] = {
    "live": 15,
    "现场": 15,
    "演唱会": 15,
    "演奏": 15,
    "cover": 30,
    "翻唱": 30,
    "remix": 20,
    "mix": 20,
    "伴奏": 20,
    "instrumental": 20,
    "karaoke": 20,
    "钢琴": 20,
    "piano": 20,
    "吉他": 20,
    "guitar": 20,
}

# ★ v9.13: 艺术家别名表（仅高频中英文转换，需扩展时独立成配置文件）
#   原则：只维护 LLM 输出语言与搜索结果语言之间确实需要映射的常见别名。
#   避免维护过大：Coldplay→酷玩乐队 有意义（LLM 输出英文、网易云返回中文），
#   但 Beethoven→贝多芬 等古典音乐别名在音乐搜索中几乎不会出现匹配分歧。
_ARTIST_ALIASES: dict[str, str] = {
    "jay chou": "周杰伦",
    "周董": "周杰伦",
    "jj lin": "林俊杰",
    "leehom wang": "王力宏",
    "mayday": "五月天",
    "coldplay": "酷玩乐队",
}

_VERSION_PATTERNS = [
    # (pattern, weight_key) — re.IGNORECASE
    (r'[（(]\s*Live\s*[)）]', "live"),
    (r'[（(]\s*伴奏\s*[)）]', "伴奏"),
    (r'[（(]\s*翻唱\s*[)）]', "翻唱"),
    (r'[（(]\s*Cover\s*[)）]', "cover"),
    (r'[（(]\s*Remix\s*[)）]', "remix"),
    (r'[（(]\s*Instrumental\s*[)）]', "instrumental"),
    (r'[（(]\s*钢琴版?\s*[)）]', "钢琴"),
    (r'[（(]\s*吉他版?\s*[)）]', "吉他"),
    (r'[（(]\s*演唱会\s*[)）]', "演唱会"),
    (r'[（(]\s*现场版?\s*[)）]', "现场"),
    (r'[（(]\s*演奏版?\s*[)）]', "演奏"),
    (r'\s*[-—]\s*(Live|伴奏|翻唱|Cover|Remix|Mix|Instrumental|钢琴|吉他|演唱会|现场|演奏)'
     r'(\s*版?)?$', lambda m: m.group(1).lower()),
]


def normalize_song_name(name: str) -> str:
    """归一化歌名：去除版本后缀，统一小写。

    "晴天(Live)" → "晴天"
    "晴天 - 伴奏" → "晴天"
    "Here Comes The Sun (Remix)" → "here comes the sun"
    """
    if not name:
        return ""

    normalized = name.strip()

    # 依次匹配版本模式，一旦命中就去除
    for pattern, _ in _VERSION_PATTERNS:
        replacement = ""
        try:
            normalized = re.sub(pattern, replacement, normalized, flags=re.IGNORECASE).strip()
        except TypeError:
            # pattern 是 tuple 的第二项是 str 或 callable
            pass

    # 也去除括号内纯数字/无意义后缀
    normalized = re.sub(r'\s*[（(][^)）]*[)）]\s*$', '', normalized).strip()
    return normalized.lower()


def _detect_version_type(song_name: str) -> str:
    """检测歌曲版本类型。返回 _VERSION_WEIGHTS 中的 key，未识别返回 "original"。"""
    name_lower = song_name.lower().strip()

    for pattern, weight_key in _VERSION_PATTERNS:
        if isinstance(weight_key, str):
            if re.search(pattern, name_lower, re.IGNORECASE):
                return weight_key

    # 无版本后缀 → 原版
    return "original"


def _version_score(song_name: str) -> int:
    """计算版本分数。分数越低越优先。"""
    vtype = _detect_version_type(song_name)
    return _VERSION_WEIGHTS.get(vtype, 50)


def _name_match_score(llm_name: str, song_name: str) -> float:
    """计算 LLM 歌名与搜索结果歌名的匹配度 [0, 1]。

    1.0 = 完全匹配（归一化后相同）
    0.8 = LLM 名是歌曲名的子串（或相反），且长度差 < 3
    0.5 = 子串匹配（但长度差大）
    0.0 = 不匹配
    """
    if not llm_name or not song_name:
        return 0.0

    ln = normalize_song_name(llm_name)
    sn = normalize_song_name(song_name)

    if ln == sn:
        return 1.0
    if ln in sn or sn in ln:
        longer = max(len(ln), len(sn))
        shorter = min(len(ln), len(sn))
        if longer - shorter <= 3:
            return 0.8
        return 0.5
    return 0.0


def _normalize_artist(name: str) -> str:
    """归一化歌手名：别名映射 + 小写 + 去空格。

    "Jay Chou" → "周杰伦"
    "周杰伦" → "周杰伦"
    """
    if not name:
        return ""
    key = name.lower().strip()
    return _ARTIST_ALIASES.get(key, key)


def _artist_match_score(llm_artist: str, song_artists_raw) -> tuple[str, int]:
    """计算歌手匹配得分。

    Returns:
        (match_type, score) — match_type 用于日志，score 用于排序

    ★ v9.13 评分（离散加分，不再归一化到 [0,1]）：
      exact (完全匹配):     +50
      alias (别名匹配):     +40
      fuzzy (子串匹配):     +20
      mismatch (不匹配):    -40
      neutral (无歌手信息):  0

    匹配优先级：exact > alias > fuzzy > mismatch
    """
    if not llm_artist:
        return "neutral", 0

    la = llm_artist.lower().strip()
    if not la:
        return "neutral", 0

    # 从搜索结果提取歌手字符串
    if isinstance(song_artists_raw, list):
        sa = ", ".join(a.get("name", "") for a in song_artists_raw).lower().strip()
    else:
        sa = (str(song_artists_raw) or "").lower().strip()

    if not sa:
        return "mismatch", -40

    # 将搜索结果歌手按逗号拆分（多歌手场景）
    sa_parts = [p.strip() for p in sa.replace("、", ",").replace("/", ",").split(",") if p.strip()]

    # 归一化 LLM 歌手
    la_norm = _normalize_artist(la)

    # 1. exact match
    if la == sa or la_norm == sa:
        return "exact", 50

    # 逐个检查 sa_parts（多歌手合作曲）
    for sp in sa_parts:
        sp_norm = _normalize_artist(sp)

        # 1a. LLM 名直接匹配某个歌手
        if la == sp or la_norm == sp_norm:
            return "exact", 50

    # 2. alias match
    if la_norm != la:  # la 通过别名映射变了
        if la_norm in sa or la_norm in sa_parts:
            return "alias", 40
        for sp in sa_parts:
            sp_canonical = _normalize_artist(sp)
            if sp_canonical == la_norm:
                return "alias", 40

    # 3. fuzzy match
    if la in sa or sa in la:
        return "fuzzy", 20
    for sp in sa_parts:
        if la in sp or sp in la:
            return "fuzzy", 20

    return "mismatch", -40


def pick_best_song(
    name: str,
    artist: str,
    search_results: list[dict],
) -> dict | None:
    """从搜索结果中选出最佳版本。

    ★ v9.13 离散评分系统（不再使用加权归一化）：

      song name exact (归一化相同):  +50
      song name strong (子串接近):   +30
      song name weak (子串但差距大): +10

      artist exact:                   +50
      artist alias:                   +40
      artist fuzzy:                   +20
      artist mismatch:                -40

      version penalty:
        Live:                         -15
        Cover/翻唱:                   -30
        Instrumental/Remix/伴奏:      -20
        其他（原版/录音室）:           0

    评分确保：
      - 原版 + 歌手匹配 > 翻唱 + 歌手匹配
      - 歌手不匹配的歌曲几乎不可能胜出（-40 惩罚）
    """
    if not search_results:
        return None

    scored: list[tuple[float, int, dict]] = []

    for i, song in enumerate(search_results):
        song_name = song.get("name", "") or ""
        song_artists = song.get("artists", []) or song.get("ar", [])

        nm_score = _name_match_score(name, song_name)
        if nm_score == 0.0:
            continue

        # 歌名得分（离散）
        if nm_score >= 1.0:
            name_pts = 50
        elif nm_score >= 0.8:
            name_pts = 30
        elif nm_score >= 0.5:
            name_pts = 10
        else:
            continue

        # 歌手得分
        _, artist_pts = _artist_match_score(artist, song_artists)

        # 版本惩罚
        vtype = _detect_version_type(song_name)
        version_penalty = _VERSION_PENALTIES.get(vtype, 0)

        total = name_pts + artist_pts - version_penalty
        scored.append((total, i, song))

    if not scored:
        return None

    # 按总分降序，同分按搜索顺序
    scored.sort(key=lambda x: (-x[0], x[1]))
    best = scored[0][2]
    logger.debug("pick_best_song: name=%r artist=%r -> best=%r (score=%d, total=%d candidates)",
                 name, artist, best.get("name", ""), scored[0][0], len(scored))
    return best


def dedup_candidates(
    candidates: list[dict],
    existing_queue: list[dict] | None = None,
    current_song_id: str = "",
) -> list[dict]:
    """对候选歌曲去重。

    去重规则（v9.1 Song Resolver 版）：
      1. song_id 已在现有队列中 → 跳过
      2. **归一化歌名** 已在现有队列中 → 跳过（不管歌手、版本）
      3. 同一归一化歌名在候选列表中只保留第一个

    ★ 仅使用归一化歌名作为唯一 key（不区分歌手/版本），
      因为播放列表面板场景下同一首歌不同版本/翻唱不应该重复出现。

    参数：
      candidates: 候选歌曲 list（搜索结果原始格式）
      existing_queue: 现有队列（_to_queue_songs 后的格式）
      current_song_id: 当前正在播放的 song_id（排除）

    返回：去重后的候选列表（保留原始 dict，非 to_queue_songs 格式）
    """
    if not candidates:
        return []

    # 收集现有队列的归一化歌名 set
    seen_names: set[str] = set()
    seen_ids: set[str] = set()

    if existing_queue:
        for s in existing_queue:
            sid = s.get("song_id", "") or s.get("id", "")
            if sid:
                seen_ids.add(sid)
            nname = normalize_song_name(s.get("name", ""))
            if nname:
                seen_names.add(nname)

    if current_song_id:
        seen_ids.add(current_song_id)

    # 候选列表自身去重
    result: list[dict] = []
    self_seen: set[str] = set()

    for s in candidates:
        sid = s.get("id", "") or s.get("song_id", "")
        song_name = s.get("name", "") or ""

        nname = normalize_song_name(song_name)

        # 1) song_id 已存在
        if sid and sid in seen_ids:
            continue
        # 2) 归一化歌名已在现有队列
        if nname and nname in seen_names:
            continue
        # 3) 同一归一化歌名已在本次候选列表
        if nname and nname in self_seen:
            continue

        seen_ids.add(sid) if sid else None
        if nname:
            seen_names.add(nname)
            self_seen.add(nname)
        result.append(s)

    return result
