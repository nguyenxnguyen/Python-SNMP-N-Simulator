import requests
from requests.auth import HTTPBasicAuth
import shutil
import os
from Tkinter import *
import re
import subprocess
from datetime import datetime
from time import sleep


class UimBuild(object):
    def __init__(self, *args, **kwargs):
        pass

    def get_build(self, nim_path, tc_username, tc_password):
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

    def deploy(self, robot_path, username, password, nim_path, tc_username, tc_password):
        #robot_path = robot_entry.get()
        #username = user_entry.get()
        #password = pass_entry.get()
        if password == '':
            password = '1QAZ2wsx'
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
        cmd_snmpc_restart = """TIMEOUT /T 1800\n%ssnmpcollector _restart\n""" % cmd_prefix
        cmd_nis_restart = """TIMEOUT /T 2000\n%snis_server _restart\n""" % cmd_prefix
        print cmd_set_dir
        proc1 = subprocess.Popen(cmd_set_dir)
        proc1.wait()
        print cmd_inst_request_dcd
        proc2 = subprocess.Popen(cmd_inst_request_dcd)
        proc2.wait()
        print cmd_inst_request_ci
        proc3 = subprocess.Popen(cmd_inst_request_ci)
        proc3.wait()
        folder = os.path.dirname(os.path.abspath(__file__))
        print folder
        f_path1 = '%s/cmd_snmpc_restart.bat' % folder
        f_open1 = open(f_path1, 'w')
        f_open1.write(cmd_snmpc_restart)
        f_open1.close()
        f_path2 = '%s/cmd_nis_restart.bat' % folder
        f_open2 = open(f_path2, 'w')
        f_open2.write(cmd_nis_restart)
        f_open2.close()
        cmd_1 = 'start cmd.exe /c \"%s\"' % f_path1
        cmd_2 = 'start cmd.exe /c \"%s\"' % f_path2
        os.system(cmd_1)
        os.system(cmd_2)
        if os.path.exists(f_path1):
            sleep(5)
            os.remove(f_path1)
        if os.path.exists(f_path2):
            sleep(5)
            os.remove(f_path2)
        #os.system('cls')


class UimDevice(object):
    def __init__(self, *args, **kwargs):
        pass

    def discover(self, robot_path, username, password, table, timeout, nim_path, folder):
        log_detail = ''
        if password == '':
            password = '1QAZ2wsx'
        #if mlb.size() > 0:
        #    table = mlb.get(0, mlb.size() - 1)
        #folder = os.path.dirname(os.path.abspath(__file__))
        folder_temp = '%s/Temp' % folder
        f_path = '%s/cmd_snmpc_discover.bat' % folder_temp
        f_open = open(f_path, 'w')
        for row in table:
            row = list(row)
            sys_oid = row[4]
            dump_file = row[2]
            state = row[3]
            port = row[1]
            ip_address = row[0]
            if state == 'Running':
                cmd_dis = '"%s/bin/pu.exe\" -u %s -p ' \
                          '%s %ssnmpcollector add_snmp_device ' \
                          '%s snmpv2c %s %s public "" "" "" "" ""\n' \
                          % (nim_path, username, password, robot_path, ip_address, dump_file, port)
                cmd_timeout = 'TIMEOUT /T %s\n' % timeout
                #print cmd_dis
                #proc = subprocess.Popen(cmd_dis)
                #proc.wait()
                f_open.write(cmd_dis)
                f_open.write(cmd_timeout)
                #os.system(cmd_dis)
                log_add = '%s,%s,%s,%s\n' % (ip_address, port, dump_file, sys_oid)
                log_detail += log_add
            else:
                pass
        f_open.close()
        cmd = 'start cmd.exe /c \"%s\"' % f_path
        os.system(cmd)
        if os.path.exists(f_path):
            sleep(5)
            os.remove(f_path)
        log_path = folder + "/" + "List_of_Discovered_Devices.csv"
        log_open = open(log_path, 'w')
        log_open.write(log_detail)
        log_open.close()

    def rediscover(self, robot_path, username, password, table, timeout, nim_path, folder):
        if password == '':
            password = '1QAZ2wsx'
        #folder = os.path.dirname(os.path.abspath(__file__))
        folder_temp = '%s/Temp' % folder
        f_path = '%s/cmd_snmpc_rediscover.bat' % folder_temp
        f_open = open(f_path, 'w')
        for row in table:
            row = list(row)
            #sys_oid = row[4]
            #dump_file = row[2]
            state = row[3]
            #port = row[1]
            ip_address = row[0]
            if state == 'Running':
                cmd_get_device = '\"%s/bin/pu.exe\" -u %s -p %s ' \
                                 '%ssnmpcollector get_snmp_device %s' \
                                 % (nim_path, username, password, robot_path, ip_address)
                response = os.popen(cmd_get_device).read()
                pattern = re.compile('.*_snmpPort')
                device_id = pattern.findall(response)[0]
                device_id = device_id.replace('_snmpPort', '')
                if device_id:
                    cmd_redis = '\"%s/bin/pu.exe\" -u %s -p %s ' \
                                '%ssnmpcollector rediscover_snmp_device %s' \
                                % (nim_path, username, password, robot_path, device_id)
                    cmd_timeout = 'TIMEOUT /T %s\n' % timeout
                    #os.system(cmd_redis)
                    f_open.write(cmd_redis)
                    f_open.write(cmd_timeout)
                else:
                    pass
            else:
                pass
        f_open.close()
        cmd = 'start cmd.exe /c \"%s\"' % f_path
        os.system(cmd)

    def rm_device(self, robot_path, username, password, table, nim_path):
        #username = user_entry.get()
        #password = pass_entry.get()
        if password == '':
            password = '1QAZ2wsx'
        #if mlb.size() > 0:
        #    table = mlb.get(0, mlb.size() - 1)
        for row in table:
            row = list(row)
            ip_address = row[0]
            cmd_remove = '"\"%s/bin/pu.exe" -u %s -p ' \
                         '%s %ssnmpcollector remove_snmp_device "%s"' \
                         % (nim_path, username, password, robot_path, ip_address)
            os.system(cmd_remove)

    def get_component(self, username, password, ip_addresses, folder, nim_path):
        if password == '':
            password = '1QAZ2wsx'
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
            cmd_pds = 'java -cp \"%s/lib/*\";\"%s/jars/*\" %s pds \"%s\" Host %s 1' \
                      % (snmpc_path, snmpc_path, callback_handler, temp, temp)
            os.chdir(folder_temp)
            os.system(cmd_pds)
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
