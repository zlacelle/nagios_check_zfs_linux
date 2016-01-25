#!/usr/bin/python

########################################################################
## 
## Written by Zachary LaCelle
## Copyright 2016
## Licensed under GPL (see below) 
##
## Nagios script to monitor ZFS pools/filesystems
## in Linux.
##
## Tested operating systems/ZFS versions:
##  * Ubuntu 14.04.3 LTS, ZFS v5
##
## This program is free software: you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published by
## the Free Software Foundation, either version 3 of the License, or
## (at your option) any later version.
##
## This program is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with this program.  If not, see <http://www.gnu.org/licenses/>.
##
########################################################################

from sys import exit
import subprocess
import argparse
from array import *
from types import *

##
# Commands to run
# CHANGE THESE IF YOU NEED TO
##
zpoolCommand='/sbin/zpool'
zfsCommand='/sbin/zfs'

##
# Variables to print at the end
##
nagiosStatus=('OK','WARNING','CRITICAL','UNKNOWN')
stateNum=0
msg=''
perfdata=''

##
# Filled from command line arguments
##
checkCapacity=False
capWarnThreshold=50
capCritThreshold=80
checkFragmentation=False
fragWarnThreshold=50
fragCritThreshold=80

def CheckArgBounds( valueArr, minVal, maxVal ):
    for value in valueArr:
        if value < minVal:
            return False
        elif value > maxVal:
            return False
    return True

def ConvertToGB( valueStr ):
    value = valueStr[:-1]
    if valueStr.endswith('G'):
        return float(value)
    elif valueStr.endswith('T'):
        gigs=float(value)*1024
        return float(gigs)
    elif valueStr.endswith('M'):
        gigs=float(value) / 1024.0
        return float(gigs)
    elif valueStr.endswith('K'):
        gigs=float(value) / (1024.0 * 1024.0)
        return float(gigs)

def RaiseStateNum( stateNumIn, stateNum ):
    if stateNumIn > stateNum:
        return stateNumIn

###################################################################################
##
# Parse command line args
##
parser = argparse.ArgumentParser(
    prog='check_zfs',
    description='Check the ZFS pool specified by an argument.',
    epilog='Note that monitor flags (e.g. capacity) require 2 arguments: warning threshold, and critical threshold')
parser.add_argument('--capacity', help="monitor utilization of zpool (%%, int [0-100]", type=int, nargs=2)
parser.add_argument('--fragmentation', help="monitor fragmentation of zpool (%%, int [0-100])", type=int, nargs=2)
parser.add_argument('pool', help="name of the zpool to check", type=str)

args = parser.parse_args()

retVal = True
if args.capacity is not None:
    checkCapacity=True
    capWarnThreshold=args.capacity[0]
    capCritThreshold=args.capacity[1]
    capArr = array('i', [capWarnThreshold, capCritThreshold])
    retVal = CheckArgBounds(capArr, 0, 100)
    if retVal is False:
        stateNum = RaiseStateNum(3, stateNum)
        print nagiosStatus[stateNum] + ": Capacity thresholds must be between 0 and 100 (as a percent)."
        parser.print_help()
        exit(stateNum)
retVal = True
if args.fragmentation is not None:
    checkFragmentation=True
    fragWarnThreshold=args.fragmentation[0]
    fragCritThreshold=args.fragmentation[1]
    fragArr = array('i', [fragWarnThreshold, fragCritThreshold])
    retVal = CheckArgBounds(fragArr, 0, 100)
    if retVal is False:
        stateNum = RaiseStateNum(3, stateNum)
        print nagiosStatus[stateNum] + ": Fragmentation thresholds must be between 0 and 100 (as a percent)."
        parser.print_help()
        exit(stateNum)
###################################################################################

###################################################################################
##
# Get generic info about the ZFS environment
zfsEntries = []
zfsArgs=' list'
fullCommand='sudo -n ' + zfsCommand + zfsArgs
childProcess = subprocess.Popen(fullCommand, shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
zfsString = childProcess.communicate()[0]
zfsRetval = childProcess.returncode

if zfsRetval is 1:
    stateNum = RaiseStateNum(3, stateNum)
    print nagiosStatus[stateNum] + ": process must be run as root. Possible solution: add the following to your visudo: nagios ALL=NOPASSWD: /sbin/zfs"    
    exit(stateNum)

zfsLines = zfsString.splitlines()
for idx, line in enumerate(zfsLines):
    if idx != 0:
        zfsEntry=line.split()
        zfsEntries.append(zfsEntry)

# Make sure the pool we specified is valid
validPool=False
for entry in zfsEntries:
    if entry[0] == args.pool:
        validPool=True
if not validPool:
    stateNum = RaiseStateNum(3, stateNum)
    print nagiosStatus[stateNum] + ": Pool " + args.pool + " is invalid. Please select a valid pool."
    exit(stateNum)

###################################################################################
##
# Get info on zpool

zpoolArgs=' list ' + args.pool;
fullCommand='sudo -n ' + zpoolCommand + zpoolArgs

childProcess = subprocess.Popen(fullCommand, shell=True, stdin=subprocess.PIPE, 
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
zpoolString = childProcess.communicate()[0]
zpoolRetval = childProcess.returncode

if zpoolRetval is 1:
    stateNum = RaiseStateNum(3, stateNum)
    print nagiosStatus[stateNum] + ": process must be run as root. Possible solution: add the following to your visudo: nagios ALL=NOPASSWD: /sbin/zpool"
    exit(stateNum)

zpoolLines=zpoolString.splitlines()
zpoolMeta=zpoolLines[0].split()
zpoolMetaStr=','.join(zpoolMeta)
zpoolEntry=zpoolLines[1].split()
zpoolEntryStr=','.join(zpoolEntry)

name=''
size=''
alloc=''
free=''
expandsz=''
frag=''
cap=''
dedup=''
health=''
altroot=''

for idx, fieldName in enumerate(zpoolMeta):
    if fieldName=='NAME':
        name=zpoolEntry[idx]
    elif fieldName=='SIZE':
        size=zpoolEntry[idx]
    elif fieldName=='ALLOC':
        alloc=zpoolEntry[idx]
    elif fieldName=='FREE':
        free=zpoolEntry[idx]
    elif fieldName=='EXPANDSZ':
        expandsz=zpoolEntry[idx]
    elif fieldName=='FRAG':
        frag=zpoolEntry[idx]
    elif fieldName=='CAP':
        cap=zpoolEntry[idx]
    elif fieldName=='DEDUP':
        dedup=zpoolEntry[idx]
    elif fieldName=='HEALTH':
        health=zpoolEntry[idx]
    elif fieldName=='ALTROOT':
        altroot=zpoolEntry[idx]

if name=='':
    stateNum = RaiseStateNum(3, stateNum)
    print nagiosStatus[stateNum] + ": Missing required field in zpool output: NAME"
    exit(stateNum)
if health=='':
    stateNum = RaiseStateNum(3, stateNum)
    print nagiosStatus[stateNum] + ": Missing required field in zpool output: HEALTH"
    exit(stateNum)
if checkCapacity and cap=='':
    stateNum = RaiseStateNum(3, stateNum)
    print nagiosStatus[stateNum] + ": Cannot monitor capacity without zpool output: CAP. Outputs are" + zpoolMetaStr
    exit(stateNum)
if checkFragmentation and frag=='':
    stateNum = RaiseStateNum(3, stateNum)
    print nagiosStatus[stateNum] + ": Cannot monitor fragmentation without zpool output: FRAG. Outputs are " + zpoolMetaStr
    exit(stateNum)

###################################################################################
##
# OK, finally in the actual status checking of the zpool

# Let's build up our perfdata, regardless of what we're checking
fragPercent=''
if frag!='':
    fragPercent=frag.replace("%", "")
    fragPerfStr="frag="+str(fragPercent)+"%;"
    if checkFragmentation:
        fragPerfStr=fragPerfStr+str(fragWarnThreshold)+";"+str(fragCritThreshold)+";"
    else:
        fragPerfStr+=(";;");
    perfdata+=(fragPerfStr)
    perfdata+=" "

capPercent=''
if cap!='':
    capPercent=cap.replace("%", "")
    capPerfStr="cap="+str(capPercent)+"%;"
    if checkCapacity:
        capPerfStr=capPerfStr+str(capWarnThreshold)+";"+str(capCritThreshold)+";"
    else:
        capPerfStr+=(";;");
    perfdata+=(capPerfStr)
    perfdata+=" "
    
# Sizes can be in K, M, G, or T (maybe P, but I'm not doing this yet)
if size!='':
    sizeGB = ConvertToGB(size)
    perfdata+="size="+str(sizeGB)+"GB;;;"
    perfdata+=" "

if alloc!='':
    allocGB = ConvertToGB(alloc)
    perfdata+="alloc="+str(allocGB)+"GB;;;"
    perfdata+=" "

if free!='':
    freeGB = ConvertToGB(free)
    perfdata+="free="+str(freeGB)+"GB;;;"
    perfdata+=" "

##
# Do mandatory checks
healthNum=-1
if health=='ONLINE':
    healthNum=0
elif health=='OFFLINE':
    stateNum = RaiseStateNum(1, stateNum)
    healthNum=1
elif health=='REMOVED':
    stateNum = RaiseStateNum(1, stateNum)
    healthNum=2
elif health=='UNAVAIL':
    stateNum = RaiseStateNum(1, stateNum)
    healthNum=3
elif health=='DEGRADED':
    stateNum = RaiseStateNum(2, stateNum)
    healthNum=4
elif health=='FAULTED':
    stateNum = RaiseStateNum(2, stateNum)
    healthNum=5
perfdata+="health="+str(healthNum)+";1;3;"
perfdata+=" "

##
# Initial part of msg
msg="POOL: "+str(name)
healthMsgFilled=False
if healthNum > 0: 
    msg+=", STATUS: "+str(health)
    healthMsgFilled=True

##
# Do optional checks
fragMsgFilled=False
capMsgFilled=False
if checkFragmentation and fragPercent!='':
    if int(fragPercent) > int(fragCritThreshold):
        fragMsgFilled=True
        stateNum = RaiseStateNum(2, stateNum)
        msg+=", FRAG CRIT: "+str(frag)
    elif int(fragPercent) > int(fragWarnThreshold):
        fragMsgFilled=True
        stateNum = RaiseStateNum(1, stateNum)
        msg+=", FRAG WARN: "+str(frag)
if checkCapacity and capPercent!='':
    if int(capPercent) > int(capCritThreshold):
        capMsgFilled=True
        stateNum = RaiseStateNum(2, stateNum)
        msg+=", CAP CRIT: "+str(cap)
    elif int(capPercent) > int(capWarnThreshold):
        capMsgFilled=True
        stateNum = RaiseStateNum(1, stateNum)
        msg+=", CAP WARN: "+str(cap)

##
# Build up rest of message
if not healthMsgFilled:
    msg+=", STATUS: "+str(health)
if size!='':
    msg+=", SIZE: "+str(size)
if alloc!='':
    msg+=", ALLOC: "+str(alloc)
if free!='':
    msg+=", FREE: "+str(free)
if frag!='' and not fragMsgFilled:
    msg+=", FRAG: "+str(frag)
if cap!='' and not capMsgFilled:
    msg+=", CAP: "+str(cap)

##
# Print our output and return
print nagiosStatus[stateNum]+": "+msg+" | "+perfdata
exit(stateNum)
