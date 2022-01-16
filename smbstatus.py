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
logging.basicConfig(filename="/var/log/sambareport",level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s')
logging.info("checking samba status")

def error_handler(type, value, tb):
    logging.exception("Uncaught Exception: {0}".format(str(value)))
sys.excepthook = error_handler


# --------Parse smbstatus--------------
logging.info("parsing smbstatus")
response = os.popen('ssh -i /home/pi/.ssh/id_rsa %s@%s "/usr/local/samba/bin/smbstatus"'%(sshcredentials.sshUser,sshcredentials.sshHost)).read()
logging.debug(response)
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
    st['Machine'] = dat[3].replace(" ","")
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
    filestruct[iden[id]['Machine']]=st

if files[0]=='No locked files':
    files =[]
    
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
    mach = iden[pid]['Machine']
    if not fname in filestruct[mach]['filelist']:
        filestruct[mach]['filelist'].append(fname)
        filestruct[mach]['timelist'].append(int(timest))   

for mach in filestruct:
    # filestruct[id]['identity']=iden[id] 
    for id in iden:
        if iden[id]['Machine'].replace(" ","") == mach:
            for k in iden[id]:
                if k in filestruct[mach]:
                    if not iden[id][k] in filestruct[mach][k]:
                        filestruct[mach][k].append(iden[id][k])
                else:
                    filestruct[mach][k]=[iden[id][k]]        

    filestruct[mach]['nr_files']=len(filestruct[mach]['filelist'])
    filestruct[mach]['nr_sessions']=len(filestruct[mach]['PID'])

    # remove keys with empty lists and convert lists of size 1 to its content
    skip=['nr_files','nr_sessions'] # skip keys that do not contain lists
    j=0
    while j < len(filestruct[mach]):
        key = list(filestruct[mach].keys())[j]
        if key in skip:
            j+=1
            continue
        if len(filestruct[mach][key])==0:
            del filestruct[mach][key]
        elif len(filestruct[mach][key])==1:
            filestruct[mach][key]=filestruct[mach][key][0]
            j+=1
        else:
            j+=1
#---------MQTT----------------------
mqttclient = mqtt.Client()
mqttclient.username_pw_set(username=sshcredentials.mqttuser,password=sshcredentials.mqttpass)
# Topics
discoveryTopicPrefix = 'homeassistant/sensor/samba/'
topicPrefix = 'home/nodes/samba/'

def on_mqtt_connect(mqttclient,obj, flags, rc):
    logging.info("Connected to MQTT server")

def on_mqtt_disconnect(mqttclienct,userdata,rc):
    logging.info("Disconnected from MQTT server")     

def on_mqtt_message(mqttclient,obj,msg):
    top = msg.topic.split(discoveryTopicPrefix)
    logging.debug("Received message on topic: %s \n payload: %s"%(msg.topic,msg.payload))
    if len(top)>1:
        name = top[1].replace("client_","").replace("/config","")
        if msg.payload != b'{}':
            delet=True
            for name2 in filestruct:
                if name2.replace(".","_").replace("(","").replace(")","") == name:
                    delet=False
                    break
            if delet:
                logging.warning("Deleting machine %s from home assistant.."%name)
                mqttclient.publish(msg.topic,"{}",retain=True)
        
mqttclient.on_connect = on_mqtt_connect
mqttclient.on_disconnect = on_mqtt_disconnect
mqttclient.on_message = on_mqtt_message

def publishDiscovery(session): #publish config payload for MQTT Discovery in HA
    machine = session['Machine']
    discoveryTopic=discoveryTopicPrefix +"client_%s/config" % machine.replace(".","_").replace("(","").replace(")","")
    payload={}
    payload['name']='Samba Session '+ machine
    payload['object_id'] = 'samba_'+machine
    payload['uniq_id'] = 'samba_'+machine
    payload['state_topic'] = "%s%s/state"%(topicPrefix,machine)
    payload['unit_of_meas'] = 'files'
    payload['icon'] = 'mdi:file-multiple'
    payload['json_attributes_topic'] = "%s%s/attr"%(topicPrefix,machine)
    logging.debug("Publishing Config for %s"%machine)
    mqttclient.publish(discoveryTopic,json.dumps(payload),0,retain=True)

def publishState(session):
    machine = session['Machine']
    stateTopic = "%s%s/state"%(topicPrefix,machine)
    attrTopic ="%s%s/attr"%(topicPrefix,machine)
    state = str(session['nr_files'])
    attributes = session
    del attributes['nr_files']
    attributes=json.dumps(attributes)
    mqttclient.publish(stateTopic,state)
    mqttclient.publish(attrTopic,attributes)
    logging.debug("published state and attributes")
    d=2

mqttclient.connect(sshcredentials.mqtthost,sshcredentials.mqttport)
mqttclient.subscribe(discoveryTopicPrefix+"#")
for mach in filestruct:
    session = filestruct[mach]
    logging.info("publishing session %s"%mach)
    publishDiscovery(session)
    publishState(session)
mqttclient.loop_start()
t0 = time.time()

# Loop for a short time to be able to receive older retained configs for potential deletion
while True:
    if time.time() - t0 > 5:
        break

mqttclient.loop_stop()
mqttclient.disconnect()
logging.info("finished")