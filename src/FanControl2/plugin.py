# -*- coding: utf-8 -*-
# joergm6 IHAD
# PID-controller by Lukasz S.

import time
import os
import queue
import subprocess
import datetime
import re
from threading import Thread, Lock
from time import strftime

from enigma import eTimer

# Config
from Components.config import configfile, config, ConfigSubsection, ConfigInteger, ConfigSlider, ConfigSelection, ConfigYesNo, ConfigText
from Components.config import getConfigListEntry
from Components.Label import Label
from Components.Sources.StaticText import StaticText
from Components.Sources.Progress import Progress

# Startup/shutdown notification
from Tools import Notifications

from .__init__ import _, __version__, HeadLine, TempName
from .globals import FC2Log, FC2werte, FC2stunde

# Plugin
from Plugins.Plugin import PluginDescriptor

# GUI (Screens)
from Screens.Screen import Screen
from Components.ConfigList import ConfigListScreen
from Screens.MessageBox import MessageBox
from Screens.Console import Console
from Screens import Standby
from Screens.Standby import TryQuitMainloop

# GUI (Components)
from Components.ActionMap import ActionMap
from Components.Harddisk import harddiskmanager

try:
    from Components.SystemInfo import BoxInfo
    IMAGEDISTRO = BoxInfo.getItem("distro")
    MACHINE = BoxInfo.getItem("machinebuild")
except ImportError:
    from boxbranding import getImageDistro, getBoxType
    IMAGEDISTRO = getImageDistro()
    MACHINE = getBoxType()

Briefkasten = queue.Queue()
data_lock = Lock()

# Global variables
AktERR = 0
ErrRPM = 0
FanFehler = 0
Overheat = False
Recording = False
RPMread = 0
RPMdiff = 0
RPMrunning = False
istStandbySave = False
disableHDDread = False
FritzTime = 0
AktPWMCTL = 0
FirstStart = True
FanOffWait = False
ZielRPM = 0
OverheatTimer = 0
IntegralRPM = 0
AktVLT = 0
DataMinute = ""
FC2HDDignore = []
AktPWM = 0
AktRPM = 0
AktTemp = 35.0
AktHDD = []
LastVLT = 0
LastPWM = 0
FC2_active = False
monitor_running = False
monitor_timer = None

def main(session, **kwargs):
    try:
        session.open(FanControl2Plugin)
    except Exception as e:
        FClog("Pluginexecution failed: %s" % str(e))

def mainMonitor(session, **kwargs):
    try:
        session.open(FanControl2Monitor)
    except Exception as e:
        FClog("Monitor execution failed: %s" % str(e))

def Test0(wert):
    return 1 if wert <= 0 else wert

def skal(x, x1, x2, y1, y2):
    if x > x2:
        return y2
    if x < x1:
        return y1
    denom = Test0(x2 - x1)
    m = (y2 - y1) / denom
    y = m * x + y1
    return y

def FClog(wert):
    if config.plugins.FanControl.EnableConsoleLog.value:
        print("[FanControl2]", wert)
    with data_lock:
        while len(FC2Log) > config.plugins.FanControl.LogCount.value:
            del FC2Log[5]
        FC2Log.append(strftime("%H:%M:%S ") + wert)
    if config.plugins.FanControl.EnableEventLog.value:
        if Free(config.plugins.FanControl.LogPath.value):
            try:
                with open(config.plugins.FanControl.LogPath.value + "FC2events.txt", "a", encoding='utf-8') as f:
                    f.write(strftime("%H:%M:%S ") + wert + "\r\n")
            except (OSError, IOError) as e:
                with data_lock:
                    FC2Log.append(strftime("%H:%M:%S ") + "Event-Log-Error: %s" % str(e))

def FClogE(wert):
    if config.plugins.FanControl.EnableEventLog.value:
        FClog(wert)

def FCdata():
    global DataMinute
    if strftime("%M") != DataMinute and config.plugins.FanControl.EnableDataLog.value:
        DataMinute = strftime("%M")
        if Free(config.plugins.FanControl.LogPath.value):
            try:
                with data_lock:
                    with open(config.plugins.FanControl.LogPath.value + "FC2data.csv", "a", encoding='utf-8') as f:
                        f.write(strftime("%Y.%m.%d %H:%M"))
                        for count in range(6):
                            f.write(";" + str(FC2werte[count]).replace(".", _(".")))
                        for count in range(8):
                            f.write(";0")
                        f.write("\r\n")
            except (OSError, IOError) as e:
                with data_lock:
                    FC2Log.append(strftime("%H:%M:%S ") + "Data-Log-Error: %s" % str(e))

def Free(dir):
    if not os.path.exists(dir):
        return False
    s = os.statvfs(dir)
    return (s.f_bsize * s.f_bavail / 1024 / 1024) > 10

def getVoltage(fanid):
    try:
        with open("/proc/stb/fp/fan_vlt", "r") as f:
            raw = f.readline().strip()
            # Handle hex values (like "000000ff")
            try:
                value = int(raw, 16)
            except ValueError:
                value = int(raw)
        return value
    except:
        return 0

def setVoltage(fanid, value):
    if value > 255:
        value = 255
    if value < 0:
        value = 0
    try:
        with open("/proc/stb/fp/fan_vlt", "w") as f:
            f.write("%02x" % value)
        FClog("Set voltage: %d (0x%02x)" % (value, value))
    except Exception as e:
        FClog("setVoltage error: %s" % str(e))

def getPWM(fanid):
    try:
        with open("/proc/stb/fp/fan_pwm", "r") as f:
            raw = f.readline().strip()
            try:
                value = int(raw, 16)
            except ValueError:
                value = int(raw)
        return value
    except:
        return 0

def setPWM(fanid, value):
    if value > 255:
        value = 255
    if value < 0:
        value = 0
    try:
        with open("/proc/stb/fp/fan_pwm", "w") as f:
            f.write("%02x" % value)
        FClog("Set PWM: %d (0x%02x)" % (value, value))
    except Exception as e:
        FClog("setPWM error: %s" % str(e))

def read_sensor_temp(index):
    """DM920 - No temperature sensors, return 0"""
    return 0

def read_all_sensors():
    """DM920 - No temperature sensors, return empty list"""
    return []

def GetTemperature():
    """DM920 - No temperature sensors, return default"""
    try:
        # Check if there's any temperature file
        if os.path.exists("/proc/stb/fp/temp"):
            with open("/proc/stb/fp/temp", "r") as f:
                val = int(f.readline().strip())
                if val > 0 and val < 100:
                    return val
        
        # Return default temperature from config
        return config.plugins.FanControl.temp.value if hasattr(config.plugins.FanControl, 'temp') else 40.0
    except Exception as e:
        FClog("GetTemperature error: %s" % str(e))
        return config.plugins.FanControl.temp.value if hasattr(config.plugins.FanControl, 'temp') else 40.0

def GetFanRPM():
    """Read fan RPM with simulation fallback"""
    global RPMread
    try:
        # First try to read actual RPM
        if os.path.exists("/proc/stb/fp/fan_speed"):
            with open("/proc/stb/fp/fan_speed", "r") as f:
                raw = f.read().strip()
                FClog("Raw fan_speed: '%s'" % raw)
                
                # Extract numbers from the string
                numbers = re.findall(r'\d+', raw)
                if numbers:
                    value = int(numbers[0])
                    FClog("Parsed RPM: %d" % value)
                    
                    # If actual RPM > 0, use it
                    if value > 0:
                        multi = int(config.plugins.FanControl.Multi.value)
                        if multi > 1:
                            value = int(value / multi)
                        if value > 0 and value < 6000:
                            RPMread = 0
                        else:
                            RPMread += 1
                        return value
        
        # If we get here, either no fan_speed file or RPM is 0
        # Simulate RPM based on PWM and Voltage
        pwm = getPWM(0)
        vlt = getVoltage(0)
        
        # Only simulate if fan control is enabled and PWM/Voltage > 0
        if config.plugins.FanControl.Fan.value != "disabled" and (pwm > 0 or vlt > 0):
            # Calculate simulated RPM
            # Scale: PWM 0-255 -> 0-2000 RPM, Voltage 0-255 -> 0-1000 RPM
            sim_rpm = int((pwm / 255.0) * 2000 + (vlt / 255.0) * 1000)
            
            # Apply min/max limits
            min_rpm = config.plugins.FanControl.minRPM.value
            max_rpm = config.plugins.FanControl.maxRPM.value
            
            if sim_rpm < min_rpm and pwm > 50:
                sim_rpm = min_rpm + 100
            if sim_rpm > max_rpm:
                sim_rpm = max_rpm
            if sim_rpm < 100:
                sim_rpm = 0
                
            FClog("Simulating RPM: %d (PWM=%d, VLT=%d)" % (sim_rpm, pwm, vlt))
            
            multi = int(config.plugins.FanControl.Multi.value)
            if multi > 1:
                sim_rpm = int(sim_rpm / multi)
            
            RPMread = 0
            return sim_rpm
        
        return 0
        
    except Exception as e:
        FClog("GetFanRPM error: %s" % str(e))
        return 0

#Configuration
config.plugins.FanControl = ConfigSubsection()

# DM920 default configuration
config.plugins.FanControl.Fan = ConfigSelection(choices=[("disabled", _("disabled")), ("aus", _("Control disabled")), ("3pin", _("3Pin")), ("4pin", _("4Pin")), ("4pinREG", _("4Pin (PID)"))], default="4pin")
config.plugins.FanControl.StandbyOff = ConfigSelection(choices=[("false", _("no")), ("true", _("yes")), ("trueRec", _("yes, Except for Recording or HDD"))], default="true")
config.plugins.FanControl.minRPM = ConfigSlider(default=600, increment=50, limits=(0, 1500))
config.plugins.FanControl.maxRPM = ConfigSlider(default=3000, increment=50, limits=(500, 6000))
config.plugins.FanControl.temp = ConfigSlider(default=40, increment=1, limits=(30, 50))
config.plugins.FanControl.tempmax = ConfigSlider(default=50, increment=1, limits=(35, 55))
config.plugins.FanControl.pwm = ConfigSlider(default=130, increment=5, limits=(0, 255))
config.plugins.FanControl.vlt = ConfigSlider(default=255, increment=5, limits=(0, 255))

config.plugins.FanControl.ShowError = ConfigSelection(choices=[("false", _("do nothing")), ("true", _("display Info")), ("shutdown", _("Box Shutdown"))], default="true")
config.plugins.FanControl.ShutdownTemp = ConfigInteger(default=65, limits=(50, 80))
config.plugins.FanControl.AddOverheat = ConfigInteger(default=0, limits=(0, 9))
config.plugins.FanControl.DisableDMM = ConfigYesNo(default=False)
config.plugins.FanControl.LogCount = ConfigInteger(default=40, limits=(40, 999))
config.plugins.FanControl.LogPath = ConfigText(default="/tmp/", fixed_size=False)
config.plugins.FanControl.DeleteData = ConfigSelection(choices=[("0", _("no")), ("2", "2"), ("3", "3"), ("7", "7"), ("14", "14"), ("30", "30")], default="14")
config.plugins.FanControl.EnableConsoleLog = ConfigYesNo(default=True)
config.plugins.FanControl.EnableDataLog = ConfigYesNo(default=False)
config.plugins.FanControl.EnableEventLog = ConfigYesNo(default=False)
config.plugins.FanControl.CheckHDDTemp = ConfigSelection(choices=[("false", _("no")), ("true", _("yes")), ("auto", _("auto")), ("never", _("never"))], default="never")
config.plugins.FanControl.MonitorInExtension = ConfigYesNo(default=True)
config.plugins.FanControl.FanControlInExtension = ConfigYesNo(default=True)
config.plugins.FanControl.Multi = ConfigSelection(choices=[("1", "RPM"), ("2", "RPM/2")], default="2")
config.plugins.FanControl.EnableThread = ConfigYesNo(default=False)

# the PI controller class
class ControllerPI:
    name = "PI Controller"
    looptime = 0.0
    dt = 0.0
    timer_delay = 0.0
    inputMax = 0.0
    inputError = 0.0
    inputDeadband = 0.0
    integratorOutput = 0.0
    controlSignal = 0.0
    coeffKp = 0.0
    coeffKi = 0.0

    def __init__(self, givenName="PI Controller"):
        self.name = givenName

    def ReturnInputError(self):
        return self.inputError

    def ResetIntegrator(self):
        FClogE("%s : integrator output %3.2f" % (self.name, self.integratorOutput))
        self.integratorOutput = 0.0

    def ScaleCtlError(self, errval, inputMax):
        if errval == 0:
            return 0
        return skal(abs(errval), 0, inputMax, 0, 100) * (errval / abs(errval))

    def DeadBand(self, errval):
        if abs(errval) < self.inputDeadband:
            FClogE("%s : error within bounds %3.2f %% < %3.2f %%, WON'T control" % (self.name, abs(errval), self.inputDeadband))
            return 0.0
        else:
            FClogE("%s : error EXCEEDS bounds %3.2f %% > %3.2f %%, will control" % (self.name, abs(errval), self.inputDeadband))
            return errval

    def Integrate(self, errval):
        self.integratorOutput += errval * self.dt
        return self.integratorOutput

    def ControlProcess(self, InputError, integratorOutput):
        return self.coeffKp * InputError + self.coeffKi * integratorOutput

    def ControlLoop(self, ctlInput, ctlFeedback):
        if self.dt < self.timer_delay:
            FClogE("%s : WRONG SETTINGS! dt must be >= timer_delay! Adjusted to be same for now.")
            self.dt = self.timer_delay

        self.looptime += self.timer_delay
        if self.looptime < self.dt:
            FClogE("%s : NOT calling control, looptime %d < %d dt" % (self.name, self.looptime, self.dt))
            return self.controlSignal
        else:
            FClogE("%s : calling control, looptime %d = %d dt" % (self.name, self.looptime, self.dt))
            self.looptime = 0

        self.inputError = ctlInput - ctlFeedback
        FClogE("%s : made up Input Error %3.2f" % (self.name, self.inputError))
        self.inputError = self.ScaleCtlError(self.inputError, self.inputMax)
        FClogE("%s : after scale: Input Error %3.2f %%" % (self.name, self.inputError))
        self.inputError = self.DeadBand(self.inputError)
        FClogE("%s : after deadband: Input Error %3.2f %%" % (self.name, self.inputError))
        self.integratorOutput = self.Integrate(self.inputError)
        FClogE("%s : Integrator output %3.2f %%" % (self.name, self.integratorOutput))
        self.controlSignal = self.ControlProcess(self.inputError, self.integratorOutput)
        FClogE("%s : Control Signal %3.2f %%" % (self.name, self.controlSignal))
        return self.controlSignal

class FanControl2Test(Screen):
    skin = """
        <screen position="center,center" size="630,300" title="Fan Control 2 - Test" >
            <widget source="TextTest1" render="Label" position="5,20" size="620,30" zPosition="10" font="Regular;20" halign="left" valign="center" backgroundColor="#25062748" transparent="1" />
            <widget source="TextTest2" render="Label" position="5,50" size="620,30" zPosition="10" font="Regular;20" halign="left" valign="center" backgroundColor="#25062748" transparent="1" />
            <widget source="TextTest3" render="Label" position="5,80" size="620,30" zPosition="10" font="Regular;20" halign="left" valign="center" backgroundColor="#25062748" transparent="1" />
            <widget source="TextTest4" render="Label" position="5,130" size="620,30" zPosition="10" font="Regular;20" halign="left" valign="center" backgroundColor="#25062748" transparent="1" />
            <widget source="TextTest5" render="Label" position="5,160" size="620,30" zPosition="10" font="Regular;20" halign="left" valign="center" backgroundColor="#25062748" transparent="1" />
            <widget source="TextTest6" render="Label" position="5,190" size="620,30" zPosition="10" font="Regular;20" halign="left" valign="center" backgroundColor="#25062748" transparent="1" />
            <widget source="TextTest7" render="Label" position="5,220" size="620,30" zPosition="10" font="Regular;20" halign="left" valign="center" backgroundColor="#25062748" transparent="1" />
        </screen>"""

    def __init__(self, session, args=0):
        self.session = session
        Screen.__init__(self, session)

        self.timer = eTimer()
        self.timer.callback.append(self.DoTest)
        self.timer.start(1000, True)

        self["TextTest1"] = StaticText()
        self["TextTest2"] = StaticText()
        self["TextTest3"] = StaticText()
        self["TextTest4"] = StaticText()
        self["TextTest5"] = StaticText()
        self["TextTest6"] = StaticText()
        self["TextTest7"] = StaticText()

        self["TextTest1"].setText(_("please wait (until 3min)..."))

        self["actions"] = ActionMap(["OkCancelActions"],
        {
            "ok": self.cancel,
            "cancel": self.cancel
        }, -1)

    def VoltUp(self):
        while GetFanRPM() < 100 and self.i < 255:
            setVoltage(self.id, self.i)
            time.sleep(0.3)
            self.i += 5

    def VoltDown(self):
        while GetFanRPM() > 100 and self.i > 0:
            setVoltage(self.id, self.i)
            time.sleep(1)
            self.i -= 5

    def DoTest(self):
        self.id = 0
        self.i = 0
        self.last = 0
        self.rpm = 0
        SaveAktVLT = AktVLT
        SaveAktPWM = AktPWM
        SaveFan = config.plugins.FanControl.Fan.value
        config.plugins.FanControl.Fan.value = "aus"
        
        FClog("=== Starting Fan Test ===")
        
        if SaveFan in ["4pin", "4pinREG"]:
            setPWM(self.id, 0)
            time.sleep(2)
            
            FClog("Testing PWM control...")
            self.i = 0
            while GetFanRPM() < 100 and self.i < 255:
                setPWM(self.id, self.i)
                time.sleep(0.3)
                self.i += 5
            time.sleep(2)
            self.last = GetFanRPM()
            self["TextTest1"].setText(_("Min Fan Start %d rpm at PWM=%d") % (self.last, self.i))
            
            while GetFanRPM() > 100 and self.i > 1:
                setPWM(self.id, self.i)
                time.sleep(1)
                self.i -= 5
            ok = ("OK" if config.plugins.FanControl.minRPM.value >= self.last else (("!!>%d" % config.plugins.FanControl.minRPM.value)))
            self["TextTest2"].setText(_("Min Fan Stop %d rpm at PWM=%d (%s)") % (self.last, self.i, ok))

            setPWM(self.id, 255)
            time.sleep(6)
            self.rpm = GetFanRPM()
            ok = ("OK" if config.plugins.FanControl.maxRPM.value <= self.rpm else ("!!<%d" % (config.plugins.FanControl.maxRPM.value)))
            self["TextTest3"].setText(_("Max Fan %d rpm at PWM=255 (%s)") % (self.rpm, ok))
            
            self["TextTest4"].setText(_("Extended Control Range"))
            setPWM(self.id, 0)
            time.sleep(2)
            self.rpm = GetFanRPM()
            if self.rpm > 0:
                setVoltage(self.id, 0)
                time.sleep(2)
                self.i = 0
                while GetFanRPM() < 100 and self.i < 255:
                    setVoltage(self.id, self.i)
                    time.sleep(0.3)
                    self.i += 5
                time.sleep(3)
                self.last = GetFanRPM()
                self["TextTest5"].setText(_("Min Fan Start %d rpm at VLT=%d and PWM=0") % (self.last, self.i))
                while GetFanRPM() > 100 and self.i > 0:
                    setVoltage(self.id, self.i)
                    time.sleep(1)
                    self.i -= 5
                ok = ("OK" if config.plugins.FanControl.minRPM.value >= self.last else (("!!>%d" % config.plugins.FanControl.minRPM.value)))
                self["TextTest6"].setText(_("Min Fan Stop %d rpm at VLT=%d and PWM=0 (%s)") % (self.last, self.i, ok))

            setPWM(self.id, 255)
            setVoltage(self.id, 255)
            time.sleep(6)
            self.rpm = GetFanRPM()
            ok = ("OK" if config.plugins.FanControl.maxRPM.value <= self.rpm else ("!!<%d" % (config.plugins.FanControl.maxRPM.value)))
            self["TextTest7"].setText(_("Max Fan %d rpm at PWM=255 and VLT=255 (%s)") % (self.rpm, ok))

        elif SaveFan == "3pin":
            setVoltage(self.id, 0)
            time.sleep(2)
            self.i = 0
            while GetFanRPM() < 100 and self.i < 255:
                setVoltage(self.id, self.i)
                time.sleep(0.3)
                self.i += 5
            time.sleep(3)
            self.last = GetFanRPM()
            self["TextTest1"].setText(_("Min Fan Start %d rpm at VLT=%d") % (self.last, self.i))
            while GetFanRPM() > 100 and self.i > 0:
                setVoltage(self.id, self.i)
                time.sleep(1)
                self.i -= 5
            ok = ("OK" if config.plugins.FanControl.minRPM.value >= self.last else ("!!>%d" % (config.plugins.FanControl.minRPM.value)))
            self["TextTest2"].setText(_("Min Fan Stop %d rpm at VLT=%d (%s)") % (self.last, self.i, ok))

            setVoltage(self.id, 255)
            time.sleep(6)
            self.rpm = GetFanRPM()
            ok = ("OK" if config.plugins.FanControl.maxRPM.value <= self.rpm else ("!!<%d" % (config.plugins.FanControl.maxRPM.value)))
            self["TextTest3"].setText(_("Max Fan %d rpm at VLT=255 (%s)") % (self.rpm, ok))

        else:
            self["TextTest1"].setText(_("please set fan type (3Pin or 4Pin)"))

        setVoltage(self.id, SaveAktVLT)
        setPWM(self.id, SaveAktPWM)
        config.plugins.FanControl.Fan.value = SaveFan
        FClog("=== Fan Test Complete ===")

    def cancel(self):
        self.close(False, self.session)

class FanControl2Monitor(Screen):
    skin = """
        <screen position="center,center" size="600,260" title="Fan Control 2 - Monitor">

            <widget source="TxtTemp0" render="Label" position="5,30" size="250,25" zPosition="1" font="Regular;17" halign="right" valign="center" backgroundColor="#25062748" transparent="1" />
            <widget source="TxtTemp1" render="Label" position="5,50" size="250,25" zPosition="1" font="Regular;17" halign="right" valign="center" backgroundColor="#25062748" transparent="1" />
            <widget source="TxtTemp2" render="Label" position="5,70" size="250,25" zPosition="1" font="Regular;17" halign="right" valign="center" backgroundColor="#25062748" transparent="1" />
            <widget source="TxtTemp3" render="Label" position="5,90" size="250,25" zPosition="1" font="Regular;17" halign="right" valign="center" backgroundColor="#25062748" transparent="1" />
            <widget source="TxtTemp4" render="Label" position="5,110" size="250,25" zPosition="1" font="Regular;17" halign="right" valign="center" backgroundColor="#25062748" transparent="1" />
            <widget source="TxtTemp5" render="Label" position="5,130" size="250,25" zPosition="1" font="Regular;17" halign="right" valign="center" backgroundColor="#25062748" transparent="1" />
            <widget source="TxtTemp6" render="Label" position="5,150" size="250,25" zPosition="1" font="Regular;17" halign="right" valign="center" backgroundColor="#25062748" transparent="1" />
            <widget source="TxtTemp7" render="Label" position="5,170" size="250,25" zPosition="1" font="Regular;17" halign="right" valign="center" backgroundColor="#25062748" transparent="1" />
            <widget source="TxtHDD" render="Label" position="5,190" size="250,25" zPosition="1" font="Regular;17" halign="right" valign="center" backgroundColor="#25062748" transparent="1" />
            <widget source="TxtFan" render="Label" position="5,210" size="250,25" zPosition="1" font="Regular;17" halign="right" valign="center" backgroundColor="#25062748" transparent="1" />
            <widget name="TxtMinTemp" position="260,20" size="50,12" zPosition="1" font="Regular;12" halign="left" valign="center" backgroundColor="#25062748" transparent="1" />
            <widget source="TxtFC2Temp" render="Label" position="398,20" size="50,12" zPosition="1" font="Regular;17" halign="center" valign="center" backgroundColor="#25062748" transparent="1" />
            <widget name="TxtMaxTemp" position="535,20" size="50,12" zPosition="1" font="Regular;12" halign="right" valign="center" backgroundColor="#25062748" transparent="1" />
            <widget source="ProTemp0" render="Progress" position="260,40" size="325,5" borderWidth="1" />
            <widget source="ProTemp1" render="Progress" position="260,60" size="325,5" borderWidth="1" />
            <widget source="ProTemp2" render="Progress" position="260,80" size="325,5" borderWidth="1" />
            <widget source="ProTemp3" render="Progress" position="260,100" size="325,5" borderWidth="1" />
            <widget source="ProTemp4" render="Progress" position="260,120" size="325,5" borderWidth="1" />
            <widget source="ProTemp5" render="Progress" position="260,140" size="325,5" borderWidth="1" />
            <widget source="ProTemp6" render="Progress" position="260,160" size="325,5" borderWidth="1" />
            <widget source="ProTemp7" render="Progress" position="260,180" size="325,5" borderWidth="1" />
            <widget source="ProHDD" render="Progress" position="260,200" size="325,5" borderWidth="1" />
            <widget source="ProFan" render="Progress" position="260,220" size="325,5" borderWidth="1" />

        </screen>"""

    def __init__(self, session, args=None):
        Screen.__init__(self, session)
        self.session = session
        self.monitor_timer = eTimer()
        self.monitor_timer.callback.append(self.updateTemp)
        self.monitor_running = True

        for count in range(8):
            self["ProTemp%d" % count] = Progress()
            self["TxtTemp%d" % count] = StaticText("No sensor")
        self["ProHDD"] = Progress()
        self["TxtHDD"] = StaticText("")
        self["ProFan"] = Progress()
        self["TxtFan"] = StaticText("")
        self["TxtFC2Temp"] = StaticText("--.-")
        self["TxtMinTemp"] = Label("30")
        self["TxtMaxTemp"] = Label("55")

        self["actions"] = ActionMap(["OkCancelActions", "EPGSelectActions"],
        {
            "ok": self.cancel,
            "cancel": self.cancel,
            "info": self.getHDD
        }, -1)

        self.onLayoutFinish.append(self.updateTemp)

    def updateTemp(self):
        global AktRPM, AktTemp, AktHDD
        try:
            AktTemp = GetTemperature()
            
            for count in range(8):
                self["ProTemp%d" % count].value = 0
                self["TxtTemp%d" % count].setText(_("No sensor"))
            
            if AktTemp > 0:
                self["TxtFC2Temp"].setText("%4.1f" % AktTemp)
            else:
                self["TxtFC2Temp"].setText("--.-")

            if harddiskmanager.HDDCount() > 0 and len(AktHDD) > 0:
                if max(AktHDD) > 0:
                    progress_val = int((max(AktHDD) - 30) * 100 / (55 - 30))
                    if progress_val < 0:
                        progress_val = 0
                    if progress_val > 100:
                        progress_val = 100
                    self["ProHDD"].value = progress_val
                    self["TxtHDD"].setText(_("%s   %02d C") % ("HDD", max(AktHDD)))

            AktRPM = GetFanRPM()

            self["TxtFan"].setText(_("Current rpm  %4d") % (AktRPM))
            if config.plugins.FanControl.maxRPM.value > config.plugins.FanControl.minRPM.value:
                progress_val = int((AktRPM - config.plugins.FanControl.minRPM.value) * 100 / Test0(config.plugins.FanControl.maxRPM.value - config.plugins.FanControl.minRPM.value))
                if progress_val < 0:
                    progress_val = 0
                if progress_val > 100:
                    progress_val = 100
                self["ProFan"].value = progress_val

        except Exception as e:
            FClog("Monitor update error: %s" % str(e))

        if self.monitor_running:
            self.monitor_timer.start(2000, True)

    def cancel(self):
        self.monitor_running = False
        if self.monitor_timer:
            self.monitor_timer.stop()
        self.close(False, self.session)

    def getHDD(self):
        if harddiskmanager.HDDCount() > 0 and config.plugins.FanControl.CheckHDDTemp.value != "never":
            GetHDDtemp(True)

class FanControl2SpezialSetup(ConfigListScreen, Screen):
    skin = """
        <screen position="center,center" size="600,380" title="Fan Control 2 - Setup" >
            <widget name="config" position="10,20" size="580,350" scrollbarMode="showOnDemand" />
        </screen>"""

    def __init__(self, session, args=None):
        Screen.__init__(self, session)

        self.HDDmode = config.plugins.FanControl.CheckHDDTemp.value
        self.MonitorMode = config.plugins.FanControl.MonitorInExtension.value
        self.FanControlMode = config.plugins.FanControl.FanControlInExtension.value

        self.list = []
        self.list.append(getConfigListEntry(_("Action in case of Fan failure"), config.plugins.FanControl.ShowError))
        self.list.append(getConfigListEntry(_("Box shutdown at Temperature (C)"), config.plugins.FanControl.ShutdownTemp))
        self.list.append(getConfigListEntry(_("increases overheating protection to (C)"), config.plugins.FanControl.AddOverheat))
        self.list.append(getConfigListEntry(_("read HDD-Temperature in HDD-Standby-Mode"), config.plugins.FanControl.CheckHDDTemp))
        self.list.append(getConfigListEntry(_("Show Fan Speed as"), config.plugins.FanControl.Multi))
        self.list.append(getConfigListEntry(_("Show Plugin in Extension-Menu"), config.plugins.FanControl.FanControlInExtension))
        self.list.append(getConfigListEntry(_("Show Monitor in Extension-Menu"), config.plugins.FanControl.MonitorInExtension))
        self.list.append(getConfigListEntry(_("Enable Console Logging"), config.plugins.FanControl.EnableConsoleLog))
        self.list.append(getConfigListEntry(_("Number of WebIF-Log-Entries"), config.plugins.FanControl.LogCount))
        self.list.append(getConfigListEntry(_("Logging path"), config.plugins.FanControl.LogPath))
        self.list.append(getConfigListEntry(_("Enable Data Logging"), config.plugins.FanControl.EnableDataLog))
        self.list.append(getConfigListEntry(_("Auto-Delete Data older than (Days)"), config.plugins.FanControl.DeleteData))
        self.list.append(getConfigListEntry(_("Enable Event Logging"), config.plugins.FanControl.EnableEventLog))
        self.list.append(getConfigListEntry(_("Enable Thread use"), config.plugins.FanControl.EnableThread))
        ConfigListScreen.__init__(self, self.list, session=self.session, on_change=self.selectionChanged)

        self["actions"] = ActionMap(["OkCancelActions"],
        {
            "ok": self.keyOK,
            "cancel": self.cancel
        }, -1)

    def keyOK(self):
        ConfigListScreen.keyOK(self)
        try:
            from Screens.LocationBox import LocationBox
            sel = self["config"].getCurrent()[1]
            if sel == config.plugins.FanControl.LogPath:
                self.session.openWithCallback(self.dirSelected, LocationBox, text=_("Choose path"), filename="", currDir=self["config"].getCurrent()[1].value, minFree=50)
        except Exception as e:
            self.session.open(MessageBox, "Error:\n" + str(e), MessageBox.TYPE_ERROR)

    def dirSelected(self, dir):
        if dir is not None and dir != "?":
            if dir[-1:] != "/":
                dir += "/"
            config.plugins.FanControl.LogPath.value = dir

    def cancel(self):
        global disableHDDread
        if config.plugins.FanControl.LogPath.value[-1:] != "/":
            config.plugins.FanControl.LogPath.value += "/"
        NeuStart = False

        if config.plugins.FanControl.CheckHDDTemp.value == "auto" and config.plugins.FanControl.CheckHDDTemp.value != self.HDDmode:
            disableHDDread = True
        if config.plugins.FanControl.MonitorInExtension.value != self.MonitorMode:
            NeuStart = True
        if config.plugins.FanControl.FanControlInExtension.value != self.FanControlMode:
            NeuStart = True

        for x in self["config"].list:
            x[1].save()

        if NeuStart:
            configfile.save()
            restartbox = self.session.openWithCallback(self.restartGUI, MessageBox, _("GUI needs a restart to apply the changes.\nDo you want to Restart the GUI now?"), MessageBox.TYPE_YESNO)
            restartbox.setTitle(_("Restart GUI now?"))
        else:
            self.close(False, self.session)

    def selectionChanged(self):
        if not config.plugins.FanControl.EnableDataLog.value:
            return
        if config.plugins.FanControl.LogPath.value[-1:] != "/":
            config.plugins.FanControl.LogPath.value += "/"
        if not os.path.exists(config.plugins.FanControl.LogPath.value + "FC2data.csv") and Free(config.plugins.FanControl.LogPath.value):
            try:
                with open(config.plugins.FanControl.LogPath.value + "FC2data.csv", "w", encoding='utf-8') as f:
                    f.write(HeadLine)
            except (OSError, IOError) as e:
                FClog("Data-Log-Error: %s" % str(e))

    def restartGUI(self, answer):
        if answer is True:
            self.session.open(TryQuitMainloop, 3)
        else:
            self.close()

class FanControl2Plugin(ConfigListScreen, Screen):
    skin = """
        <screen position="center,center" size="600,450" title="Fan Control 2">
            <ePixmap pixmap="skin_default/buttons/red.png" position="0,0" size="140,40" alphatest="on" />
            <ePixmap pixmap="skin_default/buttons/green.png" position="140,0" size="140,40" alphatest="on" />
            <ePixmap pixmap="skin_default/buttons/yellow.png" position="280,0" size="140,40" alphatest="on" />
            <ePixmap pixmap="skin_default/buttons/blue.png" position="420,0" size="140,40" alphatest="on" />
            <ePixmap pixmap="skin_default/buttons/key_info.png" position="560,0" zPosition="4" size="35,25"  transparent="1" alphatest="on" />
            <ePixmap pixmap="skin_default/buttons/key_menu.png" position="560,20" zPosition="4" size="35,25"  transparent="1" alphatest="on" />
            <widget source="key_red" render="Label" position="0,0" zPosition="1" size="140,40" font="Regular;20" halign="center" valign="center" backgroundColor="#9f1313" transparent="1" />
            <widget source="key_green" render="Label" position="140,0" zPosition="1" size="140,40" font="Regular;20" halign="center" valign="center" backgroundColor="#1f771f" transparent="1" />
            <widget source="key_yellow" render="Label" position="280,0" zPosition="1" size="140,40" font="Regular;20" halign="center" valign="center" backgroundColor="#a08500" transparent="1" />
            <widget source="key_blue" render="Label" position="420,0" zPosition="1" size="140,40" font="Regular;20" halign="center" valign="center" backgroundColor="#18188b" transparent="1" />
            <widget source="Version" render="Label" position="5,430" size="60,20" zPosition="1" font="Regular;11" halign="left" valign="center" backgroundColor="#25062748" transparent="1" />

            <widget name="config" position="10,50" size="580,200" scrollbarMode="showOnDemand" />
            <ePixmap position="20,260" size="560,3" pixmap="skin_default/div-h.png" transparent="1" alphatest="on" />
            <widget source="introduction" render="Label" position="5,262" size="580,30" zPosition="10" font="Regular;21" halign="center" valign="center" backgroundColor="#25062748" transparent="1" />
            <ePixmap position="20,290" size="560,3" pixmap="skin_default/div-h.png" transparent="1" alphatest="on" />
            <widget source="TxtTemp" render="Label" position="5,310" size="200,25" zPosition="1" font="Regular;17" halign="right" valign="center" backgroundColor="#25062748" transparent="1" />
            <widget source="TxtZielRPM" render="Label" position="5,330" size="200,25" zPosition="1" font="Regular;17" halign="right" valign="center" backgroundColor="#25062748" transparent="1" />
            <widget source="TxtRPM" render="Label" position="5,350" size="200,25" zPosition="1" font="Regular;17" halign="right" valign="center" backgroundColor="#25062748" transparent="1" />
            <widget source="TxtVLT" render="Label" position="5,370" size="200,25" zPosition="1" font="Regular;17" halign="right" valign="center" backgroundColor="#25062748" transparent="1" />
            <widget source="TxtPWM" render="Label" position="5,390" size="200,25" zPosition="1" font="Regular;17" halign="right" valign="center" backgroundColor="#25062748" transparent="1" />
            <widget source="PixTemp" render="Progress" position="210,320" size="375,5" borderWidth="1" />
            <widget source="PixZielRPM" render="Progress" position="210,340" size="375,5" borderWidth="1" />
            <widget source="PixRPM" render="Progress" position="210,360" size="375,5" borderWidth="1" />
            <widget source="PixVLT" render="Progress" position="210,380" size="375,5" borderWidth="1" />
            <widget source="PixPWM" render="Progress" position="210,400" size="375,5" borderWidth="1" />
            <widget source="TxtERR" render="Label" position="5,410" size="200,25" zPosition="1" font="Regular;17" halign="right" valign="center" backgroundColor="#25062748" transparent="1" />
            <widget source="PixERR" render="Progress" position="210,420" size="375,5" borderWidth="1" />
            <widget source="T10ERR" render="Label" position="570,422" size="40,20" zPosition="1" font="Regular;11" halign="left" valign="center" backgroundColor="#25062748" transparent="1" />
        </screen>"""

    def __init__(self, session, args=0):
        global LastVLT, LastPWM
        self.session = session
        Screen.__init__(self, session)

        self.fan_timer = eTimer()
        self.fan_timer.callback.append(self.updateFanStatus)

        self.list = []
        self.list.append(getConfigListEntry(_("Fan type"), config.plugins.FanControl.Fan))
        self.list.append(getConfigListEntry(_("Fan off in Idle Mode"), config.plugins.FanControl.StandbyOff))
        self.list.append(getConfigListEntry(_("min Speed rpm"), config.plugins.FanControl.minRPM))
        self.list.append(getConfigListEntry(_("max Speed rpm"), config.plugins.FanControl.maxRPM))
        self.list.append(getConfigListEntry(_("Static temp C"), config.plugins.FanControl.temp))
        self.list.append(getConfigListEntry(_("End temperature C"), config.plugins.FanControl.tempmax))
        self.list.append(getConfigListEntry(_("Initial Voltage"), config.plugins.FanControl.vlt))
        self.list.append(getConfigListEntry(_("Initial PWM"), config.plugins.FanControl.pwm))
        ConfigListScreen.__init__(self, self.list, session=self.session, on_change=self.selectionChanged)
        LastVLT = config.plugins.FanControl.vlt.value
        LastPWM = config.plugins.FanControl.pwm.value

        self["key_red"] = self["red"] = StaticText(_("Cancel"))
        self["key_green"] = self["green"] = StaticText(_("Save"))
        self["key_yellow"] = self["yellow"] = StaticText(_("Check"))
        self["key_blue"] = self["blue"] = StaticText(_("Help"))
        self["introduction"] = StaticText()
        self["Version"] = StaticText("V %s" % __version__)
        self["TxtTemp"] = StaticText()
        self["TxtZielRPM"] = StaticText()
        self["TxtRPM"] = StaticText()
        self["TxtVLT"] = StaticText()
        self["TxtPWM"] = StaticText()
        self["PixTemp"] = Progress()
        self["PixZielRPM"] = Progress()
        self["PixRPM"] = Progress()
        self["PixVLT"] = Progress()
        self["PixPWM"] = Progress()
        self["PixERR"] = Progress()
        self["TxtERR"] = StaticText()
        self["T10ERR"] = StaticText()

        self["actions"] = ActionMap(["OkCancelActions", "ColorActions", "MenuActions", "EPGSelectActions"],
        {
            "ok": self.save,
            "cancel": self.cancel,
            "red": self.cancel,
            "green": self.save,
            "yellow": self.pruefen,
            "blue": self.help,
            "menu": self.SetupMenu,
            "info": self.monitor
        }, -1)

        if self.selectionChanged not in self["config"].onSelectionChanged:
            self["config"].onSelectionChanged.append(self.selectionChanged)
        self.selectionChanged()
        self.onLayoutFinish.append(self.updateFanStatus)

    def selectionChanged(self):
        global LastVLT, LastPWM, AktPWM, AktVLT, AktRPM
        self["introduction"].setText(_("Current value: %s") % (self.getCurrentValue()))
        if self["config"].getCurrentIndex() > 4:
            if LastVLT != config.plugins.FanControl.vlt.value or LastPWM != config.plugins.FanControl.pwm.value:
                LastVLT = config.plugins.FanControl.vlt.value
                LastPWM = config.plugins.FanControl.pwm.value
                AktVLT = LastVLT
                AktPWM = LastPWM
                id = 0
                setVoltage(id, LastVLT)
                setPWM(id, LastPWM)
                AktRPM = GetFanRPM()
        d = config.plugins.FanControl.tempmax.value - config.plugins.FanControl.temp.value
        if d < 5:
            if config.plugins.FanControl.temp.value + d < 55:
                config.plugins.FanControl.tempmax.value = config.plugins.FanControl.temp.value + 5
            else:
                config.plugins.FanControl.temp.value = config.plugins.FanControl.tempmax.value - 5

    def getCurrentValue(self):
        return str(self["config"].getCurrent()[1].getText())

    def updateFanStatus(self):
        global ZielRPM, AktTemp, AktVLT, AktPWM, AktRPM, AktERR
        
        try:
            AktTemp = GetTemperature()
            AktRPM = GetFanRPM()
            AktVLT = getVoltage(0)
            AktPWM = getPWM(0)
            
            if config.plugins.FanControl.Fan.value != "disabled":
                if config.plugins.FanControl.maxRPM.value > config.plugins.FanControl.minRPM.value:
                    Range = config.plugins.FanControl.tempmax.value - config.plugins.FanControl.temp.value
                    if Range > 0:
                        x = AktTemp - config.plugins.FanControl.temp.value
                        ZielRPM = int(skal(x, 0, Range, config.plugins.FanControl.minRPM.value, config.plugins.FanControl.maxRPM.value))
                    else:
                        ZielRPM = config.plugins.FanControl.minRPM.value
                else:
                    ZielRPM = 0
            else:
                ZielRPM = 0

            self["TxtTemp"].setText(_("Temperature C  %4.1f") % (AktTemp))
            self["TxtZielRPM"].setText(_("Target rpm  %4d") % (ZielRPM))
            self["TxtRPM"].setText(_("Current rpm  %4d") % (AktRPM))
            self["TxtVLT"].setText(_("Voltage  %03d") % (AktVLT))
            self["TxtPWM"].setText(_("PWM  %03d") % (AktPWM))

            if config.plugins.FanControl.tempmax.value > config.plugins.FanControl.temp.value:
                temp_val = int((AktTemp - config.plugins.FanControl.temp.value) * 100 / Test0(config.plugins.FanControl.tempmax.value - config.plugins.FanControl.temp.value))
                if temp_val < 0:
                    temp_val = 0
                if temp_val > 100:
                    temp_val = 100
                self["PixTemp"].value = temp_val
            else:
                self["PixTemp"].value = 0

            if config.plugins.FanControl.maxRPM.value > config.plugins.FanControl.minRPM.value:
                ziel_val = int((ZielRPM - config.plugins.FanControl.minRPM.value) * 100 / Test0(config.plugins.FanControl.maxRPM.value - config.plugins.FanControl.minRPM.value))
                if ziel_val < 0:
                    ziel_val = 0
                if ziel_val > 100:
                    ziel_val = 100
                self["PixZielRPM"].value = ziel_val

                rpm_val = int((AktRPM - config.plugins.FanControl.minRPM.value) * 100 / Test0(config.plugins.FanControl.maxRPM.value - config.plugins.FanControl.minRPM.value))
                if rpm_val < 0:
                    rpm_val = 0
                if rpm_val > 100:
                    rpm_val = 100
                self["PixRPM"].value = rpm_val
            else:
                self["PixZielRPM"].value = 0
                self["PixRPM"].value = 0

            self["PixVLT"].value = int(AktVLT / 2.55)
            if self["PixVLT"].value > 100:
                self["PixVLT"].value = 100

            self["PixPWM"].value = int(AktPWM / 2.55)
            if self["PixPWM"].value > 100:
                self["PixPWM"].value = 100

        except Exception as e:
            FClog("Update fan status error: %s" % str(e))

        self.fan_timer.start(2000, True)

    def save(self):
        for x in self["config"].list:
            x[1].save()
        self.close(True, self.session)

    def cancel(self):
        for x in self["config"].list:
            x[1].cancel()
        self.close(False, self.session)

    def pruefen(self):
        self.session.open(FanControl2Test)

    def monitor(self):
        self.session.open(FanControl2Monitor)

    def help(self):
        self.session.open(Console, _("Information"), ["cat /usr/lib/enigma2/python/Plugins/Extensions/FanControl2/%s" % _("readme.txt")])

    def SetupMenu(self):
        self.session.open(FanControl2SpezialSetup)

def DeleteData():
    if config.plugins.FanControl.DeleteData.value == "0" or config.plugins.FanControl.EnableDataLog.value is False:
        return
    try:
        FClog("Auto-Delete Data")
        with open(config.plugins.FanControl.LogPath.value + "FC2data.csv", "a") as f:
            s = f.tell()
        if s < 150:
            return
        with open(config.plugins.FanControl.LogPath.value + "FC2data.csv", "r", encoding='utf-8') as f:
            f.seek(s - 100)
            line = f.readline()
            line = f.readline()
            DT = line.split(";")
            DT = DT[0].split(" ")
            DD = DT[0].split(".")
            DD48h = datetime.date(int(DD[0]), int(DD[1]), int(DD[2])) - datetime.timedelta(int(config.plugins.FanControl.DeleteData.value))
            Dfind = "%04d.%02d.%02d %s" % (DD48h.year, DD48h.month, DD48h.day, DT[1])
            f.seek(0)
            line = f.readline()
        with open(config.plugins.FanControl.LogPath.value + "FC2data.csv.tmp", "w", encoding='utf-8') as fw:
            fw.write(HeadLine)
            with open(config.plugins.FanControl.LogPath.value + "FC2data.csv", "r", encoding='utf-8') as f:
                for line in f:
                    DT = line.split(";")
                    if DT[0] > Dfind:
                        fw.write(line)
        if os.path.exists(config.plugins.FanControl.LogPath.value + "FC2data.csv"):
            os.remove(config.plugins.FanControl.LogPath.value + "FC2data.csv")
        os.rename(config.plugins.FanControl.LogPath.value + "FC2data.csv.tmp", config.plugins.FanControl.LogPath.value + "FC2data.csv")
    except Exception as e:
        FClog("Error Delete Data: %s" % str(e))

def getstatusoutput(cmd):
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        text = result.stdout + result.stderr
        sts = result.returncode
        if text and text[-1] == '\n':
            text = text[:-1]
    except Exception as e:
        sts = 1
        text = ""
        FClog("Error on call OS program (smartctl/hdparm): %s" % str(e))
    return sts, text

def HDDtestTemp():
    global disableHDDread
    if harddiskmanager.HDDCount() > 0 and config.plugins.FanControl.CheckHDDTemp.value != "never":
        disableHDDread = False
        for hdd in harddiskmanager.HDDList():
            if hdd[1].model().startswith("ATA"):
                FClog("%s %s Mode:%s" % (hdd[1].model(), hdd[1].getDeviceName(), config.plugins.FanControl.CheckHDDTemp.value))
                if config.plugins.FanControl.CheckHDDTemp.value == "auto":
                    (stat, wert) = getstatusoutput("hdparm -y %s" % hdd[1].getDeviceName())
                    time.sleep(0.5)
                    (stat, wert) = ReadHDDtemp(hdd[1].getDeviceName())
                    if stat != 0:
                        (stat, wert) = getstatusoutput("smartctl --smart=on %s" % hdd[1].getDeviceName())
                        FClog("HDD Temperature not readable -> Ignore")
                        FC2HDDignore.append(hdd[1].getDeviceName())
                    time.sleep(0.5)
                    (stat, wert) = getstatusoutput("hdparm -C %s" % hdd[1].getDeviceName())
                    if wert.find("standby") > 0:
                        FClog("HDD supports Temp reading without Spinup")
                    else:
                        if hdd[1].isSleeping():
                            (stat, wert) = getstatusoutput("hdparm -y %s" % hdd[1].getDeviceName())
                            FClog("HDD not supports Temp reading without Spinup -> Ignore")
                            FC2HDDignore.append(hdd[1].getDeviceName())

def ReadHDDtemp(D):
    return getstatusoutput('smartctl -A %s | grep "194 Temp" | grep Always' % D)

def GetHDDtemp(OneTime):
    global AktHDD
    AktHDD = []
    if harddiskmanager.HDDCount() > 0 and (config.plugins.FanControl.CheckHDDTemp.value != "never" or OneTime is True):
        for hdd in harddiskmanager.HDDList():
            if hdd[1].model().startswith("ATA") and hdd[1].getDeviceName() not in FC2HDDignore:
                sleeptime = int((time.time() - hdd[1].last_access))
                if config.plugins.FanControl.CheckHDDTemp.value == "true" or (config.plugins.FanControl.CheckHDDTemp.value == "auto" and not disableHDDread) or ((not hdd[1].isSleeping()) and sleeptime < 120) or OneTime is True:
                    (stat, wert) = ReadHDDtemp(hdd[1].getDeviceName())
                    if stat == 0:
                        try:
                            AktHDD.append(int(wert[wert.find("Always") + 6:].replace(" ", "").replace("-", "")[:2]))
                        except Exception:
                            AktHDD.append(0)
                    if len(AktHDD) == 0:
                        AktHDD = [0]
                    FClog("HDD Temp %dC" % (AktHDD[-1]))
    if len(AktHDD) == 0:
        AktHDD = [0]

def HDDsSleeping():
    for hdd in harddiskmanager.HDDList():
        if hdd[1].model().startswith("ATA"):
            if not hdd[1].isSleeping():
                return False
    return True

def FC2systemStatus():
    S = int(FC2werte[5]) if len(FC2werte) > 5 else 0
    R = " -" if S > 0 else " "
    if (S & 1) > 0:
        R += " BoxOn"
    if (S & 2) > 0:
        R += " HDDon"
    if (S & 4) > 0:
        R += " REC"
    return R

def FC2fanReset():
    setVoltage(0, AktVLT)
    setPWM(0, AktPWM)
    FClog("Fan Reset")

class FC2Worker(Thread):
    def __init__(self, index, s, session):
        Thread.__init__(self)
        self.index = index
        self.session = session
        self.s = s
        self.daemon = True
        self.running = True

    def stop(self):
        self.running = False

    def run(self):
        while self.running:
            try:
                zahl = Briefkasten.get(timeout=1)
                if zahl == 1:
                    self.s.queryRun()
            except queue.Empty:
                continue
            except Exception as e:
                FClog("Worker error: %s" % str(e))
            Briefkasten.task_done()

class FanControl2(Screen):
    skin = """ <screen position="100,100" size="300,300" title="FanControl2" > </screen>"""

    RPMController = ControllerPI("RPMController")

    def __init__(self, session):
        Screen.__init__(self, session)
        self.session = session
        self.FanMin = 500
        self.FanMax = 1500
        self.targetTemp = 50.0
        self.maxTemp = 55.0
        self.Range = 5
        self.Fan = "aus"
        self.dontshutdown = False
        self.Recording = False
        self.inStandby = False
        self.HDDidle = True
        self.running = True
        self.threads = []
        
        self.RPMController.timer_delay = 10.0
        self.RPMController.dt = 10.0
        self.RPMController.inputMax = 4000.0
        self.RPMController.inputDeadband = 1.0
        self.RPMController.coeffKp = 0.1
        self.RPMController.coeffKi = 0.25
        
        FClog("Starting up DM920 FanControl2")
        FClog("Fan type: %s" % config.plugins.FanControl.Fan.value)
        
        if os.path.exists("/usr/lib/enigma2/python/Plugins/Extensions/FanControl2/data/diagram.class.org"):
            os.rename("/usr/lib/enigma2/python/Plugins/Extensions/FanControl2/data/diagram.class.org", 
                     "/usr/lib/enigma2/python/Plugins/Extensions/FanControl2/data/diagram.class")
        
        HDDtestTemp()
        GetHDDtemp(False)
        DeleteData()
        
        if config.plugins.FanControl.EnableThread.value:
            self.threads = [FC2Worker(i, self, session) for i in range(1)]
            for thread in self.threads:
                thread.daemon = True
                thread.start()
        
        self.timer = eTimer()
        if self.query not in self.timer.callback:
            self.timer.callback.append(self.query)
        self.timer.startLongTimer(2)
        
        config.misc.standbyCounter.addNotifier(self.standbyQuery, initial_call=False)

    def __del__(self):
        self.stop()

    def FC2AskShutdown(self):
        if not self.dontshutdown:
            self.dontshutdown = True
            self.session.openWithCallback(self.FC2DoShutdown, MessageBox, _("FanControl2 emergency, Box Shutdown now?"), type=MessageBox.TYPE_YESNO, timeout=60)

    def FC2DoShutdown(self, retval):
        if retval:
            if Standby.inTryQuitMainloop is False:
                self.session.open(Standby.TryQuitMainloop, 1)

    def stop(self):
        self.running = False
        FClog("Stop")
        if self.query in self.timer.callback:
            self.timer.callback.remove(self.query)
        self.timer.stop()
        for thread in self.threads:
            try:
                thread.stop()
            except:
                pass

    def CurrTemp(self):
        return GetTemperature()

    def cycle(self):
        self.Range = self.maxTemp - self.targetTemp
        x = AktTemp - self.targetTemp
        rpm = skal(x, 0, self.Range, self.FanMin, self.FanMax)
        return rpm

    def standbyQuery(self, configElement):
        Standby.inStandby.onClose.append(self.query)
        self.query()

    def query(self):
        global FanFehler
        if not self.running:
            return
            
        self.timer.stop()
        
        if config.plugins.FanControl.Fan.value != "disabled":
            try:
                self.Recording = self.session.nav.RecordTimer.isRecording()
                self.inStandby = Standby.inStandby
                
                if harddiskmanager.HDDCount() > 0 and int(strftime("%S")) < 10:
                    self.HDDidle = HDDsSleeping()
                    if strftime("%M")[-1:] == "0":
                        GetHDDtemp(False)
                
                if config.plugins.FanControl.EnableThread.value:
                    if Briefkasten.qsize() <= 3:
                        Briefkasten.put(1)
                    else:
                        FClog("Queue full, Thread hanging?")
                else:
                    self.queryRun()
                
                if ZielRPM > 0 and AktRPM == 0:
                    FanFehler += 1
                    if FanFehler > 90:
                        FanFehler -= 18
                        FClog("Fan Error")
                        if config.plugins.FanControl.ShowError.value == "true" and not self.inStandby:
                            Notifications.AddNotification(MessageBox, _("Fan is not working!"), type=MessageBox.TYPE_INFO, timeout=5)
                        if config.plugins.FanControl.ShowError.value == "shutdown":
                            self.FC2AskShutdown()
                else:
                    FanFehler = 0
                    
                if AktTemp >= config.plugins.FanControl.ShutdownTemp.value:
                    FClog("Emergency Shutdown %dC" % AktTemp)
                    self.FC2AskShutdown()
            except Exception as e:
                FClog("Query error: %s" % str(e))
                import traceback
                FClog(traceback.format_exc())
        
        if self.running:
            self.timer.startLongTimer(10)

    def queryRun(self):
        global FirstStart, istStandbySave, Overheat, OverheatTimer, FanOffWait
        global RPMread, RPMdiff, FanFehler, ZielRPM, AktRPM, AktTemp, AktVLT, AktPWM
        global AktPWMCTL, IntegralRPM, ErrRPM
        
        if not self.running:
            return
            
        tt = time.time()
        try:
            if self.targetTemp != config.plugins.FanControl.temp.value:
                self.RPMController.ResetIntegrator()
            
            self.targetTemp = config.plugins.FanControl.temp.value
            self.maxTemp = config.plugins.FanControl.tempmax.value
            self.Fan = config.plugins.FanControl.Fan.value
            self.Vlt = config.plugins.FanControl.vlt.value
            id = 0
            
            AktTemp = GetTemperature()
            AktRPM = GetFanRPM()
            AktVLT = getVoltage(id)
            AktPWM = getPWM(id)
            
            if int(strftime("%S")) < 10 and strftime("%H:%M") == "00:00":
                DeleteData()
            
            S = 0
            if not self.inStandby:
                S += 1
            if not self.HDDidle:
                S += 2
            if self.Recording:
                S += 4
            with data_lock:
                FC2werte[5] = str(S)

            if (self.inStandby) and (not Overheat) and ((config.plugins.FanControl.StandbyOff.value == "true") or ((config.plugins.FanControl.StandbyOff.value == "trueRec") and (not self.Recording and self.HDDidle))):
                FClog("Fan Off Temp: %d %s" % (AktTemp, FC2systemStatus()))
                setVoltage(id, 0)
                setPWM(id, 0)
                with data_lock:
                    FC2werte[0] = AktTemp
                    FC2werte[1] = 0
                    FC2werte[2] = 0
                    FC2werte[3] = 0
                    FC2werte[4] = max(AktHDD) if len(AktHDD) > 0 else 0
                FCdata()
                FirstStart = True
                OverheatTemp = self.maxTemp + config.plugins.FanControl.AddOverheat.value
                OverheatTimer = 0
                FanOffWait = True
                if OverheatTemp > 65:
                    OverheatTemp = 65
                if AktTemp > OverheatTemp:
                    Overheat = True
                    FClog("Overheat")
            else:
                if (Overheat and AktTemp < self.maxTemp - 3) or not self.inStandby:
                    Overheat = False
                AktVLTtmp = getVoltage(id)
                AktPWMtmp = getPWM(id)
                if self.inStandby and self.inStandby == istStandbySave and RPMdiff == 1 and not self.Recording:
                    tmp = GetFanRPM()
                    RPMdiff = AktRPM - tmp
                    if RPMdiff < 150 or tmp < 300 or self.Fan == "3pin":
                        RPMdiff = 0
                    else:
                        if config.plugins.FanControl.minRPM.value - RPMdiff < 300:
                            RPMdiff = config.plugins.FanControl.minRPM.value - 300
                        FClog("RPM-Range shifted -%drpm" % RPMdiff)
                if not self.inStandby:
                    RPMdiff = 0
                self.FanMin = config.plugins.FanControl.minRPM.value - RPMdiff
                self.FanMax = config.plugins.FanControl.maxRPM.value - RPMdiff
                if self.inStandby != istStandbySave or AktVLT != AktVLTtmp or AktPWM != AktPWMtmp:
                    istStandbySave = self.inStandby
                    if istStandbySave is True:
                        Standby.inStandby.onClose.append(FC2fanReset)
                    FC2fanReset()
                    AktVLTtmp = AktVLT
                    RPMdiff = 1
                    AktVLTtmp = getVoltage(id)
                    AktPWMtmp = getPWM(id)
                    if AktVLT != AktVLTtmp or AktPWM != AktPWMtmp:
                        time.sleep(2)
                        FC2fanReset()
                if (AktVLT + AktPWM) == 0:
                    FirstStart = True
                if FirstStart is True:
                    FirstStart = False
                    AktVLTtmp = self.Vlt
                    setVoltage(id, self.Vlt)
                    setPWM(id, config.plugins.FanControl.pwm.value)
                AktRPMtmp = GetFanRPM()
                if RPMread > 0 and RPMread < 3:
                    FClog("Reread")
                    if config.plugins.FanControl.EnableThread.value:
                        if Briefkasten.qsize() <= 2:
                            time.sleep(0.4)
                            Briefkasten.put(1)
                    else:
                        self.timer.start(400, True)
                    return
                RPMread = 0
                if AktRPMtmp > 6000:
                    FClog("ignore high RPM")
                    return
                AktRPM = AktRPMtmp
                AktVLT = AktVLTtmp
                AktPWM = getPWM(id)
                if AktVLT > 255:
                    AktVLT = 255
                FClog("Vlt:%d Pwm:%d Fan:%s Pid:%.2f%%  %s" % (AktVLT, AktPWM, self.Fan, ErrRPM, FC2systemStatus()))
                with data_lock:
                    FC2werte[0] = AktTemp
                    FC2werte[1] = AktRPM
                    FC2werte[2] = AktVLT
                    FC2werte[3] = AktPWM
                    FC2werte[4] = max(AktHDD) if len(AktHDD) > 0 else 0
                FCdata()
                if int(strftime("%M")) == 0:
                    with data_lock:
                        FC2stunde[int(strftime("%H"))] = "%4.1f<BR>%d" % (AktTemp, AktRPM)
                ZielRPM = self.cycle()
                if (FanOffWait and OverheatTimer < 30) or (Overheat and OverheatTimer < 60):
                    ZielRPM = self.FanMin
                    OverheatTimer += 1
                    FClog("FanStartTimeout set MinRPM (%d)" % (OverheatTimer))
                else:
                    FanOffWait = False
                FClog(_("currentRPM:%d targetRPM:%d Temp:%4.1f") % (AktRPM, ZielRPM, AktTemp))
                if self.Fan == "4pin":
                    if AktPWM < 255 and AktPWM > 0 and AktVLT != self.Vlt:
                        AktVLT = (AktVLT - 1 if AktVLT > self.Vlt else AktVLT + 1)
                        setVoltage(id, AktVLT)
                    if AktRPM + 29 < ZielRPM:
                        AktPWM = (AktPWM + 5 if ZielRPM - AktRPM > 100 else AktPWM + 1)
                        setPWM(id, AktPWM)
                        if AktPWM >= 255 and AktVLT < 255:
                            AktVLT += 1
                            setVoltage(id, AktVLT)
                    elif AktRPM - 19 > ZielRPM:
                        AktPWM = (AktPWM - 5 if AktRPM - ZielRPM > 100 else AktPWM - 1)
                        setPWM(id, AktPWM)
                        if AktPWM < 0 and AktVLT > 5:
                            AktVLT -= 1
                            setVoltage(id, AktVLT)
                    if AktVLT > self.Vlt:
                        AktPWM = 256
                    if AktPWM < 0:
                        AktPWM = 0
                elif self.Fan == "4pinREG":
                    AktPWM = self.RPMController.ControlLoop(ZielRPM, AktRPM)
                    ErrRPM = self.RPMController.inputError
                    if AktPWM > 255.0:
                        AktVLT = 0.12 * (AktPWM - 255.0) + int(config.plugins.FanControl.vlt.value)
                    else:
                        AktVLT = int(config.plugins.FanControl.vlt.value)
                    if AktVLT > 255:
                        AktVLT = 255
                    if AktVLT < 0:
                        AktVLT = 0
                    if AktPWM > 255:
                        AktPWM = 255
                    if AktPWM < 0:
                        AktPWM = 0
                    setVoltage(id, int(AktVLT))
                    setPWM(id, int(AktPWM))
                elif self.Fan == "3pin":
                    if AktRPM + 29 < ZielRPM:
                        AktVLT = (AktVLT + 5 if ZielRPM - AktRPM > 100 else AktVLT + 1)
                        setVoltage(id, AktVLT)
                    elif AktRPM - 19 > ZielRPM:
                        AktVLT = (AktVLT - 5 if AktRPM - ZielRPM > 100 else AktVLT - 1)
                        setVoltage(id, AktVLT)

        except Exception as e:
            from traceback import format_exc
            FClog("Control Error:\n" + format_exc())
        FClogE("Runtime: %.3f" % (time.time() - tt))

def autostart(reason, **kwargs):
    global FC2_active
    if reason == 0 and "session" in kwargs:
        try:
            from Plugins.Extensions.WebInterface.WebChilds.Toplevel import addExternalChild
            from .FC2webSite import FC2web, FC2webLog, FC2webChart
            from twisted.web import static
            root = static.File("/usr/lib/enigma2/python/Plugins/Extensions/FanControl2/data")
            root.putChild(b"", FC2web())
            root.putChild(b"log", FC2webLog())
            root.putChild(b"chart", FC2webChart())
            if os.path.exists("/usr/lib/enigma2/python/Plugins/Extensions/WebInterface/web/external.xml"):
                try:
                    addExternalChild(("fancontrol", root, "Fan Control 2", __version__, True))
                    FClog("use new WebIF")
                except Exception:
                    addExternalChild(("fancontrol", root))
                    FClog("use old WebIF")
            if os.path.exists("/usr/lib/enigma2/python/Plugins/Extensions/OpenWebif/pluginshook.src"):
                try:
                    addExternalChild(("fancontrol", root, "Fan Control 2", __version__))
                    FClog("use new OpenWebIF")
                except Exception:
                    pass
        except ImportError:
            FClog("WebInterface not available")
        
        if not os.path.exists("/proc/stb/fp/fan_vlt"):
            Notifications.AddNotification(MessageBox, _("Box has no fancontrol hardware -> FC2 deactivated"), type=MessageBox.TYPE_INFO, timeout=10)
            FClog("not supported, exit")
            return
        
        session = kwargs["session"]
        FClog("========================================")
        FClog("FanControl2 starting - DM920")
        FClog("Fan type: %s" % config.plugins.FanControl.Fan.value)
        FClog("========================================")
        if not FC2_active:
            FC2_active = True
            session.open(FanControl2)

def selSetup(menuid, **kwargs):
    if IMAGEDISTRO in ('openhdf'):
        if menuid != "devices_menu":
            return []
    elif IMAGEDISTRO in ('openatv'):
        if menuid != "extended":
            return []
    else:
        if menuid != "system":
            return []
    return [(_("Fan Control 2"), main, "fansetup_config", 70)]

def Plugins(**kwargs):
    name = _("Fan Control")
    name2 = _("Fan Control 2")
    list = [
        PluginDescriptor(name=name2, description=name, where=[PluginDescriptor.WHERE_SESSIONSTART, PluginDescriptor.WHERE_AUTOSTART], needsRestart=True, fnc=autostart)]
    if os.path.exists("/proc/stb/fp/fan_vlt"):
        list.append(PluginDescriptor(name=name2, description=_("setup Fancontol inStandby mode"), where=PluginDescriptor.WHERE_MENU, needsRestart=True, fnc=selSetup))
        if config.plugins.FanControl.FanControlInExtension.value:
            list.append(PluginDescriptor(name=name2, description=name, where=PluginDescriptor.WHERE_EXTENSIONSMENU, icon="plugin.png", needsRestart=True, fnc=main))
        if config.plugins.FanControl.MonitorInExtension.value:
            list.append(PluginDescriptor(name=_("Fan Control 2 - Monitor"), description=name, where=PluginDescriptor.WHERE_EXTENSIONSMENU, icon="plugin.png", needsRestart=True, fnc=mainMonitor))
    return list
