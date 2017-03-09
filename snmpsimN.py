#!/usr/bin/env python

import sys, exceptions, re, time, os, traceback
import thread
import socket
from select import select
from snmplib import \
    SnmpOid,\
    SnmpTimeTicks,\
    SnmpOctetString,\
    SnmpInteger32,\
    SnmpGauge32,\
    SnmpCounter32,\
    SnmpCounter64,\
    SnmpIpAddress,\
    SnmpNull,\
    SnmplibInvalidData,\
    SnmpMessage,\
    SnmpNoSuchObject,\
    SnmpEndOfMibView

# SnmpMessage: for encode and decode snmp message

from n_function import timeit


# Place holder for extending exceptions
class SnmpSimError(exceptions.Exception):
    pass


class SnmpSimDumpError(SnmpSimError):
    pass


class SnmpSimUnknownRequest(SnmpSimError):
    pass


class MibStoreError(SnmpSimError):
    pass


class MibStoreInsertError(MibStoreError):
    pass


class MibStoreGetError(MibStoreError):
    pass  # For both get and get_next


class MibStoreNoSuchNameError(MibStoreGetError):
    pass


class MibStoreNotRetrievable(MibStoreGetError):
    pass


SIM_START_TIME = time.time()
DELTA_APPLY_RATE = 300  # 5 minutes


def number(string):
    try:
        return int(string)
    except (ValueError, OverflowError):
        # Unclear on why sometimes it's overflow vs value error, but this should work.
        return long(string)


# Change functions (assigned to variables dynamically)
def change_sysuptime(old_value):
    new_value = old_value.initialVal + ((time.time() - SIM_START_TIME) * 100)
    new_value = number(new_value)
    old_value.setValue(new_value)


def change_nothing():
    pass


def change_counter32_time_based(old_value):
    """Change counter32 values based on the time rather than every time this
       function is called (per request). This should prevent large deltas
       when multiple clients are all polling a counter with extremely large
       deltas.
    """
    max_counter32 = 4294967295L
    elapsed = time.time() - SIM_START_TIME
    delta = old_value.delta
    if delta < 10:
        delta = 10
    old_value.setValue((old_value.initialVal + int(elapsed / DELTA_APPLY_RATE) * delta) % (max_counter32 + 1))


def change_counter64_time_based(old_value):
    """Change counter64 values based on the time rather than every time this
       function is called (per request). This should prevent large deltas
       when multiple clients are all polling a counter with extremely large
       deltas.
    """
    max_counter64 = 18446744073709551615L
    elapsed = time.time() - SIM_START_TIME
    delta = old_value.delta
    if delta < 10:
        delta = 10
    old_value.setValue((old_value.initialVal + int(elapsed / DELTA_APPLY_RATE) * delta) % (max_counter64 + 1))


def change_counter32_per_request(old_value):
    """Change counter32 values by delta once every time this function is called
       (once per SNMP request, basically).
    """
    max_counter32 = 4294967295L
    delta = old_value.delta
    if delta < 10:
        delta = 10
    new_value = old_value.value + delta
    # Wrap counter if necessary
    if new_value > max_counter32:
        new_value %= (max_counter32 + 1)
    old_value.setValue(new_value)


def change_counter64_per_request(old_value):
    """Change counter64 values by delta once every time this function is called
       (once per SNMP request, basically).
    """
    max_counter64 = 18446744073709551615L
    delta = old_value.delta
    if delta < 10:
        delta = 10
    new_value = old_value.value + delta
    # Wrap counter if necessary
    if new_value > max_counter64:
        new_value %= (max_counter64 + 1)
    old_value.setValue(new_value)


# This mapping controls which types (in dump) are mapped to which change functions.
CHANGE = {'Counter': change_counter32_time_based,
          'Counter64': change_counter64_time_based}


class MibDataStore(object):
    """NEW mib data store (uses a hash for data and a list for getnexts).

       Class to store oids and associated values. Because ultimately only mib variable instances can be retrieved,
       the distinction between mib variables and their instances isn't maintained here--there is only a simple mapping
       between oids and the variables they point to. Use is straightforward--insert values using the insert method and
       retrieve them using the get or get_next methods.
       Logic for understanding SnmpSim-formatted dumps is in here too.
    """

    # Dictionary that maps a string data type to the class that should be used for that data.
    def __init__(self):
        self.variable = {}  # oid -> variable hash
        self.oids = []  # gets populated with all oids, used for inexact getnexts
        self.oid_pattern = re.compile(r'^\.\d\.\d+(\.\d+)*$')
        self.exp_pattern = re.compile(r'^(\d\.\d+)e\+(\d+)$')
        self.dictType = type({})
        self.bytes_per_line = 255  # Estimated average bytes per line in dump_file. Used for progress bar.
        self.verbose = 0
        self.CLASS = {
            'OID': SnmpOid,
            'TimeTicks': SnmpTimeTicks,
            'OctetString': SnmpOctetString,
            'Integer': SnmpInteger32,
            'Gauge': SnmpGauge32,
            'Counter': SnmpCounter32,
            'Counter64': SnmpCounter64,
            'IpAddress': SnmpIpAddress,
            'NULL': SnmpNull
        }

    def _expand_if_exp(self, value):
        """Convert something like '2.10453e+11' to '210453000000.0'. SnmpSim represents Counter64s
           in this format.
        """
        match = self.exp_pattern.search(value)
        if match:
            (base, exp) = match.groups()
            exp = number(exp)
            number_exp = len(base[2:])
            # Get rid of '.'
            new_value = base[0] + base[2:]
            # Add appropriate number of zeros
            new_value += '0' * (exp - number_exp)
            # Keep as floating point number for now...we take this out later.
            value = new_value + ".0"
        return value

    @timeit
    def load(self, filename):
        """Load mib values from a mib dump file.
        """
        max_counter32 = (2L ** 32 - 1)
        max_counter64 = (2L ** 64 - 1)
        # We want to provide a progress bar. Check total size of file
        size = os.path.getsize(filename)
        estimate_vars = size / self.bytes_per_line
        if estimate_vars == 0:
            estimate_vars = 1  # Avoid division by zero later
        vars_processed = 0.0
        start_time = time.time()
        f = open(filename, "rt")
        data_pattern = re.compile(r'^(\.?[.0-9]+)\s+(\S+)(\s+(\S+))?$')
        comment_pattern = re.compile(r'\s*#')
        float_pattern = re.compile(r'^\d+\.\d+$')
        lines = 0
        if self.verbose:
            sys.stdout.write("Loading: 0%")
            sys.stdout.flush()
        last_pct_printed = 0
        while 1:
            lines += 1
            line = f.readline()
            if not line:
                break
            # Skip comments
            if comment_pattern.search(line):
                continue
            line = line.rstrip()
            match = data_pattern.search(line)
            # Skip invalid lines
            if not match:
                continue
            (oid, _type, dummy, value) = match.groups()

            if oid[0] != '.':
                # format oid with prefix .
                oid = '.' + oid

            # Process type of the request
            if _type == 'Counter64' or _type == 'Counter':
                value = self._expand_if_exp(value)
                # If it's a float convert to int by truncating--TCL stores Counter64s as doubles.
                if float_pattern.search(value):
                    value = value.split('.')[0]

            elif _type == 'OID':
                # The smallest possible encode oid is .0.0. SnmpTool represents this as .0.
                if value == '.0':
                    value = '.0.0'

            if value is None:
                value = ""

            elif _type == 'OctetString':
                try:
                    value = self._convert_octet_string(value)
                except ValueError:
                    sys.exit("\n\nError converting Octet string [%s] on line %s. Exiting.\n" % (value, lines))

            elif _type == 'OID':
                if not self.oid_pattern.search(value):
                    # print "[Skipping invalid oid value %s (at oid %s)]" % (value, oid)
                    continue

            # Update progress bar if needed
            if self.verbose:
                vars_processed += 1
                current_pct_progress = int((vars_processed / estimate_vars) * 100)
                if current_pct_progress > last_pct_printed:
                    if self._print_progress(current_pct_progress, last_pct_printed):
                        last_pct_printed = current_pct_progress
            if oid in self.variable:
                # It's the second pass, get delta if counter
                if _type == 'Counter' or _type == 'Counter64':
                    # Store deltas for these types of variables during second pass
                    var = self.get(oid)
                    # Save start value
                    var.initialVal = var.value
                    # Calculate delta keeping wrap effect in mind
                    var.delta = long(value) - var.value
                    if var.delta < 0:
                        if _type == 'Counter':
                            max_value = max_counter32
                        else:
                            max_value = max_counter64
                        # Consider delta to be values needed to flip plus new value if the new val is smaller
                        var.delta = (max_value - var.value) + long(value)

                        # Finally, make delta smaller if it's too big
                        if var.delta * 2 >= max_value:
                            var.delta = number(max_value * 0.40)
                    continue
                else:
                    # Do nothing for others
                    continue

            exception = 0
            try:
                var = self._create_variable(oid, _type, value)
                self.insert_into_ds(var)
            except SnmplibInvalidData, data:
                sys.stderr.write("\nInvalid SNMP data encountered on line %s: %s\n" % (lines, data))
                exception = 1
            except (MibStoreInsertError, SnmpSimDumpError), data:
                exception_type = sys.exc_info()[0]
                sys.stderr.write("\nUnable to insert value for OID %s (line %s): %s: %s\n"
                                 % (oid, lines, exception_type, data))
                exception = 1

            if exception == 1:
                continue
            if oid == '.1.3.6.1.2.1.1.3.0':
                # sysUptime is a special case...handle it this way
                var.initialVal = var.value
                var.changeFunction = change_sysuptime
            else:
                # Otherwise, assign a change function if there's one defined for this type in CHANGE.
                # Use change_nothing if there isn't one.
                if _type in CHANGE:
                    var.changeFunction = CHANGE[_type]
                else:
                    var.changeFunction = change_nothing

        f.close()
        if self.verbose:
            # Make sure we've printed up to 99%, then add on 100%.
            self._print_progress(99, last_pct_printed)
            sys.stdout.write("100%\n")
        vars_loaded = len(self.oids)
        if vars_loaded == 0:
            sys.exit("No variables found in dump (zero loaded). Exiting.")
        else:
            # Reset time for deltas
            global SIM_START_TIME
            SIM_START_TIME = time.time()
            if self.verbose:
                stop_time = time.time()
                self._clear_screen()
                print "Loaded %s variables (%.1f seconds load time)." % (vars_loaded, stop_time - start_time)

    @staticmethod
    def _clear_screen():
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

    def _create_variable(self, oid, _type, value):
        """Function to instantiate the appropriate type of snmp variable object based on type. Also
           handles conversion of values so they match what the classes expect (strings converted to ints, etc)
        """
        if _type not in self.CLASS:
            raise "Unknown variable type %s encountered." % _type, SnmpSimDumpError
        var = self.CLASS[_type]()
        if _type == 'TimeTicks' or _type == 'Integer' or _type == 'Gauge' or _type == 'Counter' or _type == 'Counter64':
            value = long(value)
        if _type == 'TimeTicks':
            # Negative timeticks aren't valid but show up in dumps sometimes when
            # SnmpSim's ints overflow. Just use the absolute value.
            if value < 0:
                value = abs(value)
        var.setValue(value)
        var.oid = oid
        return var

    @staticmethod
    def _print_progress(current, last):
        """Print out progress in progress bar, up to 99%.
        """
        if current >= 100:
            return 0
        for i in range(last + 1, current + 1):
            # Print out X% if X is a multiple of 10
            if i % 10 == 0:
                sys.stdout.write("%s%%" % i)
            if ((i % 10) + 1) % 3 == 0:
                sys.stdout.write(".")
        sys.stdout.flush()
        return 1

    def insert_into_ds(self, var):
        """Method to insert a variable into the data store. The oid in the variable is used to specify
           where it should be stored.  Data is currently stored in a big dictionary of dictionaries.
        """
        oid = var.oid
        if oid is None:
            msg_err = "Variables must have their .oid attribute set to be inserted."
            raise MibStoreInsertError(msg_err)
        if not self.oid_pattern.search(oid):
            msg_err = "Bad OID value: %s" % oid
            raise MibStoreInsertError(msg_err)
        # Add variable to our data hash
        self.variable[oid] = var
        # Add oid to ordered list of all oids
        index_oid = self._binary_search(oid, exact=0)
        self.oids.insert(index_oid, oid)
        # Fill out .next attributes
        if index_oid + 1 <= (len(self.oids) - 1):
            # For this var, if there is a next variable
            var.next = self.oids[index_oid + 1]
        if index_oid != 0:
            # And for var before this one, if there is one.
            self.variable[self.oids[index_oid - 1]].next = oid

    def get(self, oid, change=0):
        if not self.oid_pattern.search(oid):
            msg_err = "Bad OID value: %s" % oid
            raise MibStoreGetError(msg_err)
        if oid not in self.variable:
            msg_err = "No such oid %s found." % oid
            raise MibStoreNoSuchNameError(msg_err)
        var = self.variable[oid]
        if change:
            try:
                # Make variable change itself if changeFunction exists
                var.changeFunction(var)
            except AttributeError:
                pass
        return var

    def get_next(self, oid, change=0):
        """Retrieve the next mib value from a given spot in the mib tree data. Raise an exception if there
           isn't a next oid or if the given oid doesn't exist in the data store.
        """
        if not self.oid_pattern.search(oid):
            msg_err = "Bad OID value: %s" % oid
            raise MibStoreNoSuchNameError(msg_err)
        # First, see if this oid is an exact oid that exists already. If so, use the .next attr
        # to return the appropriate var, changing it if change=1.
        if oid in self.variable:
            try:
                var = self.variable[oid].next
            except AttributeError:
                msg_err = "No next oid to retrieve for %s." % oid
                raise MibStoreNoSuchNameError(msg_err)
            if change:
                try:
                    # Make variable change itself if changeFunction exists
                    var.changeFunction(var)
                except AttributeError:
                    pass
            return self.variable[var]
        else:
            # Otherwise we need to look for the lexicographical successor of the partial oid given.
            # Do a binary search of the flat list of oids we have to determine the next oid, then
            # just return that.
            index_oid = self._binary_search(oid)
            length = len(self.oids)
            if index_oid is None or length == 0 or index_oid == length:
                msg_err = "No next oid to retrieve for %s." % oid
                raise MibStoreNoSuchNameError(msg_err)
            next_oid = self.oids[index_oid]
            var = self.get(next_oid, change)
            return var

    @staticmethod
    def _convert_octet_string(string):
        if string is None or string == "":
            return ""
        nums = string.split('-')
        return_string = ""
        for i in nums:
            return_string += chr(number(i))
        return return_string

    @staticmethod
    def _unconvert_octet_string(string):
        if string is None or string == "":
            return ""
        return '-'.join(map((lambda c: repr(ord(c))), string))

    def _binary_search(self, oid, exact=0):
        """exact = true:  Return the index of the variable containing the oid passed in, None if not present.
           exact = false: Return the index at which the oid would be inserted at into the list if it were present.
        """
        start = 0
        end = len(self.oids)
        while start < end:
            mid = (start + end) // 2
            #            if oid < self.oids[mid]:
            if self._compare_oids(oid, self.oids[mid]) == -1:
                end = mid
            else:
                start = mid + 1
        index_oid = start
        if not exact:
            # Inexact search
            return index_oid
        # Logic for exact search
        index_oid -= 1  # Back up one to exact match
        if self.oids[index_oid] == oid:
            return index_oid
        else:
            # print "index=%s, found oid %s != search oid %s" % (index, self.oids[index].oid, oid)
            return None

    @staticmethod
    def _compare_oids(oid1, oid2):
        if oid1 == oid2:
            return 0
        oid_split1 = oid1.split('.')
        oid_split2 = oid2.split('.')
        smaller = min(len(oid_split1), len(oid_split2))
        for i in xrange(smaller):
            if oid_split1[i] == oid_split2[i]:
                continue
            if oid_split1[i] > oid_split2[i]:
                return 1
            elif oid_split1[i] < oid_split2[i]:
                return -1


class SnmpSim(object):
    """SNMP simulator class. Uses MibDataStore class to store data.
    """

    # Load mib from specified file
    def __init__(self):
        self.verbose = 0
        self.data_store = MibDataStore()
        self.community = 'public'
        self.filename = ''
        self.snmpv1 = 1
        self.snmpv2 = 1
        self.port = 5000
        self.sock = None
        self.clientIp = None  # Assume serial/single threaded handling for now
        self.MAX_MESSAGE_SIZE = 8192

        # Options
        self.valid_ips = []  # If set, only respond to requests from IPs in this list

    def load(self, filename):
        """Load file into mib data store.
        """
        self.filename = filename
        self.data_store.load(filename)

    def set_verbose(self, enable_verbose):
        """Set verbose on/off (1/0). Function is used because we want to set it in the
           mib data store too.
        """
        self.verbose = enable_verbose
        self.data_store.verbose = enable_verbose

    def run(self):
        """Start the simulator (make it bind to a port and handle SNMP requests).
        """
        self.sock = socket.socket(socket.AF_INET,  # Internet
                                  socket.SOCK_DGRAM)  # UDP
        udp_ip = ''  # Accept connections from any IPv4 Address
        udp_port = self.port
        try:
            self.sock.bind((udp_ip, udp_port))
        except socket.error, data:
            sys.exit("Error binding to port %s: %s" % (self.port, data[1]))

        # version_snmp = ""
        if self.snmpv1 == 0 and self.snmpv2 == 0:
            msg_err = "You must specify at least one SNMP version mode."
            raise SnmpSimError(msg_err)
        if self.snmpv1 and self.snmpv2:
            version_snmp = "SNMPv1 and SNMPv2"
        else:
            # Must be only one or the other
            if self.snmpv1:
                version_snmp = "SNMPv1"
            else:
                version_snmp = "SNMPv2"
        if self.verbose:
            print "\nReady to respond to requests in %s mode on UDP port %s." % (version_snmp, self.port)
            if self.valid_ips:
                if len(self.valid_ips) == 1:
                    print "(Restricted to the IP address [%s].)" % self.valid_ips[0]
                else:
                    print "(Restricted to IP addresses [%s].)" % ', '.join(self.valid_ips)

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
            if self.valid_ips:
                if not self.clientIp[0] in self.valid_ips:
                    # Silently ignore requests that aren't from a specific IP, if user wanted this.
                    continue
            try:
                message = SnmpMessage(data)
            except:
                exception_type = sys.exc_info()[0]
                data = sys.exc_info()[1]
                sys.stderr.write("Unable to decode snmp message from %s: %s: %s\n" % \
                                 (self.clientIp[0], exception_type, data))
                continue

            if message.communityString.value != self.community:
                sys.stderr.write("Supplied community of %s doesn't match %s\n" % \
                                 (message.communityString.value, self.community))
                continue
            # request_type = message.pdu.type
            # Handle message. Return response to client.
            response_msg = None

            try:
                response_msg = self._process_message(message, self.clientIp[0])
            except:
                traceback.print_exc(file=sys.stdout)
            if response_msg is not None:
                encoded = response_msg.encode()
                if len(encoded) > self.MAX_MESSAGE_SIZE:
                    # Too big...for now just return a tooBig error (can get fancier later)
                    response_msg = SnmpMessage()
                    response_msg.version.setValue(message.version.value)
                    response_msg.pdu.type = 'GetResponse'
                    response_msg.pdu.errorStatus.setValue(1)  # tooBig
                    for var in message.pdu.varbind.items:
                        response_msg.pdu.varbind.items.append(var)
                    encoded = response_msg.encode()
                    if len(encoded) > self.MAX_MESSAGE_SIZE:
                        # If THIS is still too big (very unlikely) just drop packet.
                        continue
                try:
                    self.sock.sendto(encoded, self.clientIp)
                except:
                    traceback.print_exc(file=sys.stdout)

    def _process_message(self, msg, display_ip=None):
        """Process a message contained in a message object, and return the appropriate response
           (None object if there should be no response). Uses display_ip in messages if in verbose
           mode and an IP address is specified.
        """
        if len(msg.pdu.varbind.items) == 0:
            version_snmp = "v%s" % (msg.version.value + 1)
            if self.verbose:
                print "[Not responding to empty %s SNMP request (no oids in request).]" % version_snmp
            return None
        origin_vars = msg.pdu.varbind.items[:]
        ver = msg.version.value
        if ver == 0 and not self.snmpv1:
            if self.verbose:
                print "[Not responding to v1 request (set snmpv1 if you want to do this)"
            return None
        if ver == 1 and not self.snmpv2:
            if self.verbose:
                print "[Not responding to v2 request (set snmpv2 if you want to do this)"
            return None

        if ver + 1 == 1:
            # SNMPv1 request
            pdu_type = msg.pdu.type
            if pdu_type == "GetRequest":
                if self.verbose:
                    oid_string = ', '.join(map((lambda x: x.oid), msg.pdu.varbind.items))
                    if display_ip:
                        print "[%s: v%s GET request for %s]" % (display_ip, msg.version.value + 1, oid_string)
                    else:
                        print "[v%s GET request for %s]" % (msg.version.value + 1, oid_string)
                for i in range(0, len(msg.pdu.varbind.items)):
                    try:
                        msg.pdu.varbind.items[i] = self.data_store.get(msg.pdu.varbind.items[i].oid,
                                                                       change=random_mode)
                    except (MibStoreNotRetrievable, MibStoreNoSuchNameError):
                        if self.verbose:
                            print "  [noSuchName: %s]" % msg.pdu.varbind.items[i].oid
                        msg.pdu.varbind.items = origin_vars
                        msg.pdu.type = 'GetResponse'
                        msg.pdu.errorStatus.setValue(2)
                        msg.pdu.errorIndex.setValue(i + 1)
                        return msg

                msg.pdu.type = 'GetResponse'
                return msg
            elif pdu_type == 'GetNextRequest':
                if self.verbose:
                    oid_string = ', '.join(map((lambda x: x.oid), msg.pdu.varbind.items))
                    if display_ip:
                        print "[%s: v%s GETNEXT request for %s]" % (display_ip, msg.version.value + 1, oid_string)
                    else:
                        print "[v%s GETNEXT request for %s]" % (msg.version.value + 1, oid_string)
                for i in range(0, len(msg.pdu.varbind.items)):
                    try:
                        msg.pdu.varbind.items[i] = self.data_store.get_next(msg.pdu.varbind.items[i].oid,
                                                                            change=random_mode)
                    except MibStoreNoSuchNameError:
                        if self.verbose:
                            print "  [noSuchName: %s]" % msg.pdu.varbind.items[i].oid
                        msg.pdu.type = 'GetResponse'
                        msg.pdu.errorStatus.setValue(2)
                        msg.pdu.errorIndex.setValue(i + 1)
                        return msg
                msg.pdu.type = 'GetResponse'
                return msg
            else:
                raise "Unknown/unsupported request type: %s" % pdu_type, SnmpSimUnknownRequest
        elif ver + 1 == 2:
            # SNMPv2 request
            # Modify to get reports
            pdu_type = msg.pdu.type
            if pdu_type == "GetRequest":
                if self.verbose:
                    oid_string = ', '.join(map((lambda x: x.oid), msg.pdu.varbind.items))
                    if display_ip:
                        print "[%s: v%s GET request for %s]" % (display_ip, msg.version.value + 1, oid_string)
                    else:
                        print "[v%s GET request for %s]" % (msg.version.value + 1, oid_string)

                for i in range(0, len(msg.pdu.varbind.items)):
                    try:
                        msg.pdu.varbind.items[i] = self.data_store.get(msg.pdu.varbind.items[i].oid,
                                                                       change=random_mode)
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
            elif pdu_type == 'GetNextRequest':
                if self.verbose:
                    oid_string = ', '.join(map((lambda x: x.oid), msg.pdu.varbind.items))
                    if display_ip:
                        print "[%s: v%s GETNEXT request for %s]" % (display_ip, msg.version.value + 1, oid_string)
                    else:
                        print "[v%s GETNEXT request for %s]" % (msg.version.value + 1, oid_string)
                for i in range(0, len(msg.pdu.varbind.items)):
                    try:
                        msg.pdu.varbind.items[i] = self.data_store.get_next(msg.pdu.varbind.items[i].oid,
                                                                            change=random_mode)
                    except MibStoreNoSuchNameError:
                        # Do the v2 thing and just tag missing oids with SnmpEndOfMibView
                        oid = msg.pdu.varbind.items[i].oid
                        msg.pdu.varbind.items[i] = SnmpEndOfMibView()
                        msg.pdu.varbind.items[i].oid = oid
                        if self.verbose:
                            print "  [endOfMibView]"
                msg.pdu.type = 'GetResponse'
                return msg
            elif pdu_type == 'GetBulkRequest':
                if self.verbose:
                    oids = map((lambda x: x.oid), msg.pdu.varbind.items)
                    # oid_string = ', '.join(map((lambda x: x.oid), msg.pdu.varbind.items))
                    for i in range(0, msg.pdu.nonRepeaters.value):
                        oids[i] += "(NR)"
                    oid_string = ', '.join(oids)
                    if display_ip:
                        print "[%s: v%s GETBULK request for %s, nr=%s, mr=%s]" % \
                              (display_ip, msg.version.value + 1, oid_string,
                               msg.pdu.nonRepeaters.value,
                               msg.pdu.maxRepetitions.value)
                    else:
                        print "[v%s GETBULK request for %s]" % (msg.version.value + 1, oid_string)

                        # Get response msg set up properly
                response_msg = SnmpMessage()
                response_msg.version.setValue(1)  # v2
                response_msg.communityString.setValue(msg.communityString.value)
                response_msg.pdu.type = 'GetResponse'
                response_msg.pdu.requestId.setValue(msg.pdu.requestId.value)
                # A few shorthand vars for sanity below
                nr = msg.pdu.nonRepeaters.value
                mr = msg.pdu.maxRepetitions.value
                vb = msg.pdu.varbind
                response_varbind = response_msg.pdu.varbind
                if nr < 0:
                    nr = 0
                if mr < 0:
                    mr = 0

                if nr > 0:
                    # Do regular GETNEXTs on first N vars
                    for i in range(0, nr):
                        try:
                            # print "  [GETNEXT on %s (NON-REPEATER)]" % msg.pdu.varbind.items[i].oid
                            var = self.data_store.get_next(vb.items[i].oid, change=random_mode)
                        except MibStoreNoSuchNameError:
                            # Do the v2 thing and just tag missing oids with SnmpEndOfMibView
                            var = SnmpEndOfMibView()
                            var.oid = vb.items[i].oid
                            if self.verbose:
                                print "  [endOfMibView]"
                        # Add either the retrieved var or the EndOFMibView var
                        response_msg.pdu.varbind.items.append(var)

                # Loop through starting off after any nonRepeaters (index = 0, if there are none)
                remaining_oids = map((lambda x: vb.items[x].oid), range(nr, len(vb.items)))
                max_oids = len(remaining_oids) * mr
                current_oids = remaining_oids[:]
                tmp_oids = []
                while len(response_varbind.items) < max_oids and len(current_oids) != 0:
                    for oid in current_oids:
                        if len(response_varbind.items) >= max_oids:
                            # Catch any weirdo cases where one oid can't be retrieved anymore and throws cycle
                            # off the boundary
                            break
                        try:
                            var = self.data_store.get_next(oid, change=random_mode)
                            response_varbind.items.append(var)
                            tmp_oids.append(var.oid)
                        except MibStoreNoSuchNameError:
                            if self.verbose:
                                print "  [endOfMibView]"
                            var = SnmpEndOfMibView()
                            var.oid = oid
                            response_varbind.items.append(var)
                    current_oids = tmp_oids[:]  # Do getnexts on oids we got back
                    tmp_oids = []
                return response_msg
            else:
                raise SnmpSimUnknownRequest("Unknown/unsupported request type: %s") % pdu_type
        else:
            if self.verbose:
                print "[Not responding to v%s request.]" % (ver + 1)

    def _stop(self):
        if self.verbose:
            print "\nStopping simulator."
        sys.exit(0)


if __name__ == "__main__":
    usage = "Usage: snmpsim <options> -f <file>\n" + \
            " Options:\n" + \
            "  -f <file>  = file to use for SNMP data (SnmpSim dump file)\n" + \
            "  -p <port>  = Run simulator on this UDP port\n" + \
            "  -v1        = SNMPv1 enabled (on by default if nothing specified)\n" + \
            "  -v2c       = SNMPv2 enabled\n" + \
            "  -rd        = Random change OIDs value\n" + \
            "  -r         = Only response to the specific IP addresses\n"

    args = sys.argv[1:]
    if len(args) < 2:
        sys.exit(usage)
    if '-f' not in args:
        sys.exit(usage)
    port = 64001
    dump_file = ''
    snmpv1 = 0
    snmpv2 = 0
    verbose = 1
    random_mode = 0
    valid_ips = []
    index = 0
    file_info = 0
    for arg in args:
        index += 1
        if arg == '-v1':
            snmpv1 = 1
        elif arg == '-v2c':
            snmpv2 = 1
        elif arg == '-f' and not file_info:
            if index >= len(args):
                sys.exit(usage)
            dump_file = args[index]
            file_info = 1
        elif arg == '-p':
            if index >= len(args):
                sys.exit(usage)
            port = args[index]

    if dump_file == '':
        sys.exit(usage)
    if snmpv1 == 0 and snmpv2 == 0:
        # If neither mode was specified, default to v1
        snmpv1 = 1

    if not os.path.exists(dump_file) or not os.path.isfile(dump_file):
        sys.exit("%s doesn't exist or isn't a file. Exiting." % dump_file)
    sim = SnmpSim()

    sim.valid_ips = valid_ips
    sim.port = int(port)
    sim.snmpv1 = snmpv1
    sim.snmpv2 = snmpv2
    sim.set_verbose(verbose)
    sim.load(dump_file)

    mainLock = thread.allocate_lock()
    sim.run()
