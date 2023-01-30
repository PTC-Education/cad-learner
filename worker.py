import os 
# import django 
# from django.conf import settings
import redis 
from rq import Worker, Queue, Connection 

listen = ['high', 'default', 'low']
redis_url = os.getenv("REDIS_URL", 'redis://localhost:6379')
conn = redis.from_url(redis_url)

if __name__ == '__main__': 
    # settings.configure()
    # django.setup()
    with Connection(conn): 
        worker = Worker(map(Queue, listen))
        worker.work() 
