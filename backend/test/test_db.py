import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.db.json_store import JSONStore, CollectionStore

TEST_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "test_data")


def ensure_test_dir():
    if not os.path.exists(TEST_DATA_DIR):
        os.makedirs(TEST_DATA_DIR)


def cleanup_test_files():
    if os.path.exists(TEST_DATA_DIR):
        for file in os.listdir(TEST_DATA_DIR):
            os.remove(os.path.join(TEST_DATA_DIR, file))


def test_json_store():
    ensure_test_dir()
    test_file = os.path.join(TEST_DATA_DIR, "test_settings.json")
    
    if os.path.exists(test_file):
        os.remove(test_file)

    store = JSONStore(test_file, {"llm_apikey": "", "netease_apikey": ""})

    data = store.read()
    assert data == {"llm_apikey": "", "netease_apikey": ""}, f"Initial read failed: {data}"

    store.write({"llm_apikey": "test-key", "netease_apikey": ""})
    data = store.read()
    assert data["llm_apikey"] == "test-key", f"Write failed: {data}"

    store.update({"netease_apikey": "netease-key"})
    data = store.read()
    assert data["netease_apikey"] == "netease-key", f"Update failed: {data}"
    assert data["llm_apikey"] == "test-key", f"Update overwrote llm_apikey: {data}"

    value = store.get("llm_apikey")
    assert value == "test-key", f"Get failed: {value}"

    value = store.get("nonexistent", "default")
    assert value == "default", f"Get default failed: {value}"

    store.set("new_key", "new_value")
    data = store.read()
    assert data["new_key"] == "new_value", f"Set failed: {data}"

    print("✓ JSONStore tests passed")


def test_collection_store():
    ensure_test_dir()
    test_file = os.path.join(TEST_DATA_DIR, "test_playlists.json")
    
    if os.path.exists(test_file):
        os.remove(test_file)

    store = CollectionStore(test_file)

    items = store.list()
    assert items == [], f"Initial list failed: {items}"

    playlist1 = {
        "playlist_id": "p1",
        "name": "歌单1",
        "source_url": "http://test.com/1",
        "song_count": 10,
        "created_at": 1234567890
    }
    result = store.add(playlist1)
    assert result["playlist_id"] == "p1", f"Add failed: {result}"

    items = store.list()
    assert len(items) == 1, f"List count failed: {len(items)}"
    assert items[0]["name"] == "歌单1", f"List content failed: {items}"

    item = store.get_by_id("p1", id_field="playlist_id")
    assert item is not None, f"Get_by_id failed"
    assert item["name"] == "歌单1", f"Get_by_id content failed: {item}"

    item = store.get_by_id("nonexistent", id_field="playlist_id")
    assert item is None, f"Get_by_id nonexistent failed: {item}"

    playlist2 = {
        "playlist_id": "p2",
        "name": "歌单2",
        "source_url": "http://test.com/2",
        "song_count": 20,
        "created_at": 1234567891
    }
    store.add(playlist2)
    items = store.list()
    assert len(items) == 2, f"Add second failed: {len(items)}"

    updated = store.update("p1", {"name": "更新后的歌单1"}, id_field="playlist_id")
    assert updated is not None, f"Update failed"
    assert updated["name"] == "更新后的歌单1", f"Update content failed: {updated}"

    updated = store.update("nonexistent", {"name": "test"}, id_field="playlist_id")
    assert updated is None, f"Update nonexistent failed: {updated}"

    success = store.delete("p2", id_field="playlist_id")
    assert success is True, f"Delete failed"
    items = store.list()
    assert len(items) == 1, f"Delete count failed: {len(items)}"
    assert items[0]["playlist_id"] == "p1", f"Delete wrong item: {items}"

    success = store.delete("nonexistent", id_field="playlist_id")
    assert success is False, f"Delete nonexistent failed: {success}"

    print("✓ CollectionStore tests passed")


def test_real_store_operations():
    from backend.db import (
        settings_store,
        netease_store,
        user_profile_store,
        playlist_store,
        player_store,
    )

    settings_store.set("llm_apikey", "test-api-key")
    settings = settings_store.read()
    assert settings["llm_apikey"] == "test-api-key", f"Settings store failed: {settings}"
    print("✓ settings_store test passed")

    netease_store.update({"login_status": True, "nickname": "测试用户"})
    netease = netease_store.read()
    assert netease["login_status"] is True, f"Netease store failed: {netease}"
    assert netease["nickname"] == "测试用户", f"Netease nickname failed: {netease}"
    print("✓ netease_store test passed")

    user_profile_store.update({
        "nickname": "AI用户",
        "favorite_genres": ["流行", "摇滚"],
        "favorite_artists": ["周杰伦", "陈奕迅"]
    })
    profile = user_profile_store.read()
    assert profile["nickname"] == "AI用户", f"User profile failed: {profile}"
    assert profile["favorite_genres"] == ["流行", "摇滚"], f"Genres failed: {profile}"
    print("✓ user_profile_store test passed")

    test_playlist = {
        "playlist_id": "test-playlist-id",
        "name": "测试歌单",
        "source_url": "https://music.163.com/#/playlist?id=123",
        "song_count": 5,
        "created_at": 1739270400000,
        "songs": []
    }
    playlist_store.add(test_playlist)
    playlists = playlist_store.list()
    assert len(playlists) >= 1, f"Playlist store failed: {len(playlists)}"
    print("✓ playlist_store test passed")

    player_store.update({
        "is_playing": True,
        "current_index": 0
    })
    player = player_store.read()
    assert player["is_playing"] is True, f"Player store failed: {player}"
    print("✓ player_store test passed")


if __name__ == "__main__":
    print("=" * 60)
    print("Running SoulChord Database Tests")
    print("=" * 60)
    print()

    test_json_store()
    test_collection_store()
    test_real_store_operations()

    print()
    print("=" * 60)
    print("All database tests passed!")
    print("=" * 60)

    cleanup_test_files()