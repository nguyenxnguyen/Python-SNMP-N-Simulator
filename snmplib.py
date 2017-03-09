#!/usr/bin/env python

import sys, exceptions, types, struct, re


#
# Exception classes
#
class SnmplibError(exceptions.Exception):
    """Main exception class for snmplib\n"""
    pass


class SnmplibInvalidData(SnmplibError):
    """Exception class used when invalid data is encountered."""
    pass


class SnmplibUnknownTag(SnmplibError):
    """Exception class used when an unknown tag is encountered."""
    pass


class SnmplibUnknownType(SnmplibError):
    """Exception class used when an unknown type is encountered."""
    pass


class SnmplibNotImplemented(SnmplibError):
    """Exception class used when something unimplemented is called/done."""
    pass


class SnmplibGeneralError(SnmplibError):
    """Exception class used in case of general errors."""
    pass


class SnmplibTypeMismatch(SnmplibError):
    """Exception class used when something is supposed to be decoded as one type and the data is in fact another."""
    pass


# SNMP datatype tag values
# ------------------------
#
#  Type               Class                    Constructed  Tag number  Complete tag value
#  ----               -----                    -----------  ----------  ------------------
#  INTEGER/Integer32  Universal/0x00/00             0       0x02/00010  0x02/00000010
#  OCTET STRING       Universal/0x00/00             0       0x04/00100  0x04/00000100
#  NULL               Universal/0x00/00             0       0x05/00101  0x05/00000101
#  noSuchObject       Context specific/0x0/10       0       0x00/00000  0x80/10000000
#  noSuchInstance     Context specific/0x0/10       0       0x01/00001  0x81/10000001
#  endOfMibView       Context specific/0x0/10       0       0x02/00010  0x82/10000010
#  OBJECT IDENTIFIER  Universal/0x00/00             0       0x06/00110  0x06/00000110
#  SEQUENCE           Universal/0x00/00             1       0x10/10000  0x30/00110000
#  IpAddress          Application/0x01/01           0       0x00/00000  0x40/01000000
#  Counter/Counter32  Application/0x01/01           0       0x01/00001  0x41/01000001
#  Gauge/Gauge32      Application/0x01/01           0       0x02/00010  0x42/01000010
#  Unsigned32         Application/0x01/01           0       0x02/00010  0x42/01000010
#  TimeTicks          Application/0x01/01           0       0x03/00011  0x43/01000011
#  Opaque             Application/0x01/01           0       0x04/00100  0x44/01000100
#  Counter64          Application/0x01/01           0       0x06/00110  0x46/01000110
#
# SNMP pdu type tag values
# ------------------------
#
# Type               Class                     Constructed  Tag number  Complete tag value
# ----               -----                     -----------  ----------  ------------------
# GetRequest         Context specific/0x02/10       1       0x00/00000  0xa0/10100000
# GetNextRequest     Context specific/0x02/10       1       0x01/00001  0xa1/10100001
# GetResponse        Context specific/0x02/10       1       0x02/00010  0xa2/10100010
# SetRequest         Context specific/0x02/10       1       0x03/00011  0xa3/10100011
# trap               Context specific/0x02/10       1       0x04/00100  0xa4/10100100
# getbulk-request    Context specific/0x02/10       1       0x05/00101  0xa5/10100101
# inform-request     Context specific/0x02/10       1       0x06/00110  0xa6/10100110
# v2-trap            Context specific/0x02/10       1       0x07/00111  0xa7/10100111
# v2-report          Context specific/0x02/10       1       0x08/01000  0xa7/10101000
TAG = {
    'Integer': 0x02,
    'Integer32': 0x02,
    'OctetString': 0x04,
    'Null': 0x05,
    'Oid': 0x06,
    'Sequence': 0x30,
    'IpAddress': 0x40,
    'Counter': 0x41,
    'Counter32': 0x41,
    'Gauge': 0x42,
    'Gauge32': 0x42,
    'Unsigned32': 0x42,
    'TimeTicks': 0x43,
    'Opaque': 0x44,
    # TODO: Decide if bits type should be in here    
    'Counter64': 0x46,
    # SNMP PDU types
    'GetRequest': 0xa0,
    'GetNextRequest': 0xa1,
    'GetResponse': 0xa2,
    'SetRequest': 0xa3,
    'Trap': 0xa4,
    'GetBulkRequest': 0xa5,
    'InformRequest': 0xa6,
    'V2Trap': 0xa7,
    'V2Report': 0xa8,
    'NoSuchObject': 0x80,
    'NoSuchInstance': 0x81,
    'EndOfMibView': 0x82
}

# Reverse mappings for tags above. Note that some things are indistinguishable from others...this
# table indicates which a given tag value resolves to.
TYPE = {
    0x02: 'Integer32',
    0x04: 'OctetString',
    0x05: 'Null',
    0x06: 'Oid',
    0x30: 'Sequence',
    0x40: 'IpAddress',
    0x41: 'Counter32',
    0x42: 'Unsigned32',
    0x43: 'TimeTicks',
    0x44: 'Opaque',
    # TODO: Decide if bits type should be in here
    0x46: 'Counter64',
    # SNMP PDUs
    0xa0: 'GetRequest',
    0xa1: 'GetNextRequest',
    0xa2: 'GetResponse',
    0xa3: 'SetRequest',
    0xa4: 'Trap',
    0xa5: 'GetBulkRequest',
    0xa6: 'InformRequest',
    0xa7: 'V2Trap',
    0xa8: 'V2Report',
    0x80: 'NoSuchObject',
    0x81: 'NoSuchInstance',
    0x82: 'EndOfMibView'
}

#
# Low level SNMP functions
#

oidRe = re.compile(r'^\.\d\.\d+(\.\d+)*$')


def encodeTag(name):
    """Return ASN.1 tag byte given snmplib tag string identifier ('Counter32', 'Unsigned32', etc).
    """
    if TAG.has_key(name):
        return '%c' % TAG[name]
    else:
        raise SnmplibUnknownType, "encodeTag(): Unknown type: %s" % name


def decodeTag(tag):
    """Return snmplib tag string identifier given ASN.1 encoded type byte..
    """
    tag = ord(tag)
    if TYPE.has_key(tag):
        return TYPE[tag]
    else:
        raise SnmplibUnknownType, "decodeTag(): Unknown tag: %02X" % tag


def decodeSequence(encoded):
    """Function to decode a sequence and return (_type, encodedPieces):
       _type         = 'Integer32', 'OctetString', etc
       encodedPieces = blobs of individual BER encoded contents of sequence
    """
    #  (_type, encodedPieces) = decodeSequence(encoded)
    (seqType, length, data, allData, remainder) = decode(encoded)
    # Operate on payload of sequence
    remainder = data
    blobs = []
    while len(remainder) != 0:
        (_type, length, data, allData, remainder) = decode(remainder)
        blobs.append(allData)
    return (seqType, blobs)


def encodeInteger32(integer):
    """Encode SNMP Integer32 data type (valid range is -2147483648 to 2147483647)
    """
    # TODO: Consider adding a flag to force full 4 byte value encoding even when
    #       wasteful (i.e. encoding 1 as 02 04 00 00 00 01). CMU-derived stuff
    #       may except this...have to see if anything dislikes this. Code to do this is:
    #  return encodeTag('Integer32') + encodeLength(4) + struct.pack(">i", integer)

    # TODO: Make this error checked better? Maybe catch OverFlowError if pack fails and
    #       raise appropriate snmplib error?
    encodedVal = struct.pack(">i", integer)
    #    while len(encodedVal) > 1 and ord(encodedVal[0]) == 0:
    #        encodedVal = encodedVal[1:]
    return encodeTag('Integer32') + encodeLength(len(encodedVal)) + encodedVal


def decodeInteger32(packet):
    """Decode SNMP Integer32 (valid range is -2147483648 to 2147483647)
    """
    # Make sure data types match
    if packet[0] != encodeTag('Integer32'):
        raise SnmplibTypeMismatch, "Attempted decoding of non-Integer32 as Integer32 (tag=%02x)." % ord(packet[0])

    # Decode length (get length of data, and size of length, so we can skip over it
    (length, sizeOfLength) = decodeLength(packet[1:])
    start = sizeOfLength + 1
    encodedInt = packet[start:start + length]

    if length > 4:
        raise SnmplibInvalidData, "Value is encoded with too many bytes to be a valid Integer32 (length=%s)." % length
    if length != 4:
        # We pad to 4 bytes so we can use struct.unpack() to do the work.
        if ord(encodedInt[0]) & 0x80:
            padByte = 0xff
        else:
            padByte = 0x00
        encodedInt = chr(padByte) * (4 - length) + encodedInt

    return struct.unpack(">i", encodedInt)[0]


def encodeUnsigned32(integer):
    """Encode SNMP Unsigned32 data type.
    """
    return _encodeUnsigned('Unsigned32', integer)


def decodeUnsigned32(packet):
    """Decode SNMP Unsigned32 data type.
    """
    # Make sure data types match
    if packet[0] != encodeTag('Unsigned32'):
        raise SnmplibTypeMismatch, "Attempted decoding of non-Unsigned32 as Unsigned32 (tag=%02x)." % ord(packet[0])
    return _decodeUnsigned(packet)


def encodeCounter32(integer):
    """Encode SNMP Counter32 data type.
    """
    return _encodeUnsigned('Counter32', integer)


def decodeCounter32(packet):
    """Decode SNMP Counter32 data type.
    """
    # Make sure data types match
    if packet[0] != encodeTag('Counter32'):
        raise SnmplibTypeMismatch, "Attempted decoding of non-Counter32 as Counter32 (tag=%02x)." % ord(packet[0])
    return _decodeUnsigned(packet)


def encodeCounter64(integer):
    """Encode SNMP Counter64 data type.
    """
    return _encodeUnsigned('Counter64', integer)


def decodeCounter64(packet):
    """Decode SNMP Counter64 data type.
    """
    # Make sure data types match
    if packet[0] != encodeTag('Counter64'):
        raise SnmplibTypeMismatch, "Attempted decoding of non-Counter64 as Counter64 (tag=%02x)." % ord(packet[0])
    return _decodeUnsigned(packet)


def encodeGauge32(integer):
    """Encode SNMP Gauge32 data type.
    """
    return _encodeUnsigned('Gauge32', integer)


def decodeGauge32(packet):
    """Decode SNMP Gauge32 data type.
    """
    # Make sure data types match
    if packet[0] != encodeTag('Gauge32'):
        raise SnmplibTypeMismatch, "Attempted decoding of non-Gauge32 as Gauge32 (tag=%02x)." % ord(packet[0])
    return _decodeUnsigned(packet)


def encodeTimeTicks(timeTicks):
    """Encode SNMP TimeTicks data type.
    """
    return _encodeUnsigned('TimeTicks', timeTicks)


def decodeTimeTicks(packet):
    """Decode SNMP TimeTicks data type.
    """
    # Make sure data types match
    if packet[0] != encodeTag('TimeTicks'):
        raise SnmplibTypeMismatch, "Attempted decoding of non-TimeTicks as TimeTicks (tag=%02x)." % ord(packet[0])
    return _decodeUnsigned(packet)


def decodeOctetString(packet):
    """Decode SNMP OCTET STRING data type.    
    """
    # Make sure data types match
    if packet[0] != encodeTag('OctetString'):
        raise SnmplibTypeMismatch, "Attempted decoding of non-OctetSTring as OctetString (tag=%02x)." % ord(packet[0])

    # Now unpack the length
    (length, size) = decodeLength(packet[1:])

    # Return the octets string
    return packet[size + 1:size + length + 1]


def decodeIpAddress(packet):
    """Decode SNMP IpAddress data type.
    """
    # Make sure data types match
    if packet[0] != encodeTag('IpAddress'):
        raise SnmplibTypeMismatch, "Attempted decoding of non-IpAddress as IpAddress (tag=%02x)." % ord(packet[0])

    # Get the value from the packet
    (type, length, data, allData, remainder) = decode(packet)
    ipaddr = data

    # Check it is valid
    if len(ipaddr) != 4:
        raise SnmplibInvalidData, 'Malformed IP address: %s' % ipaddr

    return '.'.join((map((lambda x: str(ord(x))), ipaddr)))


def encodeOid(oid):
    """Encode SNMP OBJECT IDENTIFIER data type.
    """
    if not oidRe.search(oid):
        raise SnmplibInvalidData, "Can't encode Invalid oid %s." % oid
    oids = map(number, oid.split('.')[1:])
    encoded = ''
    # Encode first two bytes into a single byte (required)
    first, second = oids[:2]
    encoded = encoded + chr(first * 40 + second)
    oids = oids[2:]
    for num in oids:
        if num <= 127:
            # Can encode suboid in a single byte
            encoded = encoded + chr(num)
        else:
            tmpEncoded = ''
            # Need to encode in multiple bytes
            firstLoop = 1
            while num > 127:
                val = num & 0x7f
                num = num >> 7
                if not firstLoop:
                    # Only set 8th bit for last byte (first one processed)                    
                    val = chr(val + 0x80)
                else:
                    val = chr(val)
                    firstLoop = 0
                tmpEncoded = val + tmpEncoded
            # Append final (first, really) byte. Have 8th bit set.
            tmpEncoded = chr(num + 0x80) + tmpEncoded
            encoded = encoded + tmpEncoded
    encoded = encodeTag('Oid') + encodeLength(len(encoded)) + encoded
    return encoded


def decodeOid(packet):
    """Decode SNMP OBJECT IDENTIFIER data type.    
    """
    (type, length, data, allData, remainder) = decode(packet)
    # Make sure data types match
    if type != 'Oid':
        raise SnmplibTypeMismatch, "Attempted decoding of non-Oid as Oid (type=%s)." % type

    # Store int values for each oid in this list
    values = []

    # Get first two oid values from first byte (encoded as first*40 + second)
    first = ord(data[0])
    values.append(int(first / 40))
    values.append(int(first % 40))

    data = data[1:]

    # First break data up into chunks of octets for each suboid
    chunks = []
    chunk = ""
    while len(data) != 0:
        octet = data[0]
        data = data[1:]
        if ord(octet) & 0x80:
            octet = chr(ord(octet) & 0x7f)
            chunk = chunk + octet
        else:
            chunk = chunk + octet
            # If 8th bit is not set it means no more octets follow for this suboid        
            chunks.append(chunk)
            chunk = ""

    # Loop over chunks and decode them, populating the values list
    # Get the rest of the values
    for chunk in chunks:
        if len(chunk) <= 3:
            val = 0
        else:
            # Use a long if we may need it--ints will act weird if the encoded suboid's too large.
            val = long(0)
        for c in chunk:
            val = val << 7
            val = val + ord(c)
        values.append(val)

    oidStr = '.'.join(map(str, values))
    return '.' + oidStr


def encodeBits(packets):
    """Encode SNMP BITS data type.
    """
    raise SnmplibNotImplemented, "SNMP BITS data type not implemented yet."


def decodeBits(packets):
    """Decode SNMP BITS data type.
    """
    raise SnmplibNotImplemented, "SNMP BITS data type not implemented yet."


def encodeOpaque(packets):
    """Encode SNMP opaque data type.
    """
    raise SnmplibNotImplemented, "SNMP OPAQUE data type not implemented yet."


def decodeOpaque(packets):
    """Decode SNMP opaque data type.
    """
    raise SnmplibNotImplemented, "SNMP OPAQUE data type not implemented yet."


def number(string):
    """Return either an int or a long using the string passed in. Do conversion
        on basis of whether val would be too big to store as a regular int.
    """
    try:
        return int(string)
    except (ValueError, OverflowError):
        # Unclear on why sometimes it's overflow vs value error, but this should work.
        return long(string)


#
# Classes for SNMP data types.
#
class SnmpDataType:
    """General SNMP datatype class. Abstract class--shouldn't actually be instantiated for anything. Classes that
       derive from this that actually get instantiated should at least implement the following methods (see doc
       strings below for what they should do):
           encode()
    """

    def __init__(self):
        """This method actually won't ever be used...it's more of a placeholder to show that type should exist in all
           subclasses, though this isn't enforced in Python.
        """
        self.type = None

    def encode(self):
        """This function does nothing in this class. When implemented in subclasses, it should encode the
           value using the appropriate encoding/tags, etc for whichever SNMP datatype the class is defining,
           and return this encoded value.
        """
        pass


class SnmpSequence(SnmpDataType):
    """General SNMP datatype class that all other types of sequences inherit from. Subclasses should override
       various methods as needed.
    """

    def __init__(self, encoded=None):
        """Initialize attributes and if a set of items are passed in, add them to the sequence after using the
           _checkItems() method to make sure they meet the appropriate criteria.
        """
        self.type = 'Sequence'
        self.items = []
        if encoded != None:
            objects = self._decode(encoded)
            self.add(objects)

    def add(self, items):
        """Add items to the sequence.
        """
        # If it's a list, add each thing.
        if type(items) == types.ListType or type(items) == types.TupleType:
            for item in items:
                #                if type(item) != types.InstanceType:
                if not isinstance(item, SnmpDataType):
                    print "item is [%s]" % item
                    raise SnmplibInvalidData, "Invalid item in sequence--items must all be SNMP datatype class " + \
                                              "instances of some type."
                self.items.append(item)
                # If it's just a single thing, just add it
            #        elif type(items) == types.InstanceType:
        elif isinstance(items, SnmpDataType):
            self.items.append(items)
        else:
            raise SnmplibInvalidData, "add(): Takes a single SNMP object or a list of SNMP objects."

    def encode(self):
        """Check that the items meet the appropriate criteria, encode them using their encode() methods,
           and encode the result as a sequence and return it.
        """
        self._checkItems(self.items)
        encoded = ''
        for item in self.items:
            encoded = encoded + item.encode()
        return encodeASequence(self.type, encoded)

    def _decode(self, encoded):
        _type = decodeTag(encoded[0])
        # TODO: Figure out how this check will work with subclasses that have different types (pdus)
        # if _type != 'Sequence':
        #    raise SnmplibInvalidData, "Can't create sequence from encoded non-sequence (type=%s)" % _type
        (_type, encodedPieces) = decodeSequence(encoded)
        objects = []
        for blob in encodedPieces:
            _type = decodeTag(blob[0])
            obj = DATA_TYPE_CLASS[_type](blob)
            objects.append(obj)
        self._checkItems(objects)
        return objects

    def _checkItems(self, items):
        # Check that we are being passed something that's likely to be an SNMP variable instance
        for item in items:
            #            if type(item) != types.InstanceType:
            if not isinstance(item, SnmpDataType):
                raise SnmplibInvalidData, "Sequences can only contain instances of SNMP datatypes."


class SnmpMessage(SnmpSequence):
    def __init__(self, encoded=None):
        #        print "[instantiating %s]" % self
        SnmpSequence.__init__(self, encoded)
        if not encoded:
            # Initialize items[0], items[1], and items[2] to be correct objects for an SNMP sequence
            self.version = SnmpInteger32()
            self.version.setValue(0)
            self.communityString = SnmpOctetString()
            self.communityString.setValue('public')
            self.pdu = SnmpV1Pdu()
            self.add((self.version, self.communityString, self.pdu))
        else:
            # Otherwise just need to associate things in .items to attributes
            self.version = self.items[0]
            self.communityString = self.items[1]
            self.pdu = self.items[2]

    def _checkItems(self, items):
        # TODO: Make these checks vary based on SNMP version?
        if len(items) != 3:
            raise SnmplibInvalidData, "Invalid number of items in sequence to encode as SNMP message."
        if items[0].type != 'Integer32':
            raise SnmplibInvalidData, "An SnmpInteger32 instance (the version) must be the first thing in an SNMP message."
        if items[1].type != 'OctetString':
            raise SnmplibInvalidData, "An SnmpOctetString instance (the community string) must be the second " + \
                                      "thing in an SNMP message."
        if items[2].type != 'GetRequest' and items[2].type != 'GetNextRequest' and items[2].type != 'GetResponse' \
                and items[2].type != 'SetRequest' and items[2].type != 'GetBulkRequest':
            raise SnmplibInvalidData, "An SnmpPdu instance (containing the Pdu) must be the third thing in an SNMP message."


class SnmpV1TrapPdu(SnmpSequence):
    def __init__(self, encoded=None):
        raise SnmplibNotImplemented, "SnmpV1TrapPdu support not yet implemented."


class SnmpV1Pdu(SnmpSequence):
    def __init__(self, encoded=None):
        if not encoded:
            SnmpSequence.__init__(self, encoded)
            self.type = 'GetRequest'
            self.requestId = SnmpInteger32()
            self.requestId.setValue(1)
            self.errorStatus = SnmpInteger32()
            self.errorStatus.setValue(0)
            self.errorIndex = SnmpInteger32()
            self.errorIndex.setValue(0)
            self.varbind = SnmpVarbind()
            self.add((self.requestId, self.errorStatus, self.errorIndex, self.varbind))
        else:
            # Grab varbind, since this has to be treated specially. Let everything else get decoded by SnmpSequence._decode()
            _type = decodeTag(encoded[0])
            if _type != 'GetRequest' and _type != 'GetNextRequest' and _type != 'GetResponse' and _type != 'SetRequest':
                raise SnmplibInvalidData, "Can't create sequence from encoded non-sequence (type=%s)" % _type
            (_type, pieces) = decodeSequence(encoded)
            if len(pieces) != 4:
                raise SnmplibInvalidData, "Incorrect number of variables for SNMPv1 PDU in sequence (%s)." % len(pieces)
            varbind = pieces[3]
            SnmpSequence.__init__(self, encoded)
            self.type = decodeTag(encoded[0])
            self.requestId = self.items[0]
            self.errorStatus = self.items[1]
            self.errorIndex = self.items[2]
            # Overwrite the value that was there...it won't be right since a varbind needs to be decoded different
            # than a sequence.
            self.items[3] = SnmpVarbind(varbind)
            self.varbind = self.items[3]

    def _checkItems(self, items):
        if len(items) != 4:
            raise SnmplibInvalidData, "Invalid number of items in sequence to encode or decode as SNMPv1 PDU."
        if items[0].type != 'Integer32':
            raise SnmplibInvalidData, "An SnmpInteger32 instance (the requestID) must be the first thing in an SNMPv1 PDU."
        if items[1].type != 'Integer32':
            raise SnmplibInvalidData, "An SnmpInteger32 instance (the errorStatus)must be the second thing in an SNMPv1 PDU."
        if items[2].type != 'Integer32':
            raise SnmplibInvalidData, "An SnmpInteger32 instance (the errorIndex) must be the third thing in an SNMPv1 PDU."
        if items[3].type != 'Sequence':
            raise SnmplibInvalidData, "An SnmpSequence instance (the varbind) must be the fourth thing in an SNMPv1 PDU."


class SnmpV2GetBulkPdu(SnmpSequence):
    def __init__(self, encoded=None):
        # type = GetBulkRequest
        # reqid = ...
        # nonRepeaters = ...
        # maxRepetitions = ...
        # varbind = ...
        if not encoded:
            SnmpSequence.__init__(self, encoded)
            self.type = 'GetBulkRequest'
            self.requestId = SnmpInteger32()
            self.requestId.setValue(1)
            self.nonRepeaters = SnmpInteger32()
            self.nonRepeaters.setValue(0)
            self.maxRepetitions = SnmpInteger32()
            self.maxRepetitions.setValue(0)
            self.varbind = SnmpVarbind()
            self.add((self.requestId, self.nonRepeaters, self.maxRepetitions, self.varbind))
        else:
            # Grab varbind, since this has to be treated specially. Let everything else get decoded by SnmpSequence._decode()
            _type = decodeTag(encoded[0])
            if _type != 'GetBulkRequest':
                raise SnmplibInvalidData, "Can't decode non-GetBulk PDU (%s) as a GetBulkRequest PDU.)" % _type
            (_type, pieces) = decodeSequence(encoded)
            if len(pieces) != 4:
                raise SnmplibInvalidData, "Incorrect number of variables for SNMPv2 GetBulk PDU in sequence (%s)." \
                                          % len(pieces)
            varbind = pieces[3]
            SnmpSequence.__init__(self, encoded)
            self.type = decodeTag(encoded[0])
            self.requestId = self.items[0]
            self.nonRepeaters = self.items[1]
            self.maxRepetitions = self.items[2]
            # Overwrite the value that was there...it won't be right since a varbind needs to be decoded different
            # than a sequence.
            self.items[3] = SnmpVarbind(varbind)
            self.varbind = self.items[3]

    def _checkItems(self, items):
        if len(items) != 4:
            raise SnmplibInvalidData, "Invalid number of items in sequence to encode or decode as SNMPv2 PDU."
        if items[0].type != 'Integer32':
            raise SnmplibInvalidData, "An SnmpInteger32 instance (the requestID) must be the first thing in an SNMPv2 PDU."
        if items[1].type != 'Integer32':
            raise SnmplibInvalidData, "An SnmpInteger32 instance (nonRepeaters) must be the second thing in an SNMPv2 PDU."
        if items[2].type != 'Integer32':
            raise SnmplibInvalidData, "An SnmpInteger32 instance (maxRepetitions) must be the third thing in an SNMPv2 PDU."
        if items[3].type != 'Sequence':
            raise SnmplibInvalidData, "An SnmpSequence instance (the varbind) must be the fourth thing in an SNMPv2 PDU."


class SnmpV2Pdu(SnmpSequence):
    def __init__(self, encoded=None):
        if not encoded:
            SnmpSequence.__init__(self, encoded)
            self.type = 'GetRequest'
            self.requestId = SnmpInteger32()
            self.requestId.setValue(1)
            self.errorStatus = SnmpInteger32()
            self.errorStatus.setValue(0)
            self.errorIndex = SnmpInteger32()
            self.errorIndex.setValue(0)
            self.varbind = SnmpVarbind()
            self.add((self.requestId, self.errorStatus, self.errorIndex, self.varbind))
        else:
            # Grab varbind, since this has to be treated specially. Let everything else get decoded by SnmpSequence._decode()
            # TODO: Add support for other v2 pdu types
            _type = decodeTag(encoded[0])
            if _type != 'GetRequest' and _type != 'GetNextRequest' and _type != 'GetResponse' and _type != 'SetRequest':
                raise SnmplibInvalidData, "Can't create sequence from encoded non-sequence (type=%s)" % _type
            (_type, pieces) = decodeSequence(encoded)
            if len(pieces) != 4:
                raise SnmplibInvalidData, "Incorrect number of variables for SNMPv2 PDU in sequence (%s)." % len(pieces)
            varbind = pieces[3]
            SnmpSequence.__init__(self, encoded)
            self.type = decodeTag(encoded[0])
            self.requestId = self.items[0]
            self.errorStatus = self.items[1]
            self.errorIndex = self.items[2]
            # Overwrite the value that was there...it won't be right since a varbind needs to be decoded different
            # than a sequence.
            self.items[3] = SnmpVarbind(varbind)
            self.varbind = self.items[3]

    def _checkItems(self, items):
        if len(items) != 4:
            raise SnmplibInvalidData, "Invalid number of items in sequence to encode or decode as SNMPv2 PDU."
        if items[0].type != 'Integer32':
            raise SnmplibInvalidData, "An SnmpInteger32 instance (the requestID) must be the first thing in an SNMPv2 PDU."
        if items[1].type != 'Integer32':
            raise SnmplibInvalidData, "An SnmpInteger32 instance (the errorStatus)must be the second thing in an SNMPv2 PDU."
        if items[2].type != 'Integer32':
            raise SnmplibInvalidData, "An SnmpInteger32 instance (the errorIndex) must be the third thing in an SNMPv2 PDU."
        if items[3].type != 'Sequence':
            raise SnmplibInvalidData, "An SnmpSequence instance (the varbind) must be the fourth thing in an SNMPv2 PDU."


class SnmpV2InformPdu(SnmpSequence):
    def __init__(self, encoded=None):
        raise SnmplibNotImplemented, "SnmpV2InformPdu support not yet implemented."


class SnmpV2TrapPdu(SnmpSequence):
    def __init__(self, encoded=None):
        raise SnmplibNotImplemented, "SnmpV2TrapPdu support not yet implemented."


class SnmpV2ReportPdu(SnmpSequence):
    def __init__(self, encoded=None):
        raise SnmplibNotImplemented, "SnmpV2ReportPdu support not yet implemented."


class SnmpVarbind(SnmpSequence):
    def _checkItems(self, items):
        if len(items) < 1:
            raise SnmplibInvalidData, "A varbind must have at least a single variable in it to be encoded."
        for item in items:
            #            if type(item) != types.InstanceType:
            if not isinstance(item, SnmpVariable):
                raise SnmplibInvalidData, "SNMP varbinds must contain only SNMP variable instances."
            if item.oid == None:
                raise SnmplibInvalidData, "All SNMP variables in a varbind must have oid values set."

    def _decode(self, encoded):
        _type = decodeTag(encoded[0])
        if _type != 'Sequence':
            raise SnmplibInvalidData, "Can't create varbind from encoded non-sequence (type=%s)" % type
        (_type, encodedPieces) = decodeSequence(encoded)
        objects = []
        for piece in encodedPieces:
            _type = decodeTag(piece[0])
            if _type != 'Sequence':
                raise SnmplibInvalidData, "Invalid data found in varbind (%s found in varbind instead of sequence)." % type

            (_type, innerChunks) = decodeSequence(piece)
            _type = decodeTag(innerChunks[0][0])
            if _type != 'Oid':
                raise SnmplibInvalidData, "Invalid data found in varbind (%s found in varbind instead of oid)." % type
            oid = decodeOid(innerChunks[0])
            var = createDataTypeObj(innerChunks[1])
            var.oid = oid
            objects.append(var)
        return objects

    def encode(self):
        self._checkItems(self.items)
        encoded = ''
        for item in self.items:
            encoded = encoded + encodeSequence(item.encodeOid() + item.encode())
        return encodeSequence(encoded)


class SnmpVariable(SnmpDataType):
    # TODO: Consider calling _checkValue() before encoding? Would avoid any weird slip ups.
    """General SnmpVariable class that defines behavior for SNMP variables. Subclasses should implement the
       following methods (see doc strings below for what they should do):
           _checkValue()
           _decode()
           encode()
    """

    def __init__(self, encoded=None):
        """Set various attributes to None, initially. If an encoded variable was passed in, decode it
           and use the value for this variable.
        """
        self.oid = None
        self.value = None
        self.type = None
        if encoded != None:
            self.setValue(self._decode(encoded))

    def setValue(self, value):
        self._checkValue(value)
        self.value = value

    def encodeOid(self):
        """This function encodes the oid associated with this variable. Because the way oids are encoded is the
           same regardless of the type of variable, this method is defined here.
        """
        if self.oid != None:
            return encodeOid(self.oid)
        else:
            raise SnmplibInvalidData, "No OID to encode (cannot encode empty OID)."

    def encode(self):
        """This function does nothing in this class. When implemented in subclasses, it should BER encode the
           value in .value and return the binary string representing the encoded form.
        """
        pass

    def _checkValue(self, value):
        """This function does nothing in this class. When implemented in subclasses, it should check
           that the type and value of the value passed in are valid for the particular SNMP datatype
           the class is defining. If anything is amiss, it should raise an SnmplibInvalidData exception.
        """
        pass

    def _decode(self, encoded):
        """This function does nothing in this class. When implemented in subclasses, it should decode
           an encoded variable of whichever SNMP datatype the class is defining and return it. If any
           errors are encountered it should raise an SnmplibInvalidData exception.
        """
        pass


class SnmpInteger32(SnmpVariable):
    def __init__(self, encoded=None):
        SnmpVariable.__init__(self, encoded)
        self.type = 'Integer32'

    def encode(self):
        self._checkValue(self.value)
        return encodeInteger32(self.value)

    def _checkValue(self, value):
        if type(value) != types.IntType and type(value) != types.LongType:
            raise SnmplibInvalidData, "Value passed in is invalid for an SNMP Integer variable."
        if value < -2147483648L:
            raise SnmplibInvalidData, "Value passed in (%s) is too small for an SNMP Integer variable." % value
        if value > 2147483647L:
            raise SnmplibInvalidData, "Value passed in (%s) is too large for an SNMP Integer variable." % value

    def _decode(self, encoded):
        return decodeInteger32(encoded)


class SnmpUnsigned32(SnmpVariable):
    def __init__(self, encoded=None):
        SnmpVariable.__init__(self, encoded)
        self.type = 'Unsigned32'

    def encode(self):
        self._checkValue(self.value)
        return encodeUnsigned32(self.value)

    def _checkValue(self, value):
        if type(value) != types.IntType and type(value) != types.LongType:
            raise SnmplibInvalidData, "Value passed in is invalid for an SNMP Unsigned32 variable."
        if value < 0:
            raise SnmplibInvalidData, "Value passed in (%s) is too small for an SNMP Unsigned32 variable." % value
        if value > 4294967295L:
            raise SnmplibInvalidData, "Value passed in (%s) is too large for an SNMP Unsigned32 variable." % value

    def _decode(self, encoded):
        return decodeUnsigned32(encoded)


class SnmpCounter32(SnmpVariable):
    def __init__(self, encoded=None):
        SnmpVariable.__init__(self, encoded)
        self.type = 'Counter32'

    def encode(self):
        self._checkValue(self.value)
        return encodeCounter32(self.value)

    def _checkValue(self, value):
        if type(value) != types.IntType and type(value) != types.LongType:
            raise SnmplibInvalidData, "Value passed in is invalid for an SNMP Counter32 variable."
        if value < 0:
            raise SnmplibInvalidData, "Value passed in (%s) is too small for an SNMP Counter32 variable." % value
        if value > 4294967295L:
            raise SnmplibInvalidData, "Value passed in (%s) is too large for an SNMP Counter32 variable." % value

    def _decode(self, encoded):
        return decodeCounter32(encoded)


class SnmpCounter64(SnmpVariable):
    def __init__(self, encoded=None):
        SnmpVariable.__init__(self, encoded)
        self.type = 'Counter64'

    def encode(self):
        self._checkValue(self.value)
        return encodeCounter64(self.value)

    def _checkValue(self, value):
        if type(value) != types.IntType and type(value) != types.LongType:
            raise SnmplibInvalidData, "Value passed in is invalid for an SNMP Counter64 variable."
        if value < 0:
            raise SnmplibInvalidData, "Value passed in (%s) is too small for an SNMP Counter64 variable." % value
        if value > 18446744073709551615L:
            raise SnmplibInvalidData, "Value passed in (%s) is too large for an SNMP Counter64 variable." % value

    def _decode(self, encoded):
        return decodeCounter64(encoded)


class SnmpGauge32(SnmpVariable):
    def __init__(self, encoded=None):
        SnmpVariable.__init__(self, encoded)
        self.type = 'Gauge32'

    def encode(self):
        self._checkValue(self.value)
        return encodeGauge32(self.value)

    def _checkValue(self, value):
        if type(value) != types.IntType and type(value) != types.LongType:
            raise SnmplibInvalidData, "Value passed in is invalid for an SNMP Gauge32 variable."
        if value < 0:
            raise SnmplibInvalidData, "Value passed in (%s) is too small for an SNMP Gauge32 variable." % value
        if value > 4294967295L:
            raise SnmplibInvalidData, "Value passed in (%s) is too large for an SNMP Gauge32 variable." % value

    def _decode(self, encoded):
        return decodeGauge32(encoded)


class SnmpTimeTicks(SnmpVariable):
    def __init__(self, encoded=None):
        SnmpVariable.__init__(self, encoded)
        self.type = 'TimeTicks'

    def encode(self):
        self._checkValue(self.value)
        return encodeTimeTicks(self.value)

    def _checkValue(self, value):
        if type(value) != types.IntType and type(value) != types.LongType:
            raise SnmplibInvalidData, "Value passed in is invalid for an SNMP TimeTicks variable."
        if value < 0:
            raise SnmplibInvalidData, "Value passed in (%s) is too small for an SNMP TimeTicks variable." % value
        if value > 4294967295L:
            raise SnmplibInvalidData, "Value passed in (%s) is too large for an SNMP TimeTicks variable." % value

    def _decode(self, encoded):
        return decodeTimeTicks(encoded)


class SnmpOctetString(SnmpVariable):
    def __init__(self, encoded=None):
        SnmpVariable.__init__(self, encoded)
        self.type = 'OctetString'

    def encode(self):
        self._checkValue(self.value)
        return encodeOctetString(self.value)

    def _checkValue(self, value):
        if type(value) != types.StringType:
            raise SnmplibInvalidData, "Value passed in is invalid for an SNMP OctetString variable."
        if len(value) > 65535:
            raise SnmplibInvalidData, "String passed in is too large (%s) for an SNMP OctetString variable." % len(
                value)

    def _decode(self, encoded):
        return decodeOctetString(encoded)


class SnmpIpAddress(SnmpVariable):
    def __init__(self, encoded=None):
        SnmpVariable.__init__(self, encoded)
        self.type = 'IpAddress'

    def encode(self):
        self._checkValue(self.value)
        return encodeIpAddress(self.value)

    def _checkValue(self, value):
        if type(value) != types.StringType:
            raise SnmplibInvalidData, "Value passed in is invalid for an SNMP IpAddress variable."
            # TODO: Consider putting regex check in here? Make it compiled elsewhere a single time?

    def _decode(self, encoded):
        return decodeIpAddress(encoded)


class SnmpOid(SnmpVariable):
    def __init__(self, encoded=None):
        SnmpVariable.__init__(self, encoded)
        self.type = 'Oid'

    def encode(self):
        self._checkValue(self.value)
        return encodeOid(self.value)

    def _checkValue(self, value):
        if type(value) != types.StringType:
            raise SnmplibInvalidData, "Value passed in is invalid for an SNMP Oid variable."
            # TODO: Consider putting regex check in here? Make it compiled elsewhere a single time?

    def _decode(self, encoded):
        return decodeOid(encoded)


class SnmpNull(SnmpVariable):
    def __init__(self, encoded=None):
        SnmpVariable.__init__(self, encoded)
        self.type = 'Null'

    def encode(self):
        return encodeNull()


class SnmpOpaque(SnmpVariable):
    def __init__(self, encoded=None):
        # Remove this exceptionif this is ever implemented...prevents class from ever being used.
        # This code has also not really been tested.
        raise SnmplibNotImplemented, "SNMP OPAQUE data type not implemented yet."
        SnmpVariable.__init__(self, encoded)
        self.type = 'Opaque'

    def encode(self):
        self._checkValue(self.value)
        return encodeOpaque(self.value)

    # Add _checkValue definition if ever implemented?

    def _decode(self, encoded):
        return decodeOpaque(encoded)


class SnmpNoSuchObject(SnmpVariable):
    def __init__(self, encoded=None):
        SnmpVariable.__init__(self, encoded)
        self.type = 'NoSuchObject'

    def encode(self):
        # Encode like a null but with correct tag.
        return encodeTag(self.type) + encodeLength(0)


class SnmpNoSuchInstance(SnmpVariable):
    def __init__(self, encoded=None):
        SnmpVariable.__init__(self, encoded)
        self.type = 'NoSuchInstance'

    def encode(self):
        # Encode like a null but with correct tag.        
        return encodeTag(self.type) + encodeLength(0)


class SnmpEndOfMibView(SnmpVariable):
    def __init__(self, encoded=None):
        SnmpVariable.__init__(self, encoded)
        self.type = 'EndOfMibView'

    def encode(self):
        # Encode like a null but with correct tag.        
        return encodeTag(self.type) + encodeLength(0)

    # TODO: decide if this should be uncommented.
    #   def setValue(self, param):
    #       raise SnmplibGeneralError, "Unable to set value for Null SNMP data type."

    def _checkValue(self, value):
        pass

    def _decode(self, encoded):
        return decodeNull(encoded)


# Data structure that maps type string to corresponding class.
DATA_TYPE_CLASS = {
    'Integer': SnmpInteger32,
    'Integer32': SnmpInteger32,
    'OctetString': SnmpOctetString,
    'Null': SnmpNull,
    'Oid': SnmpOid,
    'Sequence': SnmpSequence,
    'IpAddress': SnmpIpAddress,
    'Counter': SnmpCounter32,
    'Counter32': SnmpCounter32,
    'Gauge': SnmpGauge32,
    'Gauge32': SnmpGauge32,
    'Unsigned32': SnmpUnsigned32,
    'TimeTicks': SnmpTimeTicks,
    'Opaque': SnmpOpaque,
    'GetBulkRequest': SnmpV2GetBulkPdu,
    'Counter64': SnmpCounter64,
    'GetRequest': SnmpV1Pdu,
    'GetNextRequest': SnmpV1Pdu,
    'GetResponse': SnmpV1Pdu,
    'SetRequest': SnmpV1Pdu,
    'Trap': SnmpV1TrapPdu,
    'InformRequest': SnmpV2InformPdu,
    'V2Trap': SnmpV2TrapPdu,
    'V2Report': SnmpV2ReportPdu,
    'NoSuchObject': SnmpNoSuchObject,
    'NoSuchInstance': SnmpNoSuchInstance,
    'EndOfMibView': SnmpEndOfMibView
}


def createDataTypeObj(encoded):
    """Helper function to identify and decode a BER encoded blob, instantiating the appropriate
       SNMP object and returning it.
    """
    tag = decodeTag(encoded[0])
    obj = DATA_TYPE_CLASS[tag](encoded)
    return obj


def inspect(encoded):
    """Function to attempt to figure out what's in a given encoded blob and output info in a human-readable
       format.
    """
    type = encoded[0]
    print "Type:            %s (%s/%s)" % (decodeTag(type), ord(type), hex(ord(type)))
    length1 = ord(encoded[1])
    # If most significant (8th from left) bit is set then it's a multi-byte length encoding.
    # If not it's single byte.
    if length1 & 0x80:
        print "Length encoding: multi-byte (first byte = %s/%s)" % (length1, hex(length1))
    else:
        print "Length encoding: single byte (first byte = %s/%s)" % (length1, hex(length1))


def decode(encoded):
    """Function to decode an encoded SNMP blob and return (typeString, length, data, allData, remainder):
       typeString = 'Integer32', 'OctetString', etc
       length     = number of bytes in the encoded thing
       data       = actual encoded data, without type or length bytes
       allData    = actual encoded data, WITH type and length bytes. Only useful if you're trying to
                    decode a blob of several things (payload of a sequence).
       remainder  = rest of data, if any (you can call this on things that are packed together and get
                                          what's left after taking the next thing off handed back to you).
    """
    type = decodeTag(encoded[0])
    length1 = ord(encoded[1])

    if not length1 & 0x80:
        # Only one byte length.
        length = length1
        multibyte = 0
    else:
        # Multi-byte length. Need to get number of length bytes and decode that many to get length value.
        multibyte = 1
        lengthSize = length1 & 0x7f
        lengthData = encoded[2:lengthSize - 1]
        # TODO: Stick this in a loop instead of messing around like this.
        if lengthSize == 1:
            length = ord(encoded[2])
        if lengthSize == 2:
            length = ord(encoded[2])
            length = length << 8
            length = length | ord(encoded[3])
        if lengthSize == 3:
            length = ord(encoded[2])
            length = length << 8
            length = ord(encoded[3])
            length = length << 8
            length = length | ord(encoded[4])
        if lengthSize == 4:
            length = ord(encoded[2])
            length = length << 8
            length = ord(encoded[3])
            length = length << 8
            length = ord(encoded[4])
            length = length << 8
            length = length | ord(encoded[5])

    if not multibyte:
        data = encoded[2:length + 2]
        allData = encoded[:length + 2]
        remainder = encoded[length + 2:]
    else:
        data = encoded[2 + lengthSize:length + lengthSize + 2]
        allData = encoded[:length + 2 + lengthSize]
        remainder = encoded[length + 2 + lengthSize:]

    return (type, length, data, allData, remainder)


def inspectMsg(msg, banner="SNMP Message"):
    """Function to print out contents of an snmp message
    """
    print banner
    print "-" * len(banner)
    print "Version:          %s" % msg.version.value
    print "Community string: %s" % msg.communityString.value
    print "  PDU"
    print "  ---"
    if msg.pdu.type == 'GetBulkRequest':
        print "  PDU type:        %s" % msg.pdu.type
        print "  Request id:      %s" % msg.pdu.requestId.value
        print "  Nonrepeaters:    %s" % msg.pdu.nonRepeaters.value
        print "  Max repetitions: %s" % msg.pdu.maxRepetitions.value
    else:
        print "  PDU type:       %s" % msg.pdu.type
        print "  Request id:     %s" % msg.pdu.requestId.value
        print "  Error status:   %s" % msg.pdu.errorStatus.value
        print "  Error index:    %s" % msg.pdu.errorIndex.value
    print
    print "  Varbind"
    print "  -------"

    for i in range(0, len(msg.pdu.varbind.items)):
        var = msg.pdu.varbind.items[i]
        print "    var%s" % (i + 1)
        print "    ----"
        print "    OID:          %s" % var.oid
        print "    Type:         %s" % var.type
        print "    Value:        %s" % var.value
        print

    sys.stdout.flush()


def inspectMsgDump(msgDump, banner="SNMP Message"):
    """Function to print out contents of an snmp message given a hex ascii
       dump of it, like:
       '30 35 02 04 00 00 00 00 04 06 70 75 62 ...'
    """
    if not re.search(r'^[0-9a-f]{2} [0-9a-f]{2}( [0-9a-f]{2})+', msgDump, re.I):
        raise SnmplibInvalidData, "Invalid message dump string:\n%s" % msgDump
    data = ''
    for c in msgDump.split(' '):
        data = data + chr(int(c, 16))
    msg = SnmpMessage(data)
    print banner
    print "-" * len(banner)
    print "Version:          %s" % msg.version.value
    print "Community string: %s" % msg.communityString.value
    print "  PDU"
    print "  ---"
    print "  PDU type:       %s" % msg.pdu.type
    print "  Request id:     %s" % msg.pdu.requestId.value
    print "  Error status:   %s" % msg.pdu.errorStatus.value
    print "  Erorr index:    %s" % msg.pdu.errorIndex.value
    print "    Varbind"
    print "    -------"

    for i in range(0, len(msg.pdu.varbind.items)):
        var = msg.pdu.varbind.items[i]
        print "      var%s" % (i + 1)
        print "      ----"
        print "      OID:          %s" % var.oid
        print "      Type:         %s" % var.type
        print "      Value:        %s" % var.value
        print

    sys.stdout.flush()


def hexStr(binStr):
    str = ''
    for c in binStr:
        str = str + "%02X " % ord(c)
    return str


## class SnmpV1Session:
##     # LEFT OFF here
##     def __init__(self):
##         self.ipAddress = None
##         self.port = None



#    The functions below are derived from code in Ilya Etingof's (ilya@glas.net)
# PySNMP library (see http://sourceforge.net/projects/pysnmp for more info).
# Until this handful of functions are rewritten, here is the PySNMP license, as
# required by its licensing:
# -----------------------------------------------------------------------------
# Copyright (c) 1999, 2000, Ilya Etingof <ilya@glas.net>
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without modification,
# are permitted provided that the following conditions are met:
#
#   * Redistributions of source code must retain the above copyright notice, this
#     list of conditions and the following disclaimer.
#
#   * Redistributions in binary form must reproduce the above copyright notice, this
#     list of conditions and the following disclaimer in the documentation and/or
#     other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS ``AS IS'' AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED.
# IN NO EVENT SHALL THE REGENTS OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
# INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED
# TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR
# BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN
# ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF
# SUCH DAMAGE. 
# -----------------------------------------------------------------------------

def encodeLength(length):
    # If given length fits one byte
    if length < 0x80:
        # Pack it into one octet
        return '%c' % length
    # One extra byte required
    elif length < 0xFF:
        # Pack it into two octets
        return '%c%c' % (0x81, length)
    # Two extra bytes required
    elif length < 0xFFFF:
        # Pack it into three octets
        return '%c%c%c' % (0x82, \
                           (length >> 8) & 0xFF, \
                           length & 0xFF)
    # Three extra bytes required
    elif length < 0xFFFFFF:
        # Pack it into three octets
        return '%c%c%c%c' % (0x83, \
                             (length >> 16) & 0xFF, \
                             (length >> 8) & 0xFF, \
                             length & 0xFF)
    # More octets may be added
    else:
        raise SnmplibNotImplemented, 'Support for 4 or more length bytes is not yet implemented (bytes=%s).' % size


def decodeLength(packet):
    # Get the most-significant-bit
    msb = ord(packet[0]) & 0x80
    if not msb:
        return (ord(packet[0]) & 0x7F, 1)

    # Get the size if the length
    size = ord(packet[0]) & 0x7F

    # One extra byte length
    if msb and size == 1:
        return (ord(packet[1]), size + 1)

    # Two extra bytes length
    elif msb and size == 2:
        result = ord(packet[1])
        result = result << 8
        return (result | ord(packet[2]), size + 1)

    # Three extra bytes length
    elif msb and size == 3:
        result = ord(packet[1])
        result = result << 8
        result = result | ord(packet[2])
        result = result << 8
        return (result | ord(packet[3]), size + 1)

    else:
        raise SnmplibNotImplemented, 'Support for 4 or more length bytes is not yet implemented (bytes=%s).' % size


def encodeSequence(sequence):
    return encodeASequence('Sequence', sequence)


def encodeASequence(tag, sequence):
    # Make a local copy and add a leading empty item
    result = sequence

    # Return encoded packet
    return encodeTag(tag) + \
           encodeLength(len(result)) + \
           result


def _encodeUnsigned(tag, integer):
    """Encode unsigned integer (Counter32, Gauge32, TimeTicks, or Unsigned32 data types).
       Encoding using tag passed in (should be 'Counter32', 'Gauge32', 'TimeTicks', or 'Unsigned32').
    """
    # Initialize result
    result = ''

    # Make a local copy
    arg = integer

    # Pack the argument
    while 1:
        # Pack an octet
        result = '%c' % int(arg & 0xff) + result

        # Stop as everything got packed
        if arg >= -128 and arg < 128:
            return encodeTag(tag) + \
                   encodeLength(len(result)) + \
                   result

        # Move to the next octet
        arg = long(arg / 256)

    # Return error
    raise SnmplibInvalidData, "Invalid integer %s" % integer


def _decodeUnsigned(packet):
    """Decode unsigned integer (Counter32, Gauge32, TimeTicks, or Unsigned32 data types).
    """
    #    # Make sure data types match
    #    if packet[0] != encodeTag('Unsigned32'):
    #        raise SnmplibTypeMismatch, "Attempted decoding of non-Unsigned32 as Unsigned32 (tag=%02x)." % ord(packet[0])
    # Unpack the length
    (length, size) = decodeLength(packet[1:])

    # Setup an index on the data area
    index = size + 1

    # Get the first octet
    result = ord(packet[index])

    result = long(result)

    # Concatinate the rest
    while index < length + size:
        index = index + 1
        result = result * 256
        result = result + ord(packet[index])

    # Return result
    return result


def encodeOctetString(string):
    """Encode SNMP OCTET STRING data type.
    """
    return encodeTag('OctetString') + encodeLength(len(string)) + string


def encodeIpAddress(addr):
    """Encode SNMP IpAddress data type.    
    """
    # Assume address is given in dotted notation
    packed = addr.split('.')

    # TODO: Just do a single regex validation against ip addr? Be nicer to have a single check
    # instead of two.

    # Make sure it is four octets length
    if len(packed) != 4:
        raise SnmplibInvalidData, "Malformed IP address: " + str(addr)

        # Convert string octets into integer counterparts
    # (this is still not immune to octet overflow)
    try:
        packed = map(int, packed)
    except ValueError:
        raise SnmplibInvalidData, "Malformed IP address: " + str(addr)

    # Build a result
    result = '%c%c%c%c' % (packed[0], packed[1], \
                           packed[2], packed[3])

    # Return encoded result
    return encodeTag('IpAddress') + \
           encodeLength(len(packed)) + \
           result


def encodeNull():
    """Encode SNMP Null data type.
    """
    return encodeTag('Null') + encodeLength(0)


def decodeNull(packet):
    """Decode SNMP Null data type.
    """
    # Make sure data types match
    if packet[0] != encodeTag('Null') and \
                    packet[0] != encodeTag('EndOfMibView') and \
                    packet[0] != encodeTag('NoSuchInstance') and \
                    packet[0] != encodeTag('NoSuchObject'):
        raise SnmplibTypeMismatch, "Attempted decoding of non-Null as Null (tag=%02x)." % ord(packet[0])

    # TODO: Decide if this is silly. Would be nice to make sure it's encoded properly (is the length zero or what?
    #       Should check.)
    # Now unpack the length
    (length, size) = decodeLength(packet[1:])

    # Return None object
    return None


def encodeHexStr(str):
    """Create a binary string from a hex string of values separated by spaces
       (i.e. "02 03 04" would encoded to "\x02\x02\x03").
    """
    encoded = ''
    for c in str.split(' '):
        encoded = encoded + chr(int(c, 16))
    return encoded
