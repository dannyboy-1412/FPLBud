from perf.suite import run


def main() -> None:
    report = run()
    slowest = report.slowest
    print(f"slowest {slowest.module}.{slowest.name} mean {slowest.timing.mean_s:.4f}s")
    spot = report.slow_spot
    if spot is not None:
        parent, entry = spot
        print(f"slow spot in {parent.name}: {entry.function} ({entry.location})")


if __name__ == "__main__":
    main()
