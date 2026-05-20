"""
Confidential Conversations Module for Project Aegis Ghost
End-to-end encrypted secure messaging system
"""

import json
import hashlib
import secrets
import base64
import os
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, field
from cryptography.hazmat.primitives.asymmetric import x25519
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import core.encryption as crypto


@dataclass
class SecureMessage:
    """Encrypted message structure"""
    id: str
    sender_id: str
    recipient_id: str
    encrypted_content: bytes
    nonce: bytes
    timestamp: str
    message_type: str = "text"
    ephemeral: bool = False
    destroy_at: Optional[str] = None
    signature: Optional[bytes] = None
    read: bool = False
    read_by: List[str] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'sender_id': self.sender_id,
            'recipient_id': self.recipient_id,
            'encrypted_content': base64.b64encode(self.encrypted_content).decode(),
            'nonce': base64.b64encode(self.nonce).decode(),
            'timestamp': self.timestamp,
            'message_type': self.message_type,
            'ephemeral': self.ephemeral,
            'destroy_at': self.destroy_at,
            'signature': base64.b64encode(self.signature).decode() if self.signature else None,
            'read': self.read,
            'read_by': self.read_by
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'SecureMessage':
        return cls(
            id=data['id'],
            sender_id=data['sender_id'],
            recipient_id=data['recipient_id'],
            encrypted_content=base64.b64decode(data['encrypted_content']),
            nonce=base64.b64decode(data['nonce']),
            timestamp=data['timestamp'],
            message_type=data.get('message_type', 'text'),
            ephemeral=data.get('ephemeral', False),
            destroy_at=data.get('destroy_at'),
            signature=base64.b64decode(data['signature']) if data.get('signature') else None,
            read=data.get('read', False),
            read_by=data.get('read_by', [])
        )


@dataclass
class Conversation:
    """Secure conversation between users"""
    id: str
    participants: List[str]
    created_at: str
    last_activity: str
    encryption_key: bytes
    name: Optional[str] = None
    is_group: bool = False
    messages: List[SecureMessage] = field(default_factory=list)


class KeyExchange:
    """
    X25519 key exchange for E2EE key derivation.
    """
    
    def __init__(self):
        self.private_key = x25519.X25519PrivateKey.generate()
        self.public_key = self.private_key.public_key()
    
    def get_public_key_pem(self) -> bytes:
        """Export public key in PEM format"""
        return self.public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
    
    @classmethod
    def from_pem(cls, pem_data: bytes) -> 'KeyExchange':
        """Create KeyExchange with an imported peer public key."""
        instance = cls()
        instance.public_key = serialization.load_pem_public_key(pem_data)
        return instance
    
    def derive_shared_key(self, peer_public_key_pem: bytes) -> bytes:
        """Derive shared encryption key using X25519 + HKDF."""
        peer_public_key = serialization.load_pem_public_key(peer_public_key_pem)
        shared_key = self.private_key.exchange(peer_public_key)
        
        # Derive symmetric key using HKDF
        derived_key = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=None,
            info=b'AegisGhost-KeyDerivation'
        ).derive(shared_key)
        
        return derived_key
    
    def encrypt_for_peer(self, peer_public_key_pem: bytes, plaintext: bytes) -> tuple:
        """Encrypt plaintext using a derived shared key."""
        aes_key = self.derive_shared_key(peer_public_key_pem)
        nonce = secrets.token_bytes(12)
        aesgcm = AESGCM(aes_key)
        ciphertext = aesgcm.encrypt(nonce, plaintext, None)
        return b"", nonce, ciphertext
    
    def decrypt_from_peer(self, encrypted_aes_key: bytes, nonce: bytes, 
                         ciphertext: bytes) -> bytes:
        """Backward-compatible placeholder for old API shape."""
        raise NotImplementedError(
            "decrypt_from_peer requires shared-key context; use derive_shared_key + AESGCM decrypt."
        )


class SecureConversationManager:
    """
    Manages end-to-end encrypted conversations
    """
    
    def __init__(self, storage_path: str = "data/conversations"):
        self.storage_path = storage_path
        os.makedirs(storage_path, exist_ok=True)
        self.conversations: Dict[str, Conversation] = {}
        self.key_exchange = KeyExchange()
        self._at_rest_key = self._load_at_rest_key()
        self.load_conversations()

    def _load_at_rest_key(self) -> Optional[bytes]:
        secret = os.getenv("DATA_AT_REST_KEY")
        if not secret:
            return None
        return hashlib.sha256(secret.encode("utf-8")).digest()

    @staticmethod
    def _norm_identifier(value: Optional[str]) -> str:
        return (value or "").strip().lower()

    def _resolve_user_keys(self, user_id: str, user_aliases: Optional[List[str]] = None) -> set[str]:
        keys = {self._norm_identifier(user_id)}
        if user_aliases:
            keys.update(self._norm_identifier(alias) for alias in user_aliases)
        keys.discard("")
        return keys

    def _conversation_participant_keys(self, conversation: Conversation) -> set[str]:
        return {self._norm_identifier(p) for p in conversation.participants if self._norm_identifier(p)}

    def _user_in_conversation(self, conversation: Conversation, user_id: str, user_aliases: Optional[List[str]] = None) -> bool:
        return bool(self._conversation_participant_keys(conversation) & self._resolve_user_keys(user_id, user_aliases))

    @staticmethod
    def _utcnow() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _iso_now_z() -> str:
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    @staticmethod
    def _parse_iso_ts(value: str) -> datetime:
        raw = (value or "").strip()
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        dt = datetime.fromisoformat(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    
    def create_conversation(self, participants: List[str], 
                           name: Optional[str] = None) -> Conversation:
        """Create new secure conversation"""
        conv_id = secrets.token_urlsafe(16)
        encryption_key = secrets.token_bytes(32)
        
        conversation = Conversation(
            id=conv_id,
            participants=participants,
            created_at=self._iso_now_z(),
            last_activity=self._iso_now_z(),
            encryption_key=encryption_key,
            name=name or f"Secure Chat {conv_id[:8]}",
            is_group=len(participants) > 2
        )
        
        self.conversations[conv_id] = conversation
        self.save_conversation(conversation)
        
        return conversation
    
    def send_message(self, conversation_id: str, sender_id: str,
                     content: str, ephemeral: bool = False,
                     destroy_after_seconds: Optional[int] = None,
                     sender_aliases: Optional[List[str]] = None) -> SecureMessage:
        """
        Send encrypted message to conversation
        
        Args:
            conversation_id: Conversation ID
            sender_id: Sender's user ID
            content: Message content (plaintext)
            ephemeral: Message self-destructs when read
            destroy_after_seconds: Auto-delete timer
            
        Returns:
            Encrypted SecureMessage
        """
        conversation = self.conversations.get(conversation_id)
        if not conversation:
            raise ValueError("Conversation not found")
        if not self._user_in_conversation(conversation, sender_id, sender_aliases):
            raise PermissionError("Sender not in conversation")
        
        # Generate message ID and timestamp
        message_id = secrets.token_urlsafe(12)
        timestamp = self._iso_now_z()
        
        # Calculate destroy time if needed
        destroy_at = None
        if destroy_after_seconds:
            destroy_time = self._utcnow() + timedelta(seconds=destroy_after_seconds)
            destroy_at = destroy_time.isoformat().replace("+00:00", "Z")
        
        # Prepare message data
        message_data = {
            'id': message_id,
            'sender': sender_id,
            'content': content,
            'timestamp': timestamp
        }
        
        plaintext = json.dumps(message_data).encode()
        
        # Encrypt message
        nonce = secrets.token_bytes(12)
        aesgcm = AESGCM(conversation.encryption_key)
        aad = f"conv:{conversation_id}:sender:{sender_id}".encode("utf-8")
        encrypted_content = aesgcm.encrypt(nonce, plaintext, aad)
        
        # Sign message
        message_bytes = f"{message_id}:{sender_id}:{timestamp}".encode()
        signature = crypto.sign_message(message_bytes)
        
        message = SecureMessage(
            id=message_id,
            sender_id=sender_id,
            recipient_id=conversation_id,
            encrypted_content=encrypted_content,
            nonce=nonce,
            timestamp=timestamp,
            message_type="text",
            ephemeral=ephemeral,
            destroy_at=destroy_at,
            signature=signature
        )
        
        conversation.messages.append(message)
        conversation.last_activity = timestamp
        self.save_conversation(conversation)
        
        return message
    
    def get_messages(self, conversation_id: str, user_id: str,
                     limit: int = 50, user_aliases: Optional[List[str]] = None) -> List[Dict]:
        """
        Get and decrypt messages for user
        
        Args:
            conversation_id: Conversation ID
            user_id: Requesting user's ID
            limit: Maximum messages to return
            
        Returns:
            List of decrypted messages
        """
        conversation = self.conversations.get(conversation_id)
        if not conversation:
            raise ValueError("Conversation not found")
        
        if not self._user_in_conversation(conversation, user_id, user_aliases):
            raise PermissionError("User not in conversation")
        
        decrypted_messages = []
        now = self._utcnow()
        kept_messages = []
        
        for message in conversation.messages:
            # Check if message should be destroyed
            if message.destroy_at:
                destroy_time = self._parse_iso_ts(message.destroy_at)
                if now > destroy_time:
                    continue
            
            # Decrypt message
            try:
                aesgcm = AESGCM(conversation.encryption_key)
                aad = f"conv:{conversation_id}:sender:{message.sender_id}".encode("utf-8")
                plaintext = aesgcm.decrypt(message.nonce, message.encrypted_content, aad)
                message_data = json.loads(plaintext.decode())
                if not isinstance(message.read_by, list):
                    message.read_by = []
                normalized_read_by = {self._norm_identifier(r) for r in message.read_by}
                requester_keys = self._resolve_user_keys(user_id, user_aliases)
                
                decrypted_messages.append({
                    'id': message.id,
                    'sender': message_data['sender'],
                    'content': message_data['content'],
                    'timestamp': message.timestamp,
                    'type': message.message_type,
                    'ephemeral': message.ephemeral,
                    'read': bool(requester_keys & normalized_read_by),
                    'signature_valid': crypto.verify_signature(
                        f"{message.id}:{message_data['sender']}:{message.timestamp}".encode(),
                        message.signature
                    )
                })
                
                # Mark as read
                sender_key = self._norm_identifier(message.sender_id)
                if self._norm_identifier(user_id) != sender_key and not (requester_keys & normalized_read_by):
                    message.read_by.append(user_id)
                    message.read = True

                # Destroy ephemeral message once all intended recipients have read it
                should_destroy = False
                if message.ephemeral:
                    required_readers = {
                        self._norm_identifier(p)
                        for p in conversation.participants
                        if self._norm_identifier(p) and self._norm_identifier(p) != sender_key
                    }
                    normalized_read_by = {self._norm_identifier(r) for r in message.read_by}
                    if required_readers and required_readers.issubset(normalized_read_by):
                        should_destroy = True
                if not should_destroy:
                    kept_messages.append(message)
                    
            except Exception:
                decrypted_messages.append({
                    'id': message.id,
                    'error': 'Failed to decrypt message',
                    'timestamp': message.timestamp
                })
                kept_messages.append(message)
        
        conversation.messages = kept_messages
        self.save_conversation(conversation)
        return decrypted_messages[-limit:]
    
    def verify_message_integrity(self, message: SecureMessage, 
                                 expected_sender: str) -> bool:
        """Verify message signature and sender"""
        if message.sender_id != expected_sender:
            return False
        
        if not crypto.verify_signature(
            f"{message.id}:{message.sender_id}:{message.timestamp}".encode(),
            message.signature
        ):
            return False
        
        return True
    
    def delete_message(self, conversation_id: str, message_id: str,
                       user_id: str, user_aliases: Optional[List[str]] = None) -> bool:
        """Delete a message from conversation"""
        conversation = self.conversations.get(conversation_id)
        if not conversation:
            return False
        
        if not self._user_in_conversation(conversation, user_id, user_aliases):
            return False
        
        for i, message in enumerate(conversation.messages):
            if message.id == message_id:
                if message.sender_id == user_id:
                    conversation.messages.pop(i)
                    self.save_conversation(conversation)
                    return True
                else:
                    return False
        
        return False
    
    def destroy_conversation(self, conversation_id: str) -> bool:
        """Permanently destroy conversation and all messages"""
        conversation = self.conversations.get(conversation_id)
        if not conversation:
            return False
        
        # Overwrite messages with zeros
        for message in conversation.messages:
            message.encrypted_content = b'\x00' * len(message.encrypted_content)
        
        # Remove from memory and storage
        del self.conversations[conversation_id]
        
        file_path = os.path.join(self.storage_path, f"{conversation_id}.json")
        if os.path.exists(file_path):
            os.remove(file_path)
        
        return True
    
    def delete_messages(self, conversation_id: str, message_ids: List[str], user_id: str) -> bool:
        """Delete specific messages from conversation"""
        conversation = self.conversations.get(conversation_id)
        if not conversation:
            return False
        
        # Check if user is in conversation
        user_keys = self._resolve_user_keys(user_id)
        participant_keys = {self._norm_identifier(p) for p in conversation.participants}
        if not (user_keys & participant_keys):
            return False
        
        # Mark messages for deletion (overwrite with zeros)
        deleted_count = 0
        for message in conversation.messages:
            if message.id in message_ids:
                message.encrypted_content = b'\x00' * len(message.encrypted_content)
                message.id = f"deleted_{message.id}"
                deleted_count += 1
        
        # Save updated conversation
        if deleted_count > 0:
            self.save_conversation(conversation)
        
        return deleted_count > 0
    
    def save_conversation(self, conversation: Conversation):
        """Save conversation to encrypted JSON file"""
        file_path = os.path.join(self.storage_path, f"{conversation.id}.json")
        
        data = {
            'id': conversation.id,
            'participants': conversation.participants,
            'created_at': conversation.created_at,
            'last_activity': conversation.last_activity,
            'encryption_key': base64.b64encode(conversation.encryption_key).decode(),
            'name': conversation.name,
            'is_group': conversation.is_group,
            'messages': [m.to_dict() for m in conversation.messages]
        }
        
        with open(file_path, 'w') as f:
            if self._at_rest_key:
                raw = json.dumps(data, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
                wrapped = crypto.encrypt_aes_gcm(raw, self._at_rest_key)
                f.write(json.dumps({"v": 2, "enc": base64.b64encode(wrapped).decode("utf-8")}))
            else:
                json.dump(data, f, indent=2)
    
    def load_conversations(self):
        """Load all conversations from storage"""
        if not os.path.exists(self.storage_path):
            return
        
        for filename in os.listdir(self.storage_path):
            if filename.endswith('.json'):
                file_path = os.path.join(self.storage_path, filename)
                try:
                    with open(file_path, 'r') as f:
                        payload = json.load(f)
                    if isinstance(payload, dict) and payload.get("v") == 2 and payload.get("enc") and self._at_rest_key:
                        dec = crypto.decrypt_aes_gcm(base64.b64decode(payload["enc"]), self._at_rest_key)
                        data = json.loads(dec.decode("utf-8"))
                    else:
                        data = payload
                    
                    conversation = Conversation(
                        id=data['id'],
                        participants=data['participants'],
                        created_at=data['created_at'],
                        last_activity=data['last_activity'],
                        encryption_key=base64.b64decode(data['encryption_key']),
                        name=data.get('name'),
                        is_group=data.get('is_group', False),
                        messages=[SecureMessage.from_dict(m) for m in data.get('messages', [])]
                    )
                    
                    self.conversations[conversation.id] = conversation
                    
                except Exception as e:
                    print(f"Failed to load conversation {filename}: {e}")
    
    def get_user_conversations(self, user_id: str, user_aliases: Optional[List[str]] = None) -> List[Dict]:
        """Get all conversations for a user"""
        user_convs = []
        now = self._utcnow()
        user_keys = self._resolve_user_keys(user_id, user_aliases)
        
        for conv in self.conversations.values():
            participant_keys = self._conversation_participant_keys(conv)
            if participant_keys & user_keys:
                unread_count = sum(1 for m in conv.messages 
                                  if (
                                      self._norm_identifier(m.sender_id) not in user_keys
                                      and not ({self._norm_identifier(r) for r in (m.read_by or [])} & user_keys)
                                      and (not m.destroy_at or self._parse_iso_ts(m.destroy_at) > now)
                                  ))
                
                user_convs.append({
                    'id': conv.id,
                    'name': conv.name,
                    'participants': conv.participants,
                    'is_group': conv.is_group,
                    'last_activity': conv.last_activity,
                    'unread_count': unread_count,
                    'message_count': len(conv.messages)
                })
        
        # Sort by last activity
        user_convs.sort(key=lambda x: x['last_activity'], reverse=True)
        
        return user_convs


class SecureFileTransfer:
    """
    Encrypted file sharing within conversations
    """
    
    def __init__(self, storage_path: str = "data/secure_files"):
        self.storage_path = storage_path
        os.makedirs(storage_path, exist_ok=True)
    
    def encrypt_file(self, file_path: str, encryption_key: bytes) -> tuple:
        """
        Encrypt file for secure sharing
        
        Returns:
            (encrypted_path, nonce, file_hash)
        """
        with open(file_path, 'rb') as f:
            plaintext = f.read()
        
        nonce = secrets.token_bytes(12)
        aesgcm = AESGCM(encryption_key)
        ciphertext = aesgcm.encrypt(nonce, plaintext, None)
        
        # Save encrypted file
        file_hash = hashlib.sha256(plaintext).hexdigest()
        output_path = os.path.join(self.storage_path, f"{file_hash[:16]}.enc")
        
        with open(output_path, 'wb') as f:
            f.write(ciphertext)
        
        return output_path, nonce, file_hash
    
    def decrypt_file(self, encrypted_path: str, encryption_key: bytes,
                     nonce: bytes, output_path: str) -> bool:
        """Decrypt shared file"""
        try:
            with open(encrypted_path, 'rb') as f:
                ciphertext = f.read()
            
            aesgcm = AESGCM(encryption_key)
            plaintext = aesgcm.decrypt(nonce, ciphertext, None)
            
            with open(output_path, 'wb') as f:
                f.write(plaintext)
            
            return True
            
        except Exception as e:
            print(f"Decryption failed: {e}")
            return False
    
    def verify_file_integrity(self, file_path: str, expected_hash: str) -> bool:
        """Verify file hasn't been tampered with"""
        with open(file_path, 'rb') as f:
            actual_hash = hashlib.sha256(f.read()).hexdigest()
        
        return actual_hash == expected_hash


# Ephemeral message utilities
def create_self_destruct_message(content: str, seconds: int = 60) -> Dict:
    """
    Create a self-destructing message
    
    Args:
        content: Message content
        seconds: Seconds until destruction
        
    Returns:
        Message with destroy timestamp
    """
    now = datetime.now(timezone.utc)
    destroy_at = now + timedelta(seconds=seconds)
    
    return {
        'content': content,
        'created_at': now.isoformat(),
        'destroy_at': destroy_at.isoformat(),
        'lifetime_seconds': seconds,
        'destroyed': False
    }


def check_message_expiry(message: Dict) -> bool:
    """Check if message should be destroyed"""
    if message.get('destroyed', False):
        return True
    
    destroy_at = message.get('destroy_at')
    if destroy_at:
        raw = str(destroy_at).strip()
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        dt = datetime.fromisoformat(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) >= dt:
            message['destroyed'] = True
            return True
    
    return False
