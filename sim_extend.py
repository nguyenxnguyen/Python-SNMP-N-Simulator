from Tkinter import *
import os, tkMessageBox
import signal
import subprocess
from time import sleep


class SimExtend(object):
    def __init__(self, *args, **kwargs):
        pass

    @staticmethod
    def stop_sim(table):
        #table_return = []
        for row in table:
            row = list(row)
            if row[4] != '---':
                pid_current = int(row[4])
                os.kill(pid_current, signal.SIGTERM)
                row[4] = '---'
            else:
                pass
            #table_return.append(row)
            yield row
        #os.system('cls')

    @staticmethod
    def snmp_get_sysoid(folder, table):
        snmpget = os.path.dirname(os.path.abspath(__file__)) + "/" + 'SnmpGet.exe'
        msg_conflict = ''
        log_detail = ''
        sys_oid = '".1.3.6.1.2.1.1.2.0"'
        table = list(table)
        #table_return = []
        #print table
        for row in table:
            row = list(row)
            # row: 0 1 2 3 4 5 == IP Port File State PID SysOid
            if row[4] == '---':
                filePath = folder + "/" + row[2]
                if os.path.exists(filePath):
                    row[3] = 'Available'
                    row[4] = '---'
                else:
                    row[3] = 'File Not Found'
                    row[4] = '---'
            else:
                cmd_snmpget = '\""%s" -q -r:%s -p:%s -t:1 -c:"public" -o:%s' % (snmpget, row[0], row[1], sys_oid)
                response = os.popen(cmd_snmpget).read()
                response = response.replace('\n', '')
                if response.__contains__('Timeout'):
                    row[3] = 'Stopped'
                    sys_oid_value = '---'
                elif response.__contains__('1.3.6.1.4.1'):
                    row[3] = 'Running'
                    sys_oid_value = response
                else:
                    row[3] = 'Unknown'
                    sys_oid_value = '---'
                if row[5] != '---' and row[5] != sys_oid_value and sys_oid_value != '---':
                    msg_conflict += '%s:%s - %s\tMibdump has changed!\n' % (row[0], row[1], row[2])
                row[5] = sys_oid_value
            log_add = '%s,%s,%s,%s\n' % (row[0], row[1], row[2], row[5])
            log_detail += log_add
            #table_return.append(row)
            yield row
        if log_detail:
            log_path = folder + "/" + "List_of_Mibdumps.csv"
            log_open = open(log_path, 'w')
            log_open.write(log_detail)
            log_open.close()
        if msg_conflict != '':
            tkMessageBox.showwarning(title='Conflict!', message=msg_conflict)
        #return table_return

    @staticmethod
    def run_sim(v1, v2c, ranDm, table, folder):
        # Weird problem. The $NH_HOME/bin/mksnt dir is usually in the path,
        # and start.exe is in there and messes up our attempt to do the windows
        # start thing (this doesn't appear to be an actual program).
        # Remove any dir with "mksnt" from the path before kicking this
        # command off.
        if os.environ.has_key('PATH'):
            newPath = []
            regex = re.compile('mksnt', re.I)
            for dir in os.environ['PATH'].split(os.pathsep):
                if not regex.search(dir):
                    newPath.append(dir)
            os.environ['PATH'] = os.pathsep.join(newPath)

        optStr = ""
        if v1 == 1:
            optStr = optStr + " -v1"
        if v2c == 1:
            optStr = optStr + " -v2c"
        #if modifySysName.get() == 1:
            #optStr = optStr + " -s"
        #if webServer.get() == 1:
            #optStr = optStr + " -w"
        #if minDump.get() == 1:
            #optStr = optStr + " -m"
        if ranDm == 1:
            optStr = optStr + " -rd"
        # Figure out where snmpsim.py(c) is based on location of this file.
        snmpsim_loc = os.path.dirname(os.path.abspath(__file__)) + "/" + "snmpsimN.py"
        if not os.path.exists(snmpsim_loc):
            snmpsim_loc = snmpsim_loc + "c"
        log_detail = ""
        log_add = ""
        #table_return = []
        table = list(table)
        for row in table:
            row = list(row)
            state = row[3]
            dump_file = row[2]
            filePath = folder + "/" + dump_file
            port = row[1]
            #ip_address = row[0]
            if state != 'Running':
                if os.path.exists(filePath):
                    cmd = 'python "%s" %s -p %s -f "%s"' % (snmpsim_loc, optStr, port, filePath)
                    proc = subprocess.Popen(cmd)
                    #pid.append(proc.pid)
                    row[4] = proc.pid
                else:
                    row[3] = 'File Not Found'
                    row[4] = '---'

            #table_return.append(row)
            yield row
            log_add = '%s,%s,%s,%s\n' % (row[0], row[1], row[2], row[5])
            log_detail += log_add
        if log_detail:
            log_path = folder + "/" + "List_of_Mibdumps.csv"
            log_open = open(log_path, 'w')
            log_open.write(log_detail)
            log_open.close()
            sleep(2)
        #return table_return, pid
        #snmp_get_sysoid()

