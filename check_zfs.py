#!/usr/bin/python3

########################################################################
##
## Written by Zachary LaCelle
## Copyright 2016-2020
## Licensed under GPL (see below)
##
## Nagios script to monitor ZFS pools/filesystems
## in Linux.
##
## Tested operating systems/ZFS versions:
##  * See README.md
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
from sys import version
import subprocess
import argparse
import logging
import sys
from array import *
from types import *
from os import geteuid
import os


# This check only works in a subset of the actual times we need it, but it is a good effort regardless.
def pythonVersionCheck():
    # Python 3.5 is current released version on Ubuntu 16.04, the oldest version supported. LTS remains supported through 2021.
    MinimumPython_MajorVersionNumber = 3
    MinimumPython_MinorVersion = 5

    majorMinor = sys.version_info[:2]
    major = majorMinor[0]
    minor = majorMinor[1]
    if ((major < MinimumPython_MajorVersionNumber) or (major == MinimumPython_MajorVersionNumber and minor < MinimumPython_MinorVersion)):
        # Note -- We WANT This string syntax, as callers may not have newer ones if running older versions of Python!
        exit("Error, script needs needs Python %s.%s or later. Detected Python version %s.%s." % (MinimumPython_MajorVersionNumber, MinimumPython_MinorVersion, major, minor))

## Check for reasonably modern version of Python.
## We do this as soon as we can in the code / run so we can be sure of seeing it.
pythonVersionCheck();

##
# Commands to run
# CHANGE THESE IF YOU NEED TO
##
sudoCommand='/usr/bin/sudo'
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
useSudoToRunZfsCommands=True

logging.basicConfig(stream=sys.stdout, format='%(message)s', level=logging.WARNING);

def CheckArgBounds( valueArr, minVal, maxVal ):
    for value in valueArr:
        if value < minVal:
            return False
        elif value > maxVal:
            return False
    return True

def ConvertToGB( valueStr ):
    value = valueStr[:-1]
    value = value.replace(',', '.')
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
    return stateNum

def CheckIfFileExists(parser, commandToCheck):
    commandExists = os.path.isfile(commandToCheck)
    if (not commandExists):
        global stateNum
        stateNum = RaiseStateNum(3, stateNum)
        logging.warning("%s : can't find command %s.", nagiosStatus[stateNum], commandToCheck)
        exit(stateNum)

def CheckForExistenceOfCommands(parser):
    CheckIfFileExists(parser, sudoCommand)
    CheckIfFileExists(parser, zpoolCommand)
    CheckIfFileExists(parser, zfsCommand)

def LogWarningRootProcessWarningAndExit(contextString, stateNum, optionalException=None):
    # If the script is failing to run because of this line, you are likely running too old a version of Python. I wish it were possible to make the script just print this
    # clearly rather than crash, but it's not possible: https://stackoverflow.com/questions/446052/how-can-i-check-for-python-version-in-a-program-that-uses-new-language-features
    # The version check done above helps in some cases, but won't fix when this f-string language feature fails to compile.
    warningString = f'{nagiosStatus[stateNum]} : process must be run as root. Possible solution: add the following to your visudo: nagios ALL=NOPASSWD: Context: {contextString}, then run check script with --nosudo option.'
    if optionalException is not None:
        warningString = f'{warningString} Exception: {optionalException}';
    logging.warning(warningString)
    exit(stateNum)

def GetArgsForZfsCommand(zfsCommandAndArgsList):
    if (useSudoToRunZfsCommands):
        # Prepend command with "sudo -n" for noninteractive (will not ask for password, will just error if there's a problem)
        return [sudoCommand, '-n'] + zfsCommandAndArgsList;
    else:
        # Will just attempt to run the command without sudo
        return zfsCommandAndArgsList;

###################################################################################
##
# Parse command line args
##
parser = argparse.ArgumentParser(
    prog='check_zfs',
    description='Check the ZFS pool specified by an argument.',
    epilog='Note that monitor flags (e.g. capacity) require 2 arguments: warning threshold, and critical threshold')
parser.add_argument('--capacity', help="monitor utilization of zpool (%%, int [0-100])", type=int, nargs=2)
parser.add_argument('--fragmentation', help="monitor fragmentation of zpool (%%, int [0-100])", type=int, nargs=2)
parser.add_argument('--nosudo', required=False, action='store_true', help="do not attempt to sudo first when running zfs commands, instead just run them. The nagios user will need permissions to run these commands if used, so edit the sudoers file - see visudo to do this.")
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
        logging.warning("%s : Capacity thresholds must be between 0 and 100 (as a percent).", nagiosStatus[stateNum])
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
        logging.warning("%s  : Fragmentation thresholds must be between 0 and 100 (as a percent).", nagiosStatus[stateNum])
        parser.print_help()
        exit(stateNum)
useSudoToRunZfsCommands = not args.nosudo

## Make sure the commands we need are available to be later run
CheckForExistenceOfCommands(parser);

###################################################################################
###################################################################################
##
# Verify that we're running as root.  This should render redundant some checks
# below, but we'll leave them there in case of bugs and to make this more readable.
#if geteuid() != 0:
#    stateNum = RaiseStateNum(3, stateNum)
#    print nagiosStatus[stateNum] + ": process must be run as root.  Did you for get sudo?  If not, possible solution: add the following toyour visudo: nagios ALL=NOPASSWD: /sbin/zfs"
#    exit(stateNum)

###################################################################################
##
# Get generic info about the ZFS environment
zfsEntries = []
fullCommand = GetArgsForZfsCommand([zfsCommand, 'list'])
try:
    childProcess = subprocess.Popen(fullCommand, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
except OSError as osException:
    stateNum = RaiseStateNum(3, stateNum)
    LogWarningRootProcessWarningAndExit("Generic info about ZFS Environment - exception", stateNum, osException);

zfsString = childProcess.communicate()[0]
zfsRetval = childProcess.returncode

if zfsRetval == 1:
    stateNum = RaiseStateNum(3, stateNum)
    LogWarningRootProcessWarningAndExit("Generic info - child process - retval", stateNum);
    logging.warning("%s : process must be run as root. Possible solution: add the following to your visudo: nagios ALL=NOPASSWD: /sbin/zfs",  nagiosStatus[stateNum])

zfsLines = zfsString.splitlines()
for idx, line in enumerate(zfsLines):
    if idx != 0:
        zfsEntry=line.split()
        zfsEntries.append(zfsEntry)

# Make sure the pool we specified is valid
validPool=False
for entry in zfsEntries:
    if entry[0].decode() == args.pool:
        validPool=True
if not validPool:
    stateNum = RaiseStateNum(3, stateNum)
    logging.warning("%s : Pool %s is invalid. Please select a valid pool.",  nagiosStatus[stateNum], args.pool)
    exit(stateNum)

###################################################################################
##
# Get info on zpool
fullCommand = GetArgsForZfsCommand([zpoolCommand, 'list', args.pool])

try:
    childProcess = subprocess.Popen(fullCommand, stdin=subprocess.PIPE,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE)
except OSError as osException:
    stateNum = RaiseStateNum(3, stateNum)
    LogWarningRootProcessWarningAndExit("Zpool command - exception", stateNum, osException);

zpoolString = childProcess.communicate()[0]
zpoolRetval = childProcess.returncode

if zpoolRetval == 1:
    stateNum = RaiseStateNum(3, stateNum)
    commandDebugString = f"Zpool command - retval. Original command: \"{fullCommand}\"";
    LogWarningRootProcessWarningAndExit(commandDebugString, stateNum);

zpoolLines=zpoolString.splitlines()
zpoolMeta=zpoolLines[0].decode().split()
zpoolMetaStr=','.join(zpoolMeta)
zpoolEntry=zpoolLines[1].decode().split()
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
    logging.warning("%s: Missing required field in zpool output: NAME", nagiosStatus[stateNum])
    exit(stateNum)
if health=='':
    stateNum = RaiseStateNum(3, stateNum)
    logging.warning("%s : Missing required field in zpool output: HEALTH", nagiosStatus[stateNum])
    exit(stateNum)
if checkCapacity and cap=='':
    stateNum = RaiseStateNum(3, stateNum)
    logging.warning("%s Cannot monitor capacity without zpool output: CAP. Outputs are %s", nagiosStatus[stateNum], zpoolMetaStr)
    exit(stateNum)
if checkFragmentation and frag=='':
    stateNum = RaiseStateNum(3, stateNum)
    logging.warning("%s : Cannot monitor fragmentation without zpool output: FRAG. Outputs are ", nagiosStatus[stateNum], zpoolMetaStr)
    exit(stateNum)

# Get compressratio on zpool

checkForCompression = GetArgsForZfsCommand([zfsCommand, 'get', 'compression', args.pool])

try:
    childProcess = subprocess.Popen(checkForCompression, stdin=subprocess.PIPE,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE)
except OSError as osException:
    stateNum = RaiseStateNum(3, stateNum)
    LogWarningRootProcessWarningAndExit("Compression Ratio on ZPool - exception", stateNum, osException); 

zpoolString = childProcess.communicate()[0]
zpoolRetval = childProcess.returncode

if zpoolRetval == 1:
    stateNum = RaiseStateNum(3, stateNum)
    LogWarningRootProcessWarningAndExit("Compression Ratio on ZPool - Retval", stateNum); 

zpoolLines=zpoolString.splitlines()
zpoolMeta=zpoolLines[0].decode().split()
zpoolMetaStr=','.join(zpoolMeta)
zpoolEntry=zpoolLines[1].decode().split()
zpoolEntryStr=','.join(zpoolEntry)

compressName=''
compressValue=''

compressRatioName=''
compressRatioValue=''

for idx, fieldName in enumerate(zpoolMeta):
    if fieldName=='NAME':
        compressName=zpoolEntry[idx]
    elif fieldName=='VALUE':
        compressValue=zpoolEntry[idx]

if compressName=='':
    stateNum = RaiseStateNum(3, stateNum)
    logging.warning("%s: Missing required field in zpool output: NAME", nagiosStatus[stateNum])
    exit(stateNum)
if compressValue=='on':
    getCompressRatioCommand = GetArgsForZfsCommand([zfsCommand, 'get', 'compressratio', args.pool])

    try:
        childProcess = subprocess.Popen(getCompressRatioCommand, stdin=subprocess.PIPE,
                                        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except OSError as osException:
        stateNum = RaiseStateNum(3, stateNum)
        LogWarningRootProcessWarningAndExit("Get compression ratio - Exception", stateNum, osException);

    zpoolString = childProcess.communicate()[0]
    zpoolRetval = childProcess.returncode

    if zpoolRetval == 1:
        stateNum = RaiseStateNum(3, stateNum)
        LogWarningRootProcessWarningAndExit("Get compression ratio - Retval", stateNum);

    zpoolLines=zpoolString.splitlines()
    zpoolMeta=zpoolLines[0].decode().split()
    zpoolMetaStr=','.join(zpoolMeta)
    zpoolEntry=zpoolLines[1].decode().split()
    zpoolEntryStr=','.join(zpoolEntry)

    for idx, fieldName in enumerate(zpoolMeta):
        if fieldName=='NAME':
            compressRatioName=zpoolEntry[idx]
        elif fieldName=='VALUE':
            compressRatioValue=zpoolEntry[idx]

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

# Perfdata for dedup & compression factor
if dedup!='':
    dedup_no_x = dedup.rstrip('x')
    perfdata+="dedup="+str(dedup_no_x)
    perfdata+=" "

if compressRatioValue!='':
    compressRatioNoX = compressRatioValue.rstrip('x')
    perfdata+="compress_ratio="+str(compressRatioNoX)
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
    if fragPercent.isdigit() == True:
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
if dedup!='':
    msg+=", DEDUP: "+str(dedup)
if compressRatioValue!='':
    msg+=", COMPRESS: "+str(compressRatioValue)
if frag!='' and not fragMsgFilled:
    msg+=", FRAG: "+str(frag)
if cap!='' and not capMsgFilled:
    msg+=", CAP: "+str(cap)

##
# Print our output and return
logging.warning("%s: %s | %s", nagiosStatus[stateNum], msg, perfdata)
exit(stateNum)
