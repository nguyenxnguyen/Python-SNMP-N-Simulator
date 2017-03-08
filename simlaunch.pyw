from Tkinter import *
import os
import sys
from MultiListbox import MultiListbox
import signal
# from time import sleep
# from datetime import datetime, timedelta
from access_file import AccessFile
from sim_extend import SimExtend
import ttk
from xml.etree.ElementTree import parse
from n_function import auto_log
# import ScrolledText
# from simdepot import get_sim_info
from capm import CAPM


def catch_exceptions(func):
    def wrapper(*args, **kw):
        try:
            return func(*args, **kw)
        except Exception, e:
            # make a popup here with your exception information.
            print "Error: %s" % e
            auto_log(e)
    return wrapper


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
        self.info = {}
        self.folder = ''
        self.info['robot'] = ''
        folder = os.path.dirname(os.path.abspath(__file__))
        f_path = folder + '/setting.xml'
        if os.path.exists(f_path):
            tree = parse(f_path)
            top = tree.getroot()
            self.info['da_host'] = top.find('da_host').text
            self.info['dc_host'] = top.find('dc_host').text
            self.info['profile'] = top.find('profile').text
        else:
            self.info['da_host'] = ''
            self.info['dc_host'] = ''
            self.info['profile'] = ''
        import atexit
        atexit.register(self.goodbye)

    @staticmethod
    def insert_mlb_dump(table):
        for row in table:
            if not row:
                continue
            mlb_dump.insert(END,
                            ('%s' % row[0],
                             '%s' % row[1],
                             '%s' % row[2],
                             '%s' % row[3],
                             '%s' % row[4],
                             '%s' % row[5],
                             '%s' % row[6]))

    @staticmethod
    def insert_mlb_missing(table):
        pass

    def save_info(self):
        self.info['da'] = da_entry.get()
        self.info['dc'] = dc_entry.get()
        self.info['profile'] = profile_entry.get()
        AccessFile().write_setting_xml(self.info['da'], self.info['dc'], self.info['profile'])
        self.info['start_port'] = port_entry.get()
        self.info['user'] = user_entry.get()
        self.info['pass'] = pass_entry.get()
        # self.info['tc_user'] = tc_user_entry.get()
        # self.info['tc_pass'] = tc_pass_entry.get()
        missing_msg = ''
        for key, value in self.info.iteritems():
            if key == 'dc':
                continue
            if not value:
                missing_msg += 'Missing __%s__ Field\n' % key
        if missing_msg:
            pass
            # tkMessageBox.showwarning('Warning!!!', missing_msg)
            # MyPopup(root, missing_msg)
        else:
            pass

    def save_setting(self):
        self.info['da'] = da_entry.get()
        self.info['dc'] = dc_entry.get()
        self.info['profile'] = profile_entry.get()
        AccessFile().write_setting_xml(self.info['da'], self.info['dc'], self.info['profile'])

    @staticmethod
    @catch_exceptions
    def convert_table_one_row(table):
        temp_table = []
        for part in table:
            temp_table.append(part[0])
        temp_table = [temp_table, '']
        return temp_table

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

    @catch_exceptions
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

        # First time getting files, load everything from List_Files into mlb
        if file_read and mlb_dump.size() == 0:
            for line in file_read:
                if not line:
                    continue
                line_split = line.split(',')
                file_path = folder + '/' + line_split[2]
                if os.path.exists(file_path):
                    state = 'Available'
                else:
                    state = 'File Not Found'
                mlb_dump.insert(END, ('%s' % line_split[0],
                                      '%s' % line_split[1],
                                      '%s' % line_split[2],
                                      '%s' % state, '---', '---', '---'))
                mlb_dump.pack(expand=YES, fill=BOTH)
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
            if mlb_dump.size() > 0:
                table = mlb_dump.get(0, mlb_dump.size() - 1)
                if mlb_dump.size() == 1:
                    table = self.convert_table_one_row(table)
            else:
                table = []
            for dump_file in os.listdir(folder):
                if dump_file.endswith(".mdr"):
                    flag_newly = 1
                    for row in table:
                        if not row:
                            continue
                        if dump_file == row[2]:
                            flag_newly = 0
                            break
                        else:
                            continue
                    if flag_newly == 1:
                        port += 1
                        ports.append(str(port))
                        i1, i2, i3 = self.new_ip(i1, i2, i3)
                        ip_address = '96.%s.%s.%s' % (str(i1), str(i2), str(i3))
                        ip_addresses.append(ip_address)
                        dump_file = dump_file.encode('ascii', 'ignore')
                        state = 'Newly Added'
                        mlb_dump.insert(END, ('%s' % ip_address, 
                                              '%s' % str(port), 
                                              '%s' % dump_file, 
                                              '%s' % state, '---', '---', '---'))
                        mlb_dump.pack(expand=YES, fill=BOTH)
                    else:
                        pass

        # Return values to self
        self.ip_addresses = ip_addresses
        self.ports = ports

    @catch_exceptions
    def snmp_get_sysoid(self):
        folder_p = folder_entry.get()
        if mlb_dump.size() > 0:
            table_p = mlb_dump.get(0, mlb_dump.size() - 1)
            if mlb_dump.size() == 1:
                table_p = self.convert_table_one_row(table_p)
            mlb_dump.delete(0, mlb_dump.size() - 1)
            table_p = list(SimExtend().snmp_get_sysoid(folder_p, table_p))
            if table_p:
                self.insert_mlb_dump(table_p)
                # mlb_dump.pack(expand=YES, fill=BOTH)

    @catch_exceptions
    def stop_sim(self):
        if mlb_dump.size() > 0:
            table = mlb_dump.get(0, mlb_dump.size() - 1)
            if mlb_dump.size() == 1:
                table = self.convert_table_one_row(table)
            folder_p = folder_entry.get()
            table_p = list(SimExtend(self).stop_sim(table))
            if table_p:
                table_p = SimExtend(self).snmp_get_sysoid(folder_p, table_p)
                if table_p:
                    mlb_dump.delete(0, mlb_dump.size() - 1)
                    self.insert_mlb_dump(table_p)
                    mlb_dump.pack(expand=YES, fill=BOTH)
                self.snmp_get_sysoid()
                self.pid = []

    @catch_exceptions
    def run_sim(self):
        if mlb_dump.size() > 0:
            v1_p = v1.get()
            v2c_p = v2c.get()
            random_p = ranDm.get()
            table_p = mlb_dump.get(0, mlb_dump.size() - 1)
            if mlb_dump.size() == 1:
                table_p = self.convert_table_one_row(table_p)
            folder_p = folder_entry.get()
            mlb_dump.delete(0, mlb_dump.size() - 1)
            table_p = SimExtend().run_sim(v1_p, v2c_p, random_p, table_p, folder_p)
            for row in table_p:
                if not row:
                    continue
                if row[4] != '---':
                    self.pid.append(row[4])
                mlb_dump.insert(END, ('%s' % row[0],
                                      '%s' % row[1],
                                      '%s' % row[2],
                                      '%s' % row[3],
                                      '%s' % row[4],
                                      '%s' % row[5],
                                      '%s' % row[6]))
                mlb_dump.pack(expand=YES, fill=BOTH)
            self.snmp_get_sysoid()

    @catch_exceptions
    def update_list_file(self):
        results_get_file = list(AccessFile().get_file(self.folder))
        folder = results_get_file[0]
        file_read = results_get_file[1:None]
        folder_entry.delete(0, END)
        folder_entry.insert(INSERT, folder)
        self.insert_table(folder, file_read)
        # remove check mlb
        # if mlb_dump.size() > 0:
        if False:
            table = mlb_dump.get(0, mlb_dump.size() - 1)
            log_detail = ''
            for row in table:
                log_add = '%s,%s,%s,%s\n' % (row[0], row[1], row[2], row[5])
                log_detail += log_add
            if log_detail:
                log_path = folder + "/" + "List_of_Mibdumps.csv"
                log_open = open(log_path, 'w')
                log_open.write(log_detail)
                log_open.close()
        self.run_sim()
        # period = 1000 * 300
        # frame21.after(period, self.update_list_file)

    @catch_exceptions
    def get_file(self):
        results_get_file = list(AccessFile().get_file(''))
        folder = results_get_file[0]
        self.folder = folder
        file_read = results_get_file[1:None]
        folder_entry.delete(0, END)
        folder_entry.insert(INSERT, folder)
        self.insert_table(folder, file_read)
        # remove check mlb
        # if mlb_dump.size() > 0:
        if False:
            table = mlb_dump.get(0, mlb_dump.size() - 1)
            log_detail = ''
            for row in table:
                log_add = '%s,%s,%s,%s\n' % (row[0], row[1], row[2], row[5])
                log_detail += log_add
            if log_detail:
                log_path = folder + "/" + "List_of_Mibdumps.csv"
                log_open = open(log_path, 'w')
                log_open.write(log_detail)
                log_open.close()
        # period = 1000 * 300
        # frame21.after(period, self.update_list_file)

    def discover(self):
        # self.dnat_for_capm()
        da_host = da_entry.get()
        profile = profile_entry.get()
        if mlb_dump.size() > 0:
            table_p = mlb_dump.get(0, mlb_dump.size() - 1)
            if mlb_dump.size() == 1:
                table_p = self.convert_table_one_row(table_p)
            table_return = CAPM().discover(da_host, profile, table_p)
            if table_return:
                mlb_dump.delete(0, mlb_dump.size() - 1)
                self.insert_mlb_dump(table_return)

    @catch_exceptions
    def rm_device(self):
        # ip_addresses = self.get_hosts()
        da_host = da_entry.get()
        if mlb_dump.size() > 0:
            table_p = mlb_dump.get(0, mlb_dump.size() - 1)
            if mlb_dump.size() == 1:
                table_p = self.convert_table_one_row(table_p)
            CAPM().rm_device(da_host, table_p)

    @catch_exceptions
    def goodbye(self):
        print("You are now leaving the Python SimSNMP.")
        pid = self.pid
        if pid != [] and pid != '---':
            for child in pid:
                if isinstance(child, int):
                    os.kill(child, signal.SIGTERM)
        else:
            pass
    
    @staticmethod
    def parse_xml():
        pass

    def dnat_for_capm(self):
        user_name = user_entry.get()
        password = pass_entry.get()
        if mlb_dump.size() > 0:
            table_p = mlb_dump.get(0, mlb_dump.size() - 1)
            dc_server_p = dc_entry.get()
            if mlb_dump.size() == 1:
                table_p = self.convert_table_one_row(table_p)
            CAPM().dnat_for_dc(user_name, password, dc_server_p, table_p)
        else:
            pass


if __name__ == "__main__":
    root = Tk()
    root.resizable(width=False, height=False)
    root.title("Python SNMP N-Simulator ver 1.1")

    # new notebook
    note_book = ttk.Notebook(root)
    page1 = ttk.Frame(note_book)
    page2 = ttk.Frame(note_book)
    page3 = ttk.Frame(note_book)
    page4 = ttk.Frame(note_book)
    page5 = ttk.Frame(note_book)
    # note_book.add(page1, text='Settings')
    note_book.add(page2, text='General')
    # note_book.add(page3, text='Extensions')
    # note_book.add(page4, text='SimDepot')
    # note_book.add(page5, text='CAPM')
    note_book.pack(expand=1, fill="both")
    # note_book.select(1)

    app = MainApplication(root)
    # app.check_version()

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

    frame16 = Frame(page1)
    frame16.grid(column=1, row=6, sticky=W)

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

    # Frame21------------------------------------------
    blank_label = Label(frame21, text="", width=5)
    blank_label.grid(column=1, row=1, sticky=W)

    # Browse folder
    folder_label = Label(frame21, text="Dump folder:", width=15)
    folder_label.grid(column=2, row=1, sticky=W)
    folder_entry = Entry(frame21, width=128)
    # folder_entry.insert(INSERT, dump_folder)
    folder_entry.grid(column=3, row=1, sticky=W)

    blank_label = Label(frame21, text="", width=1)
    blank_label.grid(column=4, row=1, sticky=W)

    # Browse button
    browse_button = Button(frame21, text="Browse", command=app.get_file, width=10)
    browse_button.grid(column=5, row=1, sticky=W)

    blank_label = Label(frame21, text="", width=5)
    blank_label.grid(column=6, row=1, sticky=W)

    # Frame22------------------------------------------
    blank_label = Label(frame22, text="", width=5)
    blank_label.grid(column=1, row=1, sticky=W)

    sub_frame22 = Frame(frame22)
    sub_frame22.grid(column=2, row=1, sticky=W + E + N + S + N + S)

    # Server DA
    da_label = Label(sub_frame22, text="DA Server:", width=15)
    da_label.grid(column=1, row=1, sticky=W)
    da_entry = Entry(sub_frame22, width=15)
    da_entry.insert(INSERT, app.info['da_host'])
    da_entry.grid(column=2, row=1, sticky=W)

    # Server DC
    dc_label = Label(sub_frame22, text="DC Server:", width=10)
    dc_label.grid(column=3, row=1, sticky=W)
    dc_entry = Entry(sub_frame22, width=15)
    dc_entry.insert(INSERT, app.info['dc_host'])
    dc_entry.grid(column=4, row=1, sticky=W)

    # Profile Name
    profile_label = Label(sub_frame22, text="Profile Name:", width=12)
    profile_label.grid(column=5, row=1, sticky=W)
    profile_entry = Entry(sub_frame22, width=15)
    profile_entry.insert(INSERT, app.info['profile'])
    profile_entry.grid(column=6, row=1, sticky=W)

    blank_label = Label(frame22, text="", width=1)
    blank_label.grid(column=4, row=1, sticky=W)

    # Username
    user_label = Label(frame22, text="User:", width=10)
    user_label.grid(column=5, row=1, sticky=W)
    user_entry = Entry(frame22, width=20)
    user_entry.insert(INSERT, 'root')
    user_entry.grid(column=6, row=1, sticky=W)

    blank_label = Label(frame22, text="", width=5)
    blank_label.grid(column=7, row=1, sticky=W)

    # Password
    pass_label = Label(frame22, text="Password:", width=10)
    pass_label.grid(column=5, row=2, sticky=W)
    pass_entry = Entry(frame22, width=20, show="*")
    pass_entry.insert(INSERT, 'interOP@3565')
    pass_entry.grid(column=6, row=2, sticky=W)

    blank_label = Label(frame22, text="", width=5)
    blank_label.grid(column=7, row=2, sticky=W)

    # Frame23------------------------------------------
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

    blank_label = Label(frame23, text="", width=15)
    blank_label.grid(column=10, row=1)

    # Frame24------------------------------------------
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

    # Check status button
    check_button = Button(frame24, text=" CHECK STATUS ", command=app.snmp_get_sysoid, relief=RAISED)
    check_button.grid(column=8, row=2, sticky=W + E + N + S)

    blank_label = Label(frame24, text="", width=40)
    blank_label.grid(column=9, row=2, sticky=W + E + N + S)

    # DNAT Button
    dnat_button = Button(frame24, text=" DNAT-CAPM ", command=app.dnat_for_capm, relief=RAISED)
    dnat_button.grid(column=17, row=2, sticky=W + E + N + S)

    blank_label = Label(frame24, text="", width=3)
    blank_label.grid(column=18, row=2, sticky=W + E + N + S)

    # Discover button
    discover_button = Button(frame24, text=" DISCOVER by CAPM ",
                             command=app.discover, relief=RAISED)
    discover_button.grid(column=19, row=2, sticky=W + E + N + S)
    # discover_button.configure(state=DISABLED)
    blank_label = Label(frame24, text="", width=3)
    blank_label.grid(column=20, row=2, sticky=W + E + N + S)

    # Frame5------------------------------------------

    blank_label = Label(frame25, text="", width=140)
    blank_label.pack()

    # Frame6------------------------------------------

    # Table
    Label(frame26, text='\n',).pack(side=RIGHT)
    blank_label = Label(frame26, text="", width=5)
    blank_label.pack(side=LEFT)
    mlb_dump = MultiListbox(frame26, 20, (('IP Address', 15), ('Port', 10), ('Mibdump', 70), ('Status', 15),
                                          ('PID', 10), ('Sys OID', 30), ('Discovery Status', 20)))
    mlb_dump.pack(expand=YES, fill=BOTH)
    # Remove discovered device
    rm_button = Button(frame27, text=" REMOVE ALL DISCOVERED DEVICES ABOVE ",
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

    blank_label = Label(frame31, text="", width=5)
    blank_label.grid(column=1, row=1, sticky=W+E+N+S)
    # Host label
    blank_label = Label(frame31, text="", width=5)
    blank_label.grid(column=1, row=2, sticky=W+E+N+S)
    ip_label = Label(frame31, text="Host: ", width=5)
    ip_label.grid(column=2, row=2, sticky=W+E+N+S)

    # Get information and settings
    # app.save_setting()
    app.save_info()

    root.mainloop()
    sys.exit(0)
