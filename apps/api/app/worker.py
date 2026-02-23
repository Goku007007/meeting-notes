from app.queue import get_queue


def run_worker() -> None:
    """Run an RQ worker process for the default queue."""
    try:
        from rq import Worker
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "RQ/Redis dependencies missing; install redis/rq."
        ) from exc

    queue = get_queue()
    worker = Worker([queue], connection=queue.connection)
    worker.work()


if __name__ == "__main__":
    run_worker()
