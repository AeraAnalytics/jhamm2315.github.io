from pathlib import Path
from uuid import uuid4
from cryptography.fernet import Fernet, InvalidToken


class Vault:
    def __init__(self, root: str, key: str): self.root=Path(root); self.cipher=Fernet(key.encode()); self.root.mkdir(parents=True,exist_ok=True)
    def put(self, content: bytes) -> str:
        oid=uuid4().hex; (self.root/oid).write_bytes(self.cipher.encrypt(content)); return oid
    def get(self, oid: str) -> bytes:
        if len(oid)!=32 or not oid.isalnum(): raise ValueError("invalid opaque document id")
        return self.cipher.decrypt((self.root/oid).read_bytes())
