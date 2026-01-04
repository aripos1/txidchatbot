import time

class SimpleCache:
    def __init__(self, ttl_seconds=60):
        self.cache = {}
        self.ttl_seconds = ttl_seconds

    def get(self, key):
        if key in self.cache:
            result, timestamp = self.cache[key]
            if time.time() - timestamp < self.ttl_seconds:
                print(f"[Cache Hit] Key: {key}")
                return result
            else:
                print(f"[Cache Miss] Key: {key} (Expired)")
                del self.cache[key]
        else:
            print(f"[Cache Miss] Key: {key}")
        return None

    def set(self, key, value):
        self.cache[key] = (value, time.time())
        print(f"[Cache Set] Key: {key}")

    def delete(self, key):
        if key in self.cache:
            del self.cache[key]
            print(f"[Cache Delete] Key: {key}")

cache = SimpleCache(ttl_seconds=300) # 5분 TTL 설정
