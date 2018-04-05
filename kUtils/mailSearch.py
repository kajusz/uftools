#!/usr/bin/env python3

import logging
log = logging.getLogger(__name__)

import email
import re
import os

# returns a tuple with the link, and trailer title OR a none tuple
def findTrailerLink(message):
    msg = email.message_from_bytes(message)

    subject = re.search('Delivery via DigiLink: (.*)$', msg['Subject'])
    if subject == None:
        log.warn('Message subject "%s" is not valid.', msg['Subject'])

    subject = str(subject.group(1)) # get trailer title

    if msg.is_multipart():
        for part in msg.get_payload():
            message = part.get_payload(decode=True)
            if part.get_content_type() == 'text/html': # want the html message with <a href=...
                link = re.search(r".*Click to download the trailer via Aspera: <br \/><a href=.?'(https.*)\\'>.*", str(message), re.MULTILINE)
                if link == None:
                    log.warn('Could not find a link in "%s".', subject)
                    continue
                link = link.group(1)

                return (link, subject) # add to the downloader

        # We should not be in this function any more if we have successfully found the link
        log.error('Failed to find a link in message "%s".', subject)
        return (None, None)
    else:
        # All messages from MPS appear to be multipart plain + html and html is easier to dodgily parse
        log.critical('WOW, a non multipart mesasge, someone needs to fix this!!!')
        return (None, None)

# returns array of downloaded files
def findAndDownloadKeys(message, downloadDir='/tmp/'):
    ret = []

    msg = email.message_from_bytes(message)
    subject = msg['Subject']
    log.debug('Looking at "%s"', subject)

    for part in msg.walk():
        if part.get_content_maintype() == 'multipart':
            continue
        if part.get('Content-Disposition') is None:
            continue

        filename = part.get_filename()
        log.debug('---> found "%s"', filename)
        dlPath = os.path.join(downloadDir, filename)

        if not os.path.isfile(dlPath) :
            fp = open(dlPath, 'wb')
            ret.append(dlPath)
            fp.write(part.get_payload(decode=True))
            fp.close()
            log.debug('Downloaded "%s"', filename)
        else:
            raise IOError('File %s exists' % (dlPath))

    return ret
