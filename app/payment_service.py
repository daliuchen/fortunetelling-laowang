import redis

redis_client = redis.Redis(host='localhost', port=6379, db=6)


class PaymentService:
    @classmethod
    def cache_key(cls, session_id):
        return f"payment:{session_id}"

    def __init__(self, session_id):
        self.session_id = session_id

    def is_payment(self):
        key = PaymentService.cache_key(self.session_id)
        return redis_client.exists(key)

    def payment(self):
        key = PaymentService.cache_key(self.session_id)
        redis_client.set(key, self.session_id)

    def del_payment(self):
        key = PaymentService.cache_key(self.session_id)
        redis_client.delete(key)

    def set_not_payment_white_list(self):
        key = f"not_payment_white_list:{self.session_id}"
        redis_client.set(key, "1")

    def is_exists_not_payment_white_list(self):
        key = f"not_payment_white_list:{self.session_id}"
        return redis_client.exists(key)
    def del_exists_not_payment_white_list(self):
        key = f"not_payment_white_list:{self.session_id}"
        redis_client.delete(key)