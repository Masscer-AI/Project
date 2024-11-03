import time
from streaming.server.utils.brave_search import (
    search_brave,
    search_brave_query,
    query_brave,
)

print("Running test for concurrent and sequential search brave")


def test_search_brave():
    # Measure time for concurrent search
    start_time = time.time()
    result = search_brave("What is the weather in Cuenca, Ecuador?", "")
    concurrent_duration = time.time() - start_time
    print(f"Concurrent search took {concurrent_duration:.2f} seconds.")
    # print(type(result), "TYPE RESULT")
    print(result, "RESULT")


def test_search_brave_query():
    # Measure time for concurrent search
    start_time = time.time()
    search_brave_query("What is the weather in Cuenca, Ecuador?", "US")
    concurrent_duration = time.time() - start_time
    print(f"Concurrent search took {concurrent_duration:.2f} seconds.")


test_search_brave()
# test_search_brave_query()


def test_query_brave():
    result = query_brave("What is the weather in Tokyo?")
    print(result, "RESULT")


# test_query_brave()
