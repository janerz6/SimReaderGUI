# -*- coding: latin-1 -*-

from __future__ import print_function
from __future__ import print_function
from __future__ import print_function
import time
import calendar
import os
from binascii import hexlify, unhexlify


def print_exc():
    print("Error")


try:
    SerialError = 0
    import serial
except ImportError:
    SerialError = 1
    import traceback

    traceback.print_exc()

SCARD_PROTOCOL_T0 = 1
SCARD_PROTOCOL_T1 = 2

SW_OK = "9000"
SW_FOLDER_SELECTED_OK = "9F17"
SW_FILE_SELECTED_OK = "9F0F"

CHV_ALWAYS = 0
CHV_READ = 1
CHV_UPDATE = 2

ATTRIBUTE_ATR = 0x90303
ATTRIBUTE_VENDOR_NAME = 0x10100
ATTRIBUTE_VENDOR_SERIAL_NO = 0x10103

ACK_NULL = 0x60
ACK_OK = 0x90


class pySIMlib:
    def __init__(self, dbg=False):
        self.debug = dbg

        self.state = False
        self.serialport = None

        self.chv1_enabled = 0
        self.chv1_tries_left = 0
        self.chv1 = ""
        self.chv2_enabled = 0
        self.chv2_tries_left = 0
        self.chv2 = ""
        self.FDN_available = 0

        self.FILE_MF = "3F00"
        self.FILE_DF_TELECOM = "7F10"
        self.FILE_DF_GSM = "7F20"
        self.FILE_EF_ICCID = "2FE2"
        self.FILE_EF_LP = "6F05"
        self.FILE_EF_ADN = "6F3A"
        self.FILE_EF_SMS = "6F3C"
        self.FILE_EF_FDN = "6F3B"
        self.FILE_EF_LND = "6F44"
        self.FILE_EF_SPN = "6F46"
        self.FILE_EF_MSISDN = "6F40"
        self.FILE_EF_LOCI = "6F7E"
        self.FILE_EF_IMSI = "6F07"
        self.FILE_EF_KC = "6F20"
        self.FILE_EF_PHASE = "6FAE"
        self.FILE_EF_HPLMN = "6F31"
        self.FILE_EF_SST = "6F38"
        self.FILE_EF_BCCH = "6F74"
        self.FILE_EF_ACC = "6F78"
        self.FILE_EF_FPLMN = "6F7B"
        self.FILE_EF_AD = "6FAD"

    def openSession(self, portname):
        """openSession(portname)

            portname : string of serila port name
            result  : if(0) OK else error
        """
        self.serialport = serial.Serial(port=portname,
                                        parity=serial.PARITY_EVEN,
                                        bytesize=serial.EIGHTBITS,
                                        stopbits=serial.STOPBITS_TWO,
                                        timeout=1,
                                        xonxoff=0,
                                        rtscts=0,
                                        baudrate=9600)
        if (not self.serialport):
            return 1

        # reset it!
        self.serialport.setRTS(1)
        self.serialport.setDTR(1)
        time.sleep(0.01)  # 10ms?
        self.serialport.flushInput()
        self.serialport.setRTS(0)
        self.serialport.setDTR(0)

        ts = self.serialport.read()
        if ts == None:
            return 2  # no card?
        if ord(ts) != 0x3B:
            return 3  # bad ATR byte
        # ok got 0x3B
        if (self.debug): print("TS: 0x%x Direct convention" % ord(ts))

        t0 = chr(0x3B)
        while ord(t0) == 0x3b:
            t0 = self.serialport.read()

        if t0 == None:
            return 2
        if (self.debug): print("T0: 0x%x" % ord(t0))

        # read interface bytes
        if (ord(t0) & 0x10):
            if (self.debug): print("TAi = %x" % ord(self.serialport.read()))
        if (ord(t0) & 0x20):
            if (self.debug): print("TBi = %x" % ord(self.serialport.read()))
        if (ord(t0) & 0x40):
            if (self.debug): print("TCi = %x" % ord(self.serialport.read()))
        if (ord(t0) & 0x80):
            tdi = self.serialport.read()
            if (self.debug): print("TDi = %x" % ord(tdi))

        for i in range(0, ord(t0) & 0xF):
            x = self.serialport.read()
            if (self.debug): print("HI: %x" % ord(x))

        while 1:
            x = self.serialport.read()
            if (x == ""):
                break
            if (self.debug): print("read: %x" % ord(x))

        self.state = True
        self.checkCHV()
        return 0

    def closeSession(self):
        """closeSession()
        """
        self.serialport.close()
        self.serialport = None
        self.state = False
        return 0

    def sendAPDU(self, command, checkSW=False, refSW=""):
        """sendAPDU(pdu)

            command : string of hexadecimal characters (ex. "A0A40000023F00")
            result  : tuple(data, sw), where
                      data : string (in hex) of returned data (ex. "074F4EFFFF")
                      sw   : string (in hex) of status word (ex. "9000")
        """
        if (self.debug): print("CM: " + command)
        # send first 5 'header' bytes
        for i in range(5):
            s = int(command[i * 2] + command[i * 2 + 1], 16)
            self.serialport.write(chr(s))
            # because rx and tx are tied together, we will read an echo
            self.serialport.read()

        while 1:
            rep = self.serialport.read()
            time.sleep(0.001)
            # check that it is echoing the INS (second byte)
            if (ord(rep) == int(command[2] + command[3], 16)):
                if (self.debug): print("RS: OK")
                break
            if (ord(rep) != ACK_NULL):
                if (self.debug): print("RS: BAD %X" % ord(rep))
                return ("", "")  # bad response
            if (self.debug): print("RS: NULL")

        data = ''
        if (len(command) == 10):
            # read data
            datalen = int(command[8] + command[9], 16)
            for i in range(datalen):
                s = ord(self.serialport.read())
                hexed = "%02X" % s
                data += hexed[0]
                data += hexed[1]
        else:
            # time to send command
            datalen = int(command[8] + command[9], 16)
            for i in range(datalen):
                s = int(command[10 + i * 2] + command[11 + i * 2], 16)
                self.serialport.write(chr(s))
                # because rx and tx are tied together, we will read an echo
                self.serialport.read()

        # look for the ack word, but ignore a 0x60
        while 1:
            sw1 = self.serialport.read()
            if (ord(sw1) != ACK_NULL):
                break
        sw2 = self.serialport.read()
        sw = "%02x%02x" % (ord(sw1), ord(sw2))
        if self.debug: print("SW: " + sw)

        if checkSW:
            if sw != refSW:
                raise RuntimeError("Status words do not match. Result: %s, Expected: %s" % (sw, matchSW))

        return data, sw
        if data:
            return data, sw
        else:
            return '', sw

    def _SELECT(self, fileId):
        rdata, sw = self.sendAPDU("A0A4000002" + fileId)
        return sw

    def _STATUS(self, lgth):
        rdata, sw = self.sendAPDU("A0F20000" + lgth)
        return rdata, sw

    def _READ_BINARY(self, off, lgth):
        rdata, sw = self.sendAPDU("A0B0" + off + lgth)
        return rdata, sw

    def _UPDATE_BINARY(self, off, lgth, data):
        rdata, sw = self.sendAPDU("A0D6" + off + lgth + data)
        return sw

    def _READ_RECORD(self, recNum, mode, lgth):
        rdata, sw = self.sendAPDU("A0B2" + recNum + mode + lgth)
        return rdata, sw

    def _UPDATE_RECORD(self, recNum, mode, lgth, data):
        rdata, sw = self.sendAPDU("A0DC" + recNum + mode + lgth + data)
        return sw

    def _SEEK(self, typeMode, lgth, data):
        rdata, sw = self.sendAPDU("A0A200" + typeMode + lgth + data)
        return rdata, sw

    def _INCREASE(self, typeMode, lgth, data):
        rdata, sw = self.sendAPDU("A032000003" + typeMode + lgth + data)
        return rdata, sw

    def _VERIFY_CHV(self, chvNum, data):
        rdata, sw = self.sendAPDU("A02000" + chvNum + "08" + data)
        return sw

    def _CHANGE_CHV(self, chvNum, data):
        rdata, sw = self.sendAPDU("A02400" + chvNum + "10" + data)
        return sw

    def _DISABLE_CHV(self, data):
        rdata, sw = self.sendAPDU("A026000108" + data)
        return sw

    def _ENABLE_CHV(self, data):
        rdata, sw = self.sendAPDU("A028000108" + data)
        return sw

    def _UNBLOCK_CHV(self, chvNum, data):
        rdata, sw = self.sendAPDU("A02C00" + chvNum + "10" + data)
        return sw

    def _INVALIDATE(self):
        rdata, sw = self.sendAPDU("A004000000")
        return sw

    def _REHABILITATE(self):
        rdata, sw = self.sendAPDU("A044000000")
        return sw

    def _RUN_GMS_ALGORITHM(self, data):
        rdata, sw = self.sendAPDU("A088000010" + data)
        return rdata, sw

    def _SLEEP(self):
        rdata, sw = self.sendAPDU("A0FA000000")
        return sw

    def _GET_RESPONSE(self, lgth):
        rdata, sw = self.sendAPDU("A0C00000" + lgth)
        return rdata, sw

    def _TERMINAL_PROFILE(self, lgth):
        rdata, sw = self.sendAPDU("A0100000" + lgth)
        return sw

    def _ENVELOPE(self, lgth):
        rdata, sw = self.sendAPDU("A0C20000" + lgth)
        return rdata, sw

    def _FETCH(self, lgth):
        rdata, sw = self.sendAPDU("A0120000" + lgth)
        return rdata, sw

    def _TERMINAL_RESPONSE(self, lgth):
        rdata, sw = self.sendAPDU("A0140000" + lgth)
        return sw

    def setFile(self, dirList):
        """setFile(dirList)
           dirList: list of files 1 or more
        """
        for i in dirList:
            self._SELECT(i)

    def checkCHV(self):
        """readBasicInfo()

           reads info regarding chv1 and chv2 fileds (PIN, PUK)
        """
        try:
            self.setFile([self.FILE_MF])
            data, sw = self._STATUS("0D")
            l = 0x0D + int(data[24:26], 16)
            data, sw = self._STATUS("%02x" % l)
            s = unhexlify(data)

            # Check whether CHV1 is enabled
            self.chv1_enabled = 1
            if ord(s[13]) & 0x80:
                self.chv1_enabled = 0

            # Get number of CHV1 attempts left (0 means blocked, oh crap!)
            self.chv1_tries_left = ord(s[18]) & 0x0F

            if len(s) >= 22:
                # Get number of CHV2 attempts left (0 means blocked, oh crap!)
                self.chv2_enabled = 1
                self.chv2_tries_left = ord(s[20]) & 0x0F

            # See if the FDN file exists
            try:
                self.setFile([self.FILE_MF, self.FILE_DF_TELECOM, self.FILE_EF_FDN])
                self.FDN_available = 1
            except:
                pass
        except:
            print_exc()

    def getICCID(self):
        self.setFile([self.FILE_MF, self.FILE_EF_ICCID])
        data, sw = self._READ_BINARY("0000", "0A")
        return data

    def getLP(self):
        self.setFile([self.FILE_MF, self.FILE_DF_GSM, self.FILE_EF_LP])
        data, sw = self._READ_BINARY("0000", "01")
        return data

    def getIMSI(self):
        self.setFile([self.FILE_MF, self.FILE_DF_GSM, self.FILE_EF_IMSI])
        data, sw = self._READ_BINARY("0000", "09")
        return data

    def getKC(self):
        self.setFile([self.FILE_MF, self.FILE_DF_GSM, self.FILE_EF_KC])
        data, sw = self._READ_BINARY("0000", "09")
        return data

    def getHPLMN(self):
        self.setFile([self.FILE_MF, self.FILE_DF_GSM, self.FILE_EF_HPLMN])
        data, sw = self._READ_BINARY("0000", "01")
        return data

    def getSST(self):
        self.setFile([self.FILE_MF, self.FILE_DF_GSM, self.FILE_EF_SST])
        data, sw = self._READ_BINARY("0000", "02")
        return data

    def getBCCH(self):
        self.setFile([self.FILE_MF, self.FILE_DF_GSM, self.FILE_EF_BCCH])
        data, sw = self._READ_BINARY("0000", "10")
        return data

    def getACC(self):
        self.setFile([self.FILE_MF, self.FILE_DF_GSM, self.FILE_EF_ACC])
        data, sw = self._READ_BINARY("0000", "02")
        return data

    def getFPLMN(self):
        self.setFile([self.FILE_MF, self.FILE_DF_GSM, self.FILE_EF_FPLMN])
        data, sw = self._READ_BINARY("0000", "0C")
        return data

    def getLOCI(self):
        self.setFile([self.FILE_MF, self.FILE_DF_GSM, self.FILE_EF_LOCI])
        data, sw = self._READ_BINARY("0000", "0B")
        return data

    def getAD(self):
        self.setFile([self.FILE_MF, self.FILE_DF_GSM, self.FILE_EF_AD])
        data, sw = self._READ_BINARY("0000", "03")
        return data

    def getPhase(self):
        self.setFile([self.FILE_MF, self.FILE_DF_GSM, self.FILE_EF_PHASE])
        data, sw = self._READ_BINARY("0000", "01")
        return data

    def getPINinfo(self):
        return self.chv1_enabled, self.chv1_tries_left

    def enPIN(self, pin):
        sw = self._ENABLE_CHV(self._ASCII2PIN(pin))
        self.chv1_enabled = 1
        self.chv1_tries_left = 3
        self.chv1 = pin
        return 0

    def verPIN(self, pin):
        sw = self._VERIFY_CHV("01", self._ASCII2PIN(pin))
        pinOk = sw == SW_OK
        self.chv1 = pin
        self.chv1_tries_left = self.chv1_tries_left - 1 if not pinOk else 3
        return pinOk

    def chgPIN(self, pinOld, pinNew):
        sw = self._CHANGE_CHV("01", self._ASCII2PIN(pinOld) + self._ASCII2PIN(pinNew))
        self.chv1 = pinNew
        self.chv1_tries_left = 3
        return 0

    def disPIN(self, pin):
        sw = self._DISABLE_CHV(self._ASCII2PIN(pin))
        self.chv1_enabled = 0
        self.chv1 = ""
        return 0

    def getNumInfo(self, numFile):
        self.setFile([self.FILE_MF, self.FILE_DF_TELECOM, numFile])

        # Send the get response command, to find out record length
        data, sw = self._GET_RESPONSE("0F")
        recLen = int(data[28:30], 16)  # Usually 0x20
        nameLen = recLen - 14  # Defined GSM 11.11
        recNum = int(data[4:8], 16) / recLen
        return recNum, recLen, nameLen

    def getNums(self, numFile):
        recNum, recLen, nameLen = self.getNumInfo(numFile)

        numbers = {}
        free_slots = []
        for i in range(1, recNum + 1):
            (name, number) = self.getNum(numFile, i, recLen, nameLen)
            if len(name) != 0 and len(number) != 0:
                numbers[i] = (name, number)
            else:
                free_slots = list(range(i, recNum))
                break
        return numbers, free_slots

    def getNum(self, numFile, recNum, recLen, nameLen):
        self.setFile([self.FILE_MF, self.FILE_DF_TELECOM, numFile])
        data, sw = self._READ_RECORD("%02X" % recNum, "04", "%02X" % recLen)

        # Find the end of the name
        name = ""
        number = ""
        hexNameLen = nameLen << 1
        if data[0:2] != 'FF':
            name = self.GSM3_38_2_ASCII(unhexlify(data[:hexNameLen]))
            if ord(name[-1]) > 0x80:
                # Nokia phones add this as a group identifier. Remove it.
                name = name[:-1].rstrip()
            number = ""
            numberLen = int(data[hexNameLen:hexNameLen + 2], 16)
            if numberLen > 0 and numberLen <= (11):  # Includes TON/NPI byte
                hexNumber = data[hexNameLen + 2:hexNameLen + 2 + (numberLen << 1)]
                if hexNumber[:2] == '91':
                    number = "+"
                number += self.GSMPhoneNumber_2_String(hexNumber[2:])
        return (name, number)

    def setNum(self, numFile, recNum, recLen, nameLen, name='', number=''):
        self.setFile([self.FILE_MF, self.FILE_DF_TELECOM, numFile])

        if not name:
            data = "FF" * recLen
        else:
            GSMnumber = self.String_2_GSMPhoneNumber(number)
            data = "%s%s%sFFFF" % (
                self.padString(hexlify(self.ASCII_2_GSM3_38(name)), nameLen << 1, "F"), "%02X" % (len(GSMnumber) / 2),
                self.padString(GSMnumber, 22, 'F'))

        if (numFile == self.FILE_EF_ADN):
            sw = self._UPDATE_RECORD("%02X" % recNum, "04", "%02X" % recLen, data)
            return 0
        elif (numFile == self.FILE_EF_FDN):
            return 1
        elif (numFile == self.FILE_EF_LND):
            sw = self._UPDATE_RECORD("00", "03", "%02X" % recLen, data)
            return 0

    def getSMSinfo(self):
        self.setFile([self.FILE_MF, self.FILE_DF_TELECOM, self.FILE_EF_SMS])

        # Send the get response command, to find out record length
        data, sw = self._GET_RESPONSE("0F")

        recLen = int(data[28:30], 16)  # Should be 0xB0 (176)
        recNum = int(data[4:8], 16) / recLen
        return recNum, recLen

    def getSMSs(self):
        recNum, recLen = self.getSMSinfo()

        smss = {}
        for i in range(1, recNum + 1):
            smss[i] = self.getSMS(i, recLen)
        return smss

    def getSMS(self, recNum, recLen):
        self.setFile([self.FILE_MF, self.FILE_DF_TELECOM, self.FILE_EF_SMS])

        data, sw = self._READ_RECORD("%02X" % recNum, "04", "%02X" % recLen)

        # See if SMS record is used
        status = int(data[0:2], 16)
        if status & 1 or data[2:4] != 'FF':
            return self.smsFromData(data)
        else:
            return ""

    def smsFromData(self, data):
        rawMessage = data

        status = int(data[0:2], 16)

        i = int(data[2:4], 16) << 1
        smsc = self.GSMPhoneNumber_2_String(data[4:4 + i], replaceTonNPI=1)
        data = data[4 + i:]

        val = int(data[0:2], 16)
        mti = (val >> 6) & 3
        mms = (val >> 5) & 1
        sri = (val >> 4) & 1
        udhi = (val >> 3) & 1
        rp = (val >> 2) & 1
        data = data[2:]

        i = int(data[:2], 16)
        j = 4 + i + (i % 2)
        number = self.GSMPhoneNumber_2_String(data[2:j], replaceTonNPI=1)
        data = data[j:]

        pid = int(data[:2], 16)
        dcs = int(data[2:4], 16)

        timestamp = self.convertTimestamp(data[4:18])

        udl = int(data[18:20], 16)  # it's meaning is dependant upon dcs value
        if ((dcs >> 2) & 3) == 0:  # 7-bit, Default alphabet
            i = ((udl * 7) / 8) << 1
            if (udl * 7) % 8:
                i += 2
            message = self.GSM7bit_2_Ascii(data[20:20 + i])
        elif ((dcs >> 2) & 3) == 1:  # 8-bit data, binary
            message = "ERROR: Don't understand 8-bit binary messages"
        elif ((dcs >> 2) & 3) == 2:  # 16-bit, UCS2 oh hell!  :)
            message = "ERROR: Don't understand 16-bit UCS2 messages"
        else:
            message = "ERROR: Don't understand this message format"
        return status, timestamp, number, message

    def _ASCII2PIN(self, pin):
        """ converts a PIN code string to a hex string with padding
            The PIN code string is padded with 'FF' until (8 - lg_sPIN).
            sample : "0000" is converted to "30303030FFFFFFFF"
            Input :
                - sPIN     = string containing the  cardholder code (PIN)

            Return a hex string of the PIN with FF padding.
        """
        from binascii import hexlify

        return hexlify(pin) + (8 - len(pin)) * 'FF'

    def swapNibbles(hexString, paddingNibble='F'):
        """ converts a string in a buffer with swap of each character
            If odd number of characters, the paddingNibble is concatened to the result string
            before swap.
            sample : "01396643721" is converted to "1093663427F1"
            Input :
                - hexString     = string containing data to swap
                - paddingNibble = value of the padd (optional parameter, default value is 'F')

            Return a list of bytes.
        """
        remove_pad = 0
        length = len(hexString)
        if length >= 2 and hexString[-2] == paddingNibble:
            remove_pad = 1

        if (length % 2):  # need padding
            hexString += paddingNibble

        res = ''
        for i in range(0, length, 2):
            res += "%s%s" % (hexString[i + 1], hexString[i])

        if remove_pad:
            res = res[:-1]
        return res

    def String_2_GSMPhoneNumber(self, phoneString):
        """ converts a number string to a GSM number string representation
            Input :
                - phoneString    = phone string (data to swap)
            Returns a GSM number string.
        """
        if not phoneString:
            return ''

        if phoneString[0] == '+':
            res = "91"
            phoneString = phoneString[1:]
        else:
            res = "81"

        if len(phoneString) % 2:
            phoneString += "F"

        i = 0
        while i < len(phoneString):
            res += '%s%s' % (phoneString[i + 1], phoneString[i])
            i += 2

        return res

    def GSMPhoneNumber_2_String(self, phoneString, replaceTonNPI=0):
        """ converts a GSM string number to a normal string representation
            If the second last character is 'F', the F is removed from the result string.
            sample : "10936634F7"  is converted to "013966437"
            Input :
                - phoneString    = GSM phone string (data to swap)
            Returns a normal number string.
        """
        if not phoneString:
            return ''

        res = ""
        if replaceTonNPI:
            if phoneString[:2] == "91":
                res = "+"
            phoneString = phoneString[2:]

        i = 0
        while i < len(phoneString):
            res += '%s%s' % (phoneString[i + 1], phoneString[i])
            i += 2

        if res and res[-1].upper() == 'F':
            res = res[:-1]

        return res

    def ASCII_2_GSM3_38(self, sName):
        """ converts an ascii name string to a GSM 3.38 name string
            Input :
                - sName     = string containing the name
            Returns a string
        """
        # GSM3.38 character conversion table
        dic_GSM_3_38 = {'@': 0x00,  # @ At symbol
                        chr(0x9C): 0x01,  # £ Britain pound symbol
                        '$': 0x02,  # $ Dollar symbol
                        chr(0xA5): 0x03,  # ¥ Yen symbol
                        'è': 0x04,  # è e accent grave
                        'é': 0x05,  # é e accent aigu
                        'ù': 0x06,  # ù u accent grave
                        chr(0xEC): 0x07,  # ì i accent grave
                        chr(0xF2): 0x08,  # ò o accent grave
                        chr(0xC7): 0x09,  # Ç C majuscule cedille
                        chr(0x0A): 0x0A,  # LF Line Feed
                        chr(0xD8): 0x0B,  # Ø O majuscule barré
                        chr(0xF8): 0x0C,  # ø o minuscule barré
                        chr(0x0D): 0x0D,  # CR Carriage Return
                        chr(0xC5): 0x0E,  # Å Angstroem majuscule
                        chr(0xE5): 0x0F,  # å Angstroem minuscule

                        '_': 0x11,  # underscore
                        chr(0xC6): 0x1C,  # Æ majuscule ae
                        chr(0xE6): 0x1D,  # æ minuscule ae
                        chr(0xDF): 0x1E,  # ß s dur allemand
                        chr(0xC9): 0x1F,  # É majuscule é

                        ' ': 0x20, '!': 0x21,
                        '\"': 0x22,  # guillemet
                        '#': 0x23,
                        '¤': 0x24,  # ¤ carré

                        chr(0xA1): 0x40,  # ¡ point d'exclamation renversé

                        chr(0xC4): 0x5B,  # Ä majuscule A trema
                        chr(0xE4): 0x7B,  # ä minuscule a trema

                        chr(0xD6): 0x5C,  # Ö majuscule O trema
                        chr(0xF6): 0x7C,  # ö minuscule o trema

                        chr(0xD1): 0x5D,  # Ñ majuscule N tilda espagnol
                        chr(0xF1): 0x7D,  # ñ minuscule n tilda espagnol

                        chr(0xDC): 0x5E,  # Ü majuscule U trema
                        chr(0xFC): 0x7E,  # ü minuscule u trema

                        chr(0xA7): 0x5F,  # § signe paragraphe

                        chr(0xBF): 0x60,  # ¿ point interrogation renversé

                        'à': 0x7F  # a accent grave
                        }

        gsmName = ''
        for char in sName:
            if ((char >= "%") and (char <= "?")):
                gsmName += char
            elif ((char >= "A") and (char <= "Z")):
                gsmName += char
            elif ((char >= "a") and (char <= "z")):
                gsmName += char
            else:
                gsmName += chr(dic_GSM_3_38[char])
        return gsmName

    def GSM3_38_2_ASCII(self, gsmName):
        """ converts a GSM name string to ascii string using GSM 3.38 conversion table.

            - gsmName   = string containing the gsm name
            - Returns   = ascii string representation of the name.

            sample : "\x00\x01\x02\x04\x05\x06Pascal"
            	     is converted to "@£$èéùPascal"
        """
        dic_GSM_3_38_toAscii = {0x00: '@',  # @ At symbol
                                0x01: '£',  # £ Britain pound symbol
                                0x02: '$',  # $ Dollar symbol
                                0x03: chr(0xA5),  # ¥ Yen symbol
                                0x04: 'è',  # è e accent grave
                                0x05: 'é',  # é e accent aigu
                                0x06: 'ù',  # ù u accent grave
                                0x07: chr(0xEC),  # ì i accent grave
                                0x08: chr(0xF2),  # ò o accent grave
                                0x09: chr(0xC7),  # Ç C majuscule cedille
                                0x0A: chr(0x0A),  # LF Line Feed
                                0x0B: chr(0xD8),  # Ø O majuscule barré
                                0x0C: chr(0xF8),  # ø o minuscule barré
                                0x0D: chr(0x0D),  # CR Carriage Return
                                0x0E: chr(0xC5),  # Å Angstroem majuscule
                                0x0F: chr(0xE5),  # å Angstroem minuscule
                                0x11: '_',  # underscore
                                0x1C: chr(0xC6),  # Æ majuscule ae
                                0x1D: chr(0xE6),  # æ minuscule ae
                                0x1E: chr(0xDF),  # ß s dur allemand
                                0x1F: chr(0xC9),  # É majuscule é

                                0x20: ' ',
                                0x21: '!',
                                0x22: '\"',  # guillemet
                                0x23: '#',
                                0x24: '¤',  # ¤ carré

                                0x40: chr(0xA1),  # ¡ point d'exclamation renversé
                                0x5B: chr(0xC4),  # Ä majuscule A trema
                                0x5C: chr(0xD6),  # Ö majuscule O trema
                                0x5D: chr(0xD1),  # Ñ majuscule N tilda espagnol
                                0x5E: chr(0xDC),  # Ü majuscule U trema
                                0x5F: chr(0xA7),  # § signe paragraphe
                                0x60: chr(0xBF),  # ¿ point interrogation renversé
                                0x7B: chr(0xE4),  # ä minuscule a trema
                                0x7C: chr(0xF6),  # ö minuscule o trema
                                0x7D: chr(0xF1),  # ñ minuscule n tilda espagnol
                                0x7E: chr(0xFC),  # ü minuscule u trema
                                0x7F: 'à'  # a accent grave
                                }

        sName = ""
        for i in gsmName:
            c = ord(i)
            if c == 0xFF:  # End of name reached, treat an NULL character
                break
            elif dic_GSM_3_38_toAscii.has_key(c):
                sName += dic_GSM_3_38_toAscii[c]
            else:
                sName += i
        return sName

    def padString(self, s, length, padding="F"):
        l = length - len(s)
        return s + padding * l

    def GSM7bit_2_Ascii(self, data):
        i = 0
        mask = 0x7F
        last = 0
        res = []
        for c in unhexlify(data):
            val = ((ord(c) & mask) << i) + (last >> (8 - i))
            res.append(chr(val))

            i += 1
            mask >>= 1
            last = ord(c)
            if i % 7 == 0:
                res.append(chr(last >> 1))
                i = 0
                mask = 0x7F
                last = 0
        return self.GSM3_38_2_ASCII(''.join(res))

    def convertTimestamp(self, ts):
        # 2050107034146B
        self.timetuple = [0, 0, 0, 0, 0, 0, 0, 0, 0]

        self.timetuple[0] = int(ts[0]) + int(ts[1]) * 10
        if self.timetuple[0] >= 80:
            # Convert to previous century, hopefully no one uses this after 2079 ;)
            self.timetuple[0] += 1900
        else:
            # Convert to current century
            self.timetuple[0] += 2000

        # ~ print ts
        self.timetuple[1] = int(ts[2]) + int(ts[3]) * 10
        self.timetuple[2] = int(ts[4]) + int(ts[5]) * 10
        self.timetuple[3] = int(ts[6]) + int(ts[7]) * 10
        self.timetuple[4] = int(ts[8]) + int(ts[9]) * 10
        self.timetuple[5] = int(ts[10]) + int(ts[11]) * 10
        self.timetuple[6] = calendar.weekday(self.timetuple[0], self.timetuple[1], self.timetuple[2])

        return time.asctime(self.timetuple)
