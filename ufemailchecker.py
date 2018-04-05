#!/usr/bin/env python3

import logging
log = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)

import argparse

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

pickleDbDelim = ';'

# Keys ingester dependencies
import os
from hashlib import blake2b
import zipfile
import xml.etree.ElementTree as ET

keysCache = '/opt/uftools/keys/tmp'

# Uploader dependencies
import ftplib

# Email details
from credentials import emailConfig

if __name__ == '__main__':
    parser = argparse.ArgumentParser()

    parser.add_argument('-n', '--new', action='store_true', help='Only fetch new messages')
    parser.add_argument('-d', '--debug', action='store_true', help='Debugging info')
    parser.add_argument('--no-update', action='store_true', dest='noupdate', help='Don\'t update cache pickles')
    parser.add_argument('--dru-run', action='store_true', dest='dryrun', help='Don\'t call helper programs or upload to ftp')
    args = parser.parse_args()

    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

##########
# Setup mailbox object
    mailbox = imaplib.IMAP4_SSL(emailConfig['server'], port=emailConfig['port'])
    try:
        rv, data = mailbox.login_cram_md5(emailConfig['username'], emailConfig['password'])
        log.debug('action = "login", result = "%s", data = "%s"', rv, data)
        assert(rv == 'OK' and data == [b'AUTHENTICATE Completed'])
    except imaplib.IMAP4.error:
        print ('LOGIN FAILED!!!')
        sys.exit(1)

##########
# Check for new trailers
    msgDb = {}
    msgDb = pickle.load(open('trailers.pickle','rb'))
    trailersToDownload = []

    rv, data = mailbox.select('Trailers')
    if not (rv == 'OK'):
        log.error('action = "select", result = "%s", data = "%s"', rv, data)

    rv, data = None, None
    if args.new:
        rv, data = mailbox.search(None, '(UNSEEN)')
    else:
        rv, data = mailbox.search(None, 'SUBJECT "Delivery via DigiLink"')
    if not (rv == 'OK'):
        log.error('action = "search", result = "%s", data = "%s"', rv, data)

    messages = data[0].split()
    for num in messages:
        rv, rawMsg = mailbox.fetch(num, '(RFC822)')
        if not (rv == 'OK'):
            log.error('action = "fetch", result = "%s", data = "%s"', rv, rawMsg)

        link, title = kUtils.mailSearch.findTrailerLink(rawMsg[0][1])
        if link == None:
            continue

        key = re.search('.*\?id\=(.*)$', link)
        if key == None:
            log.warn('Could not extract aspera id from "%s" with link "%s".', title, link)
            continue
        key = key.group(1)

        if key in msgDb:
            assert(msgDb[key] == title) #if this fails something's really wrong as the key is meant to be unique
            log.debug('Error: "%s" already exists with key="%s"', title, key) # not really an error, we want this
        else:
            log.warn('Found new trailer of "%s" with key="%s"', title, key)

            log.debug('Adding "%s" to download queue with link "%s"', link, title)
            trailersToDownload.append((link, key, title)) # add to the downloader

    if not trailersToDownload:
        print('No new trailers found...')# sadface
    else:
        log.info('New trailers found, adding into Aspera...')
        log.debug(trailersToDownload) # print things to download

        for link, key, title in trailersToDownload:
            result = False
            if not args.dryrun:
                result = kUtils.aspera.addDownload(link)
            else:
                result = True

            if not result:
                print('Failed to add the link to aspera.')
            else:
                msgDb[key] = title # mark this as done, will not be downloaded again

            time.sleep(1)

    if not args.noupdate:
        pickleDb = open('trailers.pickle','wb')
        pickle.dump(msgDb, pickleDb)
        pickleDb.close()

# TODO
# ingest the trailers via ftp onto the server

##########
# Check for new keys
    keysDb = {}
    keysDb = pickle.load(open('keys.pickle','rb'))
    newKeys = []

    rv, data = mailbox.select('Keys')
    if not (rv == 'OK'):
        log.error('action = "select", result = "%s", data = "%s"', rv, data)

    rv, data = None, None
    if args.new:
        rv, data = mailbox.search(None, '(UNSEEN)')
    else:
        rv, data = mailbox.search(None, 'ALL')
    if not (rv == 'OK'):
        log.error('action = "search", result = "%s", data = %s', rv, data)

    messages = data[0].split()
    for num in messages:
        rv, rawMsg = mailbox.fetch(num, '(RFC822)')
        if not (rv == 'OK'):
            log.error('action = "fetch", result = "%s", data = "%s"', rv, rawMsg)

        msg = email.message_from_bytes(rawMsg[0][1])
        subject = msg['Subject']
        log.debug('have "%s"', subject)

        h = blake2b(key=b'UnionFilms', digest_size=16)
        h.update(bytes(subject, 'utf-8'))
        key = h.hexdigest()

        if key in keysDb:
            log.debug('Error: "%s" already exists with key="%s"', subject, key) # not really an error, we want this
            continue

        keysDb[key] = ''

        result = kUtils.mailSearch.findAndDownloadKeys(rawMsg[0][1], keysCache)
        print(result)
        for kfile in result:
            _, ext = os.path.splitext(kfile)
            if ext == '.zip':
                log.debug('We have a zip "%s"', kfile)
                zip_ref = zipfile.ZipFile(kfile, 'r')
                zip_ref.extractall(keysCache)
                for i in zip_ref.namelist():
                    keysDb[key] = keysDb[key] + i + pickleDbDelim
                    newKeys.append(i)
                zip_ref.close()

    if not newKeys:
        print('No new keys found...')# sadface
    else:
        log.info('New keys found, validating...')
        log.debug(newKeys)

        for kdm in newKeys:
            tree = ET.parse(os.path.join(keysCache, kdm))
            treeroot = tree.getroot()
            if not (treeroot.tag == '{http://www.smpte-ra.org/schemas/430-3/2006/ETM}DCinemaSecurityMessage'):
                log.warning('invalid xml file %s', kdm)
            ## TODO
            ## find <X509SubjectName>dnQualifier=0CZKyI1XLWHJZtGO1tTG77h0Ss8=,CN=SM SPB MDI MDA MDS FMI FMA.Dolby-CAT745-00001BC6,O=DC256.Cinea.Com,OU=DolbyMediaBlock</X509SubjectName>
            ## and compare to 'openssl x509 -in cert_Dolby-CAT745-H0007110.pem.crt -noout -subject'
            ## which gives '''subject=OU = DolbyMediaBlock, O = DC256.Cinea.Com, CN = SM SPB MDI MDA MDS FMI FMA.Dolby-CAT745-00001BC6, dnQualifier = 0CZKyI1XLWHJZtGO1tTG77h0Ss8='''
            ## check if it expires in the future

    if not args.noupdate:
        pickleDb = open('keys.pickle','wb')
        pickle.dump(keysDb, pickleDb)
        pickleDb.close()

# TODO
# ingest the key via ftp onto the server

##########
    log.info('Closing mailbox...')
    mailbox.close()
    mailbox.logout()
