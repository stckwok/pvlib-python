#!/usr/bin/env python3

import pvlib
import pandas as pd
import sys, getopt
from matplotlib import pyplot as plt
from pv_base import PVBase
# from geopy.geocoders import Nominatim
from tkinter import *


# a "typical meteorological year" (TMY) is composed of individual months
# from several years, but to run a simulation we need
# to calculate solar positions for an actual year.
YEAR = 2019 #2018 #2015 #2010 # 2001 #1999 # 1997 #1990
STARTDATE = '%d-01-01T00:00:00' % YEAR
ENDDATE = '%d-12-31T23:59:59' % YEAR
TIMES = pd.date_range(start=STARTDATE, end=ENDDATE, freq='H')

# pvlib python can retrieve CEC module and inverter parameters from the SAM libraries
CECMODS = pvlib.pvsystem.retrieve_sam('CECMod')
INVERTERS = pvlib.pvsystem.retrieve_sam('CECInverter')

# It can be tricky to find the modules you want so you can visit their
# GitHub page to search the CSV files manually, or use pvfree
# https://pvfree.azurewebsites.net/api/v1/cecmodule/
# https://pvfree.azurewebsites.net/api/v1/pvinverters/
# Filtering
# https://pvfree.azurewebsites.net/api/v1/cecmodule/?{pv_params}&limit={limits}
# NOTE: whitespace, hyphens, dashes, etc. are replaced by underscores
# These are some basic 300-W Canadian Solar poly and mono Si modules

# Manufacturer datasheet
# https://www.pvxchange.com/Solar-Modules/Canadian-Solar/MaxPower-CS6X-300P_1-2106189
# https://www.pvxchange.com/Solar-Modules/Canadian-Solar/MaxPower-CS6X-300M_1-2108905

# monocrystalline and polycrystalline solar
CECMOD_POLY_1 = CECMODS['Canadian_Solar_Inc__CS6X_300P']
CECMOD_MONO_1 = CECMODS['Canadian_Solar_Inc__CS6X_300M']
# CS1H-325MS
CECMOD_POLY_2 = CECMODS['Canadian_Solar_Inc__CS1H_325MS']
CECMOD_MONO_2 = CECMODS['Canadian_Solar_Inc__CS1H_325MS']

# Inverter - transpose the database, and search the index using strings
INVERTERS.T[INVERTERS.T.index.str.startswith('SMA_America__STP')]
#                                       Vac         Pso     Paco  ... Mppt_high    CEC_Date             CEC_Type
# SMA_America__STP_60_US_10__480V_      480  116.969749  60000.0  ...     800.0         NaN  Utility Interactive
# SMA_America__STP_62_US_41__480V_      480  133.166687  62500.0  ...     800.0         NaN  Utility Interactive

# use the 60-kW Sunny TriPower, it's a good inverter.
INVERTER_60K = INVERTERS['SMA_America__STP_60_US_10__480V_']

# First, need to know where is the location (latitude, and longitude)
# https://www.generateit.net/gps-coordinates/   <<< enter address to look up LAT, and LON
# or
# Use geopy APIs  (only work in commandline since it can not be installed to IDE)

# LATITUDE, LONGITUDE = 40.5137, -108.5449
# LATITUDE, LONGITUDE = 49.194793, -123.182710   # Vancouver International Airport
# LATITUDE, LONGITUDE = 40.642422, -73.781749    # New York Airport
# LATITUDE, LONGITUDE = 22.312130, 113.924857    # 1 Sky Plaza Rd, Chek Lap Kok, Hong Kong
# LATITUDE, LONGITUDE = 63.995339, -22.623854   # Iceland Airport
# LATITUDE, LONGITUDE = 51.504473, 0.052271,    # London Airport
# LATITUDE, LONGITUDE = 29.241639, 47.972874,   # Newzealand Airport
# LATITUDE, LONGITUDE = 25.252747, 55.361275,   # Dubai Airport

# set address from user input
address = ""


def main(argv):
    # address = ''
    try:
        opts, args = getopt.getopt(argv, "ha:d:n:p:", ["ifile=", "ofile=", "lfile", "pfile"])
    except getopt.GetoptError:
        print("pv_modeling.py -a <address>")
        sys.exit(2)
    for opt, arg in opts:
        if opt == '-h':
            print("pv_modeling.py -a <address>")
            # print_usages()
            sys.exit()
        elif opt in ("-a", "--ifile"):
            address = arg

    print("Address = ", address)
    return address


class PVModeling(PVBase):
        # Modelling steps are defined in https://pvpmc.sandia.gov/
        # (1) weather
        # (2) solar position
        # (3) PV surface orientation, aoi, etc.
        # (4) plane of array irradiance
        # (5) module temperatures
        # (6) DC output power
        # (7) DC to AC conversion

        def set_test_params(self):
            # Override test parameters for your individual test.
            # This method must be overridden and num_nodes must be explicitly set.
            self.setup_clean_chain = True
            self.mpp1 = ''
            self.mpp2 = ''
            self.tech1 = ''
            self.tech2 = ''

        def get_solar_position(self, latitude, longitude):
            # get solar position
            # data.index = TIMES
            sp = pvlib.solarposition.get_solarposition(TIMES, latitude, longitude)
            solar_zenith = sp.apparent_zenith.values
            solar_azimuth = sp.azimuth.values
            # sp.plot()
            # plt.legend()
            # plt.grid()
            # plt.show()

            return solar_zenith, solar_azimuth

        def get_tracker_position(self, solar_zenith, solar_azimuth):
            # The angle of incidence (AOI) calculations require
            # surface_tilt, surface_azimuth and the extrinsic sun position
            tracker = pvlib.tracking.singleaxis(solar_zenith, solar_azimuth)
            surface_tilt = tracker['surface_tilt']
            surface_azimuth = tracker['surface_azimuth']
            aoi = tracker['aoi']
            return surface_tilt, surface_azimuth, aoi

        def get_irradiance(self, data):
            # Direct Normal, Global Horizontal, Diffuse Horizontal Irradiance
            dni = data['Gb(n)'].values
            ghi = data['G(h)'].values
            dhi = data['Gd(h)'].values
            dni_extra = pvlib.irradiance.get_extra_radiation(TIMES).values
            return dni, ghi, dhi, dni_extra

        def get_mpp(self, cecparams):
            # brentq - failed to converge after 100 iters.
            mpp = pvlib.pvsystem.max_power_point(*cecparams, method='newton')
            mpp = pd.DataFrame(mpp, index=TIMES)
            return mpp

        def plot_dc_energy(self, technology, mpp, longitude, latitude, location):
            mpp.p_mp.resample('D').sum().plot(figsize=(12, 8),
                        label='{} -> Longitude={}  Latitude={} '.format(location, str(longitude), str(latitude)),
                        title='Daily Energy ( {} )'.format(technology))
            plt.legend()
            plt.ylabel('Production [Wh]')
            plt.grid()
            plt.show()

        def plot_dc_ac_energy(self, technology, location, edaily, ac_output):
            plt.rcParams['font.size'] = 14
            ax = edaily.resample('D').sum().plot(figsize=(12, 8), label='DC',
                                                 title='Yearly Energy ( {} - {} )'.format(technology, location))
            ac_output.resample('D').sum().plot(ax=ax, label='AC')
            plt.ylabel('Energy [Wh/day]')
            plt.legend()
            plt.grid()
            plt.show()

        def plot_dc_compare(self, mpp1, mpp2, location, tech1="Mono-c-Si", tech2="Multi-c-Si"):
            mpp1.p_mp.resample('D').sum().plot(figsize=(12, 8),
                        label=tech1,
                        title='Comparing Daily Energy ( {} )'.format(location))
            mpp2.p_mp.resample('D').sum().plot(figsize=(12, 8), label=tech2)
            plt.legend()
            plt.ylabel('Production [Wh]')
            plt.grid()
            plt.show()

        def build_pv_array(self, cec_technology, temp_air, mpp):
            # Before we can do the AC side we need to build up our array. The first thing is the string length,
            # which is determined by the open circuit voltage, the lowest expected temperature at the site,
            # and the open circuit temperature coefficient.
            temp_ref = 25.0  # degC
            dc_ac = 1.3
            # maximum open circuit voltage
            MAX_VOC = cec_technology.V_oc_ref + cec_technology.beta_oc * (temp_air.min() - temp_ref)
            STRING_LENGTH = int(INVERTER_60K['Vdcmax'] // MAX_VOC)
            STRING_VOLTAGE = STRING_LENGTH * MAX_VOC
            STRING_OUTPUT = cec_technology.STC * STRING_LENGTH
            STRING_COUNT = int(dc_ac * INVERTER_60K['Paco'] // STRING_OUTPUT)
            DC_CAPACITY = STRING_COUNT * STRING_OUTPUT
            DCAC = DC_CAPACITY / INVERTER_60K['Paco']
            # MAX_VOC, STRING_LENGTH, STRING_VOLTAGE, STRING_OUTPUT, STRING_COUNT, DC_CAPACITY, DCAC

            # The Sandia grid inverter is a convenient model. The coefficients in the NREL SAM library are derived from
            # California Energy Commision (CEC) testing (see CEC Solar Equipment List).
            #
            # Use pvlib.inverter.sandia to calculate AC output given DC voltage and power and the inverter parameters
            # from the NREL SAM library which we downloaded earlier into INVERTER_60K for the SMA STP 60kW inverter.
            EDAILY = mpp.p_mp * STRING_LENGTH * STRING_COUNT
            AC_OUTPUT = pvlib.inverter.sandia(
                        mpp.v_mp * STRING_LENGTH, mpp.p_mp * STRING_LENGTH * STRING_COUNT, INVERTER_60K)
            AC_OUTPUT.max()
            return EDAILY, AC_OUTPUT

        def get_location_coordinate(self, coordinates):
            # from tkinter import *

            #
            # Create an instance of tkinter frame
            win = Tk()

            from geopy.geocoders import Nominatim
            # Define geometry of the window
            win.geometry("700x350")

            # Initialize Nominatim API
            geolocator = Nominatim(user_agent="MyApp")

            # Latitude & Longitude input
            # coordinates = "49.194793, -123.182710"

            location = geolocator.reverse(coordinates)

            address = location.raw['address']

            # Traverse the data
            city = address.get('city', '')
            state = address.get('state', '')
            country = address.get('country', '')

            # Create a Label widget
            label1 = Label(text="Given Latitude and Longitude: " + coordinates, font=("Calibri", 24, "bold"))
            label1.pack(pady=20)
            label2 = Label(text="The city is: " + city, font=("Calibri", 24, "bold"))
            label2.pack(pady=20)
            label3 = Label(text="The state is: " + state, font=("Calibri", 24, "bold"))
            label3.pack(pady=20)
            label4 = Label(text="The country is: " + country, font=("Calibri", 24, "bold"))
            label4.pack(pady=20)
            win.mainloop()

        def get_location_from_address(self, address):
            # from tkinter import *

            # Create an instance of tkinter frame
            win = Tk()

            from geopy.geocoders import Nominatim
            # Define geometry of the window
            win.geometry("700x350")

            # Initialize Nominatim API
            geolocator = Nominatim(user_agent="MyApp")

            location = geolocator.geocode(address)

            print("The latitude of the location is: ", location.latitude)
            print("The longitude of the location is: ", location.longitude)

            lat = location.latitude
            long = location.longitude

            label1 = Label(text="The location is: " + address, font=("Calibri", 24, "bold"))
            label1.pack(pady=20)
            label2 = Label(text="The latitude is: " + str(lat), font=("Calibri", 24, "bold"))
            label2.pack(pady=20)
            label3 = Label(text="The longitude is: " + str(long), font=("Calibri", 24, "bold"))
            label3.pack(pady=20)
            win.mainloop()
            return lat, long

        def test_1(self, cec_technology, location, latitude, longitude):
            # get some weather, before we used TMY, and then get some data from PVGIS
            data, months, inputs, meta = pvlib.iotools.get_pvgis_tmy(latitude, longitude, map_variables=False)

            # 1. get solar position
            data.index = TIMES
            solar_zenith, solar_azimuth = self.get_solar_position(latitude, longitude)

            # 2. get tracker positions
            surface_tilt, surface_azimuth, aoi = self.get_tracker_position(solar_zenith, solar_azimuth)

            # 3. get irradiance
            surface_albedo = 0.25
            temp_air = data['T2m'].values
            dni, ghi, dhi, dni_extra = self.get_irradiance(data)

            # 4. Use the Hay Davies transposition model
            poa_sky_diffuse = pvlib.irradiance.get_sky_diffuse(
                        surface_tilt, surface_azimuth, solar_zenith, solar_azimuth,
                        dni, ghi, dhi, dni_extra=dni_extra, model='haydavies')

            poa_ground_diffuse = pvlib.irradiance.get_ground_diffuse(surface_tilt, ghi, albedo=surface_albedo)
            poa = pvlib.irradiance.poa_components(aoi, dni, poa_sky_diffuse, poa_ground_diffuse)
            poa_direct = poa['poa_direct']
            poa_diffuse = poa['poa_diffuse']
            poa_global = poa['poa_global']

            iam = pvlib.iam.ashrae(aoi)
            effective_irradiance = poa_direct * iam + poa_diffuse

            # 5. module temperature
            temp_cell = pvlib.temperature.pvsyst_cell(poa_global, temp_air)

            # 6. calculate cec parameter
            cecparams = pvlib.pvsystem.calcparams_cec(
                        effective_irradiance, temp_cell,
                        cec_technology.alpha_sc, cec_technology.a_ref,
                        cec_technology.I_L_ref, cec_technology.I_o_ref,
                        cec_technology.R_sh_ref, cec_technology.R_s, cec_technology.Adjust)

            # 7. calculate DC output
            mpp = self.get_mpp(cecparams)
            self.plot_dc_energy(cec_technology["Technology"], mpp, longitude, latitude, location)
            if "Mono" in cec_technology["Technology"]:
                print("Technology1 = Mono-c-Si")
                self.mpp1 = mpp
                self.tech1 = cec_technology["Technology"]
            else:
                print("Technology2 = Multi-c-Si")
                self.mpp2 = mpp
                self.tech2 = cec_technology["Technology"]

            # 8. calculate AC output
            edaily, ac_output = self.build_pv_array(cec_technology, temp_air, mpp)
            self.plot_dc_ac_energy(cec_technology["Technology"], location, edaily, ac_output)

        def run_test(self):
            cec_technology = CECMOD_MONO_1
            # coordinates = "49.194793, -123.182710"   # vancouver
            # self.get_location_coordinate(coordinates)

            # LATITUDE, LONGITUDE = 25.252747, 55.361275,   # Dubai Airport
            # lat, long = 25.252747, 55.361275

            lat, long = self.get_location_from_address(address)   # use global from input argv
            self.test_1(cec_technology, location=address, latitude=lat, longitude=long)

            cec_technology = CECMOD_POLY_1
            self.test_1(cec_technology, location=address, latitude=lat, longitude=long)

            self.plot_dc_compare(self.mpp1, self.mpp2, address, self.tech1, self.tech2)


if __name__ == '__main__':
    address = main(sys.argv[1:])   # set global
    PVModeling().main()