#!/usr/bin/python
# -*- coding: utf-8 -*-
import numpy as np

def wheatstone(ud, u0, nref, rs1):
    """ Return wheatstone bridge unknown resistance.
    Arguments:
        ud:   Bridge voltage differential
        u0:   Reference bridge leg absolute voltage
        nref: Reference bridge leg resistance ratio
        rs1:  Measurement bridge leg series resistor
      _______
      |      |
     rs1    rs0       nref=rs0/r0
      |--ud->|..u0
     r1     r0
      |      |
      _______ ..0V
    """
    return rs1 * (u0 + ud)/(u0*nref - ud)


def ptRTD_temperature(r_x, r_0=1000.0):
    """Quadratic equation for the temperature of platinum RTDs.
    This is the inversion of the H.L.Callendar polynomial for positive
    temperatures.
    
    Result is temperature in °C according to the ITS-90 scale.

    For negative temperatures, we are adding a correction term. This is
    a fifth-order polynomial fit of the deviation of the numerically
    inverted ITS-90 standard Callendar-Van Dusen equation, using coef-
    ficient "C" for T < 0, from the second-order equation without
    coefficient "C". Source for the ITS-90 standard polynomial:
    
    http://de-de.wika.de/upload/DS_IN0029_en_co_59667.pdf
    (Verified with DIN EN 60751:2009, 2017-02-21)

    Source for the correction term:
    https://github.com/ulikoehler/UliEngineering
    """
    PT_A =  3.9083E-3
    PT_B = -5.775E-7
    # Uncorrected solution which is exact for positive temperatures
    r_norm = r_x / r_0
    theta = (- PT_A + np.sqrt(PT_A**2 - 4*PT_B*(1 - r_norm))
            ) / (2*PT_B)
    if r_norm < 1.0:
        # Polynomial correction only for negative temperatures
        correction = np.poly1d(
            [1.51892983e+00, -2.85842067e+00, -5.34227299e+00,
             1.80282972e+01, -1.61875985e+01,  4.84112370e+00]
        )
        return theta + correction(r_norm)
    else:
        return theta


def rho_water(theta):
    """5-th order polynomial for the density of water depending on the
    temperature according to the ITS-90 scale.

    Result is density in g/cm³.

    Source: Bettin, H.,"Die Dichte des Wassers als Funktion der
    Temperatur nach Einführung der Internationalen Temperaturskala
    von 1990.", PTB Mitteilungen, 1990, 100(3), pg. 195 - 196
    """
    water_num = np.poly1d([-2.8103006E-10, 1.0584601E-7, -4.6241757E-5,
                           -7.9905127E-3,  1.6952577E+1,  9.9983952E+2])
    water_denom = np.poly1d([1.6887200E+1, 1000.0])
    return water_num(theta)/water_denom(theta)

 
def c_th_water(theta):
    """Piecewise linear interpolation of the specific heat capacity of
    water for the temperature range between 0°C and 100°C

    Temp.(°C)     c(p)(J/kg/K)
    =============================
       0          4218  (liquid)
      10          4192
      20          4182
      30          4179
      40          4179
      50          4181
      60          4184
      70          4190
      80          4196
      90          4205
     100          4216  (liquid)

    Source:
    http://www.wissenschaft-technik-ethik.de/wasser_eigenschaften.html#kap04
    """
    t_ref = np.array(range(0, 110, 10))
    c_ref = np.array((4217.7, 4192.2, 4181.9, 4178.5, 4178.6, 4180.7,
                      4184.4, 4189.6, 4196.4, 4205.1, 4216.0))
    return np.interp(theta, t_ref, c_ref)


def rho_glykol60(theta):
    """Piecewise linear interpolation of the density of a 60% by volume mixture
    of ethylene glycol and water for the temperature range of -40°C to 110°C

    Source: graph data,
    BASF "GLYSANTIN Graphs", September 2016, page 3
    """
    t_ref = np.array((
        -40, -30, -20, -10, 0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 110
    ))
    rho_ref = np.array((
         1.120010, 1.114359, 1.108554, 1.102760, 1.096879, 1.090945, 1.085007,
         1.078812, 1.072367, 1.065847, 1.059047, 1.051983, 1.044773, 1.037459,
         1.030002, 1.022522
    ))
    return np.interp(theta, t_ref, rho_ref)


def c_th_glykol60(theta):
    """Piecewise linear interpolation of the specific heat capacity of
    a 60% by volume mixture of ethylene glycol and water for the temperature
    range between -40°C and 105°C

    Source: graph data,
    BASF "GLYSANTIN Graphs", September 2016, page 5 
    """
    t_ref = np.array((
        -40, -35, -30, -25, -20, -15, -10, -5, 0, 5, 10, 15, 20, 25, 30, 35,
         40, 45, 50, 55, 60, 65, 70, 75, 80, 85, 90, 95, 100, 105
    ))
    c_ref = np.array((
         2703.30, 2749.60, 2793.74, 2838.47, 2879.21, 2919.42, 2955.72, 2992.30,
         3026.66, 3059.85, 3092.32, 3122.75, 3152.32, 3181.33, 3208.28,
         3234.92, 3259.96, 3285.54, 3309.36, 3331.49, 3354.35, 3375.35,
         3396.78, 3415.90, 3435.59, 3454.44, 3471.16, 3487.49, 3503.92, 3517.87
    ))
    return np.interp(theta, t_ref, c_ref)
