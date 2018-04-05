#!/user/bin/env python3

import logging
log = logging.getLogger(__name__)

import requests
import re
import uuid
import json

# Returns true is added successfully
def addDownload(link):
    r = requests.get(link) # get the page from the link
    assert(r.status_code == 200)

    data = ''.join(str(r.text).split()) # strip new lines/spaces/tabs
    jData = re.search('<script>transferSpec=(.*);connectSettings=.*<\/script>', data) # steal the javascript/json config that contains useful info
    assert(jData is not None) # and fail otherwise

    headers = {'Content-Type':'text/plain;charset=UTF-8', 'Origin':'https://aspera.motionpicturesolutions.net', 'Referer':link}
    jsonData = {"transfer_specs":[{"transfer_spec":json.loads(jData.group(1)),"aspera_connect_settings":{"allow_dialogs":"no","app_id":"localhost","request_id":str(uuid.uuid4()),"back_link":link}}],"aspera_connect_settings":{"app_id":"localhost"}}

    r = requests.post("https://local.connectme.us:43003/v5/connect/transfers/start", headers=headers, json=jsonData)

    if not (r.status_code == requests.codes.ok):
        log.error('Failed to add aspera link, status = %s, reason = %s', r.status_code, r.reason)
        return False
    else:
        return True
