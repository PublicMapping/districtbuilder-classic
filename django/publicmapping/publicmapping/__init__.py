import os

REDIS_URL = 'redis://:{password}@{host}:{port}/{db}'.format(
    password=os.getenv('KEY_VALUE_STORE_PASSWORD'),
    host=os.getenv('KEY_VALUE_STORE_HOST'),
    port=os.getenv('KEY_VALUE_STORE_PORT'),
    db=os.getenv('KEY_VALUE_STORE_DB'),
)
