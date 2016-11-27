Python SNMP N-Simulator ver 1.1
---------------------

  [ See the end of this file for info on using the simlaunch.pyw GUI tool ]

  Overview
  --------
     This directory contains the code for an SNMP simulator written in Python 
  with the following features:

  - SNMP v1 GET, and GETNEXT support
  - SNMP v2c GET, GETNEXT, and GETBULK support
  - Support for most commonly used SNMP v1/v2c datatypes (including
    Counter64 support (with the full range of values)).
  - Basic support for varying Counter data (easy enough to extend/improve upon
    to include other data types)
  - An optionally enabled embedded web server for a web interface to inspecting
    and changing data manually

     This simulator was written in a combination of Python and C (99% Python)
  with certain tradeoffs in mind. Specifically, this simulator will run more 
  slowly and take more memory than our current C simulator. However, the code
  is something along the lines of an order of magnitude smaller, allowing a 
  larger feature set (proper v2c GET/GETNEXT/GETBULK semantics/complete 
  Counter64 support) and future changes to (hopefully) be made with less 
  effort. 

  Installation/Running the simulator
  ----------------------------------
     
    Windows
    -------
       To run the simulator on Windows, you'll need to have a version of the
    Python interpreter installed. The simulator should run with versions of
    Python >= 2.1, though 2.2 is recommended (the current latest stable version
    as of this writing). An installer for Windows can be downloaded at:

      http://www.python.org/ftp/python/2.2.1/Python-2.2.1.exe

       With this installed, the following steps should be taken to make the
    simulator runnable from the command line:

    - Add the directory that you installed Python to (D:\Python22, for example)
      to the PATH of your windows system. This usually entails something like:
      - Start->Settings->Control Panel->System->Environment
      - Clicking on the PATH variable in the System Variables, and appending 
        a semicolon and the name of your Python directory to the text in the
        Value textbox (appending ;D:\Python22 in the example above).
      - Clicking Set, then Apply, then Ok.

    - Copy the contents of the dist\windows directory to a directory in your 
      PATH, creating a new directory if necessary. I have an H:\UTILS 
      subdirectory that's in my PATH, so I have these files copied there.

    - Change the directory referenced in the file snmpsim.bat from H:\UTILS
      to the location you've placed these files in, if it's not H:\UTILS.

       With these steps taken, you should be able to start up a new cmd.exe
    window, type in snmpsim, and get a usage message. At this point the
    command line options are very similar to the C simulator's; to run
    the simulator on a file called C:\dump.mdr and have it listen on port 5000,
    you'd run this:

      snmpsim -p 5000 -f c:\dump.mdr

       See the usage message (gotten by invoking the simulator with no 
    parameters) for the full set of options, including enabling SNMP v2c
    support and the embedded web server.

    Unix
    ----
       Concord Solaris machines
       ------------------------
          On Concord Solaris machines Python is installed in /home/tools, so
       you can make Python accessible by adding the directory 
       /home/tools/SunOS5.7/bin to your path (I have this line in my .cshrc:
          setenv PATH $PATH":/home/tools/SunOS5.7/bin"
       The other step is to copy the contents of the dist\solaris directory to
       someplace in your path (I have a bin dir in my home directory I use).
       With these steps taken, you should be able to start up a new shell,
       type in snmpsim, and get a usage message. At this point the
       command line options are very similar to the C simulator's; to run
       the simulator on a file called /dump.mdr and have it listen on port 
       5000, you'd run this:

         snmpsim -p 5000 -f /dump.mdr

          See the usage message (gotten by invoking the simulator with no 
       parameters) for the full set of options, including enabling SNMP v2c
       support and the embedded web server.
       

       Other Unix machines/non-Concord machines
       ----------------------------------------
          To run the simulator under other Unix machines or off site, you'll 
       need to have a version of the Python interpreter installed. The 
       simulator should run with version of Python >= 2.1, though 2.2 is 
       recommended (the current latest stable version as of this writing). 
       The source code can be downloaded at:

         http://www.python.org/ftp/python/2.2.1/Python-2.2.1.tgz

          With this installed on your system (typically in /usr/local, with the
       Python interpreter in /usr/local/bin), the following steps should be 
       taken to make the simulator runnable from the command line:

       - Ensure that the Python interpreter is in your PATH

       - Copy the contents of the snmpsim\dist\other directory to a 
         directory in your PATH.
   
          With these steps taken, you should be able to start up a new shell,
       type in snmpsim, and get a usage message. At this point the
       command line options are very similar to the C simulator's; to run
       the simulator on a file called /dump.mdr and have it listen on port 
       5000, you'd run this:

         snmpsim -p 5000 -f /dump.mdr

          See the usage message (gotten by invoking the simulator with no 
       parameters) for the full set of options, including enabling SNMP v2c
       support and the embedded web server.

       NOTE: Without the C extension compiled and in the same directory,
             some operations will be slower. Using this will speed load times
             and certain types of GETNEXT/GETBULK operations.


  Using simlaunch.pyw (Windows only)
  ----------------------------------
     If you already have the simulator running and installed, you can use 
  simlaunch.pyw to launch simulators in windows environments--it's a GUI front 
  end launcher for snmpsim. To use it can just copy the file to the same 
  location as snmpsim.pyc (it needs to be in the same directory as snmpsim.pyc)
  and double click on it to use it, or you can set up an association so you 
  can right click on a .mdr file and simulate it from Explorer. 
 
  To set up the association, follow these steps:

  - Copy the simlaunch.pyw file to the same directory snmpsim.pyc is located 
    (I use h:\utils).

  - Create a new file type in Explorer if the "Mib Dump" file type doesn't 
    exist (Nick's Certify tool does this, I believe). This can be checked in 
    Explorer using View->Folder Options->File Types and looking for the 
    "Mib Dump" file type in the list of registered files types. If it's not 
    there, create it using the New Type button, giving a description of 
    "New Type" and an extension of ".mdr".

  - Create a new action for the "Mib Dump" file type. Can be gotten to from 
    Explorer using View->Folder Options->File Types, selecting Mib Dump, and 
    clicking the "Edit" button. Create the new action using the "New" button. 
    Call the new Action "Simulate" or whatever you'd like to see when you 
    right click on a .mdr file. For the Action, put in:
        pythonw.exe "<full path to location of simlaunch.pyw>"
    I use:
        pythonw.exe "h:\utils\simlaunch.pyw"
    ...since I copied simlaunch.pyw to h:\utils.

     Once all this is done you ought to be able to right click on anything 
  that ends in .mdr and be able to simulate it on the spot, with the ability
  to toggle most of the interesting options to the simulator.
  