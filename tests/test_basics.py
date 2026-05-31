"""Unit tests for the teaching toolset. No LLM required."""

from datetime import date

from tools.basics import calculator, current_date, word_count, TOOLS, TOOL_DOCS


class TestCalculator:
    def test_simple_addition(self):
        assert calculator("2 + 2") == "4"

    def test_multiplication(self):
        assert calculator("17 * 23") == "391"

    def test_order_of_operations(self):
        assert calculator("2 + 3 * 4") == "14"

    def test_division(self):
        assert calculator("10 / 4") == "2.5"

    def test_bad_expression_returns_error_string(self):
        result = calculator("this is not math")
        assert result.startswith("Error:")

    def test_builtins_are_disabled(self):
        # eval'ing with no builtins should refuse import()
        result = calculator("__import__('os').system('echo hi')")
        assert result.startswith("Error:")


class TestCurrentDate:
    def test_returns_today(self):
        assert current_date("") == date.today().isoformat()

    def test_input_is_ignored(self):
        assert current_date("anything") == date.today().isoformat()


class TestWordCount:
    def test_simple(self):
        assert word_count("hello world") == "2"

    def test_three_words(self):
        assert word_count("agents plan and act") == "4"

    def test_empty_string(self):
        assert word_count("") == "0"

    def test_multiple_spaces(self):
        assert word_count("  foo   bar   baz  ") == "3"


class TestRegistry:
    def test_all_three_tools_registered(self):
        assert set(TOOLS.keys()) == {"calculator", "current_date", "word_count"}

    def test_docs_reference_each_tool(self):
        for name in TOOLS:
            assert name in TOOL_DOCS

    def test_every_tool_takes_string_returns_string(self):
        for name, fn in TOOLS.items():
            out = fn("23 * 47") if name == "calculator" else fn("hello world")
            assert isinstance(out, str), f"{name} returned {type(out)}"
