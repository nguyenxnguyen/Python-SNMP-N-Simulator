@echo off
python -OO -c "from py_compile import compile; compile('snmpsim.py', 'bytecode/snmpsim.pyc'); compile('snmplib.py', 'bytecode/snmplib.pyc'); compile('simlaunch.pyw', 'bytecode/simlaunch.pyw')"
rem Windows
copy bytecode\snmplib.pyc dist\windows
copy bytecode\snmpsim.pyc dist\windows
copy bytecode\simlaunch.pyw dist\windows

rem Solaris
copy bytecode\snmplib.pyc dist\solaris
copy bytecode\snmpsim.pyc dist\solaris

rem Other
copy bytecode\snmplib.pyc dist\other
copy bytecode\snmpsim.pyc dist\other
