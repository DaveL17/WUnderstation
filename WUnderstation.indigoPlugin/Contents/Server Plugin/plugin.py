#!/usr/bin/env python2.5
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
# TODO: Think about adding a device to track the health of the plugin.  It could register:
#   - the timestamp of the last successful update,
#   - the plugin version,
#   - the last update message (i.e, OK, Error, what the error is, etc.)
# TODO: Consider whether it's possible to include the PWS sign-up within the plugin.
# TODO: Enable RapidFire?
# TODO: What Trigger, Action events (etc.) are necessary?

import indigoPluginUpdateChecker
import socket
import urllib2
try:
    import indigo
except ImportError:
    pass

__author__    = "DaveL17"
__build__     = ""
__copyright__ = 'Copyright 2016 DaveL17'
__license__   = "MIT"
__title__     = 'WUnderstation Plugin for Indigo Home Control'
__version__   = '1.0.01'

# Establish default plugin prefs; create them if they don't already exist.
kDefaultPluginPrefs = {
    'showDebugInfo'        : False,  # Debug on/off
    'showDebugLevel'       : "1",    # Low, Medium or High debug output.
    'updaterEmail'         : "",     # Email to notify of plugin updates.
    'updaterEmailsEnabled' : False,  # Notification of plugin updates wanted.
    'uploadInterval'       : 900,    # How often to upload data?
    'wunderstationID'      : "",     # Frequency of updates.
    'wunderstationPassword': ""      # Verbose debug logging?
}


class Plugin(indigo.PluginBase):
    def __init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs):
        indigo.PluginBase.__init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs)
        self.debugLog(u"Plugin initialization called.")

        self.debug                = self.pluginPrefs.get('showDebugInfo', False)
        self.debugLevel           = int(self.pluginPrefs.get('showDebugLevel', "1"))
        updater_url               = 'https://dl.dropboxusercontent.com/u/2796881/wunderstation.html'
        self.updater              = indigoPluginUpdateChecker.updateChecker(self, updater_url)
        self.updaterEmail         = self.pluginPrefs.get('updaterEmail', "")
        self.updaterEmailsEnabled = self.pluginPrefs.get('updaterEmailsEnabled', "false")

        self.debugLog(u"Debug level set to: {0}".format(self.debugLevel))
        if self.debug and self.debugLevel >= 3:
            self.debugLog(u"================================================================================")
            self.debugLog(u"Caution! Debug set to high. Your username and password will be shown in the log.")
            self.debugLog(u"================================================================================")
            self.sleep(3)
            self.debugLog(unicode(pluginPrefs))
        else:
            self.debugLog(u"Set debug level to [High] to write plugin preferences to the log.")

    def __del__(self):
        indigo.PluginBase.__del__(self)

    def closedPrefsConfigUi(self, valuesDict, userCancelled):
        """User closes config menu."""
        self.debugLog(u"closedPrefsConfigUi() method called.")

        if userCancelled:
            self.debugLog(u"  User prefs dialog cancelled.")

        if not userCancelled:
            # If the user selects 'save' within the dialog.
            self.debugLog(u"  User prefs saved.")
            self.debug      = valuesDict.get('showDebugInfo', False)
            self.debugLevel = int(self.pluginPrefs['showDebugLevel'])

            self.debugLog(u"============ Plugin Prefs ============")
            if self.debug and self.debugLevel >= 3:
                self.debugLog(unicode(valuesDict))
            else:
                self.debugLog(u"Plugin preferences suppressed. Set debug level to [High] to write them to the log.")

            if self.debug:
                self.debugLog(u"Debugging on. Level set to: {0}".format(self.debugLevel))
            else:
                self.debugLog(u"Debugging off.")

    def toggleDebugEnabled(self):
        """Toggle debug on/off."""
        self.debugLog(u"toggleDebugEnabled() method called.")

        if not self.debug:
            self.debug = True
            self.pluginPrefs['showDebugInfo'] = True
            indigo.server.log(u"Debugging on.")
            self.debugLog(u"Debug level: {0}".format(self.debugLevel))
        else:
            self.debug = False
            self.pluginPrefs['showDebugInfo'] = False
            indigo.server.log(u"Debugging off.")

    def validatePrefsConfigUi(self, valuesDict):
        """Validate select plugin config menu settings."""
        self.debugLog(u"validatePrefsConfigUi() method called.")

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
            pass

        return True, valuesDict

    def shutdown(self):
        self.debugLog(u"Shutdown() method called.")

    def startup(self):
        """See if there is a plugin update and whether the user wants to be notified."""
        self.debugLog(u"Startup() method called.")

        try:
            self.updater.checkVersionPoll()
        except Exception as error:
            self.errorLog(u"Update checker error.")

    def checkVersionNow(self):
        """Called if user selects "Check For Plugin Updates..." Indigo
        # menu item."""
        self.debugLog(u"checkVersionNow() method called.")

        self.updater.checkVersionNow()

    def floatCheck(self, var_name, val):
        """The floatCheck() method takes a passed value and determines
        whether it will float. If it will, it is returned for use.  If
        it will not, it is set to an empty string and the user is
        notified. If we don't set it to an empty string, WU may reject
        the entire upload."""
        self.debugLog(u"floatCheck() method called.")

        try:
            if float(val):
                return val
        except Exception as error:
            val = ""
            self.errorLog(u"Disallowing {0}. Reason: value must be greater than or equal to 0.".format(var_name))
            return val

    def getGlobalProps(self):
        """The getGlobalProps method retrieves all pluginProps and
        assigns them to global variables."""
        self.debugLog(u"getGlobalProps() method called.")

        # Set up global values for each device as we iterate through
        # them (as they may have changed.)
        self.debug            = self.pluginPrefs.get('showDebugInfo', False)
        self.debugLevel       = self.pluginPrefs.get('showDebugLevel', 1)
        self.updater          = indigoPluginUpdateChecker.updateChecker(self, "http://dl.dropboxusercontent.com/u/2796881/WUnderstation_version.html")
        self.updaterEmail     = self.pluginPrefs.get('updaterEmail', "")

    def getPrefsConfigUiValues(self):
        """
        The getPrefsConfigUiValues() method will return the
        pluginPrefs dict when the plugin 'Configure...' menu item is
        called.  It is run between the reading of the pluginPrefs dict
        and the dialog display. It is therefore possible to modify it
        before the config dialog opens."""
        self.debugLog(u'getPrefsConfigUiValues(self) method called:')

        prefs_config_ui_values = self.pluginPrefs
        for key in prefs_config_ui_values:
            if prefs_config_ui_values[key] == "":
                prefs_config_ui_values[key] = u'None'
        return prefs_config_ui_values

    def greaterThanZero(self, var_name, val):
        """The percentageCheck() method ensures that a wind direction
        value is valid (greater than zero.)"""
        self.debugLog(u"greaterThanZero() method called.")

        if not float(val) >= 0:
            val = ""
            self.errorLog(u"Disallowing {0}. Reason: value must be greater than or equal to 0.".format(var_name))

        return val

    def percentageCheck(self, var_name, val):
        """The percentageCheck() method ensures that a wind direction
        value is valid (between 0 and 100.)"""
        self.debugLog(u"percentageCheck() method called.")

        if not 100 >= float(val) >= 0:
            val = ""
            self.errorLog(u"Disallowing {0}. Reason: value must be between 0 and 100.".format(var_name))

        return val

    def uploadWUnderstationData(self):
        """The uploadWUnderstationData() method gathers weather data
        from user-specified variable values and assigns them to the
        appropriate variable names for upload. All values are assigned--
        blank values are assigned an empty string--and are added to a
        master dictionary with the structure {WUvariable:value}. These
        are parsed out later when the final URL is assembled for upload."""
        self.debugLog(u"uploadWUnderstationData() method called.")

        try:
            self.debugLog(u"  Get variable values.")
            self.debugLevel = int(self.pluginPrefs.get('showDebugLevel', 1))
            var_dict = {}

# Weather values. Certain rules are applied to the data which are governed by methods above.

    # Wind Direction: [0-360 instantaneous wind direction] Integer, must be greater than or equal to zero.
            try:
                wind_dir            = indigo.variables[int(self.pluginPrefs['winddir'])].value
                var_dict['winddir'] = u"winddir={0}&".format(self.windCheck('winddir', wind_dir))
            except Exception as error:
                var_dict['winddir'] = u""

    # Wind Speed [mph instantaneous wind speed] Float, must be greater than or equal to zero.
            try:
                wind_speed               = indigo.variables[int(self.pluginPrefs['windspeedmph'])].value
                var_dict['windspeedmph'] = u"windspeedmph={0}&".format(self.greaterThanZero('windspeedmph', wind_speed))
            except Exception as error:
                var_dict['windspeedmph'] = u""

    # Wind Speed Gust [mph current wind gust, using software specific time period] Float, must be greater than or equal to zero.
            try:
                wind_speed_gust         = indigo.variables[int(self.pluginPrefs['windgustmph'])].value
                var_dict['windgustmph'] = u"windgustmph={0}&".format(self.greaterThanZero('windgustmph', wind_speed_gust))
            except Exception as error:
                var_dict['windgustmph'] = u""

    # Wind Speed Gust Direction [0-360 using software specific time period] Integer, must be between 0 and 360 inclusive.
            try:
                wind_speed_gust_dir     = indigo.variables[int(self.pluginPrefs['windgustdir'])].value
                var_dict['windgustdir'] = u"windgustdir={0}&".format(self.windCheck('windgustdir', wind_speed_gust_dir))
            except Exception as error:
                var_dict['windgustdir'] = u""

    # Wind Speed Average 2 Minutes [mph 2 minute average wind speed mph] Float, must be greater than or equal to zero.
            try:
                wind_speed_avg_2min          = indigo.variables[int(self.pluginPrefs['windspdmph_avg2m'])].value
                var_dict['windspdmph_avg2m'] = u"windspdmph_avg2m={0}&".format(self.greaterThanZero('windspdmph_avg2m', wind_speed_avg_2min))
            except Exception as error:
                var_dict['windspdmph_avg2m'] = u""

    # Wind Direction Average 2 Minutes [0-360 2 minute average wind direction] Integer, must be between 0 and 360 inclusive.
            try:
                wind_dir_avg_2min         = indigo.variables[int(self.pluginPrefs['winddir_avg2m'])].value
                var_dict['winddir_avg2m'] = u"winddir_avg2m={0}&".format(self.windCheck('winddir_avg2m', wind_dir_avg_2min))
            except Exception as error:
                var_dict['winddir_avg2m'] = u""

    # Wind Speed Average 10 Minutes [mph past 10 minutes wind gust mph] Float, must be greater than or equal to zero.
            try:
                wind_speed_avg_10min        = indigo.variables[int(self.pluginPrefs['windgustmph_10m'])].value
                var_dict['windgustmph_10m'] = u"windgustmph_10m={0}&".format(self.greaterThanZero('windgustmph_10m', wind_speed_avg_10min))
            except Exception as error:
                var_dict['windgustmph_10m'] = u""

    # Wind Direction Average 10 Minutes [0-360 past 10 minutes wind gust direction] Integer, must be between 0 and 360 inclusive.
            try:
                wind_dir_avg_10min          = indigo.variables[int(self.pluginPrefs['windgustdir_10m'])].value
                var_dict['windgustdir_10m'] = u"windgustdir_10m={0}&".format(self.windCheck('windgustdir_10m', wind_dir_avg_10min))
            except Exception as error:
                var_dict['windgustdir_10m'] = u""

    # Outdoor Humidity [% outdoor humidity 0-100%] Float, must be between 0 and 100 inclusive.
            try:
                outdoor_humidity     = indigo.variables[int(self.pluginPrefs['humidity'])].value
                var_dict['humidity'] = u"humidity={0}&".format(self.percentageCheck('humidity', outdoor_humidity))
            except Exception as error:
                var_dict['humidity'] = u""

    # Outdoor Dewpoint [F outdoor dewpoint F] Float.
            try:
                outdoor_dewpoint   = indigo.variables[int(self.pluginPrefs['dewptf'])].value
                var_dict['dewptf'] = u"dewptf={0}&".format(self.floatCheck('dewptf', outdoor_dewpoint))
            except Exception as error:
                var_dict['dewptf'] = u""

    # Outdoor Temperature 1 [F outdoor temperature] Float.
            try:
                outdoor_temp_1     = indigo.variables[int(self.pluginPrefs['tempf1'])].value
                var_dict['temp1f'] = u"tempf={0}&".format(self.floatCheck('temp1f', outdoor_temp_1))
            except Exception as error:
                var_dict['temp1f'] = u""

    # Outdoor Temperature 2 [F outdoor temperature] Float.
            try:
                outdoor_temp_2     = indigo.variables[int(self.pluginPrefs['tempf2'])].value
                var_dict['temp2f'] = u"temp2f={0}&".format(self.floatCheck('temp2f', outdoor_temp_2))
            except Exception as error:
                var_dict['temp2f'] = u""

    # Outdoor Temperature 3 [F outdoor temperature] Float.
            try:
                outdoor_temp_3     = indigo.variables[int(self.pluginPrefs['tempf3'])].value
                var_dict['temp3f'] = u"temp3f={0}&".format(self.floatCheck('temp3f', outdoor_temp_3))
            except Exception as error:
                var_dict['temp3f'] = u""

    # Outdoor Temperature 4 [F outdoor temperature] Float.
            try:
                outdoor_temp_4     = indigo.variables[int(self.pluginPrefs['tempf4'])].value
                var_dict['temp4f'] = u"temp4f={0}&".format(self.floatCheck('temp4f', outdoor_temp_4))
            except Exception as error:
                var_dict['temp4f'] = u""

    # Rain Last Hour [rain inches over the past hour] Float, must be greater than or equal to zero.
            try:
                rain_last_hour     = indigo.variables[int(self.pluginPrefs['rainin'])].value
                var_dict['rainin'] = u"rainin={0}&".format(self.floatCheck('rainin', rain_last_hour))
            except Exception as error:
                var_dict['rainin'] = u""

    # Rain All Day [rain inches so far today in local time] Float, must be greater than or equal to zero.
            try:
                rain_all_day            = indigo.variables[int(self.pluginPrefs['dailyrainin'])].value
                var_dict['dailyrainin'] = u"dailyrainin={0}&".format(self.greaterThanZero('dailyrainin', rain_all_day))
            except Exception as error:
                var_dict['dailyrainin'] = u""

    # Barometric Pressure [barometric pressure inches] Float, must be greater than zero.
            try:
                barometric_pressure = indigo.variables[int(self.pluginPrefs['baromin'])].value
                var_dict['baromin'] = u"baromin={0}&".format(self.greaterThanZero('baromin', barometric_pressure))
            except Exception as error:
                var_dict['baromin'] = u""

    # Current Weather [metar style (+RA)] String.
            try:
                current_weather     = indigo.variables[int(self.pluginPrefs['weather'])].value
                var_dict['weather'] = u"weather={0}&".format(self.webify(current_weather))
            except Exception as error:
                var_dict['weather'] = u""

    # Current CloudsText - SKC, FEW, SCT, BKN, OVC] String.
            try:
                current_clouds     = indigo.variables[int(self.pluginPrefs['clouds'])].value
                var_dict['clouds'] = u"clouds={0}&".format(self.webify(current_clouds))
            except Exception as error:
                var_dict['clouds'] = u""

    # Soil Temperature 1 [F soil temperature] Float.
            try:
                soil_temp_1           = indigo.variables[int(self.pluginPrefs['soiltempf1'])].value
                var_dict['soiltempf'] = u"soiltemp1f={0}&".format(self.floatCheck('soiltemp1f', soil_temp_1))
            except Exception as error:
                var_dict['soiltempf'] = u""

    # Soil Temperature 2 [F soil temperature] Float.
            try:
                soil_temp_2            = indigo.variables[int(self.pluginPrefs['soiltempf2'])].value
                var_dict['soiltemp2f'] = u"soiltemp2f={0}&".format(self.floatCheck('soiltemp2f', soil_temp_2))
            except Exception as error:
                var_dict['soiltemp2f'] = u""

    # Soil Temperature 3 [F soil temperature] Float.
            try:
                soil_temp_3            = indigo.variables[int(self.pluginPrefs['soiltempf3'])].value
                var_dict['soiltemp3f'] = u"soiltemp3f={0}&".format(self.floatCheck('soiltemp3f', soil_temp_3))
            except Exception as error:
                var_dict['soiltemp3f'] = u""

    # Soil Temperature 4 [F soil temperature] Float.
            try:
                soil_temp_4            = indigo.variables[int(self.pluginPrefs['soiltempf4'])].value
                var_dict['soiltemp4f'] = u"soiltemp4f={0}&".format(self.floatCheck('soiltemp4f', soil_temp_4))
            except Exception as error:
                var_dict['soiltemp4f'] = u""

    # Soil Moisture 1 [%] Float. Must be between 0 and 100 inclusive.
            try:
                soil_moisture_1          = indigo.variables[int(self.pluginPrefs['soilmoisture1'])].value
                var_dict['soilmoisture'] = u"soilmoisture1={0}&".format(self.percentageCheck('soilmoisture1', soil_moisture_1))
            except Exception as error:
                var_dict['soilmoisture'] = u""

    # Soil Moisture 2 [%] Float. Must be between 0 and 100 inclusive.
            try:
                soil_moisture_2           = indigo.variables[int(self.pluginPrefs['soilmoisture2'])].value
                var_dict['soilmoisture2'] = u"soilmoisture2={0}&".format(self.percentageCheck('soilmoisture2', soil_moisture_2))
            except Exception as error:
                var_dict['soilmoisture2'] = u""

    # Soil Moisture 3 [%] Float. Must be between 0 and 100 inclusive.
            try:
                soil_moisture_3           = indigo.variables[int(self.pluginPrefs['soilmoisture3'])].value
                var_dict['soilmoisture3'] = u"soilmoisture3={0}&".format(self.percentageCheck('soilmoisture3', soil_moisture_3))
            except Exception as error:
                var_dict['soilmoisture3'] = u""

    # Soil Moisture 4 [%] Float. Must be between 0 and 100 inclusive.
            try:
                soil_moisture_4           = indigo.variables[int(self.pluginPrefs['soilmoisture4'])].value
                var_dict['soilmoisture4'] = u"soilmoisture4={0}&".format(self.percentageCheck('soilmoisture4', soil_moisture_4))
            except Exception as error:
                var_dict['soilmoisture4'] = u""

    # Leaf Wetness 1 [%] Float. Must be between 0 and 100 inclusive.
            try:
                leaf_wetness_1          = indigo.variables[int(self.pluginPrefs['leafwetness1'])].value
                var_dict['leafwetness'] = u"leafWetness1={0}&".format(self.percentageCheck('leafWetness1', leaf_wetness_1))
            except Exception as error:
                var_dict['leafwetness'] = u""

    # Leaf Wetness 2 [%] Float. Must be between 0 and 100 inclusive.
            try:
                leaf_wetness_2           = indigo.variables[int(self.pluginPrefs['leafwetness2'])].value
                var_dict['leafwetness2'] = u"leafWetness2={0}&".format(self.percentageCheck('leafWetness2', leaf_wetness_2))
            except Exception as error:
                var_dict['leafwetness2'] = u""

    # Solar Radiation [Watts per square meter. W/m^2] Float. Must be greater than or equal to zero.
            try:
                solar_radiation            = indigo.variables[int(self.pluginPrefs['solarradiation'])].value
                var_dict['solarradiation'] = u"solarradiation={0}&".format(self.floatCheck('solarradiation', solar_radiation))
            except Exception as error:
                var_dict['solarradiation'] = u""

    # Ultra Violet Index [Index] Integer. Must be greater than or equal to zero.
            try:
                uv_index       = indigo.variables[int(self.pluginPrefs['UV'])].value
                var_dict['uv'] = u"UV={0}&".format(self.floatCheck('UV', uv_index))
            except Exception as error:
                var_dict['uv'] = u""

    # Visibility [nautical miles visibility] Float. Must be greater than or equal to zero.
            try:
                visibility             = indigo.variables[int(self.pluginPrefs['visibility'])].value
                var_dict['visibility'] = u"visibility={0}&".format(self.floatCheck('visibility', visibility))
            except Exception as error:
                var_dict['visibility'] = u""

    # Indoor Temperature [F indoor temperature F] Float.
            try:
                indoor_temperature      = indigo.variables[int(self.pluginPrefs['indoortempf'])].value
                var_dict['indoortempf'] = u"indoortempf={0}&".format(self.floatCheck('indoortempf', indoor_temperature))
            except Exception as error:
                var_dict['indoortempf'] = u""

    # Indoor Humidity [% indoor humidity 0-100] Float.  Must be between 0 and 100 inclusive.
            try:
                indoor_humidity            = indigo.variables[int(self.pluginPrefs['indoorhumidity'])].value
                var_dict['indoorhumidity'] = u"indoorhumidity={0}&".format(self.floatCheck('indoorhumidity', indoor_humidity))
            except Exception as error:
                var_dict['indoorhumidity'] = u""

# Air quality values.  These need rules at some point.

    # Nitric Oxide [NO (nitric oxide) PPB]
            try:
                nitric_oxide     = indigo.variables[int(self.pluginPrefs['AqNO'])].value
                var_dict['AqNO'] = u"AqNO={0}&".format(nitric_oxide)
            except Exception as error:
                var_dict['AqNO'] = u""

    # Nitrogen Dioxide [(nitrogen dioxide), true measure PPB]
            try:
                nitrogen_dioxide   = indigo.variables[int(self.pluginPrefs['AqNO2T'])].value
                var_dict['AqNO2T'] = u"AqNO2T={0}&".format(nitrogen_dioxide)
            except Exception as error:
                var_dict['AqNO2T'] = u""

    # [NO2 computed, NOx-NO PPB]
            try:
                no2_computed_nox  = indigo.variables[int(self.pluginPrefs['AqNO2'])].value
                var_dict['AqNO2'] = u"AqNO2={0}&".format(no2_computed_nox)
            except Exception as error:
                var_dict['AqNO2'] = u""

    # [NO2 computed, NOy-NO PPB]
            try:
                no2_computed_noy   = indigo.variables[int(self.pluginPrefs['AqNO2Y'])].value
                var_dict['AqNO2Y'] = u"AqNO2Y={0}&".format(no2_computed_noy)
            except Exception as error:
                var_dict['AqNO2Y'] = u""

    # Nitrogen Oxides [NOx (nitrogen oxides) - PPB]
            try:
                nitrogen_oxides   = indigo.variables[int(self.pluginPrefs['AqNOX'])].value
                var_dict['AqNOX'] = u"AqNOX={0}&".format(nitrogen_oxides)
            except Exception as error:
                var_dict['AqNOX'] = u""

    # Total Reactive Nitrogen [NOy (total reactive nitrogen) - PPB]
            try:
                total_reactive_nitrogen = indigo.variables[int(self.pluginPrefs['AqNOY'])].value
                var_dict['AqNOY']       = u"AqNOY={0}}&".format(total_reactive_nitrogen)
            except Exception as error:
                var_dict['AqNOY']       = u""

    # [NO3 ion (nitrate, not adjusted for ammonium ion) UG/M3]
            try:
                no3_ion = indigo.variables[int(self.pluginPrefs['AqNO3'])].value
                var_dict['AqNO3'] = u"AqNO3={0}&".format(no3_ion)
            except Exception as error:
                var_dict['AqNO3'] = u""

    # [SO4 ion (sulfate, not adjusted for ammonium ion) UG/M3]
            try:
                s04_ion           = indigo.variables[int(self.pluginPrefs['AqSO4'])].value
                var_dict['AqSO4'] = u"AqSO4={0}&".format(s04_ion)
            except Exception as error:
                var_dict['AqSO4'] = u""

    # Sulfur Dioxide [(sulfur dioxide), conventional PPB]
            try:
                sulfur_dioxide    = indigo.variables[int(self.pluginPrefs['AqSO2'])].value
                var_dict['AqSO2'] = u"AqSO2={0}&".format(sulfur_dioxide)
            except Exception as error:
                var_dict['AqSO2'] = u""

    # [trace levels PPB]
            try:
                trace_ppb          = indigo.variables[int(self.pluginPrefs['AqSO2T'])].value
                var_dict['AqSO2T'] = u"AqSO2T={0}&".format(trace_ppb)
            except Exception as error:
                var_dict['AqSO2T'] = u""

    # Carbon Monoxide [CO (carbon monoxide), conventional ppm]
            try:
                carbon_monoxide  = indigo.variables[int(self.pluginPrefs['AqCO'])].value
                var_dict['AqCO'] = u"AqCO={0}&".format(carbon_monoxide)
            except Exception as error:
                var_dict['AqCO'] = u""

    # Carbon Monoxide Trace [CO trace levels PPB]
            try:
                carbon_monoxide_trace = indigo.variables[int(self.pluginPrefs['AqCOT'])].value
                var_dict['AqCOT']     = u"AqCOT={0}&".format(carbon_monoxide_trace)
            except Exception as error:
                var_dict['AqCOT']     = ""

    # Elemental Carbon[EC (elemental carbon) – PM2.5 UG/M3]
            try:
                elemental_carbon = indigo.variables[int(self.pluginPrefs['AqEC'])].value
                var_dict['AqEC'] = u"AqEC={0}&".format(elemental_carbon)
            except Exception as error:
                var_dict['AqEC'] = u""

    # Organic Carbon [OC (organic carbon, not adjusted for oxygen and hydrogen) – PM2.5 UG/M3]
            try:
                organic_carbon   = indigo.variables[int(self.pluginPrefs['AqOC'])].value
                var_dict['AqOC'] = u"AqOC={0}&".format(organic_carbon)
            except Exception as error:
                var_dict['AqOC'] = u""

    # Black Carbon [BC (black carbon at 880 nm) UG/M3]
            try:
                black_carbon     = indigo.variables[int(self.pluginPrefs['AqBC'])].value
                var_dict['AqBC'] = u"AqBC={0}&".format(black_carbon)
            except Exception as error:
                var_dict['AqBC'] = u""

    # Aethalometer [UV-AETH (second channel of Aethalometer at 370 nm for aromatic organic compounds) UG/M3]
            try:
                aethalometer          = indigo.variables[int(self.pluginPrefs['AqUV-AETH'])].value
                var_dict['AqUV_AETH'] = u"AqUV_AETH={0}&".format(aethalometer)
            except Exception as error:
                var_dict['AqUV_AETH'] = u""

    # [PM2.5 mass - UG/M3]
            try:
                pm25_mass           = indigo.variables[int(self.pluginPrefs['AqPM2.5'])].value
                var_dict['AqPM2_5'] = u"AqPM2_5={0}&".format(pm25_mass)
            except Exception as error:
                var_dict['AqPM2_5'] = u""

    # [PM10 mass - PM10 mass]
            try:
                aq_pm_10           = indigo.variables[int(self.pluginPrefs['AqPM10'])].value
                var_dict['AqPM10'] = u"AqPM10={0}&".format(aq_pm_10)
            except Exception as error:
                var_dict['AqPM10'] = u""

    # Ozone [Ozone - PPB]
            try:
                ozone               = indigo.variables[int(self.pluginPrefs['AqOZONE'])].value
                var_dict['AqOZONE'] = u"AqOZONE={0}&".format(ozone)
            except Exception as error:
                var_dict['AqOZONE'] = u""

            if self.debugLevel >= 2:
                for (key, value) in sorted(var_dict.iteritems()):
                    self.debugLog(u"{0} = {1}".format(key, value))

            # Construct URL for upload. Variables arrayed in order of WUnderground Wiki. Not sure if they can appear in the URL in any order...
            self.debugLog(u"Constructing URL for upload.")

            # [YYYY-MM-DD HH:MM:SS (mysql format)] In Universal Coordinated Time (UTC) __not_local_time__
            pws_id        = u"ID={0}&".format(self.pluginPrefs['wunderstationID'])
            password      = u"PASSWORD={0}&".format(self.pluginPrefs['wunderstationPassword'])
            dateutc       = u"dateutc=now&"
            software_type = u"softwaretype=WUnderstation%20Plugin%20for%20Indigo%20{0}&".format(__version__)
            action        = u"action=updateraw"

            # Create the first part of the upload URL. I believe that it is a requirement to have these items appear first.
            url = (u"http://weatherstation.wunderground.com/weatherstation/updateweatherstation.php?{0}{1}{2}".format(pws_id, password, dateutc))

            # Add the established variables to the url before uploading.
            for key, value in var_dict.iteritems():
                url = url + value

            # Follow up with the last remaining elements
            url = url + software_type + action

            if self.debugLevel >= 3:
                self.debugLog(u"{0}".format(url))

            try:
                socket.setdefaulttimeout(15)
                f = urllib2.urlopen(url)
                result = f.read()
                f.close()

                if "INVALIDPASSWORDID" in result:
                    self.errorLog(u"Warning: Password and/or id are incorrect")
                elif "SUCCESS" in result:
                    self.degLog(u"Data uploaded successfully.")
                # TODO: the following elif is for future functionality.
                elif "RapidFire Server" in result:
                    self.degLog(u"RapidFire Data uploaded successfully.")
                else:
                    self.errorLog(u"Result: {0}".format(result))

            except urllib2.HTTPError as e:
                self.errorLog(u"Unable to reach PWS service. Reason: HTTPError - {0}".format(e))

            except urllib2.URLError as e:
                self.errorLog(u"Unable to reach PWS service. Reason: URLError - {0}".format(e))

            except Exception as e:
                if "invalid literal for int() with base 16: ''" in e:
                    self.errorLog(u"Congratulations! You have discovered a somewhat obscure bug in Python2.5. "
                                  u"This problem should clear up on its own, but may come back periodically.")
                else:
                    self.errorLog(u"Error preparing for upload to PWS service. Reason: Exception - {0}".format(e))
            return

        except Exception as e:
            self.errorLog(u"Unable to upload WUnderstation data. Reason: Exception - {0}".format(e))

        return

    def varListGenerator(self, filter="", valuesDict=None, typeId=0, targetId=0):
        """This method collects IDs and names for all Indigo devices
        and variables. It creates a dictionary of the form ((dev.id,
        dev.name), (var.id, var.name)). We don't write this call to the
        debug log because if we did, it would be written 53 times."""

        var_list = [(var.id, var.name) for var in indigo.variables]
        var_list.append((u'None', u'None'))
        return var_list

    def webify(self, val):
        """The webify() method takes the passed value and corrects it
        for proper structure for use in the URL.
        [using: http://www.w3schools.com/tags/ref_urlencode.asp]
        Do not replace '&', '?' (as they are required characters.)"""
        self.debugLog(u"webify() method called.")

        val = val.replace(' ', '%20')
        return val

    def windCheck(self, var_name, val):
        """The windCheck() method ensures that a wind direction value
        is valid (between 0 and 360.)"""
        self.debugLog(u"windCheck() method called.")

        if not 360 >= float(val) >= 0:
            val = ""
            self.errorLog(u"Disallowing {0}. Reason: value must be between 0 and 360.".format(var_name))

        return val

    def runConcurrentThread(self):
        self.debugLog(u"runConcurrentThread initiated. Sleeping for 5 seconds.")
        self.sleep(5)
        self.updater.checkVersionPoll()

        try:
            while True:
                self.uploadWUnderstationData()
                self.sleep(int(self.pluginPrefs.get('uploadInterval', 900)))

        except self.StopThread:
            self.debugLog(u"StopThread() method called.")
