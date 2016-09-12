import os
import subprocess
import settings.settings as s
import numpy as np
import matplotlib.pyplot as plt

"""
File with commonly used functions.
"""

def read_from_file():
    '''
    Reads all solved network files in the 'nodes_folder' set in 'settings.py'.
    Returns a list of dictionaries with the values from the files in the form:
        [{'c':'u', 'f':'s', 'a':1.00, 'g':1.00, 'b':1.00},
            {'c':'c', 'f':'s', 'a':1.00, 'g':1.00, 'b':1.00}]
    '''
    filename_list = os.listdir(s.nodes_folder)
    all_combinations = []
    for name in filename_list:
        all_combinations.append({'c':name[0],
                                 'f':name[2],
                                 'a':float(name[5:9]),
                                 'g':float(name[11:15]),
                                 'b':float(name[17:21])})
    return all_combinations


def get_chosen_combinations(**kwargs):
    '''
    Function that extracts the wanted files in the 'self.all_combinations list'.

    To choose all the solved networks in the synchronized flow scheme:
        "self.get_chosen_combinations(f='s')".

    All unconstrained networks with a gamma = 1.00 can be found by:
        self.get_chosen_combinations(c='u', g=1.00)

    returns a list of dictionaries with the desired values.
    For instance:
        [{'c':'u', 'f':'s', 'a':1.00, 'g':1.00, 'b':1.00},
            {'c':'c', 'f':'s', 'a':0.80, 'g':1.00, 'b':0.50}
            ...]
    '''
    def _check_in_dict(dic, kwargs):
        """ Check if values are present in a dictionary.

        Args:
            dic: dictionary to check in.
            kwargs: the keyword arguments to check for in the dictionary.
        Returns:
            boolean: True if all values are present in the dictionary, False if any are not.
        """
        for (name, value) in kwargs.items():
            value = np.array(value)
            if not dic[name] in value:
                return False
        return True

    chosen_combinations = []
    # Checking all combinations.
    for combination in read_from_file():

        if _check_in_dict(combination, kwargs):
            chosen_combinations.append(combination)

    if len(chosen_combinations) == 0:
        # Raise error if no chosen combinations are found.
        raise ValueError('No files with {0} found!'.format(kwargs))
    return chosen_combinations


def quantile(quantile, dataset):
    """
    Docstring for quantile.
    Args:
        quantile [float]: the desired quantile eg. 0.99.
        dataset [list/1-dimensional array]: a timeseries.
    """
    return np.sort(dataset)[int(round(quantile*len(dataset)))]


def quantile_old(quantile, dataset, cutzeros=False):
    """
    Takes a list of numbers, converts it to a list without zeros
    and returns the value of the 99% quantile.
    """
    if cutzeros:
        # Removing zeros
        dataset = dataset[np.nonzero(dataset)]
    # Convert to numpy histogram
    hist, bin_edges = np.histogram(dataset, bins = 10000, normed = True)
    dif = np.diff(bin_edges)[0]
    q = 0
    for index, val in enumerate(reversed(hist)):
        q += val*dif
        if q > 1 - float(quantile):
            #print 'Found %.3f quantile' % (1 - q)
            return bin_edges[-index]

def storage_size(backup_without_storage,
                 backup_beta_capacity,
                 curtailment=np.array([]), 
                 eta_in=1.0, 
                 eta_out=1.0,
                 charging_capacity=np.inf,
                 discharging_capacity=np.inf):
    '''
    Function that calculates the storage time series.

    parameters:
        backup_without_storage: sequence (list, tuple, array) | time series for the backup generation
        in units of mean load.
        backup_beta_capacity: number | backup capacity in units of mean load.
        curtailment: sequence(list, tuple, array) | time series for the curtailment. Can be omitted.
        eta_in: number between 0 and 1 | charging efficiency.
        eta_out: number between 0 and 1 | discharging efficiency.
        charging_capacity: number | the maximum allowed charging capacity in units of mean load.
        discharging_capacity: number | the maximum allowed discharging capacity in units of mean load.

    returns:
        K_SE: numpy array | storage energy capacity i.e. lowest point in storage time series.
        S: numpy array | storage filling level time series.
        B_storage: numpy array | the backup generation timeseries with a storage.
    '''
    B = np.array(backup_without_storage)
    B_storage = np.empty_like(backup_without_storage)
    KB = backup_beta_capacity
    KSPc = charging_capacity
    KSPd = - discharging_capacity

    # Check if curtailment is not zero - i.e. we consider curtailment.
    if curtailment.any():
        C = np.array(curtailment)
    else:
        C = np.zeros_like(B)

    # The initial maximum level of the emergency storage.
    S_max = 0
    # The storage filling level time series.
    S = np.empty_like(B)

    for t, (b, c) in enumerate(zip(B, C)):
        K_C_B = KB + c - b
        if K_C_B < 0: # If the backup > capacity + curtailment = discharging storage
            if t == 0:
                s = np.min((S_max, (eta_out ** - 1) * K_C_B))
                S[t] = np.max((s, KSPd))
            else:
                s = np.min((S_max, S[t - 1] + (eta_out ** - 1) * K_C_B))
                S[t] = np.max((s, KSPd + S[t - 1]))
        else: # If backup < capacity + curtailment = charging storage
            if t == 0:
                s = np.min((S_max, (eta_in) * K_C_B))
                S[t] = np.min((s, KSPc))
            else:
                s = np.min((S_max, S[t - 1] + (eta_in) * K_C_B))
                S[t] = np.min((s, KSPc + S[t - 1]))

        # Calculate the new backup generation time series
        if b > KB:
            B_storage[t] = KB
        else:
            if np.abs(S[t]) > KB - b:
                B_storage[t] = KB
            else:
                B_storage[t] = b + np.abs(S[t])

    # Storage energy capacity
    K_SE = S_max - np.min(S)

    return(K_SE, S, B_storage)

def convert_to_exp_notation(number, print_it=False):
    n = '{:.2E}'.format(number)
    if print_it:
        print(n)
    return n


def get_remote_figures():
    if not os.path.exists(s.remote_figures):
        os.mkdir(s.remote_figures)
    """Copy figures from the result-folder on a remote server"""
    os.system('scp -r {0}. {1}'.format(s.remote_figures_folder, s.remote_figures))
    return


def load_remote_network(filename, N_or_F='N'):
    '''
    Function that copies a given solved network- or flow-object from the remote server
    to a local temp-folder and returns the loaded object.

    parameters:
        filename: string | the name of the object without the suffix and extension:
        'c_s_a0.80_g1.00_b1.00'
        N_or_F:   string | whether you want the network- or flow-object returned.

    returns:
        temp_load: numpy_object | the contents of the chosen file.

    '''

    file_to_check = filename + '_{}.npz'.format(N_or_F)

    print('\nChecking for file {} on server...'.format(file_to_check))
    remote_path = '/home/kofoed/emergency_backup/results/{}/'.format(N_or_F)
    command = 'ssh {0} ls {1}'.format(s.remote_ip, remote_path)
    p = subprocess.Popen(command,
                         universal_newlines=True,
                         shell=True, stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE)
    out, err = p.communicate()
    files_list = out.split()

    if file_to_check in files_list:
        print('\nFound file on server - copying to temp-directory...')
        filename_total = '{0}:{1}{2}'.format(s.remote_ip, remote_path, file_to_check)
        p2 = subprocess.Popen(['scp', filename_total, 'temp/temp.npz'])
        sts = os.waitpid(p2.pid, 0)

        temp_load = np.load('temp/temp.npz')
        return(temp_load)
    else:
#         print('Did NOT find file')
        raise IOError('No file named {0} on server {1}.'.format(filename, s.remote_ip))


def find_minima(timeseries):
    '''
    Function that takes a timeseries and find the minimum in each connected event (the bottom of the
    dips).

    parameters:
        timeseries: list | a timeseries (here the non-served energy).
    returns:
        minima: list | a list of the minima in the clustered events.
    '''
    intervals = []
    interval = []
    minima = []

    nonzero = np.nonzero(timeseries)[0]
    diff = np.diff(nonzero)

    for i, d in enumerate(diff):
        interval.append(nonzero[i])
        if d != 1:
            intervals.append(interval)
            interval = []

    if nonzero[-1] - nonzero[-2] == 1:
        interval.append(nonzero[-1])
        intervals.append(interval)
    else:
        intervals.append([nonzero[-1]])

    for interval in intervals:
        minima.append(np.min(timeseries[interval]))

    return(np.array(minima))

def annuity(n, r):
    '''
    '''
    return r/(1. -1./(1.+r)**n)

def diff_max_min(timeseries):
    '''
    Finding the biggest positive and negative gradients of a timeseries.
    '''
    timeseries_diff = np.diff(timeseries)
    diff_max = np.max(timeseries_diff)
    diff_min = -np.min(timeseries_diff)
    argmax = np.argmax(timeseries_diff)
    argmin = np.argmin(timeseries_diff)
    return((diff_max, diff_min), (argmax, argmin))

def get_objectives(S, eta_in=1, eta_out=1):
        K_SE = -np.min(S)
        diff = np.diff(S)
        K_SPc = np.max(diff) / eta_in
        K_SPd = -np.min(diff) * eta_out
        return(K_SE, K_SPc, K_SPd)

def fancy_histogram(array, bins=10, density=False, range=None):
    '''
    Outputs the bin edges of np.histogram as well as the y-values
    corresponding to the edges, instead of the y-values in 
    between the edges.

    Example
    -------
    hist, bin_edges = fancy_histogram(array)
    plt.plot(bin_edges, hist, 'b-')
    '''
    hist, bin_edges = np.histogram(array, bins=bins, range=range,
                                   density=density)
    left, right = bin_edges[:-1], bin_edges[1:]
    X = np.array([left, right]).T.flatten()
    Y = np.array([hist, hist]).T.flatten()

    return Y, X
    


