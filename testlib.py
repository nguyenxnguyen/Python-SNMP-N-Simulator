#!/usr/bin/env python

# TODO: Consider importing * from snmplib so everything doesn't have to be fully qualified?

import sys, unittest
import snmplib

class TestSnmpLib(unittest.TestCase):
    """Test that various low level things work forward and backwards--that decoding an snmp message
       and encoding it again results in the same thing, for instance.
    """
    verbose = 0

    # Things that need to work for other stuff to work (want to see these errors first)
    def testMultiByteDecoding(self):
        """Multibyte decoding in decode() works.
        """
        multiByteSeq = ''.join(map(chr, (0x30, 0x82, 0x00, 0x06, 0x02, 0x01, 0x01, 0x02, 0x01, 0x02)))
        realType = 'Sequence'
        realLength = 6
        realData = ''.join(map(chr, (0x02, 0x01, 0x01, 0x02, 0x01, 0x02)))
        realAllData = multiByteSeq
        realRemainder = ''
        (type, length, data, allData, remainder) = snmplib.decode(multiByteSeq)
        self.assertEqual(realType, type)
        self.assertEqual(realLength, length, "Multibyte decoding fouled up (length value wrong)")
        self.assertEqual(realData, data, "Multibyte decoding fouled up (data value wrong).")
        self.assertEqual(realAllData, allData, "Multibyte decoding fouled up (allData value wrong).")
        self.assertEqual(realRemainder, remainder, "Multibyte decoding fouled up (remainder value wrong).") 

    def testSingleByteDecoding(self):
        """Single byte decoding in decode() works.
        """
        singleByteSeq = ''.join(map(chr, (0x02, 0x01, 0x02)))
        realType = 'Integer32'
        realLength = 1
        realData = chr(0x02)
        realAllData = singleByteSeq
        realRemainder = ''
        (type, length, data, allData, remainder) = snmplib.decode(singleByteSeq)
        self.assertEqual(realType, type)
        self.assertEqual(realLength, length, "Single byte decoding fouled up (length value wrong)")
        self.assertEqual(realData, data, "Single byte decoding fouled up (data value wrong).")
        self.assertEqual(realAllData, allData, "Single byte decoding fouled up (allData value wrong).")
        self.assertEqual(realRemainder, remainder, "Single byte decoding fouled up (remainder value wrong).") 
    

    #
    # Low level function tests
    #
    def testEncodeInteger32(self):
        """SNMP Integer32 types encode and decode to the same thing.
        """
        ints = [-2147483648L, -1000, -1, 0 , 1, 131, 1000, 8388608, 2147483647]
        for int in ints:
            if self.verbose == 1:
                print "[%s]" % int
            encoded = snmplib.encodeInteger32(int)
            self.assertEqual(int, snmplib.decodeInteger32(encoded))


    def testEncodeUnsigned32(self):
        """SNMP Unsigned32 types encode and decode to the same thing.
        """
        ints = [0 , 1, 932, 1000003, 2147483647L, 4294967295L]
        for int in ints:
            if self.verbose == 1:
                print "[%s] " % int
            encoded = snmplib.encodeUnsigned32(int)
            self.assertEqual(int, snmplib.decodeUnsigned32(encoded))


    def testEncodeCounter32(self):
        """SNMP Counter32 types encode and decode to the same thing.
        """
        ints = [0 , 1, 932, 1000003, 2147483647L, 4294967295L]
        for int in ints:
            if self.verbose == 1:
                print "[%s] " % int
            encoded = snmplib.encodeCounter32(int)
            self.assertEqual(int, snmplib.decodeCounter32(encoded))

            
    def testEncodeCounter64(self):
        """SNMP Counter64 types encode and decode to the same thing.
        """
        ints = [0 , 1, 932, 1000003, 2147483647L, 4294967295L, 1000000000L, 18446744073709551615L]
        for int in ints:
            if self.verbose == 1:
                print "[%s] " % int
            encoded = snmplib.encodeCounter64(int)
            self.assertEqual(int, snmplib.decodeCounter64(encoded))


    def testEncodeGauge32(self):
        """SNMP Gauge32 types encode and decode to the same thing.
        """        
        ints = [0 , 1, 932, 1000003, 2147483647L, 4294967295L]
        for int in ints:
            if self.verbose == 1:
                print "[%s] " % int
            encoded = snmplib.encodeGauge32(int)
            self.assertEqual(int, snmplib.decodeGauge32(encoded))            


    def testEncodeTimeticks(self):
        """SNMP TimeTicks types encode and decode to the same thing.
        """
        ints = [0 , 1, 932, 1000003, 2147483647L, 4294967295L]
        for int in ints:
            if self.verbose == 1:
                print "[%s] " % int
            encoded = snmplib.encodeTimeTicks(int)
            self.assertEqual(int, snmplib.decodeTimeTicks(encoded))

            
    def testEncodeOctetString(self):
        """SNMP OCTET STRING types encode and decode to the same thing.
        """
        # Pick some interesting strings to test...small, large, binary, etc.
        strings = ['abc', 'This is a test', 'a' * 65535, ''.join(map(chr, [0x00, 0xff, 0x41, 0xa0]*3)) ]
        for string in strings:
            encoded = snmplib.encodeOctetString(string)
            self.assertEqual(string, snmplib.decodeOctetString(encoded))


    def testEncodeIpAddress(self):
        """SNMP IpAddress types encode and decode to the same thing.
        """
        ips = ['0.0.0.0', '127.0.0.1', '255.255.255.255']
        for ip in ips:
            encoded = snmplib.encodeIpAddress(ip)
            self.assertEqual(ip, snmplib.decodeIpAddress(encoded))


    def testEncodeOid(self):
        """SNMP OBJECT IDENTIFIER types encode and decode to the same thing.
        """
        oids = ['.1.3',
                '.1.3.6.1.2.1.1.1.0',
                '.1.3.6.1.4.1.9.9.147.1.2.1.1.1.2.6',
                '.1.3.6.1.4.1.9' + ('.1' * 120),
                '.1.3.6.1.4.1.4294967295.1']
        for oid in oids:
            encoded = snmplib.encodeOid(oid)
            self.assertEqual(oid, snmplib.decodeOid(encoded))


    def testEncodeNull(self):
        """SNMP OBJECT NULL type encodes and decodes to the same thing.
        """
        encoded = snmplib.encodeNull()
        self.assertEqual(None, snmplib.decodeNull(encoded))

    # BITS data encoding test would go here, if the library supported it.
    
    # Opaque data encoding test would go here, if the library supported it.

    def testEncodeSequence(self):
        """SNMP sequence type encodes and decodes to the same thing.
        """
        c1 = snmplib.encodeCounter32(23112)
        c2 = snmplib.encodeCounter32(1541)
        encodedSeq = snmplib.encodeSequence(c1 + c2)
        (_type, blobs) = snmplib.decodeSequence(encodedSeq)
        self.assertEqual(_type, 'Sequence')
        self.assertEqual(blobs[0], c1)
        self.assertEqual(blobs[1], c2)


    #
    # Class level tests
    #

    # TODO: Add in doc strings for these.
    def testSnmpInteger32(self):
        vals = [-2147483648L, -1000, -1, 0 , 1, 1000, 2147483647L]
        for val in vals:
            encoded = snmplib.encodeInteger32(val)
            i = snmplib.createDataTypeObj(encoded)
            self.assertEqual('Integer32', i.type)
            self.assertEqual(val, i.value)


    def testSnmpUnsigned32(self):
        vals = [0, 43, 2001, 4294967295L]
        for val in vals:
            encoded = snmplib.encodeUnsigned32(val)
            c = snmplib.createDataTypeObj(encoded)
            self.assertEqual('Unsigned32', c.type)
            self.assertEqual(val, c.value)         

            
    def testSnmpCounter32(self):
        vals = [0, 43, 2001, 4294967295L]
        for val in vals:
            encoded = snmplib.encodeCounter32(val)
            c = snmplib.createDataTypeObj(encoded)
            self.assertEqual('Counter32', c.type)
            self.assertEqual(val, c.value)

    def testSnmpCounter64(self):
        vals = [0, 43, 2001, 4294967295L, 1000000000L, 18446744073709551615L]
        for val in vals:
            encoded = snmplib.encodeCounter64(val)
            c = snmplib.SnmpCounter64(encoded)
            self.assertEqual('Counter64', c.type)
            self.assertEqual(val, c.value)            

    def testSnmpGauge32(self):
        vals = [0, 43, 2001, 4294967295L]
        for val in vals:
            encoded = snmplib.encodeGauge32(val)
            g = snmplib.createDataTypeObj(encoded)
            self.assertEqual('Unsigned32', g.type)
            self.assertEqual(val, g.value)

    def testSnmpTimeTicks(self):
        vals = [0, 43, 2001, 4294967295L]
        for val in vals:
            encoded = snmplib.encodeTimeTicks(val)
            t = snmplib.createDataTypeObj(encoded)
            self.assertEqual('TimeTicks', t.type)
            self.assertEqual(val, t.value)


    def testSnmpOctetString(self):
        vals = ['abc', 'This is a test', 'a' * 65535, ''.join(map(chr, [0x00, 0xff, 0x41, 0xa0]*3)) ]
        for val in vals:
            encoded = snmplib.encodeOctetString(val)
            s = snmplib.createDataTypeObj(encoded)
            self.assertEqual('OctetString', s.type)
            self.assertEqual(val, s.value)
            

    def testSnmpIpAddress(self):
        ips = ['0.0.0.0', '127.0.0.1', '255.255.255.255']        
        for ip in ips:
            encoded = snmplib.encodeIpAddress(ip)
            s = snmplib.createDataTypeObj(encoded)
            self.assertEqual('IpAddress', s.type)
            self.assertEqual(ip, s.value)

            
    def testSnmpOid(self):
        oids = ['.1.3', '.1.3.6.1.2.1.1.1.0', '.1.3.6.1.4.1.9' + ('.1' * 120)]        
        for oid in oids:
            encoded = snmplib.encodeOid(oid)
            s = snmplib.createDataTypeObj(encoded)
            self.assertEqual('Oid', s.type)
            self.assertEqual(oid, s.value)


    def testSnmpNull(self):
        encoded = snmplib.encodeNull()
        s = snmplib.createDataTypeObj(encoded)
        self.assertEqual('Null', s.type)
        self.assertEqual(None, s.value)

    def testSnmpSequence(self):
        # Test automated decoding of encoded sequence passed when object is instantiated
        c = snmplib.SnmpCounter32()
        c.setValue(1000)
        u = snmplib.SnmpUnsigned32()
        u.setValue(3202)
        o = snmplib.SnmpOid()
        o.setValue('.1.3.6.1.2.1.1.1.0')
        s = snmplib.SnmpOctetString()
        s.setValue('this is a string')
        encodedSeq = snmplib.encodeSequence(c.encode() + u.encode() + o.encode() + s.encode())
        seq = snmplib.SnmpSequence(encodedSeq)
        self.assertEqual(len(seq.items), 4, "Different number of items in sequence than inserted.")
        self.assertEqual(seq.items[0].type, 'Counter32')
        self.assertEqual(seq.items[1].type, 'Unsigned32')
        self.assertEqual(seq.items[2].type, 'Oid')
        self.assertEqual(seq.items[3].type, 'OctetString')                
        self.assertEqual(encodedSeq, seq.encode(), "Initially encoded sequence vs .encode() encoded sequence " + \
                         "are different:\nBefore: %s\nAfter:  %s\n" % (encodedSeq, seq.encode()))

        # Test that .add() works right
        ip = snmplib.SnmpIpAddress()
        ip.setValue('127.0.0.1')
        seq2 = snmplib.SnmpSequence()
        seq2.add(ip)
        i1 = snmplib.SnmpInteger32()
        i1.setValue(40000)
        i2 = snmplib.SnmpInteger32()
        i2.setValue(80000)
        seq2.add([i1, i2])
        self.assertEqual(seq2.items[0], ip)
        self.assertEqual(seq2.items[1], i1)
        self.assertEqual(seq2.items[2], i2)                

    def testSnmpVarbind(self):
        i = snmplib.SnmpInteger32()
        s = snmplib.SnmpOctetString()
        i.setValue(4223)
        i.oid = '.1.3.6.1.4.1.9.1.0'
        s.setValue('Simulators rock!')
        s.oid = '.1.3.6.1.4.1.9.2.0'
        encoded = snmplib.encodeSequence( snmplib.encodeSequence(i.encodeOid() + i.encode()) + \
                                         snmplib.encodeSequence(s.encodeOid() + s.encode()))
        vb = snmplib.SnmpVarbind(encoded)
        self.assertEqual(vb.type, 'Sequence')
        self.assertEqual(vb.items[0].type, 'Integer32')
        self.assertEqual(vb.items[1].type, 'OctetString')
        self.assertEqual(vb.items[0].value, 4223)
        self.assertEqual(vb.items[1].value, 'Simulators rock!')
        self.assertEqual(vb.encode(), encoded)

    def testSnmpV1Pdu(self):
        reqId = snmplib.SnmpInteger32()
        reqId.setValue(1)
        errStatus = snmplib.SnmpInteger32()
        errStatus.setValue(0)
        errIndex = snmplib.SnmpInteger32()
        errIndex.setValue(0)
        vb = snmplib.SnmpVarbind()
        i = snmplib.SnmpInteger32()
        i.setValue(30)
        i.oid = '.1.3.6.1.2.1.1.2.0'
        vb.add(i)
        encodedPdu = snmplib.encodeASequence('GetRequest', reqId.encode() + errStatus.encode() + errIndex.encode() + \
                                     vb.encode())
        pdu = snmplib.SnmpV1Pdu(encodedPdu)
        self.assertEqual(pdu.type, 'GetRequest')
        self.assertEqual(pdu.requestId.value, reqId.value)
        self.assertEqual(pdu.errorStatus.value, errStatus.value)
        self.assertEqual(pdu.errorIndex.value, errIndex.value)
        self.assertEqual(pdu.varbind.items[0].value, i.value)
        self.assertEqual(pdu.varbind.items[0].oid, i.oid)
        self.assertEqual(pdu.encode(), encodedPdu)        


    def testSnmpV2Pdu(self):
        reqId = snmplib.SnmpInteger32()
        reqId.setValue(1)
        errStatus = snmplib.SnmpInteger32()
        errStatus.setValue(0)
        errIndex = snmplib.SnmpInteger32()
        errIndex.setValue(0)
        vb = snmplib.SnmpVarbind()
        i = snmplib.SnmpInteger32()
        i.setValue(30)
        i.oid = '.1.3.6.1.2.1.1.2.0'
        vb.add(i)
        encodedPdu = snmplib.encodeASequence('GetRequest', reqId.encode() + errStatus.encode() + errIndex.encode() + \
                                     vb.encode())
        pdu = snmplib.SnmpV2Pdu(encodedPdu)
        self.assertEqual(pdu.type, 'GetRequest')
        self.assertEqual(pdu.requestId.value, reqId.value)
        self.assertEqual(pdu.errorStatus.value, errStatus.value)
        self.assertEqual(pdu.errorIndex.value, errIndex.value)
        self.assertEqual(pdu.varbind.items[0].value, i.value)
        self.assertEqual(pdu.varbind.items[0].oid, i.oid)
        self.assertEqual(pdu.encode(), encodedPdu)


    def testSnmpV2GetBulkPdu(self):
        """Test that basic encoding/decoding of an SNMPv2 GetBulk pdu seems to work ok.
        """
        reqId = snmplib.SnmpInteger32()
        reqId.setValue(1)
        nonRepeaters = snmplib.SnmpInteger32()
        nonRepeaters.setValue(0)
        maxRepetitions = snmplib.SnmpInteger32()
        maxRepetitions.setValue(0)
        vb = snmplib.SnmpVarbind()
        i = snmplib.SnmpInteger32()
        i.setValue(30)
        i.oid = '.1.3.6.1.2.1.1.2.0'
        vb.add(i)
        encodedPdu = snmplib.encodeASequence('GetBulkRequest', reqId.encode() + nonRepeaters.encode() + \
                                             maxRepetitions.encode() + vb.encode())
        pdu = snmplib.SnmpV2GetBulkPdu(encodedPdu)
        self.assertEqual(pdu.type, 'GetBulkRequest')
        self.assertEqual(pdu.requestId.value, reqId.value)
        self.assertEqual(pdu.nonRepeaters.value, nonRepeaters.value)
        self.assertEqual(pdu.maxRepetitions.value, maxRepetitions.value)
        self.assertEqual(pdu.varbind.items[0].value, i.value)
        self.assertEqual(pdu.varbind.items[0].oid, i.oid)
        self.assertEqual(pdu.encode(), encodedPdu, "Reencoded SNMPv2 GetBulk PDU didn't match original.")
        

    def testSnmpMessage(self):
        ver = snmplib.SnmpInteger32()
        ver.setValue(0)
        cs = snmplib.SnmpOctetString()
        cs.setValue('public')
        pdu = snmplib.SnmpV1Pdu()
        i = snmplib.SnmpInteger32()
        i.setValue(43)
        i.oid = '.1.3.6.1.2.1'
        pdu.varbind.add(i)
        encodedMsg = snmplib.encodeSequence(ver.encode() + cs.encode() + pdu.encode())
        msg = snmplib.SnmpMessage(encodedMsg)
        self.assertEqual(msg.version.value, 0)
        self.assertEqual(msg.communityString.value, 'public')
        self.assertEqual(msg.pdu.varbind.items[0].oid, '.1.3.6.1.2.1')
        self.assertEqual(msg.pdu.varbind.items[0].value, 43)        
        


        
    #
    # Other random things that should be true
    #
    def testTypesAndClassMappingsSame(self):
        """Types defined in TAG and those there are mappings for in DATA_TYPE_CLASS dict are identical.
        """
        for tag in snmplib.TAG.keys():
            self.assert_(snmplib.DATA_TYPE_CLASS.has_key(tag), "DATA_TYPE_CLASS doesn't have %s but TAG does." % tag)
            
        for tag in snmplib.DATA_TYPE_CLASS.keys():
            self.assert_(snmplib.TAG.has_key(tag), "TAG doesn't have %s but DATA_TYPE_CLASS does." % tag)

    def testTypesDictsConsistent(self):
        """Types defined in TAG and TYPE dictionaries are consistent (they map to each other).
        """
        TAG = snmplib.TAG
        TYPE = snmplib.TYPE

        for tagNum in TYPE.keys():
            self.assert_(TAG.has_key(TYPE[tagNum]), "No mapping for %s in TAG dictionary." % tagNum)
            
        for tag in TAG.keys():
            self.assert_(TYPE.has_key(TAG[tag]), "No reverse mapping for %s in TYPE dictionary." % tag)


    #
    # Things that have been problems in the past
    #
    def testTwoStringSeqOk(self):
        str1 = snmplib.SnmpOctetString()
        str1.setValue('blah')
        str2 = snmplib.SnmpOctetString()
        str2.setValue('etc')
        tmp = snmplib.encodeSequence(str1.encode() + str2.encode())
        pdu = snmplib.SnmpSequence(tmp)
        self.assertEqual(len(pdu.items), 2, "Weird problem where there was only a single octet string in this sequence.")


    def testNullTypesDecode(self):
        """Test that v2 implicit null types decode--had problems with this with endOfMibView.
        """
        # test endOfMibView
        exception = None
        try:
            error = snmplib.SnmpEndOfMibView()
            error._decode(error.encode())
        except:
            exception = sys.exc_info()[0]
        self.assertEqual(exception, None, "Error decoding endOfMibView type (exception=%s)" % exception)

        # test noSuchInstance
        exception = None
        try:
            error = snmplib.SnmpNoSuchInstance()
            error._decode(error.encode())
        except:
            exception = sys.exc_info()[0]
        self.assertEqual(exception, None, "Error decoding noSuchInstance type (exception=%s)" % exception)

        # test noSuchObject
        exception = None
        try:
            error = snmplib.SnmpNoSuchObject()
            error._decode(error.encode())
        except:
            exception = sys.exc_info()[0]
        self.assertEqual(exception, None, "Error decoding noSuchObject type (exception=%s)" % exception)        

##     def testIntEncodingLengthsMinimal(self):
##         """Test that encoding of integer values only uses minimum number of
##            bytes needed and no more. Noticed we were encoding things like:
##            02 04 00 00 00 01 instead of 02 01 01 at one point.
##         """    
##         #        Number     Encoded bytes expected
##         data = [(1,         1),
##                 (300,       2),
##                 (70000,     3),
##                 (17000000,  4)]
##         for number, numBytes in data:
##             i = snmplib.SnmpInteger32()
##             i.setValue(number)
##             encoded = i.encode()
##             encodedVal = encoded[2:]  # Skip type and length bytes
##             length = len(encodedVal)
##             self.assertEqual(length, numBytes, "Took %s bytes to encode %s instead of %s." % (length, number, numBytes))

if __name__ == '__main__':
    unittest.main()



