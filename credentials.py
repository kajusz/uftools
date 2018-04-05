#!/usr/bin/env python3

if __name__ == '__main__':
    import sys
    print('NO! BAD! Don\'t run the credentials!')
    sys.exit(1)

# Define your pdus here
myPduConfig = (
    {'module':'AvocentPDU', 'ip':'192.168.0.1', 'user':'pduSnmp', 'auth':'authPriv', 'key':('1234567890abcdefghij', 'klmnopqrstuvwxyz1234'),},
)

# projection email
emailConfig = {
    'username': 'username',
    'password': 'p@$$w0rd',
    'host': 'imap.gmail.com',
    'port': 993,
}

# ftp target
dcpServerFtpDetails = {
    'username': 'username',
    'password': 'password',
    'host': '192.168.0.1',
    'port': 21,
}