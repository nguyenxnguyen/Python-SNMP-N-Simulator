import time
import os


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


def catch_exceptions(func):
    def wrapper(*args, **kw):
        try:
            return func(*args, **kw)
        except Exception, e:
            # make a popup here with your exception information.
            print "Error: %s" % e
            auto_log(e)
    return wrapper




