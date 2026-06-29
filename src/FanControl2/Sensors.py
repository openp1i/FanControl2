# -*- coding: utf-8 -*-
class Sensors:
    # (type, name, unit, directory)
    TYPE_TEMPERATURE = 0

    def __init__(self):
        self.sensors_list = []
        self.addSensors()

    def getSensorsCount(self, type=None):
        if type is None:
            return len(self.sensors_list)
        count = 0
        for sensor in self.sensors_list:
            if sensor[0] == type:
                count += 1
        return count

    def getSensorsList(self, type=None):
        if type is None:
            return list(range(len(self.sensors_list)))
        items = []
        for sensorid in range(len(self.sensors_list)):
            if self.sensors_list[sensorid][0] == type:
                items.append(sensorid)
        return items

    def getSensorType(self, sensorid):
        return self.sensors_list[sensorid][0]

    def getSensorName(self, sensorid):
        return self.sensors_list[sensorid][1]

    def getSensorDir(self, sensorid):
        return self.sensors_list[sensorid][3]

    def getSensorValue(self, sensorid):
        value = -1
        sensor = self.sensors_list[sensorid]
        if sensor[0] == self.TYPE_TEMPERATURE:
            try:
                with open("%s/value" % sensor[3], "r") as f:
                    value = int(f.readline().strip())
            except (OSError, ValueError, IOError):
                pass
        return value

    def addSensors(self):
        import os
        if os.path.exists("/proc/stb/sensors"):
            sd = []
            sd = os.listdir("/proc/stb/sensors")
            sd.sort()
            for dirname in sd:
                if dirname.find("temp", 0, 4) == 0:
                    try:
                        with open("/proc/stb/sensors/%s/name" % dirname, "r") as f:
                            name = f.readline().strip()
                        with open("/proc/stb/sensors/%s/unit" % dirname, "r") as f:
                            unit = f.readline().strip()
                        self.sensors_list.append((self.TYPE_TEMPERATURE, name, unit, "/proc/stb/sensors/%s" % dirname))
                    except (OSError, IOError):
                        pass

sensors = Sensors()
