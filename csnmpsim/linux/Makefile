# Note: This is how it should work under Linux. Need to find equivalent way
# of doing this for Solaris.
all:	csnmpsim.o	csnmpsim.so

csnmpsim.o:	csnmpsim.c
	gcc -fpic  -g -O2 -I/usr/local/include/python2.2 -DHAVE_CONFIG_H -c ./csnmpsim.c

csnmpsim.so:	csnmpsim.o
	gcc -shared  csnmpsim.o  -o csnmpsim.so
