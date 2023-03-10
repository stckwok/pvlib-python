"""
Calculating a module's IV curves
================================

Examples of modeling IV curves using a single-diode circuit equivalent model.
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
# This example uses :py:meth:`pvlib.pvsystem.calcparams_desoto` to calculate
# the 5 electrical parameters needed to solve the single-diode equation.
# :py:meth:`pvlib.pvsystem.singlediode` is then used to generate the IV curves.

from pvlib import pvsystem
import pandas as pd
import matplotlib.pyplot as plt

m1 = 'Trina_Solar_TSM_300DEG5C_07_II_'
m2 = 'Canadian_Solar_Inc__CS5P_220M'
cec_modules = pvsystem.retrieve_sam('CECMod')
# cec_module1 = cec_modules['Trina_Solar_TSM_300DEG5C_07_II_']
cec_module1 = cec_modules[m1]
# cec_module2 = cec_modules['Canadian_Solar_Inc__CS5P_200M']
cec_module2 = cec_modules[m2]

name = m1
use_module = cec_module1

name = m2
use_module = cec_module2

# Example module parameters for the Canadian Solar CS5P-220M:
parameters = {
    'Name': name,
    'BIPV': 'N',
    'Date': '10/5/2009',
    'T_NOCT': 42.4,
    'A_c': 1.7,
    'N_s': 96,
    # 'I_sc_ref': 5.1,
    'I_sc_ref': cec_module2['I_sc_ref'],
    # 'V_oc_ref': 59.4,
    'V_oc_ref': cec_module2['V_oc_ref'],
    # 'I_mp_ref': 4.69,
    'I_mp_ref': cec_module2['I_mp_ref'],
    # 'V_mp_ref': 46.9,
    'V_mp_ref': cec_module2['V_mp_ref'],
    'beta_oc': -0.22216,
    'alpha_sc': 0.004539,
    # 'beta_oc': -0.22216,
    # 'a_ref': 2.6373,
    'a_ref': cec_module2['a_ref'],
    # 'I_L_ref': 5.114,
    'I_L_ref': cec_module2['I_L_ref'],
    # 'I_o_ref': 8.196e-10,
    'I_o_ref': cec_module2['I_o_ref'],
    # 'R_s': 1.065,
    'R_s': cec_module2['R_s'],
    # 'R_sh_ref': 381.68,
    'R_sh_ref': cec_module2['R_sh_ref'],
    # 'Adjust': 8.7,
    'Adjust': cec_module2['Adjust'],
    # 'gamma_r': -0.476,
    'gamma_r': cec_module2['gamma_r'],
    'Version': 'MM106',
    # 'PTC': 200.1,
    'PTC': cec_module2['PTC'],
    # 'Technology': 'Mono-c-Si',
    'Technology': cec_module2['Technology'],
}

cases = [
    (1000, 55),
    (800, 55),
    (600, 55),
    (400, 25),
    (400, 40),
    (400, 55)
]

conditions = pd.DataFrame(cases, columns=['Geff', 'Tcell'])

# adjust the reference parameters according to the operating
# conditions using the De Soto model:
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
    method='lambertw'
)

# draw trend arrows
def draw_arrow(ax, label, x0, y0, rotation, size, direction):
    style = direction + 'arrow'
    bbox_props = dict(boxstyle=style, fc=(0.8, 0.9, 0.9), ec="b", lw=1)
    t = ax.text(x0, y0, label, ha="left", va="bottom", rotation=rotation,
                size=size, bbox=bbox_props, zorder=-1)

    bb = t.get_bbox_patch()
    bb.set_boxstyle(style, pad=0.6)

# plot the calculated curves:
plt.figure()

# draw arrow for incrasing values
ax = plt.gca()
draw_arrow(ax, 'Irradiance', 20, 2.5, 90, 13, 'r')
draw_arrow(ax, 'Temperature', 35, 1, 0, 13, 'l')


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
plt.gcf().set_tight_layout(True)

print(pd.DataFrame({
    'i_sc': curve_info['i_sc'],
    'v_oc': curve_info['v_oc'],
    'i_mp': curve_info['i_mp'],
    'v_mp': curve_info['v_mp'],
    'p_mp': curve_info['p_mp'],
}))
