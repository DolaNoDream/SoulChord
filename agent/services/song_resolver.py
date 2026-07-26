"""Song Resolver — 搜索结果的歌曲选择器。

职责：
  1. normalize_song_name() — 归一化歌名
  2. pick_best_song() — 从搜索结果中选出最佳版本
  3. dedup_candidates() — 队列去重
  4. resolve() — (v9.14) 多 Provider 搜索结果融合：normalize → merge → rank

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


def _extract_first_artist(song: dict) -> str:
    """从 song dict 中提取首位歌手名。

    支持格式：
      - {"artists": [{"name": "..."}]}     ← 搜索结果
      - {"artists": ["..."]}               ← ProviderSearchResult
      - {"artist": "..."}                  ← _to_queue_songs 简化格式
    """
    # 1) artists 列表（搜索结果格式）
    artists = song.get("artists") or song.get("ar") or []
    if isinstance(artists, list) and artists:
        first = artists[0]
        if isinstance(first, dict):
            return (first.get("name") or first.get("nickname") or "").strip()
        return str(first).strip()

    # 2) artist 字符串（队列简化格式）
    artist_str = song.get("artist", "")
    if artist_str:
        return artist_str.split(",")[0].strip()
    return ""


def normalize_title(song: dict) -> str:
    """清洗歌曲标题：去版本后缀 + 去歌手前缀（仅当前缀匹配首位歌手时）。

    例如：
      {name: "买辣椒也用券-起风了（小7 remix）", artists: [...]}
        → 去版本 → "买辣椒也用券-起风了"
        → 检查前缀 "买辣椒也用券-" → 匹配 → "起风了"

      {name: "Love Story", artists: ["Taylor Swift"]}
        → 去版本 → "love story"
        → 检查前缀 "taylor swift-" → 不匹配 → "love story"
    """
    title = (song.get("name") or "").strip()
    if not title:
        return ""

    # 1) 去版本后缀 + 小写（复用 normalize_song_name）
    title = normalize_song_name(title)

    # 2) 去歌手前缀（仅当前缀 == 首位歌手时）
    artist = _extract_first_artist(song)
    if artist:
        artist_lower = artist.lower().strip()
        prefix = artist_lower + "-"
        if title.startswith(prefix):
            title = title[len(prefix):].strip()

    return title


def build_song_dedup_key(song: dict) -> tuple[str, str]:
    """构建去重 key = (归一化标题, 归一化首位歌手)。

    确保：
      - QQ 和网易云的同一首歌去重 key 相同
      - 不同歌手的同名歌曲不被去重
    """
    title = normalize_title(song)
    artist = _extract_first_artist(song)
    return (title, _normalize_artist(artist))


def dedup_candidates(
    candidates: list[dict],
    existing_queue: list[dict] | None = None,
    current_song_id: str = "",
) -> list[dict]:
    """对候选歌曲去重。

    去重规则（v9.15 升级版）：
      1. song_id 已在现有队列中 → 跳过
      2. **(归一化标题, 归一化歌手)** 已在现有队列中 → 跳过
         - 标题先去版本后缀，再去歌手前缀（仅当前缀匹配首位歌手）
      3. 同一 (标题, 歌手) 在候选列表中只保留第一个

    ★ 使用 (归一化标题, 归一化歌手) 作为唯一 key，
      确保 QQ 和网易云同一首歌在不同 name 格式下也能去重。
    """
    if not candidates:
        return []

    # 收集现有队列的 dedup key set
    seen_keys: set[tuple[str, str]] = set()
    seen_ids: set[str] = set()

    if existing_queue:
        for s in existing_queue:
            sid = s.get("song_id", "") or s.get("id", "")
            if sid:
                seen_ids.add(sid)
            key = build_song_dedup_key(s)
            if key[0]:
                seen_keys.add(key)

    if current_song_id:
        seen_ids.add(current_song_id)

    # 候选列表自身去重
    result: list[dict] = []
    self_seen: set[tuple[str, str]] = set()

    for s in candidates:
        sid = s.get("id", "") or s.get("song_id", "")
        key = build_song_dedup_key(s)

        # 1) song_id 已存在
        if sid and sid in seen_ids:
            continue
        # 2) (标题, 歌手) 已在现有队列
        if key[0] and key in seen_keys:
            continue
        # 3) 同一 (标题, 歌手) 已在本次候选列表
        if key[0] and key in self_seen:
            continue

        seen_ids.add(sid) if sid else None
        if key[0]:
            seen_keys.add(key)
            self_seen.add(key)
        result.append(s)

    return result


def _merge_key(result) -> tuple[str, str]:
    """生成跨 Provider 的合并 key = (归一化歌名, 归一化首歌手名)。

    将 "夜曲" + "周杰伦" 和 "夜曲" + "Jay Chou" 视为同一首歌。
    """
    name = normalize_song_name(result.name if hasattr(result, 'name') else (result.get("name", "") or ""))
    artists_raw = result.artists if hasattr(result, 'artists') else (result.get("artists", []) or [])
    first_artist = ""
    if isinstance(artists_raw, list):
        for a in artists_raw:
            aname = a.get("name", "") if isinstance(a, dict) else str(a)
            if aname:
                first_artist = aname
                break
    elif isinstance(artists_raw, str):
        first_artist = artists_raw
    return (name, _normalize_artist(first_artist))


def resolve(
    provider_results: dict[str, list["ProviderSearchResult"]],
    default_provider: str = "netease",
) -> list[dict]:
    """多 Provider 搜索结果融合入口：normalize → merge → rank。

    Args:
        provider_results: {provider_name: [ProviderSearchResult, ...]}
        default_provider: 默认 Provider，其 platform_id 作为 Song.id。

    Returns:
        融合排序后的 Song dict 列表（兼容现有 Song 格式）。
    """
    # 延迟导入避免循环依赖
    from agent.config import settings

    dp = default_provider or settings.DEFAULT_PROVIDER

    # 1) 展平 + 按 merge_key 分组
    groups: dict[tuple[str, str], list[dict]] = {}
    for provider_name, results in provider_results.items():
        for r in results:
            rdict = _result_to_dict(r)
            key = _merge_key(rdict)
            if not key[0]:
                continue
            groups.setdefault(key, []).append(rdict)

    if not groups:
        return []

    # 2) 对每个 group：评分 + 选最佳 + 合并 sources
    merged: list[tuple[int, dict]] = []  # (score, song_dict)

    for key, items in groups.items():
        # 评分（version penalty + provider 偏好）
        scored = []
        for i, item in enumerate(items):
            vtype = _detect_version_type(item["name"])
            penalty = _VERSION_PENALTIES.get(vtype, 0)
            # 原版 +0，Live -15，Cover -30
            base_score = 100
            if vtype == "original":
                base_score = 100
            provider_bonus = 0
            if item["_provider"] == dp:
                provider_bonus = 5
            total = base_score - penalty + provider_bonus
            scored.append((total, i, item))

        scored.sort(key=lambda x: (-x[0], x[1]))
        best = scored[0][2]

        # 合并 sources
        sources = []
        for item in items:
            sources.append({
                "provider": item["_provider"],
                "platform_id": item["platform_id"],
                "platform_mid": item.get("platform_mid"),
                "play_available": True,
            })

        # 构建对外 Song dict
        song_out = {
            "id": best["platform_id"] if best["_provider"] == dp else (items[0]["platform_id"] if items else ""),
            "provider": dp,
            "platform_id": best["platform_id"],
            "platform_mid": best.get("platform_mid"),
            "name": best["name"],
            "artists": best["artists"],
            "album": best["album"],
            "cover_url": best["cover_url"],
            "duration_ms": best["duration_ms"],
            "fee": best["fee"],
            "sources": sources,
        }
        merged.append((scored[0][0], song_out))

    # 3) 按分数降序排列
    merged.sort(key=lambda x: -x[0])
    return [item for _, item in merged]


def _result_to_dict(r: "ProviderSearchResult") -> dict:
    """ProviderSearchResult → 临时 dict（含 _provider 标记）。"""
    return {
        "_provider": r.provider,
        "platform_id": r.platform_id,
        "platform_mid": r.platform_mid,
        "name": r.name,
        "artists": r.artists,
        "album": r.album,
        "cover_url": r.cover_url,
        "duration_ms": r.duration_ms,
        "fee": r.fee,
    }
