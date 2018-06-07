# SIM Reader GUI

Simple python application that enables reading and writing basic data from the SIM 
card using serial port reader. The library used for serial communication with reader 
can was found on link: https://github.com/polz113/simread  
Many thanks to the author. 

The first version of this application was written by Janez Eržen as part of a digital forensics class assignment at FRI.
### Requirements
* python 2.7 installed 
* PyQt5 python library 

### Usage
Run 'python pySIM_GUI.py <port>' from the terminal  
You should always pass port parameter on linux systems!   
Example: python pySIM_GUI.py /dev/ttyUSB0 
 
### Useful links

* Prolific PL-2303 Driver 3.2.0.0 http://pdxpiedmont.net/node/52
