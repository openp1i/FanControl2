# -*- coding: utf-8 -*-
from Components.Language import language
from Tools.Directories import resolveFilename, SCOPE_PLUGINS
import gettext

PluginLanguageDomain = "FanControl2"
PluginLanguagePath = "Extensions/FanControl2/locale"

def localeInit():
    gettext.bindtextdomain(PluginLanguageDomain, resolveFilename(SCOPE_PLUGINS, PluginLanguagePath))

def _(txt):
    if gettext.dgettext(PluginLanguageDomain, txt):
        return gettext.dgettext(PluginLanguageDomain, txt)
    else:
        print("[%s] fallback to default translation for %s" % (PluginLanguageDomain, txt))
        return gettext.gettext(txt)

localeInit()
language.addCallback(localeInit)

HeadLine = "Time;Temp;RPM;VLT;PWM;HDD;Status;Temp1;Temp2;Temp3;Temp4;Temp5;Temp6;Temp7;Temp8\r\n"
TempName = [
    _("below Tunerslot 4"),
    _("near XILINX Spartan"),
    _("under the WLAN"),
    _("left of the Battery"),
    _("left near Front-CI"),
    _("left near Card-Slot"),
    _("over Security Card"),
    _("under the Fan")
]

__version__ = "2.9.3"
