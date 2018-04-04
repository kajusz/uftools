#!/usr/bin/env python3

from flask import Flask, request, redirect, url_for
app = Flask(__name__)

import logging
log = logging.getLogger(__name__)

logging.basicConfig(level=logging.INFO)

ch = logging.FileHandler('/var/log/ufPdu.log', mode='w')
ch.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s:%(name)s:%(levelname)s:%(message)s')
ch.setFormatter(formatter)
log.addHandler(ch)

from credentials import myPduConfig

import importlib

pdus = []
for pduDetails in myPduConfig:
    module = importlib.import_module('pdu.' + pduDetails['module'])
    pdu = getattr(module, pduDetails['module'])
    pdus.append(pdu(pduDetails['ip'], user=pduDetails['user'], auth=pduDetails['auth'], key=pduDetails['key']))

## START UF MODS
@app.route('/')
def index():
    return redirect(url_for('simple'))

@app.route('/simple')
def simple():
    buf = '<DOCTYPE html><html><head><title>Simple Power Management</title></head><body><h1>Welcome to the Union Films Projection Booth!</h1><p>Lets turn things on and off!</p><ul>'
    for i in range(0, len(pdus)):
        name = pdus[i].getName()
        if name == 'SoundRack':
            #buf += '<li>%s, <a href="/pdu%d/set/all/on">all on</a> or <a href="/pdu%d/set/all/off">all off</a></li>' % (name, i, i)
            def getRangeStatus(start, end):
                overallStatus = 0
                for outletId in range(start, end+1):
                    if pdus[i].getStatus(outletId) == 'on':
                        overallStatus += 1

                if overallStatus == (end - start + 1):
                    return 'on'
                elif overallStatus == 0:
                    return 'off'
                else:
                    return 'mixed'

            def printRangeHtml(label, start, end):
                rangeStatus = getRangeStatus(start, end)
                if rangeStatus == 'mixed':
                    return '<li>%s, <a href="/pdu%d/set/range/%d/%d/on">all on</a> or <a href="/pdu%d/set/range/%d/%d/off">all off</a></li>' % (label, i, start, end, i, start, end)
                else:
                    invstatus = pdus[i].invert(rangeStatus)
                    return '<li>%s, <a href="/pdu%d/set/range/%d/%d/%s">power %s</a></li>' % (label, i, start, end, invstatus, invstatus)

            buf += printRangeHtml('audio-processing', 2, 4)
            buf += printRangeHtml('amplifiers', 5, 9)

        elif name == 'MainRack1':
            listOfThings = [1, 10] # 1=Proj, 10=Monitor
            for outlet in listOfThings:
                label, status = pdus[i].getLS(outlet)
                invstatus = pdus[i].invert(status)
                buf += '<li>%s, <a href="/pdu%d/set/%d/%s">power %s</a></li>' % (label, i, outlet, invstatus, invstatus)

#        elif name == 'MainRack2':
#            listOfThings = [6] # 6=Freesat
#            for outlet in listOfThings:
#                label, status = pdus[i].getLS(outlet)
#                invstatus = pdus[i].invert(status)
#                buf += '<li>%s, <a href="/pdu%d/set/%d/%s">power %s</a></li>' % (label, i, outlet, invstatus, invstatus)

    buf += '</ul><p><a href="/advanced">I can be trusted, give me all the power!</a></p></body></html>'

    return buf

@app.route('/advanced')
def mainPage():
    buf = '<DOCTYPE html><html><head><title>Advanced Power Management</title><style type="text/css"> span.on, span.off {font-weight:bold;} .on {color:green;} .off {color:red;}</style></head><body><h1>Union Films Projection Booth Power Management!</h1><p>Lets turn things on and off!</p><p><a href="/simple">This is too complex, take me to the simple interface!</a></p><ul>'
    #buf = '<DOCTYPE html><html><head><title>Advanced Power Distribution Management</title><style type="text/css"> span.on, span.off {font-weight:bold;} .on {color:green;} .off {color:red;}</style></head><body><h1>Advanced Power Distribution Management</h1><p>Lets turn things on and off!</p><ul>'
### END UF MODS
    for i in range(0, len(pdus)):
        ncvp  = pdus[i].getNCVP()
        buf2 = '<div><p>name = %s | current = %.1fA | voltage = %dV | power = %.1fW | <a href="/pdu%d/set/all/on">all <span class="on">on</span></a> | <a href="/pdu%d/set/all/off">all <span class="off">off</span></a></p><ol>' % (*ncvp, i, i)

        olsc = pdus[i].getOLSC()
        for outlet, label, status, current in olsc:
            if pdus[i].currentPerOutlet and status == 'on':
                buf2 += '<li>%s is <span class="on">on</span> drawing %.1fA, <a href="/pdu%d/set/%d/off">power off</a></li>' % (label, current, i, outlet)
            else:
                invStatus = pdus[i].invert(status)
                buf2 += '<li>%s is <span class="%s">%s</span>, <a href="/pdu%d/set/%d/%s">power %s</a></li>' % (label, status, status, i, outlet, invStatus, invStatus)

        buf += buf2 + '</ol></div>'

    buf += '</ul></body></html>'
    return buf

@app.route('/pdu<int:pduId>/save')
def handlePduSave(pduId):
    pdus[pduId].save()
    return redirect(request.referrer)

@app.route('/pdu<int:pduId>/label/<int:outlet>/<string:label>')
def handlePduSetLabel(pduId, outlet, label):
    pdus[pduId].setLabel(outlet, label)
    return redirect(request.referrer)

@app.route('/pdu<int:pduId>/set/<int:outlet>/<string:status>')
def handlePduSetStatus(pduId, outlet, status):
    pdus[pduId].setStatus(outlet, status)
    return redirect(request.referrer)

@app.route('/pdu<int:pduId>/set/all/<string:status>')
def handlePduSetStatusAll(pduId, status):
    pdus[pduId].setStatusAll(status)
    return redirect(request.referrer)

@app.route('/pdu<int:pduId>/set/range/<int:start>/<int:end>/<string:status>')
def handlePduSetStatusRange(pduId, start, end, status):
    assert(start < end)
    for outlet in range(start, end+1):
        pdus[pduId].setStatus(outlet, status)
    return redirect(request.referrer)

if __name__ == '__main__':
    app.run()
