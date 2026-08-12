"""Fail-safe entry point for the dormant P0 browser task definition.

The P0 launch adapter set uses documented direct HTTP feeds, so no browser work is
currently emitted. Keeping this image non-polling guarantees idle-to-zero behavior
until a separately reviewed browser adapter and durable event contract are added.
"""


def main() -> None:
    print("No browser-required P0 adapter is enabled; exiting safely.")


if __name__ == "__main__":
    main()
