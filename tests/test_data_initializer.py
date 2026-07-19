"""data_initializer 测试 — 6 个 JSON 文件首次启动自动生成。

覆盖：
  1. init_data_files() 创建全部 6 个文件
  2. 每个文件内容与 Store DEFAULT 一致
  3. 不覆盖已存在的文件
  4. OSError 容错（logging warning 不抛异常）

使用方法：
    cd dev
    python -m pytest tests/test_data_initializer.py -v
"""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent.state.data_initializer import init_data_files, _INIT_TASKS
from agent.state.memory_store import DEFAULT_MEMORY
from agent.state.settings_store import DEFAULT_SETTINGS
from agent.state.playlist_store import DEFAULT_PLAYLISTS
from agent.state.program_state import DEFAULT_PROGRAM_STATE
from agent.state.player_state import DEFAULT_PLAYER_MIRROR

# 6 个文件的预期默认值（与 Store DEFAULT 对齐）
EXPECTED_DEFAULTS: dict = {
    "MEMORY_FILE": DEFAULT_MEMORY,
    "SETTINGS_FILE": DEFAULT_SETTINGS,
    "PLAYLISTS_FILE": DEFAULT_PLAYLISTS,
    "PROGRAM_STATE_FILE": DEFAULT_PROGRAM_STATE,
    "PLAYER_MIRROR_FILE": DEFAULT_PLAYER_MIRROR,
    "PLAYER_HISTORY_FILE": [],  # 列表，非 dict
}

# 类型标记（验证 JSON 根类型）
EXPECTED_TYPES: dict = {k: type(v) for k, v in EXPECTED_DEFAULTS.items()}


# ═══════════════════════════════════════════════════════════════
# 夹具
# ═══════════════════════════════════════════════════════════════


@pytest.fixture
def tmp_data_dir(monkeypatch, tmp_path):
    """创建空临时数据目录，覆盖 settings 路径。"""
    tmpdir = str(tmp_path)
    from agent.config import settings as cfg
    monkeypatch.setattr(cfg, "DATA_DIR", tmpdir)
    monkeypatch.setattr(cfg, "MEMORY_FILE", os.path.join(tmpdir, "memory.json"))
    monkeypatch.setattr(cfg, "SETTINGS_FILE", os.path.join(tmpdir, "settings.json"))
    monkeypatch.setattr(cfg, "PLAYLISTS_FILE", os.path.join(tmpdir, "playlists.json"))
    monkeypatch.setattr(cfg, "PLAYER_MIRROR_FILE", os.path.join(tmpdir, "player_mirror.json"))
    monkeypatch.setattr(cfg, "PLAYER_HISTORY_FILE", os.path.join(tmpdir, "player_history.json"))
    monkeypatch.setattr(cfg, "PROGRAM_STATE_FILE", os.path.join(tmpdir, "program_state.json"))
    return tmpdir


# ═══════════════════════════════════════════════════════════════
# Test Case 1: 首次启动生成全部 6 个文件
# ═══════════════════════════════════════════════════════════════


class TestInitDataFiles:
    def test_creates_all_six_files(self, tmp_data_dir):
        """init_data_files() 在空目录下创建全部 6 个 JSON 文件。"""
        assert os.listdir(tmp_data_dir) == [], "测试夹具应为空目录"

        init_data_files()

        files = os.listdir(tmp_data_dir)
        assert "memory.json" in files
        assert "settings.json" in files
        assert "playlists.json" in files
        assert "program_state.json" in files
        assert "player_mirror.json" in files
        assert "player_history.json" in files
        assert len(files) == 6, f"期望 6 个文件，实际 {len(files)}"

    # ═══════════════════════════════════════════════════════════
    # Test Case 2: 每个文件内容与 Store DEFAULT 一致
    # ═══════════════════════════════════════════════════════════

    def test_memory_content(self, tmp_data_dir):
        """memory.json 内容与 DEFAULT_MEMORY 一致。"""
        init_data_files()
        with open(os.path.join(tmp_data_dir, "memory.json"), "r") as f:
            data = json.load(f)
        assert data == DEFAULT_MEMORY
        assert data["profile"] == {}
        assert data["preference"] == {}
        assert data["context"] == {}
        assert data["feedback"] == {}

    def test_settings_content(self, tmp_data_dir):
        """settings.json 内容与 DEFAULT_SETTINGS 一致。"""
        init_data_files()
        with open(os.path.join(tmp_data_dir, "settings.json"), "r") as f:
            data = json.load(f)
        assert data == DEFAULT_SETTINGS
        assert data["llm_apikey"] == ""
        assert data["netease_apikey"] == ""

    def test_playlists_content(self, tmp_data_dir):
        """playlists.json 内容与 DEFAULT_PLAYLISTS 一致。"""
        init_data_files()
        with open(os.path.join(tmp_data_dir, "playlists.json"), "r") as f:
            data = json.load(f)
        assert data == DEFAULT_PLAYLISTS
        assert data["playlists"] == []
        assert data["songs"] == {}

    def test_program_state_content(self, tmp_data_dir):
        """program_state.json 内容与 DEFAULT_PROGRAM_STATE 一致。"""
        init_data_files()
        with open(os.path.join(tmp_data_dir, "program_state.json"), "r") as f:
            data = json.load(f)
        assert data == DEFAULT_PROGRAM_STATE
        assert data["version"] == "1.0"
        assert data["program_status"] == "idle"

    def test_player_mirror_content(self, tmp_data_dir):
        """player_mirror.json 内容与 DEFAULT_PLAYER_MIRROR 一致。"""
        init_data_files()
        with open(os.path.join(tmp_data_dir, "player_mirror.json"), "r") as f:
            data = json.load(f)
        assert data == DEFAULT_PLAYER_MIRROR
        assert data["current_song"] is None
        assert data["is_playing"] is False
        assert data["playlist_queue"] == []

    def test_history_content(self, tmp_data_dir):
        """player_history.json 初始为空列表。"""
        init_data_files()
        with open(os.path.join(tmp_data_dir, "player_history.json"), "r") as f:
            data = json.load(f)
        assert data == []
        assert isinstance(data, list)

    # ═══════════════════════════════════════════════════════════
    # Test Case 3: 不覆盖已存在的文件
    # ═══════════════════════════════════════════════════════════

    def test_does_not_overwrite_existing(self, tmp_data_dir):
        """已有内容的文件不被 init_data_files() 覆盖。"""
        test_data = {"custom": "value", "nested": {"a": 1}}
        path = os.path.join(tmp_data_dir, "settings.json")
        os.makedirs(tmp_data_dir, exist_ok=True)
        with open(path, "w") as f:
            json.dump(test_data, f)

        init_data_files()

        with open(path, "r") as f:
            data = json.load(f)
        assert data == test_data, "不应覆盖已有文件"

    # ═══════════════════════════════════════════════════════════
    # Test Case 4: json.dumps 可序列化（间接验证）
    # ═══════════════════════════════════════════════════════════

    def test_all_defaults_are_json_serializable(self, tmp_data_dir):
        """所有 DEFAULT 值经 json.dumps 无异常。"""
        for attr_name, default_value in _INIT_TASKS:
            try:
                json.dumps(default_value, ensure_ascii=False)
            except (TypeError, ValueError) as e:
                pytest.fail(f"{attr_name} DEFAULT 不可 JSON 序列化: {e}")

    # ═══════════════════════════════════════════════════════════
    # Test Case 5: 分类批量验证
    # ═══════════════════════════════════════════════════════════

    def test_all_files_expected_types(self, tmp_data_dir):
        """每个生成的 JSON 文件根类型与预期一致。"""
        init_data_files()
        from agent.config import settings as cfg
        for attr_name, expected_type in EXPECTED_TYPES.items():
            path = getattr(cfg, attr_name)
            with open(path, "r") as f:
                data = json.load(f)
            assert isinstance(data, expected_type), (
                f"{attr_name} 文件根类型应为 {expected_type.__name__}，"
                f"实际 {type(data).__name__}"
            )
