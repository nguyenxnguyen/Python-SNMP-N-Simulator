from Tkinter import *
from string import join
import tkFileDialog, tkMessageBox,  os, sys, re
from MultiListbox import MultiListbox
import subprocess
import signal
from time import sleep
from datetime import datetime, timedelta
from access_file import AccessFile
from sim_extend import SimExtend
from uim import UimBuild, UimDevice
import ttk
from xml.etree.ElementTree import parse


def auto_log(message):
    import logging, os
    folder = os.path.dirname(os.path.abspath(__file__))
    log_path = folder + '/log_detail.log'
    logging.basicConfig(filename=log_path, level=logging.DEBUG,
                        format='%(asctime)s \n'
                               '\t%(levelname)s : %(name)s : %(module)s : %(message)s')
    logger = logging.getLogger(__name__)
    logger.error(message)


class MyDialog:
    def __init__(self, parent):
        top = self.top = Toplevel(parent)
        self.myLabel1 = Label(top, text='Enter TeamCity Username')
        self.myLabel1.pack()
        self.myEntryBox1 = Entry(top)
        self.myEntryBox1.pack()
        self.myLabel2 = Label(top, text='Enter TeamCity Password')
        self.myLabel2.pack()
        self.myEntryBox2 = Entry(top, show="*")
        self.myEntryBox2.pack()
        self.mySubmitButton = Button(top, text='Submit', command=self.send)
        self.mySubmitButton.pack()

    def send(self):
        self.tc_username = self.myEntryBox1.get()
        self.tc_password = self.myEntryBox2.get()
        self.top.destroy()


class MainApplication(Frame):
    def __init__(self, master, *args, **kwargs):
        Frame.__init__(self, master, *args, **kwargs)
        self.pid = []
        self.ports = []
        self.ip_addresses = []
        self.i1 = 0
        self.i2 = 0
        self.i3 = 0
        self.loop = 0
        self.timer = 0
        folder = os.path.dirname(os.path.abspath(__file__))
        f_path = folder + '/setting.xml'
        if os.path.exists(f_path):
            tree = parse(f_path)
            top = tree.getroot()
            self.nim_path = top.find('nim_path').text
            self.schedule_time = top.find('schedule_time').text
            self.timeout = top.find('timeout').text
        else:
            self.nim_path = 'c:/Program Files (x86)/Nimsoft'
            self.schedule_time = 1
            self.timeout = 10
        import atexit
        atexit.register(self.goodbye)

        if 'robot' in os.environ:
            self.robot = os.getenv('robot')
        else:
            self.robot = ''

    @staticmethod
    def update_python_sim():
        folder = os.path.dirname(os.path.abspath(__file__))
        file_path = folder + '/update_python_sim.py'
        echo_off = '@echo off'
        cmd_1 = 'taskkill /IM python.exe /F > nul'
        cmd_2 = 'c:/Python27/python.exe %s > nul' % file_path
        f_path = folder + "/" + "starting_clean_install.bat"
        if os.path.exists(f_path):
            os.remove(f_path)
        f_open = open(f_path, 'w')
        f_open.write(echo_off + '\n' + cmd_1 + '\n' + cmd_2 + '\n')
        f_open.write('start /b "" cmd /c del "%~f0"&exit /b')
        f_open.close()
        cmd = 'start cmd.exe /c "%s"' % f_path
        os.system(cmd)

    def check_version(self):
        ans = AccessFile(self).check_version()
        if ans:
            self.update_python_sim()

    def save_setting(self):
        nim_path = nim_path_entry.get()
        schedule_time = schedule_box.get()
        timeout = timeout_entry.get()
        AccessFile(self).write_setting_XML(nim_path, schedule_time, timeout)

    @staticmethod
    def new_ip(i1, i2, i3):
        i1 = int(i1)
        i2 = int(i2)
        i3 = int(i3)
        i3 += 1
        if i3 > 255:
            i3 = 1
            i2 += 1
            if i2 > 255:
                i2 = 1
                i1 += 1
                if i1 > 255:
                    sys.exit()
        return i1, i2, i3

    def insert_table(self, folder, file_read):
        ports = list(self.ports)
        if ports:
            last_port = ports[-1]
        else:
            last_port = int(port_entry.get()) - 1
        ip_addresses = list(self.ip_addresses)
        if ip_addresses:
            last_ip = str(ip_addresses[-1])
            octets = last_ip.split('.')
            i1 = octets[1]
            i2 = octets[2]
            i3 = octets[3]
        else:
            i1 = self.i1
            i2 = self.i2
            i3 = self.i3
        port = int(last_port)

        # First time getting file, load everything from List_Files
        if file_read and mlb.size() == 0:
            for line in file_read:
                line_split = line.split(',')
                file_path = folder + '/' + line_split[2]
                if os.path.exists(file_path):
                    state = 'Available'
                else:
                    state = 'File Not Found'
                mlb.insert(END, ('%s' % line_split[0],
                                 '%s' % line_split[1],
                                 '%s' % line_split[2],
                                 '%s' % state, '---', '---'))
                mlb.pack(expand=YES, fill=BOTH)
                ip_addresses.append(line_split[0])
                last_ip = str(ip_addresses[-1])
                octets = last_ip.split('.')
                i1 = octets[1]
                i2 = octets[2]
                i3 = octets[3]
                ports.append(line_split[1])
                last_port = ports[-1]
                port = int(last_port)

        # Already have data on the mlb, insert newly data into it
        if True:
            if mlb.size() > 0:
                table = mlb.get(0, mlb.size() - 1)
            else:
                table = []
            for dump_file in os.listdir(folder):
                if dump_file.endswith(".mdr"):
                    flag_newly = 1
                    for row in table:
                        if dump_file == row[2]:
                            flag_newly = 0
                            break
                        else:
                            continue
                    if flag_newly == 1:
                        port += 1
                        ports.append(str(port))
                        i1, i2, i3 = self.new_ip(i1, i2, i3)
                        ip_address = '127.%s.%s.%s' % (str(i1), str(i2), str(i3))
                        ip_addresses.append(ip_address)
                        dump_file = dump_file.encode('ascii', 'ignore')
                        state = 'Newly Added'
                        mlb.insert(END, ('%s' % ip_address, 
                                         '%s' % str(port), 
                                         '%s' % dump_file, 
                                         '%s' % state, '---', '---'))
                        mlb.pack(expand=YES, fill=BOTH)
                    else:
                        pass

        # Return values to self
        self.ip_addresses = ip_addresses
        self.ports = ports

    def shadow_insert_table(self, folder, file_read):
        i1 = self.i1
        i2 = self.i2
        i3 = self.i3
        ports = self.ports
        ip_addresses = self.ip_addresses
        start_port = port_entry.get()
        port = int(start_port) - 1
        table = []
        if mlb.size() > 0:
            table = mlb.get(0, mlb.size() - 1)
        if len(file_read) > 0:
            for line in file_read:
                line_split = line.split(',')
                file_path = folder + '/' + line_split[2]
                duplicate = 0
                if os.path.exists(file_path):
                    if table:
                        for row in table:
                            if line_split[2] == row[2]:
                                duplicate = 1
                                break
                            else:
                                for dump_file in os.listdir(folder):
                                    if dump_file == row[2]:
                                        duplicate = 1
                                        break
                    if duplicate == 0:
                        ip_addresses.append((line_split[0]))
                        ports.append(line_split[1])
                        mlb.insert(END, ('%s' % line_split[0], '%s' % line_split[1],
                                         '%s' % line_split[2], '---', '---', '---'))
                        mlb.pack(expand=YES, fill=BOTH)
                    else:
                        pass
                else:
                    pass
        else:
            pass

        for dump_file in os.listdir(folder):
            if dump_file.endswith(".mdr"):
                if True:
                    exist = 0
                    if len(file_read) > 0:
                        for line in file_read:
                            line_split = line.split(',')
                            if dump_file == line_split[2]:
                                exist = 1
                                break
                    elif table:
                        for row in table:
                            if dump_file == row[2]:
                                exist = 1
                                break
                            else:
                                pass

                    if exist == 0:
                        port += 1
                        while str(port) in ports:
                            port += 1
                        ports.append(str(port))
                        i1, i2, i3 = self.new_ip(i1, i2, i3)
                        ip_address = '127.%s.%s.%s' % (str(i1), str(i2), str(i3))
                        while ip_address in ip_addresses:
                            i1, i2, i3 = self.new_ip(i1, i2, i3)
                            ip_address = '127.%s.%s.%s' % (str(i1), str(i2), str(i3))
                        ip_addresses.append(ip_address)
                        # state = snmp_get_sysoid(ip_address, str(port))
                        dump_file = dump_file.encode('ascii', 'ignore')
                        mlb.insert(END, ('%s' % ip_address, '%s' % str(port), '%s' % dump_file, '---', '---', '---'))
                        mlb.pack(expand=YES, fill=BOTH)

    def snmp_get_sysoid(self):
        folder_p = folder_entry.get()
        if mlb.size() > 0:
            table_p = mlb.get(0, mlb.size() - 1)
            mlb.delete(0, mlb.size() - 1)
            table_p = list(SimExtend(self).snmp_get_sysoid(folder_p, table_p))
            if table_p:
                for row in table_p:
                    mlb.insert(END,
                               ('%s' % row[0],
                                '%s' % row[1],
                                '%s' % row[2],
                                '%s' % row[3],
                                '%s' % row[4],
                                '%s' % row[5]))
                    mlb.pack(expand=YES, fill=BOTH)

    def stop_sim(self):
        if mlb.size() > 0:
            table = mlb.get(0, mlb.size() - 1)
            folder_p = folder_entry.get()
            table_p = list(SimExtend(self).stop_sim(table))
            if table_p:
                table_p = SimExtend(self).snmp_get_sysoid(folder_p, table_p)
                if table_p:
                    mlb.delete(0, mlb.size() - 1)
                    for row in table_p:
                        mlb.insert(END, ('%s' % row[0],
                                         '%s' % row[1],
                                         '%s' % row[2],
                                         '%s' % row[3],
                                         '%s' % row[4],
                                         '%s' % row[5]))
                        mlb.pack(expand=YES, fill=BOTH)
                self.snmp_get_sysoid()
                self.pid = []

    def run_sim(self):
        if mlb.size() > 0:
            v1_p = v1.get()
            v2c_p = v2c.get()
            ranDm_p = ranDm.get()
            #pid_p = self.pid
            table_p = mlb.get(0, mlb.size() - 1)
            folder_p = folder_entry.get()
            mlb.delete(0, mlb.size() - 1)
            table_p = SimExtend(self).run_sim(v1_p, v2c_p, ranDm_p, table_p, folder_p)
            for row in table_p:
                if row[4] != '---':
                    self.pid.append(row[4])
                mlb.insert(END, ('%s' % row[0],
                                 '%s' % row[1],
                                 '%s' % row[2],
                                 '%s' % row[3],
                                 '%s' % row[4],
                                 '%s' % row[5]))
                mlb.pack(expand=YES, fill=BOTH)
            self.snmp_get_sysoid()

    def get_file(self):
        results_get_file = list(AccessFile(self).get_file())
        folder = results_get_file[0]
        file_read = results_get_file[1:None]
        folder_entry.delete(0, END)
        folder_entry.insert(INSERT, folder)
        self.insert_table(folder, file_read)
        #if mlb.size() > 0:
        if False:
            table = mlb.get(0, mlb.size() - 1)
            log_detail = ''
            for row in table:
                log_add = '%s,%s,%s,%s\n' % (row[0], row[1], row[2], row[5])
                log_detail += log_add
            if log_detail:
                log_path = folder + "/" + "List_of_Mibdumps.csv"
                log_open = open(log_path, 'w')
                log_open.write(log_detail)
                log_open.close()

    def write_file(self, file_name, body):
        AccessFile(self).write_file(file_name, body)

    def deploy(self):
        inputDialog = MyDialog(root)
        root.wait_window(inputDialog.top)
        robot_path_p = robot_entry.get()
        username_p = user_entry.get()
        password_p = pass_entry.get()
        nim_path_p = nim_path_entry.get()
        UimBuild(self).deploy(robot_path_p, username_p, password_p, nim_path_p,
                              inputDialog.tc_username, inputDialog.tc_password)

    def discover(self):
        folder_p = folder_entry.get()
        robot_path_p = robot_entry.get()
        username_p = user_entry.get()
        password_p = pass_entry.get()
        timeout_p = timeout_entry.get()
        nim_path_p = nim_path_entry.get()
        if mlb.size() > 0:
            table_p = mlb.get(0, mlb.size() - 1)
            UimDevice(self).discover(robot_path_p, username_p, password_p, table_p, timeout_p, nim_path_p, folder_p)

    def rediscover(self):
        folder_p = folder_entry.get()
        robot_path_p = robot_entry.get()
        username_p = user_entry.get()
        password_p = pass_entry.get()
        timeout_p = timeout_entry.get()
        nim_path_p = nim_path_entry.get()
        if mlb.size() > 0:
            table_p = mlb.get(0, mlb.size() - 1)
            UimDevice(self).rediscover(robot_path_p, username_p, password_p, table_p, timeout_p, nim_path_p, folder_p)

    @staticmethod
    def get_hosts():
        username_p = user_entry.get()
        password_p = pass_entry.get()
        robot_path_p = robot_entry.get()
        nim_path_p = nim_path_entry.get()
        if password_p == '':
            password_p = '1QAZ2wsx'
        ip_addresses = []
        cmd_get_all_device = '"%s/bin/pu.exe" -u %s -p %s ' \
                             '%ssnmpcollector get_snmp_device ALL' \
                             % (nim_path_p, username_p, password_p, robot_path_p)
        response = os.popen(cmd_get_all_device).read()
        response_split = response.split('\n')
        for line in response_split:
            if 'IP = ' in line:
                ip_address = line.replace('IP = ', '')
                ip_addresses.append(ip_address)
        ip_addresses.sort()
        ip_combobox['values'] = ip_addresses
        return ip_addresses

    def get_component(self):
        username_p = user_entry.get()
        password_p = pass_entry.get()
        folder_p = folder_entry.get()
        nim_path_p = nim_path_entry.get()
        ip_addresses = []
        if mlb.size() > 0:
            table = mlb.get(0, mlb.size() - 1)
            for row in table:
                row = list(row)
                ip_address = row[0]
                ip_addresses.append(ip_address)
            #file_paths = list(UimDevice(self).get_component(username_p, password_p, ip_addresses, folder_p, nim_path_p))
            UimDevice(self).get_component(username_p, password_p, ip_addresses, folder_p, nim_path_p)
        #return file_paths

    def get_some_component(self):
        username_p = user_entry.get()
        password_p = pass_entry.get()
        nim_path_p = nim_path_entry.get()
        folder_p = folder_entry.get()
        if not folder_p:
            folder_p = os.path.expanduser('~/Desktop')
        ip_addresses = []
        ip_address = ip_combobox.get()
        if ip_address != '---':
            ip_addresses.append(ip_address)
        else:
            ip_addresses = self.get_hosts()
        UimDevice(self).get_component(username_p, password_p, ip_addresses, folder_p, nim_path_p)

    def rm_device(self):
        robot_path_p = robot_entry.get()
        username_p = user_entry.get()
        password_p = pass_entry.get()
        nim_path_p = nim_path_entry.get()
        if mlb.size() > 0:
            table_p = mlb.get(0, mlb.size() - 1)
            UimDevice(self).rm_device(robot_path_p, username_p, password_p, table_p, nim_path_p)

    def goodbye(self):
        print("You are now leaving the Python SimSNMP.")
        pid = self.pid
        if pid != [] and pid != '---':
            for child in pid:
                os.kill(child, signal.SIGTERM)
        else:
            pass

    def schedule(self):
        if self.loop > 0:
            self.deploy()
            sleep(2600)
            self.rediscover()
            sleep(600)
            self.get_component()
        else:
            self.discover()
        now_click = datetime.now()
        set_time = int(schedule_box.get())
        set_datetime = now_click.replace(hour=set_time, minute=00)
        delta_time = set_datetime - now_click
        if delta_time < timedelta(seconds=0):
            delta_time += timedelta(seconds=24*60*60)
        #schedule_button['relief'] = 'flat'
        #schedule_button['text'] = ''
        schedule_button.configure(state=DISABLED)
        schedule_time_label['text'] = 'Rediscover at: %s:00' % str(set_time)
        schedule_time_label['fg'] = 'dark green'
        schedule_time_label['font'] = 'Helvetica 10 bold'
        self.loop += 1
        micro_seconds = delta_time.seconds*1000
        root.after(micro_seconds, self.schedule)

    @staticmethod
    def parse_XML():
        pass


if __name__ == "__main__":
    root = Tk()
    root.resizable(width=False, height=False)
    root.title("Python SNMP N-Simulator ver 1.0")

    # new notebook
    note_book = ttk.Notebook(root)
    page1 = ttk.Frame(note_book)
    page2 = ttk.Frame(note_book)
    page3 = ttk.Frame(note_book)
    note_book.add(page1, text='Setting')
    note_book.add(page2, text='General')
    note_book.add(page3, text='Extensions')
    note_book.pack(expand=1, fill="both")
    note_book.select(1)

    # This is main application
    #try:
     #   app = MainApplication(root)
    #except Exception as err:
     #   auto_log(err)
    app = MainApplication(root)
    #app.check_version()

    # ----------------------------------- PAGE 1 # -----------------------------------
    frame11 = Frame(page1)
    frame11.grid(column=1, row=1, sticky=E)

    frame12 = Frame(page1)
    frame12.grid(column=1, row=2, sticky=W)

    frame13 = Frame(page1)
    frame13.grid(column=1, row=3, sticky=W)

    frame14 = Frame(page1)
    frame14.grid(column=1, row=4, sticky=W)

    frame15 = Frame(page1)
    frame15.grid(column=1, row=5, sticky=E)

    # Check Version button
    check_version_button = Button(frame11, text="Check Version",
                                  command=app.check_version, font='Times 8', width=15)
    check_version_button.pack()

    blank_label = Label(frame12, text="", width=5)
    blank_label.grid(column=1, row=1, sticky=W)

    blank_label = Label(frame12, text="", width=5)
    blank_label.grid(column=1, row=2, sticky=W)

    # Browse Probe
    nim_path_label = Label(frame12, text="PATH of NIMSOFT:", width=25)
    nim_path_label.grid(column=2, row=2)
    nim_path_entry = Entry(frame12, width=128)
    nim_path_entry.insert(INSERT, app.nim_path)
    nim_path_entry.grid(column=3, row=2, sticky=W)

    blank_label = Label(frame12, text="", width=5)
    blank_label.grid(column=4, row=2, sticky=W)

    blank_label = Label(frame13, text="", width=5)
    blank_label.grid(column=1, row=1, sticky=W)

    # Schedule box
    schedule_label = Label(frame13, text="  Daily Rediscover Schedule:", width=25)
    schedule_label.grid(column=2, row=1)
    var = StringVar(root)
    var.set(app.schedule_time)
    schedule_box = Spinbox(frame13, from_=1, to=24, state='readonly', wrap='true',
                           textvariable=var, width=10)
    schedule_box.grid(column=3, row=1, sticky=W)

    schedule_format_label = Label(frame13, text="(24 hour format)")
    schedule_format_label.grid(column=4, row=1, sticky=W)

    blank_label = Label(frame14, text="", width=5)
    blank_label.grid(column=1, row=1, sticky=W+E+N+S)

    # Timeout entry
    timeout_label = Label(frame14, text="               Discovery Timeout:", width=25)
    timeout_label.grid(column=2, row=1)
    timeout_entry = Entry(frame14, width=10)
    timeout_entry.insert(INSERT, app.timeout)
    timeout_entry.grid(column=3, row=1)
    timeout_format_label = Label(frame14, text="seconds")
    timeout_format_label.grid(column=4, row=1)

    # Save setting button
    save_setting_button = Button(frame15, text="Save Setting",
                                 command=app.save_setting, font='Times 10 bold', width=15)
    save_setting_button.pack()

    # ----------------------------------- PAGE 2 # -----------------------------------
    frame21 = Frame(page2)
    frame21.grid(column=1, row=1, sticky=W)

    frame22 = Frame(page2)
    frame22.grid(column=1, row=2, sticky=W)

    frame23 = Frame(page2)
    frame23.grid(column=1, row=3, sticky=W)

    frame24 = Frame(page2)
    frame24.grid(column=1, row=4, sticky=W)

    frame25 = Frame(page2)
    frame25.grid(column=1, row=5, sticky=W)

    frame26 = Frame(page2)
    frame26.grid(column=1, row=6, sticky=W)

    frame27 = Frame(page2)
    frame27.grid(column=1, row=7, sticky=W+E+N+S+N+S)

    # Frame1------------------------------------------
    blank_label = Label(frame21, text="", width=5)
    blank_label.grid(column=1, row=1, sticky=W)

    # Browse folder
    folder_label = Label(frame21, text="Dump folder:", width=15)
    folder_label.grid(column=2, row=1, sticky=W)
    folder_entry = Entry(frame21, width=128)
    #folder_entry.insert(INSERT, dump_folder)
    folder_entry.grid(column=3, row=1, sticky=W)

    blank_label = Label(frame21, text="", width=1)
    blank_label.grid(column=4, row=1, sticky=W)

    # Browse button
    browse_button = Button(frame21, text="Browse", command=app.get_file, width=10)
    browse_button.grid(column=5, row=1, sticky=W)

    blank_label = Label(frame21, text="", width=5)
    blank_label.grid(column=6, row=1, sticky=W)

    # Frame2------------------------------------------
    blank_label = Label(frame22, text="", width=5)
    blank_label.grid(column=1, row=1, sticky=W)

    # Robot
    robot_label = Label(frame22, text="Robot:", width=15)
    robot_label.grid(column=2, row=1, sticky=W)
    robot_entry = Entry(frame22, width=70)
    robot_entry.insert(INSERT, app.robot)
    robot_entry.grid(column=3, row=1, sticky=W)

    blank_label = Label(frame22, text="", width=5)
    blank_label.grid(column=4, row=1, sticky=W)

    # Username
    user_label = Label(frame22, text="User:", width=10)
    user_label.grid(column=5, row=1, sticky=W)
    user_entry = Entry(frame22, width=16)
    user_entry.insert(INSERT, 'administrator')
    user_entry.grid(column=6, row=1, sticky=W)

    blank_label = Label(frame22, text="", width=5)
    blank_label.grid(column=7, row=1, sticky=W)

    # Password
    pass_label = Label(frame22, text="Password:", width=10)
    pass_label.grid(column=8, row=1, sticky=W)
    pass_entry = Entry(frame22, width=20, show="*")
    pass_entry.grid(column=9, row=1, sticky=W)

    # Frame3------------------------------------------
    blank_label = Label(frame23, text="", width=5)
    blank_label.grid(column=1, row=1)

    # Port
    port_label = Label(frame23, text="Start Port:", width=15)
    port_label.grid(column=2, row=1, sticky=W)
    port_entry = Entry(frame23, width=16)
    port_entry.insert(INSERT, 64001)
    port_entry.grid(column=3, row=1, sticky=W)

    blank_label = Label(frame23, text="", width=1)
    blank_label.grid(column=4, row=1)

    # V1 checkbox
    v1 = IntVar()
    v1CheckBox = Checkbutton(frame23, text="SNMPv1 ", variable=v1, width=10)
    v1CheckBox.select()
    v1CheckBox.grid(column=5, row=1)

    # V2 checkbox
    v2c = IntVar()
    v2cCheckBox = Checkbutton(frame23, text="SNMPv2c", variable=v2c, width=10)
    v2cCheckBox.select()
    v2cCheckBox.grid(column=6, row=1)

    # Random checkbox
    ranDm = IntVar()
    ranDmCheckBox = Checkbutton(frame23, text="Random", variable=ranDm, width=10)
    ranDmCheckBox.grid(column=7, row=1)

    blank_label = Label(frame23, text="", width=15)
    blank_label.grid(column=8, row=1)

    # Schedule time label
    schedule_time_label = Label(frame23, text="", width=17)
    schedule_time_label.grid(column=9, row=1, sticky=W+E+N+S+N+S)

    # Frame4------------------------------------------
    blank_label = Label(frame24, text="", width=5)
    blank_label.grid(column=1, row=1, sticky=W+E+N+S)

    blank_label = Label(frame24, text="", width=5)
    blank_label.grid(column=1, row=2, sticky=W+E+N+S)

    blank_label = Label(frame24, text="", width=5)
    blank_label.grid(column=2, row=2, sticky=W+E+N+S)

    # Stop button
    stop_button = Button(frame24, text=" STOP SIMULATOR ", command=app.stop_sim, relief=RAISED)
    stop_button.grid(column=3, row=2, sticky=W+E+N+S)

    blank_label31 = Label(frame24, text="", width=3)
    blank_label31.grid(column=4, row=2, sticky=W+E+N+S)

    # Run button
    run_button = Button(frame24, text=" RUN SIMULATOR ", command=app.run_sim, relief=RAISED)
    run_button.grid(column=5, row=2, sticky=W+E+N+S)

    blank_label32 = Label(frame24, text="", width=3)
    blank_label32.grid(column=6, row=2, sticky=W+E+N+S)

    # Get latest build button
    run_button = Button(frame24, text=" DEPLOY LATEST DCD&CI ",
                        command=app.deploy, relief=RAISED)
    run_button.grid(column=7, row=2, sticky=W+E+N+S)

    blank_label = Label(frame24, text="", width=3)
    blank_label.grid(column=8, row=2, sticky=W+E+N+S)

    # Discover button
    discover_button = Button(frame24, text=" DISCOVER by UIM ",
                             command=app.discover, relief=RAISED)
    discover_button.grid(column=9, row=2, sticky=W+E+N+S)

    blank_label = Label(frame24, text="", width=3)
    blank_label.grid(column=10, row=2, sticky=W+E+N+S)

    # Rediscover button
    rediscover_button = Button(frame24, text="  REDISCOVER  ",
                               command=app.rediscover, relief=RAISED)
    rediscover_button.grid(column=11, row=2, sticky=W+E+N+S)

    blank_label = Label(frame24, text="", width=3)
    blank_label.grid(column=12, row=2, sticky=W+E+N+S)

    # Check status button
    run_button = Button(frame24, text=" CHECK STATUS ",
                        command=app.snmp_get_sysoid, relief=RAISED)
    run_button.grid(column=13, row=2, sticky=W+E+N+S)

    blank_label = Label(frame24, text="", width=3)
    blank_label.grid(column=14, row=2, sticky=W + E + N + S)

    # Schedule button
    schedule_button = Button(frame24, text="   SCHEDULE   ",
                             command=app.schedule, relief=RAISED)
    schedule_button.grid(column=15, row=2, sticky=W+E+N+S)

    blank_label = Label(frame24, text="", width=3)
    blank_label.grid(column=16, row=2, sticky=W+E+N+S)

    # Frame5------------------------------------------

    blank_label = Label(frame25, text="", width=140)
    blank_label.pack()

    # Frame6------------------------------------------

    # Table
    Label(frame26, text='\n',).pack(side=RIGHT)
    blank_label = Label(frame26, text="", width=5)
    blank_label.pack(side=LEFT)
    mlb = MultiListbox(frame26, 20, (('IP Address', 15), ('Port', 10), ('Mibdump', 70), ('Status', 15),
                                    ('PID', 10), ('Sys OID', 35)))
    # Remove discovered device
    rm_button = Button(frame27, text=" REMOVE ALL DISCOVERED DEVICES by THIS SIMULATOR ",
                       command=app.rm_device, relief=RAISED, font=("Helvetica", 10))
    rm_button.pack()

    # ----------------------------------- PAGE 3 # -----------------------------------
    frame31 = Frame(page3)
    frame31.grid(column=1, row=1, sticky=W)

    frame32 = Frame(page3)
    frame32.grid(column=1, row=2, sticky=W)

    frame33 = Frame(page3)
    frame33.grid(column=1, row=3, sticky=W)

    frame34 = Frame(page3)
    frame34.grid(column=1, row=4, sticky=W)

    frame35 = Frame(page3)
    frame35.grid(column=1, row=5, sticky=W)

    # Host label
    blank_label = Label(frame31, text="1.", width=15)
    blank_label.grid(column=1, row=1, sticky=W+E+N+S)
    ip_label = Label(frame31, text="Host: ", width=5)
    ip_label.grid(column=2, row=1, sticky=W+E+N+S)

    # Host combobox
    ip_combobox = ttk.Combobox(frame31)
    ip_combobox.grid(column=3, row=1, sticky=W+E+N+S)
    ip_combobox.insert(INSERT, '---')

    # Check HOST button
    check_host_button = Button(frame31, text=" CHECK HOSTS ", command=app.get_hosts, relief=RAISED)
    check_host_button.grid(column=4, row=1, sticky=W+E+N+S)

    blank_label = Label(frame31, text="", width=5)
    blank_label.grid(column=5, row=1, sticky=W+E+N+S)

    # Get component button
    get_component_button = Button(frame31, text=" GET DEVICE COMPONENT ",
                                  command=app.get_some_component, relief=RAISED)
    get_component_button.grid(column=6, row=1, sticky=W+E+N+S)

    blank_label = Label(frame32, text="", width=5)
    blank_label.grid(column=1, row=1, sticky=W+E+N+S)

    # Update button
    #update_button = Button(frame32, text=" UPDATE PYTHON SIM ",
    #                       command=app.update_python_sim, relief=RAISED)
    #update_button.grid(column=2, row=1, sticky=W+E+N+S)

    root.mainloop()
    sys.exit(0)
