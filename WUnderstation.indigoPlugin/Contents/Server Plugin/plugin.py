#!/usr/bin/env python2.7
# -*- coding: utf-8 -*-

"""
WUnderstation Indigo Plugin
Author: DaveL17
Update Checker by: berkinet (with additional features by Travis Cook)

The WUnderstation Plugin takes Indigo data provided by user-defined
variables and makes it available for upload to wunderground.com. It is
presumed that the user will only create one WUnderstation implementation.

API: http://wiki.wunderground.com/index.php/PWS_-_Upload_Protocol
"""

# =================================== TO DO ===================================

# TODO: Consider whether it's possible to include the PWS sign-up within the plugin.
# TODO: Enable RapidFire?
# TODO: What Trigger, Action events (etc.) are necessary?  (i.e., upload data now, trigger to fire on some bad event, etc.)

# ================================== IMPORTS ==================================

# Built-in modules
# from dateutil import parser
import logging
import requests

# Third-party modules
from DLFramework import indigoPluginUpdateChecker
try:
    import indigo
except ImportError:
    pass
try:
    import pydevd
except ImportError:
    pass

# My modules
import DLFramework.DLFramework as Dave

# =================================== HEADER ==================================

__author__    = Dave.__author__
__copyright__ = Dave.__copyright__
__license__   = Dave.__license__
__build__     = Dave.__build__
__title__     = 'WUnderstation Plugin for Indigo Home Control'
__version__   = '1.1.01'

# Establish default plugin prefs; create them if they don't already exist.
kDefaultPluginPrefs = {
    u'showDebugInfo'        : False,  # Debug on/off
    u'showDebugLevel'       : "30",   # Controls logging output.
    u'updaterEmail'         : "",     # Email to notify of plugin updates.
    u'updaterEmailsEnabled' : False,  # Notification of plugin updates wanted.
    u'uploadInterval'       : 900,    # How often to upload data?
    u'wunderstationID'      : "",     # Frequency of updates.
    u'wunderstationPassword': ""      # Verbose debug logging?
}


class Plugin(indigo.PluginBase):
    def __init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs):
        indigo.PluginBase.__init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs)

        self.pluginIsInitializing = True
        self.pluginIsShuttingDown = False

        updater_url               = 'https://raw.githubusercontent.com/DaveL17/WUnderstation/master/wunderstation_version.html'
        self.updater              = indigoPluginUpdateChecker.updateChecker(self, updater_url)
        self.updaterEmail         = self.pluginPrefs.get('updaterEmail', "")
        self.updaterEmailsEnabled = self.pluginPrefs.get('updaterEmailsEnabled', "false")

        self.plugin_file_handler.setFormatter(logging.Formatter('%(asctime)s.%(msecs)03d\t%(levelname)-10s\t%(name)s.%(funcName)-28s %(msg)s', datefmt='%Y-%m-%d %H:%M:%S'))
        self.debugLevel = int(self.pluginPrefs.get('showDebugLevel', '30'))
        self.indigo_log_handler.setLevel(self.debugLevel)

        # ====================== Initialize DLFramework =======================

        self.Fogbert = Dave.Fogbert(self)

        # Weather Underground Attribution and disclaimer.
        indigo.server.log(u"{0:*^130}".format(""))
        indigo.server.log(u"{0:*^130}".format("  Data are provided by Weather Underground, LLC. This plugin and its author are in no way affiliated with Weather Underground.  "))
        indigo.server.log(u"{0:*^130}".format(""))

        # Log pluginEnvironment information when plugin is first started
        self.Fogbert.pluginEnvironment()

        # try:
        #     pydevd.settrace('localhost', port=5678, stdoutToServer=True, stderrToServer=True, suspend=False)
        # except:
        #     pass

        self.pluginIsInitializing = False

    def __del__(self):
        indigo.PluginBase.__del__(self)

    # =============================== Indigo Methods ===============================

    def closedPrefsConfigUi(self, valuesDict, userCancelled):

        if userCancelled:
            self.logger.debug(u"User prefs dialog cancelled.")

        if not userCancelled:
            self.logger.debug(u"User prefs saved.")
            self.debugLevel = int(self.pluginPrefs.get('showDebugLevel', '30'))
            self.indigo_log_handler.setLevel(self.debugLevel)

    def deviceStartComm(self, dev):

        self.logger.debug(u"Starting WUnderstation device: {0}".format(dev.name))
        dev.stateListOrDisplayStateIdChanged()
        dev.updateStateOnServer('onOffState', value=False, uiValue=u"")

    def deviceStopComm(self, dev):

        self.logger.debug(u"Stopping WUnderstation device: {0}".format(dev.name))
        dev.updateStateOnServer('onOffState', value=False, uiValue=u"Disabled")

    def getPrefsConfigUiValues(self):

        plugin_prefs = self.pluginPrefs

        for key in plugin_prefs:
            if plugin_prefs[key] == "":
                plugin_prefs[key] = u'None'

            try:
                if int(plugin_prefs.get('showDebugLevel', '30')) < 10:
                    plugin_prefs['showDebugLevel'] = '30'
            except ValueError:
                plugin_prefs['showDebugLevel'] = '30'

        return plugin_prefs

    def runConcurrentThread(self):

        self.logger.debug(u"runConcurrentThread initiated.")
        self.sleep(3)
        self.updater.checkVersionPoll()

        try:
            while True:
                for dev in indigo.devices.itervalues("self"):
                    if dev.deviceTypeId == 'wunderstation' and dev.enabled:
                        dev.updateStateOnServer('lastUploadResult', value=u"In process", uiValue=u"In process")

                    self.uploadWUnderstationData(dev)
                self.sleep(int(self.pluginPrefs.get('uploadInterval', 900)))

        except self.StopThread:
            self.logger.debug(u"StopThread() method called.")

    def validatePrefsConfigUi(self, valuesDict):

        error_msg_dict = indigo.Dict()
        update_email   = valuesDict['updaterEmail']
        update_wanted  = valuesDict['updaterEmailsEnabled']

        # Test plugin update notification settings.
        try:
            if update_wanted and not update_email:
                error_msg_dict['updaterEmail']  = u"If you want to be notified of updates, you must supply an email address."
                error_msg_dict['showAlertText'] = u"To receive an update notification, you must supply an email address."
                return False, valuesDict, error_msg_dict

            elif update_wanted and "@" not in update_email:
                error_msg_dict['updaterEmail']  = u"Valid email addresses have at least one @ symbol in them (foo@bar.com)."
                error_msg_dict['showAlertText'] = u"The email address that you have entered is invalid.\n\n"
                return False, valuesDict, error_msg_dict

        except Exception as error:
            self.logger.critical(u"{0}".format(error))

        return True, valuesDict

    def shutdown(self):

        self.pluginIsShuttingDown = True

    def startup(self):

        try:
            self.updater.checkVersionPoll()

        except Exception as error:
            self.logger.critical(u"Update checker error. Error: {0}".format(error))

    # =========================== WUnderstation Methods ============================

    def checkFloat(self, var_name, val):
        """
        Check values to make sure they will float

        The checkFloat() method takes a passed value and determines whether it will
        float. If it will, it is returned for use.  If it will not, it is set to an
        empty string and the user is notified. If we don't set it to an empty string,
        WU may reject the entire upload.

        -----

        """

        try:
            return float(val)

        except ValueError:
            self.logger.critical(u"Disallowing {0}. Reason: value must be greater than or equal to 0.".format(var_name))
            return ""

    def checkPercentage(self, var_name, val):
        """
        Check to make sure value is between 0 and 100

        The checkPercentage() method ensures that a wind direction value is valid
        (between 0 and 100.)

        -----

        """

        if not 100 >= float(val) >= 0:
            val = ""
            self.logger.critical(u"Disallowing {0}. Reason: value must be between 0 and 100.".format(var_name))

        return val

    def checkPositive(self, var_name, val):
        """
        Check values to make sure they're greater than zero

        The checkPercentage() method ensures that a wind direction value is valid
        (greater than zero.)

        -----

        """

        if not float(val) >= 0:
            val = ""
            self.logger.critical(u"Disallowing {0}. Reason: value must be greater than or equal to 0.".format(var_name))

        return val

    def checkWind(self, var_name, val):
        """
        Check to make sure that the value is between 0 and 360

        The checkWind() method ensures that a wind direction value is valid
        (between 0 and 360.)

        -----

        """

        if not 0 <= float(val) <= 360:
            self.logger.critical(u"Disallowing {0}. Reason: value must be between 0 and 360.".format(var_name))
            val = " "

        return val

    def checkVersionNow(self):
        """
        Check for current version of the plugin

        Called if user selects "Check For Plugin Updates..." Indigo menu item.

        -----

        """

        self.updater.checkVersionNow()

    def getGlobalProps(self):
        """
        Assign and/or update global variables

        The getGlobalProps method retrieves all pluginProps and assigns them to global
        variables.

        -----

        """

        # Set up global values for each device as we iterate through them (as they may
        # have changed.)
        self.debugLevel       = self.pluginPrefs.get('showDebugLevel', '30')
        self.updater          = indigoPluginUpdateChecker.updateChecker(self, "http://dl.dropboxusercontent.com/u/2796881/WUnderstation_version.html")
        self.updaterEmail     = self.pluginPrefs.get('updaterEmail', "")

    def listOfVariables(self, filter="", valuesDict=None, typeId=0, targetId=0):
        """
        Generate a list of variables for Indigo menu controls

        This method collects IDs and names for all Indigo variables. It creates a list
        of the form ((var.id, var.name), ...). We don't write this call to the debug
        log because if we did, it would be written 53 times.

        -----

        """

        return self.Fogbert.variableList()

    def uploadWUnderstationData(self, dev):
        """
        Assemble final data and upload to Weather Underground

        The uploadWUnderstationData() method gathers weather data from user-specified
        variable values and assigns them to the appropriate variable names for upload.
        All values are assigned--blank values are assigned an empty string--and are
        added to a master dictionary with the structure {WUvariable:value}. These are
        parsed out later when the final URL is assembled for upload.

        -----
        """

        states_list = []
        var_dict    = {}

# =============================== Weather Values ===============================
# Certain rules are applied to the data which are governed by methods above.

        # Wind Direction [0-360 instantaneous wind direction] Integer, must be greater than or equal to zero.
        try:
            wind_dir            = indigo.variables[int(self.pluginPrefs['winddir'])].value
            var_dict['winddir'] = u"winddir={0}&".format(self.checkWind('winddir', wind_dir))
        except ValueError:
            var_dict['winddir'] = u""

        # Wind Speed [mph instantaneous wind speed] Float, must be greater than or equal to zero.
        try:
            wind_speed               = indigo.variables[int(self.pluginPrefs['windspeedmph'])].value
            var_dict['windspeedmph'] = u"windspeedmph={0}&".format(self.checkPositive('windspeedmph', wind_speed))
        except ValueError:
            var_dict['windspeedmph'] = u""

        # Wind Speed Gust [mph current wind gust, using software specific time period] Float, must be greater than or equal to zero.
        try:
            wind_speed_gust         = indigo.variables[int(self.pluginPrefs['windgustmph'])].value
            var_dict['windgustmph'] = u"windgustmph={0}&".format(self.checkPositive('windgustmph', wind_speed_gust))
        except ValueError:
            var_dict['windgustmph'] = u""

        # Wind Speed Gust Direction [0-360 using software specific time period] Integer, must be between 0 and 360 inclusive.
        try:
            wind_speed_gust_dir     = indigo.variables[int(self.pluginPrefs['windgustdir'])].value
            var_dict['windgustdir'] = u"windgustdir={0}&".format(self.checkWind('windgustdir', wind_speed_gust_dir))
        except ValueError:
            var_dict['windgustdir'] = u""

        # Wind Speed Average 2 Minutes [mph 2 minute average wind speed mph] Float, must be greater than or equal to zero.
        try:
            wind_speed_avg_2min          = indigo.variables[int(self.pluginPrefs['windspdmph_avg2m'])].value
            var_dict['windspdmph_avg2m'] = u"windspdmph_avg2m={0}&".format(self.checkPositive('windspdmph_avg2m', wind_speed_avg_2min))
        except ValueError:
            var_dict['windspdmph_avg2m'] = u""

        # Wind Direction Average 2 Minutes [0-360 2 minute average wind direction] Integer, must be between 0 and 360 inclusive.
        try:
            wind_dir_avg_2min         = indigo.variables[int(self.pluginPrefs['winddir_avg2m'])].value
            var_dict['winddir_avg2m'] = u"winddir_avg2m={0}&".format(self.checkWind('winddir_avg2m', wind_dir_avg_2min))
        except ValueError:
            var_dict['winddir_avg2m'] = u""

        # Wind Speed Average 10 Minutes [mph past 10 minutes wind gust mph] Float, must be greater than or equal to zero.
        try:
            wind_speed_avg_10min        = indigo.variables[int(self.pluginPrefs['windgustmph_10m'])].value
            var_dict['windgustmph_10m'] = u"windgustmph_10m={0}&".format(self.checkPositive('windgustmph_10m', wind_speed_avg_10min))
        except ValueError:
            var_dict['windgustmph_10m'] = u""

        # Wind Direction Average 10 Minutes [0-360 past 10 minutes wind gust direction] Integer, must be between 0 and 360 inclusive.
        try:
            wind_dir_avg_10min          = indigo.variables[int(self.pluginPrefs['windgustdir_10m'])].value
            var_dict['windgustdir_10m'] = u"windgustdir_10m={0}&".format(self.checkWind('windgustdir_10m', wind_dir_avg_10min))
        except ValueError:
            var_dict['windgustdir_10m'] = u""

        # Outdoor Humidity [% outdoor humidity 0-100%] Float, must be between 0 and 100 inclusive.
        try:
            outdoor_humidity     = indigo.variables[int(self.pluginPrefs['humidity'])].value
            var_dict['humidity'] = u"humidity={0}&".format(self.checkPercentage('humidity', outdoor_humidity))
        except ValueError:
            var_dict['humidity'] = u""

        # Outdoor Dewpoint [F outdoor dewpoint F] Float.
        try:
            outdoor_dewpoint   = indigo.variables[int(self.pluginPrefs['dewptf'])].value
            var_dict['dewptf'] = u"dewptf={0}&".format(self.checkFloat('dewptf', outdoor_dewpoint))
        except ValueError:
            var_dict['dewptf'] = u""

        # Outdoor Temperature 1 [F outdoor temperature] Float.
        try:
            outdoor_temp_1     = indigo.variables[int(self.pluginPrefs['tempf1'])].value
            var_dict['temp1f'] = u"tempf={0}&".format(self.checkFloat('temp1f', outdoor_temp_1))
        except ValueError:
            var_dict['temp1f'] = u""

        # Outdoor Temperature 2 [F outdoor temperature] Float.
        try:
            outdoor_temp_2     = indigo.variables[int(self.pluginPrefs['tempf2'])].value
            var_dict['temp2f'] = u"temp2f={0}&".format(self.checkFloat('temp2f', outdoor_temp_2))
        except ValueError:
            var_dict['temp2f'] = u""

        # Outdoor Temperature 3 [F outdoor temperature] Float.
        try:
            outdoor_temp_3     = indigo.variables[int(self.pluginPrefs['tempf3'])].value
            var_dict['temp3f'] = u"temp3f={0}&".format(self.checkFloat('temp3f', outdoor_temp_3))
        except ValueError:
            var_dict['temp3f'] = u""

        # Outdoor Temperature 4 [F outdoor temperature] Float.
        try:
            outdoor_temp_4     = indigo.variables[int(self.pluginPrefs['tempf4'])].value
            var_dict['temp4f'] = u"temp4f={0}&".format(self.checkFloat('temp4f', outdoor_temp_4))
        except ValueError:
            var_dict['temp4f'] = u""

        # Rain Last Hour [rain inches over the past hour] Float, must be greater than or equal to zero.
        try:
            rain_last_hour     = indigo.variables[int(self.pluginPrefs['rainin'])].value
            var_dict['rainin'] = u"rainin={0}&".format(self.checkFloat('rainin', rain_last_hour))
        except ValueError:
            var_dict['rainin'] = u""

        # Rain All Day [rain inches so far today in local time] Float, must be greater than or equal to zero.
        try:
            rain_all_day            = indigo.variables[int(self.pluginPrefs['dailyrainin'])].value
            var_dict['dailyrainin'] = u"dailyrainin={0}&".format(self.checkPositive('dailyrainin', rain_all_day))
        except ValueError:
            var_dict['dailyrainin'] = u""

        # Barometric Pressure [barometric pressure inches] Float, must be greater than zero.
        try:
            barometric_pressure = indigo.variables[int(self.pluginPrefs['baromin'])].value
            var_dict['baromin'] = u"baromin={0}&".format(self.checkPositive('baromin', barometric_pressure))
        except ValueError:
            var_dict['baromin'] = u""

        # Current Weather [metar style (+RA)] String.
        try:
            current_weather     = indigo.variables[int(self.pluginPrefs['weather'])].value
            var_dict['weather'] = u"weather={0}&".format(self.webify(current_weather))
        except ValueError:
            var_dict['weather'] = u""

        # Current Clouds [Text - SKC, FEW, SCT, BKN, OVC] String.
        try:
            current_clouds     = indigo.variables[int(self.pluginPrefs['clouds'])].value
            var_dict['clouds'] = u"clouds={0}&".format(self.webify(current_clouds))
        except ValueError:
            var_dict['clouds'] = u""

        # Soil Temperature 1 [F soil temperature] Float.
        try:
            soil_temp_1           = indigo.variables[int(self.pluginPrefs['soiltempf1'])].value
            var_dict['soiltempf'] = u"soiltemp1f={0}&".format(self.checkFloat('soiltemp1f', soil_temp_1))
        except ValueError:
            var_dict['soiltempf'] = u""

        # Soil Temperature 2 [F soil temperature] Float.
        try:
            soil_temp_2            = indigo.variables[int(self.pluginPrefs['soiltempf2'])].value
            var_dict['soiltemp2f'] = u"soiltemp2f={0}&".format(self.checkFloat('soiltemp2f', soil_temp_2))
        except ValueError:
            var_dict['soiltemp2f'] = u""

        # Soil Temperature 3 [F soil temperature] Float.
        try:
            soil_temp_3            = indigo.variables[int(self.pluginPrefs['soiltempf3'])].value
            var_dict['soiltemp3f'] = u"soiltemp3f={0}&".format(self.checkFloat('soiltemp3f', soil_temp_3))
        except ValueError:
            var_dict['soiltemp3f'] = u""

        # Soil Temperature 4 [F soil temperature] Float.
        try:
            soil_temp_4            = indigo.variables[int(self.pluginPrefs['soiltempf4'])].value
            var_dict['soiltemp4f'] = u"soiltemp4f={0}&".format(self.checkFloat('soiltemp4f', soil_temp_4))
        except ValueError:
            var_dict['soiltemp4f'] = u""

        # Soil Moisture 1 [%] Float. Must be between 0 and 100 inclusive.
        try:
            soil_moisture_1          = indigo.variables[int(self.pluginPrefs['soilmoisture1'])].value
            var_dict['soilmoisture'] = u"soilmoisture1={0}&".format(self.checkPercentage('soilmoisture1', soil_moisture_1))
        except ValueError:
            var_dict['soilmoisture'] = u""

        # Soil Moisture 2 [%] Float. Must be between 0 and 100 inclusive.
        try:
            soil_moisture_2           = indigo.variables[int(self.pluginPrefs['soilmoisture2'])].value
            var_dict['soilmoisture2'] = u"soilmoisture2={0}&".format(self.checkPercentage('soilmoisture2', soil_moisture_2))
        except ValueError:
            var_dict['soilmoisture2'] = u""

        # Soil Moisture 3 [%] Float. Must be between 0 and 100 inclusive.
        try:
            soil_moisture_3           = indigo.variables[int(self.pluginPrefs['soilmoisture3'])].value
            var_dict['soilmoisture3'] = u"soilmoisture3={0}&".format(self.checkPercentage('soilmoisture3', soil_moisture_3))
        except ValueError:
            var_dict['soilmoisture3'] = u""

        # Soil Moisture 4 [%] Float. Must be between 0 and 100 inclusive.
        try:
            soil_moisture_4           = indigo.variables[int(self.pluginPrefs['soilmoisture4'])].value
            var_dict['soilmoisture4'] = u"soilmoisture4={0}&".format(self.checkPercentage('soilmoisture4', soil_moisture_4))
        except ValueError:
            var_dict['soilmoisture4'] = u""

        # Leaf Wetness 1 [%] Float. Must be between 0 and 100 inclusive.
        try:
            leaf_wetness_1          = indigo.variables[int(self.pluginPrefs['leafwetness1'])].value
            var_dict['leafwetness'] = u"leafWetness1={0}&".format(self.checkPercentage('leafWetness1', leaf_wetness_1))
        except ValueError:
            var_dict['leafwetness'] = u""

        # Leaf Wetness 2 [%] Float. Must be between 0 and 100 inclusive.
        try:
            leaf_wetness_2           = indigo.variables[int(self.pluginPrefs['leafwetness2'])].value
            var_dict['leafwetness2'] = u"leafWetness2={0}&".format(self.checkPercentage('leafWetness2', leaf_wetness_2))
        except ValueError:
            var_dict['leafwetness2'] = u""

        # Solar Radiation [Watts per square meter. W/m^2] Float. Must be greater than or equal to zero.
        try:
            solar_radiation            = indigo.variables[int(self.pluginPrefs['solarradiation'])].value
            var_dict['solarradiation'] = u"solarradiation={0}&".format(self.checkFloat('solarradiation', solar_radiation))
        except ValueError:
            var_dict['solarradiation'] = u""

        # Ultra Violet Index [Index] Integer. Must be greater than or equal to zero.
        try:
            uv_index       = indigo.variables[int(self.pluginPrefs['UV'])].value
            var_dict['uv'] = u"UV={0}&".format(self.checkFloat('UV', uv_index))
        except ValueError:
            var_dict['uv'] = u""

        # Visibility [nautical miles visibility] Float. Must be greater than or equal to zero.
        try:
            visibility             = indigo.variables[int(self.pluginPrefs['visibility'])].value
            var_dict['visibility'] = u"visibility={0}&".format(self.checkFloat('visibility', visibility))
        except ValueError:
            var_dict['visibility'] = u""

        # Indoor Temperature [F indoor temperature F] Float.
        try:
            indoor_temperature      = indigo.variables[int(self.pluginPrefs['indoortempf'])].value
            var_dict['indoortempf'] = u"indoortempf={0}&".format(self.checkFloat('indoortempf', indoor_temperature))
        except ValueError:
            var_dict['indoortempf'] = u""

        # Indoor Humidity [% indoor humidity 0-100] Float.  Must be between 0 and 100 inclusive.
        try:
            indoor_humidity            = indigo.variables[int(self.pluginPrefs['indoorhumidity'])].value
            var_dict['indoorhumidity'] = u"indoorhumidity={0}&".format(self.checkFloat('indoorhumidity', indoor_humidity))
        except ValueError:
            var_dict['indoorhumidity'] = u""

# ============================= Air Quality Values =============================
# These need rules at some point.

        # Nitric Oxide [NO (nitric oxide) PPB]
        try:
            nitric_oxide     = indigo.variables[int(self.pluginPrefs['AqNO'])].value
            var_dict['AqNO'] = u"AqNO={0}&".format(nitric_oxide)
        except ValueError:
            var_dict['AqNO'] = u""

        # Nitrogen Dioxide [(nitrogen dioxide), true measure PPB]
        try:
            nitrogen_dioxide   = indigo.variables[int(self.pluginPrefs['AqNO2T'])].value
            var_dict['AqNO2T'] = u"AqNO2T={0}&".format(nitrogen_dioxide)
        except ValueError:
            var_dict['AqNO2T'] = u""

        # [NO2 computed, NOx-NO PPB]
        try:
            no2_computed_nox  = indigo.variables[int(self.pluginPrefs['AqNO2'])].value
            var_dict['AqNO2'] = u"AqNO2={0}&".format(no2_computed_nox)
        except ValueError:
            var_dict['AqNO2'] = u""

        # [NO2 computed, NOy-NO PPB]
        try:
            no2_computed_noy   = indigo.variables[int(self.pluginPrefs['AqNO2Y'])].value
            var_dict['AqNO2Y'] = u"AqNO2Y={0}&".format(no2_computed_noy)
        except ValueError:
            var_dict['AqNO2Y'] = u""

        # Nitrogen Oxides [NOx (nitrogen oxides) - PPB]
        try:
            nitrogen_oxides   = indigo.variables[int(self.pluginPrefs['AqNOX'])].value
            var_dict['AqNOX'] = u"AqNOX={0}&".format(nitrogen_oxides)
        except ValueError:
            var_dict['AqNOX'] = u""

        # Total Reactive Nitrogen [NOy (total reactive nitrogen) - PPB]
        try:
            total_reactive_nitrogen = indigo.variables[int(self.pluginPrefs['AqNOY'])].value
            var_dict['AqNOY']       = u"AqNOY={0}}&".format(total_reactive_nitrogen)
        except ValueError:
            var_dict['AqNOY']       = u""

        # [NO3 ion (nitrate, not adjusted for ammonium ion) UG/M3]
        try:
            no3_ion = indigo.variables[int(self.pluginPrefs['AqNO3'])].value
            var_dict['AqNO3'] = u"AqNO3={0}&".format(no3_ion)
        except ValueError:
            var_dict['AqNO3'] = u""

        # [SO4 ion (sulfate, not adjusted for ammonium ion) UG/M3]
        try:
            s04_ion           = indigo.variables[int(self.pluginPrefs['AqSO4'])].value
            var_dict['AqSO4'] = u"AqSO4={0}&".format(s04_ion)
        except ValueError:
            var_dict['AqSO4'] = u""

        # Sulfur Dioxide [(sulfur dioxide), conventional PPB]
        try:
            sulfur_dioxide    = indigo.variables[int(self.pluginPrefs['AqSO2'])].value
            var_dict['AqSO2'] = u"AqSO2={0}&".format(sulfur_dioxide)
        except ValueError:
            var_dict['AqSO2'] = u""

        # [trace levels PPB]
        try:
            trace_ppb          = indigo.variables[int(self.pluginPrefs['AqSO2T'])].value
            var_dict['AqSO2T'] = u"AqSO2T={0}&".format(trace_ppb)
        except ValueError:
            var_dict['AqSO2T'] = u""

        # Carbon Monoxide [CO (carbon monoxide), conventional ppm]
        try:
            carbon_monoxide  = indigo.variables[int(self.pluginPrefs['AqCO'])].value
            var_dict['AqCO'] = u"AqCO={0}&".format(carbon_monoxide)
        except ValueError:
            var_dict['AqCO'] = u""

        # Carbon Monoxide Trace [CO trace levels PPB]
        try:
            carbon_monoxide_trace = indigo.variables[int(self.pluginPrefs['AqCOT'])].value
            var_dict['AqCOT']     = u"AqCOT={0}&".format(carbon_monoxide_trace)
        except ValueError:
            var_dict['AqCOT']     = ""

        # Elemental Carbon[EC (elemental carbon) – PM2.5 UG/M3]
        try:
            elemental_carbon = indigo.variables[int(self.pluginPrefs['AqEC'])].value
            var_dict['AqEC'] = u"AqEC={0}&".format(elemental_carbon)
        except ValueError:
            var_dict['AqEC'] = u""

        # Organic Carbon [OC (organic carbon, not adjusted for oxygen and hydrogen) – PM2.5 UG/M3]
        try:
            organic_carbon   = indigo.variables[int(self.pluginPrefs['AqOC'])].value
            var_dict['AqOC'] = u"AqOC={0}&".format(organic_carbon)
        except ValueError:
            var_dict['AqOC'] = u""

        # Black Carbon [BC (black carbon at 880 nm) UG/M3]
        try:
            black_carbon     = indigo.variables[int(self.pluginPrefs['AqBC'])].value
            var_dict['AqBC'] = u"AqBC={0}&".format(black_carbon)
        except ValueError:
            var_dict['AqBC'] = u""

        # Aethalometer [UV-AETH (second channel of Aethalometer at 370 nm for aromatic organic compounds) UG/M3]
        try:
            aethalometer          = indigo.variables[int(self.pluginPrefs['AqUV-AETH'])].value
            var_dict['AqUV_AETH'] = u"AqUV_AETH={0}&".format(aethalometer)
        except ValueError:
            var_dict['AqUV_AETH'] = u""

        # [PM2.5 mass - UG/M3]
        try:
            pm25_mass           = indigo.variables[int(self.pluginPrefs['AqPM2.5'])].value
            var_dict['AqPM2_5'] = u"AqPM2_5={0}&".format(pm25_mass)
        except ValueError:
            var_dict['AqPM2_5'] = u""

        # [PM10 mass - PM10 mass]
        try:
            aq_pm_10           = indigo.variables[int(self.pluginPrefs['AqPM10'])].value
            var_dict['AqPM10'] = u"AqPM10={0}&".format(aq_pm_10)
        except ValueError:
            var_dict['AqPM10'] = u""

        # Ozone [Ozone - PPB]
        try:
            ozone               = indigo.variables[int(self.pluginPrefs['AqOZONE'])].value
            var_dict['AqOZONE'] = u"AqOZONE={0}&".format(ozone)
        except ValueError:
            var_dict['AqOZONE'] = u""

        try:

            action        = u"action=updateraw"                                                               # always supply this parameter to indicate you are making a weather observation upload
            dateutc       = u"dateutc=now&"                                                                   # [YYYY-MM-DD HH:MM:SS (mysql format)] In Universal Coordinated Time (UTC) __not_local_time__
            password      = u"PASSWORD={0}&".format(self.pluginPrefs['wunderstationPassword'])                # [Station Key registered with this PWS ID, case sensitive]
            pws_id        = u"ID={0}&".format(self.pluginPrefs['wunderstationID'])                            # [ID as registered by wunderground.com]
            software_type = u"softwaretype=WUnderstation%20Plugin%20for%20Indigo%20{0}&".format(__version__)  # [text] ie: WeatherLink, VWS, WeatherDisplay

            # Create the first part of the upload URL. Seems like it is a requirement
            # to have these items appear first.
            url = (u"http://weatherstation.wunderground.com/weatherstation/updateweatherstation.php?{0}{1}{2}".format(pws_id, password, dateutc))

            # Add the established variables to the url before uploading.
            for key in var_dict.keys():
                url += var_dict[key]

            # Follow up with the last remaining elements
            url = u"{0}{1}{2}".format(url, software_type, action)

            # self.logger.debug(u"{0}".format(url))
            self.logger.debug(u"URL for upload: {0}".format(url))

            result = requests.get(url, timeout=1)

            # There are (as of 2018-05-16) two possible responses from the server.
            # [Note that there is also a Rapid Fire response, but Rapid Fire is not
            # currently supported by the plugin.]
            if result.status_code == 200:

                if "SUCCESS" in result.text:
                    self.logger.debug(u"Data uploaded successfully.")
                    states_list.append({'key': 'onOffState', 'value': True, 'uiValue': 'OK'})
                    states_list.append({'key': 'lastUploadResult', 'value': result.text})
                    states_list.append({'key': 'lastUploadTime', 'value': u"{0}".format(indigo.server.getTime())})

                elif "INVALIDPASSWORDID" in result.text:
                    self.logger.warning(u"Warning: Unable to upload WUderstation data. Reason: Password and/or id are incorrect.")
                    states_list.append({'key': 'onOffState', 'value': False, 'uiValue': 'PWD'})
                    states_list.append({'key': 'lastUploadResult', 'value': result.text})
                    states_list.append({'key': 'lastUploadTime', 'value': u"{0}".format(indigo.server.getTime())})

                elif result.status_code != 200:
                    self.logger.warning(u"Warning: Unable to upload WUnderstation data. Reason: {0}".format(result.text))
                    states_list.append({'key': 'onOffState', 'value': False, 'uiValue': 'ERR'})
                    states_list.append({'key': 'lastUploadResult', 'value': result.text})
                    states_list.append({'key': 'lastUploadTime', 'value': u"{0}".format(indigo.server.getTime())})

                else:
                    raise Exception

            dev.updateStatesOnServer(states_list)

            return

        except Exception as error:
            self.logger.critical(u"Unable to upload WUnderstation data. Reason: Exception - {0}".format(error))

    def webify(self, val):
        """
        Format the target URL for proper structure

        The webify() method takes the passed value and corrects it for proper structure
        for use in the URL. [using: http://www.w3schools.com/tags/ref_urlencode.asp]
        Do not replace '&', '?' (as they are required characters.)

        -----

        """

        return val.replace(' ', '%20')

