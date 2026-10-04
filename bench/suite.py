"""The tasks.

Fifteen bug fixes, each a tiny project with one planted bug and tests that describe the correct
behaviour (four of them are traced through a second module), and five refactors checked by tests
plus a look at the code's structure. Every task is defined here as data, so nothing in this file
is collected as a test by the repository's own test run, and `python -m bench verify` proves two
things about each: the starting project fails its tests, and the reference solution passes.
"""

from textwrap import dedent
from typing import Dict, List, Optional

from .task import Task

PYTEST_FOOTER = ""


def _t(text: str) -> str:
    return dedent(text).lstrip("\n")


def bugfix(
    id: str,
    title: str,
    prompt: str,
    files: Dict[str, str],
    fixed: Dict[str, str],
    tests_file: str,
) -> Task:
    return Task(
        id=id,
        kind="bugfix",
        title=title,
        prompt=prompt
        + " The tests in the tests folder describe the correct behaviour; do not change them.",
        files={name: _t(text) for name, text in files.items()},
        solution={name: _t(text) for name, text in fixed.items()},
        protected=(tests_file,),
    )


def refactor(
    id: str,
    title: str,
    prompt: str,
    files: Dict[str, str],
    solution: Dict[str, str],
    tests_file: str,
) -> Task:
    return Task(
        id=id,
        kind="refactor",
        title=title,
        prompt=prompt
        + " Behaviour must not change. The tests in the tests folder check both the behaviour and"
        " the new structure; do not change them.",
        files={name: _t(text) for name, text in files.items()},
        solution={name: _t(text) for name, text in solution.items()},
        protected=(tests_file,),
    )


TASKS: List[Task] = []


def add(task: Task) -> None:
    TASKS.append(task)


# ---------------------------------------------------------------------------------------
# Bug fixes
# ---------------------------------------------------------------------------------------

add(
    bugfix(
        "bug-sum-to-off-by-one",
        "sum_to leaves out its last number",
        "`sum_to(5)` returns 10, but it should return 15 (1+2+3+4+5). Find and fix the bug.",
        {
            "mathutil.py": '''
                def sum_to(n):
                    """Return 1 + 2 + ... + n (0 when n is 0)."""
                    total = 0
                    for i in range(1, n):
                        total += i
                    return total
            ''',
            "tests/test_mathutil.py": """
                from mathutil import sum_to


                def test_sum_to_includes_n():
                    assert sum_to(5) == 15


                def test_sum_to_one():
                    assert sum_to(1) == 1


                def test_sum_to_zero():
                    assert sum_to(0) == 0
            """,
        },
        {"mathutil.py": '''
                def sum_to(n):
                    """Return 1 + 2 + ... + n (0 when n is 0)."""
                    total = 0
                    for i in range(1, n + 1):
                        total += i
                    return total
            '''},
        "tests/test_mathutil.py",
    )
)

add(
    bugfix(
        "bug-discount-wrong-sign",
        "A discount makes the price go up",
        "`apply_discount(200, 25)` returns 250.0 instead of 150.0. Fix it.",
        {
            "pricing.py": '''
                def apply_discount(price, percent):
                    """Price after taking `percent` percent off, rounded to cents."""
                    return round(price + price * percent / 100, 2)
            ''',
            "tests/test_pricing.py": """
                from pricing import apply_discount


                def test_quarter_off():
                    assert apply_discount(200, 25) == 150.0


                def test_no_discount():
                    assert apply_discount(80, 0) == 80


                def test_rounds_to_cents():
                    assert apply_discount(10, 33) == 6.7
            """,
        },
        {"pricing.py": '''
                def apply_discount(price, percent):
                    """Price after taking `percent` percent off, rounded to cents."""
                    return round(price - price * percent / 100, 2)
            '''},
        "tests/test_pricing.py",
    )
)

add(
    bugfix(
        "bug-shared-default-list",
        "Tags from one call show up in the next",
        "Calling `add_tag('b')` after `add_tag('a')` returns ['a', 'b'] instead of ['b']: the "
        "calls are leaking into each other. Fix it.",
        {
            "tags.py": '''
                def add_tag(tag, tags=[]):
                    """Return a list with `tag` added to `tags` (a new list when none is given)."""
                    tags.append(tag)
                    return tags
            ''',
            "tests/test_tags.py": """
                from tags import add_tag


                def test_calls_do_not_share_state():
                    assert add_tag("a") == ["a"]
                    assert add_tag("b") == ["b"]


                def test_adds_to_a_given_list():
                    assert add_tag("c", ["a", "b"]) == ["a", "b", "c"]
            """,
        },
        {"tags.py": '''
                def add_tag(tag, tags=None):
                    """Return a list with `tag` added to `tags` (a new list when none is given)."""
                    if tags is None:
                        tags = []
                    tags.append(tag)
                    return tags
            '''},
        "tests/test_tags.py",
    )
)

add(
    bugfix(
        "bug-csv-fields-not-stripped",
        "Table cells keep their surrounding spaces",
        "`load_table('name, age\\nann, 31')` gives cells like ' age' and ' 31' with a leading "
        "space. Cells should have surrounding whitespace removed. Find the cause and fix it.",
        {
            "rows.py": '''
                def parse_row(line):
                    """Split one comma-separated line into trimmed cells."""
                    return line.split(",")
            ''',
            "table.py": '''
                from rows import parse_row


                def load_table(text):
                    """Parse text into a list of rows, skipping blank lines."""
                    return [parse_row(line) for line in text.splitlines() if line.strip()]
            ''',
            "tests/test_table.py": """
                from table import load_table


                def test_cells_are_trimmed():
                    assert load_table("name, age\\nann, 31") == [["name", "age"], ["ann", "31"]]


                def test_blank_lines_are_skipped():
                    assert load_table("a,b\\n\\n  \\nc,d") == [["a", "b"], ["c", "d"]]


                def test_single_cell():
                    assert load_table(" x ") == [["x"]]
            """,
        },
        {"rows.py": '''
                def parse_row(line):
                    """Split one comma-separated line into trimmed cells."""
                    return [cell.strip() for cell in line.split(",")]
            '''},
        "tests/test_table.py",
    )
)

add(
    bugfix(
        "bug-top-scores-lowest",
        "The 'top' scores are the lowest ones",
        "`top_scores([5, 9, 1, 7], 2)` returns [1, 5]; it should return the two highest, "
        "[9, 7]. Fix it.",
        {
            "leaderboard.py": '''
                def top_scores(scores, n):
                    """The `n` highest scores, best first."""
                    return sorted(scores)[:n]
            ''',
            "tests/test_leaderboard.py": """
                from leaderboard import top_scores


                def test_highest_first():
                    assert top_scores([5, 9, 1, 7], 2) == [9, 7]


                def test_n_larger_than_list():
                    assert top_scores([3, 1], 5) == [3, 1]


                def test_does_not_modify_input():
                    scores = [2, 8, 4]
                    top_scores(scores, 2)
                    assert scores == [2, 8, 4]
            """,
        },
        {"leaderboard.py": '''
                def top_scores(scores, n):
                    """The `n` highest scores, best first."""
                    return sorted(scores, reverse=True)[:n]
            '''},
        "tests/test_leaderboard.py",
    )
)

add(
    bugfix(
        "bug-average-of-nothing",
        "A report on an empty list crashes",
        "`summary([])` raises ZeroDivisionError. An empty list should give an average of 0.0 "
        "and a count of 0. Find the cause and fix it.",
        {
            "stats.py": '''
                def average(values):
                    """Mean of `values`; 0.0 when there are none."""
                    return sum(values) / len(values)
            ''',
            "report.py": """
                from stats import average


                def summary(values):
                    return {"count": len(values), "average": average(values)}
            """,
            "tests/test_report.py": """
                from report import summary


                def test_summary_of_numbers():
                    assert summary([1, 2, 3]) == {"count": 3, "average": 2.0}


                def test_summary_of_nothing():
                    assert summary([]) == {"count": 0, "average": 0.0}
            """,
        },
        {"stats.py": '''
                def average(values):
                    """Mean of `values`; 0.0 when there are none."""
                    if not values:
                        return 0.0
                    return sum(values) / len(values)
            '''},
        "tests/test_report.py",
    )
)

add(
    bugfix(
        "bug-word-count-keyerror",
        "Counting words crashes on the first word",
        "`count_words('a b a')` raises KeyError. It should return {'a': 2, 'b': 1} and ignore "
        "case. Fix it.",
        {
            "words.py": '''
                def count_words(text):
                    """How many times each word occurs, ignoring case."""
                    counts = {}
                    for word in text.lower().split():
                        counts[word] += 1
                    return counts
            ''',
            "tests/test_words.py": """
                from words import count_words


                def test_counts():
                    assert count_words("a b a") == {"a": 2, "b": 1}


                def test_ignores_case():
                    assert count_words("Go go GO") == {"go": 3}


                def test_empty():
                    assert count_words("") == {}
            """,
        },
        {"words.py": '''
                def count_words(text):
                    """How many times each word occurs, ignoring case."""
                    counts = {}
                    for word in text.lower().split():
                        counts[word] = counts.get(word, 0) + 1
                    return counts
            '''},
        "tests/test_words.py",
    )
)

add(
    bugfix(
        "bug-truncate-too-long",
        "Truncated text is longer than the limit",
        "`truncate('hello world', 8)` returns 'hello wo...' (11 characters). The result "
        "including the '...' must never be longer than the limit, so it should be 'hello...'. "
        "Fix it.",
        {
            "textutil.py": '''
                def truncate(text, limit):
                    """Shorten `text` to at most `limit` characters, ending in '...' when cut."""
                    if len(text) <= limit:
                        return text
                    return text[:limit] + "..."
            ''',
            "tests/test_textutil.py": """
                from textutil import truncate


                def test_cut_text_ends_in_dots_within_the_limit():
                    assert truncate("hello world", 8) == "hello..."


                def test_short_text_is_unchanged():
                    assert truncate("short", 10) == "short"


                def test_exact_length_is_unchanged():
                    assert truncate("exactly10!", 10) == "exactly10!"


                def test_never_longer_than_the_limit():
                    assert len(truncate("x" * 100, 20)) == 20
            """,
        },
        {"textutil.py": '''
                def truncate(text, limit):
                    """Shorten `text` to at most `limit` characters, ending in '...' when cut."""
                    if len(text) <= limit:
                        return text
                    return text[: limit - 3] + "..."
            '''},
        "tests/test_textutil.py",
    )
)

add(
    bugfix(
        "bug-percentage-rounds-down",
        "Progress always shows 0%",
        "`progress_label(1, 4)` returns '0%' but should return '25.0%'. Find the cause and fix "
        "it.",
        {
            "ratio.py": '''
                def percentage(part, whole):
                    """`part` as a percentage of `whole` (0.0 when whole is 0)."""
                    if whole == 0:
                        return 0.0
                    return part // whole * 100
            ''',
            "progress.py": """
                from ratio import percentage


                def progress_label(done, total):
                    return f"{percentage(done, total)}%"
            """,
            "tests/test_progress.py": """
                from progress import progress_label


                def test_quarter():
                    assert progress_label(1, 4) == "25.0%"


                def test_complete():
                    assert progress_label(3, 3) == "100.0%"


                def test_nothing_to_do():
                    assert progress_label(0, 0) == "0.0%"
            """,
        },
        {"ratio.py": '''
                def percentage(part, whole):
                    """`part` as a percentage of `whole` (0.0 when whole is 0)."""
                    if whole == 0:
                        return 0.0
                    return part / whole * 100
            '''},
        "tests/test_progress.py",
    )
)

add(
    bugfix(
        "bug-user-lookup-case",
        "User lookup is case sensitive",
        "`find_user('alice')` returns None although a user called 'Alice' exists. Names should "
        "be matched ignoring case. Fix it.",
        {
            "users.py": '''
                USERS = [{"name": "Alice", "id": 1}, {"name": "Bob", "id": 2}]


                def find_user(name):
                    """The user with this name (any capitalisation), or None."""
                    for user in USERS:
                        if user["name"] == name:
                            return user
                    return None
            ''',
            "tests/test_users.py": """
                from users import find_user


                def test_exact_match():
                    assert find_user("Alice")["id"] == 1


                def test_other_capitalisation():
                    assert find_user("alice")["id"] == 1
                    assert find_user("BOB")["id"] == 2


                def test_unknown_user():
                    assert find_user("carol") is None
            """,
        },
        {"users.py": '''
                USERS = [{"name": "Alice", "id": 1}, {"name": "Bob", "id": 2}]


                def find_user(name):
                    """The user with this name (any capitalisation), or None."""
                    for user in USERS:
                        if user["name"].lower() == name.lower():
                            return user
                    return None
            '''},
        "tests/test_users.py",
    )
)

add(
    bugfix(
        "bug-leap-year-centuries",
        "1900 is reported as a leap year",
        "`is_leap_year(1900)` returns True, but 1900 was not a leap year (years divisible by "
        "100 are not, unless they are also divisible by 400). Fix it.",
        {
            "calendar_rules.py": '''
                def is_leap_year(year):
                    """Gregorian leap year rule."""
                    return year % 4 == 0 or year % 100 == 0 and year % 400 != 0
            ''',
            "tests/test_calendar_rules.py": """
                import pytest

                from calendar_rules import is_leap_year


                @pytest.mark.parametrize("year", [2000, 2024, 1996, 2400])
                def test_leap_years(year):
                    assert is_leap_year(year) is True


                @pytest.mark.parametrize("year", [1900, 2100, 2023, 1999])
                def test_ordinary_years(year):
                    assert is_leap_year(year) is False
            """,
        },
        {"calendar_rules.py": '''
                def is_leap_year(year):
                    """Gregorian leap year rule."""
                    return (year % 4 == 0 and year % 100 != 0) or year % 400 == 0
            '''},
        "tests/test_calendar_rules.py",
    )
)

add(
    bugfix(
        "bug-flatten-one-level",
        "flatten leaves nested lists nested",
        "`flatten([1, [2, [3, [4]]]])` returns [1, 2, [3, [4]]]; it should return [1, 2, 3, 4]. "
        "Fix it.",
        {
            "nested.py": '''
                def flatten(items):
                    """A flat list of every non-list element, in order, however deeply nested."""
                    result = []
                    for item in items:
                        if isinstance(item, list):
                            result.extend(item)
                        else:
                            result.append(item)
                    return result
            ''',
            "tests/test_nested.py": """
                from nested import flatten


                def test_deeply_nested():
                    assert flatten([1, [2, [3, [4]]]]) == [1, 2, 3, 4]


                def test_already_flat():
                    assert flatten([1, 2, 3]) == [1, 2, 3]


                def test_empty_lists_vanish():
                    assert flatten([[], [1], [[]]]) == [1]
            """,
        },
        {"nested.py": '''
                def flatten(items):
                    """A flat list of every non-list element, in order, however deeply nested."""
                    result = []
                    for item in items:
                        if isinstance(item, list):
                            result.extend(flatten(item))
                        else:
                            result.append(item)
                    return result
            '''},
        "tests/test_nested.py",
    )
)

add(
    bugfix(
        "bug-cache-key-collision",
        "Different arguments share a cache entry",
        "`cache_key('1', '23')` and `cache_key('12', '3')` give the same key, so unrelated "
        "results overwrite each other. Different arguments must give different keys. Fix it.",
        {
            "cachekeys.py": '''
                def cache_key(*parts):
                    """A string key that is the same for the same arguments and different otherwise."""
                    return "".join(str(part) for part in parts)
            ''',
            "tests/test_cachekeys.py": """
                from cachekeys import cache_key


                def test_same_arguments_same_key():
                    assert cache_key("a", 1) == cache_key("a", 1)


                def test_boundaries_matter():
                    assert cache_key("1", "23") != cache_key("12", "3")


                def test_order_matters():
                    assert cache_key("a", "b") != cache_key("b", "a")


                def test_number_of_arguments_matters():
                    assert cache_key("a") != cache_key("a", "")


                def test_is_a_string():
                    assert isinstance(cache_key(1, 2, 3), str)
            """,
        },
        {"cachekeys.py": '''
                import json


                def cache_key(*parts):
                    """A string key that is the same for the same arguments and different otherwise."""
                    return json.dumps([str(part) for part in parts])
            '''},
        "tests/test_cachekeys.py",
    )
)

add(
    bugfix(
        "bug-duration-minutes",
        "Minutes are counted as seconds",
        "`parse_duration('1h30m')` returns 3630 but should return 5400. Fix it.",
        {
            "durations.py": '''
                import re

                SECONDS = {"h": 3600, "m": 1, "s": 1}


                def parse_duration(text):
                    """Seconds in a duration like '1h30m', '45s' or '2m'."""
                    total = 0
                    for amount, unit in re.findall(r"(\\d+)([hms])", text):
                        total += int(amount) * SECONDS[unit]
                    return total
            ''',
            "tests/test_durations.py": """
                from durations import parse_duration


                def test_hours_and_minutes():
                    assert parse_duration("1h30m") == 5400


                def test_seconds():
                    assert parse_duration("45s") == 45


                def test_minutes():
                    assert parse_duration("2m") == 120


                def test_everything():
                    assert parse_duration("1h1m1s") == 3661
            """,
        },
        {"durations.py": '''
                import re

                SECONDS = {"h": 3600, "m": 60, "s": 1}


                def parse_duration(text):
                    """Seconds in a duration like '1h30m', '45s' or '2m'."""
                    total = 0
                    for amount, unit in re.findall(r"(\\d+)([hms])", text):
                        total += int(amount) * SECONDS[unit]
                    return total
            '''},
        "tests/test_durations.py",
    )
)

add(
    bugfix(
        "bug-queue-is-a-stack",
        "Jobs run in the wrong order",
        "`process_all` handles the most recently added job first; jobs should be handled in the "
        "order they were added (first in, first out). Find the cause and fix it.",
        {
            "jobqueue.py": '''
                class JobQueue:
                    """First in, first out."""

                    def __init__(self):
                        self._items = []

                    def enqueue(self, item):
                        self._items.append(item)

                    def dequeue(self):
                        return self._items.pop()

                    def __len__(self):
                        return len(self._items)
            ''',
            "worker.py": '''
                def process_all(queue):
                    """Handle every queued job, returning them in the order they were handled."""
                    handled = []
                    while len(queue):
                        handled.append(queue.dequeue())
                    return handled
            ''',
            "tests/test_worker.py": """
                import pytest

                from jobqueue import JobQueue
                from worker import process_all


                def make(*items):
                    queue = JobQueue()
                    for item in items:
                        queue.enqueue(item)
                    return queue


                def test_first_in_first_out():
                    assert process_all(make("a", "b", "c")) == ["a", "b", "c"]


                def test_dequeue_on_empty_raises():
                    with pytest.raises(IndexError):
                        JobQueue().dequeue()


                def test_length_tracks_contents():
                    queue = make(1, 2)
                    queue.dequeue()
                    assert len(queue) == 1
            """,
        },
        {"jobqueue.py": '''
                class JobQueue:
                    """First in, first out."""

                    def __init__(self):
                        self._items = []

                    def enqueue(self, item):
                        self._items.append(item)

                    def dequeue(self):
                        return self._items.pop(0)

                    def __len__(self):
                        return len(self._items)
            '''},
        "tests/test_worker.py",
    )
)

# ---------------------------------------------------------------------------------------
# Refactors
# ---------------------------------------------------------------------------------------

add(
    refactor(
        "refactor-rename-across-files",
        "Rename calc_total to compute_total everywhere",
        "Rename the function `calc_total` to `compute_total` in pricing.py and update every place "
        "that uses it. Nothing in the project should still mention `calc_total`.",
        {
            "pricing.py": '''
                def calc_total(prices, tax_rate=0.0):
                    """Sum of `prices` plus tax."""
                    return round(sum(prices) * (1 + tax_rate), 2)
            ''',
            "cart.py": """
                from pricing import calc_total


                class Cart:
                    def __init__(self):
                        self.prices = []

                    def add(self, price):
                        self.prices.append(price)

                    def total(self):
                        return calc_total(self.prices, 0.1)
            """,
            "checkout.py": """
                import pricing


                def receipt(prices):
                    return "TOTAL: %.2f" % pricing.calc_total(prices)
            """,
            "tests/test_rename.py": """
                from pathlib import Path

                import cart
                import checkout
                import pricing


                def test_new_name_works():
                    assert pricing.compute_total([10, 20], 0.1) == 33.0


                def test_old_name_is_gone():
                    assert not hasattr(pricing, "calc_total")


                def test_no_file_still_mentions_the_old_name():
                    root = Path(__file__).resolve().parents[1]
                    for path in root.rglob("*.py"):
                        if "tests" in path.relative_to(root).parts:
                            continue
                        assert "calc_total" not in path.read_text(), path.name


                def test_users_still_work():
                    c = cart.Cart()
                    c.add(10)
                    c.add(20)
                    assert c.total() == 33.0
                    assert checkout.receipt([5, 5]) == "TOTAL: 10.00"
            """,
        },
        {
            "pricing.py": '''
                def compute_total(prices, tax_rate=0.0):
                    """Sum of `prices` plus tax."""
                    return round(sum(prices) * (1 + tax_rate), 2)
            ''',
            "cart.py": """
                from pricing import compute_total


                class Cart:
                    def __init__(self):
                        self.prices = []

                    def add(self, price):
                        self.prices.append(price)

                    def total(self):
                        return compute_total(self.prices, 0.1)
            """,
            "checkout.py": """
                import pricing


                def receipt(prices):
                    return "TOTAL: %.2f" % pricing.compute_total(prices)
            """,
        },
        "tests/test_rename.py",
    )
)

add(
    refactor(
        "refactor-extract-validation",
        "Extract the duplicated order validation",
        "`place_order` and `update_order` in orders.py contain the same validation code. Move it "
        "into one function called `validate_order` that both of them call.",
        {
            "orders.py": """
                ORDERS = {}


                def place_order(order_id, items, customer):
                    if not customer:
                        raise ValueError("customer is required")
                    if not items:
                        raise ValueError("an order needs at least one item")
                    for item in items:
                        if item["quantity"] <= 0:
                            raise ValueError("quantities must be positive")
                    ORDERS[order_id] = {"items": items, "customer": customer}
                    return ORDERS[order_id]


                def update_order(order_id, items, customer):
                    if not customer:
                        raise ValueError("customer is required")
                    if not items:
                        raise ValueError("an order needs at least one item")
                    for item in items:
                        if item["quantity"] <= 0:
                            raise ValueError("quantities must be positive")
                    if order_id not in ORDERS:
                        raise KeyError(order_id)
                    ORDERS[order_id] = {"items": items, "customer": customer}
                    return ORDERS[order_id]
            """,
            "tests/test_orders.py": """
                import ast
                from pathlib import Path

                import pytest

                import orders

                GOOD = [{"sku": "a", "quantity": 2}]


                @pytest.fixture(autouse=True)
                def clean():
                    orders.ORDERS.clear()


                def test_place_and_update_still_work():
                    assert orders.place_order(1, GOOD, "ann")["customer"] == "ann"
                    assert orders.update_order(1, GOOD, "bob")["customer"] == "bob"


                @pytest.mark.parametrize("function", ["place_order", "update_order"])
                @pytest.mark.parametrize(
                    "items, customer, message",
                    [
                        (GOOD, "", "customer is required"),
                        ([], "ann", "at least one item"),
                        ([{"sku": "a", "quantity": 0}], "ann", "positive"),
                    ],
                )
                def test_validation_messages(function, items, customer, message):
                    with pytest.raises(ValueError, match=message):
                        getattr(orders, function)(1, items, customer)


                def test_update_of_unknown_order_still_fails():
                    with pytest.raises(KeyError):
                        orders.update_order(99, GOOD, "ann")


                def _called_names(function):
                    return {
                        node.func.id
                        for node in ast.walk(function)
                        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    }


                def test_validation_lives_in_one_function_that_both_call():
                    tree = ast.parse((Path(orders.__file__)).read_text())
                    functions = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
                    assert "validate_order" in functions
                    assert "validate_order" in _called_names(functions["place_order"])
                    assert "validate_order" in _called_names(functions["update_order"])


                def test_the_checks_are_no_longer_repeated():
                    source = Path(orders.__file__).read_text()
                    assert source.count("customer is required") == 1
            """,
        },
        {"orders.py": """
                ORDERS = {}


                def validate_order(items, customer):
                    if not customer:
                        raise ValueError("customer is required")
                    if not items:
                        raise ValueError("an order needs at least one item")
                    for item in items:
                        if item["quantity"] <= 0:
                            raise ValueError("quantities must be positive")


                def place_order(order_id, items, customer):
                    validate_order(items, customer)
                    ORDERS[order_id] = {"items": items, "customer": customer}
                    return ORDERS[order_id]


                def update_order(order_id, items, customer):
                    validate_order(items, customer)
                    if order_id not in ORDERS:
                        raise KeyError(order_id)
                    ORDERS[order_id] = {"items": items, "customer": customer}
                    return ORDERS[order_id]
            """},
        "tests/test_orders.py",
    )
)

add(
    refactor(
        "refactor-name-the-constants",
        "Replace magic numbers with named constants",
        "`quote` in shipping.py uses the bare numbers 0.2 (tax rate), 5.0 (flat shipping) and "
        "50 (order value above which shipping is free). Define module-level constants TAX_RATE, "
        "FLAT_SHIPPING and FREE_SHIPPING_THRESHOLD with those values and use them in `quote`.",
        {
            "shipping.py": '''
                def quote(subtotal):
                    """Total price: subtotal plus tax, plus shipping unless the order is large."""
                    shipping = 0.0 if subtotal > 50 else 5.0
                    return round(subtotal * (1 + 0.2) + shipping, 2)
            ''',
            "tests/test_shipping.py": """
                import ast
                from pathlib import Path

                import shipping


                def test_constants_have_the_agreed_values():
                    assert shipping.TAX_RATE == 0.2
                    assert shipping.FLAT_SHIPPING == 5.0
                    assert shipping.FREE_SHIPPING_THRESHOLD == 50


                def test_small_order_pays_shipping():
                    assert shipping.quote(10) == 17.0


                def test_large_order_ships_free():
                    assert shipping.quote(100) == 120.0


                def test_threshold_is_not_free():
                    assert shipping.quote(50) == 65.0


                def test_quote_has_no_bare_numbers_left():
                    tree = ast.parse(Path(shipping.__file__).read_text())
                    quote = next(
                        n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "quote"
                    )
                    numbers = [
                        n.value
                        for n in ast.walk(quote)
                        if isinstance(n, ast.Constant)
                        and isinstance(n.value, (int, float))
                        and not isinstance(n.value, bool)
                    ]
                    assert set(numbers) <= {0, 1, 2}, numbers
            """,
        },
        {"shipping.py": '''
                TAX_RATE = 0.2
                FLAT_SHIPPING = 5.0
                FREE_SHIPPING_THRESHOLD = 50


                def quote(subtotal):
                    """Total price: subtotal plus tax, plus shipping unless the order is large."""
                    shipping = 0.0 if subtotal > FREE_SHIPPING_THRESHOLD else FLAT_SHIPPING
                    return round(subtotal * (1 + TAX_RATE) + shipping, 2)
            '''},
        "tests/test_shipping.py",
    )
)

add(
    refactor(
        "refactor-move-function",
        "Move slugify into its own module",
        "Move the function `slugify` out of utils.py into a new module text.py, and update the "
        "modules that use it. utils.py should no longer define it.",
        {
            "utils.py": '''
                import re


                def slugify(title):
                    """'Hello, World!' -> 'hello-world'."""
                    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")


                def clamp(value, low, high):
                    return max(low, min(high, value))
            ''',
            "blog.py": """
                from utils import slugify


                def post_url(title):
                    return "/posts/" + slugify(title)
            """,
            "urls.py": """
                from utils import clamp, slugify


                def category_url(name, page):
                    return "/c/%s/%d" % (slugify(name), clamp(page, 1, 50))
            """,
            "tests/test_move.py": """
                from pathlib import Path

                import blog
                import text
                import urls
                import utils


                def test_slugify_lives_in_text():
                    assert text.slugify("Hello, World!") == "hello-world"


                def test_utils_no_longer_defines_it():
                    assert not hasattr(utils, "slugify")
                    assert utils.clamp(99, 1, 50) == 50


                def test_users_still_work():
                    assert blog.post_url("My First Post!") == "/posts/my-first-post"
                    assert urls.category_url("Open Source", 99) == "/c/open-source/50"


                def test_nobody_imports_it_from_utils():
                    root = Path(__file__).resolve().parents[1]
                    for path in root.rglob("*.py"):
                        if "tests" in path.relative_to(root).parts:
                            continue
                        for line in path.read_text().splitlines():
                            if line.startswith("from utils import"):
                                assert "slugify" not in line, (path.name, line)
            """,
        },
        {
            "utils.py": """
                def clamp(value, low, high):
                    return max(low, min(high, value))
            """,
            "text.py": '''
                import re


                def slugify(title):
                    """'Hello, World!' -> 'hello-world'."""
                    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
            ''',
            "blog.py": """
                from text import slugify


                def post_url(title):
                    return "/posts/" + slugify(title)
            """,
            "urls.py": """
                from text import slugify
                from utils import clamp


                def category_url(name, page):
                    return "/c/%s/%d" % (slugify(name), clamp(page, 1, 50))
            """,
        },
        "tests/test_move.py",
    )
)

add(
    refactor(
        "refactor-class-to-dataclass",
        "Turn Point into a dataclass",
        "`Point` in geometry.py writes its __init__, __repr__ and __eq__ by hand. Convert it to a "
        "dataclass and delete the hand-written methods; keep `distance_to` and everything else "
        "working the same.",
        {
            "geometry.py": """
                import math


                class Point:
                    def __init__(self, x, y):
                        self.x = x
                        self.y = y

                    def __repr__(self):
                        return f"Point(x={self.x!r}, y={self.y!r})"

                    def __eq__(self, other):
                        if not isinstance(other, Point):
                            return NotImplemented
                        return (self.x, self.y) == (other.x, other.y)

                    def distance_to(self, other):
                        return math.hypot(self.x - other.x, self.y - other.y)
            """,
            "tests/test_geometry.py": """
                import ast
                import dataclasses
                from pathlib import Path

                import geometry
                from geometry import Point


                def test_is_a_dataclass():
                    assert dataclasses.is_dataclass(Point)


                def test_equality_and_repr_unchanged():
                    assert Point(1, 2) == Point(1, 2)
                    assert Point(1, 2) != Point(2, 1)
                    assert repr(Point(1, 2)) == "Point(x=1, y=2)"


                def test_comparison_with_other_types():
                    assert Point(1, 2) != (1, 2)


                def test_distance():
                    assert Point(0, 0).distance_to(Point(3, 4)) == 5.0


                def test_attributes_can_still_change():
                    p = Point(1, 2)
                    p.x = 10
                    assert p.x == 10


                def test_hand_written_methods_are_gone():
                    tree = ast.parse(Path(geometry.__file__).read_text())
                    point = next(
                        n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "Point"
                    )
                    methods = {n.name for n in point.body if isinstance(n, ast.FunctionDef)}
                    assert methods == {"distance_to"}, methods
            """,
        },
        {"geometry.py": """
                import math
                from dataclasses import dataclass


                @dataclass
                class Point:
                    x: float
                    y: float

                    def distance_to(self, other):
                        return math.hypot(self.x - other.x, self.y - other.y)
            """},
        "tests/test_geometry.py",
    )
)


def get(task_id: str) -> Task:
    for task in TASKS:
        if task.id == task_id:
            return task
    raise KeyError(f"No benchmark task called '{task_id}'")


def select(ids: Optional[List[str]] = None, kind: Optional[str] = None) -> List[Task]:
    chosen = [get(i) for i in ids] if ids else list(TASKS)
    return [t for t in chosen if kind is None or t.kind == kind]
