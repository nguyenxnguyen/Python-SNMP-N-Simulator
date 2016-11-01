CC=cc
PY_INCLUDE=/home/tools/SunOS5.7/python2.2/include/python2.2
POS_IND_CODE_FLAG=-Kpic
SHARED_LIB_FLAG=-G

all:	csnmpsim.o	csnmpsim.so

csnmpsim.o:	csnmpsim.c
	$(CC) $(SHARED_LIB_FLAG) -I/home/tools/SunOS5.7/python2.2/include/python2.2 -DHAVE_CONFIG_H -c ./csnmpsim.c

csnmpsim.so:	csnmpsim.o
	$(CC) $(SHARED_LIB_FLAG) csnmpsim.o  -o csnmpsim.so
