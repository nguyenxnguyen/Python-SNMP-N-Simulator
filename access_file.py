from Tkinter import *
import tkFileDialog, tkMessageBox,  os, sys, re
import requests
from xml.etree.ElementTree import parse, Element, SubElement, Comment
from xml.etree import ElementTree
from xml.dom import minidom


def prettify(elem):
    """Return a pretty-printed XML string for the Element.
    """
    rough_string = ElementTree.tostring(elem, 'utf-8')
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="  ")

class AccessFile(object):
    def __init__(self, *args, **kwargs):
        pass

    def check_version(self):
        folder = os.path.dirname(os.path.abspath(__file__))
        f_path = folder + '/Readme.txt'
        f_open = open(f_path, 'r')
        lines = f_open.read().splitlines()
        prefix_version = 'Python SNMP N-Simulator ver '
        version = lines[0].replace(prefix_version, '')
        link = 'https://www.dropbox.com/s/rntyaxaaxn03oai/Readme.txt?dl=1'
        f_source = requests.get(link)
        f_text = f_source.text.split('\n')
        f_open.close()
        if f_text:
            for line in f_text:
                if prefix_version in line:
                    latest_version = line.replace(prefix_version, '')
                    if float(latest_version) > float(version):
                        msg = 'Version %s is available!\n Do you want to update?' % latest_version
                        ans = tkMessageBox.askyesno('New version!', message=msg)
                        return ans

    def get_file(self):
        folder = tkFileDialog.askdirectory(initialdir=os.path.expanduser('~/Desktop'))
        yield folder
        #file_read = read_file(folder)
        #insert_table(folder, file_read)
        #if check_state.get() == 1:
        #    snmp_get_sysoid()
        file_path = folder + '/' + "List_of_Mibdumps.csv"
        #file_read = []
        if os.path.exists(file_path):
            f = open(file_path, 'r')
            if f:
                f_read = f.read().split('\n')
                for f_line in f_read:
                    if '127' not in f_line:
                        continue
                    else:
                        #file_read.append(f_line)
                        yield f_line

    def write_file(self, file_name, body):
        f_path = os.path.dirname(os.path.abspath(__file__)) + "/" + file_name
        f_open = open(f_path, 'w')
        f_open.write(body)
        f_open.close()

    def parse_XML(self):
        pass

    def prettify(elem):
        """Return a pretty-printed XML string for the Element.
        """
        rough_string = ElementTree.tostring(elem, 'utf-8')
        reparsed = minidom.parseString(rough_string)
        return reparsed.toprettyxml(indent="\t")

    def write_setting_XML(self, nim_path, schedule_time, timeout):
        top = Element('Setting')

        comment = Comment('Generated by Python_SnmpSim')
        top.append(comment)

        l1_nim_path = SubElement(top, 'nim_path')
        l1_nim_path.text = nim_path

        l1_schedule_time = SubElement(top, 'schedule_time')
        l1_schedule_time.text = schedule_time

        l1_timeout = SubElement(top, 'timeout')
        l1_timeout.text = timeout

        #print prettify(top)
        body = prettify(top)
        folder = os.path.dirname(os.path.abspath(__file__))
        f_path = folder + '/setting.xml'
        f_open = open(f_path, 'w')
        f_open.write(body)
        f_open.close()
