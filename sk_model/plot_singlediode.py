#!/usr/bin/env python3

"""
CEC parameters extraction automation

Modeling IV curves using a single-diode circuit equivalent model
================================================================
Given a list of module search criteria using a parameter filter,
retrieve all PV modules from different manufacturers matching to the search criteria
then
calculate the simulated Max Power Point (MPP) under the STC conditions (1000 irradiance W/m2 and 55 deg C)
and
compare to the given MPP known from the manufacturer datasheet to get the error percentage

We can then assign a quality score to different brands based on the automated data-driven approach

"""

# %%
# Calculating a module IV curve for certain operating conditions is a two-step
# process.  Multiple methods exist for both parts of the process.  Here we use
# the De Soto model [1]_ to calculate the electrical parameters for an IV
# curve at a certain irradiance and temperature using the module's
# base characteristics at reference conditions.  Those parameters are then used
# to calculate the module's IV curve by solving the single-diode equation using
# the Lambert W method.
#
# The single-diode equation is a circuit-equivalent model of a PV
# cell and has five electrical parameters that depend on the operating
# conditions.  For more details on the single-diode equation and the five
# parameters, see the `PVPMC single diode page
# <https://pvpmc.sandia.gov/modeling-steps/2-dc-module-iv/diode-equivalent-circuit-models/>`_.
#
# References
# ----------
#  .. [1] W. De Soto et al., "Improvement and validation of a model for
#     photovoltaic array performance", Solar Energy, vol 80, pp. 78-88, 2006.
#
# Calculating IV Curves
# -----------------------
# This file uses :py:meth:`pvlib.pvsystem.calcparams_desoto` to calculate
# the 5 electrical parameters needed to solve the single-diode equation.
# :py:meth:`pvlib.pvsystem.singlediode` is then used to generate the IV curves.

from pvlib import pvsystem
import pandas as pd
import matplotlib.pyplot as plt
import urllib, json
from pv_base import PVBase

# Static csv files from data folder installed with pvLib-python (v0.9.4)
# Replace following calls with PV Free A public API for PV modeling parameters
cec_modules = pvsystem.retrieve_sam('CECMod')
cec_inverters = pvsystem.retrieve_sam('cecinverter')
cec_inverter = cec_inverters['ABB__MICRO_0_25_I_OUTD_US_208__208V_']


def get_total_pv_numbers():
    """
    Retrieve the total number of PV modules available from PV Free hosted in Azure

    Parameters
    ----------
    filter : integer
        source current Isc less than 60A (arbitrary high value so all moduel will fall below this)

    Returns
    -------
    total_number : number of modules
    """
    params = urllib.parse.urlencode({
        # 'STC__gt': 219, 'STC__lt': 221,
        'I_sc_ref__lt': 60})
    with urllib.request.urlopen(f'https://pvfree.azurewebsites.net/api/v1/cecmodule/?{params}') as fp:
        total_number = json.load(fp)
    print(f"\n\nTotal count of all modules with Isc < 60 A: {total_number['meta']['total_count']}")


def get_cecmodules(pv_params, limits=200):
    """
    Retrieve PV modules based on filter criteria

    Parameters
    ----------
    pv_params: dict of criteria
        manufacturer: name, Power Lower: integer, Upper: integer, Isc : integer

    Returns
    -------
    list of devices : dict
    """
    with urllib.request.urlopen(f'https://pvfree.azurewebsites.net/api/v1/cecmodule/?{pv_params}&limit={limits}') as fp:
        module_used = json.load(fp)

    param1 = pv_params.split("=")
    I_sc = param1[3]
    Watt = int((int(param1[1].split("&")[0]) + int(param1[2].split("&")[0])) / 2)
    # print(type(module_used))
    print(f"\n\nTotal number of PV modules" + " ({}W and ".format(Watt) +
          "Isc < {}A) ".format(I_sc) + " = {}".format(module_used['meta']['total_count']))

    if module_used['meta']['total_count'] == 0:
        print("No module found from searching criteria .... ")
        exit(0)
    else:
        print(f"====================================================================")
        total_modules = module_used['meta']['total_count']
        for i in range(total_modules):
            print("({}) ".format(i+1) + module_used['objects'][i]['Name'])
        print(f"====================================================================\n")

    # use_module = module_used['objects'][0]
    use_modules = module_used['objects']
    return use_modules


class PVPerfTest(PVBase):

    # Override the set_test_params(), add_options(), setup_chain(), setup_network()
    # and setup_nodes() methods to customize the test setup as required.

    def set_test_params(self):
        """Override test parameters for your individual test.

        This method must be overridden and num_nodes must be explicitly set."""
        self.setup_clean_chain = True

    def extract_module_params(self, use_module):
        """Extract module parameters from cec_module

        This method must be overridden and num_nodes must be explicitly set."""
        parameters = {
            # 'Name': self.name,
            'Name': use_module['Name'],
            'BIPV': use_module['BIPV'],
            'Date': use_module['Date'],
            'T_NOCT': use_module['T_NOCT'],
            'A_c': use_module['A_c'],
            'N_s': use_module['N_s'],
            'I_sc_ref': use_module['I_sc_ref'],
            'V_oc_ref': use_module['V_oc_ref'],
            'I_mp_ref': use_module['I_mp_ref'],
            'V_mp_ref': use_module['V_mp_ref'],
            'beta_oc': use_module['beta_oc'],
            'alpha_sc': use_module['alpha_sc'],
            'a_ref': use_module['a_ref'],
            'I_L_ref': use_module['I_L_ref'],
            'I_o_ref': use_module['I_o_ref'],
            'R_s': use_module['R_s'],
            'R_sh_ref': use_module['R_sh_ref'],
            'Adjust': use_module['Adjust'],
            'gamma_r': use_module['gamma_r'],
            'Version': use_module['Version'],
            'PTC': use_module['PTC'],
            # 'Technology': 'Mono-c-Si',
            'Technology': use_module['Technology'],
        }
        return parameters

    def draw_arrow(self, ax, label, x0, y0, rotation, size, direction):
        """Draw trend arrows

        This method must be overridden and num_nodes must be explicitly set."""
        style = direction + 'arrow'
        bbox_props = dict(boxstyle=style, fc=(0.8, 0.9, 0.9), ec="b", lw=1)
        t = ax.text(x0, y0, label, ha="left", va="bottom", rotation=rotation,
                    size=size, bbox=bbox_props, zorder=-1)

        bb = t.get_bbox_patch()
        bb.set_boxstyle(style, pad=0.6)

    def calcuate_errors(self, curve_info, parameters):
        """Draw trend arrows

        This method must be overridden and num_nodes must be explicitly set."""
        # print(pd.DataFrame({ 'p_mp': curve_info['p_mp'], }))
        p_mp = pd.DataFrame({'p_mp': curve_info['p_mp']}).to_dict().popitem()
        print(p_mp)
        # print(type(p_mp[1]))
        print("\nManufacturer = "
              + parameters['Name'] + "  {:.0f}-Watts".format(self.use_watt) + " (" + parameters['Technology'] + ")")

        mpp = p_mp[1][0]  # first element on the dict
        print("Mpp simulated for 'Geff = 1000 W/m^2' 'Tcell = 55C' : {:.0f} Watts".format(mpp))

        diff = mpp / self.use_watt
        diff_percent = (1-diff) * 100
        print("\nError : {:.1f} %".format(diff_percent))
        return diff_percent

    def calculate_result(self, input_module, irrad_temps, plot_graph=False):
        # module parameters for input module:
        parameters = self.extract_module_params(input_module)

        # express five primary parameters as a function of cell temperature and total absorbed irradiance
        conditions = pd.DataFrame(irrad_temps, columns=['Geff', 'Tcell'])

        # adjust the reference parameters according to the operating
        # conditions using the De Soto (five-parameters) model.
        IL, I0, Rs, Rsh, nNsVth = pvsystem.calcparams_desoto(
            conditions['Geff'],
            conditions['Tcell'],
            alpha_sc=parameters['alpha_sc'],
            a_ref=parameters['a_ref'],
            I_L_ref=parameters['I_L_ref'],
            I_o_ref=parameters['I_o_ref'],
            R_sh_ref=parameters['R_sh_ref'],
            R_s=parameters['R_s'],
            EgRef=1.121,
            dEgdT=-0.0002677
        )

        # plug the parameters into the SDE and solve for IV curves:
        curve_info = pvsystem.singlediode(
            photocurrent=IL,
            saturation_current=I0,
            resistance_series=Rs,
            resistance_shunt=Rsh,
            nNsVth=nNsVth,
            ivcurve_pnts=100,
            method='lambertw'   # lambertw, newton or brentq
        )

        if plot_graph:
            # plot the calculated curves:
            plt.figure()
            # draw arrow for increasing values
            ax = plt.gca()
            self.draw_arrow(ax, 'Irradiance', 20, 2.5, 90, 13, 'r')
            self.draw_arrow(ax, 'Temperature', 35, 1, 0, 13, 'l')

            for i, case in conditions.iterrows():
                label = (
                    "$G_{eff}$ " + f"{case['Geff']} $W/m^2$\n"
                    "$T_{cell}$ " + f"{case['Tcell']} $\\degree C$"
                )
                plt.plot(curve_info['v'][i], curve_info['i'][i], label=label)
                v_mp = curve_info['v_mp'][i]
                i_mp = curve_info['i_mp'][i]
                # mark the MPP
                plt.plot([v_mp], [i_mp], ls='', marker='o', c='k')

            plt.legend(loc=(0.86, 0.36))
            plt.xlabel('Module voltage [V]')
            plt.ylabel('Module current [A]')
            plt.title(parameters['Name'] + " (" + parameters['Technology'] + ")")
            plt.show()
            # plt.gcf().set_tight_layout(True)

        print(pd.DataFrame({
            'i_sc': curve_info['i_sc'],
            'v_oc': curve_info['v_oc'],
            'i_mp': curve_info['i_mp'],
            'v_mp': curve_info['v_mp'],
            'p_mp': curve_info['p_mp'],
        }))

        return curve_info, parameters

    def run_test(self):
        # get_total_pv_numbers()  # 21187
        self.STC_Low= 219 #59 #219
        self.STC_Hi = 221 #61 #221
        self.use_watt = (self.STC_Hi + self.STC_Low) / 2
        self.name = "Canadian Solar "
        params = urllib.parse.urlencode({
            # 'Name__istartswith': 'canadian',
            'STC__gt': self.STC_Low, 'STC__lt': self.STC_Hi,
            'I_sc_ref__lt': 6})

        cases = [
            (1000, 55), (800, 55), (600, 55), (400, 25), (400, 40), (400, 55)
        ]

        max_returns = 200
        cec_modules = get_cecmodules(params, max_returns)

        device_errors = []
        for index in range(len(cec_modules)):
            curve_info, parameters = self.calculate_result(cec_modules[index], cases)
            calculated_errs = self.calcuate_errors(curve_info=curve_info, parameters=parameters)
            name = str(parameters['Name'])
            device_errors.append((name, calculated_errs))
            # print(name + "Error % = {:.1f} %".format(calculated_errs))

        # print(device_errors)
        print("\n")
        for name, err in device_errors:
            print(name + " [Error = {:.1f}%]".format(err))

        # (1) Same Power (220W 100W 80W)
        # (2) for loop to get different manufacturer (same Power)
        # calculate mpp for each and calculate error %
        # plots (a) Error vs Brand - for 200W
        # plots (b) Error vs Brand - for 100W

        # Assign a Quality score for each brand
        # (Manufacture, Mpp, Error Diff, Quality_Score)


if __name__ == '__main__':
    PVPerfTest().main()
