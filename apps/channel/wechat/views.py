import logging
import xml.etree.ElementTree as ET
from django.http import HttpResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from .crypto import WXBizMsgCrypt
from .handlers import handle_wechat_message

logger = logging.getLogger('apps')

@csrf_exempt
def wechat_webhook_view(request):
    msg_signature = request.GET.get('msg_signature', '')
    timestamp = request.GET.get('timestamp', '')
    nonce = request.GET.get('nonce', '')

    wxcpt = WXBizMsgCrypt(
        settings.WECHAT_TOKEN,
        settings.WECHAT_ENCODING_AES_KEY,
        settings.WECHAT_CORP_ID
    )

    if request.method == 'GET':
        echostr = request.GET.get('echostr', '')
        if not echostr:
            return HttpResponseBadRequest('Missing echostr')
            
        ret, reply_echostr = wxcpt.VerifyURL(msg_signature, timestamp, nonce, echostr)
        if ret != 0:
            logger.error(f"WeChat URL verification failed with code: {ret}")
            return HttpResponseBadRequest('Verification failed')
            
        return HttpResponse(reply_echostr)

    elif request.method == 'POST':
        # 接收并解密消息
        ret, xml_content = wxcpt.DecryptMsg(request.body.decode('utf-8'), msg_signature, timestamp, nonce)
        if ret != 0:
            logger.error(f"WeChat message decryption failed with code: {ret}")
            return HttpResponseBadRequest('Decryption failed')
            
        try:
            xml_tree = ET.fromstring(xml_content)
            msg_type = xml_tree.find('MsgType').text
            from_user = xml_tree.find('FromUserName').text
            
            # 目前主要处理文本消息中的链接
            if msg_type == 'text':
                content = xml_tree.find('Content').text
                reply_content = handle_wechat_message(msg_type, content, from_user)
            else:
                reply_content = handle_wechat_message(msg_type, "Non-text message", from_user)
                
            # 构造回复给微信服务器的消息
            xml_reply = f"""<xml>
<ToUserName><![CDATA[{from_user}]]></ToUserName>
<FromUserName><![CDATA[{settings.WECHAT_CORP_ID}]]></FromUserName>
<CreateTime>{timestamp}</CreateTime>
<MsgType><![CDATA[text]]></MsgType>
<Content><![CDATA[{reply_content}]]></Content>
</xml>"""
            ret, encrypt_xml = wxcpt.EncryptMsg(xml_reply, nonce, timestamp)
            if ret != 0:
                logger.error(f"WeChat message encryption failed with code: {ret}")
                return HttpResponse('success')
                
            return HttpResponse(encrypt_xml)
            
        except Exception as e:
            logger.error(f"Error processing WeChat message: {str(e)}")
            return HttpResponse('success')

    return HttpResponseBadRequest('Method not allowed')
