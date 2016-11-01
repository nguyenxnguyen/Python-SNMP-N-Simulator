#!/usr/bin/env python

import sys, exceptions, re, types, time, os, traceback
import BaseHTTPServer, thread, urllib, cgi
import socket
import random
from select import select
from snmplib import *
try:
    import inspect
    cmd_subfolder = os.path.realpath(os.path.abspath(os.path.join(os.path.split(inspect.getfile(inspect.currentframe()))[0], "csnmpsim/windows")))
    print cmd_subfolder
    if cmd_subfolder not in sys.path:
        sys.path.insert(0, cmd_subfolder)
    import csnmpsim
    CSNMPSIM_LOADED = 1
except ImportError:
    print "[C extension not found--load times may be increased]"
    CSNMPSIM_LOADED = 0

class SnmpSimError(exceptions.Exception): pass
class SnmpSimDumpError(SnmpSimError): pass
class SnmpSimUnknownRequest(SnmpSimError): pass
class MibStoreError(SnmpSimError): pass
class MibStoreInsertError(MibStoreError): pass
class MibStoreGetError(MibStoreError): pass     # For both gets and getNexts
class MibStoreNoSuchNameError(MibStoreGetError): pass
class MibStoreNotRetrievable(MibStoreGetError): pass
list_fixed_Oids = []
BELL = chr(0x07)  # ASCII code for bell/beep

# TODO: At some point I should figure out how to do this without a global. Also,
#       right now change functions are dynamically assigned--might be more elegant
#       to have them inherited (have this module subclass snmplib classes or something)
SIM_START_TIME = time.time() # Gets reset again during SnmpSim.load(), but it's global.
DELTA_APPLY_RATE = 300   # Delta is applied once every DELTA_APPLY_RATE seconds

#
# Change functions (assigned to variables dynamically)
#

def rd_snmpsim(oidsStr):
    ele_oid = oidsStr.split(", ")
    for ele in ele_oid:
        try:
            if ele not in list_fixed_Oids:
                oid_value = sim.mib.get(ele)
                if oid_value.type == 'Gauge32':
                    if oid_value.value < 100:
                        oid_value.value = 100
                    if oid_value.value < 10000:
                        delta_value = random.randrange(-oid_value.value / 2, oid_value.value / 2)
                    else:
                        delta_value = random.randrange(-100, 100)
                    new_oid_value = long(oid_value.value) + delta_value
                    if new_oid_value > 4294967000:
                        new_oid_value = 4294967295
                    if new_oid_value < 0:
                        new_oid_value = 0
                    oid_value.setValue(new_oid_value)
                if oid_value.type == 'TimeTicks':
                    delta_value = random.randrange(0, 300)
                    new_oid_value = long(oid_value.value) + delta_value
                    if new_oid_value > 4294967000:
                        new_oid_value = 4294967295
                    oid_value.setValue(new_oid_value)
                if oid_value.type == 'Counter32':
                    if oid_value.value < 100:
                        oid_value.value = 1000
                    if oid_value.value < 10000:
                        delta_value = random.randrange(0, oid_value.value / 2)
                    else:
                        delta_value = random.randrange(0, 1000)
                    new_oid_value = long(oid_value.value) + delta_value
                    if new_oid_value > 4294966000:
                        new_oid_value = 0
                    oid_value.setValue(new_oid_value)
                if oid_value.type == 'Counter64':
                    if oid_value.value < 100:
                        oid_value.value = 1000
                    if oid_value.value < 1000000:
                        delta_value = random.randrange(0, oid_value.value / 2)
                    else:
                        delta_value = random.randrange(0, 1000)
                    new_oid_value = long(oid_value.value) + delta_value
                    if new_oid_value > 9223372036854774000:
                        new_oid_value = 0
                    oid_value.setValue(new_oid_value)
        except MibStoreError, data:
            print "Set value error"


def sysUptimeChange(self):
    newVal = self.initialVal + ((time.time() - SIM_START_TIME) * 100)
    newVal = number(newVal)
    self.setValue(newVal)


def noChange(self):
    pass

def changeCounter32TimeBased(self):
    """Change counter32 values based on the time rather than every time this
       function is called (per request). This should prevent large deltas
       when multiple clients are all polling a counter with extremely large
       deltas.
    """
    max = 4294967295L
    elapsed = time.time() - SIM_START_TIME
    self.setValue((self.initialVal + int(elapsed/DELTA_APPLY_RATE)*self.delta) % (max+1))

    
def changeCounter64TimeBased(self):
    """Change counter64 values based on the time rather than every time this
       function is called (per request). This should prevent large deltas
       when multiple clients are all polling a counter with extremely large
       deltas.
    """
    max = 18446744073709551615L    
    elapsed = time.time() - SIM_START_TIME
    self.setValue((self.initialVal + int(elapsed/DELTA_APPLY_RATE)*self.delta) % (max+1))    

def changeCounter32PerReq(self):
    """Change counter32 values by delta once every time this function is called
       (once per SNMP request, basically).
    """
    max = 4294967295L
    newVal = self.value + self.delta
    # Wrap counter if necessary
    if newVal > max:
        newVal = newVal % (max + 1)
    self.setValue(newVal)


def changeCounter64PerReq(self):
    """Change counter64 values by delta once every time this function is called
       (once per SNMP request, basically).
    """    
    max = 18446744073709551615L
    newVal = self.value + self.delta
    # Wrap counter if necessary
    if newVal > max:
        newVal = newVal % (max + 1)
    self.setValue(newVal)

# This mapping controls which types (in dump) are mapped to which change functions.
CHANGE = { 'Counter': changeCounter32TimeBased,
           'Counter64': changeCounter64TimeBased }
#CHANGE = { 'Counter': changeCounter32PerReq,
#           'Counter64': changeCounter64PerReq }
#CHANGE = { 'Counter': noChange,
#           'Counter64': noChange }

class MibDataStore:
    """NEW mib data store (uses a hash for data and a list for getnexts).

       Class to store oids and associated values. Because ultimately only mib variable instances can be retreieved,
       the distinction between mib variables and their instances isn't maintained here--there is only a simple mapping
       between oids and the variables they point to. Use is straightforward--insert values using the insert method and
       retrieve them using the get or getNext methods. Logic for understanding nhSnmpTool-formatted dumps is in here too.
    """
    # Dictionary that maps a string data type to the class that should be used for that data.
    def __init__(self):
        self.variable = {}  # oid -> variable hash
        self.oids = []      # gets populated with all oids, used for inexact getnexts
        self.oidRe = re.compile(r'^\.\d\.\d+(\.\d+)*$')
        self.expRe = re.compile(r'^(\d\.\d+)e\+(\d+)$')
        self.dictType = type({})
        self.bytesPerVar = 55  # Estimated average bytes per var in dump. Used for progress bar.
        self.verbose = 1
        self.CLASS = {
            'OID':         SnmpOid,
            'TimeTicks':   SnmpTimeTicks,
            'OctetString': SnmpOctetString,
            'Integer':     SnmpInteger32,
            'Gauge':       SnmpGauge32,
            'Counter':     SnmpCounter32,
            'Counter64':   SnmpCounter64,
            'IpAddress':   SnmpIpAddress,
            'NULL':        SnmpNull
        }
        # Just reverse mapping of above. Use in _generateMinimalDump()
        self.DUMPTYPE = {
            'Oid'        : 'OID',
            'TimeTicks'  : 'TimeTicks',
            'OctetString': 'OctetString',
            'Integer32'  : 'Integer',
            'Gauge32'    : 'Gauge',
            'Counter32'  : 'Counter',
            'Counter64'  : 'Counter64',
            'IpAddress'  : 'IpAddress',
            'Null'       : 'NULL'
        }


        if CSNMPSIM_LOADED:
            self.oidCompFunc = csnmpsim.compareOids
        else:
            self.oidCompFunc = self._compareOids

    def _expandIfExp(self, value):
        """Convert something like '2.10453e+11' to '210453000000.0'. nhSnmpTool represents Counter64s
           in this format.
        """
        match = self.expRe.search(value)
        if match:
            (base, exp) = match.groups()
            exp = number(exp)
            alreadyExp = len(base[2:])
            # Get rid of '.'            
            newVal = base[0] + base[2:]
            # Add appropriate number of zeros            
            newVal = newVal + '0' * (exp - alreadyExp)
            # Keep as floating point number for now...we take this out later.
            value = newVal + ".0"
        return value

    def load(self, filename):
        """Load mib values from a mib dump file.
        """
        c32Max = (2L**32-1)
        c64Max = (2L**64-1)
        # We want to provide a progress bar. Check total size of file
        size = os.path.getsize(filename)
        estVars = size / self.bytesPerVar
        if estVars == 0:
            estVars = 1  # Avoid division by zero later
        rawVarsProcessed = 0.0
        startTime = time.time()
        f = open(filename, "rt")
        dataRe = re.compile(r'^(\.?[.0-9]+)\s+(\S+)(\s+(\S+))?$')
        commentRe = re.compile(r'\s*#')
        floatRe = re.compile(r'^\d+\.\d+$')
        lines = 0
        if self.verbose:
            sys.stdout.write("Loading: 0%")
            sys.stdout.flush()
        lastPctPrinted = 0        
        while 1:
            lines = lines + 1
            line = f.readline()
            if line == "":
                break
            # Skip comments
            if commentRe.search(line):
                continue
            line = line.rstrip()
            match = dataRe.search(line)
            # Skip invalid lines
            if not match:
                continue
            (oid, _type, dummy, value) = match.groups()

            if oid[0] != '.':
                # We expect normally formatted oids in the library, even though
                # we allow oids with missing leading dots in dumps.
                oid = '.' + oid
            

            if _type == 'Counter64' or _type == 'Counter':
                # Expand exponential notation TCL uses for large floating point numbers,
                # if the value is in that format.
                value = self._expandIfExp(value)
                # If it's a float convert to int by truncating--TCL stores Counter64s as doubles.
                # Do this for Counters as well as Counter64s so we can simulate converted dumps (Counter64->Counter) too.
                if floatRe.search(value):
                    value = value.split('.')[0]


            elif _type == 'OID':
                # The smallest possible encodable oid is .0.0. nhSnmpTool represents this as .0. Convert so we
                # can encode it properly.
                if value == '.0':
                    value = '.0.0'
                
            if value == None:
                value = ""
            elif _type == 'OctetString':
                try:
                    value = self._convertOctetString(value)
                except ValueError:
                    sys.exit("\n\nError converting Octet string [%s] on line %s. Exiting.\n" % (value, lines))
            elif _type == 'OID':
                if not self.oidRe.search(value):
#                    print "[Skipping invalid oid value %s (at oid %s)]" % (value, oid)
                    continue
            # Update progress bar if needed
            rawVarsProcessed = rawVarsProcessed + 1
            currentPctProg = int((rawVarsProcessed/estVars)*100)
            if self.verbose and (currentPctProg > lastPctPrinted):
                if (self._printProgress(currentPctProg, lastPctPrinted)):
                    lastPctPrinted = currentPctProg                
            if self.variable.has_key(oid):
                # If we already saw this var (if in second pass)
                if _type == 'Counter' or _type == 'Counter64':
                    # Store deltas for these types of variables during second pass
                    var = self.get(oid)
                    # Save start value
                    var.initialVal = var.value                        
                    # Calculate delta keeping wrap effect in mind
                    var.delta = long(value) - var.value
                    if var.delta < 0:
                        if _type == 'Counter':
                            max = c32Max
                        else:
                            max = c64Max
                        # Consider delta to be values needed to flip plus new value if the new val is smaller
                        var.delta = (max - var.value) + long(value)

                        # Finally, make delta smaller if it's too big
                        if var.delta*2 >= max:
                            var.delta = number(max*0.40)
                    continue
                else:
                    # Do nothing for others
#                    print "[not reinserting %s]" % oid
                    continue
            exception = 0
            try:
                var = self._createVariable(oid, _type, value)
                self.insert(var)
            except SnmplibInvalidData, data:
                sys.stderr.write("\nInvalid SNMP data encountered on line %s: %s\n" % (lines, data))
                exception = 1
            except (MibStoreInsertError, SnmpSimDumpError), data:
                excType = sys.exc_info()[0]
                sys.stderr.write("\nUnable to insert value for OID %s (line %s): %s: %s\n" % (oid, lines, excType, data))
                exception = 1                
                
            if exception == 1:
                continue
            if oid == '.1.3.6.1.2.1.1.3.0':
                # sysUptime is a special case...handle it this way
                var.initialVal = var.value
                var.changeFunction = sysUptimeChange
            else:
                # Otherwise, assign a change function if there's one defined for this type in CHANGE.
                # Use noChange if there isn't one.
                if CHANGE.has_key(_type):
                    var.changeFunction = CHANGE[_type]
                else:
                    var.changeFunction = noChange

        f.close()
        if self.verbose:
            # Make sure we've printed up to 99%, then add on 100%.
            self._printProgress(99, lastPctPrinted)
            sys.stdout.write("100%\n")
        varsLoaded = len(self.oids)
        if varsLoaded == 0:
            sys.exit("No variables found in dump (zero loaded). Exiting.")
        else:
            # Reset time for deltas
            global SIM_START_TIME
            SIM_START_TIME = time.time()
            if self.verbose:
                stopTime = time.time()
                self._clearScreen()
                print "Loaded %s variables (%.1f seconds load time)." % (varsLoaded, stopTime - startTime)

    def _clearScreen(self):
        """Clear the screen (should work on Windows NT and Unix).
        """
        if os.name == 'nt':
            cmd = 'cls'
        elif os.name == 'posix':
            cmd = 'clear'
        else:
            # Don't do anything if we don't know how
            return
        os.system(cmd)

    def _createVariable(self, oid, _type, value):
        """Function to instantiate the appropriate type of snmp variable object based on type. Also
           handles conversion of values so they match what the classes expect (strings converted to ints, etc)
        """
        if not self.CLASS.has_key(_type):
            raise SnmpSimDumpError, "Unknown variable type %s encountered." % _type
        var = self.CLASS[_type]()
        if _type == 'TimeTicks' or _type == 'Integer' or _type == 'Gauge' or _type == 'Counter' or _type == 'Counter64':
            value = long(value)
        if _type == 'TimeTicks':
            # Negative timeticks aren't valid but show up in dumps sometimes when
            # nhSnmpTool's ints overflow. Just use the absolute value.
            if value < 0:
                value = abs(value)
        var.setValue(value)
        var.oid = oid
        return var

    def _printProgress(self, current, last):
        """Print out progress in progress bar, up to 99%.
        """
        if current >= 100:
            return 0
        for i in range(last+1, current+1):
            # Print out X% if X is a multiple of 10
            if i % 10 == 0:
                sys.stdout.write("%s%%" % i)                
            if ((i%10)+1) % 3 == 0:
                sys.stdout.write(".")
        sys.stdout.flush()
        return 1

    def insert(self, var):
        """Method to insert a variable into the data store. The oid in the variable is used to specify
           where it should be stored.  Data is currently stored in a big dictionary of dictionaries.
        """
        oid = var.oid
        if oid == None:
            raise MibStoreInsertError, "Variables must have their .oid attribute set to be inserted."            
        if not self.oidRe.search(oid):
            raise MibStoreInsertError, "Bad OID value: %s" % oid
        # Add variable to our data hash
        self.variable[oid] = var
        # Add oid to ordered list of all oids
        index = self._binarySearch(oid, exact=0)
        self.oids.insert(index, oid)
        # Fill out .next attributes
        if index + 1 <= (len(self.oids) - 1):
            # For this var, if there is a next variable
            var.next = self.oids[index+1]
        if index != 0:
            # And for var before this one, if there is one.
            self.variable[self.oids[index-1]].next = oid

    def get(self, oid, change=0):
        """Retrieve the mib value associated with an oid. Oid must have previously been inserted into datastore.
        """
        if not self.oidRe.search(oid):
            raise MibStoreGetError, "Bad OID value: %s" % oid
        if not self.variable.has_key(oid):
            raise MibStoreNoSuchNameError, "No such oid %s found." % oid
        var = self.variable[oid]
        if change:
            try:
                # Make variable change itself if changeFunction exists
                var.changeFunction(var)
            except AttributeError:
                pass
        return var

    def getNext(self, oid, change=0):
        """Retrieve the next mib value from a given spot in the mib tree data struct. Raise an exception if there
           isn't a next oid or if the given oid doesn't exist in the data store.
        """
        if not self.oidRe.search(oid):
            raise MibStoreNoSuchNameError, "Bad OID value: %s" % oid
        # First, see if this oid is an exact oid that exists already. If so, use the .next attr
        # to return the appropriate var, changing it if change=1.
        if self.variable.has_key(oid):
            try:
                var = self.variable[oid].next
            except AttributeError:
                raise MibStoreNoSuchNameError, "No next oid to retrieve for %s." % oid            
            if change:
                try:
                    # Make variable change itself if changeFunction exists
                    var.changeFunction(var)
                except AttributeError:
                    pass
            return self.variable[var]
        else:
            # Otherwise we need to look for the lexographical successor of the partial oid given.
            # Do a binary search of the flat list of oids we have to determine the next oid, then
            # just return that.
            index = self._binarySearch(oid)
            length = len(self.oids)
            if index == None or length == 0 or index == length:
                raise MibStoreNoSuchNameError, "No next oid to retrieve for %s." % oid
            nextOid = self.oids[index]
            var = self.get(nextOid, change)
            return var

    def _convertOctetString(self, string):
        if string == None or string == "":
            return ""
        nums = string.split('-')
        retStr = ""
        for i in nums:
            retStr = retStr + chr( number(i))
        return retStr

    def _unconvertOctetString(self, string):
        if string == None or string == "":
            return ""
        return '-'.join(map((lambda c: `ord(c)`), string))
        
    def _binarySearch(self, oid, exact=0):
        """exact = true:  Return the index of the variable containing the oid passed in, None if not present.
           exact = false: Return the index at which the oid would be inserted at into the list if it were present.
        """ 
        start = 0
        end = len(self.oids)
        while start < end:
            mid = (start+end)//2
#            if oid < self.oids[mid]:
            if self.oidCompFunc(oid, self.oids[mid]) == -1:
                end = mid
            else:
                start = mid+1
        index = start
        if not exact:
            # Inexact search
            return index
        # Logic for exact search
        index = index -1  # Back up one to exact match
        if self.oids[index] == oid:
            return index
        else:
#            print "index=%s, found oid %s != search oid %s" % (index, self.oids[index].oid, oid)
            return None

    def _compareOids(self, oid1, oid2):
        """Function to compare oid1 and oid2 and return -1 if oid1 comes first, 0 if equal, and
           1 if oid2 comes first. Note that for speed no validity checking is done--the caller should do this.
        """
        pos1 = 0
        pos2 = 0

        len1 = len(oid1)
        len2 = len(oid2)
        smaller = min(len1, len2)
        for i in range(smaller):
            if oid1[i] == oid2[i]:
                continue
            # Found difference. Grab chars up to next . and then compare numerically
            start1 = start2 = i
            while oid1[start1-1] != '.':
                start1 = start1 - 1
            while oid2[start2-1] != '.':
                start2 = start2 - 1
                
            end1 = i
            end2 = i
            while end1 < len1 and oid1[end1] != '.':
                end1 = end1 + 1
            while end2 < len2 and oid2[end2] != '.':
                end2 = end2 + 1

            val1 = number(oid1[start1:end1])
            val2 = number(oid2[start2:end2])

            if val1 < val2:
                # First oid comes first
                return -1
            elif val1 > val2:
                # Second oid comes first
                return 1
        if len1 == len2:
            # They are the same
            return 0
        else:
            # One's a substring of the other. The shorter comes first.
            return cmp(len1, len2)


class SnmpSim:
    """SNMP simulator class. Uses MibDataStore class to store data. 
    """
    # Load mib from specified file
    def __init__(self):
        self.verbose = 1
        self.mib = MibDataStore()
        self.community = 'public'
        self.v1Mode = 1
        self.v2Mode = 1
        self.port = 5000
        self.tweakSysName = 0
        self.sock = None
        self.clientIp = None   # Assume serial/single threaded handling for now
        self.MAX_MESSAGE_SIZE = 5120
        self.interestingOids = {}

        # Options
        self.dumpOutgoingMessage = 0
        self.dumpIncomingMessage = 0
        self.minDumpMode = 0
        self.validIps = []  # If set, only respond to requests from IPs in this list

    def load(self, filename):
        """Load file into mib data store.
        """
        self.filename = filename
        self.mib.load(filename)

    def setVerbose(self, verbose):
        """Set verbose on/off (1/0). Function is used because we want to set it in the
           mib data store too.
        """
        self.verbose = verbose
        self.mib.verbose = verbose

    def run(self):
        """Start the simulator (make it bind to a port and handle SNMP requests).
        """
        if self.tweakSysName:
            try:
                sysDescr = self.mib.get('.1.3.6.1.2.1.1.5.0')
#                hostname = os.popen('uname -n').readline()
                hostname = socket.gethostname()
                sysDescr.setValue(hostname + ':' + str(self.port) + "_" + sysDescr.value)
            except:
                pass
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            self.sock.bind( ('', self.port) )
        except socket.error, data:
            sys.exit("Error binding to port %s: %s" % (self.port, data[1]))
        if self.verbose:
            sys.stdout.write(BELL)
        verStr = ""
        if self.v1Mode == 0 and self.v2Mode == 0:
            raise SnmpSimError, "You must specify at least one SNMP version mode."
        if self.v1Mode and self.v2Mode:
            verStr = "SNMPv1 and SNMPv2"
        else:
            # Must be only one or the other
            if self.v1Mode:
                verStr = "SNMPv1"
            else:
                verStr = "SNMPv2"
        if self.verbose:
            print "\nReady to respond to requests in %s mode on UDP port %s." % (verStr, self.port)
            if self.validIps:
                if len(self.validIps)== 1:
                    print "(Restricted to the IP address [%s].)" % self.validIps[0]                    
                else:
                    print "(Restricted to IP addresses [%s].)" % ', '.join(self.validIps)
                    
        while 1:
            try:
                (read, write, error) = select([self.sock], [], [], 1.0)
            except (KeyboardInterrupt, SystemExit):
                self._stop()
            if len(read) == 0:
                continue
            self.sock = read[0]
            try:
                data, self.clientIp = self.sock.recvfrom(self.MAX_MESSAGE_SIZE)
            except socket.error, data:
                print "[* socket error: %s *]" % data
                continue
            if self.validIps:
                if not self.clientIp[0] in self.validIps:
                    # Silently ignore requests that aren't from a specific IP, if user wanted this.
                    continue
            if self.dumpIncomingMessage:
                # Dump incoming msg
                print "[incoming msg: %s]" % hexStr(data)                            
            try:
                message = SnmpMessage(data)
#            except SnmplibError, data:
            except:
                excType = sys.exc_info()[0]
                data = sys.exc_info()[1]
                sys.stderr.write("Unable to decode snmp message from %s: %s: %s\n" % \
                                 (self.clientIp[0], excType, data))
                continue

            if message.communityString.value != self.community:
                sys.stderr.write("Supplied community of %s doesn't match %s\n" % \
                                 (message.communityString.value, self.community))
            reqType = message.pdu.type
            # Handle message. Return response to client.
            respMsg = None
            # Note incoming oids in varbind
            if self.minDumpMode:
                oids = map((lambda x: x.oid), message.pdu.varbind.items)
                for oid in oids:
                    if not self.interestingOids.has_key(oid):
                        self.interestingOids[oid] = 1
                        
            try:
#                mainLock.acquire()
                respMsg = self._processMessage(message, self.clientIp[0])
#                mainLock.release()
#            except SnmplibError, data:
            except:
                # TODO: Decide if this should change at all (i.e. be preceeded by "Error processing message" or anything)
                traceback.print_exc(file=sys.stdout)
            # TODO: Make clientIp be just a local variable?
            if respMsg != None:
                encoded = respMsg.encode()
                if len(encoded) > self.MAX_MESSAGE_SIZE:
                    # Too big...for now just return a tooBig error (can get fancier later)
                    respMsg = SnmpMessage()
                    respMsg.version.setValue(message.version.value)
                    respMsg.pdu.type = 'GetResponse'
                    respMsg.pdu.errorStatus.setValue(1)  # tooBig
                    for var in message.pdu.varbind.items:
                        respMsg.pdu.varbind.items.append(var)
                    encoded = respMsg.encode()
                    if len(encoded) > self.MAX_MESSAGE_SIZE:
                        # If THIS is still too big (very unlikely) just drop packet.
                        continue
                if self.dumpOutgoingMessage:
                    print "[outgoing msg: %s]" % hexStr(encoded)  
                try:
                    self.sock.sendto(encoded, self.clientIp)
                except:
                    # TODO: Decide what this should look like. Probably add -d option for full traceback, and
                    #       do only more generic error otherwise.
                    traceback.print_exc(file=sys.stdout)
                    #                        excType = sys.exc_info()[0]
                    #                        data = sys.exc_info()[1]
                    #                        sys.stderr.write("Unable to encode snmp response to send to %s: %s: %s\n" \
                    #                                         % (self.clientIp[0], excType, data))
            # Note outgoing oids in varbind
            if self.minDumpMode and respMsg != None:
                oids = map((lambda x: x.oid), respMsg.pdu.varbind.items)
                for oid in oids:
                    if not self.interestingOids.has_key(oid):
                        self.interestingOids[oid] = 1

    def _processMessage(self, msg, displayIp=None):
        """Process a message contained in a message object, and return the appropriate response
           (None object if there should be no response). Uses displayIp in messages if in verbose
           mode and an IP addr is specified.
        """
        if len(msg.pdu.varbind.items) == 0:
            verStr = "v%s" % (msg.version.value + 1)
            if self.verbose:
                print "[Not responding to empty %s SNMP request (no oids in request).]" % verStr
            return None
        origVars = msg.pdu.varbind.items[:]
        ver = msg.version.value
        if ver == 0 and not self.v1Mode:
            if self.verbose:
                print "[Not responding to v1 request (set v1Mode if you want to do this)"
            return None
        if ver == 1 and not self.v2Mode:
            if self.verbose:            
                print "[Not responding to v2 request (set v2Mode if you want to do this)"
            return None
                    
        if ver+1 == 1:
            # SNMPv1 request
            pduType = msg.pdu.type
            if pduType == "GetRequest":
                if self.verbose:
                    oidsStr = ', '.join(map((lambda x: x.oid), msg.pdu.varbind.items))
                    if displayIp:
                        print "[%s: v%s GET request for %s]" % (displayIp, msg.version.value+1, oidsStr)
                    else:
                        print "[v%s GET request for %s]" % (msg.version.value+1, oidsStr)
                for i in range(0, len(msg.pdu.varbind.items)):
                    try:
                        msg.pdu.varbind.items[i] = self.mib.get(msg.pdu.varbind.items[i].oid, change=1)
                    except (MibStoreNotRetrievable, MibStoreNoSuchNameError):
                        if self.verbose:
                            print "  [noSuchName: %s]" % msg.pdu.varbind.items[i].oid
                        msg.pdu.varbind.items = origVars
                        msg.pdu.type = 'GetResponse'
                        msg.pdu.errorStatus.setValue(2)
                        msg.pdu.errorIndex.setValue(i+1)
                        return msg

                msg.pdu.type = 'GetResponse'
                return msg
            elif pduType == 'GetNextRequest':
                if self.verbose:
                    oidsStr = ', '.join(map((lambda x: x.oid), msg.pdu.varbind.items))
                    if displayIp:
                        print "[%s: v%s GETNEXT request for %s]" % (displayIp, msg.version.value+1, oidsStr)
                    else:
                        print "[v%s GETNEXT request for %s]" % (msg.version.value+1, oidsStr)
                for i in range(0, len(msg.pdu.varbind.items)):
                    try:
                        msg.pdu.varbind.items[i] = self.mib.getNext(msg.pdu.varbind.items[i].oid, change=1)
                    except MibStoreNoSuchNameError:
                        if self.verbose:
                            print "  [noSuchName: %s]" % msg.pdu.varbind.items[i].oid
                        msg.pdu.type = 'GetResponse'                                        
                        msg.pdu.errorStatus.setValue(2)
                        msg.pdu.errorIndex.setValue(i+1)
                        return msg            
                msg.pdu.type = 'GetResponse'
                return msg
            else:
                raise SnmpSimUnknownRequest, "Unknown/unsupported request type: %s" % pduType            
        elif ver+1 == 2:
            # SNMPv2 request
            # Modify to get reports
            pduType = msg.pdu.type
            if pduType == "GetRequest":
                if self.verbose:
                    oidsStr = ', '.join(map((lambda x: x.oid), msg.pdu.varbind.items))
                    if displayIp:
                        print "[%s: v%s GET request for %s]" % (displayIp, msg.version.value+1, oidsStr)
                    else:
                        print "[v%s GET request for %s]" % (msg.version.value+1, oidsStr)                    
                if ranDmMode == 1:
                    rd_snmpsim(oidsStr)
                for i in range(0, len(msg.pdu.varbind.items)):
                    try:
                        msg.pdu.varbind.items[i] = self.mib.get(msg.pdu.varbind.items[i].oid, change=1)
                    except (MibStoreNoSuchNameError, MibStoreNotRetrievable):
                        # Do the v2 thing and just tag missing oids with SnmpNoSuchObject
                        # (we don't differentiate between objects and instances so just use this)
                        oid = msg.pdu.varbind.items[i].oid
                        msg.pdu.varbind.items[i] = SnmpNoSuchObject()
                        msg.pdu.varbind.items[i].oid = oid
                        if self.verbose:
                            print "  [noSuchObject: %s]" % oid
                msg.pdu.type = 'GetResponse'
                return msg
            elif pduType == 'GetNextRequest':
                if self.verbose:
                    oidsStr = ', '.join(map((lambda x: x.oid), msg.pdu.varbind.items))
                    if displayIp:
                        print "[%s: v%s GETNEXT request for %s]" % (displayIp, msg.version.value+1, oidsStr)
                    else:
                        print "[v%s GETNEXT request for %s]" % (msg.version.value+1, oidsStr)                    
                for i in range(0, len(msg.pdu.varbind.items)):
                    try:
                        msg.pdu.varbind.items[i] = self.mib.getNext(msg.pdu.varbind.items[i].oid, change=1)
                    except MibStoreNoSuchNameError:
                        # Do the v2 thing and just tag missing oids with SnmpEndOfMibView
                        oid = msg.pdu.varbind.items[i].oid
                        msg.pdu.varbind.items[i] = SnmpEndOfMibView()
                        msg.pdu.varbind.items[i].oid = oid                        
                        if self.verbose:
                            print "  [endOfMibView]"                    
                msg.pdu.type = 'GetResponse'
                return msg
            elif pduType == 'GetBulkRequest':
                if self.verbose:
                    oids = map((lambda x: x.oid), msg.pdu.varbind.items)                    
                    oidsStr = ', '.join(map((lambda x: x.oid), msg.pdu.varbind.items))
                    for i in range(0, msg.pdu.nonRepeaters.value):
                        oids[i] = oids[i] + "(NR)"
                    oidsStr = ', '.join(oids)                    
                    if displayIp:
                        print "[%s: v%s GETBULK request for %s, nr=%s, mr=%s]" % \
                              (displayIp, msg.version.value+1, oidsStr, msg.pdu.nonRepeaters.value, msg.pdu.maxRepetitions.value)
                    else:
                        print "[v%s GETBULK request for %s]" % (msg.version.value+1, oidsStr)                                                
                # Get response msg set up properly
                respMsg = SnmpMessage()
                respMsg.version.setValue(1) # v2
                respMsg.communityString.setValue(msg.communityString.value)
                respMsg.pdu.type = 'GetResponse'
                respMsg.pdu.requestId.setValue(msg.pdu.requestId.value)
                # A few shorthand vars for sanity below
                nr = msg.pdu.nonRepeaters.value
                mr = msg.pdu.maxRepetitions.value
                vb = msg.pdu.varbind
                respVb = respMsg.pdu.varbind
                if nr < 0:
                    nr = 0
                if mr < 0:
                    mr = 0

                if nr > 0:
                    # Do regular GETNEXTs on first N vars
                    for i in range(0, nr):
                        try:
#                            print "  [GETNEXT on %s (NON-REPEATER)]" % msg.pdu.varbind.items[i].oid
                            var = self.mib.getNext(vb.items[i].oid, change=1)
                        except MibStoreNoSuchNameError:
                            # Do the v2 thing and just tag missing oids with SnmpEndOfMibView
                            var = SnmpEndOfMibView()
                            var.oid = vb.items[i].oid
                            if self.verbose:
                                print "  [endOfMibView]"
                        # Add either the retrieved var or the EndOFMibView var
                        respMsg.pdu.varbind.items.append(var)

                # Loop through starting off after any nonRepeaters (index = 0, if there are none)
                remainingOids = map((lambda x: vb.items[x].oid), range(nr, len(vb.items)))
                maxOids = len(remainingOids) * mr
                currentOids = remainingOids[:]
                tmpOids = []
                while len(respVb.items) < maxOids and len(currentOids) != 0:
                    for oid in currentOids:
                        if len(respVb.items) >= maxOids:
                            # Catch any weirdo cases where one oid can't be retrieved anymore and throws cycle
                            # off the boundary
                            break   
                        try:
                            var = self.mib.getNext(oid, change=1)
                            respVb.items.append(var)                            
                            tmpOids.append(var.oid)
                        except MibStoreNoSuchNameError:
                            if self.verbose:
                                print "  [endOfMibView]"
                            var = SnmpEndOfMibView()
                            var.oid = oid
                            respVb.items.append(var)
                    currentOids = tmpOids[:]    # Do getnexts on oids we got back
                    tmpOids = []
                return respMsg
            else:
                raise SnmpSimUnknownRequest, "Unknown/unsupported request type: %s" % pduType
        else:
            if self.verbose:
                print "[Not responding to v%s request.]" % (ver+1)

    def _generateMinimalDump(self):
        """Make a minimal dump containing only oids that have been requested or returned.
           Store in self.minDumpFile.
        """
        oids = self.interestingOids.keys()
        oids.sort(self.mib.oidCompFunc)
        # Generate new filename
        minDumpFile = self.filename
        minDumpFile = re.sub(r'(\.[^.]*)$', r'-min\1', minDumpFile)  # try to make dump.mdr -> dump-min.mdr
        if minDumpFile == self.filename:
            minDumpFile = minDumpFile + "-min.mdr"                   # Just tack this on if there's no .
        fh = open(minDumpFile, "wt")
        fh.write("#\n")
        fh.write("# Minimal dump file generated from %s on %s.\n" % (self.filename, time.strftime("%Y-%m-%d %H:%M")))
        fh.write("#\n")

        # Dump first pass
        count = 0
        foundDelta = 0
        for oid in oids:
            count += 1
            if not self.mib.variable.has_key(oid):
                continue
            var = self.mib.variable[oid]
            # Note which oids have deltas...used to generate second pass
            if not foundDelta and hasattr(var, "delta"):
                foundDelta = 1
            oidStr = var.oid
            valStr = var.value
            typeStr = self.mib.DUMPTYPE[var.type]
            if typeStr == 'OctetString':
                valStr = self.mib._unconvertOctetString(valStr)
            fh.write("%s %s %s\n" % (oidStr, typeStr, valStr))
        # And second, if any oids has deltas
        if foundDelta:
            fh.write("\n#\n")
            fh.write("# Second pass\n")
            fh.write("#\n")
            for oid in oids:
                if not self.mib.variable.has_key(oid):
                    continue
                var = self.mib.variable[oid]
                oidStr = var.oid
                if hasattr(var, "delta"):
                    var.changeFunction(var)  # Change variables with deltas
                valStr = var.value
                typeStr = self.mib.DUMPTYPE[var.type]
                if typeStr == 'OctetString':
                    valStr = self.mib._unconvertOctetString(valStr)
                # TODO: get counter64 stuff working.
                fh.write("%s %s %s\n" % (oidStr, typeStr, valStr))            
        fh.close()
        print "%s oids written to %s (minimal dump)" % (count, os.path.basename(minDumpFile))

    def _stop(self):
        """Stop simulator, generating minimal mib dump if -m given.
        """
        if self.verbose:
            print "\nStopping simulator."
        if self.minDumpMode:
            self._generateMinimalDump()
        sys.exit(0)

class ReqHandler(BaseHTTPServer.BaseHTTPRequestHandler):
    # NOTE: _handler dict defined at bottom of class instead of here since it references
    #       members of the class that need to exist when it does so.
    def log_request(self, format):
        # Don't log stuff for now.
        pass
    
    def do_GET(self):
        try:
            if '?' in self.path:
                path = self.path.split('?')[0]
            else:
                path = self.path
        except:
            # If anything weird happens just bail.
            self.send_response(400, "Bad Request")
            self.send_header('Content-type', 'text/html')
            self.end_headers()            
            self.wfile.write("Bad request sent.")
            return
        if not self._handler.has_key(path):
            self.send_response(404, "Not Found")
            self.send_header('Content-type', 'text/html')
            self.end_headers()            
            self.wfile.write("Requested URI %s not found on this server." % path)
            return
  
        # Call function associated with path
#        mainLock.acquire()
        try:
            self._handler[path](self)
        finally:
#            mainLock.release()
            pass

    def _mainPage(self):
        """Generate main page for web interface to simulator.
        """
        self.send_response(200, "Ok")
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        write = self.wfile.write
        try:
            sysDescr = sim.mib.get('.1.3.6.1.2.1.1.5.0')
            write("<html><head><title>%s Simulator</title></head><body>\r\n" % cgi.escape(sysDescr.value,1 ))
            write("<h1>%s Simulator</h1>\r\n" % cgi.escape(sysDescr.value,1 ))
        except:
            write("<html><head><title>%s Simulator Main Page</title></head><body>\r\n")
            write("<h1>Simulator Main Page</h1>\r\n")
        write("<hr><form action=/viewVar>View a single variable:<br>\r\n")
        write('<input type=text name=oid value=".1.3.6.1.2.1.1.1.0" size=40>\r\n')
        write("<input type=submit value=View></form><hr>\r\n")
        write("<a href=listVars>View all variables</a> (may produce lots of output)<br>\r\n")
        write("</body></html>\r\n")

    def _listVars(self):
        """Generate output listing all oids and their values.
        """
        self.send_response(200, "Ok")
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        write = self.wfile.write
        write("<html><head><title>Simulator Loaded Variables</title></head><body>\r\n")
        write("<h1>Simulator Loaded Variables</h1>\r\n")
        write("<table border=1>\r\n")
        write("<tr><td>OID</td><td>Type</td><td>Value</td></tr>\r\n")
        curOid = '.1.3'
        while 1:
            try:
                var = sim.mib.getNext(curOid)
            except:
                break
            oid = var.oid
            _type = var.type
            value = str(var.value)
            if value == '':
                value = '&nbsp;'
            write("<tr><td><a href=viewVar?oid=%s>%s</a></td><td>%s</td><td>%s</td></tr>\r\n" % (oid, oid, _type, value))
            curOid = var.oid
        write("</table></body></html>\r\n")

    def _viewVar(self):
        """View info about a variable and allow it to be changed.
        """
        write = self.wfile.write
        try:
            # Try to grab oid value
            reqStr = self.path.split('?')[1]
            pairs = reqStr.split('&')
            data = {}
            for pair in pairs:
                var, val = pair.split('=')
                data[var] = urllib.unquote_plus(val)
            if not data.has_key('oid'):
                # They have to specific an oid.
                self.send_response(200, "Ok")
                self.send_header('Content-type', 'text/html')
                self.end_headers()            
                write("Error: An Oid must be specified.")
                return
            oid = data['oid']
            if oid[0] != '.':
                oid = '.' + oid
        except:
            # If anything weird happens just bail.
            self.send_response(400, "Bad Request")
            self.send_header('Content-type', 'text/html')
            self.end_headers()            
            write("Bad request sent.")
            return

        # Make sure OID exists
        try:
            var = sim.mib.get(oid)
        except MibStoreError, data:
            exception = sys.exc_info()[0]
            self.send_response(200, "Ok")
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            write("<html><head><title>Error Viewing Variable</title></head><body>\r\n")
            write("<h1>Error Viewing Variable</h1>\r\n")            
            write("<font size=+1>Exception %s:</font><br>\r\n" % exception)
            write(str(data) + "\r\n")
            write("</body></html>")
            return
        
        # Display OID attributes if all is well.
        self.send_response(200, "Ok")
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        oid = var.oid
        _type = var.type
        value = str(var.value)
        changeFunction = str(var.changeFunction)
        if value == '':
            value = '&nbsp;'
        changeFunction = re.sub(r'<', '&lt;', changeFunction)
        changeFunction = re.sub(r'>', '&gt;', changeFunction)    
        write("<html><head><title>View Variable</title></head><body>\r\n")
        write("<h1>View Variable</h1>\r\n")
        write("<table border=1>\r\n")
        write("<tr><td><b>OID:</b></td><td>%s</td><td>&nbsp;</td></tr>\r\n" % oid)
        write("<tr><td><b>Type:</b></td><td>%s</td><td>&nbsp;</td></tr>\r\n" % _type)
        write('<form action="/changeVar"><input type=hidden name=oid value="%s">\r\n' % cgi.escape(oid, 1))
        write('<tr><td><b>Value:</b></td><td><input name=value size=40 value="%s"></td><td>' % cgi.escape(value,1) + \
              "<input type=submit value=Change></tr></form>\r\n")
        try:
            # Show delta if there is one
            d = var.delta
            write('<tr><td><b>Delta:</b></td><td>%s</td></tr>\r\n' % d)
        except:
            pass
        write("<tr><td><b>Change Function:</b></td><td>%s</td><td>&nbsp;</td></tr>\r\n" % changeFunction)
        write("</table>\r\n")
        try:
            var = sim.mib.getNext(oid)
            write("<a href=/viewVar?oid=%s>Next Oid</a> " % var.oid)
        except:
            pass
        write('<a href="/">Main Page</a>\r\n')        
        write("</body></html>")            

    def _changeVar(self):
        """Change an variables OID's value on the fly, while the simulator is running.
        """
        write = self.wfile.write
        try:
            # Try to get parameters
            reqStr = self.path.split('?')[1]
            pairs = reqStr.split('&')
            data = {}
            for pair in pairs:
                var, val = pair.split('=')
                data[var] = urllib.unquote_plus(val)
            if not data.has_key('oid') and data.has_key('value'):
                # They have to specific an oid.
                self.send_response(200, "Ok")
                self.send_header('Content-type', 'text/html')
                self.end_headers()            
                write("Error: An Oid and a value must both be specified.")
                return
            oid = data['oid']
            if oid[0] != '.':
                oid = '.' + oid            
            value = data['value']
        except:
            # If anything weird happens just bail.
            self.send_response(400, "Bad Request")
            self.send_header('Content-type', 'text/html')
            self.end_headers()            
            write("Bad request sent.")
            return
        # Get var
        try:
            var = sim.mib.get(oid)
        except MibStoreError, data:
            exception = sys.exc_info()[0]
            self.send_response(200, "Ok")
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            write("<html><head><title>Error Changing Variable</title></head><body>\r\n")
            write("<h1>Error Changing Variable</h1>\r\n")
            write("<font size=+1>Exception %s:</font><br>" % exception)
            write(str(data) + "\r\n")
            write("</body></html>")
            return
        # Change value
        try:
            if var.type != 'OctetString' and var.type != 'Oid' and var.type != 'IpAddress':
                value = number(value)
                list_fixed_Oids.append(oid)
            var.setValue(value)
        except (MibStoreError, SnmplibError), data:
            exception = sys.exc_info()[0]
            self.send_response(200, "Ok")
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            write("<html><head><title>Error Changing Variable</title></head><body>\r\n")
            write("<h1>Error Changing Variable</h1>\r\n")
            write("<font size=+1>Exception %s:</font><br>\r\n" % exception)
            write(str(data) + "\r\n")
            write("</body></html>")
            return
        # Let user know value was changed successfully.
        self.send_response(200, "Ok")
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        write("<html><head><title>Variable Value Changed</title></head><body>\r\n")
        write("<h1>Variable Value Changed</h1>\r\n")
        write("<font size=+1>Changed value of Variable</font>%s<font size=+1> to </font>" % oid)
        write("%s <font size=+1>successfully.</font><br>\r\n" % value)
        write('<br><a href="/">Main Page</a>\r\n')
        write("</body></html>")


    def _writeMinDump(self):
        """Write out minimal dump file if we are in minimal dump mode.
        """
        write = self.wfile.write
        if sim.minDumpMode:
            # Stop simulator and generate minimal mib dump if in min dump mode
            self.send_response(200, "Ok")
            self.send_header('Content-type', 'text/html')
            self.end_headers()            
            write("Writing out minimal dump file.")
            sim._generateMinimalDump()
        else:
            self.send_response(200, "Ok")
            self.send_header('Content-type', 'text/html')
            self.end_headers()            
            write("Error--not in minimal dump mode")
            

    _handler = {'/':              _mainPage,
                '/listVars':      _listVars,
                '/viewVar':       _viewVar,
                '/changeVar':     _changeVar,
                '/writeMinDump':  _writeMinDump}


def runWebServer(port):
    server_class = BaseHTTPServer.HTTPServer
    handler_class = ReqHandler
    server_address = ('', port)
    httpd = server_class(server_address, handler_class)
    httpd.serve_forever()


if __name__ == "__main__":
    usage = "Usage: snmpsim <options> -f <file>\n" + \
            " Options:\n" + \
            "  -f <file>  = file to use for SNMP data (nhSnmpTool dump file)\n" + \
            "  -p <port>  = Run simulator on this UDP port\n" + \
            "  -w         = enable embedded web server (runs on same port as sim except TCP)\n" + \
            "  -s         = Prepend local <hostname>:<port>_ to sysName\n" + \
            "  -q         = Quiet mode--suppress most output\n" + \
            "  -v1        = SNMPv1 enabled (on by default if nothing specified)\n" + \
            "  -v2c       = SNMPv2 enabled\n" + \
            "  -di        = Dump incoming SNMP messages, in hex.\n" + \
            "  -do        = Dump outgoing SNMP messages, in hex.\n" + \
            "  -m         = Generate minimal dump (with only oids used in session) on exit.\n" + \
            "  -r [<ip>]  = Restrict responses to requests from <ip> (default is local ip)\n"
            
    args = sys.argv[1:]
    if len(args) < 2:
        sys.exit(usage)
    port = 5000
    file = ''
    v1Mode = 0
    v2Mode = 0
    webServer = 0
    verbose = 1
    tweakSysName = 0
    dumpIncoming = 0
    dumpOutgoing = 0
    minDumpMode = 0
    ranDmMode = 0
    validIps = []
    while len(args):
        arg = args[0]
        args = args[1:]

        if arg == '-v1':
            v1Mode = 1
        elif arg == '-v2c':
            v2Mode = 1
        elif arg == '-w':
            webServer = 1
        elif arg == '-s':
            tweakSysName = 1
        elif arg == '-di':
            dumpIncoming = 1
        elif arg == '-do':
            dumpOutgoing = 1
        elif arg == '-q':
            verbose = 0
        elif arg == '-p':
            if not len(args):
                sys.exit(usage)
            port = args[0]
            args = args[1:]
        elif arg == '-f':
            if not len(args):
                sys.exit(usage)
            file = args[0]
            args = args[1:]
        elif arg == '-m':
            minDumpMode = 1
        elif arg == '-rd':
            ranDmMode = 1
        elif arg == '-r':
            # Restrict to either IP specified or local machine if none given
            if not len(args) or args[0][0] == '-':
                # Default to loopback and local ip
                validIps.append('127.0.0.1')
                try:
                    localIp = socket.gethostbyname(socket.gethostname())
                    validIps.append(localIp)
                except:
                    pass
            else:
                # Use provided IP
                validIps = [args[0]]
                args = args[1:]
        else:
            sys.exit(usage)
            
    if file == '':
        sys.exit(usage)
    if v1Mode == 0 and v2Mode == 0:
        # If neither mode was specified, default to v1
        v1Mode = 1

    if not os.path.exists(file) or not os.path.isfile(file):
        sys.exit("%s doesn't exist or isn't a file. Exiting." % file)
    sim = SnmpSim()

    sim.minDumpMode = minDumpMode
    sim.validIps = validIps
    sim.port = int(port)
    sim.dumpIncomingMessage = dumpIncoming
    sim.dumpOutgoingMessage = dumpOutgoing
    sim.v1Mode = v1Mode
    sim.v2Mode = v2Mode
    sim.tweakSysName = tweakSysName
    sim.setVerbose(verbose)
    sim.load(file)

    mainLock = thread.allocate_lock()
    if verbose:
        if sim.minDumpMode:
            print "\n  Hit CTRL-C to generate minimal mib dump after hitting oids in simulator."
        if webServer:
            url = 'http://' + socket.gethostname() + ':' + port + '/'
            # Get lock in main scope so both sim and web server can use it
            print "\n  Spawning embedded web server on %s" % url
            thread.start_new_thread(runWebServer, (int(port),))

    sim.run()

