from redis import Redis
from rq import Queue, Worker

from app.main import settings
import app.phase3  # noqa: F401


def main():
    connection = Redis.from_url(settings.redis_url)
    queue = Queue('renders', connection=connection)
    worker = Worker([queue], connection=connection, name='product-ads-render-worker')
    worker.work(with_scheduler=False)


if __name__ == '__main__':
    main()
