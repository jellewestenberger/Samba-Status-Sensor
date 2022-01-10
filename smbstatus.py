#! /usr/bin/env python3
import sys
import os 
import paho.mqtt.client as mqtt
import datetime
import time
import sshcredentials
import logging
import logging.handlers
import json
logging.basicConfig(filename="/var/log/sambareport",level=logging.DEBUG, format='%(asctime)s %(levelname)s: %(message)s')
logging.info("checking samba status")

def error_handler(type, value, tb):
    logging.exception("Uncaught Exception: {0}".format(str(value)))
sys.excepthook = error_handler


# --------Parse smbstatus--------------
response = os.popen('ssh -i /home/pi/.ssh/id_rsa %s@%s "/usr/local/samba/bin/smbstatus"'%(sshcredentials.sshUser,sshcredentials.sshHost)).read()

lines = response.split('-----\n')
a = lines[0].split('------\n')
identityheader = a[0].split('\n')[2].split(" ")

# clean up header
i=0
while i<len(identityheader):
    if identityheader[i]=="":
        del identityheader[i]
    else:
        i+=1


identities=lines[1].split('Service\t')[0].split('\n')
# clean up identities list
i=0
while i<len(identities):
    if identities[i]=='':
        del identities[i]
    else:
        i+=1
iden = {}
for line in identities:
    line= line.split(")")[0]+")"
    st={}
    # clean up line
    dat = line.split(" ")
    i=0
    while i < len(dat):
        if dat[i]=="":
            del dat[i]
        else:
            i+=1
    if len(dat)>4:
        dat[3]=dat[3]+dat[4]
    st['PID'] = dat[0]
    st['Username'] = dat[1]
    st['Group'] = dat[2]
    st['Machine'] = dat[3]
    iden[dat[0]]=st

files = lines[-1].split('\n')
#clean up files
i=0
while i<len(files):
    if files[i]=='':
        del files[i]
    else:
        i+=1

filestruct={}
for id in iden:
    st={}
    st['filelist']=[]
    st['timelist']=[]
    filestruct[id]=st


for f in files:
    l= f.split('   ')
    i=0
    while i < len(l):
        if l[i]=='':
            del l[i]
        else:
            i+=1
    
    pid = l[0]
    uid= l[1]
    oplock = l[3]
    path = l[5]
    fname = l[6]
    for q in range(len(l)):
        if ':' in l[q]: # find time
            break
    
    timest = time.mktime(datetime.datetime.strptime(l[q].replace("  "," "),"%a %b %d %H:%M:%S %Y").timetuple())
    if not fname in filestruct[pid]['filelist']:
        filestruct[pid]['filelist'].append(fname)
        filestruct[pid]['timelist'].append(int(timest))   

for id in filestruct:
    # filestruct[id]['identity']=iden[id] 
    for k in iden[id]:
        filestruct[id][k]=iden[id][k]
    filestruct[id]['nr_files']=len(filestruct[id]['filelist'])

#---------MQTT----------------------
mqttclient = mqtt.Client()
mqttclient.username_pw_set(username=sshcredentials.mqttuser,password=sshcredentials.mqttpass)
# Topics
discoveryTopicPrefix = 'homeassistant/sensor/samba/'
topicPrefix = 'home/nodes/samba/'

def on_mqtt_connect(mqttclient,obj, flags, rc):
    logging.debug("Connected to MQTT server")

def on_mqtt_disconnect(mqttclienct,userdata,rc):
    logging.debug("Disconnected from MQTT server")     

def on_mqtt_message(mqttclient,obj,msg):
    top = msg.topic.split(discoveryTopicPrefix)
    if len(top)>1:
        name = top[1].split("/config")[0]
        if msg.payload != b'{}':
            delet=False
            if name in filestruct:
                if filestruct[name]['nr_files']==0:
                    delet = False # set to False if you want to keep history in HA
            elif (not name in filestruct)  : #delete config if session id does not exist anymore:
                delet = True
            if delet:
                logging.warning("%s does not exist anymore. Deleting from home assistant.."%name)
                mqttclient.publish(msg.topic,"{}",retain=True)
        
mqttclient.on_connect = on_mqtt_connect
mqttclient.on_disconnect = on_mqtt_disconnect
mqttclient.on_message = on_mqtt_message

def publishDiscovery(session): #publish config payload for MQTT Discovery in HA
    sessionID = session['PID']
    discoveryTopic=discoveryTopicPrefix +"%s/config" % sessionID
    payload={}
    payload['name']='Samba Session '+ sessionID
    payload['uniq_id'] = 'SambaSession_%s'%sessionID
    payload['state_topic'] = "%s%s/state"%(topicPrefix,sessionID)
    payload['unit_of_meas'] = 'files'
    payload['icon'] = 'mdi:file-multiple'
    payload['json_attributes_topic'] = "%s%s/attr"%(topicPrefix,sessionID)
    # payload['dev'] = {
    #             'identifiers' : ['vpnClient{}'.format(session['Name'])],
    #             'manufacturer' : 'WireGuard',
    #             'name' : 'VPN-Client-{}'.format(session['Name']),
    #             'model' : 'VPN Client',
    #             'sw_version': "not applicable"            
    #         }
    logging.debug("Publishing Config for %s"%sessionID)
    mqttclient.publish(discoveryTopic,json.dumps(payload),0,retain=True)

def publishState(session):
    sessionID = session['PID']
    stateTopic = "%s%s/state"%(topicPrefix,sessionID)
    attrTopic ="%s%s/attr"%(topicPrefix,sessionID)
    state = str(session['nr_files'])
    attributes = {}
    attributes['files']=session['filelist']
    attributes['PID'] = session['PID']
    attributes['username'] = session['Username']
    attributes['group'] = session['Group']
    attributes['machine'] = session['Machine']
    attributes=json.dumps(attributes)
    mqttclient.publish(stateTopic,state)
    mqttclient.publish(attrTopic,attributes)
    logging.debug("published state and attributes")
    d=2

mqttclient.connect(sshcredentials.mqtthost,sshcredentials.mqttport)
mqttclient.subscribe(discoveryTopicPrefix+"#")
for id in filestruct:
    session = filestruct[id]
    if session['nr_files'] > 0:
        publishDiscovery(session)
        publishState(session)
mqttclient.loop_start()
t0 = time.time()
while True:
    if time.time() - t0 > 5:
        break

mqttclient.loop_stop()
mqttclient.disconnect()
logging.info("finished")