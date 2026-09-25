import os
import secrets
from pathlib import Path


root = Path(__file__).resolve().parents[1]
target = root / ".env"
values = (root / ".env.example").read_text()
while "replace-with-random-hex" in values:
    values = values.replace("replace-with-random-hex", secrets.token_hex(24), 1)
try:
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
except FileExistsError:
    raise SystemExit(".env already exists; left unchanged")
with os.fdopen(fd, "w") as file:
    file.write(values)
print("Created .env with random credentials. Set your domain and contact User-Agent before deployment.")
