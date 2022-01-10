#! /usr/bin/env python3

import os 
import paho.mqtt.client as mqtt
import datetime
import time
import sshcredentials

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


for f in  files:
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
    timest = time.mktime(datetime.datetime.strptime(l[7].replace("  "," "),"%a %b %d %H:%M:%S %Y").timetuple())
    filestruct[pid]['filelist'].append(fname)
    filestruct[pid]['timelist'].append(int(timest))    
