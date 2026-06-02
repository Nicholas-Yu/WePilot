#!/usr/bin/env python3
"""
Tests for P0-P2 bug fixes.
Run: python3 -m pytest tests/test_bugfixes.py -v
Or:  python3 tests/test_bugfixes.py
"""
import sys
import time
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch
from collections import OrderedDict

sys.path.insert(0, str(Path(__file__).parent.parent))


# ============================================================
# Test P0-1: Menu not matched -> pending should NOT be discarded
# ============================================================
def _make_bot():
    """Create a properly configured mock bot for menu tests."""
    from bot import WeChatBot

    bot = MagicMock(spec=WeChatBot)
    bot._memory_key = WeChatBot._memory_key.__get__(bot)
    bot._pending_skill_menus = {}
    bot._pending_skill_menus_lock = threading.Lock()
    bot.account_id = "test_bot"
    bot._match_menu_keyword = WeChatBot._match_menu_keyword.__get__(bot)
    bot._MENU_NUMBER_MAP = WeChatBot._MENU_NUMBER_MAP
    bot._MENU_TYPE_NAMES = WeChatBot._MENU_TYPE_NAMES
    bot._MENU_SELECTION_PATTERNS = WeChatBot._MENU_SELECTION_PATTERNS
    return bot


def test_p0_1_menu_not_matched_preserves_pending():
    """When user sends a message that doesn't match any menu option,
    the pending menu should be preserved for future selections."""
    from bot import WeChatBot

    bot = _make_bot()

    mock_skill = MagicMock()
    mock_skill.menu_keywords = ["深度分析=深度研报", "标准报告=标准投资报告"]

    bot._pending_skill_menus["test_bot:user1"] = {
        "skill": mock_skill,
        "timestamp": time.time(),
        "original_text": "分析下医药行业",
        "file_contexts": [],
    }

    result = WeChatBot._check_menu_selection(bot, "user1", "你好")

    assert result is None, "Non-matching message should return None"
    assert "test_bot:user1" in bot._pending_skill_menus, "Pending menu should be preserved"
    print("  PASS: P0-1 menu not matched preserves pending")


def test_p0_1_menu_matched_removes_pending():
    """When user selects a valid option, pending should be removed."""
    from bot import WeChatBot

    bot = _make_bot()

    mock_skill = MagicMock()
    mock_skill.menu_keywords = ["深度分析=深度研报"]

    bot._pending_skill_menus["test_bot:user1"] = {
        "skill": mock_skill,
        "timestamp": time.time(),
        "original_text": "分析下医药行业",
        "file_contexts": [],
    }

    result = WeChatBot._check_menu_selection(bot, "user1", "1")

    assert result is not None, "Matching message should return result"
    assert result["report_type"] == "快速简报"
    assert "test_bot:user1" not in bot._pending_skill_menus, "Pending should be removed after match"
    print("  PASS: P0-1 menu matched removes pending")


# ============================================================
# Test P0-4: stream=True should not crash _complete
# ============================================================
def test_p0_4_complete_forces_no_stream():
    """_complete should pass force_no_stream=True to _create_chat_completion."""
    import inspect
    from llm_engine import LLMEngine

    sig = inspect.signature(LLMEngine._create_chat_completion)
    params = list(sig.parameters.keys())
    assert "force_no_stream" in params, "_create_chat_completion should have force_no_stream parameter"

    source = inspect.getsource(LLMEngine._complete)
    assert "force_no_stream=True" in source, "_complete should pass force_no_stream=True"
    print("  PASS: P0-4 _complete forces no stream")


def test_p0_4_stream_check_respects_force_no_stream():
    """_create_chat_completion should check force_no_stream before streaming."""
    import inspect
    from llm_engine import LLMEngine

    source = inspect.getsource(LLMEngine._create_chat_completion)
    assert "not force_no_stream" in source, "Stream check should respect force_no_stream"
    print("  PASS: P0-4 stream check respects force_no_stream")


# ============================================================
# Test P1-5: _selected_report_types TTL
# ============================================================
def test_p1_5_report_type_ttl():
    """Report types should expire after TTL."""
    from bot import WeChatBot

    bot = MagicMock(spec=WeChatBot)
    bot._memory_key = WeChatBot._memory_key.__get__(bot)
    bot._selected_report_types = {}
    bot._report_type_ttl = 1  # 1 second TTL for testing
    bot.account_id = "test_bot"

    WeChatBot._set_selected_report_type(bot, "user1", "快速简报")

    result = WeChatBot._get_selected_report_type(bot, "user1")
    assert result == "快速简报", "Should return report type before expiry"

    result2 = WeChatBot._get_selected_report_type(bot, "user1")
    assert result2 is None, "Should be consumed after first get"
    print("  PASS: P1-5 report type consumed after get")


def test_p1_5_report_type_expires():
    """Report types should expire after TTL."""
    from bot import WeChatBot

    bot = MagicMock(spec=WeChatBot)
    bot._memory_key = WeChatBot._memory_key.__get__(bot)
    bot._selected_report_types = {}
    bot._report_type_ttl = 0.1  # 100ms TTL
    bot.account_id = "test_bot"

    WeChatBot._set_selected_report_type(bot, "user1", "快速简报")
    time.sleep(0.2)

    result = WeChatBot._get_selected_report_type(bot, "user1")
    assert result is None, "Should return None after TTL expiry"
    print("  PASS: P1-5 report type expires after TTL")


# ============================================================
# Test P2-8: _resolve_skill_menus helper exists
# ============================================================
def test_p2_8_resolve_skill_menus_exists():
    """_resolve_skill_menus helper method should exist."""
    from bot import WeChatBot

    assert hasattr(WeChatBot, "_resolve_skill_menus"), "_resolve_skill_menus should exist"
    print("  PASS: P2-8 _resolve_skill_menus exists")


def test_p2_8_no_duplicate_menu_logic():
    """The inline menu logic should be removed from _handle_message and _process_buffered_message."""
    import inspect
    from bot import WeChatBot

    handle_source = inspect.getsource(WeChatBot._handle_message)
    buffered_source = inspect.getsource(WeChatBot._process_buffered_message)

    assert "_resolve_skill_menus" in handle_source, "_handle_message should use _resolve_skill_menus"
    assert "_resolve_skill_menus" in buffered_source, "_process_buffered_message should use _resolve_skill_menus"

    assert "self._get_selected_report_type" not in handle_source, "_handle_message should not have inline menu logic"
    assert "self._get_selected_report_type" not in buffered_source, "_process_buffered_message should not have inline menu logic"
    print("  PASS: P2-8 no duplicate menu logic")


# ============================================================
# Test P2-10: _handle_message exception isolation
# ============================================================
def test_p2_10_message_exception_isolation():
    """Each message should be handled in its own try/except."""
    import inspect
    from bot import WeChatBot

    source = inspect.getsource(WeChatBot._loop)
    assert "message handling error" in source, "_loop should catch per-message exceptions"
    print("  PASS: P2-10 message exception isolation")


# ============================================================
# Test P2-12: menu_keywords preserve case
# ============================================================
def test_p2_12_menu_keywords_preserve_case():
    """menu_keywords should preserve case for report_type."""
    from skill_runtime import SkillRuntime

    sr = MagicMock(spec=SkillRuntime)
    result = SkillRuntime._parse_menu_keywords(sr, ["深度分析=深度研报", "Standard=标准报告"])

    assert result == ["深度分析=深度研报", "Standard=标准报告"], f"Should preserve case, got {result}"
    print("  PASS: P2-12 menu_keywords preserve case")


def test_p2_12_list_meta_still_lowers():
    """_list_meta should still lowercase for intents etc."""
    from skill_runtime import SkillRuntime

    sr = MagicMock(spec=SkillRuntime)
    result = SkillRuntime._list_meta(sr, ["Hello", "WORLD"])

    assert result == ["hello", "world"], f"_list_meta should lowercase, got {result}"
    print("  PASS: P2-12 _list_meta still lowers")


# ============================================================
# Test menu selection patterns
# ============================================================
def test_menu_selection_patterns():
    """Test various natural language menu selection patterns."""
    from bot import WeChatBot

    bot = _make_bot()

    mock_skill = MagicMock()
    mock_skill.menu_keywords = ["深度分析=深度研报"]

    test_cases = [
        ("1", "快速简报"),
        ("2", "标准投资报告"),
        ("3", "深度研报"),
        ("选1", "快速简报"),
        ("选 2", "标准投资报告"),
        ("第三个", "深度研报"),
        ("我要1", "快速简报"),
        ("2号", "标准投资报告"),
        ("深度分析", "深度研报"),
    ]

    for text, expected_type in test_cases:
        bot._pending_skill_menus["test_bot:user1"] = {
            "skill": mock_skill,
            "timestamp": time.time(),
            "original_text": "分析下医药行业",
            "file_contexts": [],
        }

        result = WeChatBot._check_menu_selection(bot, "user1", text)
        assert result is not None, f"'{text}' should match"
        assert result["report_type"] == expected_type, f"'{text}' -> expected '{expected_type}', got '{result['report_type']}'"

    print(f"  PASS: menu selection patterns ({len(test_cases)} cases)")


# ============================================================
# Test _resolve_skill_menus
# ============================================================
def test_resolve_skill_menus_returns_context():
    """_resolve_skill_menus should return updated skill_context when no menu skills."""
    from bot import WeChatBot

    bot = MagicMock(spec=WeChatBot)
    bot._get_selected_report_type = MagicMock(return_value=None)
    bot._match_menu_keyword = MagicMock(return_value=None)

    skill_no_menu = MagicMock()
    skill_no_menu.menu = ""

    result = WeChatBot._resolve_skill_menus(
        bot, [skill_no_menu], "user1", "test", [], "ctx_token", "base context"
    )

    assert result == "base context", f"Should return unchanged context, got {result}"
    print("  PASS: _resolve_skill_menus returns context for no-menu skills")


def test_resolve_skill_menus_returns_none_on_menu_sent():
    """_resolve_skill_menus should return None when menu is sent."""
    from bot import WeChatBot

    bot = MagicMock(spec=WeChatBot)
    bot._get_selected_report_type = MagicMock(return_value=None)
    bot._match_menu_keyword = MagicMock(return_value=None)
    bot._set_pending_menu = MagicMock()
    bot.ilink = MagicMock()
    bot.logger = MagicMock()

    skill_with_menu = MagicMock()
    skill_with_menu.menu = "请选择报告类型..."
    skill_with_menu.name = "test-skill"

    result = WeChatBot._resolve_skill_menus(
        bot, [skill_with_menu], "user1", "test", [], "ctx_token", "base context"
    )

    assert result is None, "Should return None when menu is sent"
    bot.ilink.send_message.assert_called_once()
    bot._set_pending_menu.assert_called_once()
    print("  PASS: _resolve_skill_menus returns None on menu sent")


def test_resolve_skill_menus_skip_menu():
    """_resolve_skill_menus with skip_menu=True should use default report type."""
    from bot import WeChatBot

    bot = MagicMock(spec=WeChatBot)

    skill_with_menu = MagicMock()
    skill_with_menu.menu = "请选择报告类型..."

    result = WeChatBot._resolve_skill_menus(
        bot, [skill_with_menu], "user1", "test", [], "ctx_token", "base", skip_menu=True
    )

    assert result is not None, "Should return context with skip_menu"
    assert "快速简报" in result, "Should inject default report type"
    print("  PASS: _resolve_skill_menus skip_menu works")


# ============================================================
# Run all tests
# ============================================================
def main():
    print("\n" + "=" * 60)
    print("Running bug fix verification tests")
    print("=" * 60 + "\n")

    tests = [
        ("P0-1: Menu not matched preserves pending", test_p0_1_menu_not_matched_preserves_pending),
        ("P0-1: Menu matched removes pending", test_p0_1_menu_matched_removes_pending),
        ("P0-4: _complete forces no stream", test_p0_4_complete_forces_no_stream),
        ("P0-4: Stream check respects force_no_stream", test_p0_4_stream_check_respects_force_no_stream),
        ("P1-5: Report type consumed after get", test_p1_5_report_type_ttl),
        ("P1-5: Report type expires after TTL", test_p1_5_report_type_expires),
        ("P2-8: _resolve_skill_menus exists", test_p2_8_resolve_skill_menus_exists),
        ("P2-8: No duplicate menu logic", test_p2_8_no_duplicate_menu_logic),
        ("P2-10: Message exception isolation", test_p2_10_message_exception_isolation),
        ("P2-12: menu_keywords preserve case", test_p2_12_menu_keywords_preserve_case),
        ("P2-12: _list_meta still lowers", test_p2_12_list_meta_still_lowers),
        ("Menu selection patterns", test_menu_selection_patterns),
        ("_resolve_skill_menus returns context", test_resolve_skill_menus_returns_context),
        ("_resolve_skill_menus returns None on menu sent", test_resolve_skill_menus_returns_none_on_menu_sent),
        ("_resolve_skill_menus skip_menu", test_resolve_skill_menus_skip_menu),
    ]

    passed = 0
    failed = 0
    errors = []

    for name, test_fn in tests:
        try:
            test_fn()
            passed += 1
        except Exception as e:
            failed += 1
            errors.append((name, str(e)))
            print(f"  FAIL: {name}: {e}")

    print(f"\n{'=' * 60}")
    print(f"Results: {passed} passed, {failed} failed out of {len(tests)}")
    if errors:
        print("\nFailures:")
        for name, err in errors:
            print(f"  - {name}: {err}")
    print(f"{'=' * 60}\n")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
