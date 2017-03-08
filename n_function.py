import time
import os


def snmp_get(ip, port, oid):
    snmp_get_file = os.path.dirname(os.path.abspath(__file__)) + "/" + 'SnmpGet.exe'
    cmd_snmp_get = '\""%s" -q -r:%s -p:%s -t:1 -c:"public" -o:%s' % (snmp_get_file, ip, port, oid)
    print cmd_snmp_get
    response = os.popen(cmd_snmp_get).read()
    response = response.replace('\n', '')
    if response.__contains__('Timeout'):
        state = 'Stopped'
        value = '---'
    elif response:
        state = 'Running'
        value = response
    else:
        state = 'Unknown'
        value = '---'
    return state, value


def timeit(method):
    def timed(*args, **kw):
        ts = time.time()
        result = method(*args, **kw)
        te = time.time()
        print '%r %2.2f sec' % (method.__name__, te-ts)
        return result
    return timed


def auto_log(message):
    import logging
    folder = os.path.dirname(os.path.abspath(__file__))
    log_path = folder + '/log_detail.log'
    logging.basicConfig(filename=log_path, level=logging.DEBUG,
                        format='%(asctime)s \n'
                               '\t%(levelname)s : %(name)s : %(module)s : %(message)s')
    logger = logging.getLogger(__name__)
    logger.error(message)







