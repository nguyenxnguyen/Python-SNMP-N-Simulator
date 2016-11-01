#!/usr/bin/env python

import sys, unittest, exceptions, os, time
import snmpsim, snmplib


class TestMibStore(unittest.TestCase):
    insertValues = ( ('.1.3.6.1.2.1.1.1.0', 'OctetString', 'Linux 2.4.1'),
                     ('.1.3.6.1.2.1.1.2.0', 'OID', '.1.3.6.1.4.1.9.1'),
                     ('.1.3.6.1.2.1.1.3.0', 'TimeTicks', 810023300))

    nextValues = ( ('.1.3',               '.1.3.6.1.2.1.1.1.0'),
                   ('.1.3.1',             '.1.3.6.1.2.1.1.1.0'),
                   ('.1.3.6.1.2.1.1.1.0', '.1.3.6.1.2.1.1.2.0'),
                   ('.1.3.6.1.2.1.1.2.0', '.1.3.6.1.2.1.1.3.0'),
                   ('.1.3.9',             'NONE'))

    #
    # Test MibStore stuff
    #
    def testMibStoreGet(self):
        """Test that basic GET requests made of the MibDataStore work as expected.
        """
        mds = snmpsim.MibDataStore()
        for oid, type, val in self.insertValues:
            var = mds._createVariable(oid, type, val)
            mds.insert(var)

        for oid, type, val in self.insertValues:
            var = mds.get(oid)
            self.assertEqual(var.oid, oid)
            # Compare data types in lower case, since they differ from types the simulator thinks exists
            # vs those snmplib thinks exist (also, in some cases they different even more that just in case--
            # INTEGER vs Integer32, for instance. Oh well...should be ok for testing. :)
            self.assertEqual(var.type.lower(), type.lower())
            self.assertEqual(var.value, val)

            
    def testMibStoreGetNext(self):
        """Test that basic GETNEXT requests made of the MibDataStore work as expected.
        """        
        mds = snmpsim.MibDataStore()
        for oid, type, val in self.insertValues:
            var = mds._createVariable(oid, type, val)
            mds.insert(var)            

        for reqOid, respOid in self.nextValues:
            try:
                var = mds.getNext(reqOid)
                oid = var.oid
            except snmpsim.MibStoreError:
                oid = 'NONE'
            self.assertEqual(oid, respOid, "Got back %s from GETNEXT on %s instead of %s" % (oid, reqOid, respOid))



    def testMibStoreGetNextProblem(self):
        """Test problem that cropped up because single pass doesn't make change functions get set, and we
           watched for attribute error while seeing if .next existed, and in the same block called changeFunction,
           which didn't exist due to the single pass thing, and was caught and made it look like the .next wasn't
           set when it really was. Fix was to make it so changeFunction is only called if .changeFunction() exists,
           and the change stuff was moved out of the .next testing try block.
        """
        insertValues = ( ('.1.3.6.1.2.1.2.2.1.9.5', 'TimeTicks', '0'),
                         ('.1.3.6.1.2.1.2.2.1.9.6', 'TimeTicks', '0'),
                         ('.1.3.6.1.2.1.2.2.1.10.1', 'Counter', '0'),
                         ('.1.3.6.1.2.1.2.2.1.10.2', 'Counter', '1170278098'),
                         ('.1.3.6.1.2.1.2.2.1.10.3', 'Counter', '5664661'),
                         ('.1.3.6.1.2.1.2.2.1.10.4', 'Counter', '0'))
        mds = snmpsim.MibDataStore()
        for oid, type, val in insertValues:
            var = mds._createVariable(oid, type, val)
            mds.insert(var)
        # Here's the call that should work but fails (raises an exception)
        mds.getNext('.1.3.6.1.2.1.2.2.1.9.6', change=1)   


## 2002-05-23: Disabled test with new data store...seems silly to differentiate between
##             whether an oid is a substring of another--it's either there or it's not. Changed
##             exception to just be MibStoreNoSuchNameError in get().
##
##     def testMibStoreShorterOidGetRaisesException(self):
##         """Verify that a GET request for an oid that's shorter than one that actually exists
##            fails with the appropriate exception (MibStoreNotRetrievable)
##         """   
##         mds = snmpsim.MibDataStore()
##         var = mds._createVariable('.1.3.6.1.2.1.1.1.1.0', 'OctetString', 'AAAA')
##         mds.insert(var)
##         exception = None
##         try:
##             var = mds.get('.1.3.6.1.2.1')
##         except snmpsim.MibStoreNotRetrievable:
##             exception = sys.exc_info()[0]
##         except exceptions.Exception, data:
##             exception = sys.exc_info()[0]
##         self.assertEqual(exception, snmpsim.MibStoreNotRetrievable, \
##                          "Didn't raise MibStoreNotRetrievable with GET of shorter than existing oid (exception was %s)." \
##                          % exception)


    def testMibStoreLongerOidGetRaisesException(self):
        """Verify that if a GET for an oid that's longer than an existing one is requested that the
           appropriate exception is raised (MibStoreNoSuchNameError). For instance, if .1.3.6.1.2.1.1.1.0 was inserted,
           and then .1.3.6.1.2.1.1.1.0.0 was requested.
        """         
        mds = snmpsim.MibDataStore()
        var = mds._createVariable('.1.3.6.1.2.1.1.1.1.0', 'OctetString', 'AAAA')
        mds.insert(var)
        exception = None
        try:
            var = mds.get('.1.3.6.1.2.1.1.1.1.0.1.1')
        except snmpsim.MibStoreInsertError:
            exception = sys.exc_info()[0]
        except exceptions.Exception, data:
            exception = sys.exc_info()[0]
        self.assertEqual(exception, snmpsim.MibStoreNoSuchNameError, \
                         "Didn't raise MibStoreNoSuchNameError on GET of shorter, overwritten oid (raised %s)." % exception)
       
        
    def testMibStoreLongerOidGetNextRaisesException(self):
        """Verify that if a GETNEXT for an oid that's longer than an existing one is requested that the
           appropriate exception is raised (MibStoreNoSuchNameError). For instance, if .1.3.6.1.2.1.1.1.0 was inserted,
           and then .1.3.6.1.2.1.1.1.0.0 was requested.
        """   
        mds = snmpsim.MibDataStore()
        var = mds._createVariable('.1.3.6.1.2.1.1.1.1.0', 'OctetString', 'AAAA')
        mds.insert(var)
        exception = None
        try:
            var = mds.getNext('.1.3.6.1.2.1.1.1.1.0.1.1')
        except snmpsim.MibStoreInsertError:
            exception = sys.exc_info()[0]
        except exceptions.Exception, data:
            exception = sys.exc_info()[0]
        self.assertEqual(exception, snmpsim.MibStoreNoSuchNameError, \
                         "Didn't raise MibStoreNoSuchNameError on GETNEXT of shorter, overwritten oid (raised %s)." % \
                         exception)

    def testMibStoreOverLappingOidsOk(self):
        """Insert oids that used to be invalid under the old scheme and verify that everything (gets, getnexts)
           looks good.
        """
        insertValues = ( ('.1.3.6.1.2.1.1.2.0',             'OctetString', 'one'),
                         ('.1.3.6.1.2.1.1.2.0.1',           'OctetString', 'two'),
                         ('.1.3.6.1.2.1.1.2.0.1.1.1.2',     'OctetString', 'three'),
                         ('.1.3.6.1.2.1.1.2.0.1.1.1.2.5.4', 'OctetString', 'four'))
        nextValues = ( ('.1.3',                           '.1.3.6.1.2.1.1.2.0'),
                       ('.1.3.6.1.2.1.1.2.0',             '.1.3.6.1.2.1.1.2.0.1'),
                       ('.1.3.6.1.2.1.1.2.0.1',           '.1.3.6.1.2.1.1.2.0.1.1.1.2'),
                       ('.1.3.6.1.2.1.1.2.0.1.1.1.2',     '.1.3.6.1.2.1.1.2.0.1.1.1.2.5.4'),
                       ('.1.3.6.1.2.1.1.2.0.1.1.1.2.5.4', 'NONE'))
        
        mds = snmpsim.MibDataStore()
        for oid, type, val in insertValues:
            var = mds._createVariable(oid, type, val)
            mds.insert(var)

        # Test GET stuff
        for oid, type, val in insertValues:
            var = mds.get(oid)
            self.assertEqual(var.oid, oid)
            # Compare data types in lower case, since they differ from types the simulator thinks exists
            # vs those snmplib thinks exist (also, in some cases they different even more that just in case--
            # INTEGER vs Integer32, for instance. Oh well...should be ok for testing. :)
            self.assertEqual(var.type.lower(), type.lower())
            self.assertEqual(var.value, val)        

        # Test GETNEXT stuff
        for reqOid, respOid in nextValues:
            try:
                var = mds.getNext(reqOid)
                oid = var.oid
            except snmpsim.MibStoreError:
                oid = 'NONE'
            self.assertEqual(oid, respOid)



    def testMibStoreExpNotationExpansion(self):
        """Test that exponential expansion of TCL floating point numbers works properly.
        """
        expandVals = [('7.28138e+06', '7281380.0'),
                      ('2.10453e+11', '210453000000.0'),
                      ('5.08963e+18', '5089630000000000000.0') ]
        mds = snmpsim.MibDataStore()
        for exp, newVal in expandVals:
            self.assertEqual(mds._expandIfExp(exp), newVal, "Returned %s instead of expected %s when converting %s" \
                             % (mds._expandIfExp(exp), newVal, exp))



    #
    # Test change functions
    #
    def testChangeCounter32(self):
        """Test that delta behavior for counter32s is as expected (increments based on time, not
           number of requests, wraps properly, etc).
        """
        # Format =  delta,   initialval, afteronedelta, aftertwodeltas, afterthreedeltas
        data = [ [      1, [          0,             1,              2,                3] ],
                 [  37000, [      50000,         87000,         124000,           161000] ],
                 [      1, [4294967294L,   4294967295L,              0,                1] ] ]
      
        # Shorten time period for delta change so we can test more quickly
        snmpsim.DELTA_APPLY_RATE = 1       
        for delta, correct in data:
            # Make and load a temporary dump, exercising the load() function
            TEMP_DUMP = "temp.mdr"
            fh = open(TEMP_DUMP, "wb")
            fh.write(".1.3.6.1.2.1.2.2.1.10.1 Counter %s\n" % correct[0])
            fh.write(".1.3.6.1.2.1.2.2.1.10.1 Counter %s\n" % (correct[0] + delta))
            fh.close()
            sim = snmpsim.SnmpSim()
            sim.setVerbose(0)
            sim.load(TEMP_DUMP)
            os.remove(TEMP_DUMP)

            mds = sim.mib
            req = 0
            distinctVals = {}
            retrieved = []
            numVals = 4
            while len(distinctVals.keys()) < numVals and req < 100:
                var = mds.get('.1.3.6.1.2.1.2.2.1.10.1', change=1)
                req += 1
#                print "[got %s]" % var.value                
                if not distinctVals.has_key(var.value):
                    retrieved.append(var.value)
                    distinctVals[var.value] = 1
                time.sleep(0.1)
            self.assert_(req < 100, "Too many requests before value changed--is the change function set right?")
            # Make sure we didn't get different values back for each request (if counter changes based on time
            # and not request it should be the same for a few requests).
            reqsPerVal = req/numVals
            self.assert_(reqsPerVal >= 2, "Number of requests per value (%s) too low. Using time-based change functions?" \
                         % reqsPerVal)
            self.assertEqual(len(correct), len(retrieved))
            for i in range(len(correct)):
                self.assertEqual(correct[i], retrieved[i], "Didn't get expected value (%s) back (got %s)." % \
                                 (correct[i], retrieved[i]))


    def testChangeCounter64(self):
        """Test that delta behavior for counter64s is as expected (increments based on time, not
           number of requests, wraps properly, etc).
        """
        # Format =  delta,             initialval,        afteronedelta,  aftertwodeltas, afterthreedeltas
        data = [ [      1, [                    0,                     1,              2,                3] ],
                 [  37000, [              9050000,               9087000,        9124000,          9161000] ],
                 [      1, [18446744073709551614L, 18446744073709551615L,              0,                1] ] ]      
      
        # Shorten time period for delta change so we can test more quickly
        snmpsim.DELTA_APPLY_RATE = 1       
        for delta, correct in data:
            # Make and load a temporary dump, exercising the load() function
            TEMP_DUMP = "temp.mdr"
            fh = open(TEMP_DUMP, "wb")
            fh.write(".1.3.6.1.2.1.2.2.1.10.1 Counter64 %s\n" % correct[0])
            fh.write(".1.3.6.1.2.1.2.2.1.10.1 Counter64 %s\n" % (correct[0] + delta))
            fh.close()
            sim = snmpsim.SnmpSim()
            sim.setVerbose(0)
            sim.load(TEMP_DUMP)
            os.remove(TEMP_DUMP)

            mds = sim.mib
            req = 0
            distinctVals = {}
            retrieved = []
            numVals = 4
            while len(distinctVals.keys()) < numVals and req < 100:
                var = mds.get('.1.3.6.1.2.1.2.2.1.10.1', change=1)
                req += 1
#                print "[got %s]" % var.value
                if not distinctVals.has_key(var.value):
                    retrieved.append(var.value)
                    distinctVals[var.value] = 1
                time.sleep(0.1)
            self.assert_(req < 100, "Too many requests before value changed--is the change function set right?")
            # Make sure we didn't get different values back for each request (if counter changes based on time
            # and not request it should be the same for a few requests).
            reqsPerVal = req/numVals
            self.assert_(reqsPerVal >= 2, "Number of requests per value (%s) too low. Using time-based change functions?" \
                         % reqsPerVal)
            self.assertEqual(len(correct), len(retrieved))
            for i in range(len(correct)):
                self.assertEqual(correct[i], retrieved[i], "Didn't get expected value (%s) back (got %s)." % \
                                 (correct[i], retrieved[i]))                


    #
    # Test _processMessage function for various things
    #
    def testV1Get(self):
        """Test the _processMessage() works properly for basic SNMPv1 GET requests.
        """
        insertValues = ( ('.1.3.6.1.2.1.1.1.0', 'OctetString', 'Linux 2.4.1'),
                         ('.1.3.6.1.2.1.1.3.0', 'TimeTicks', 810023300))
        # Get sim object with mib containing values above.
        s = snmpsim.SnmpSim()
        # v1 mode only
        s.v1Mode = 1
        s.v2Mode = 0
        s.verbose = 0
        mib = snmpsim.MibDataStore()
        for oid, _type, val in self.insertValues:
            var = mib._createVariable(oid, _type, val)
            mib.insert(var)
            
        s.mib = mib
        # Construct a message that does a GET on each of these
        for oid, _type, val in insertValues:
            getMsg = snmplib.SnmpMessage()
            getMsg.pdu.type = 'GetRequest'
            var = snmplib.SnmpNull()
            var.oid = oid
            getMsg.pdu.varbind.items.append(var)
            respMsg = s._processMessage(getMsg)
            self.assertEqual(respMsg.pdu.type, 'GetResponse', "Response type set incorrectly (expected GetResponse)")
            self.assertEqual(respMsg.pdu.errorStatus.value, 0, "Error status set incorrectly (expected 0)")
            self.assertEqual(respMsg.pdu.errorIndex.value, 0, "Error index set incorrectly (expected 0)")
            self.assertEqual(respMsg.pdu.varbind.items[0].oid, oid, "OID set incorrectly (expected %s)" % oid)
            self.assertEqual(respMsg.pdu.varbind.items[0].type, _type, "Type set incorrectly (expected %s)" % _type)
            self.assertEqual(respMsg.pdu.varbind.items[0].value, val, "Value set incorrectly (expected %s)" % val)
            
        
    def testV1GetFail(self):
        """Test that message processing for SNMPv1 GET requests when the oid requested doesn't exist
           works properly (verify that response has errorStatus/errorIndex set correctly, etc).
        """   
        insertValues = ( ('.1.3.6.1.2.1.1.1.0', 'OctetString', 'Linux 2.4.1'),
                         ('.1.3.6.1.2.1.1.2.0', 'OID', '.1.3.6.1.4.1.9.1'),
                         ('.1.3.6.1.2.1.1.3.0', 'TimeTicks', 810023300))
        # Get sim object with mib containing values above.
        s = snmpsim.SnmpSim()
        s.verbose = 0
        mib = snmpsim.MibDataStore()
        for oid, type, val in self.insertValues:
            var = mib._createVariable(oid, type, val)
            mib.insert(var)

        s.mib = mib
        # Construct a message that does a GET on something that doesn't exist
        getMsg = snmplib.SnmpMessage()
        getMsg.pdu.type = 'GetRequest'
        var = snmplib.SnmpNull()
        var.oid = '.1.3.6.1.2.1.1.7.0'  # Doesn't exist
        getMsg.pdu.varbind.items.append(var)
        respMsg = s._processMessage(getMsg)
        self.assertEqual(respMsg.pdu.type, 'GetResponse', "Response type set incorrectly (expected GetResponse)")
        self.assertEqual(respMsg.pdu.errorStatus.value, 2, "Error status set incorrectly (expected 2/noSuchName)")
        self.assertEqual(respMsg.pdu.errorIndex.value, 1, "Error index set incorrectly (expected 1)")
        self.assertEqual(respMsg.pdu.varbind.items[0].oid, var.oid, "OID set incorrectly (expected %s)" % var.oid)


    def testV2Get(self):
        """Test the _processMessage() works properly for basic SNMPv2 GET requests.
        """
        insertValues = ( ('.1.3.6.1.2.1.1.1.0', 'OctetString', 'Linux 2.4.1'),
                         ('.1.3.6.1.2.1.1.3.0', 'TimeTicks', 810023300))
        # Get sim object with mib containing values above.
        s = snmpsim.SnmpSim()
        # v2 mode only
        s.v1Mode = 0
        s.v2Mode = 1
        s.verbose = 0
        mib = snmpsim.MibDataStore()
        for oid, _type, val in self.insertValues:
            var = mib._createVariable(oid, _type, val)
            mib.insert(var)
            
        s.mib = mib
        # Construct a message that does a GET on each of these
        for oid, _type, val in insertValues:
            getMsg = snmplib.SnmpMessage()
            getMsg.version.setValue(1)  # v2
            getMsg.pdu.type = 'GetRequest'
            var = snmplib.SnmpNull()
            var.oid = oid
            getMsg.pdu.varbind.items.append(var)
            respMsg = s._processMessage(getMsg)
            self.assertEqual(respMsg.pdu.type, 'GetResponse', "Response type set incorrectly (expected GetResponse)")
            self.assertEqual(respMsg.pdu.errorStatus.value, 0, "Error status set incorrectly (expected 0)")
            self.assertEqual(respMsg.pdu.errorIndex.value, 0, "Error index set incorrectly (expected 0)")
            self.assertEqual(respMsg.pdu.varbind.items[0].oid, oid, "OID set incorrectly (expected %s)" % oid)
            self.assertEqual(respMsg.pdu.varbind.items[0].type, _type, "Type set incorrectly (expected %s)" % _type)
            self.assertEqual(respMsg.pdu.varbind.items[0].value, val, "Value set incorrectly (expected %s)" % val)
        

    def testV2GetFail(self):
        """Test that message processing for SNMPv2 GET requests when some oids exist and another doesn't.
           Verify that the ones that are there are retrieved, and the one that isn't there has the appropriate
           error value set (noSuchObject thingy).
        """   
        insertValues = ( ('.1.3.6.1.2.1.1.1.0', 'OctetString', 'Linux 2.4.1'),
                         ('.1.3.6.1.2.1.1.3.0', 'TimeTicks', 810023300))
        # Get sim object with mib containing values above.
        s = snmpsim.SnmpSim()
        s.verbose = 0
        mib = snmpsim.MibDataStore()
        for oid, type, val in insertValues:
            var = mib._createVariable(oid, type, val)
            mib.insert(var)

        s.mib = mib
        # v2 mode only
        s.v1Mode = 0
        s.v2Mode = 1
        
        # Get a request put together that hits stuff that exists, and some that doesn't.
        getMsg = snmplib.SnmpMessage()
        getMsg.version.setValue(1)  # v2
        getMsg.pdu.type = 'GetRequest'
        var = snmplib.SnmpNull()
        var.oid = '.1.3.6.1.2.1.1.1.0'
        getMsg.pdu.varbind.items.append(var)
        var = snmplib.SnmpNull()
        var.oid = '.1.3.6.1.2.1.1.2.0'
        getMsg.pdu.varbind.items.append(var)
        var = snmplib.SnmpNull()
        var.oid = '.1.3.6.1.2.1.1.3.0'
        getMsg.pdu.varbind.items.append(var)
        # Make request
        respMsg = s._processMessage(getMsg)
        # Check first var...
        self.assertEqual(respMsg.pdu.varbind.items[0].oid, '.1.3.6.1.2.1.1.1.0')
        self.assertEqual(respMsg.pdu.varbind.items[0].value, 'Linux 2.4.1')
        # ...that second doesn't exist...
        self.assertEqual(respMsg.pdu.varbind.items[1].oid, '.1.3.6.1.2.1.1.2.0')
        self.assertEqual(respMsg.pdu.varbind.items[1].type, 'NoSuchObject')
        # And that third does.
        self.assertEqual(respMsg.pdu.varbind.items[2].oid, '.1.3.6.1.2.1.1.3.0')
        self.assertEqual(respMsg.pdu.varbind.items[2].value, 810023300)
        


    def testV2GetNext(self):
        """Test the _processMessage() works properly for basic SNMPv2 GETNEXT requests. Test that end
           of mib view type is set for last request too (probably skip v2getnextfail test).
        """
        insertValues = ( ('.1.3.6.1.2.1.1.1.0', 'OctetString', 'Linux 2.4.1'),
                         ('.1.3.6.1.2.1.1.2.0', 'OID', '.1.3.6.1.4.1.9.1'),
                         ('.1.3.6.1.2.1.1.3.0', 'TimeTicks', 810023300))

        nextValues = ( ('.1.3',               '.1.3.6.1.2.1.1.1.0'),
                       ('.1.3.1',             '.1.3.6.1.2.1.1.1.0'),
                       ('.1.3.6.1.2.1.1.1.0', '.1.3.6.1.2.1.1.2.0'),
                       ('.1.3.6.1.2.1.1.2.0', '.1.3.6.1.2.1.1.3.0'),
                       ('.1.3.9',             'NONE'))
        
        # Get sim object with mib containing values above.
        s = snmpsim.SnmpSim()
        # v2 mode only
        s.v1Mode = 0
        s.v2Mode = 1
        s.verbose = 0
        mib = snmpsim.MibDataStore()
        for oid, _type, val in self.insertValues:
            var = mib._createVariable(oid, _type, val)
            mib.insert(var)
        s.mib = mib
        # Construct a message that does a GETNEXT on each of these
        for reqOid, oid in nextValues:
            getMsg = snmplib.SnmpMessage()
            getMsg.version.setValue(1)  # v2
            getMsg.pdu.type = 'GetNextRequest'
            var = snmplib.SnmpNull()
            var.oid = reqOid
            getMsg.pdu.varbind.items.append(var)
            respMsg = s._processMessage(getMsg)
            self.assertEqual(respMsg.pdu.type, 'GetResponse', "Response type set incorrectly (expected GetResponse)")
            if oid == 'NONE':
                self.assertEqual(respMsg.pdu.varbind.items[0].type, 'EndOfMibView', \
                                 "Didn't get EndOfMibView for last GETNEXT.")
            else:
                self.assertEqual(respMsg.pdu.varbind.items[0].oid, oid, "OID set incorrectly (expected %s)" % oid)

    def testGetBulkEndOfMibView(self):
        """Test that GETBULK does endOfMibView thing properly.
        """
        insertValues = (('.1.3.6.1.2.1.2.1.0', 'Integer', '3'),
                        ('.1.3.6.1.2.1.2.2.1.1.1', 'Integer', '1'),
                        ('.1.3.6.1.2.1.2.2.1.1.2', 'Integer', '2'))        
        # Set up simulator with values
        s = snmpsim.SnmpSim()
        # v2 mode only
        s.v1Mode = 0
        s.v2Mode = 1
        s.verbose = 0
        s.mib = snmpsim.MibDataStore()
        for oid, _type, val in insertValues:
            var = s.mib._createVariable(oid, _type, val)
            s.mib.insert(var)            

        nr = 0
        mr = 10
        # build getbulk req
        reqMsg = snmplib.SnmpMessage()
        reqMsg.version.setValue(1)  # v2
        pdu = snmplib.SnmpV2GetBulkPdu()
        reqMsg.pdu = pdu
        reqMsg.items[2] = pdu
        reqMsg.pdu.nonRepeaters.setValue(nr)
        reqMsg.pdu.maxRepetitions.setValue(mr)
        var = snmplib.SnmpNull()
        var.oid = '.1.3.6.1.2.1.2'
        reqMsg.pdu.varbind.items.append(var)
        respMsg = s._processMessage(reqMsg)
        vars = respMsg.pdu.varbind.items
        self.assertEqual(vars[3].type, 'EndOfMibView', "Didn't get EndOfMibView back when expected from GETBULK.")


    def testGetBulkOrdering(self):
        """Test that normal GETBULK appears to work (also check that ordering is correct--
           apparently GETNEXTs should be done cycling over oids in PDU instead of doing all
           the GETNEXTs possible for a single oid then continuing.
        """
        insertValues = (('.1.3.6.1.2.1.2.1.0', 'Integer', '3'),
                        ('.1.3.6.1.2.1.2.2.1.1.1', 'Integer', '1'),
                        ('.1.3.6.1.2.1.2.2.1.1.2', 'Integer', '2'),
                        ('.1.3.6.1.2.1.2.2.1.1.3', 'Integer', '3'),
                        ('.1.3.6.1.2.1.2.2.1.2.1', 'OctetString', '65-65-65'),
                        ('.1.3.6.1.2.1.2.2.1.2.2', 'OctetString', '66-66-66'),
                        ('.1.3.6.1.2.1.2.2.1.2.3', 'OctetString', '67-67-67'),
                        ('.1.3.6.1.2.1.2.2.1.3.1', 'Integer', '6'),
                        ('.1.3.6.1.2.1.2.2.1.3.2', 'Integer', '24'),
                        ('.1.3.6.1.2.1.2.2.1.3.3', 'Integer', '56'),
                        ('.1.3.6.1.2.1.2.2.1.4.1', 'Integer', '1500'),
                        ('.1.3.6.1.2.1.2.2.1.4.2', 'Integer', '32768'),
                        ('.1.3.6.1.2.1.2.2.1.4.3', 'Integer', '1500'))
        # Set up simulator with values
        s = snmpsim.SnmpSim()
        # v2 mode only
        s.v1Mode = 0
        s.v2Mode = 1
        s.verbose = 0
        s.mib = snmpsim.MibDataStore()
        for oid, _type, val in insertValues:
            var = s.mib._createVariable(oid, _type, val)
            s.mib.insert(var)            

        nr = 0
        mr = 3
        # build getbulk req
        reqMsg = snmplib.SnmpMessage()
        reqMsg.version.setValue(1)  # v2
        pdu = snmplib.SnmpV2GetBulkPdu()
        reqMsg.pdu = pdu
        reqMsg.items[2] = pdu
        reqMsg.pdu.nonRepeaters.setValue(nr)
        reqMsg.pdu.maxRepetitions.setValue(mr)
        for i in (1, 2, 3, 4):
            var = snmplib.SnmpNull()
            var.oid = '.1.3.6.1.2.1.2.2.1.%s' % i
            reqMsg.pdu.varbind.items.append(var)
        respMsg = s._processMessage(reqMsg)
        oids = map((lambda x: x.oid), respMsg.pdu.varbind.items)
        expectedOids = ['.1.3.6.1.2.1.2.2.1.1.1', '.1.3.6.1.2.1.2.2.1.2.1', '.1.3.6.1.2.1.2.2.1.3.1',
                        '.1.3.6.1.2.1.2.2.1.4.1', '.1.3.6.1.2.1.2.2.1.1.2', '.1.3.6.1.2.1.2.2.1.2.2',
                        '.1.3.6.1.2.1.2.2.1.3.2', '.1.3.6.1.2.1.2.2.1.4.2', '.1.3.6.1.2.1.2.2.1.1.3',
                        '.1.3.6.1.2.1.2.2.1.2.3', '.1.3.6.1.2.1.2.2.1.3.3', '.1.3.6.1.2.1.2.2.1.4.3']
        self.assertEqual(oids, expectedOids, "Oids returned in wrong (old) order or other GETBULK problem.")
#        print "request (%s oids, nr=%s, mr=%s):" % (len(reqMsg.pdu.varbind.items), nr, mr)
#        for i in reqMsg.pdu.varbind.items:
#            print "  %s" % i.oid
#        print "varbind (%s oids):" % len(respMsg.pdu.varbind.items)
#        for i in respMsg.pdu.varbind.items:
#            print "  %s" % i.oid
    
    #
    # Test other random things that have come up
    #
    def testEmptyV2GetBulk(self):
        """Make sure an empty GetBulk request is encoded properly (must have something in
           the varbind to encode).
        """
        # Get sim w/empty MibDataStore
        s = snmpsim.SnmpSim()
        # v2 mode only
        s.v1Mode = 0
        s.v2Mode = 1
        s.verbose = 0
        s.mib = snmpsim.MibDataStore()
        reqMsg = snmplib.SnmpMessage()
        reqMsg.version.setValue(1)  # v2
        pdu = snmplib.SnmpV2GetBulkPdu()
        reqMsg.pdu = pdu
        reqMsg.items[2] = pdu
        reqMsg.pdu.nonRepeaters.setValue(0)
        reqMsg.pdu.maxRepetitions.setValue(3)
        var = snmplib.SnmpNull()
        var.oid = '.1.3.6.1.4.1'
        reqMsg.pdu.varbind.items.append(var)
        respMsg = s._processMessage(reqMsg)
        self.assertEqual(respMsg.pdu.type, 'GetResponse', "Response type set incorrectly (expected GetResponse)")
        self.assertEqual(len(respMsg.pdu.varbind.items), 1, "Didn't get exactly one item back in varbind (got %s)." \
                         % len(respMsg.pdu.varbind.items) )
        self.assertEqual(respMsg.pdu.varbind.items[0].oid, '.1.3.6.1.4.1')
                        

    def testEmptyRequestHandled(self):
        """Verify that a request sent that doesn't have anything in the PDU is handled properly
           (this was causing problems when the poller sent a message like this at one point).
        """
        # Get a sim object
        s = snmpsim.SnmpSim()
        s.verbose = 0

        # Construct a message with nothing in the pdu
        getMsg = snmplib.SnmpMessage()
        getMsg.pdu.type = 'GetRequest'
        respMsg = s._processMessage(getMsg)
        self.assertEqual(respMsg, None)

    def testErrorIndexSetRight(self):
        """Verify that errorIndex is one-based and not zero-based (how I originally developed it
           until Tuan noticed the bug).
        """
        # Build a mib ds with a few vars in it
        s = snmpsim.SnmpSim()
        s.verbose = 0
        s.mib = snmpsim.MibDataStore()
        var = snmplib.SnmpOctetString()
        var.setValue('test sysDescr')
        var.oid = '.1.3.6.1.2.1.1.1.0'
        s.mib.insert(var)
        var = snmplib.SnmpOctetString()        
        var.setValue('aaaaaaaaaaaaaaaaaa')
        var.oid = '.1.3.6.1.4.1.5555.1.0'
        s.mib.insert(var)
        var = snmplib.SnmpOctetString()        
        var.setValue('bbbbbbbbbbbbbbbbbb')
        var.oid = '.1.3.6.1.4.1.5555.2.0'
        s.mib.insert(var)

        # Test out some bad requests to make sure errorIndex is set right.
        getMsg = snmplib.SnmpMessage()
        getMsg.pdu.type = 'GetRequest'
        var = snmplib.SnmpNull()
        var.oid = '.1.3.6.1.2.1.1.2.0'   # Not present
        getMsg.pdu.varbind.items.append(var)
        respMsg = s._processMessage(getMsg)
        eStat = respMsg.pdu.errorStatus.value
        eInd  = respMsg.pdu.errorIndex.value
        self.assertEqual(eStat, 2, "Got unexpected errorStatus of %s instead of 2 (noSuchName)" % eStat)
        self.assertEqual(eInd, 1, "errorIndex appears to be zero based instead of 1 based (got %s instead of 1)" % eInd)

        getMsg = snmplib.SnmpMessage()
        getMsg.pdu.type = 'GetRequest'
        var = snmplib.SnmpNull()
        var.oid = '.1.3.6.1.2.1.1.1.0'   # Present
        getMsg.pdu.varbind.items.append(var)
        var = snmplib.SnmpNull()
        var.oid = '.1.3.6.1.2.1.1.3.0'   # Not present
        getMsg.pdu.varbind.items.append(var)
        respMsg = s._processMessage(getMsg)
        eStat = respMsg.pdu.errorStatus.value
        eInd  = respMsg.pdu.errorIndex.value
        self.assertEqual(eStat, 2, "Got unexpected errorStatus of %s instead of 2 (noSuchName)" % eStat)
        self.assertEqual(eInd, 2, "errorIndex appears to be zero based instead of 1 based (got %s instead of 2)" % eInd)


        getMsg = snmplib.SnmpMessage()
        getMsg.pdu.type = 'GetRequest'
        var = snmplib.SnmpNull()
        var.oid = '.1.3.6.1.2.1.1.1.0'    # Present
        getMsg.pdu.varbind.items.append(var)
        var = snmplib.SnmpNull()
        var.oid = '.1.3.6.1.4.1.5555.1.0'   # Present
        getMsg.pdu.varbind.items.append(var)
        var = snmplib.SnmpNull()
        var.oid = '.1.3.6.1.4.1.5555.5.0'   # Not present
        getMsg.pdu.varbind.items.append(var)
        var = snmplib.SnmpNull()        
        var.oid = '.1.3.6.1.4.1.5555.2.0'   # Present
        getMsg.pdu.varbind.items.append(var)        
        respMsg = s._processMessage(getMsg)        
        eStat = respMsg.pdu.errorStatus.value
        eInd  = respMsg.pdu.errorIndex.value
        self.assertEqual(eStat, 2, "Got unexpected errorStatus of %s instead of 2 (noSuchName)" % eStat)
        self.assertEqual(eInd, 3, "errorIndex appears to be zero based instead of 1 based (got %s instead of 3)" % eInd)


    def testMibStoreDeepNonexistentGetNext(self):
        """Turns out the implementation of getnext looks to be wrong. If you have these oids in an snmp device:
           .1.3.6.1.2.1.1.1.0
           .1.3.6.1.2.1.1.2.0
           .1.3.6.1.2.1.1.3.0
           ...then a GETNEXT on .1.3.6.1.2.1.1.1.9999999.12312.12.1.23, even though the oid isn't a substring
           of an existing oid and isn't an existing oid, should still return .1.3.6.1.2.1.1.2.0. Before it
           was failing with a noSuchName sort of error, which was incorrect. It's supposed to work like they
           are ordered alphabetically, it looks like.
        """
        insertValues = ( ('.1.3.6.1.2.1.1.1.0', 'OctetString', 'Linux 2.4.1'),
                         ('.1.3.6.1.2.1.1.2.0', 'OID', '.1.3.6.1.4.1.9.1'),
                         ('.1.3.6.1.2.1.1.3.0', 'TimeTicks', 810023300))
        mds = snmpsim.MibDataStore()
        for oid, type, val in insertValues:
            var = mds._createVariable(oid, type, val)
            mds.insert(var)

        exception = None
        try:
            var = mds.getNext('.1.3.6.1.2.1.1.1.9999999.12312.12.1.23')
        except:
            exception = sys.exc_info()[0]
        self.assertEqual(exception, None, "GETNEXT raised %s instead of returning .1.3.6.1.2.1.1.2.0." % exception)

    def testWeirdGetNextProblem(self):
        """GETNEXT on something returns something obviously wrong--looks like we assumed that the oids would be
           in order in the dump.
        """
        insertValues = ( ('.1.3.6.1.2.1.31.1.1.1.18.33',       'OctetString', '34-80-86-71'),
                         ('.1.3.6.1.2.1.31.1.1.1.18.34',       'OctetString', '116-117-110-49-95'),
                         ('.1.3.6.1.2.1.4.20.1.1.154.11.0.72', 'IpAddress',   '154.11.0.72'),
                         ('.1.3.6.1.2.1.32.1.0',               'OctetString', '116-117-110-49-95'))
        mds = snmpsim.MibDataStore()
        for oid, type, val in insertValues:
            var = mds._createVariable(oid, type, val)
            mds.insert(var)
        var = mds.getNext('.1.3.6.1.2.1.31.1.1.1.18.34')
        self.assertEqual(var.oid, '.1.3.6.1.2.1.32.1.0', "Got %s back instead of .1.3.6.1.2.1.32.1.0" % var.oid)                        
    def testCmpProblem(self):
        """Subtle oid comparision problem that came up once--thought
           .1.3.6.1.2.1.2.2.1.19.1 came before
           .1.3.6.1.2.1.2.2.1.2.
        """
        mds = snmpsim.MibDataStore()
        retVal = mds._compareOids('.1.3.6.1.2.1.2.2.1.2', '.1.3.6.1.2.1.2.2.1.19.1')
        self.assertEqual(retVal, -1, "Oid comparision problem--.1.3.6.1.2.1.2.2.1.2 is supposed to come before\n" + \
                         ".1.3.6.1.2.1.2.2.1.19.1")

    def testCCmpProblem(self):
        """Subtle oid comparision problem that came up once--thought
           .1.3.6.1.2.1.2.2.1.19.1 came before
           .1.3.6.1.2.1.2.2.1.2.
           (test C function)
        """
        import csnmpsim
        retVal = csnmpsim.compareOids('.1.3.6.1.2.1.2.2.1.2', '.1.3.6.1.2.1.2.2.1.19.1')
        self.assertEqual(retVal, -1, "Oid comparision problem--.1.3.6.1.2.1.2.2.1.2 is supposed to come before\n" + \
                         ".1.3.6.1.2.1.2.2.1.19.1")
        
    def testNewGetNextProblem(self):
        """Problem where new backend messes up some getnexts.
        """
        insertValues = ( ('.1.3.6.1.2.1.2.2.1.1.1', 'Integer', '1'),
                         ('.1.3.6.1.2.1.2.2.1.2.1', 'Counter', '0'),
                         ('.1.3.6.1.2.1.2.2.1.19.1', 'Counter', '0'),
                         ('.1.3.6.1.2.1.2.2.1.20.1', 'Counter', '0'))

        mds = snmpsim.MibDataStore()
        for oid, type, val in insertValues:
            var = mds._createVariable(oid, type, val)
            mds.insert(var)
        var = mds.getNext('.1.3.6.1.2.1.2.2.1.2')
        self.assertEqual(var.oid, '.1.3.6.1.2.1.2.2.1.2.1', "Got %s back instead of .1.3.6.1.2.1.2.2.1.2.1" % var.oid)

    def testMibStoreOidComparision(self):
        """Test that suboids are compared numberically and not alphabetically in new flat list/
           binary search data structure.
        """
        insertValues = ( ('.1.3.6.1.2.1.1.9.0', 'OctetString', 'Linux 2.4.1'),
                         ('.1.3.6.1.2.1.1.10.0', 'OID', '.1.3.6.1.4.1.9.1'))

        mds = snmpsim.MibDataStore()
        for oid, type, val in insertValues:
            var = mds._createVariable(oid, type, val)
            mds.insert(var)
        expected = '.1.3.6.1.2.1.1.10.0'
        exception = None
        try:       
            var = mds.getNext('.1.3.6.1.2.1.1.9.0')
        except:
            exception = sys.exc_info()[0]
        self.assertEqual(exception, None, "OID comparision probably wrong--GETNEXT raised %s instead of returning oid." % \
                         exception)
        self.assertEqual(var.oid, expected, "OID comparision probably wrong--GETNEXT returned %s instead of %s." % \
                         (var.oid, expected))

    def testCompareFunctionOk(self):
        """Verify that compare function is working. It should return -1 if the first oid is
           before the second oid, 0 if they are equal, and 1 if the second is before the first.
        """
        data = (('.1.3.6.1',                '.1.3.6.2',                -1),
                ('.1.3.6.2',                '.1.3.6.1',                 1),
                ('.1.3.6.1',                '.1.3.6.1.2',              -1),
                ('.1.3.6.1.2',              '.1.3.6.1',                 1),                
                ('.1.3.6.1.2.1.1.1.0',      '.1.3.6.1.4.1.9',          -1),
                ('.1.3.6.1.2.1.1.9.0',      '.1.3.6.1.2.1.1.10.0',     -1),
                ('.1.3.6.1.2.17.1.1.1.2.0', '.1.3.6.1.2.17.1.1.1.2.0',  0),
                ('.1.3.6.1.2.1.4.20.1.1.192.168.100.192', '.1.3.6.1.2.1.4.20.1.1.192.168.1.254', 1))
        mds = snmpsim.MibDataStore()
        for oid1, oid2, res in data:
            compareRes = mds._compareOids(oid1, oid2)
            self.assertEqual(compareRes, res, "Compare function returned %s instead of %s (%s -> %s)" % \
                             (compareRes, res, oid1, oid2))
        

    def testCCompareFunctionOk(self):
        """Verify that compare function is working. It should return -1 if the first oid is
           before the second oid, 0 if they are equal, and 1 if the second is before the first.
           (test C function)
        """
        import csnmpsim
        data = (('.1.3.6.1',                '.1.3.6.2',                -1),
                ('.1.3.6.2',                '.1.3.6.1',                 1),
                ('.1.3.6.1',                '.1.3.6.1.2',              -1),
                ('.1.3.6.1.2',              '.1.3.6.1',                 1),                
                ('.1.3.6.1.2.1.1.1.0',      '.1.3.6.1.4.1.9',          -1),
                ('.1.3.6.1.2.1.1.9.0',      '.1.3.6.1.2.1.1.10.0',     -1),
                ('.1.3.6.1.2.17.1.1.1.2.0', '.1.3.6.1.2.17.1.1.1.2.0',  0),
                ('.1.3.6.1.2.1.4.20.1.1.192.168.100.192', '.1.3.6.1.2.1.4.20.1.1.192.168.1.254', 1))
        for oid1, oid2, res in data:
            compareRes = csnmpsim.compareOids(oid1, oid2)
            self.assertEqual(compareRes, res, "C Compare function returned %s instead of %s (%s -> %s)" % \
                             (compareRes, res, oid1, oid2))


    def testNonsensicalGetNextFailure(self):
        """Test that a getnext on ipForwDatagrams.0 doesn't return no such name when it
           shouldn't.
        """
        insertValues = ( ('.1.3.6.1.2.1.4.20.1.5.192.168.0.4', 'Integer', '65535'),
                         ('.1.3.6.1.2.1.4.6.0', 'Counter', '0'),
                         ('.1.3.6.1.4.1.4785.2.1.1.1.0', 'Integer', '1'))
        mds = snmpsim.MibDataStore()
        for oid, type, val in insertValues:
            var = mds._createVariable(oid, type, val)
            mds.insert(var)

        exception = None
        try:
            var = mds.getNext('.1.3.6.1.2.1.4.6.0')
        except:
            exception = sys.exc_info()[0]
        self.assertEqual(exception, None, "GETNEXT raised %s instead of returning .1.3.6.1.2.1.4.20.1.5.192.168.0.4." % \
                         exception)


if __name__ == '__main__':
    unittest.main()

