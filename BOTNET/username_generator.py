import random
import string
from typing import Optional

def generate_random_username(length: int = 12, prefix: str = "") -> str:
    if length < 5:
        length = 5
    elif length > 32:
        length = 32
    chars = string.ascii_letters + string.digits
    random_part = ''.join(random.choice(chars) for _ in range(length))
    if prefix:
        username = prefix + random_part
        if len(username) > 32:
            username = prefix + random_part[:32 - len(prefix)]
    else:
        username = random_part
    if username[0].isdigit():
        username = random.choice(string.ascii_letters) + username[1:]
    return username

def generate_unique_username(min_length: int = 8, max_length: int = 15, attempts: int = 10) -> str:
    length = random.randint(min_length, max_length)
    return generate_random_username(length=length)
