import requests
from requests.auth import HTTPBasicAuth
import shutil
import os
import re
import subprocess
from datetime import datetime
from time import sleep, time
from n_function import *


class UimBuild(object):
    def __init__(self, *args, **kwargs):
        pass

    @staticmethod
    def get_build(nim_path, tc_username, tc_password):
        if os.path.exists(nim_path):
            folder = '%s/for_testing_DCD/' % nim_path
            if not os.path.exists(folder):
                os.mkdir(folder)
            link_artifact = 'http://artifactory.dev.fco/artifactory/libs-release-probes-local/com/nimsoft/' \
                            'ci_defn_pack/[RELEASE]/ci_defn_pack-[RELEASE].zip'
            response_artifact = requests.get(link_artifact, stream=True)
            artifact_header = response_artifact.headers['Content-Disposition']
            pattern_ci = re.compile('ci_defn_pack.[^";]*.zip')
            ci_name = pattern_ci.findall(artifact_header)[0]
            ci_path = '%s/for_testing_DCD/' % nim_path + str(ci_name)
            with open(ci_path, 'wb') as out_file_artifact:
                shutil.copyfileobj(response_artifact.raw, out_file_artifact)

            link_teamcity = 'http://build.dev.fco/teamcity/repository/download/' \
                            'Uim_Snmpc_SnmpDeviceCertificationDeployer_SnmpDeviceCertificationDeployer/' \
                            'lastSuccessful/Device_Certification_Deployer.zip?branch=develop%2FDCD_current_dev'
            response_teamcity = requests.get(link_teamcity, auth=HTTPBasicAuth(tc_username, tc_password), stream=True)
            teamcity_header = response_teamcity.headers['Content-Disposition']
            pattern_dcd = re.compile('Device_Certification_Deployer.*.zip')
            dcd_name = pattern_dcd.findall(teamcity_header)[0]
            dcd_path = '%s/for_testing_DCD/' % nim_path + str(dcd_name)
            with open(dcd_path, 'wb') as out_file_teamcity:
                shutil.copyfileobj(response_teamcity.raw, out_file_teamcity)
            return ci_name, dcd_name
        else:
            raise Exception('The system can not find the UIM Path')

    def deploy(self, nim_path, username, password, robot_path, tc_username, tc_password):
        if os.path.exists(nim_path):
            ci, dcd = self.get_build(nim_path, tc_username, tc_password)
            ci_name = 'ci_defn_pack.zip'
            dcd_name = 'Device_Certification_Deployer.zip'
            ci_name = ci_name.replace('.zip', '')
            dcd_name = dcd_name.replace('.zip', '')
            cmd_prefix = '\"%s/bin/pu.exe\" -u %s -p %s %s' \
                         % (nim_path, username, password, robot_path)
            cmd_set_dir = '%sdistsrv archive_set_dir for_testing_DCD' % cmd_prefix
            cmd_inst_request_dcd = '%scontroller inst_request %s' % (cmd_prefix, dcd_name)
            cmd_inst_request_ci = '%scontroller inst_request %s' % (cmd_prefix, ci_name)
            proc1 = subprocess.Popen(cmd_set_dir)
            proc1.wait()
            proc2 = subprocess.Popen(cmd_inst_request_dcd)
            proc2.wait()
            proc3 = subprocess.Popen(cmd_inst_request_ci)
            proc3.wait()
            timeout = 1800
            UimDevice().restart_snmpc(nim_path, username, password, robot_path, timeout)
            UimDevice().restart_nis(nim_path, username, password, robot_path, timeout)
        else:
            raise Exception('The system can not find the UIM Path')


class UimDevice(object):
    def __init__(self, *args, **kwargs):
        pass

    @staticmethod
    def check_state(cmd_get_device, ip_address):
        from time import time
        ts = time()
        t = 0
        error_msg = 'Failed'
        while t < 900:
            response = os.popen(cmd_get_device).read()
            if not response:
                print 'UIM Server is not responding'
                error_msg = 'Unknown'
                break
            else:
                pattern_state = re.compile('.*_discoState.*')
                resp = pattern_state.findall(response)
                if resp:
                    state = resp[0]
                    if 'complete' in state.lower():
                        return 'Completed'
                    else:
                        print 'Waiting for rediscovery process of %s to complete...' % ip_address
                        sleep(3)
                        t = time() - ts
                else:
                    print "Device was not discovered"
                    error_msg = 'Not discovered'
                    break
        return error_msg

    @staticmethod
    def restart_snmpc(nim_path, username, password, robot_path, timeout):
        folder = os.path.dirname(os.path.abspath(__file__))
        f_path = '%s/cmd_snmpc_restart.bat' % folder
        if not os.path.exists(f_path):
            cmd_prefix = '\"%s/bin/pu.exe\" -u %s -p %s %s' % (nim_path, username, password, robot_path)
            cmd_snmpc_restart = """TIMEOUT /T %s\n%ssnmpcollector _restart\n""" % (timeout, cmd_prefix)
            f_open = open(f_path, 'w')
            f_open.write('@echo off\n')
            f_open.write(cmd_snmpc_restart)
            f_open.close()
        else:
            pass
        cmd = 'start cmd.exe /c \"%s\"' % f_path
        subprocess.call(cmd, shell=True)

    @staticmethod
    def restart_nis(nim_path, username, password, robot_path, timeout):
        folder = os.path.dirname(os.path.abspath(__file__))
        f_path = '%s/cmd_nis_restart.bat' % folder
        if not os.path.exists(f_path):
            cmd_prefix = '\"%s/bin/pu.exe\" -u %s -p %s %s' % (nim_path, username, password, robot_path)
            cmd_nis_restart = """TIMEOUT /T %s\n%snis_server _restart\n""" % (timeout, cmd_prefix)
            f_open = open(f_path, 'w')
            f_open.write('@echo off\n')
            f_open.write(cmd_nis_restart)
            f_open.close()
        else:
            pass
        cmd = 'start cmd.exe /c \"%s\"' % f_path
        subprocess.call(cmd, shell=True)
        #sleep(10)

    @staticmethod
    def discover(nim_path, username, password, robot_path, folder, table, discovered_hosts, timeout):
        #log_detail = ''
        if os.path.exists(nim_path):
            folder_temp = '%s/Temp' % folder
            timeout = int(timeout)
            if not os.path.exists(folder_temp):
                os.mkdir(folder_temp)
            else:
                pass
            f_path = '%s/cmd_snmpc_discover.bat' % folder_temp
            f_open = open(f_path, 'w')
            f_open.write('@echo off\n')
            for row in table:
                if not row:
                    continue
                row = list(row)
                dump_file = row[2]
                state = row[3]
                port = row[1]
                ip_address = row[0]
                cmd_get_device = '\"%s/bin/pu.exe\" -u %s -p %s ' \
                                 '%ssnmpcollector get_snmp_device %s' \
                                 % (nim_path, username, password, robot_path, ip_address)
                if ip_address in discovered_hosts:
                    row[6] = UimDevice().check_state(cmd_get_device, ip_address)
                    yield row
                    continue
                if state == 'Running':
                    cmd_dis = '\"%s/bin/pu.exe\" -u %s -p %s %ssnmpcollector add_snmp_device ' \
                              '%s snmpv2c \"%s\" %s public "" "" "" "" ""' \
                              % (nim_path, username, password, robot_path, ip_address, dump_file, port)
                    subprocess.call(cmd_dis, shell=True)
                    #command = "start /wait cmd /c %s" % cmd_dis
                    #os.system(command)
                    for i in xrange(timeout):
                        print timeout - i
                        sleep(1)
                    discover_state = UimDevice().check_state(cmd_get_device, ip_address)
                    print 'Discovery process of %s is %s' % (ip_address, discover_state)
                    row[6] = str(discover_state)
                    #log_add = '%s,%s,%s,%s\n' % (ip_address, port, dump_file, sys_oid)
                    #log_detail += log_add
                else:
                    pass
                yield row
            #log_path = folder + "/" + "List_of_Discovered_Devices.csv"
            #log_open = open(log_path, 'w')
            #log_open.write(log_detail)
            #log_open.close()
        else:
            raise Exception('The system can not find the UIM Path')

    @staticmethod
    def rediscover(nim_path, username, password, robot_path, folder, table, discovered_hosts, timeout):
        if os.path.exists(nim_path):
            folder_temp = '%s/Temp' % folder
            if not os.path.exists(folder_temp):
                os.mkdir(folder_temp)
            else:
                pass
            f_path = '%s/cmd_snmpc_rediscover.bat' % folder_temp
            f_open = open(f_path, 'w')
            f_open.write('@echo off\n')
            for row in table:
                if not row:
                    continue
                row = list(row)
                ip_address = row[0]
                cmd_get_device = '\"%s/bin/pu.exe\" -u %s -p %s ' \
                                 '%ssnmpcollector get_snmp_device %s' \
                                 % (nim_path, username, password, robot_path, ip_address)
                if ip_address not in discovered_hosts:
                    yield row
                    continue
                if row[3] == 'Running':
                    response = os.popen(cmd_get_device).read()
                    pattern = re.compile('.*_snmpPort')
                    device_id = pattern.findall(response)[0]
                    if device_id:
                        device_id = device_id.replace('_snmpPort', '')
                        cmd_redis = '\"%s/bin/pu.exe\" -u %s -p %s %ssnmpcollector rediscover_snmp_device %s' \
                                    % (nim_path, username, password, robot_path, device_id)
                        subprocess.call(cmd_redis)
                        sleep(timeout)
                        discover_state = UimDevice().check_state(cmd_get_device, ip_address)
                        print 'Re-Discovery process of %s is %s' % (ip_address, discover_state)
                        row[6] = str(discover_state)
                    else:
                        pass
                else:
                    pass
                yield row
        else:
            raise Exception('The system can not find the UIM Path')

    @staticmethod
    def rm_device(nim_path, username, password, robot_path, table):
        if os.path.exists(nim_path):
            for row in table:
                if not row:
                    continue
                row = list(row)
                ip_address = row[0]
                cmd_get_device = '\"%s/bin/pu.exe\" -u %s -p %s ' \
                                 '%ssnmpcollector get_snmp_device %s' \
                                 % (nim_path, username, password, robot_path, ip_address)
                cmd_remove = '\"%s/bin/pu.exe\" -u %s -p ' \
                             '%s %ssnmpcollector remove_snmp_device \"%s\"' \
                             % (nim_path, username, password, robot_path, ip_address)
                subprocess.call(cmd_remove)
                row[6] = UimDevice().check_state(cmd_get_device, ip_address)
                yield row
        else:
            raise Exception('The system can not find the UIM Path')

    @staticmethod
    def get_component(nim_path, username, password, folder, ip_addresses):
        if os.path.exists(nim_path):
            folder_component = '%s/Components' % folder
            if not os.path.exists(folder_component):
                os.mkdir(folder_component)
            else:
                pass
            folder_temp = '%s/Temp' % folder
            print 'Folder contains component files: %s' % folder_component
            if not os.path.exists(folder_temp):
                os.mkdir(folder_temp)
            else:
                pass
            time_now = datetime.now()
            callback_handler = 'com.nimsoft.probes.network.snmpcollector.tools.CallbackHandler'
            snmpc_path = nim_path + '/probes/network/snmpcollector'
            temp_files = ip_addresses
            for temp in temp_files:
                if temp == 'ALL':
                    continue
                cmd_pds = 'java -cp \"%s/lib/*\";\"%s/jars/*\" %s pds \"%s\" Host %s 1' \
                          % (snmpc_path, snmpc_path, callback_handler, temp, temp)
                os.chdir(folder_temp)
                subprocess.call(cmd_pds)
                file_name = 'Component_%s_%s.xml' % (time_now.strftime("%d-%m-%y"), temp)
                file_path = folder_component + "/" + file_name
                cmd_get_component = 'java -cp \"%s/lib/*\";\"%s/jars/*\" %s ' \
                                    'callback snmpcollector get_device_component_file %s %s %s' \
                                    % (snmpc_path, snmpc_path, callback_handler, temp, username, password)
                os.chdir(folder_temp)
                #os.system(cmd_get_component)
                response = os.popen(cmd_get_component).read()
                lines = response.splitlines()
                lines[0] = '<?xml version="1.0" encoding="UTF-8"?>'
                lines[1] = ''
                lines[2] = '<root>'
                lines[-2] = ''
                lines[-1] = '</root>'
                f_open = open(file_path, 'w')
                for line in lines:
                    if line:
                        f_open.write(line)
                        f_open.write('\n')
                f_open.close()
                temp_file_name = '%s.pds' % temp
                os.remove(temp_file_name)
                #yield file_path

        else:
            raise Exception('The system can not find the UIM Path')
