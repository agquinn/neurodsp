"""Simulating time series, with periodic activity."""

import numpy as np
from numpy.random import rand, randn, randint
import pandas as pd

from neurodsp.utils.decorators import normalize
from neurodsp.sim.transients import sim_osc_cycle

###################################################################################################
###################################################################################################

@normalize
def sim_oscillation(n_seconds, fs, freq, cycle='sine', **cycle_params):
    """Simulate an oscillation.

    Parameters
    ----------
    n_seconds : float
        Signal duration, in seconds.
    fs : float
        Signal sampling rate, in Hz.
    freq : float
        Oscillation frequency.
    cycle : {'sine', 'asine', 'sawtooth', 'gaussian', 'exp', '2exp'}
        What type of oscillation cycle to simulate.
        See `sim_osc_cycle` for details on cycle types and parameters.
    **cycle_params
        Parameters for the simulated oscillation cycle.

    Returns
    -------
    osc : 1d array
        Oscillating time series.
    """

    n_cycles = int(np.ceil(n_seconds * freq))
    n_seconds_cycle = int(np.ceil(fs / freq)) / fs

    osc_cycle = sim_osc_cycle(n_seconds_cycle, fs, cycle, **cycle_params)
    osc = np.tile(osc_cycle, n_cycles)

    return osc


@normalize
def sim_jittered_oscillation(n_seconds, fs, freq, jitter=0, cycle='sine', **cycle_params):
    """Simulate an oscillation with jitter.

    # THIS 'CONVOLUITON APPROACH' GENERALIZE WITH KERNEL APPROACH.

    Parameters
    ----------
    n_seconds : float
        Simulation time, in seconds.
    fs : float
        Sampling rate of simulated signal, in Hz.
    freq : float
        Frequency of simulated oscillation, in Hz.
    jitter : float
        Maximum jitter of oscillation period, in seconds.
    cycle : {'sine', 'asine', 'sawtooth', 'gaussian', 'exp', '2exp'}
        What type of oscillation cycle to simulate.
        See `sim_osc_cycle` for details on cycle types and parameters.
    **cycle_params
        Parameters for the simulated oscillation cycle.

    Returns
    -------
    sig: 1d array
        Simulated oscillation with jitter.
    """

    n_cycles = int(np.ceil(n_seconds * freq))
    n_seconds_cycle = int(np.ceil(fs / freq)) / fs

    # Create a single cycle of the oscillation
    osc_cycle = sim_osc_cycle(n_seconds_cycle, fs, cycle, **cycle_params)

    # Binary "spike-train" of when each cycle should occur & oscillation "event" indices
    spks = np.zeros(int(n_seconds * fs + len(osc_cycle)) - 1)
    osc_period = int(fs / freq)
    spk_indices = np.arange(osc_period, len(spks), osc_period)

    # Add jitter to "spike" indices
    if jitter != 0:
        spk_indices = spk_indices + \
            randint(low=-int(fs * jitter), high=int(fs * jitter), size=len(spk_indices))

    spks[spk_indices] = 1
    sig = np.convolve(spks, osc_cycle, 'valid')

    return sig


@normalize
def sim_bursty_oscillation(n_seconds, fs, freq, enter_burst=.2, leave_burst=.2,
                           cycle='sine', **cycle_params):
    """Simulate a bursty oscillation.

    Parameters
    ----------
    n_seconds : float
        Simulation time, in seconds.
    fs : float
        Sampling rate of simulated signal, in Hz
    freq : float
        Oscillation frequency, in Hz.
    enter_burst : float
        Probability of a cycle being oscillating given the last cycle is not oscillating.
    leave_burst : float
        Probability of a cycle not being oscillating given the last cycle is oscillating.
    cycle : {'sine', 'asine', 'sawtooth', 'gaussian', 'exp', '2exp'}
        What type of oscillation cycle to simulate.
        See `sim_osc_cycle` for details on cycle types and parameters.
    **cycle_params
        Parameters for the simulated oscillation cycle.

    Returns
    -------
    sig : 1d array
        Bursty oscillation.

    Notes
    -----
    * This function takes a 'tiled' approach to simulating cycles, with evenly spaced
    and consistent cycles across the whole signal, that are either oscillating or not.
    * If the cycle length does not fit evenly into the simulated data length,
    then the last few cycle will be non-oscillating.
    """

    # Determine number of samples & cycles
    n_samples = int(n_seconds * fs)
    n_seconds_cycle = (1/freq * fs)/fs

    # Make a single cycle of an oscillation
    osc_cycle = sim_osc_cycle(n_seconds_cycle, fs, cycle, **cycle_params)
    n_samples_cycle = len(osc_cycle)
    n_cycles = int(np.floor(n_samples / n_samples_cycle))

    # Determine which periods will be oscillating
    is_oscillating = _make_is_osc(n_cycles, enter_burst, leave_burst)

    # Fill in the signal with cycle oscillations, for all bursting cycles
    sig = np.zeros([n_samples])
    for is_osc, cycle_ind in zip(is_oscillating, range(0, n_samples, n_samples_cycle)):
        if is_osc:
            sig[cycle_ind:cycle_ind+n_samples_cycle] = osc_cycle

    return sig


@normalize
def sim_bursty_oscillation_features(n_seconds, fs, freq, rdsym=.5, enter_burst=.2, leave_burst=.2,
                                    cycle_features=None, return_cycle_df=False, n_tries=5):
    """Simulate a bursty oscillation, with defined cycle features.

    # NEEDS REFACTORING TO USE KERNEL APPROACH
    # WHEN DONE, THIS SHOULD BE ABLE TO MERGE TO SIM_BURSTY_OSCILLATION

    Parameters
    ----------
    n_seconds : float
        Simulation time, in seconds.
    fs : float
        Sampling rate of simulated signal, in Hz
    freq : float
        Oscillation frequency, in Hz.
    rdsym : float
        Rise-decay symmetry of the oscillation, as fraction of the period in the rise time:

        - = 0.5: symmetric (sine wave)
        - < 0.5: shorter rise, longer decay
        - > 0.5: longer rise, shorter decay
    enter_burst : float
        Probability of a cycle being oscillating given the last cycle is not oscillating.
    leave_burst : float
        Probability of a cycle not being oscillating given the last cycle is oscillating.
    cycle_features : dict
        Specifies the mean and standard deviations (within and across bursts) of each cycle's
        amplitude, period, and rise-decay symmetry. This can include a complete or incomplete
        set (using defaults) of the following keys:

        * amp_mean: mean cycle amplitude
        * amp_std: standard deviation of cycle amplitude
        * amp_burst_std: standard deviation of mean amplitude for each burst
        * period_mean: mean period (computed from `freq`)
        * period_std: standard deviation of period (samples)
        * period_burst_std: standard deviation of mean period for each burst
        * rdsym_mean: mean rise-decay symmetry
        * rdsym_std: standard deviation of rdsym
        * rdsym_burst_std: standard deviation of mean rdsym for each burst
    return_cycle_df : bool
        If True, return the dataframe that contains the simulation parameters for each cycle.
        This may be useful for computing power, for example, as the power of the oscillation
        should only be considered over the times where there are bursts.
    n_tries : int, optional, default=5
        Number of times to try to resimulate cycle features when an
        invalid value is returned before raising an user error.

    Returns
    -------
    sig : 1d array
        Bursty oscillation.
    df : pd.DataFrame
        Cycle-by-cycle properties of the simulated oscillation.
        Only returned if `return_cycle_df` is True.
    """

    # Define default parameters for cycle features
    mean_period_samples = int(fs / freq)
    cycle_features_use = {'amp_mean': 1, 'amp_burst_std': 0, 'amp_std': 0,
                          'period_mean': mean_period_samples, 'period_burst_std': 0, 'period_std': 0,
                          'rdsym_mean': rdsym, 'rdsym_burst_std': 0, 'rdsym_std': 0}

    # Overwrite default cycle features with those specified
    if cycle_features is not None:
        for k in cycle_features:
            cycle_features_use[k] = cycle_features[k]

    # Determine number of cycles to generate
    n_samples = int(n_seconds * fs)
    n_cycles_overestimate = int(np.ceil(n_samples / mean_period_samples * 2))

    # Determine which periods will be oscillating and the cycle properties for each cycle
    is_oscillating = _make_is_osc(n_cycles_overestimate, enter_burst, leave_burst)
    periods, amps, rdsyms = _determine_cycle_properties(is_oscillating, cycle_features_use, n_tries)

    # Set up the dataframe of parameters
    df = pd.DataFrame({'is_cycle': is_oscillating, 'period': periods,
                       'amp': amps, 'rdsym': rdsyms})
    df['start_sample'] = np.insert(df['period'].cumsum().values[:-1], 0, 0)
    df = df[df['start_sample'] < n_samples]

    # Create the signal
    sig = _sim_cycles(df)
    sig = sig[:n_samples]

    if return_cycle_df:
        # Shorten df to only cycles that are included in the data
        df.drop(df.index[len(df) - 1], inplace=True)
        return sig, df
    else:
        return sig

###################################################################################################
###################################################################################################

def _make_is_osc(n_cycles, enter_burst, leave_burst):
    """Create a vector describing if each cycle is oscillating, for bursting oscillations."""

    is_oscillating = [None] * (n_cycles)
    is_oscillating[0] = False

    for ii in range(1, n_cycles):

        rand_num = rand()

        if is_oscillating[ii-1]:
            is_oscillating[ii] = rand_num > leave_burst
        else:
            is_oscillating[ii] = rand_num < enter_burst

    return is_oscillating



def _determine_cycle_properties(is_oscillating, cycle_features, n_tries):
    """Calculate the properties for each cycle."""

    periods = np.zeros_like(is_oscillating, dtype=int)
    amps = np.zeros_like(is_oscillating, dtype=float)
    rdsyms = np.zeros_like(is_oscillating, dtype=float)

    for ind, is_osc in enumerate(is_oscillating):

        if is_osc is False:
            period = cycle_features['period_mean'] + randn() * cycle_features['period_std']
            amp = np.nan
            rdsym = np.nan

            cur_burst = {'period_mean' : np.nan, 'amp_mean' : np.nan, 'rdsym_mean' : np.nan}

        else:

            if np.isnan(cur_burst['period_mean']):

                cur_burst['period_mean'] = cycle_features['period_mean'] + randn() \
                    * cycle_features['period_burst_std']
                cur_burst['amp_mean'] = cycle_features['amp_mean'] + randn() \
                    * cycle_features['amp_burst_std']
                cur_burst['rdsym_mean'] = cycle_features['rdsym_mean'] + randn() \
                    * cycle_features['rdsym_burst_std']

            # Simulate for n_tries to get valid features
            #   After which, if any params are still negative, raise error
            for n_try in range(n_tries):

                period = cur_burst['period_mean'] + randn() * cycle_features['period_std']
                amp = cur_burst['amp_mean'] + randn() * cycle_features['amp_std']
                rdsym = cur_burst['rdsym_mean'] + randn() * cycle_features['rdsym_std']

                if period > 0 and amp > 0 and rdsym > 0 and rdsym < 1:
                    break

            # If did not break out of the for loop, no valid features were found
            else:

                # Check which features are invalid - anything below 0, and rdsym above 1
                features_invalid = [label for label in ['period', 'amp', 'rdsym'] if eval(label) < 0]
                features_invalid = features_invalid + ['rdsym'] if rdsym > 1 else features_invalid

                raise ValueError("""A cycle was repeatedly simulated with invalid feature(s)
                                    for: {} (e.g. less than 0). Please change per-cycle
                                    distribution parameters (mean & std) and restart
                                    simulation.""".format(', '.join(features_invalid)))

        periods[ind] = int(period)
        amps[ind] = amp
        rdsyms[ind] = rdsym

    return periods, amps, rdsyms


def _sim_cycles(df):
    """Simulate cycle time series, given a set of parameters for each cycle."""

    sig = np.array([])
    last_cycle_oscillating = False

    for ind, row in df.iterrows():

        if row['is_cycle'] is False:

            # If last cycle was oscillating, add a decay to 0 then 0s
            if last_cycle_oscillating:
                decay_pha = np.linspace(0, np.pi / 2, int(row['period'] / 4))
                decay_t = np.cos(decay_pha) * sig[-1]
                sig = np.append(sig, decay_t)

                cycle_t = np.zeros(row['period'] - int(row['period'] / 4))
                sig = np.append(sig, cycle_t)

            else:

                # Add a blank cycle
                cycle_t = np.zeros(row['period'])
                sig = np.append(sig, cycle_t)

            last_cycle_oscillating = False

        else:

            # If last cycle was oscillating, add a decay to 0
            if not last_cycle_oscillating:

                rise_pha = np.linspace(-np.pi / 2, 0, int(row['period'] / 4))[1:]
                rise_t = np.cos(rise_pha) * row['amp']

                if len(rise_pha) > 0:
                    sig[-len(rise_t):] = rise_t

            # Add a cycle with rdsym
            rise_samples = int(np.round(row['period'] * row['rdsym']))
            decay_samples = row['period'] - rise_samples
            pha_t = np.hstack([np.linspace(0, np.pi, decay_samples + 1)[1:],
                               np.linspace(-np.pi, 0, rise_samples + 1)[1:]])
            cycle_t = np.cos(pha_t)

            # Adjust decay if the last cycle was oscillating
            if last_cycle_oscillating:

                scaling = (row['amp'] + sig[-1]) / 2
                offset = (sig[-1] - row['amp']) / 2
                cycle_t[:decay_samples] = cycle_t[:decay_samples] * scaling + offset
                cycle_t[decay_samples:] = cycle_t[decay_samples:] * row['amp']

            else:
                cycle_t = cycle_t * row['amp']

            sig = np.append(sig, cycle_t)
            last_cycle_oscillating = True

    return sig