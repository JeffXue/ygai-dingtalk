import base64
import socket
import string
import struct
import random
import time
import hashlib
from Crypto.Cipher import AES
import xml.etree.cElementTree as ET

class WXBizMsgCrypt(object):
    def __init__(self, sToken, sEncodingAESKey, sCorpId):
        try:
            self.key = base64.b64decode(sEncodingAESKey + "=")
            assert len(self.key) == 32
        except:
            raise Exception("encodingAESKey unvalid")
        self.m_sToken = sToken
        self.m_sCorpID = sCorpId

    def VerifyURL(self, sMsgSignature, sTimeStamp, sNonce, sEchoStr):
        sha1 = hashlib.sha1()
        sha1.update(self.get_sha1(self.m_sToken, sTimeStamp, sNonce, sEchoStr).encode('utf-8'))
        if sha1.hexdigest() != sMsgSignature:
            return -40001, None
        ret, sReplyEchoStr = self.decrypt(sEchoStr)
        if ret != 0:
            return ret, None
        return ret, sReplyEchoStr

    def DecryptMsg(self, sPostData, sMsgSignature, sTimeStamp, sNonce):
        try:
            xml_tree = ET.fromstring(sPostData)
            encrypt = xml_tree.find("Encrypt").text
        except Exception as e:
            return -40002, None

        sha1 = hashlib.sha1()
        sha1.update(self.get_sha1(self.m_sToken, sTimeStamp, sNonce, encrypt).encode('utf-8'))
        if sha1.hexdigest() != sMsgSignature:
            return -40001, None

        ret, xml_content = self.decrypt(encrypt)
        return ret, xml_content

    def EncryptMsg(self, sReplyMsg, sNonce, sTimeStamp=None):
        ret, encrypt = self.encrypt(sReplyMsg, self.m_sCorpID)
        if ret != 0:
            return ret, None

        if not sTimeStamp:
            sTimeStamp = str(int(time.time()))

        sha1 = hashlib.sha1()
        sha1.update(self.get_sha1(self.m_sToken, sTimeStamp, sNonce, encrypt).encode('utf-8'))
        sMsgSignature = sha1.hexdigest()

        xml_format = "<xml><Encrypt><![CDATA[{encrypt}]]></Encrypt><MsgSignature><![CDATA[{signature}]]></MsgSignature><TimeStamp>{timestamp}</TimeStamp><Nonce><![CDATA[{nonce}]]></Nonce></xml>"
        return 0, xml_format.format(encrypt=encrypt, signature=sMsgSignature, timestamp=sTimeStamp, nonce=sNonce)

    def decrypt(self, text):
        try:
            cryptor = AES.new(self.key, AES.MODE_CBC, self.key[:16])
            plain_text = cryptor.decrypt(base64.b64decode(text))
        except Exception as e:
            return -40004, None
        try:
            pad = plain_text[-1]
            content = plain_text[16:-pad]
            xml_len = socket.ntohl(struct.unpack("I", content[: 4])[0])
            xml_content = content[4 : xml_len + 4].decode('utf-8')
            from_corpid = content[xml_len + 4:].decode('utf-8')
        except Exception as e:
            return -40005, None
        if from_corpid != self.m_sCorpID:
            return -40005, None
        return 0, xml_content

    def encrypt(self, text, corpid):
        text = text.encode('utf-8')
        tmp_list = []
        tmp_list.append(self.get_random_str(16).encode('utf-8'))
        length = struct.pack(b"I", socket.htonl(len(text)))
        tmp_list.append(length)
        tmp_list.append(text)
        tmp_list.append(corpid.encode('utf-8'))

        obj = b"".join(tmp_list)
        pad_len = 32 - (len(obj) % 32)
        pad_str = chr(pad_len) * pad_len
        obj += pad_str.encode('utf-8')

        try:
            cryptor = AES.new(self.key, AES.MODE_CBC, self.key[:16])
            ciphertext = cryptor.encrypt(obj)
            return 0, base64.b64encode(ciphertext).decode('utf-8')
        except Exception as e:
            return -40006, None

    def get_random_str(self, length):
        rule = string.ascii_letters + string.digits
        return "".join(random.sample(rule, length))

    def get_sha1(self, token, timestamp, nonce, encrypt):
        sort_list = [token, timestamp, nonce, encrypt]
        sort_list.sort()
        return "".join(sort_list)
