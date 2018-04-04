#!/usr/bin/env python3

import logging
log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# Email parser dependency
import sys
import imaplib
import email

# Aspera trailers dependencies
import re
import pickle
import kUtils.mailSearch
import kUtils.aspera
import time

# Keys ingester dependencies
import os
import zipfile

keysCache = '/home/ufadmin/keys/cache'

# Uploader dependencies
import ziplib

# Email details
from credentials import emailConfig

##########
# Setup mailbox object
mailbox = imaplib.IMAP4_SSL(emailConfig['server'], port=emailConfig['port'])
try:
    rv, data = mailbox.login_cram_md5(emailConfig['username'], emailConfig['password'])
    log.debug('result = %s, data = %s', rv, data)
    assert(rv == 'OK' and data == [b'AUTHENTICATE Completed'])
except imaplib.IMAP4.error:
    print ("LOGIN FAILED!!! ")
    sys.exit(1)

##########
# Check for new trailers
msgDb = {}
msgDb = pickle.load(open("trailers.pickle","rb"))
trailersToDownload = []

rv, data = mailbox.select('Trailers')
log.debug('result = %s, data = %s', rv, data)
assert(rv == 'OK')

rv, data = mailbox.search(None, 'SUBJECT "Delivery via DigiLink"')
log.debug('result = %s, data = %s', rv, data)
assert(rv == 'OK')

messages = data[0].split()
for num in messages:
    rv, rawMsg = mailbox.fetch(num, '(RFC822)')
    log.debug('result = %s, data = %s', rv, rawMsg)
    assert(rv == 'OK')

    link, title = mailSearch.findTrailerLink(rawMsg[0][1])

    key = re.search('.*\?id\=(.*)$', link)
    if key == None:
        log.warn('Could not extract aspera id from "%s" with link "%s".', title, link)
        continue
    key = key.group(1)

    if key in msgDb:
        assert(msgDb[key] == title) #if this fails something's really wrong as the key is meant to be unique
        log.debug('Error: "%s" already exists with key=%s', title, key) # not really an error, we want this
    else:
        log.warn('Found new trailer of "%s" with key=%s', title, key)
        msgDb[key] = title # mark this as done, will not be downloaded again
        log.debug('Adding %s to download queue with link %s', link, title)
        trailersToDownload.append(link) # add to the downloader

log.debug(trailersToDownload) # print things to download

if not trailersToDownload:
    print('No new trailers found...')# sadface
else:
    log.info('New trailers found, adding into Aspera...')
    for link in trailersToDownload:
        result = aspera.addDownload(link)

        if not result:
           print('Failed to add the link to aspera.')
           sys.exit(1)

        time.sleep(1)

pickleDb = open("trailers.pickle","wb")
pickle.dump(msgDb, pickleDb)
pickleDb.close()

# TODO
# ingest the trailers via ftp onto the server

##########
# Check for new keys
rv, data = mailbox.select('Keys')
log.debug('result = %s, data = %s', rv, data)
assert(rv == 'OK')

rv, data = mailbox.search(None, 'SUBJECT "Midwife"')
log.debug('result = %s, data = %s', rv, data)
assert(rv == 'OK')

messages = data[0].split()
for num in messages:
    newKeys = []

    rv, rawMsg = mailbox.fetch(num, '(RFC822)')
    log.debug('result = %s, data = %s', rv, rawMsg)
    assert(rv == 'OK')

    result = mailSearch.findAndDownloadKeys(rawMsg[0][1], keysCache)

    for file in result:
        _, ext = os.path.splitext(file)
        if ext == 'zip':
            zip_ref = zipfile.ZipFile(file, 'r')
            zip_ref.extractall(keysCache)
            for i in zip_ref.namelist():
                newKeys.append(i)
            zip_ref.close()

import xml.etree.ElementTree as ET
for key in newKeys:
    tree = ET.parse(key)
    treeroot = tree.getroot()
    assert(treeroot.tag == 'DCinemaSecurityMessage')
    ## TODO
    ## find <X509SubjectName>dnQualifier=0CZKyI1XLWHJZtGO1tTG77h0Ss8=,CN=SM SPB MDI MDA MDS FMI FMA.Dolby-CAT745-00001BC6,O=DC256.Cinea.Com,OU=DolbyMediaBlock</X509SubjectName>
    ## and compare to 'openssl x509 -in cert_Dolby-CAT745-H0007110.pem.crt -noout -subject'
    ## which gives '''subject=OU = DolbyMediaBlock, O = DC256.Cinea.Com, CN = SM SPB MDI MDA MDS FMI FMA.Dolby-CAT745-00001BC6, dnQualifier = 0CZKyI1XLWHJZtGO1tTG77h0Ss8='''
    ## check if it expires in the future

# TODO
# ingest the key via ftp onto the server

##########
mailbox.close()
mailbox.logout()
